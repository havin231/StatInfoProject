from datetime import datetime
from flask import Blueprint, render_template, url_for, flash, redirect, request, jsonify, session, abort
from flask_babel import gettext as _
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from app import db, bcrypt, limiter
from app.models import User, Subject, ExamResult, SiteInfo, Page, Question, PageComment
from app.forms import SetupForm, CommentForm

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
                Subject.description.ilike(f'%{search_query}%')
            )
        ).all()
        
        page_list = Page.query.join(Subject).filter(
            Subject.is_public == True,
            or_(
                Page.title.ilike(f'%{search_query}%'),
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
    # 1. Subject performance aggregation
    subject_scores = db.session.query(
        Subject.name,
        func.avg(ExamResult.score)
    ).join(ExamResult).group_by(Subject.id).all()

    # 2. Extract labels and rounded values for Chart.js
    chart_labels = [row[0] for row in subject_scores]
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
    from app.models import SubjectTeacher
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()

    # Visibility Check: If hidden, restrict access to staff only
    if not target_subject.is_public and not current_user.is_authenticated:
        abort(403)

    current_assignments = SubjectTeacher.query.filter_by(subject_id=target_subject.id).all()
    visible_teachers = [a.teacher for a in current_assignments if a.show_name and a.teacher]

    return render_template('subject.html', subject=target_subject, visible_teachers=visible_teachers)


@public.route('/subject/<slug>/page/<int:page_id>')
def view_page(slug, page_id):
    """
    LECTURE / CHAPTER CONTENT VIEW

    Displays bilingual content and attached resources.
    Discovers if targeted quiz questions exist for this lecture.
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

    comments = PageComment.query.filter_by(
        page_id=target_lecture.id
    ).order_by(PageComment.created_at.desc()).all()
    comment_form = CommentForm()

    can_moderate = False
    if current_user.is_authenticated:
        from app.routes.helpers import can_edit_subject
        can_moderate = can_edit_subject(target_subject)

    return render_template(
        'page.html',
        page=target_lecture,
        subject=target_subject,
        has_quiz=specific_questions_exist,
        comments=comments,
        comment_form=comment_form,
        can_moderate=can_moderate
    )


@public.route('/subject/<slug>/page/<int:page_id>/comment', methods=['POST'])
@limiter.limit("15/minute")
def add_page_comment(slug, page_id):
    """
    PUBLIC LECTURE COMMENT SUBMISSION

    Allows any visitor to post a comment on a lecture after providing their
    name, age, optional personality/about-you info, and comment text.
    """
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()
    target_lecture = Page.query.get_or_404(page_id)

    if not target_subject.is_public and not current_user.is_authenticated:
        abort(403)

    if target_lecture.subject_id != target_subject.id:
        abort(404)

    form = CommentForm()
    if form.validate_on_submit():
        new_comment = PageComment(
            page_id=target_lecture.id,
            author_name=form.author_name.data.strip(),
            author_age=form.author_age.data,
            personality_info=form.personality_info.data.strip() if form.personality_info.data else None,
            comment_text=form.comment_text.data.strip()
        )
        try:
            db.session.add(new_comment)
            db.session.commit()
            flash(_('Your comment has been posted!'), 'success')
        except Exception as e:
            db.session.rollback()
            flash(_('Error posting comment: %(error)s', error=str(e)), 'danger')
    else:
        for field_name, errors in form.errors.items():
            for err in errors:
                flash(f"{err}", 'danger')

    return redirect(url_for('public.view_page', slug=slug, page_id=page_id) + '#comments-section')


# ==============================================================================
# SECTION 4: EXAM ENGINE (PUBLIC QUIZZES & EXAMS)
# ==============================================================================

@public.route('/subject/<slug>/exam')
@public.route('/subject/<slug>/lecture/<int:page_id>/quiz')
def take_exam(slug, page_id=None):
    """
    EXAM ENGINE (DUAL MODE)

    Handles:
    A) Global Final Exams: Pulls all questions for a subject.
    B) Lecture Quizzes: Pulls only questions tagged to a specific page_id.
    """
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()

    if not target_subject.is_public and not current_user.is_authenticated:
        abort(403)

    if page_id:
        lecture_record = Page.query.get_or_404(page_id)
        if lecture_record.subject_id != target_subject.id:
            abort(404)
        active_questions = Question.query.filter_by(page_id=page_id).all()
        exam_title_text = f"Quiz: {lecture_record.title}"
    else:
        active_questions = Question.query.filter_by(subject_id=target_subject.id).all()
        exam_title_text = f"{target_subject.name} Final Examination"

    return render_template(
        'exam.html',
        subject=target_subject,
        questions=active_questions,
        quiz_title=exam_title_text,
        page_id=page_id
    )


@public.route('/subject/<slug>/exam/submit', methods=['POST'])
def submit_exam(slug):
    """
    EXAM GRADING SYSTEM

    Calculates percentage score based on submitted answers and
    flashes the result immediately on redirect.
    """
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()

    if not target_subject.is_public and not current_user.is_authenticated:
        abort(403)

    # Dynamic Question Identification
    submitted_question_ids = []
    for key in request.form.keys():
        if key.startswith('q_'):
            try:
                q_id_int = int(key.split('_')[1])
                submitted_question_ids.append(q_id_int)
            except (IndexError, ValueError):
                continue

    validated_questions = Question.query.filter(
        Question.id.in_(submitted_question_ids),
        Question.subject_id == target_subject.id
    ).all() if submitted_question_ids else []

    correct_choices_count = 0
    total_exam_questions = len(validated_questions)

    if total_exam_questions > 0:
        for question in validated_questions:
            selection = request.form.get(f'q_{question.id}')
            if selection == question.correct_answer:
                correct_choices_count += 1

        final_percentage = int((correct_choices_count / total_exam_questions) * 100)
    else:
        final_percentage = 0

    flash(_('Examination Submitted. Final Grade: %(grade)s%%', grade=final_percentage), 'success')
    return redirect(url_for('public.subject_detail', slug=target_subject.slug))

