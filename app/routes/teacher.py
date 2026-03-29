from flask import Blueprint, render_template, url_for, flash, redirect, abort
from flask_login import login_required, current_user

from app import db, bcrypt
from app.models import User, Subject, Page, Question, ExamResult, StudentAnswer
from app.forms import SubjectForm, TeacherSignupForm, TeacherEditForm

teacher = Blueprint('teacher', __name__)

# ==============================================================================
# SECTION 5: STAFF DASHBOARD & TEACHER ADMINISTRATION
# ==============================================================================

@teacher.route('/teacher/dashboard')
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


@teacher.route('/subject/<int:subject_id>/toggle_visibility', methods=['POST'])
@login_required
def toggle_visibility(subject_id):
    """
    TOGGLE SUBJECT VISIBILITY

    Allows Teachers and Admins to show/hide a subject on the public homepage.
    Uses a traditional form POST + redirect for maximum reliability.
    """
    subject = Subject.query.get_or_404(subject_id)

    # Permission Check: Must be Admin OR Owner
    if not current_user.is_admin and subject.teacher_id != current_user.id:
        abort(403)

    try:
        subject.is_public = not subject.is_public
        db.session.commit()
        status = "visible" if subject.is_public else "hidden"
        flash(f'Subject "{subject.name}" is now {status} on the public homepage.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating visibility: {str(e)}', 'danger')

    return redirect(url_for('teacher.teacher_dashboard'))


@teacher.route('/admin/add_teacher', methods=['POST'])
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
            return redirect(url_for('teacher.teacher_dashboard'))

        # B. Uniqueness Check (Username)
        existing_name = User.query.filter_by(username=form.username.data).first()
        if existing_name:
            flash(f'Error: The name "{form.username.data}" is already taken.', 'danger')
            return redirect(url_for('teacher.teacher_dashboard'))

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

    return redirect(url_for('teacher.teacher_dashboard'))


@teacher.route('/admin/edit/teacher/<int:teacher_id>', methods=['GET', 'POST'])
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
                return redirect(url_for('teacher.edit_teacher', teacher_id=target_staff.id))

        if target_staff.email != form.email.data:
            if User.query.filter_by(email=form.email.data).first():
                flash('Error: The new email is already in use.', 'danger')
                return redirect(url_for('teacher.edit_teacher', teacher_id=target_staff.id))

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
        return redirect(url_for('teacher.teacher_dashboard'))

    return render_template('admin/edit_teacher.html', form=form, teacher=target_staff)


@teacher.route('/admin/delete/teacher/<int:teacher_id>')
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
        return redirect(url_for('teacher.teacher_dashboard'))

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

    return redirect(url_for('teacher.teacher_dashboard'))


@teacher.route('/admin/view_teacher/<int:teacher_id>')
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
