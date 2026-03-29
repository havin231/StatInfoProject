from flask import Blueprint, render_template, url_for, flash, redirect, request, session, abort
from sqlalchemy import desc

from app import db
from app.models import Student, Subject, Page, Question, ExamResult, StudentAnswer

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
        flash('Access Denied: You do not have permission to view this record.', 'danger')
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
            
    return render_template('subject.html', subject=target_subject)


@student.route('/subject/<slug>/page/<int:page_id>')
def view_page(slug, page_id):
    """
    LECTURE / CHAPTER CONTENT VIEW

    Logic:
    - TASK 4: Determines if this specific lecture has a "targeted" quiz.
    - Displays bilingual content and attached resources.
    """
    # 1. Fetch Objects
    target_lecture = Page.query.get_or_404(page_id)
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()

    # 2. Relationship Validation
    # Ensures the lecture actually belongs to the subject in the URL.
    if target_lecture.subject_id != target_subject.id:
        abort(404)

    # 3. Targeted Quiz Discovery
    # Checks the Question bank for any items specifically 'tagged' with this Page ID.
    specific_questions_exist = Question.query.filter_by(
        page_id=target_lecture.id
    ).first() is not None

    return render_template(
        'page.html',
        page=target_lecture,
        subject=target_subject,
        has_quiz=specific_questions_exist
    )


# ==============================================================================
# SECTION 4: EXAMINATION ENGINE (TASK 4 DUAL-MODE)
# ==============================================================================

@student.route('/subject/<slug>/exam')
@student.route('/subject/<slug>/lecture/<int:page_id>/quiz')
def take_exam(slug, page_id=None):
    """
    EXAM ENGINE (DUAL MODE)

    Handles:
    A) Global Final Exams: Pulls all questions for a subject.
    B) Lecture Quizzes: Pulls only questions tagged to a specific page_id.

    TASK FIX: If not logged in, uses relative path (request.full_path)
    to ensure the security check in Section 3 passes.
    """
    # 1. Login Verification
    if 'student_id' not in session:
        # Pass the current relative URL as 'next'
        return redirect(url_for('auth.student_login', next=request.full_path))

    # 2. Identify Context
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()
    current_student = Student.query.get(session['student_id'])

    # 3. Logic: General Exam vs Specific Quiz
    if page_id:
        # Targeted Mode (Lecture specific)
        lecture_record = Page.query.get_or_404(page_id)
        active_questions = Question.query.filter_by(page_id=page_id).all()
        exam_title_text = f"Quiz: {lecture_record.title}"
    else:
        # Comprehensive Mode (All subject questions)
        active_questions = Question.query.filter_by(subject_id=target_subject.id).all()
        exam_title_text = f"{target_subject.name} Final Examination"

    return render_template(
        'exam.html',
        subject=target_subject,
        questions=active_questions,
        student=current_student,
        quiz_title=exam_title_text
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
        flash(f'Examination Submitted. Final Grade: {final_percentage}%', 'success')

    except Exception as db_err:
        db.session.rollback()
        flash(f'Critical system error during submission: {str(db_err)}', 'danger')

    return redirect(url_for('student.student_dashboard'))
