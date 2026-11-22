from flask import Blueprint, render_template, url_for, flash, redirect, request, abort
from flask_babel import gettext as _

from app import db
from app.models import Subject, Page, Question

student = Blueprint('student', __name__)

# ==============================================================================
# SECTION 4: COURSE & LECTURE BROWSING
# ==============================================================================

@student.route('/subject/<slug>')
def subject_detail(slug):
    """
    SUBJECT REPOSITORY VIEW

    Lists all lectures (Pages) within a specific subject.
    Open to visitors and staff.
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

    Displays bilingual content and attached resources.
    Discovers if targeted quiz questions exist for this lecture.
    """
    target_lecture = Page.query.get_or_404(page_id)
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()

    if target_lecture.subject_id != target_subject.id:
        abort(404)

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
# SECTION 5: EXAM ENGINE (ANONYMOUS / PUBLIC QUIZZES)
# ==============================================================================

@student.route('/subject/<slug>/exam')
@student.route('/subject/<slug>/lecture/<int:page_id>/quiz')
def take_exam(slug, page_id=None):
    """
    EXAM ENGINE (DUAL MODE)

    Handles:
    A) Global Final Exams: Pulls all questions for a subject.
    B) Lecture Quizzes: Pulls only questions tagged to a specific page_id.
    """
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()

    if page_id:
        lecture_record = Page.query.get_or_404(page_id)
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


@student.route('/subject/<slug>/exam/submit', methods=['POST'])
def submit_exam(slug):
    """
    EXAM GRADING SYSTEM

    Calculates percentage score based on submitted answers and
    flashes the result immediately on redirect.
    """
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()

    # Dynamic Question Identification
    submitted_question_ids = []
    for key in request.form.keys():
        if key.startswith('q_'):
            try:
                q_id_int = int(key.split('_')[1])
                submitted_question_ids.append(q_id_int)
            except (IndexError, ValueError):
                continue

    validated_questions = Question.query.filter(Question.id.in_(submitted_question_ids)).all()
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
    return redirect(url_for('student.subject_detail', slug=target_subject.slug))


# Graceful redirects for deprecated student endpoints
@student.route('/student/dashboard')
@student.route('/student/profile')
@student.route('/student/exam/review/<int:result_id>')
@student.route('/student/delete-account')
def deprecated_student_endpoints(*args, **kwargs):
    """Redirect deprecated student dashboard and profile pages to homepage."""
    return redirect(url_for('public.index'))
