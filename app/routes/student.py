from datetime import datetime
from flask import Blueprint, render_template, url_for, flash, redirect, request, session, abort
from flask_babel import gettext as _
from sqlalchemy import desc

from app import db
from app.models import Student, Subject, Page, Question, ExamResult, StudentAnswer, StudentPinnedSubject, LessonProgress, ExamProgress, AdminNotification

student = Blueprint('student', __name__)

# ==============================================================================
# SECTION 4: STUDENT EXPERIENCE (DASHBOARD, LECTURES, & REVIEWS)
# ==============================================================================

@student.route('/student/dashboard')
def student_dashboard():
    """
    STUDENT PERSONAL DASHBOARD

    Displays:
    - Academic Stats: Total Exams and Global Average.
    - Subject Mastery: Average score per subject.
    - Chronological History: List of past attempts with a Review option.

    TASK 2 FIX: Image placeholder logic removed for clean UI.
    """
    # 1. Verification: Is the student logged in?
    if 'student_id' not in session:
        return redirect(url_for('auth.student_login'))

    # 2. Fetch Student Object
    student_record = Student.query.get_or_404(session['student_id'])

    # 3. Fetch Exam History (Ordered by most recent)
    all_results = ExamResult.query.filter_by(
        student_id=student_record.id
    ).order_by(desc(ExamResult.date_submitted)).all()

    # 4. Filter out "Ghost Exams" (attempts with no answers due to deletion)
    # This ensures the dashboard remains accurate if questions were removed.
    valid_results = []
    for res in all_results:
        if len(res.answers) > 0:
            valid_results.append(res)
        else:
            # Cleanup logic: If we find an empty exam result, delete it from DB
            try:
                db.session.delete(res)
                db.session.commit()
            except Exception:
                db.session.rollback()

    # 5. Global Stat Calculation
    total_completed_exams = len(valid_results)

    if total_completed_exams > 0:
        sum_of_scores = sum(r.score for r in valid_results)
        global_avg_score = round(sum_of_scores / total_completed_exams, 1)
    else:
        global_avg_score = 0

    # 6. Mastery Calculation: Group Results by Subject
    # We use a dictionary to organize scores per course
    subject_map = {}
    for r in valid_results:
        subj_id = r.subject.id
        if subj_id not in subject_map:
            subject_map[subj_id] = {
                'name': r.subject.name,
                'slug': r.subject.slug,
                'scores': [],
                'exams': []
            }
        subject_map[subj_id]['scores'].append(r.score)
        subject_map[subj_id]['exams'].append(r)

    # 7. Convert mapping to list and calculate per-subject averages
    subject_performance_list = []
    for s_id, data in subject_map.items():
        s_average = sum(data['scores']) / len(data['scores'])
        data['average'] = round(s_average, 1)
        subject_performance_list.append(data)

    # Sort subjects alphabetically by name
    subject_performance_list.sort(key=lambda x: x['name'])

    return render_template(
        'student/dashboard.html',
        student=student_record,
        results=valid_results,
        avg_score=global_avg_score,
        total_exams=total_completed_exams,
        subject_performance=subject_performance_list
    )


@student.route('/student/exam/review/<int:result_id>')
def student_review_exam(result_id):
    """
    EXAM REVIEW INTERFACE

    Logic:
    - Fetches a specific ExamResult ID.
    - Security: Confirms the current student is the owner of the record.
    - Renders a read-only view of the attempt (Red/Green card feedback).
    """
    # 1. Login Check
    if 'student_id' not in session:
        return redirect(url_for('auth.student_login'))

    # 2. Fetch Record
    attempt_record = ExamResult.query.get_or_404(result_id)

    # 3. Security: Anti-Snooping Check
    # Prevents students from guessing IDs to see other people's results.
    if attempt_record.student_id != session['student_id']:
        flash(_('Access Denied: You do not have permission to view this record.'), 'danger')
        return redirect(url_for('student.student_dashboard'))

    return render_template('student/review_exam.html', result=attempt_record)


@student.route('/subject/<slug>')
def subject_detail(slug):
    """
    SUBJECT REPOSITORY VIEW

    Lists all lectures (Pages) within a specific subject.
    Open to authenticated students and staff.
    """
    from flask_login import current_user
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()

    # Visibility Check: If hidden, restrict access to staff only
    if not target_subject.is_public:
        if not current_user.is_authenticated:
            abort(403)

    # Check if student has pinned this subject (v0.5.0)
    is_pinned = False
    if 'student_id' in session:
        pin_record = StudentPinnedSubject.query.filter_by(
            student_id=session['student_id'],
            subject_id=target_subject.id
        ).first()
        is_pinned = pin_record is not None

    return render_template('subject.html', subject=target_subject, is_pinned=is_pinned)


@student.route('/subject/<slug>/page/<int:page_id>')
def view_page(slug, page_id):
    """
    LECTURE / CHAPTER CONTENT VIEW

    Logic:
    - TASK 4: Determines if this specific lecture has a "targeted" quiz.
    - v0.5.0: Checks lesson completion status for logged-in students.
    - Displays bilingual content and attached resources.
    """
    # 1. Fetch Objects
    target_lecture = Page.query.get_or_404(page_id)
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()

    # 2. Relationship Validation
    if target_lecture.subject_id != target_subject.id:
        abort(404)

    # 3. Targeted Quiz Discovery
    specific_questions_exist = Question.query.filter_by(
        page_id=target_lecture.id
    ).first() is not None

    # 4. Check Lesson Progress (v0.5.0 - Feature 2)
    is_completed = False
    if 'student_id' in session:
        progress = LessonProgress.query.filter_by(
            student_id=session['student_id'],
            page_id=target_lecture.id
        ).first()
        is_completed = progress.is_completed if progress else False

    return render_template(
        'page.html',
        page=target_lecture,
        subject=target_subject,
        has_quiz=specific_questions_exist,
        is_completed=is_completed
    )


# ==============================================================================
# SECTION 4: EXAMINATION ENGINE (TASK 4 DUAL-MODE)
# ==============================================================================

@student.route('/subject/<slug>/exam')
@student.route('/subject/<slug>/lecture/<int:page_id>/quiz')
def take_exam(slug, page_id=None):
    """
    EXAM ENGINE (DUAL MODE) - v0.5.0 PROGRESSIVE SUPPORT

    Handles:
    A) Global Final Exams: Pulls all questions for a subject.
    B) Lecture Quizzes: Pulls only questions tagged to a specific page_id.
    C) Progressive: Loads existing ExamProgress to show grayed questions.

    TASK FIX: If not logged in, uses relative path (request.full_path)
    to ensure the security check in Section 3 passes.
    """
    # 1. Login Verification
    if 'student_id' not in session:
        return redirect(url_for('auth.student_login', next=request.full_path))

    # 2. Identify Context
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()
    current_student = Student.query.get(session['student_id'])

    # 3. Logic: General Exam vs Specific Quiz
    if page_id:
        lecture_record = Page.query.get_or_404(page_id)
        active_questions = Question.query.filter_by(page_id=page_id).all()
        exam_title_text = f"Quiz: {lecture_record.title}"
    else:
        active_questions = Question.query.filter_by(subject_id=target_subject.id).all()
        exam_title_text = f"{target_subject.name} Final Examination"

    # 4. Load Exam Progress (v0.5.0 - Feature 4)
    exam_progress = ExamProgress.query.filter_by(
        student_id=current_student.id,
        subject_id=target_subject.id,
        page_id=page_id
    ).first()

    submitted_answers = {}
    locked_questions = []
    is_completed = False

    if exam_progress:
        submitted_answers = exam_progress.submitted_answers or {}
        locked_questions = exam_progress.locked_questions or []
        is_completed = exam_progress.is_completed

    return render_template(
        'exam.html',
        subject=target_subject,
        questions=active_questions,
        student=current_student,
        quiz_title=exam_title_text,
        submitted_answers=submitted_answers,
        locked_questions=locked_questions,
        is_completed=is_completed,
        page_id=page_id
    )


@student.route('/subject/<slug>/exam/submit', methods=['POST'])
def submit_exam(slug):
    """
    EXAM GRADING & LOGGING SYSTEM

    Logic:
    - Calculates the percentage score based on questions present in the form.
    - Creates a Result Record (Parent).
    - Links every individual Answer to that Parent (Fixes duplicate bug).
    """
    # 1. Verify Session
    if 'student_id' not in session:
        return redirect(url_for('auth.student_login'))

    # 2. Context Initialization
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()
    current_student = Student.query.get(session['student_id'])

    # 3. Dynamic Question Identification
    # Extract IDs from the POST keys (e.g. 'q_23' -> 23)
    submitted_question_ids = []
    for key in request.form.keys():
        if key.startswith('q_'):
            try:
                q_id_int = int(key.split('_')[1])
                submitted_question_ids.append(q_id_int)
            except (IndexError, ValueError):
                continue

    # Fetch actual question objects from DB to verify correctness
    validated_questions = Question.query.filter(Question.id.in_(submitted_question_ids)).all()

    correct_choices_count = 0
    total_exam_questions = len(validated_questions)

    # 4. Preparation for Batch DB Entry
    temp_answer_data = []

    if total_exam_questions > 0:
        for question in validated_questions:
            student_selection = request.form.get(f'q_{question.id}')

            # Check correctness against the primary key
            is_selection_correct = (student_selection == question.correct_answer)

            if is_selection_correct:
                correct_choices_count += 1

            temp_answer_data.append({
                'q_id': question.id,
                'choice': student_selection,
                'status': is_selection_correct
            })

        # Integer division for whole percentage
        final_percentage = int((correct_choices_count / total_exam_questions) * 100)
    else:
        final_percentage = 0

    # 5. Database Commit Transaction
    try:
        # A. Create the Parent Result record
        final_result_record = ExamResult(
            score=final_percentage,
            student_id=current_student.id,
            subject_id=target_subject.id
        )
        db.session.add(final_result_record)

        # Flush to generate ID for the foreign key links
        db.session.flush()

        # B. Create the Child Answer records linked to the specific Attempt ID
        for data_row in temp_answer_data:
            db.session.add(StudentAnswer(
                student_id=current_student.id,
                question_id=data_row['q_id'],
                exam_id=final_result_record.id, # The Link (Foreign Key)
                selected_option=data_row['choice'],
                is_correct=data_row['status']
            ))

        db.session.commit()
        
        # v0.5.0 - Create Admin Notification for exam submission
        try:
            exam_notif = AdminNotification(
                category='exam',
                content=f"Exam Submitted: {current_student.full_name} scored {final_percentage}% in {target_subject.name}"
            )
            db.session.add(exam_notif)
            db.session.commit()
        except Exception as e_notif:
            db.session.rollback()
            print(f"Notification error: {e_notif}")
            
        flash(_('Examination Submitted. Final Grade: %(grade)s%%', grade=final_percentage), 'success')

    except Exception as db_err:
        db.session.rollback()
        flash(_('Critical system error during submission: %(error)s', error=str(db_err)), 'danger')

    return redirect(url_for('student.student_dashboard'))


@student.route('/student/delete-account', methods=['GET', 'POST'])
def delete_account():
    """
    STUDENT SELF-DELETION

    Allows students to delete their own account.
    Personal data is anonymized but exam results are kept for analytics.
    """
    if 'student_id' not in session:
        return redirect(url_for('auth.student_login'))

    student = Student.query.get_or_404(session['student_id'])

    if request.method == 'POST':
        confirm_delete = request.form.get('confirm_delete')

        if not confirm_delete:
            flash(_('Please confirm that you understand the consequences.'), 'warning')
            return render_template('student/delete_account.html', student=student)

        try:
            # Anonymize student data (keep ID for exam result relationships)
            student.full_name = f"Deleted Student #{student.id}"
            student.email = None
            student.password_hash = None
            student.access_code = None

            db.session.commit()

            # Clear session
            session.pop('student_id', None)

            flash(_('Your account has been deleted. Your exam data has been anonymized and retained for analytics.'), 'info')
            return redirect(url_for('public.index'))

        except Exception as e:
            db.session.rollback()
            flash(_('Error deleting account: %(error)s', error=str(e)), 'danger')
            return redirect(url_for('student.student_dashboard'))

    return render_template('student/delete_account.html', student=student)


# ==============================================================================
# SECTION 5: PINNED SUBJECTS & PROFILE (v0.5.0 - Feature 1 & 5)
# ==============================================================================

@student.route('/student/profile')
def student_profile():
    """
    STUDENT PROFILE WITH TABS

    Displays:
    - Tab 1: Pinned Subjects
    - Tab 2: Exam History
    - Degree/Score shown at top of both tabs
    """
    if 'student_id' not in session:
        return redirect(url_for('auth.student_login'))

    student_record = Student.query.get_or_404(session['student_id'])

    # Fetch pinned subjects
    pinned_subjects = db.session.query(Subject).join(
        StudentPinnedSubject
    ).filter(
        StudentPinnedSubject.student_id == student_record.id
    ).order_by(StudentPinnedSubject.pinned_at.desc()).all()

    # Fetch Exam History
    all_results = ExamResult.query.filter_by(
        student_id=student_record.id
    ).order_by(desc(ExamResult.date_submitted)).all()

    # Filter ghost exams
    valid_results = []
    for res in all_results:
        if len(res.answers) > 0:
            valid_results.append(res)

    # Calculate global average
    total_completed_exams = len(valid_results)
    if total_completed_exams > 0:
        global_avg_score = round(sum(r.score for r in valid_results) / total_completed_exams, 1)
    else:
        global_avg_score = 0

    return render_template(
        'student/profile.html',
        student=student_record,
        pinned_subjects=pinned_subjects,
        results=valid_results,
        avg_score=global_avg_score,
        total_exams=total_completed_exams
    )


@student.route('/api/subject/<slug>/pin', methods=['POST'])
def toggle_pin_subject(slug):
    """
    TOGGLE PIN STATUS FOR A SUBJECT

    API endpoint to pin/unpin a subject for the logged-in student.
    Returns JSON response for AJAX calls.
    """
    if 'student_id' not in session:
        return {'success': False, 'error': 'Not authenticated'}, 401

    student_id = session['student_id']
    subject = Subject.query.filter_by(slug=slug).first_or_404()

    # Check if already pinned
    existing_pin = StudentPinnedSubject.query.filter_by(
        student_id=student_id,
        subject_id=subject.id
    ).first()

    try:
        if existing_pin:
            # Unpin
            db.session.delete(existing_pin)
            db.session.commit()
            return {
                'success': True,
                'pinned': False,
                'message': _('Subject unpinned successfully')
            }
        else:
            # Pin
            new_pin = StudentPinnedSubject(
                student_id=student_id,
                subject_id=subject.id
            )
            db.session.add(new_pin)
            db.session.commit()
            return {
                'success': True,
                'pinned': True,
                'message': _('Subject pinned successfully')
            }
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}, 500


@student.route('/student/api/pinned-subjects')
def get_pinned_subjects():
    """
    GET PINNED SUBJECTS JSON

    Returns list of pinned subjects for the current student.
    Used for dynamic updates.
    """
    if 'student_id' not in session:
        return {'success': False, 'error': 'Not authenticated'}, 401

    pinned = StudentPinnedSubject.query.filter_by(
        student_id=session['student_id']
    ).join(Subject).all()

    subjects_data = []
    for pin in pinned:
        subjects_data.append({
            'id': pin.subject.id,
            'name': pin.subject.name,
            'name_kurdish': pin.subject.name_kurdish,
            'slug': pin.subject.slug,
            'pinned_at': pin.pinned_at.isoformat()
        })

    return {'success': True, 'subjects': subjects_data}


@student.route('/api/page/<int:page_id>/progress', methods=['POST'])
def toggle_lesson_progress(page_id):
    """
    TOGGLE LESSON COMPLETION STATUS

    API endpoint to mark/unmark a lesson as completed.
    Returns JSON response for AJAX calls.
    """
    if 'student_id' not in session:
        return {'success': False, 'error': 'Not authenticated'}, 401

    student_id = session['student_id']
    page = Page.query.get_or_404(page_id)

    # Check if progress record exists
    progress = LessonProgress.query.filter_by(
        student_id=student_id,
        page_id=page_id
    ).first()

    try:
        if progress:
            # Toggle existing progress
            progress.is_completed = not progress.is_completed
            progress.completed_at = datetime.utcnow() if progress.is_completed else None
        else:
            # Create new completed progress
            progress = LessonProgress(
                student_id=student_id,
                page_id=page_id,
                is_completed=True,
                completed_at=datetime.utcnow()
            )
            db.session.add(progress)

        db.session.commit()
        return {
            'success': True,
            'is_completed': progress.is_completed,
            'message': _('Lesson marked as completed') if progress.is_completed else _('Lesson marked as incomplete')
        }
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}, 500


@student.route('/api/subject/<slug>/progress')
def get_subject_progress(slug):
    """
    GET LESSON PROGRESS FOR SUBJECT

    Returns progress data for all pages in a subject for the current student.
    """
    if 'student_id' not in session:
        return {'success': False, 'error': 'Not authenticated'}, 401

    subject = Subject.query.filter_by(slug=slug).first_or_404()

    # Get all progress records for this student and subject
    progress_records = LessonProgress.query.filter_by(
        student_id=session['student_id']
    ).join(Page).filter(Page.subject_id == subject.id).all()

    progress_data = {}
    for record in progress_records:
        progress_data[record.page_id] = {
            'is_completed': record.is_completed,
            'completed_at': record.completed_at.isoformat() if record.completed_at else None
        }

    # Calculate stats
    total_pages = len(subject.pages)
    completed_pages = len([p for p in progress_records if p.is_completed])
    progress_percentage = round((completed_pages / total_pages * 100), 1) if total_pages > 0 else 0

    return {
        'success': True,
        'progress': progress_data,
        'stats': {
            'total_pages': total_pages,
            'completed_pages': completed_pages,
            'progress_percentage': progress_percentage
        }
    }


# ==============================================================================
# SECTION 6: PROGRESSIVE EXAM SUPPORT (v0.5.0 - Feature 4)
# ==============================================================================

@student.route('/subject/<slug>/exam/save-progress', methods=['POST'])
def save_exam_progress(slug):
    """
    SAVE EXAM PROGRESS

    API endpoint to save partial exam answers.
    Creates or updates an ExamProgress record.
    """
    if 'student_id' not in session:
        return {'success': False, 'error': 'Not authenticated'}, 401

    data = request.get_json()
    if not data or 'answers' not in data:
        return {'success': False, 'error': 'No answers provided'}, 400

    student_id = session['student_id']
    subject = Subject.query.filter_by(slug=slug).first_or_404()
    page_id = data.get('page_id')

    # Extract question IDs from answer keys (e.g., 'q_23' -> 23)
    submitted_answers = data['answers']
    locked_question_ids = []

    for key, value in submitted_answers.items():
        if key.startswith('q_') and value:
            try:
                q_id = int(key.split('_')[1])
                locked_question_ids.append(q_id)
            except (IndexError, ValueError):
                continue

    try:
        # Get or create ExamProgress
        progress = ExamProgress.query.filter_by(
            student_id=student_id,
            subject_id=subject.id,
            page_id=page_id
        ).first()

        if not progress:
            progress = ExamProgress(
                student_id=student_id,
                subject_id=subject.id,
                page_id=page_id,
                submitted_answers={},
                locked_questions=[]
            )
            db.session.add(progress)

        # Update progress
        progress.submitted_answers = submitted_answers
        progress.locked_questions = locked_question_ids
        progress.last_activity = datetime.utcnow()

        db.session.commit()

        return {
            'success': True,
            'locked_count': len(locked_question_ids),
            'message': _('Progress saved successfully')
        }

    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}, 500


@student.route('/subject/<slug>/exam/reset')
def reset_exam(slug):
    """
    RESET EXAM PROGRESS

    Allows students to retake a completed exam.
    Deletes the ExamProgress record but keeps ExamResult for history.
    """
    if 'student_id' not in session:
        return redirect(url_for('auth.student_login'))

    student_id = session['student_id']
    subject = Subject.query.filter_by(slug=slug).first_or_404()
    page_id = request.args.get('page_id', type=int)

    try:
        # Find and delete progress record
        progress = ExamProgress.query.filter_by(
            student_id=student_id,
            subject_id=subject.id,
            page_id=page_id
        ).first()

        if progress:
            db.session.delete(progress)
            db.session.commit()
            flash(_('Exam progress has been reset. You can now retake the exam.'), 'info')
        else:
            flash(_('No exam progress found to reset.'), 'warning')

    except Exception as e:
        db.session.rollback()
        flash(_('Error resetting exam: %(error)s', error=str(e)), 'danger')

    # Redirect back to exam page
    if page_id:
        return redirect(url_for('student.take_exam', slug=slug, page_id=page_id))
    else:
        return redirect(url_for('student.take_exam', slug=slug))
