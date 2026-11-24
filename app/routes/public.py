from datetime import datetime, date
from flask import Blueprint, render_template, url_for, flash, redirect, request, jsonify, session, abort
from flask_babel import gettext as _, get_locale
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from app import db, bcrypt, limiter
from app.models import (
    User, Subject, ExamResult, SiteInfo, Page, Question,
    PageComment, AdminNotification, TeacherNotification, SubjectTeacher,
    Student, PrivateExam, CommentGuest, ExamGuest, calculate_age
)
from app.forms import SetupForm, CommentForm, CommentReplyForm
from app.routes.helpers import (
    can_edit_subject, can_student_access_subject, get_reply_display_name,
    get_comment_author_profile_url, generate_comment_guest_code, generate_exam_guest_code
)

public = Blueprint('public', __name__)

# ==============================================================================
# SECTION 1: SYSTEM UTILITIES & CORE SETUP
# ==============================================================================

@public.route('/keep_alive')
def keep_alive():
    """
    THE HEARTBEAT ROUTE (The 'Secret Door')

    Purpose:
    This route provides a lightweight endpoint for UptimeRobot to ping.
    It resets the PythonAnywhere sleep timer without querying the database.

    Returns:
        JSON response indicating server health.
    """
    return jsonify(
        status="alive",
        timestamp=datetime.utcnow().isoformat(),
        version="2.0.4",
        message="StatInfoPRO System is active."
    )


@public.route('/setup', methods=['GET', 'POST'])
@limiter.limit("10/minute")
def setup():
    """
    SYSTEM INITIALIZATION ROUTE

    Purpose:
    Allows the creation of the primary Administrator (Headmaster).
    Blocked once an admin already exists in the system.
    """
    # 1. Verification: Does an administrator already exist?
    existing_admin = User.query.filter_by(is_admin=True).first()

    if existing_admin:
        flash(_('System is already initialized. Access to setup is restricted.'), 'warning')
        return redirect(url_for('auth.login'))

    # 2. Setup Form
    form = SetupForm()

    # 3. Validation and User Creation
    if form.validate_on_submit():

        # Verify email uniqueness
        check_email = User.query.filter_by(email=form.email.data).first()
        if check_email:
            flash(_('Error: This email is already registered in our systems.'), 'danger')
            return render_template('setup.html', form=form)

        # Secure password hashing using Bcrypt
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')

        # Create user object
        master_admin = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=hashed_password,
            is_admin=True
        )

        try:
            db.session.add(master_admin)
            db.session.commit()
            flash(_('Admin Account Created! Please login to begin managing the school.'), 'success')
            return redirect(url_for('auth.login'))
        except Exception as database_error:
            db.session.rollback()
            flash(_('Critical Database Error: %(error)s', error=str(database_error)), 'danger')

    return render_template('setup.html', form=form)


# ==============================================================================
# SECTION 2: PUBLIC USER INTERFACE
# ==============================================================================

@public.route('/')
def index():
    """
    HOMEPAGE

    Lists all academic subjects currently offered, with support for search.
    """
    search_query = request.args.get('q', '').strip()
    
    if search_query:
        subject_list = Subject.query.filter(
            Subject.is_public == True,
            or_(
                Subject.name.ilike(f'%{search_query}%'),
                Subject.name_kurdish.ilike(f'%{search_query}%'),
                Subject.description.ilike(f'%{search_query}%'),
                Subject.description_kurdish.ilike(f'%{search_query}%')
            )
        ).all()
        
        page_list = Page.query.join(Subject).filter(
            Subject.is_public == True,
            or_(
                Page.title.ilike(f'%{search_query}%'),
                Page.title_kurdish.ilike(f'%{search_query}%'),
                Page.content_body.ilike(f'%{search_query}%'),
                Page.content_body_kurdish.ilike(f'%{search_query}%')
            )
        ).all()
    else:
        subject_list = Subject.query.filter_by(is_public=True).all()
        page_list = []

    return render_template('index.html', subjects=subject_list, pages=page_list, search_query=search_query)


@public.route('/about')
def about():
    """
    ABOUT US PAGE

    Content is dynamically fetched from the SiteInfo model.
    """
    site_content = SiteInfo.query.filter_by(key='about').first()
    return render_template('about.html', info=site_content)


@public.route('/public/stats')
def public_stats():
    """
    ANALYTICS OVERVIEW (PUBLIC)

    Calculates high-level metrics for public display using SQL aggregations.
    """
    lang = get_locale().language

    # 1. Subject performance aggregation (bilingual subject names)
    subject_scores = db.session.query(
        Subject,
        func.avg(ExamResult.score)
    ).join(ExamResult).group_by(Subject.id).all()

    # 2. Extract localized labels and rounded values for Chart.js
    chart_labels = [row[0].display_name(lang) for row in subject_scores]
    chart_values = [round(row[1], 1) for row in subject_scores]

    # 3. Global counters
    total_completed_exams = ExamResult.query.count()
    total_subjects_count = Subject.query.count()

    # 4. Global Average score
    avg_aggregate = db.session.query(func.avg(ExamResult.score)).scalar()
    global_average_percent = round(avg_aggregate, 1) if avg_aggregate else 0

    # 5. Success/Failure metrics
    passing_grade_count = ExamResult.query.filter(ExamResult.score >= 50).count()
    failing_grade_count = ExamResult.query.filter(ExamResult.score < 50).count()

    return render_template(
        'stats.html',
        labels=chart_labels,
        values=chart_values,
        total_exams=total_completed_exams,
        total_subjects=total_subjects_count,
        global_average=global_average_percent,
        pass_count=passing_grade_count,
        fail_count=failing_grade_count
    )

@public.route('/test-lang')
@login_required
def test_lang():
    """
    Admin-only test route to verify translations are working correctly.
    This helps debug language switching issues.
    """
    if not current_user.is_admin:
        abort(403)

    from flask import current_app
    from flask_babel import get_locale
    
    current_app.logger.info(f"test_lang: Current locale from get_locale(): {get_locale()}")
    current_app.logger.info(f"test_lang: Session contents: {dict(session)}")
    current_app.logger.info(f"test_lang: Session lang: {session.get('lang')}")
    
    # Test some translations
    test_translations = {
        'welcome': _('Welcome'),
        'toggle_language': _('Toggle Language'),
        'home': _('Home'),
        'about_us': _('About Us')
    }
    
    return {
        'current_locale': str(get_locale()),
        'session_lang': session.get('lang'),
        'translations': test_translations,
        'is_rtl': get_locale().language == 'ku'
    }


@public.route('/set-lang/<lang>')
def set_lang(lang):
    """
    Sets the user's preferred language.
    Stored in session FIRST (always), then persisted to DB for cross-device use.
    """
    from flask import current_app
    from flask_babel import refresh

    ALLOWED_LANGS = ['en', 'ku']

    current_app.logger.info(f"set_lang called with lang='{lang}'")
    current_app.logger.info(f"Current session before change: {dict(session)}")

    if lang not in ALLOWED_LANGS:
        flash(_('Invalid language selected.'), 'danger')
        current_app.logger.error(f"Invalid language '{lang}' attempted")
        return redirect(request.referrer or url_for('public.index'))
    
    # 1. SESSION FIRST — this is the single source of truth for select_locale()
    session['lang'] = lang
    current_app.logger.info(f"set_lang: session['lang'] set to '{lang}'")
    current_app.logger.info(f"Session after change: {dict(session)}")

    # 2. Persist to DB for cross-device/cross-session recall
    if current_user and current_user.is_authenticated and hasattr(current_user, 'preferred_lang'):
        try:
            current_user.preferred_lang = lang
            db.session.commit()
            current_app.logger.info(f"set_lang: User {current_user.id} preferred_lang updated to '{lang}'")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"set_lang: Failed to update user preferred_lang: {e}")
    
    # 3. FORCE REFRESH BABEL CACHE - This is the key fix!
    try:
        refresh()
        current_app.logger.info("set_lang: Babel cache refreshed successfully")
    except Exception as e:
        current_app.logger.warning(f"set_lang: Failed to refresh Babel cache: {e}")
    
    flash(_('Language changed successfully.'), 'success')
    current_app.logger.info(f"Language successfully changed to '{lang}', redirecting to: {request.referrer or url_for('public.index')}")
    return redirect(request.referrer or url_for('public.index'))


# ==============================================================================
# SECTION 3: COURSE & LECTURE BROWSING
# ==============================================================================

@public.route('/subject/<slug>')
def subject_detail(slug):
    """
    SUBJECT REPOSITORY VIEW

    Lists all lectures (Pages) within a specific subject.
    Open to visitors and staff.
    Shows ONLY currently assigned teachers who opted to show their name.
    """
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()

    # Visibility Check: If hidden, restrict access to staff only
    if not target_subject.is_public and not current_user.is_authenticated:
        abort(403)

    current_assignments = SubjectTeacher.query.filter_by(subject_id=target_subject.id).all()
    visible_teachers = [a.teacher for a in current_assignments if a.show_name and a.teacher]
    can_edit = current_user.is_authenticated and can_edit_subject(target_subject)

    return render_template(
        'subject.html',
        subject=target_subject,
        visible_teachers=visible_teachers,
        can_edit=can_edit,
        new_exam_guest_code=session.pop('new_exam_guest_code', None)
    )


@public.route('/teacher/<int:user_id>/profile')
def teacher_public_profile(user_id):
    """
    PUBLIC TEACHER PROFILE PAGE (With Granular Teacher Privacy Controls)
    Returns 404 to non-admin visitors if teacher disabled `profile_public`.
    """
    teacher = User.query.get_or_404(user_id)
    is_privileged = current_user.is_authenticated and (current_user.is_admin or current_user.id == teacher.id)
    if not bool(teacher.profile_public) and not is_privileged:
        abort(404)

    public_subjects = []
    if teacher.profile_show_name:
        assigns = SubjectTeacher.query.filter_by(teacher_id=teacher.id, show_name=True).all()
        public_subjects = [a.subject for a in assigns if a.subject and a.subject.is_public]

    return render_template(
        'teacher_profile.html',
        teacher=teacher,
        public_subjects=public_subjects
    )


@public.route('/subject/<slug>/page/<int:page_id>')
def view_page(slug, page_id):
    """
    LECTURE / CHAPTER CONTENT VIEW

    Displays bilingual content, clickable teachers, attached resources, and threaded comments.
    """
    target_lecture = Page.query.get_or_404(page_id)
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()

    if not target_subject.is_public and not current_user.is_authenticated:
        abort(403)

    if target_lecture.subject_id != target_subject.id:
        abort(404)

    specific_questions_exist = Question.query.filter_by(
        page_id=target_lecture.id
    ).first() is not None

    current_assignments = SubjectTeacher.query.filter_by(subject_id=target_subject.id).all()
    visible_teachers = [a.teacher for a in current_assignments if a.show_name and a.teacher]

    # Fetch top-level comments (replies are eager/lazy accessed via c.replies)
    comments = PageComment.query.filter_by(
        page_id=target_lecture.id,
        parent_id=None
    ).order_by(PageComment.created_at.desc()).all()
    comment_form = CommentForm()
    reply_form = CommentReplyForm()

    can_moderate = current_user.is_authenticated and can_edit_subject(target_subject)
    new_comment_guest_code = session.pop('new_comment_guest_code', None)
    new_exam_guest_code = session.pop('new_exam_guest_code', None)

    return render_template(
        'page.html',
        page=target_lecture,
        subject=target_subject,
        visible_teachers=visible_teachers,
        has_quiz=specific_questions_exist,
        comments=comments,
        comment_form=comment_form,
        reply_form=reply_form,
        can_moderate=can_moderate,
        new_comment_guest_code=new_comment_guest_code,
        new_exam_guest_code=new_exam_guest_code,
        get_reply_display_name=get_reply_display_name,
        get_comment_author_profile_url=get_comment_author_profile_url
    )


@public.route('/subject/<slug>/page/<int:page_id>/comment', methods=['POST'])
@limiter.limit("15/minute")
def add_page_comment(slug, page_id):
    """
    PUBLIC & STAFF LECTURE COMMENT SUBMISSION (v0.9.1)

    - Logged-in Teacher/Admin: posts directly with zero extra questions.
    - Guest: supplies Name/Birth Date/Optional Personality (with optional 8-char code generation)
      OR reuses a previously generated 8-char CommentGuest code.
    """
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()
    target_lecture = Page.query.get_or_404(page_id)

    if not target_subject.is_public and not current_user.is_authenticated:
        abort(403)

    if target_lecture.subject_id != target_subject.id:
        abort(404)

    dest_url = url_for('public.view_page', slug=slug, page_id=page_id) + '#comments-section'

    # 1. Direct staff comment (logged-in Teacher or Admin — no extra info asked)
    if current_user.is_authenticated:
        comment_text = (request.form.get('comment_text') or '').strip()
        if not comment_text:
            flash(_('Comment text cannot be empty.'), 'danger')
            return redirect(dest_url)

        staff_comment = PageComment(
            page_id=target_lecture.id,
            parent_id=None,
            author_user_id=current_user.id,
            is_teacher_reply=True,
            is_read_by_admin=True,
            author_name=current_user.username,
            author_birth_date=current_user.birth_date,
            author_age=current_user.age,
            comment_text=comment_text
        )
        try:
            db.session.add(staff_comment)
            db.session.commit()
            flash(_('Your comment has been posted!'), 'success')
        except Exception as e:
            db.session.rollback()
            flash(_('Error posting comment: %(error)s', error=str(e)), 'danger')
        return redirect(dest_url)

    # 2. Guest Comment (Details + Optional Code OR Existing 8-char Comment Guest Code)
    guest_mode = (request.form.get('guest_mode') or 'details').strip().lower()
    raw_comment_code = (request.form.get('comment_guest_code') or '').strip().upper()

    comment_guest_id = None
    generated_code = None
    author_name = None
    birth_date = None
    computed_age = None
    personality_info = None
    comment_text = None

    if guest_mode == 'code' or raw_comment_code:
        comment_text = (request.form.get('comment_text') or '').strip()
        if not comment_text:
            flash(_('Comment text cannot be empty.'), 'danger')
            return redirect(dest_url)
        cg = CommentGuest.query.filter_by(guest_code=raw_comment_code).first() if raw_comment_code else None
        if not cg:
            flash(_('Invalid Comment Guest Code. Please check your 8-character code.'), 'danger')
            return redirect(dest_url)
        comment_guest_id = cg.id
        author_name = cg.author_name
        birth_date = cg.author_birth_date
        computed_age = calculate_age(birth_date)
        personality_info = cg.personality_info
    else:
        form = CommentForm()
        if not form.validate_on_submit():
            for field_name, errors in form.errors.items():
                for err in errors:
                    flash(f"{err}", 'danger')
            return redirect(dest_url)

        author_name = form.author_name.data.strip()
        birth_date = form.author_birth_date.data
        computed_age = calculate_age(birth_date)
        personality_info = form.personality_info.data.strip() if form.personality_info.data else None
        comment_text = form.comment_text.data.strip()

        if request.form.get('generate_comment_code') == '1':
            new_cg = CommentGuest(
                guest_code=generate_comment_guest_code(8),
                author_name=author_name,
                author_birth_date=birth_date,
                personality_info=personality_info
            )
            db.session.add(new_cg)
            db.session.flush()
            comment_guest_id = new_cg.id
            generated_code = new_cg.guest_code

    new_comment = PageComment(
        page_id=target_lecture.id,
        parent_id=None,
        comment_guest_id=comment_guest_id,
        is_teacher_reply=False,
        is_read_by_admin=False,
        author_name=author_name,
        author_birth_date=birth_date,
        author_age=computed_age,
        personality_info=personality_info,
        comment_text=comment_text
    )

    detail_lines = [
        f"Subject: {target_subject.name} | Lesson: {target_lecture.title}",
        f"By: {author_name} (Born: {birth_date.strftime('%Y-%m-%d')}, Age: {computed_age})"
    ]
    if personality_info:
        detail_lines.append(f"About: {personality_info}")
    detail_lines.append(f"Comment: {comment_text}")
    notif_title = f"{target_subject.name} — {target_lecture.title}"
    notif_body = "\n".join(detail_lines)

    try:
        db.session.add(new_comment)

        assignments = SubjectTeacher.query.filter_by(subject_id=target_subject.id).all()
        recipient_teacher_ids = {a.teacher_id for a in assignments}
        if target_subject.teacher_id:
            recipient_teacher_ids.add(target_subject.teacher_id)

        for tid in recipient_teacher_ids:
            db.session.add(TeacherNotification(
                teacher_id=tid,
                notification_type='comment',
                title=notif_title,
                message=notif_body,
                related_subject_id=target_subject.id,
                related_page_id=target_lecture.id
            ))

        db.session.commit()
        if generated_code:
            session['new_comment_guest_code'] = generated_code
            flash(_('Your comment has been posted! Your 8-character code is: %(code)s', code=generated_code), 'success')
        else:
            flash(_('Your comment has been posted!'), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error posting comment: %(error)s', error=str(e)), 'danger')

    return redirect(dest_url)


# ==============================================================================
# SECTION 4: EXAM ENGINE (PUBLIC & STUDENT-CODE-GATED QUIZZES/EXAMS)
# ==============================================================================

def _resolve_unlocked_student(target_subject):
    """Return authorized Student if unlocked via query param or session for target_subject."""
    code = (request.args.get('code') or session.get(f'unlocked_code_{target_subject.id}') or '').strip().upper()
    if not code:
        return None
    candidate = Student.query.filter_by(student_code=code).first()
    if candidate and can_student_access_subject(candidate, target_subject):
        return candidate
    return None


def _grade_questions_submission(expected_questions, form_data):
    """Grade all expected questions against submitted form selections."""
    correct_choices_count = 0
    total_exam_questions = len(expected_questions)
    if total_exam_questions > 0:
        for question in expected_questions:
            selection = (form_data.get(f'q_{question.id}') or '').strip().upper()
            if selection == question.correct_answer:
                correct_choices_count += 1
        final_percentage = int((correct_choices_count / total_exam_questions) * 100)
    else:
        final_percentage = 0
    return correct_choices_count, total_exam_questions, final_percentage


def _handle_student_unlock(target_subject, dest_url):
    """Shared handler to validate an 8+ char Student Code and store unlock session."""
    raw_code = (request.form.get('student_code') or '').strip().upper()
    if not raw_code:
        flash(_('Please enter your Student Code.'), 'danger')
        return redirect(dest_url)

    student = Student.query.filter_by(student_code=raw_code).first()
    if not student or not can_student_access_subject(student, target_subject):
        flash(_('Invalid or unauthorized Student Code for this teacher/subject.'), 'danger')
        return redirect(dest_url)

    session[f'unlocked_code_{target_subject.id}'] = student.student_code
    flash(_('Exam unlocked for %(name)s.', name=student.display_name(get_locale().language)), 'success')
    return redirect(dest_url)


@public.route('/subject/<slug>/unlock_exam', methods=['POST'])
@limiter.limit("20/minute")
def unlock_exam(slug):
    """Validate an 8+ char Student Code to unlock a hidden/restricted exam or quiz."""
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()
    page_id = request.form.get('page_id', type=int)
    dest_url = (
        url_for('public.take_exam', slug=slug, page_id=page_id)
        if page_id else url_for('public.take_exam', slug=slug)
    )
    return _handle_student_unlock(target_subject, dest_url)


@public.route('/subject/<slug>/exam')
@public.route('/subject/<slug>/lecture/<int:page_id>/quiz')
def take_exam(slug, page_id=None):
    """
    EXAM ENGINE (DUAL MODE + BILINGUAL QUESTIONS + STUDENT-CODE GATE)
    """
    lang = get_locale().language
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()

    if not target_subject.is_public and not current_user.is_authenticated:
        abort(403)

    if page_id:
        lecture_record = Page.query.get_or_404(page_id)
        if lecture_record.subject_id != target_subject.id:
            abort(404)
        is_restricted = bool(lecture_record.quiz_student_only)
        active_questions = Question.query.filter_by(page_id=page_id).all()
        exam_title_text = _('Quiz: %(title)s', title=lecture_record.display_title(lang))
    else:
        is_restricted = bool(target_subject.exam_student_only)
        active_questions = Question.query.filter_by(subject_id=target_subject.id).all()
        exam_title_text = _('%(name)s Final Examination', name=target_subject.display_name(lang))

    unlocked_student = _resolve_unlocked_student(target_subject)
    is_staff_viewer = current_user.is_authenticated and can_edit_subject(target_subject)

    if is_restricted and not unlocked_student and not is_staff_viewer:
        return render_template(
            'exam_gate.html',
            subject=target_subject,
            page_id=page_id,
            quiz_title=exam_title_text
        )

    return render_template(
        'exam.html',
        subject=target_subject,
        questions=active_questions,
        quiz_title=exam_title_text,
        page_id=page_id,
        is_restricted=is_restricted,
        unlocked_student=unlocked_student
    )


@public.route('/exam/link/<token>')
def take_private_exam(token):
    """Student-Code-Gated Auto-Generated Hidden Exam / Quiz Link."""
    lang = get_locale().language
    pe = PrivateExam.query.filter_by(access_token=token, is_active=True).first_or_404()
    target_subject = pe.subject
    exam_title_text = pe.display_title(lang)

    unlocked_student = _resolve_unlocked_student(target_subject)
    is_staff_viewer = current_user.is_authenticated and can_edit_subject(target_subject)

    if not unlocked_student and not is_staff_viewer:
        return render_template(
            'exam_gate.html',
            subject=target_subject,
            page_id=None,
            quiz_title=exam_title_text,
            unlock_action=url_for('public.unlock_private_exam', token=token)
        )

    return render_template(
        'exam.html',
        subject=target_subject,
        questions=pe.assigned_questions,
        quiz_title=exam_title_text,
        page_id=None,
        is_restricted=True,
        unlocked_student=unlocked_student,
        private_exam=pe,
        submit_action=url_for('public.submit_private_exam', token=token)
    )


@public.route('/exam/link/<token>/unlock', methods=['POST'])
@limiter.limit("20/minute")
def unlock_private_exam(token):
    """Validate an authorized Student Code for a PrivateExam link."""
    pe = PrivateExam.query.filter_by(access_token=token, is_active=True).first_or_404()
    return _handle_student_unlock(pe.subject, url_for('public.take_private_exam', token=token))


@public.route('/exam/link/<token>/submit', methods=['POST'])
def submit_private_exam(token):
    """Grade & persist ExamResult for a student-code-gated PrivateExam link."""
    pe = PrivateExam.query.filter_by(access_token=token, is_active=True).first_or_404()
    target_subject = pe.subject
    retry_url = url_for('public.take_private_exam', token=token)

    raw_code = (request.form.get('student_code') or '').strip().upper()
    student = Student.query.filter_by(student_code=raw_code).first() if raw_code else None
    if not student:
        flash(_('Invalid or missing Student Code.'), 'danger')
        return redirect(retry_url)
    if not can_student_access_subject(student, target_subject):
        flash(_('This student code is not authorized for this teacher/subject exam.'), 'danger')
        return redirect(retry_url)

    correct_choices_count, total_exam_questions, final_percentage = _grade_questions_submission(
        pe.assigned_questions, request.form
    )

    try:
        db.session.add(ExamResult(
            score=final_percentage,
            correct_count=correct_choices_count,
            total_questions=total_exam_questions,
            subject_id=target_subject.id,
            page_id=None,
            private_exam_id=pe.id,
            student_record_id=student.id
        ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(_('Error saving exam result: %(error)s', error=str(e)), 'danger')
        return redirect(retry_url)

    flash(
        _('Examination Submitted. Score: %(correct)s/%(total)s (%(grade)s%%)',
          correct=correct_choices_count, total=total_exam_questions, grade=final_percentage),
        'success'
    )
    if target_subject.is_public or (current_user.is_authenticated and can_edit_subject(target_subject)):
        return redirect(url_for('public.subject_detail', slug=target_subject.slug))
    return redirect(url_for('public.index'))


@public.route('/subject/<slug>/exam/submit', methods=['POST'])
def submit_exam(slug):
    """
    EXAM GRADING SYSTEM & LIVE STATS PERSISTENCE

    Validates student code OR guest taker info (optional name, required DOB & gender),
    grades against the COMPLETE question pool for that exam/quiz, and saves ExamResult.
    """
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()

    if not target_subject.is_public and not current_user.is_authenticated:
        abort(403)

    page_id = request.form.get('page_id', type=int)
    retry_url = (
        url_for('public.take_exam', slug=slug, page_id=page_id)
        if page_id else url_for('public.take_exam', slug=slug)
    )

    if page_id:
        lecture_record = Page.query.get_or_404(page_id)
        if lecture_record.subject_id != target_subject.id:
            abort(404)
        is_restricted = bool(lecture_record.quiz_student_only)
        expected_questions = Question.query.filter_by(page_id=page_id).all()
    else:
        is_restricted = bool(target_subject.exam_student_only)
        expected_questions = Question.query.filter_by(subject_id=target_subject.id).all()

    # Taker Identification: Student Code vs. Guest Exam Code vs. Guest Details
    taker_mode = (request.form.get('taker_mode') or 'guest').strip().lower()
    raw_code = (request.form.get('student_code') or '').strip().upper()
    raw_guest_code = (request.form.get('exam_guest_code') or '').strip().upper()

    student_record_id = None
    exam_guest_id = None
    generated_guest_code = None
    create_exam_guest = False
    taker_name = None
    parsed_dob = None
    taker_gender = None

    if is_restricted or taker_mode == 'student' or raw_code:
        student = Student.query.filter_by(student_code=raw_code).first() if raw_code else None
        if not student:
            flash(_('Invalid or missing Student Code.'), 'danger')
            return redirect(retry_url)
        if is_restricted and not can_student_access_subject(student, target_subject):
            flash(_('This student code is not authorized for this teacher/subject exam.'), 'danger')
            return redirect(retry_url)
        student_record_id = student.id
    elif taker_mode == 'guest_code' or raw_guest_code:
        eg = ExamGuest.query.filter_by(guest_code=raw_guest_code).first() if raw_guest_code else None
        if not eg:
            flash(_('Invalid Guest Exam Code. Please check your 8-character code.'), 'danger')
            return redirect(retry_url)
        exam_guest_id = eg.id
        taker_name = eg.taker_name
        parsed_dob = eg.taker_birth_date
        taker_gender = eg.taker_gender
    else:
        taker_name = (request.form.get('taker_name') or '').strip() or None
        dob_str = (request.form.get('taker_birth_date') or '').strip()
        taker_gender = (request.form.get('taker_gender') or '').strip().lower()

        if not dob_str or taker_gender not in ('male', 'female'):
            flash(_('Please provide your birth date and gender before submitting.'), 'danger')
            return redirect(retry_url)

        try:
            parsed_dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
        except ValueError:
            flash(_('Invalid birth date format.'), 'danger')
            return redirect(retry_url)

        today = date.today()
        age_years = calculate_age(parsed_dob)
        if parsed_dob > today or age_years < 5 or age_years > 120:
            flash(_('Please enter a valid birth date (age must be between 5 and 120).'), 'danger')
            return redirect(retry_url)

        create_exam_guest = (request.form.get('generate_exam_guest_code') == '1')

    # Accurate grading against the COMPLETE expected question set
    correct_choices_count, total_exam_questions, final_percentage = _grade_questions_submission(
        expected_questions, request.form
    )

    try:
        if create_exam_guest:
            new_eg = ExamGuest(
                guest_code=generate_exam_guest_code(8),
                taker_name=taker_name,
                taker_birth_date=parsed_dob,
                taker_gender=taker_gender
            )
            db.session.add(new_eg)
            db.session.flush()
            exam_guest_id = new_eg.id
            generated_guest_code = new_eg.guest_code

        db.session.add(ExamResult(
            score=final_percentage,
            correct_count=correct_choices_count,
            total_questions=total_exam_questions,
            subject_id=target_subject.id,
            page_id=page_id,
            student_record_id=student_record_id,
            exam_guest_id=exam_guest_id,
            taker_name=taker_name,
            taker_birth_date=parsed_dob,
            taker_gender=taker_gender
        ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(_('Error saving exam result: %(error)s', error=str(e)), 'danger')
        return redirect(retry_url)

    flash(
        _('Examination Submitted. Score: %(correct)s/%(total)s (%(grade)s%%)',
          correct=correct_choices_count, total=total_exam_questions, grade=final_percentage),
        'success'
    )
    if generated_guest_code:
        session['new_exam_guest_code'] = generated_guest_code
        flash(_('Your new 8-character Guest Exam Code is: %(code)s', code=generated_guest_code), 'info')
    if page_id:
        return redirect(url_for('public.view_page', slug=target_subject.slug, page_id=page_id))
    return redirect(url_for('public.subject_detail', slug=target_subject.slug))

