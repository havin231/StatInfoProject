from flask import Blueprint, render_template, url_for, flash, redirect, abort, request
from flask_babel import gettext as _
from flask_login import login_required, current_user

from app import db, bcrypt
from app.models import User, Subject, Page, Question, Resource, ExamResult, SubjectTeacher, AdminNotification, PageComment
from app.forms import SubjectForm, TeacherSignupForm, TeacherEditForm
from app.routes.helpers import can_edit_subject

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
        # v0.5.0 - Admin Notification Cleanup (Delete > 3 days old)
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=3)
        try:
            AdminNotification.query.filter(AdminNotification.created_at < cutoff_date).delete()
            db.session.commit()
        except Exception:
            db.session.rollback()

        # Fetch Notifications
        notifications = AdminNotification.query.order_by(AdminNotification.created_at.desc()).all()

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
            teacher_form=new_teacher_form,
            notifications=notifications
        )

    # 2. Standard Teacher Context (v0.5.0 - Multi-Teacher Support)
    else:
        # Fetch subjects assigned to this teacher via SubjectTeacher association
        assignments = SubjectTeacher.query.filter_by(teacher_id=current_user.id).all()
        assigned_subjects = [a.subject for a in assignments if a.subject]
        assignment_map = {a.subject_id: a for a in assignments}

        return render_template(
            'teacher/dashboard.html',
            subjects=assigned_subjects,
            assignment_map=assignment_map
        )


@teacher.route('/teacher/toggle_name_visibility', methods=['POST'])
@login_required
def toggle_name_visibility():
    """
    TEACHER NAME VISIBILITY TOGGLE (GLOBAL)

    Allows teachers to toggle whether their name appears publicly
    across all their assigned subject pages.
    """
    current_user.show_name_on_subject = not current_user.show_name_on_subject

    try:
        SubjectTeacher.query.filter_by(teacher_id=current_user.id).update(
            {'show_name': current_user.show_name_on_subject}
        )
        db.session.commit()
        status = _('shown') if current_user.show_name_on_subject else _('hidden')
        flash(_('Your name will be %(status)s on all your subject pages.', status=status), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error updating setting: %(error)s', error=str(e)), 'danger')

    return redirect(url_for('teacher.teacher_dashboard'))


@teacher.route('/subject/<int:subject_id>/toggle_my_name', methods=['POST'])
@login_required
def toggle_subject_name_visibility(subject_id):
    """
    PER-SUBJECT INDIVIDUAL TEACHER NAME VISIBILITY TOGGLE

    Allows each teacher assigned to a subject to independently show or hide
    their own name on that specific subject's public page.
    """
    assignment = SubjectTeacher.query.filter_by(
        subject_id=subject_id,
        teacher_id=current_user.id
    ).first()

    if not assignment:
        abort(403)

    assignment.show_name = not assignment.show_name

    try:
        db.session.commit()
        status = _('shown') if assignment.show_name else _('hidden')
        flash(_('Your name is now %(status)s on "%(subject)s".', status=status, subject=assignment.subject.name), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error updating setting: %(error)s', error=str(e)), 'danger')

    return redirect(request.referrer or url_for('teacher.teacher_dashboard'))


@teacher.route('/subject/<int:subject_id>/toggle_visibility', methods=['POST'])
@login_required
def toggle_visibility(subject_id):
    """
    TOGGLE SUBJECT VISIBILITY

    Allows Teachers and Admins to show/hide a subject on the public homepage.
    Uses a traditional form POST + redirect for maximum reliability.
    """
    subject = Subject.query.get_or_404(subject_id)

    # Permission Check: Must be Admin OR Assigned Teacher (v0.5.0 - Multi-Teacher)
    if not can_edit_subject(subject):
        abort(403)

    try:
        subject.is_public = not subject.is_public
        db.session.commit()
        status = _("visible") if subject.is_public else _("hidden")
        flash(_('Subject "%(name)s" is now %(status)s on the public homepage.', name=subject.name, status=status), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error updating visibility: %(error)s', error=str(e)), 'danger')

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
            flash(_('Error: The email address "%(email)s" is already in use.', email=form.email.data), 'danger')
            return redirect(url_for('teacher.teacher_dashboard'))

        # B. Uniqueness Check (Username)
        existing_name = User.query.filter_by(username=form.username.data).first()
        if existing_name:
            flash(_('Error: The name "%(username)s" is already taken.', username=form.username.data), 'danger')
            return redirect(url_for('teacher.teacher_dashboard'))

        # C. Security: Hash Password
        password_hash_str = bcrypt.generate_password_hash(form.password.data).decode('utf-8')

        # D. Object Instantiation
        is_admin_user = form.is_admin.data
        new_staff_member = User(
            username=form.username.data,
            username_kurdish=form.username_kurdish.data,
            email=form.email.data,
            password_hash=password_hash_str,
            is_admin=is_admin_user
        )

        # E. Database Persistence
        try:
            db.session.add(new_staff_member)
            db.session.commit()

            role_label = _("Administrator") if is_admin_user else _("Teacher")
            flash(_('Success: %(role)s account created for %(username)s.', role=role_label, username=form.username.data), 'success')
        except Exception as db_err:
            db.session.rollback()
            flash(_('Database Error during staff creation: %(error)s', error=str(db_err)), 'danger')

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
                flash(_('Error: The new username is already taken.'), 'danger')
                return redirect(url_for('teacher.edit_teacher', teacher_id=target_staff.id))

        if target_staff.email != form.email.data:
            if User.query.filter_by(email=form.email.data).first():
                flash(_('Error: The new email is already in use.'), 'danger')
                return redirect(url_for('teacher.edit_teacher', teacher_id=target_staff.id))

        # Update Visible Info
        target_staff.username = form.username.data
        target_staff.username_kurdish = form.username_kurdish.data
        target_staff.email = form.email.data
        target_staff.show_name_on_subject = form.show_name_on_subject.data

        # Security Logic: Prevent Admins from accidentally downgrading themselves
        if target_staff.id == current_user.id:
            target_staff.is_admin = True
        else:
            target_staff.is_admin = form.is_admin.data

        # Optional Password Reset
        if form.password.data:
            new_pw_hash = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
            target_staff.password_hash = new_pw_hash
            flash(_('Password has been reset.'), 'success')

        db.session.commit()
        flash(_('Staff profile updated.'), 'success')
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
        flash(_('Security Violation: You cannot delete your own account.'), 'danger')
        return redirect(url_for('teacher.teacher_dashboard'))

    try:
        # 2. Remove co-teacher assignments for this teacher
        SubjectTeacher.query.filter_by(teacher_id=target_staff.id).delete()

        # 3. Iterate through owned Subjects
        subjects_to_clear = Subject.query.filter_by(teacher_id=target_staff.id).all()

        for subj in subjects_to_clear:
            # A. Clean up Admin Notifications referencing this subject
            AdminNotification.query.filter_by(related_subject_id=subj.id).delete()

            # B. Clean up Exam Results
            ExamResult.query.filter_by(subject_id=subj.id).delete()

            # C. Clean up Questions (before Pages due to page_id FK)
            Question.query.filter_by(subject_id=subj.id).delete()

            # D. Clean up Comments, Resources & Pages
            pages_found = Page.query.filter_by(subject_id=subj.id).all()
            for p in pages_found:
                PageComment.query.filter_by(page_id=p.id).delete()
                Resource.query.filter_by(page_id=p.id).delete()
                db.session.delete(p)

            # E. Clean up remaining SubjectTeacher links
            SubjectTeacher.query.filter_by(subject_id=subj.id).delete()

            # F. Delete the Subject itself
            db.session.delete(subj)

        # 4. Final Step: Remove the Staff Member
        db.session.delete(target_staff)
        db.session.commit()
        flash(_('Account for %(username)s and all associated course data have been purged.', username=target_staff.username), 'success')

    except Exception as cleanup_err:
        db.session.rollback()
        flash(_('Integrity Error during deletion: %(error)s', error=str(cleanup_err)), 'danger')

    return redirect(url_for('teacher.teacher_dashboard'))


@teacher.route('/admin/subject/<int:subject_id>/teachers', methods=['POST'])
@login_required
def manage_subject_teachers(subject_id):
    """
    MULTI-TEACHER SUBJECT ASSIGNMENT (ADMIN ONLY)

    Assigns one or more teachers to a subject. Removes any teacher who is no
    longer selected so former teachers never appear on the subject page, and
    preserves each continuing teacher's individual show_name setting.
    """
    if not current_user.is_admin:
        abort(403)

    subject = Subject.query.get_or_404(subject_id)
    raw_ids = request.form.getlist('teacher_ids')
    selected_ids = []
    for raw in raw_ids:
        try:
            tid = int(raw)
            if tid not in selected_ids:
                selected_ids.append(tid)
        except ValueError:
            continue

    if not selected_ids:
        flash(_('Error: At least one teacher must be assigned to a subject.'), 'danger')
        return redirect(url_for('teacher.teacher_dashboard'))

    valid_teachers = User.query.filter(User.id.in_(selected_ids)).all()
    valid_map = {t.id: t for t in valid_teachers}
    valid_ids = [tid for tid in selected_ids if tid in valid_map]

    if not valid_ids:
        flash(_('Error: No valid teachers selected.'), 'danger')
        return redirect(url_for('teacher.teacher_dashboard'))

    try:
        # Remove any teachers no longer assigned to this subject
        existing_assignments = SubjectTeacher.query.filter_by(subject_id=subject.id).all()
        existing_by_tid = {a.teacher_id: a for a in existing_assignments}

        for tid, assignment in existing_by_tid.items():
            if tid not in valid_map:
                db.session.delete(assignment)

        # Ensure primary teacher_id is in the new set
        if subject.teacher_id not in valid_map:
            subject.teacher_id = valid_ids[0]

        # Add newly assigned teachers and sync is_primary
        for tid in valid_ids:
            is_prim = (tid == subject.teacher_id)
            if tid in existing_by_tid:
                existing_by_tid[tid].is_primary = is_prim
            else:
                teacher_obj = valid_map[tid]
                db.session.add(SubjectTeacher(
                    subject_id=subject.id,
                    teacher_id=tid,
                    is_primary=is_prim,
                    show_name=bool(teacher_obj.show_name_on_subject)
                ))

        db.session.commit()
        flash(_('Assigned teachers for "%(subject)s" updated successfully.', subject=subject.name), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error updating subject teachers: %(error)s', error=str(e)), 'danger')

    return redirect(url_for('teacher.teacher_dashboard'))


@teacher.route('/admin/transfer/subject/<int:subject_id>', methods=['POST'])
@login_required
def transfer_subject(subject_id):
    """
    TRANSFER SUBJECT TO ANOTHER TEACHER

    Replaces the previous primary teacher with the new teacher and removes
    the old teacher's SubjectTeacher assignment so former teachers no longer
    appear on the subject page.
    """
    if not current_user.is_admin:
        abort(403)

    subject = Subject.query.get_or_404(subject_id)
    new_teacher_id = request.form.get('new_teacher_id', type=int)

    if not new_teacher_id:
        flash(_('Error: Please select a new teacher.'), 'danger')
        return redirect(url_for('teacher.teacher_dashboard'))

    new_teacher = User.query.get(new_teacher_id)
    if not new_teacher:
        flash(_('Error: Selected teacher not found.'), 'danger')
        return redirect(url_for('teacher.teacher_dashboard'))

    old_teacher_id = subject.teacher_id
    old_teacher_name = subject.teacher.username
    subject.teacher_id = new_teacher_id

    # Remove old primary teacher's assignment so former teachers don't linger
    if old_teacher_id != new_teacher_id:
        SubjectTeacher.query.filter_by(subject_id=subject.id, teacher_id=old_teacher_id).delete()

    SubjectTeacher.query.filter_by(subject_id=subject.id, is_primary=True).update({'is_primary': False})
    existing_assignment = SubjectTeacher.query.filter_by(subject_id=subject.id, teacher_id=new_teacher_id).first()
    if existing_assignment:
        existing_assignment.is_primary = True
    else:
        db.session.add(SubjectTeacher(
            subject_id=subject.id,
            teacher_id=new_teacher_id,
            is_primary=True,
            show_name=bool(new_teacher.show_name_on_subject)
        ))

    try:
        db.session.commit()
        flash(_('Subject "%(subject)s" transferred from %(old)s to %(new)s.', 
               subject=subject.name, old=old_teacher_name, new=new_teacher.username), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error transferring subject: %(error)s', error=str(e)), 'danger')

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
    assignments = SubjectTeacher.query.filter_by(teacher_id=teacher_record.id).all()
    teacher_subjects = [a.subject for a in assignments if a.subject]
    assignment_map = {a.subject_id: a for a in assignments}

    # Aggregated stats for the view
    subject_ids = [s.id for s in teacher_subjects]
    results_count = ExamResult.query.filter(ExamResult.subject_id.in_(subject_ids)).count() if subject_ids else 0

    return render_template(
        'teacher/dashboard.html',
        subjects=teacher_subjects,
        assignment_map=assignment_map,
        total_results=results_count,
        view_as_admin=True,
        teacher_name=teacher_record.username
    )
