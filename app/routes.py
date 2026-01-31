import os
import csv
import io
import json
import secrets
import string
import zipfile  # Required for the Full System Backup feature
import pandas as pd
from datetime import datetime

# Flask Core Imports
from flask import (
    Blueprint,
    render_template,
    url_for,
    flash,
    redirect,
    request,
    session,
    abort,
    Response,
    jsonify,
    current_app
)

# Authentication & Security
from flask_login import (
    login_user,
    current_user,
    logout_user,
    login_required
)

# Database & Logic
from sqlalchemy import func, desc

# Application Context Imports
from app import db, bcrypt
from app.models import (
    User,
    Student,
    Subject,
    Page,
    Question,
    ExamResult,
    StudentAnswer,
    SiteInfo,
    Resource,
    SystemCommand,
    Tool
)
from app.forms import (
    LoginForm,
    SubjectForm,
    PageForm,
    QuestionForm,
    TeacherSignupForm,
    StudentForm,
    StudentEditForm,
    TeacherEditForm,
    InfoPageForm,
    ToolForm,
    SetupForm,
    BulkImportForm,
    ResourceForm,
    CommandForm,
    RestoreBackupForm
)

# Define the Blueprint logic
main = Blueprint('main', __name__)

# ==============================================================================
# SECTION 1: SYSTEM UTILITIES & CORE SETUP
# ==============================================================================

def generate_access_code(length=6):
    """
    Generates a cryptographically secure random alphanumeric code.
    Used for student login tokens to ensure unique identification.

    Args:
        length (int): Length of the code. Default is 6 characters.

    Returns:
        str: A random string like 'A9X2B1'.
    """
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@main.route('/keep_alive')
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


@main.route('/setup', methods=['GET', 'POST'])
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
        flash('System is already initialized. Access to setup is restricted.', 'warning')
        return redirect(url_for('main.login'))

    # 2. Setup Form
    form = SetupForm()

    # 3. Validation and User Creation
    if form.validate_on_submit():

        # Verify email uniqueness
        check_email = User.query.filter_by(email=form.email.data).first()
        if check_email:
            flash('Error: This email is already registered in our systems.', 'danger')
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
            flash('Admin Account Created! Please login to begin managing the school.', 'success')
            return redirect(url_for('main.login'))
        except Exception as database_error:
            db.session.rollback()
            flash(f'Critical Database Error: {str(database_error)}', 'danger')

    return render_template('setup.html', form=form)


# ==============================================================================
# SECTION 2: PUBLIC USER INTERFACE
# ==============================================================================

@main.route('/')
def index():
    """
    HOMEPAGE

    Lists all academic subjects currently offered.
    """
    subject_list = Subject.query.all()
    return render_template('index.html', subjects=subject_list)


@main.route('/about')
def about():
    """
    ABOUT US PAGE

    Content is dynamically fetched from the SiteInfo model.
    """
    site_content = SiteInfo.query.filter_by(key='about').first()
    return render_template('about.html', info=site_content)


@main.route('/public/stats')
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
    total_registered_students = Student.query.count()

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
        total_students=total_registered_students,
        global_average=global_average_percent,
        pass_count=passing_grade_count,
        fail_count=failing_grade_count
    )


# ==============================================================================
# SECTION 3: AUTHENTICATION (STAFF & STUDENTS)
# ==============================================================================

@main.route('/login', methods=['GET', 'POST'])
def login():
    """
    STAFF PORTAL LOGIN

    Handles authentication for both Teachers and Administrators.
    Includes 'remember me' cookie support.
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.teacher_dashboard'))

    form = LoginForm()

    if form.validate_on_submit():
        user_record = User.query.filter_by(email=form.email.data).first()

        if user_record and bcrypt.check_password_hash(user_record.password_hash, form.password.data):
            login_user(user_record, remember=form.remember.data)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('main.teacher_dashboard'))
        else:
            flash('Authentication failed. Check credentials.', 'danger')

    return render_template('login.html', title='Staff Access', form=form)


@main.route('/student/login', methods=['GET', 'POST'])
def student_login():
    """
    STUDENT PORTAL LOGIN

    Authenticates students via Access Code.
    Implements redirection logic for deep links (Task Fix).
    """
    if request.method == 'POST':
        user_token = request.form.get('access_code')
        student_record = Student.query.filter_by(access_code=user_token).first()

        if student_record:
            # Persistent session identification
            session['student_id'] = student_record.id
            flash(f'Welcome, {student_record.full_name}.', 'success')

            # REDIRECT LOGIC: Support for the 'next' parameter
            target_page = request.args.get('next')
            if target_page and target_page.startswith('/'):
                return redirect(target_page)

            return redirect(url_for('main.student_dashboard'))
        else:
            flash('The Access Code provided is invalid.', 'danger')

    return render_template('student_login.html')


@main.route('/logout')
def logout():
    """
    GLOBAL SESSION TERMINATION

    Clears all active sessions for both staff and students.
    """
    logout_user()
    session.pop('student_id', None)
    flash('Session ended.', 'info')
    return redirect(url_for('main.index'))

# ==============================================================================
# SECTION 3: STUDENT EXPERIENCE (DASHBOARD, LECTURES, & REVIEWS)
# ==============================================================================

@main.route('/student/dashboard')
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
        return redirect(url_for('main.student_login'))

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


@main.route('/student/exam/review/<int:result_id>')
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
        return redirect(url_for('main.student_login'))

    # 2. Fetch Record
    attempt_record = ExamResult.query.get_or_404(result_id)

    # 3. Security: Anti-Snooping Check
    # Prevents students from guessing IDs to see other people's results.
    if attempt_record.student_id != session['student_id']:
        flash('Access Denied: You do not have permission to view this record.', 'danger')
        return redirect(url_for('main.student_dashboard'))

    return render_template('student/review_exam.html', result=attempt_record)


@main.route('/subject/<slug>')
def subject_detail(slug):
    """
    SUBJECT REPOSITORY VIEW

    Lists all lectures (Pages) within a specific subject.
    Open to authenticated students and staff.
    """
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()
    return render_template('subject.html', subject=target_subject)


@main.route('/subject/<slug>/page/<int:page_id>')
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

@main.route('/subject/<slug>/exam')
@main.route('/subject/<slug>/lecture/<int:page_id>/quiz')
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
        return redirect(url_for('main.student_login', next=request.full_path))

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


@main.route('/subject/<slug>/exam/submit', methods=['POST'])
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
        return redirect(url_for('main.student_login'))

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

    return redirect(url_for('main.student_dashboard'))

# ==============================================================================
# SECTION 5: STAFF DASHBOARD & TEACHER ADMINISTRATION
# ==============================================================================

@main.route('/teacher/dashboard')
@login_required
def teacher_dashboard():
    """
    CENTRAL STAFF CONTROL PANEL

    Logic:
    - Admin Mode: Pulls all data for global management (Teachers + Subjects).
    - Teacher Mode: Pulls data restricted to the current user's ownership.
    """
    # 1. Administrator Context
    if current_user.is_admin:
        # Fetch the complete subject roster
        all_global_subjects = Subject.query.all()
        # Fetch the complete staff roster
        all_staff_members = User.query.all()

        # Initialize the Subject Creation Form for the sidebar
        subject_creation_form = SubjectForm()
        # Populate the teacher dropdown with all staff
        subject_creation_form.teacher_id.choices = [
            (staff.id, staff.username) for staff in all_staff_members
        ]

        # Initialize the Staff Signup Form for the sidebar
        new_teacher_form = TeacherSignupForm()

        return render_template(
            'admin_dashboard.html',
            subjects=all_global_subjects,
            teachers=all_staff_members,
            subject_form=subject_creation_form,
            teacher_form=new_teacher_form
        )

    # 2. Standard Teacher Context
    else:
        # Fetch only subjects assigned to this specific teacher
        assigned_subjects = Subject.query.filter_by(
            teacher_id=current_user.id
        ).all()

        # Calculate performance metrics for the teacher's classroom
        # Joins ExamResults with Subjects to filter by teacher_id
        aggregate_results_count = ExamResult.query.join(Subject).filter(
            Subject.teacher_id == current_user.id
        ).count()

        return render_template(
            'teacher/dashboard.html',
            subjects=assigned_subjects,
            total_results=aggregate_results_count
        )


@main.route('/admin/add_teacher', methods=['POST'])
@login_required
def add_teacher():
    """
    STAFF REGISTRATION HANDLER

    Security: Admin Only.
    Function: Creates a new Teacher or Administrator account.
    """
    # 1. Permission Gate
    if not current_user.is_admin:
        abort(403)

    form = TeacherSignupForm()

    # 2. Form Processing
    if form.validate_on_submit():

        # A. Uniqueness Check (Email)
        existing_email = User.query.filter_by(email=form.email.data).first()
        if existing_email:
            flash(f'Error: The email address "{form.email.data}" is already in use.', 'danger')
            return redirect(url_for('main.teacher_dashboard'))

        # B. Uniqueness Check (Username)
        existing_name = User.query.filter_by(username=form.username.data).first()
        if existing_name:
            flash(f'Error: The name "{form.username.data}" is already taken.', 'danger')
            return redirect(url_for('main.teacher_dashboard'))

        # C. Security: Hash Password
        password_hash_str = bcrypt.generate_password_hash(form.password.data).decode('utf-8')

        # D. Object Instantiation
        is_admin_user = form.is_admin.data
        new_staff_member = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=password_hash_str,
            is_admin=is_admin_user
        )

        # E. Database Persistence
        try:
            db.session.add(new_staff_member)
            db.session.commit()

            role_label = "Administrator" if is_admin_user else "Teacher"
            flash(f'Success: {role_label} account created for {form.username.data}.', 'success')
        except Exception as db_err:
            db.session.rollback()
            flash(f'Database Error during staff creation: {str(db_err)}', 'danger')

    return redirect(url_for('main.teacher_dashboard'))


@main.route('/admin/edit/teacher/<int:teacher_id>', methods=['GET', 'POST'])
@login_required
def edit_teacher(teacher_id):
    """
    STAFF MODIFICATION INTERFACE

    Allows changing name, email, permissions, or resetting password.
    """
    if not current_user.is_admin:
        abort(403)

    # Fetch existing data
    target_staff = User.query.get_or_404(teacher_id)
    form = TeacherEditForm(obj=target_staff)

    if form.validate_on_submit():
        # Check uniqueness for modified fields
        if target_staff.username != form.username.data:
            if User.query.filter_by(username=form.username.data).first():
                flash('Error: The new username is already taken.', 'danger')
                return redirect(url_for('main.edit_teacher', teacher_id=target_staff.id))

        if target_staff.email != form.email.data:
            if User.query.filter_by(email=form.email.data).first():
                flash('Error: The new email is already in use.', 'danger')
                return redirect(url_for('main.edit_teacher', teacher_id=target_staff.id))

        # Update Visible Info
        target_staff.username = form.username.data
        target_staff.email = form.email.data

        # Security Logic: Prevent Admins from accidentally downgrading themselves
        if target_staff.id == current_user.id:
            target_staff.is_admin = True
        else:
            target_staff.is_admin = form.is_admin.data

        # Optional Password Reset
        if form.password.data:
            new_pw_hash = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
            target_staff.password_hash = new_pw_hash
            flash('Password has been reset.', 'success')

        db.session.commit()
        flash('Staff profile updated.', 'success')
        return redirect(url_for('main.teacher_dashboard'))

    return render_template('admin/edit_teacher.html', form=form, teacher=target_staff)


@main.route('/admin/delete/teacher/<int:teacher_id>')
@login_required
def delete_teacher(teacher_id):
    """
    ROBUST TEACHER REMOVAL (BOTTOM-UP CLEANUP)

    MySQL Constraint Logic:
    We cannot delete a teacher if they own subjects that have exams with answers.
    We delete in this order: Answers -> Results -> Questions -> Pages -> Subjects -> User.
    """
    if not current_user.is_admin:
        abort(403)

    target_staff = User.query.get_or_404(teacher_id)

    # 1. Logic Check: Cannot delete self
    if target_staff.id == current_user.id:
        flash('Security Violation: You cannot delete your own account.', 'danger')
        return redirect(url_for('main.teacher_dashboard'))

    try:
        # 2. Iterate through Subjects
        subjects_to_clear = Subject.query.filter_by(teacher_id=target_staff.id).all()

        for subj in subjects_to_clear:
            # A. Clean up Exams
            exams_found = ExamResult.query.filter_by(subject_id=subj.id).all()
            for attempt in exams_found:
                # Delete Child Answers first
                StudentAnswer.query.filter_by(exam_id=attempt.id).delete()
                # Delete the Result
                db.session.delete(attempt)

            # B. Clean up Questions
            questions_found = Question.query.filter_by(subject_id=subj.id).all()
            for quest in questions_found:
                # Delete legacy answer links
                StudentAnswer.query.filter_by(question_id=quest.id).delete()
                db.session.delete(quest)

            # C. Clean up Pages
            # This handles both Page content and the relationship to resources
            Page.query.filter_by(subject_id=subj.id).delete()

            # D. Delete the Subject itself
            db.session.delete(subj)

        # 3. Final Step: Remove the Staff Member
        db.session.delete(target_staff)
        db.session.commit()
        flash(f'Account for {target_staff.username} and all associated course data have been purged.', 'success')

    except Exception as cleanup_err:
        db.session.rollback()
        flash(f'Integrity Error during deletion: {str(cleanup_err)}', 'danger')

    return redirect(url_for('main.teacher_dashboard'))


@main.route('/admin/view_teacher/<int:teacher_id>')
@login_required
def view_teacher(teacher_id):
    """
    SIMULATED TEACHER VIEW

    Allows an Administrator to enter a 'Read-Only' view of a specific teacher's
    classroom to verify content or check results.
    """
    if not current_user.is_admin:
        abort(403)

    teacher_record = User.query.get_or_404(teacher_id)
    teacher_subjects = Subject.query.filter_by(teacher_id=teacher_record.id).all()

    # Aggregated stats for the view
    results_count = ExamResult.query.join(Subject).filter(
        Subject.teacher_id == teacher_record.id
    ).count()

    return render_template(
        'teacher/dashboard.html',
        subjects=teacher_subjects,
        total_results=results_count,
        view_as_admin=True,
        teacher_name=teacher_record.username
    )


# ==============================================================================
# SECTION 6: STUDENT ADMINISTRATION (TASK 1 LOGIC)
# ==============================================================================

@main.route('/admin/students', methods=['GET', 'POST'])
@login_required
def admin_students():
    """
    STUDENT MANAGEMENT HUB

    - Provides Roster view.
    - Provides Manual Add form.
    - Provides access to Bulk Import.
    """
    if not current_user.is_admin:
        abort(403)

    form_manual = StudentForm()
    form_batch = BulkImportForm()

    # Pre-generate a code to show in the UI placeholder
    if request.method == 'GET':
        form_manual.access_code.data = generate_access_code()

    # Manual Registration Logic
    if form_manual.validate_on_submit():
        # Uniqueness Check
        if Student.query.filter_by(access_code=form_manual.access_code.data).first():
            flash('Error: This Access Code is already in use.', 'danger')
        else:
            new_student = Student(
                full_name=form_manual.full_name.data,
                access_code=form_manual.access_code.data,
                group_id=form_manual.group_id.data
            )
            db.session.add(new_student)
            db.session.commit()
            flash(f'Student "{form_manual.full_name.data}" registered successfully.', 'success')
            return redirect(url_for('main.admin_students'))

    # Fetch all students for the table
    all_students_roster = Student.query.all()

    return render_template(
        'admin/students.html',
        form=form_manual,
        students=all_students_roster,
        import_form=form_batch
    )


@main.route('/admin/edit/student/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    """
    TASK 1: PROTECTED STUDENT EDIT

    Goal: Change name, code, or group without breaking Database integrity.
    Since Answer records are linked by student.id (Primary Key),
    changing visibile attributes does not affect history.
    """
    if not current_user.is_admin:
        abort(403)

    student_record = Student.query.get_or_404(student_id)
    form = StudentEditForm(obj=student_record)

    if form.validate_on_submit():
        # Check if the code was changed and if the new one is taken
        if student_record.access_code != form.access_code.data:
            code_check = Student.query.filter_by(access_code=form.access_code.data).first()
            if code_check:
                flash('Critical Error: The new access code is already assigned to someone else.', 'danger')
                return render_template('admin/edit_student.html', form=form, student=student_record)

        # Update Record
        student_record.full_name = form.full_name.data
        student_record.access_code = form.access_code.data
        student_record.group_id = form.group_id.data

        try:
            db.session.commit()
            flash('Student profile updated. All grades and history remain linked.', 'success')
            return redirect(url_for('main.admin_students'))
        except Exception as e:
            db.session.rollback()
            flash(f'Database Error: {str(e)}', 'danger')

    return render_template('admin/edit_student.html', form=form, student=student_record)


@main.route('/admin/delete/student/<int:student_id>')
@login_required
def delete_student(student_id):
    """
    SAFE DELETE FOR INDIVIDUAL STUDENTS

    Cleanup Process: Answers -> Results -> Student.
    """
    if not current_user.is_admin:
        abort(403)

    target_student = Student.query.get_or_404(student_id)

    try:
        # 1. Wipe Choice Logs
        StudentAnswer.query.filter_by(student_id=target_student.id).delete()
        # 2. Wipe Result History
        ExamResult.query.filter_by(student_id=target_student.id).delete()
        # 3. Wipe Student Record
        db.session.delete(target_student)

        db.session.commit()
        flash(f'Student "{target_student.full_name}" and all their records have been removed.', 'success')
    except Exception as fatal_err:
        db.session.rollback()
        flash(f'Failed to delete student: {str(fatal_err)}', 'danger')

    return redirect(url_for('main.admin_students'))


@main.route('/admin/delete/all/students', methods=['POST'])
@login_required
def delete_all_students():
    """
    THE NUCLEAR OPTION (BATCH WIPE)

    Deletes every single student and all academic data from the system.
    Leaves Subjects and Teachers intact.
    """
    if not current_user.is_admin:
        abort(403)

    try:
        # BOTTOM-UP WIPE
        # Step 1: Remove all answers (the deepest level)
        count_answers = db.session.query(StudentAnswer).delete()

        # Step 2: Remove all exam scores
        count_results = db.session.query(ExamResult).delete()

        # Step 3: Remove all students
        count_students = db.session.query(Student).delete()

        db.session.commit()
        flash(f'Database Wipe Successful: {count_students} students, {count_results} exams, and {count_answers} choices deleted.', 'success')

    except Exception as critical_wipe_error:
        db.session.rollback()
        flash(f'CRITICAL SYSTEM ERROR during batch wipe: {str(critical_wipe_error)}', 'danger')

    return redirect(url_for('main.admin_students'))


# ==============================================================================
# SECTION 7: SYSTEM COMMAND CENTER & DOCUMENTATION
# ==============================================================================

@main.route('/admin/system/commands')
@login_required
def admin_command_center():
    """
    SYSTEM DOCUMENTATION HUB (RE-NAMED TO AVOID OVERWRITE ERROR)

    Displays the list of saved maintenance scripts.
    """
    if not current_user.is_admin:
        abort(403)

    # Fetch all documented commands
    saved_commands = SystemCommand.query.all()
    form_entry = CommandForm()

    return render_template(
        'admin/commands.html',
        commands=saved_commands,
        form=form_entry
    )


@main.route('/admin/system/commands/add', methods=['POST'])
@login_required
def add_command():
    """Logic to add a new command to the documentation."""
    if not current_user.is_admin:
        abort(403)

    form = CommandForm()
    if form.validate_on_submit():
        new_cmd = SystemCommand(
            title=form.title.data,
            command_text=form.command_text.data,
            description=form.description.data
        )

        try:
            db.session.add(new_cmd)
            db.session.commit()
            flash('Maintenance script documented successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('main.admin_command_center'))


@main.route('/admin/system/commands/delete/<int:cmd_id>')
@login_required
def delete_command(cmd_id):
    """Logic to remove a command from documentation."""
    if not current_user.is_admin:
        abort(403)

    target_cmd = SystemCommand.query.get_or_404(cmd_id)

    try:
        db.session.delete(target_cmd)
        db.session.commit()
        flash('Documentation entry removed.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('main.admin_command_center'))

# ==============================================================================
# SECTION 8: BULK IMPORT ENGINE (WITH LANGUAGE & LECTURE LOGIC)
# ==============================================================================

@main.route('/admin/import/students', methods=['POST'])
@login_required
def import_students_step1():
    """
    BULK STUDENT IMPORT (STEP 1: PARSING)

    Logic:
    - Reads Excel or CSV into a Pandas DataFrame.
    - Validates presence of 'Name' and 'Group' columns.
    - Generates temporary preview data with auto-generated codes.
    """
    if not current_user.is_admin:
        abort(403)

    form = BulkImportForm()

    if form.validate_on_submit():
        uploaded_file = form.file.data
        file_extension = uploaded_file.filename.lower()

        try:
            # Read file using Pandas
            if file_extension.endswith('.csv'):
                data_frame = pd.read_csv(uploaded_file)
            else:
                data_frame = pd.read_excel(uploaded_file)

            # Normalize column names to lowercase for robust matching
            data_frame.columns = [col_name.lower().strip() for col_name in data_frame.columns]

            # Validate required columns
            if 'name' not in data_frame.columns or 'group' not in data_frame.columns:
                flash('Import Error: Your file must contain columns named "Name" and "Group".', 'danger')
                return redirect(url_for('main.admin_students'))

            # Construct the preview list
            batch_preview_list = []
            for index, row in data_frame.iterrows():
                batch_preview_list.append({
                    'full_name': str(row['name']),
                    'group_id': str(row['group']),
                    'access_code': generate_access_code()
                })

            # Render the intermediate preview page
            return render_template(
                'admin/import_preview.html',
                data=batch_preview_list,
                import_type='student',
                title="Verify Student Batch"
            )

        except Exception as e:
            flash(f'An error occurred while reading the file: {str(e)}', 'danger')
            return redirect(url_for('main.admin_students'))

    flash('File upload failed. Please ensure you selected a valid CSV or Excel file.', 'danger')
    return redirect(url_for('main.admin_students'))


@main.route('/teacher/import/questions/<int:subject_id>', methods=['POST'])
@login_required
def import_questions_step1(subject_id):
    """
    BULK QUESTION IMPORT (STEP 1: PARSING)

    Logic:
    - Parses the question table.
    - Fetches current Subject Lectures to populate the Batch Settings dropdown.
    """
    # 1. Permission and Context check
    target_subject = Subject.query.get_or_404(subject_id)
    if not current_user.is_admin and target_subject.teacher_id != current_user.id:
        abort(403)

    form = BulkImportForm()

    # 2. Fetch all lectures associated with this subject for the preview dropdown
    available_lectures = []
    for p in target_subject.pages:
        available_lectures.append({
            'id': p.id,
            'title': p.title
        })

    # 3. Handle File
    if form.validate_on_submit():
        uploaded_file = form.file.data
        file_extension = uploaded_file.filename.lower()

        try:
            if file_extension.endswith('.csv'):
                data_frame = pd.read_csv(uploaded_file)
            else:
                data_frame = pd.read_excel(uploaded_file)

            data_frame.columns = [col.lower().strip() for col in data_frame.columns]

            # Define required structure
            required_fields = ['question', 'opt a', 'opt b', 'opt c', 'opt d', 'answer']
            missing_fields = [f for f in required_fields if f not in data_frame.columns]

            if missing_fields:
                flash(f'Import Error: Missing columns: {", ".join(missing_fields)}', 'danger')
                return redirect(url_for('main.builder_exam', subject=target_subject.id))

            # Prepare Preview
            question_preview_data = []
            for _, row in data_frame.iterrows():
                question_preview_data.append({
                    'question_text': str(row['question']),
                    'option_a': str(row['opt a']),
                    'option_b': str(row['opt b']),
                    'option_c': str(row['opt c']),
                    'option_d': str(row['opt d']),
                    'correct_answer': str(row['answer']).upper().strip()[0]
                })

            return render_template(
                'admin/import_preview.html',
                data=question_preview_data,
                import_type='question',
                subject_id=target_subject.id,
                lectures=available_lectures, # Passes the dropdown list
                title=f"Verify Questions for {target_subject.name}"
            )

        except Exception as file_err:
            flash(f'Processing Error: {str(file_err)}', 'danger')
            return redirect(url_for('main.builder_exam', subject=target_subject.id))

    flash('Invalid request or file format.', 'danger')
    return redirect(url_for('main.builder_exam', subject=target_subject.id))


@main.route('/common/import/confirm', methods=['POST'])
@login_required
def process_import_confirmation():
    """
    BULK IMPORT (STEP 2: COMMITMENT)

    Logic:
    - Receives JSON string of data.
    - Captures Global Batch settings (Lecture ID, Language).
    - Writes to DB.
    """
    try:
        # 1. Data Extraction
        raw_json_data = request.form.get('data')
        import_category = request.form.get('import_type')
        parsed_data = json.loads(raw_json_data)

        # 2. Handle Student Commit
        if import_category == 'student':
            if not current_user.is_admin:
                abort(403)

            save_count = 0
            for student_row in parsed_data:
                # Resolve potential access code collisions
                final_code = student_row['access_code']
                while Student.query.filter_by(access_code=final_code).first():
                    final_code = generate_access_code()

                db.session.add(Student(
                    full_name=student_row['full_name'],
                    access_code=final_code,
                    group_id=student_row['group_id'][:20] # Strict string truncation
                ))
                save_count += 1

            db.session.commit()
            flash(f'Batch Processed: {save_count} students added.', 'success')
            return redirect(url_for('main.admin_students'))

        # 3. Handle Question Commit (Includes Batch Language and Lecture)
        elif import_category == 'question':
            subj_id_str = request.form.get('subject_id')
            subject_record = Subject.query.get_or_404(int(subj_id_str))

            if not current_user.is_admin and subject_record.teacher_id != current_user.id:
                abort(403)

            # --- EXTRACT BATCH SETTINGS FROM FORM ---
            # Lecture ID
            global_pid = request.form.get('bulk_lecture_id')
            if global_pid == "" or global_pid == "None":
                global_pid = None
            else:
                global_pid = int(global_pid)

            # Language Toggle (Task Requirement)
            bulk_lang_val = request.form.get('bulk_language')
            mark_kurdish = (bulk_lang_val == 'on')

            q_save_count = 0
            for q_row in parsed_data:
                db.session.add(Question(
                    question_text=q_row['question_text'],
                    option_a=q_row['option_a'],
                    option_b=q_row['option_b'],
                    option_c=q_row['option_c'],
                    option_d=q_row['option_d'],
                    correct_answer=q_row['correct_answer'],
                    subject_id=subject_record.id,
                    page_id=global_pid,     # Linked to specific lecture
                    is_kurdish=mark_kurdish # Applied globally per your request
                ))
                q_save_count += 1

            db.session.commit()
            flash(f'Batch Processed: {q_save_count} questions assigned to bank.', 'success')
            return redirect(url_for('main.builder_exam', subject=subject_record.id))

    except Exception as commit_error:
        db.session.rollback()
        flash(f'Critical Commit Failure: {str(commit_error)}', 'danger')
        return redirect(url_for('main.teacher_dashboard'))

    return redirect(url_for('main.teacher_dashboard'))


# ==============================================================================
# SECTION 9: SUBJECT & CONTENT MANAGEMENT
# ==============================================================================

@main.route('/teacher/add_subject', methods=['POST'])
@login_required
def add_subject():
    """Initializes a new course subject."""
    if not current_user.is_admin:
        abort(403)

    form = SubjectForm()
    # Populate the assigned teacher dropdown
    form.teacher_id.choices = [(t.id, t.username) for t in User.query.all()]

    if form.validate_on_submit():
        # Verify slug uniqueness
        if Subject.query.filter_by(slug=form.slug.data).first():
            flash('Error: The URL Slug must be unique across all subjects.', 'danger')
        else:
            new_subj = Subject(
                name=form.name.data,
                slug=form.slug.data,
                description=form.description.data,
                teacher_id=form.teacher_id.data
            )
            db.session.add(new_subj)
            db.session.commit()
            flash(f'Subject "{form.name.data}" created successfully.', 'success')

    return redirect(url_for('main.teacher_dashboard'))


@main.route('/teacher/edit/subject/<int:subject_id>', methods=['GET', 'POST'])
@login_required
def edit_subject(subject_id):
    """Edits subject metadata."""
    subj_record = Subject.query.get_or_404(subject_id)

    if not current_user.is_admin and subj_record.teacher_id != current_user.id:
        abort(403)

    form = SubjectForm(obj=subj_record)

    # Restrict dropdown based on role
    if current_user.is_admin:
         form.teacher_id.choices = [(t.id, t.username) for t in User.query.all()]
    else:
         form.teacher_id.choices = [(current_user.id, current_user.username)]

    if form.validate_on_submit():
        subj_record.name = form.name.data
        subj_record.slug = form.slug.data
        subj_record.description = form.description.data

        if current_user.is_admin:
             subj_record.teacher_id = form.teacher_id.data

        db.session.commit()
        flash('Subject information updated.', 'success')
        return redirect(url_for('main.teacher_dashboard'))

    return render_template('teacher/builder.html', form=form, title="Edit Subject Details", subject=subj_record)


@main.route('/teacher/delete/subject/<int:subject_id>')
@login_required
def delete_subject(subject_id):
    """
    SAFE SUBJECT DELETION

    Removes:
    1. Answer Logs
    2. Results
    3. Pages/Lectures
    4. Questions
    5. Subject record
    """
    subj_record = Subject.query.get_or_404(subject_id)

    if not current_user.is_admin and subj_record.teacher_id != current_user.id:
        abort(403)

    try:
        # A. Clear results and choices
        exam_list = ExamResult.query.filter_by(subject_id=subj_record.id).all()
        for attempt in exam_list:
            StudentAnswer.query.filter_by(exam_id=attempt.id).delete()
            db.session.delete(attempt)

        # B. Clear Lectures
        Page.query.filter_by(subject_id=subj_record.id).delete()

        # C. Clear Question bank
        questions_list = Question.query.filter_by(subject_id=subj_record.id).all()
        for q in questions_list:
            StudentAnswer.query.filter_by(question_id=q.id).delete()
            db.session.delete(q)

        # D. Purge Subject
        db.session.delete(subj_record)
        db.session.commit()
        flash(f'Subject "{subj_record.name}" and all internal content has been deleted.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Deletion failed: {str(e)}', 'danger')

    return redirect(url_for('main.teacher_dashboard'))


@main.route('/teacher/builder/info', methods=['GET', 'POST'])
@login_required
def builder_info():
    """Route to add a new lecture page."""
    sid_param = request.args.get('subject')
    subj_record = Subject.query.get_or_404(sid_param)

    if not current_user.is_admin and subj_record.teacher_id != current_user.id:
        abort(403)

    form = PageForm()
    form.subject_id.choices = [(subj_record.id, subj_record.name)]

    if request.method == 'GET':
        form.subject_id.data = subj_record.id

    if form.validate_on_submit():
        new_page_record = Page(
            title=form.title.data,
            content_body=form.content_body.data,
            content_body_kurdish=form.content_body_kurdish.data,
            subject_id=subj_record.id
        )
        db.session.add(new_page_record)
        db.session.commit()
        flash('Lecture content published.', 'success')
        return redirect(url_for('main.teacher_dashboard'))

    return render_template('teacher/builder.html', form=form, title="Create New Lecture", subject=subj_record)


@main.route('/teacher/edit/page/<int:page_id>', methods=['GET', 'POST'])
@login_required
def edit_page(page_id):
    """Route to edit lecture content and manage multiple resources."""
    target_page = Page.query.get_or_404(page_id)

    if not current_user.is_admin and target_page.subject.teacher_id != current_user.id:
        abort(403)

    form = PageForm(obj=target_page)
    form.subject_id.choices = [(target_page.subject.id, target_page.subject.name)]

    # Resource management form
    res_form_instance = ResourceForm()

    if form.validate_on_submit():
        target_page.title = form.title.data
        target_page.content_body = form.content_body.data
        target_page.content_body_kurdish = form.content_body_kurdish.data
        db.session.commit()
        flash('Changes saved.', 'success')
        return redirect(url_for('main.subject_detail', slug=target_page.subject.slug))

    return render_template(
        'teacher/builder.html',
        form=form,
        title="Edit Lecture Content",
        subject=target_page.subject,
        page=target_page,
        resource_form=res_form_instance
    )


@main.route('/teacher/delete/page/<int:page_id>')
@login_required
def delete_page(page_id):
    """Purges a single lecture."""
    target_page = Page.query.get_or_404(page_id)

    if not current_user.is_admin and target_page.subject.teacher_id != current_user.id:
        abort(403)

    subject_slug_ref = target_page.subject.slug
    db.session.delete(target_page)
    db.session.commit()

    flash('Lecture deleted.', 'success')
    return redirect(url_for('main.subject_detail', slug=subject_slug_ref))


@main.route('/teacher/resource/add/<int:page_id>', methods=['POST'])
@login_required
def add_resource(page_id):
    """Logic to attach a link to a lecture."""
    target_page = Page.query.get_or_404(page_id)

    if not current_user.is_admin and target_page.subject.teacher_id != current_user.id:
        abort(403)

    form = ResourceForm()
    if form.validate_on_submit():
        new_res = Resource(
            title=form.title.data,
            link=form.link.data,
            page_id=target_page.id
        )
        db.session.add(new_res)
        db.session.commit()
        flash('Learning resource attached.', 'success')
    else:
        flash('Attachment Error: Title and Link are required.', 'danger')

    return redirect(url_for('main.edit_page', page_id=target_page.id))


@main.route('/teacher/resource/delete/<int:resource_id>')
@login_required
def delete_resource(resource_id):
    """Logic to remove an attached link."""
    target_res = Resource.query.get_or_404(resource_id)
    parent_page_id = target_res.page_id

    if not current_user.is_admin and target_res.page.subject.teacher_id != current_user.id:
        abort(403)

    db.session.delete(target_res)
    db.session.commit()
    flash('Resource removed.', 'success')
    return redirect(url_for('main.edit_page', page_id=parent_page_id))


# ==============================================================================
# SECTION 10: QUESTION BANK MANAGEMENT
# ==============================================================================

@main.route('/teacher/builder/exam', methods=['GET'])
@login_required
def builder_exam():
    """Displays the Bulk Spreadsheet Editor for Questions."""
    sid_param = request.args.get('subject')
    target_subject = Subject.query.get_or_404(sid_param)

    if not current_user.is_admin and target_subject.teacher_id != current_user.id:
        abort(403)

    form = QuestionForm()
    import_form = BulkImportForm()

    # Prepare lecture list for the spreadsheet column
    subject_lectures_list = [{'id': p.id, 'title': p.title} for p in target_subject.pages]

    existing_questions_data = []
    for question in target_subject.questions:
        existing_questions_data.append({
            'id': question.id,
            'text': question.question_text,
            'a': question.option_a,
            'b': question.option_b,
            'c': question.option_c,
            'd': question.option_d,
            'correct': question.correct_answer,
            'page_id': question.page_id,
            'is_kurdish': question.is_kurdish
        })

    return render_template(
        'teacher/builder.html',
        form=form,
        import_form=import_form,
        title="Question Bank Spreadsheet",
        subject=target_subject,
        questions_json=existing_questions_data,
        pages=subject_lectures_list
    )


@main.route('/teacher/api/save_questions/<int:subject_id>', methods=['POST'])
@login_required
def save_questions_api(subject_id):
    """The AJAX backend that saves the Bulk Editor grid data."""
    target_subject = Subject.query.get_or_404(subject_id)
    if not current_user.is_admin and target_subject.teacher_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    incoming_json_data = request.get_json()
    if incoming_json_data is None:
        return jsonify({'status': 'error', 'message': 'Payload Empty'}), 400

    try:
        # Determine which IDs were sent
        sent_ids = [q['id'] for q in incoming_json_data if q.get('id')]

        # 1. Clean up deleted questions
        current_db_questions = Question.query.filter_by(subject_id=target_subject.id).all()
        for q_db in current_db_questions:
            if q_db.id not in sent_ids:
                # Always remove answer logs first
                StudentAnswer.query.filter_by(question_id=q_db.id).delete()
                db.session.delete(q_db)

        # 2. Process UPSERT (Update or Insert)
        for data_row in incoming_json_data:
            text_content = data_row.get('text', '').strip()
            if not text_content:
                continue

            # Handle Foreign Key for Lecture
            pid_val = data_row.get('page_id')
            if pid_val == "" or pid_val == "None" or pid_val == 0:
                pid_val = None

            # Boolean check for language
            kurdish_flag = data_row.get('is_kurdish', False)

            if data_row.get('id'):
                # Update existing
                target_q = Question.query.get(data_row['id'])
                if target_q and target_q.subject_id == target_subject.id:
                    target_q.question_text = text_content
                    target_q.option_a = data_row.get('a', '')
                    target_q.option_b = data_row.get('b', '')
                    target_q.option_c = data_row.get('c', '')
                    target_q.option_d = data_row.get('d', '')
                    target_q.correct_answer = data_row.get('correct', 'A')
                    target_q.page_id = pid_val
                    target_q.is_kurdish = kurdish_flag
            else:
                # Insert new
                db.session.add(Question(
                    question_text=text_content,
                    option_a=data_row.get('a', ''),
                    option_b=data_row.get('b', ''),
                    option_c=data_row.get('c', ''),
                    option_d=data_row.get('d', ''),
                    correct_answer=data_row.get('correct', 'A'),
                    subject_id=target_subject.id,
                    page_id=pid_val,
                    is_kurdish=kurdish_flag
                ))

        db.session.commit()
        return jsonify({'status': 'success'})

    except Exception as fatal_api_err:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(fatal_api_err)}), 500


@main.route('/teacher/export/questions/<int:subject_id>', methods=['GET'])
@login_required
def export_questions_csv(subject_id):
    """Exports Question Bank for a subject. Uses strict quoting and BOM."""
    target_subject = Subject.query.get_or_404(subject_id)
    if not current_user.is_admin and target_subject.teacher_id != current_user.id:
        abort(403)

    string_io_obj = io.StringIO()
    string_io_obj.write('\ufeff') # BOM for Excel UTF-8
    csv_writer_obj = csv.writer(string_io_obj, quoting=csv.QUOTE_ALL)

    csv_writer_obj.writerow(['Question', 'Opt A', 'Opt B', 'Opt C', 'Opt D', 'Ans', 'Kurdish'])
    for q in target_subject.questions:
        csv_writer_obj.writerow([
            q.question_text, q.option_a, q.option_b, q.option_c, q.option_d, q.correct_answer,
            "True" if q.is_kurdish else "False"
        ])

    return Response(
        string_io_obj.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={target_subject.slug}_questions.csv"}
    )


@main.route('/teacher/edit/question/<int:question_id>', methods=['GET', 'POST'])
@login_required
def edit_question(question_id):
    """Edit a single question manually."""
    target_q = Question.query.get_or_404(question_id)
    if not current_user.is_admin and target_q.subject.teacher_id != current_user.id:
        abort(403)

    form = QuestionForm(obj=target_q)
    form.subject_id.choices = [(target_q.subject.id, target_q.subject.name)]

    # Get available lectures for dropdown
    form.page_id.choices = [(0, "(None - General Exam)")] + [(p.id, p.title) for p in target_q.subject.pages]

    if form.validate_on_submit():
        target_q.question_text = form.question_text.data
        target_q.option_a = form.option_a.data
        target_q.option_b = form.option_b.data
        target_q.option_c = form.option_c.data
        target_q.option_d = form.option_d.data
        target_q.correct_answer = form.correct_answer.data
        target_q.is_kurdish = form.is_kurdish.data

        # Handle the 0/None selection for page_id
        if form.page_id.data == 0:
            target_q.page_id = None
        else:
            target_q.page_id = form.page_id.data

        db.session.commit()
        flash('Question updated.', 'success')
        return redirect(url_for('main.subject_detail', slug=target_q.subject.slug))

    return render_template('teacher/builder.html', form=form, title="Modify Question", subject=target_q.subject)


@main.route('/teacher/delete/question/<int:question_id>')
@login_required
def delete_question(question_id):
    """Single question deletion logic."""
    target_q = Question.query.get_or_404(question_id)
    if not current_user.is_admin and target_q.subject.teacher_id != current_user.id:
        abort(403)

    subject_slug_ref = target_q.subject.slug
    try:
        StudentAnswer.query.filter_by(question_id=target_q.id).delete()
        db.session.delete(target_q)
        db.session.commit()
        flash('Question removed from bank.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error during question deletion: {str(e)}', 'danger')

    return redirect(url_for('main.subject_detail', slug=subject_slug_ref))


# ==============================================================================
# SECTION 11: ANALYTICS, EXPORTS & CMS
# ==============================================================================

@main.route('/teacher/analytics')
@login_required
def teacher_analytics():
    """COMPREHENSIVE ANALYTICS HUB"""
    if current_user.is_admin:
        set_questions = Question.query.all()
        set_results = ExamResult.query.all()
    else:
        subject_ids_owned = [subj.id for subj in current_user.subjects]
        set_questions = Question.query.filter(Question.subject_id.in_(subject_ids_owned)).all()
        set_results = ExamResult.query.filter(ExamResult.subject_id.in_(subject_ids_owned)).all()

    # 1. Question Difficulty Analysis
    question_stats_list = []
    for q_item in set_questions:
        ans_total = StudentAnswer.query.filter_by(question_id=q_item.id).count()
        ans_wrong = StudentAnswer.query.filter_by(question_id=q_item.id, is_correct=False).count()
        difficulty_percent = int((ans_wrong/ans_total)*100) if ans_total > 0 else 0
        question_stats_list.append({
            'subject': q_item.subject.name,
            'text': q_item.question_text,
            'failures': ans_wrong,
            'difficulty': difficulty_percent
        })
    question_stats_list.sort(key=lambda x: x['difficulty'], reverse=True)

    # 2. Student Rankings
    unique_student_ids = set(result.student_id for result in set_results)
    students_active = Student.query.filter(Student.id.in_(unique_student_ids)).all()
    student_metric_data = []
    at_risk_student_list = []

    for active_student in students_active:
        personal_scores = [r.score for r in set_results if r.student_id == active_student.id]
        personal_average = round(sum(personal_scores)/len(personal_scores), 1) if personal_scores else 0

        student_obj = {
            'id': active_student.id,
            'name': active_student.full_name,
            'group': active_student.group_id,
            'avg_score': personal_average
        }
        student_metric_data.append(student_obj)
        if personal_average < 50:
            at_risk_student_list.append(student_obj)

    # 3. Chart Data Preparations
    # Group Chart
    group_metric_map = {}
    for r in set_results:
        g_id = r.student.group_id
        if g_id not in group_metric_map: group_metric_map[g_id] = []
        group_metric_map[g_id].append(r.score)

    g_labels = list(group_metric_map.keys())
    g_values = [round(sum(group_metric_map[k])/len(group_metric_map[k]), 1) for k in g_labels]

    # Distribution Chart
    dist_buckets = {'Excellent': 0, 'Good': 0, 'Pass': 0, 'Fail': 0}
    for r in set_results:
        if r.score >= 90: dist_buckets['Excellent'] += 1
        elif r.score >= 70: dist_buckets['Good'] += 1
        elif r.score >= 50: dist_buckets['Pass'] += 1
        else: dist_buckets['Fail'] += 1

    # Time Trend Chart
    sorted_history = sorted(set_results, key=lambda x: x.date_submitted)
    timeline_map = {}
    for r in sorted_history:
        date_str = r.date_submitted.strftime('%Y-%m-%d')
        if date_str not in timeline_map: timeline_map[date_str] = []
        timeline_map[date_str].append(r.score)

    t_labels = sorted(timeline_map.keys())
    t_values = [round(sum(timeline_map[d])/len(timeline_map[d]), 1) for d in t_labels]

    # Subject Mastery (Radar)
    radar_map = {}
    for r in set_results:
        s_name = r.subject.name
        if s_name not in radar_map: radar_map[s_name] = []
        radar_map[s_name].append(r.score)

    r_labels = list(radar_map.keys())
    r_values = [round(sum(radar_map[k])/len(radar_map[k]), 1) for k in r_labels]

    # Recent activity log
    activity_feed = sorted(set_results, key=lambda x: x.date_submitted, reverse=True)[:10]

    return render_template(
        'teacher/analytics.html',
        question_data=question_stats_list,
        student_data=student_metric_data,
        at_risk_students=at_risk_student_list,
        group_labels=g_labels,
        group_values=g_values,
        dist_values=list(dist_buckets.values()),
        trend_dates=t_labels,
        trend_scores=t_values,
        radar_labels=r_labels,
        radar_values=r_values,
        recent_activity=activity_feed
    )


@main.route('/teacher/analytics/student/<int:student_id>')
@login_required
def student_detail_view(student_id):
    """Detailed view for staff to see a student's answer grouped by attempt."""
    target_student = Student.query.get_or_404(student_id)

    attempt_query = ExamResult.query.filter_by(student_id=target_student.id)
    if not current_user.is_admin:
        teacher_subj_ids = [subj_obj.id for subj_obj in current_user.subjects]
        attempt_query = attempt_query.filter(ExamResult.subject_id.in_(teacher_subj_ids))

    exam_history_results = attempt_query.order_by(desc(ExamResult.date_submitted)).all()

    final_grouped_history = []
    for result_obj in exam_history_results:
        # We ensure cards are only created if answers were logged correctly
        if len(result_obj.answers) > 0:
            final_grouped_history.append({
                'exam': result_obj,
                'answers': result_obj.answers
            })
        else:
            # Automatic housekeeping for ghost results
            try:
                db.session.delete(result_obj)
                db.session.commit()
            except:
                db.session.rollback()

    return render_template(
        'teacher/student_detail.html',
        student=target_student,
        history=final_grouped_history
    )


@main.route('/teacher/export/grades')
@login_required
def export_grades():
    """Global CSV score export."""
    results_to_export = ExamResult.query.all() if current_user.is_admin else ExamResult.query.join(Subject).filter(Subject.teacher_id == current_user.id).all()

    output_stream = io.StringIO()
    output_stream.write('\ufeff') # BOM
    writer = csv.writer(output_stream, quoting=csv.QUOTE_ALL)

    writer.writerow(['Student', 'Group', 'Course', 'Score (%)', 'Date'])
    for res in results_to_export:
        writer.writerow([
            res.student.full_name,
            res.student.group_id,
            res.subject.name,
            res.score,
            res.date_submitted.strftime('%Y-%m-%d')
        ])

    return Response(
        output_stream.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=gradebook_export.csv"}
    )


@main.route('/teacher/export/student/answers/<int:student_id>')
@login_required
def export_student_answers(student_id):
    """Detailed CSV choice log export."""
    target_student = Student.query.get_or_404(student_id)
    results_to_export = ExamResult.query.filter_by(student_id=target_student.id).order_by(desc(ExamResult.date_submitted)).all()

    output_stream = io.StringIO()
    output_stream.write('\ufeff') # BOM
    writer = csv.writer(output_stream, quoting=csv.QUOTE_ALL)

    writer.writerow(['Timestamp', 'Subject', 'Question', 'Student Selected', 'Correct Key', 'Result Status'])
    for attempt in results_to_export:
        for choice in attempt.answers:
            writer.writerow([
                attempt.date_submitted.strftime('%Y-%m-%d %H:%M'),
                attempt.subject.name,
                choice.question.question_text,
                choice.selected_option,
                choice.question.correct_answer,
                "PASS" if choice.is_correct else "FAIL"
            ])

    return Response(
        output_stream.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=Choices_{target_student.full_name}.csv"}
    )


@main.route('/admin/export/full_backup')
@login_required
def export_full_backup():
    """
    GENERATES THE MASTER ENCRYPTED ZIP SYSTEM BACKUP.
    [UPGRADE]: Added PK/FK IDs and distinct 'subjects_master.csv' for lossless restoration.
    """
    if not current_user.is_admin:
        abort(403)

    binary_stream = io.BytesIO()

    with zipfile.ZipFile(binary_stream, 'w', zipfile.ZIP_DEFLATED) as master_zip:

        # 1. Staff (Users)
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w_obj = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w_obj.writerow(['ID', 'Name', 'Email', 'Password_Hash', 'Is_Admin'])
        for staff in User.query.all():
            w_obj.writerow([staff.id, staff.username, staff.email, staff.password_hash, staff.is_admin])
        master_zip.writestr('1_users.csv', s_obj.getvalue())

        # 2. Subjects (The missing piece)
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w_obj = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w_obj.writerow(['ID', 'Name', 'Slug', 'Description', 'Teacher_ID'])
        for subj in Subject.query.all():
            w_obj.writerow([subj.id, subj.name, subj.slug, subj.description, subj.teacher_id])
        master_zip.writestr('2_subjects.csv', s_obj.getvalue())

        # 3. Students
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w_obj = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w_obj.writerow(['ID', 'Full_Name', 'Access_Code', 'Group_ID'])
        for student in Student.query.all():
            w_obj.writerow([student.id, student.full_name, student.access_code, student.group_id])
        master_zip.writestr('3_students.csv', s_obj.getvalue())

        # 4. Pages (Lectures)
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w_obj = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w_obj.writerow(['ID', 'Subject_ID', 'Title', 'Content_EN', 'Content_KU'])
        for page in Page.query.all():
            w_obj.writerow([page.id, page.subject_id, page.title, page.content_body, page.content_body_kurdish])
        master_zip.writestr('4_pages.csv', s_obj.getvalue())

        # 5. Resources
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w_obj = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w_obj.writerow(['ID', 'Page_ID', 'Title', 'Link'])
        for res in Resource.query.all():
            w_obj.writerow([res.id, res.page_id, res.title, res.link])
        master_zip.writestr('5_resources.csv', s_obj.getvalue())

        # 6. Questions
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w_obj = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w_obj.writerow(['ID', 'Subject_ID', 'Page_ID', 'Question_Text', 'Option_A', 'Option_B', 'Option_C', 'Option_D', 'Correct', 'Is_Kurdish'])
        for q in Question.query.all():
            # Page ID can be None (Final Exam questions)
            p_id = q.page_id if q.page_id else ''
            w_obj.writerow([q.id, q.subject_id, p_id, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d, q.correct_answer, q.is_kurdish])
        master_zip.writestr('6_questions.csv', s_obj.getvalue())

        # 7. Exam Results (Attempts)
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w_obj = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w_obj.writerow(['ID', 'Student_ID', 'Subject_ID', 'Score', 'Date_Submitted'])
        for res in ExamResult.query.all():
            w_obj.writerow([res.id, res.student_id, res.subject_id, res.score, res.date_submitted])
        master_zip.writestr('7_results.csv', s_obj.getvalue())

        # 8. Student Answers (Details)
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w_obj = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w_obj.writerow(['ID', 'Student_ID', 'Question_ID', 'Exam_ID', 'Selected_Option', 'Is_Correct'])
        for ans in StudentAnswer.query.all():
            w_obj.writerow([ans.id, ans.student_id, ans.question_id, ans.exam_id, ans.selected_option, ans.is_correct])
        master_zip.writestr('8_answers.csv', s_obj.getvalue())

        # 9. System Commands
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w_obj = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w_obj.writerow(['Title', 'Command', 'Description'])
        for cmd in SystemCommand.query.all():
            w_obj.writerow([cmd.title, cmd.command_text, cmd.description])
        master_zip.writestr('9_commands.csv', s_obj.getvalue())

        # 10. Site Info
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w_obj = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w_obj.writerow(['Key', 'Title', 'Content'])
        for info in SiteInfo.query.all():
            w_obj.writerow([info.key, info.title, info.content])
        master_zip.writestr('10_siteinfo.csv', s_obj.getvalue())

    binary_stream.seek(0)
    current_time_str = datetime.now().strftime("%Y_%m_%d_%H%M")
    backup_file_name = f"StatInfo_FULL_BACKUP_{current_time_str}.zip"

    return Response(
        binary_stream.getvalue(),
        mimetype='application/zip',
        headers={"Content-Disposition": f"attachment;filename={backup_file_name}"}
    )


@main.route('/admin/system/restore', methods=['GET', 'POST'])
@login_required
def restore_system():
    """
    OPTIMIZED NUCLEAR RESTORE ROUTE (MEMORY SAFE).
    Wipes DB via row deletion and re-hydrates from ZIP using streaming.
    Prevents PythonAnywhere timeouts by handling data in chunks.
    """
    if not current_user.is_admin:
        abort(403)

    form = RestoreBackupForm()

    if form.validate_on_submit():
        file = form.backup_file.data
        if not file:
            flash('No file provided.', 'danger')
            return redirect(request.url)

        try:
            # 1. READ ZIP (Keep in memory, but process contents as streams)
            zip_buffer = io.BytesIO(file.read())
            
            with zipfile.ZipFile(zip_buffer, 'r') as archive:
                file_list = archive.namelist()
                
                # Validation
                required_files = ['1_users.csv', '2_subjects.csv', '3_students.csv']
                if not all(f in file_list for f in required_files):
                    flash('Invalid Backup Format. Missing core CSV files.', 'danger')
                    return redirect(request.url)

                # 2. SAFE WIPE (Delete rows in reverse dependency order)
                # Instead of Drop/Create, we empty tables. This keeps metadata locks happy.
                try:
                    db.session.query(StudentAnswer).delete()
                    db.session.query(ExamResult).delete()
                    db.session.query(Question).delete()
                    db.session.query(Resource).delete()
                    db.session.query(Page).delete()
                    db.session.query(Student).delete()
                    db.session.query(Subject).delete()
                    db.session.query(SiteInfo).delete()
                    db.session.query(SystemCommand).delete()
                    # We do NOT delete users, as that would kill the current admin session immediately.
                    # We will update/upsert users instead.
                    db.session.commit()
                except Exception as wipe_err:
                    db.session.rollback()
                    flash(f'Pre-Restore Wipe Failed: {wipe_err}', 'danger')
                    return redirect(request.url)

                # 3. REHYDRATE GENERATOR (Memory Efficient)
                def stream_csv(filename):
                    """Yields one row at a time to avoid loading 50k lines into RAM."""
                    if filename not in file_list:
                        return
                    
                    with archive.open(filename) as f:
                        text = io.TextIOWrapper(f, encoding='utf-8-sig', newline='')
                        reader = csv.DictReader(text)
                        for row in reader:
                            yield row

                # BUFFERED COMMIT HELPER
                def commit_batch(objects, limit=100):
                    db.session.add_all(objects)
                    if len(db.session.new) >= limit:
                        db.session.commit()
                
                # A. Users (Upsert Logic to keep Admin alive)
                # Note: We wipe non-admin users if we want a pure restore, but let's just 
                # strictly restore what is in the CSV.
                # Actually, to trust the backup, we should probably align with it.
                # But deleting the user *executing* the request is risky.
                # Let's delete all users EXCEPT current one, then restore? Too complex.
                # Simple strategy: Upsert all users from CSV. Existing ones get updated.
                
                user_batch = []
                # First, clear users not in the backup? 
                # For safety on PA, let's just Upsert.
                for row in stream_csv('1_users.csv'):
                    uid = int(row['ID'])
                    existing = User.query.get(uid)
                    if existing:
                        existing.username = row['Name']
                        existing.email = row['Email']
                        existing.password_hash = row['Password_Hash']
                        existing.is_admin = (row['Is_Admin'] == 'True')
                    else:
                        u = User(
                            id=uid,
                            username=row['Name'],
                            email=row['Email'],
                            password_hash=row['Password_Hash'],
                            is_admin=(row['Is_Admin'] == 'True')
                        )
                        db.session.add(u)
                db.session.commit()

                # B. Subjects
                for row in stream_csv('2_subjects.csv'):
                    db.session.add(Subject(
                        id=int(row['ID']),
                        name=row['Name'],
                        slug=row['Slug'],
                        description=row['Description'],
                        teacher_id=int(row['Teacher_ID'])
                    ))
                db.session.commit()

                # C. Students
                batch = []
                for row in stream_csv('3_students.csv'):
                    batch.append(Student(
                        id=int(row['ID']),
                        full_name=row['Full_Name'],
                        access_code=row['Access_Code'],
                        group_id=row['Group_ID']
                    ))
                    if len(batch) >= 100:
                        db.session.add_all(batch)
                        db.session.commit()
                        batch = []
                if batch: 
                    db.session.add_all(batch)
                    db.session.commit()

                # D. Pages
                batch = []
                for row in stream_csv('4_pages.csv'):
                    batch.append(Page(
                        id=int(row['ID']),
                        subject_id=int(row['Subject_ID']),
                        title=row['Title'],
                        content_body=row['Content_EN'],
                        content_body_kurdish=row['Content_KU']
                    ))
                    if len(batch) >= 50: # HTML content is heavy, smaller batch
                        db.session.add_all(batch)
                        db.session.commit()
                        batch = []
                if batch:
                    db.session.add_all(batch)
                    db.session.commit()

                # E. Resources
                for row in stream_csv('5_resources.csv'):
                    db.session.add(Resource(
                        id=int(row['ID']),
                        page_id=int(row['Page_ID']),
                        title=row['Title'],
                        link=row['Link']
                    ))
                db.session.commit()

                # F. Questions
                batch = []
                for row in stream_csv('6_questions.csv'):
                    pid = int(row['Page_ID']) if row['Page_ID'] else None
                    batch.append(Question(
                        id=int(row['ID']),
                        subject_id=int(row['Subject_ID']),
                        page_id=pid,
                        question_text=row['Question_Text'],
                        option_a=row['Option_A'],
                        option_b=row['Option_B'],
                        option_c=row['Option_C'],
                        option_d=row['Option_D'],
                        correct_answer=row['Correct'],
                        is_kurdish=(row['Is_Kurdish'] == 'True')
                    ))
                    if len(batch) >= 100:
                        db.session.add_all(batch)
                        db.session.commit()
                        batch = []
                if batch:
                    db.session.add_all(batch)
                    db.session.commit()

                # G. Exam Results
                batch = []
                for row in stream_csv('7_results.csv'):
                    d_str = row['Date_Submitted']
                    try:
                        d_obj = datetime.strptime(d_str, '%Y-%m-%d %H:%M:%S.%f')
                    except ValueError:
                        try:
                            d_obj = datetime.strptime(d_str, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            d_obj = datetime.utcnow()

                    batch.append(ExamResult(
                        id=int(row['ID']),
                        student_id=int(row['Student_ID']),
                        subject_id=int(row['Subject_ID']),
                        score=int(row['Score']),
                        date_submitted=d_obj
                    ))
                    if len(batch) >= 100:
                        db.session.add_all(batch)
                        db.session.commit()
                        batch = []
                if batch:
                    db.session.add_all(batch)
                    db.session.commit()

                # H. Student Answers (The BIG Table)
                batch = []
                for row in stream_csv('8_answers.csv'):
                    batch.append(StudentAnswer(
                        id=int(row['ID']),
                        student_id=int(row['Student_ID']),
                        question_id=int(row['Question_ID']),
                        exam_id=int(row['Exam_ID']),
                        selected_option=row['Selected_Option'],
                        is_correct=(row['Is_Correct'] == 'True')
                    ))
                    if len(batch) >= 200: # Simple data, larger batch
                        db.session.add_all(batch)
                        db.session.commit()
                        batch = []
                if batch:
                    db.session.add_all(batch)
                    db.session.commit()

                # I. Misc
                for row in stream_csv('9_commands.csv'):
                    db.session.add(SystemCommand(
                        title=row['Title'],
                        command_text=row['Command'],
                        description=row['Description']
                    ))
                
                for row in stream_csv('10_siteinfo.csv'):
                    db.session.add(SiteInfo(
                        key=row['Key'],
                        title=row['Title'],
                        content=row['Content']
                    ))
                
                db.session.commit()
                flash('SYSTEM RESTORE COMPLETED. Database re-hydrated successfully.', 'success')
                return redirect(url_for('main.teacher_dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f'CRITICAL RESTORE FAILURE: {str(e)}', 'danger')
            return redirect(request.url)

    return render_template('admin/restore_center.html', form=form)


@main.route('/admin/edit/about', methods=['GET', 'POST'])
@login_required
def edit_about():
    """CMS Administration for 'About Us'."""
    if not current_user.is_admin:
        abort(403)

    info_record = SiteInfo.query.filter_by(key='about').first()
    if not info_record:
        info_record = SiteInfo(key='about', title='About Us', content='')

    edit_form = InfoPageForm(obj=info_record)

    if edit_form.validate_on_submit():
        if not info_record.id:
            db.session.add(info_record)
        info_record.title = edit_form.title.data
        info_record.content = edit_form.content.data
        db.session.commit()
        flash('Public Information Page Updated.', 'success')
        return redirect(url_for('main.teacher_dashboard'))

    return render_template('admin/edit_about.html', form=edit_form)


# ==============================================================================
# SECTION 7: TOOL BASE
# ==============================================================================

@main.route('/toolbase', methods=['GET', 'POST'])
def toolbase():
    """
    TOOL BASE / EXTERNAL LINKS MANAGER
    """
    # Check if user is logged in (either as Staff via Flask-Login or Student via session)
    is_admin = False
    if current_user.is_authenticated:
        is_admin = current_user.is_admin
    # Guests and Students are allowed read-only access (fall-through)
        
    form = ToolForm()
    # Task: Bulk Import Form (Reusing existing one)
    import_form = BulkImportForm()
    
    # Only process form submission if user is admin
    if is_admin:
        # A. SINGLE TOOL ADD
        if form.validate_on_submit() and 'submit' in request.form:
             # Check if this valid submission is from the manual form
             # (Flask-WTF might validate both if fields overlap, but file field is unique)
            if not form.link.data:
                 # If link is missing but validation passed (odd case), skip
                 pass
            else:
                new_tool = Tool(
                    title=form.title.data,
                    link=form.link.data,
                    description=form.description.data
                )
                try:
                    db.session.add(new_tool)
                    db.session.commit()
                    flash('New tool added successfully.', 'success')
                    return redirect(url_for('main.toolbase'))
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error adding tool: {str(e)}', 'danger')

        # B. BULK IMPORT
        if import_form.validate_on_submit() and 'file' in request.files:
            uploaded_file = import_form.file.data
            filename = uploaded_file.filename.lower()
            
            try:
                # Read file
                if filename.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                # Normalize headers
                df.columns = [c.lower().strip() for c in df.columns]
                
                # Validate Headers (Name, Link) - Description is optional
                if 'name' not in df.columns or 'link' not in df.columns:
                    flash('Import Error: CSV must have "Name" and "Link" columns.', 'danger')
                    return redirect(url_for('main.toolbase'))
                
                # Iterate and Add
                count = 0
                for _, row in df.iterrows():
                    # Basic Validation
                    t_title = str(row['name']).strip()
                    t_link = str(row['link']).strip()
                    t_desc = str(row.get('description', '')).strip()
                    
                    if t_title and t_link:
                         # Optional: Check for duplicates or just add?
                         # For now, we just add.
                         new_tool = Tool(
                             title=t_title,
                             link=t_link,
                             description=t_desc
                         )
                         db.session.add(new_tool)
                         count += 1
                
                db.session.commit()
                flash(f'Success! Imported {count} tools from file.', 'success')
                return redirect(url_for('main.toolbase'))

            except Exception as e:
                db.session.rollback()
                flash(f'Import Failed: {str(e)}', 'danger')
            
    tools = Tool.query.order_by(desc(Tool.created_at)).all()
    # Pass both forms to template
    return render_template('toolbase.html', form=form, import_form=import_form, tools=tools, is_admin=is_admin)

@main.route('/toolbase/delete/<int:tool_id>', methods=['POST'])
@login_required
def delete_tool(tool_id):
    if not current_user.is_admin:
        abort(403)
    
    tool = Tool.query.get_or_404(tool_id)
    try:
        db.session.delete(tool)
        db.session.commit()
        flash('Tool deleted.', 'success')
    except:
        db.session.rollback()
        flash('Error deleting tool.', 'danger')
        
    return redirect(url_for('main.toolbase'))


@main.route('/toolbase/delete_all', methods=['POST'])
@login_required
def delete_all_tools():
    """
    DELETE ALL TOOLS
    """
    if not current_user.is_admin:
        abort(403)
    
    try:
        # Delete all records in the Tool table
        num_deleted = db.session.query(Tool).delete()
        db.session.commit()
        flash(f'All tools deleted! ({num_deleted} removed)', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting all tools: {str(e)}', 'danger')
        
    return redirect(url_for('main.toolbase'))