from flask import Blueprint, render_template, url_for, flash, redirect, abort, request
from flask_babel import gettext as _
from flask_login import login_required, current_user
from sqlalchemy import or_

from app import db, bcrypt
from app.models import (
    User, Subject, Page, Question, Resource, ExamResult,
    SubjectTeacher, AdminNotification, PageComment, TeacherNotification,
    Student, StudentTeacher, TeacherRequest,
    PrivateExam, PrivateQuestion, PrivateExamQuestion
)
from app.forms import (
    SubjectForm, TeacherSignupForm, TeacherEditForm,
    TeacherProfileForm, AdminMessageForm, TeacherToAdminMessageForm,
    StudentManageForm
)
from app.routes.helpers import can_edit_subject, generate_student_code

teacher = Blueprint('teacher', __name__)


def _build_teacher_dashboard_context(target_user, view_as_admin=False):
    """Build identical Teacher Dashboard context for both the teacher and Admin inspector."""
    assignments = SubjectTeacher.query.filter_by(teacher_id=target_user.id).all()
    assigned_subjects = [a.subject for a in assignments if a.subject]
    assignment_map = {a.subject_id: a for a in assignments}

    # Dashboard small notification box shows ONLY unread notifications
    teacher_notifications = TeacherNotification.query.filter_by(
        teacher_id=target_user.id,
        is_read=False
    ).order_by(
        TeacherNotification.created_at.desc()
    ).all()
    total_notifications_count = TeacherNotification.query.filter_by(teacher_id=target_user.id).count()

    profile_form = TeacherProfileForm(obj=target_user)
    admin_msg_form = TeacherToAdminMessageForm()
    my_students_count = StudentTeacher.query.filter_by(teacher_id=target_user.id).count()

    return dict(
        subjects=assigned_subjects,
        assignment_map=assignment_map,
        teacher_notifications=teacher_notifications,
        total_notifications_count=total_notifications_count,
        profile_form=profile_form,
        admin_msg_form=admin_msg_form,
        my_students_count=my_students_count,
        inspected_teacher=target_user,
        teacher_name=target_user.username,
        view_as_admin=view_as_admin
    )

# ==============================================================================
# SECTION 5: STAFF DASHBOARD & TEACHER ADMINISTRATION
# ==============================================================================

@teacher.route('/teacher/dashboard')
@login_required
def teacher_dashboard():
    """
    CENTRAL STAFF CONTROL PANEL

    Logic:
    - Admin Mode: Pulls unread notifications for the sidebar box + all subjects & staff.
    - Teacher Mode: Uses _build_teacher_dashboard_context (only unread in small box).
    """
    # 1. Administrator Context
    if current_user.is_admin:
        # Admin sidebar box displays ONLY unread (is_checked=False) notifications
        notifications = AdminNotification.query.filter_by(
            is_checked=False
        ).order_by(
            AdminNotification.created_at.desc()
        ).all()
        total_notifications_count = AdminNotification.query.count()
        unread_comments_count = PageComment.query.filter_by(
            is_read_by_admin=False,
            is_teacher_reply=False
        ).count()
        pending_requests_count = TeacherRequest.query.filter_by(status='pending').count()

        # Fetch the complete subject roster
        all_global_subjects = Subject.query.all()
        # Fetch the complete staff roster
        all_staff_members = User.query.all()

        # Initialize the Subject Creation Form for the sidebar
        subject_creation_form = SubjectForm()
        subject_creation_form.teacher_id.choices = [
            (staff.id, staff.username) for staff in all_staff_members
        ]

        # Initialize the Staff Signup Form for the sidebar
        new_teacher_form = TeacherSignupForm()

        # Initialize Admin -> Teacher Message Form
        admin_message_form = AdminMessageForm()
        non_admin_teachers = [s for s in all_staff_members if s.id != current_user.id]
        admin_message_form.recipient_id.choices = [
            (0, _('All Teachers'))
        ] + [(s.id, s.username) for s in non_admin_teachers]

        # Initialize Self-Profile Form for the logged-in admin
        profile_form = TeacherProfileForm(obj=current_user)

        return render_template(
            'admin_dashboard.html',
            subjects=all_global_subjects,
            teachers=all_staff_members,
            subject_form=subject_creation_form,
            teacher_form=new_teacher_form,
            admin_message_form=admin_message_form,
            profile_form=profile_form,
            notifications=notifications,
            total_notifications_count=total_notifications_count,
            unread_comments_count=unread_comments_count,
            pending_requests_count=pending_requests_count
        )

    # 2. Standard Teacher Context
    ctx = _build_teacher_dashboard_context(current_user, view_as_admin=False)
    return render_template('teacher/dashboard.html', **ctx)


@teacher.route('/teacher/profile/update', methods=['POST'])
@login_required
def update_own_profile():
    """
    SELF-SERVICE PROFILE & PRIVACY UPDATE (TEACHERS & ADMINS)
    """
    form = TeacherProfileForm()
    target_uid = request.form.get('target_user_id', type=int)
    if target_uid and target_uid != current_user.id:
        if not current_user.is_admin:
            abort(403)
        target_user = User.query.get_or_404(target_uid)
        redirect_url = url_for('teacher.view_teacher', teacher_id=target_user.id)
    else:
        target_user = current_user
        redirect_url = url_for('teacher.teacher_dashboard')

    if form.validate_on_submit():
        new_username = form.username.data.strip()

        # Check username uniqueness if modified
        if new_username != target_user.username:
            if User.query.filter_by(username=new_username).first():
                flash(_('Error: The name "%(username)s" is already taken.', username=new_username), 'danger')
                return redirect(redirect_url)

        target_user.username = new_username
        target_user.username_kurdish = form.username_kurdish.data.strip() if form.username_kurdish.data else None
        target_user.gender = form.gender.data or None
        target_user.birth_date = form.birth_date.data
        target_user.bio = form.bio.data.strip() if form.bio.data else None

        # Profile Privacy Flags
        target_user.profile_public = bool(form.profile_public.data)
        target_user.profile_show_name = bool(form.profile_show_name.data)
        target_user.profile_show_bio = bool(form.profile_show_bio.data)
        target_user.profile_show_age = bool(form.profile_show_age.data)
        target_user.profile_show_gender = bool(form.profile_show_gender.data)

        if form.new_password.data:
            target_user.password_hash = bcrypt.generate_password_hash(form.new_password.data).decode('utf-8')

        try:
            db.session.commit()
            flash(_('Your profile has been updated successfully.'), 'success')
        except Exception as e:
            db.session.rollback()
            flash(_('Error updating profile: %(error)s', error=str(e)), 'danger')
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                flash(str(err), 'danger')

    return redirect(redirect_url)


@teacher.route('/admin/message_teacher', methods=['POST'])
@login_required
def send_teacher_message():
    """
    ADMIN DIRECT MESSAGE TO TEACHERS

    Creates a visually distinct 'admin_message' TeacherNotification for
    either a specific teacher or all non-admin teachers.
    """
    if not current_user.is_admin:
        abort(403)

    all_staff = User.query.all()
    other_staff = [s for s in all_staff if s.id != current_user.id]

    form = AdminMessageForm()
    form.recipient_id.choices = [(0, _('All Teachers'))] + [(s.id, s.username) for s in other_staff]

    if form.validate_on_submit():
        recipient_id = form.recipient_id.data
        msg_title = form.title.data.strip()
        msg_body = form.message.data.strip()

        if recipient_id == 0:
            recipients = [s for s in other_staff if not s.is_admin]
            if not recipients:
                flash(_('No teachers available to message.'), 'warning')
                return redirect(url_for('teacher.teacher_dashboard'))
        else:
            target = User.query.get(recipient_id)
            if not target:
                flash(_('Error: Selected teacher not found.'), 'danger')
                return redirect(url_for('teacher.teacher_dashboard'))
            recipients = [target]

        try:
            for rec in recipients:
                db.session.add(TeacherNotification(
                    teacher_id=rec.id,
                    sender_id=current_user.id,
                    notification_type='admin_message',
                    title=msg_title,
                    message=msg_body
                ))
            db.session.commit()
            if recipient_id == 0:
                flash(_('Announcement sent to %(count)s teacher(s).', count=len(recipients)), 'success')
            else:
                flash(_('Message sent to %(username)s.', username=recipients[0].username), 'success')
        except Exception as e:
            db.session.rollback()
            flash(_('Error sending message: %(error)s', error=str(e)), 'danger')
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                flash(str(err), 'danger')

    return redirect(url_for('teacher.teacher_dashboard'))


@teacher.route('/teacher/notification/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_teacher_notification_read(notif_id):
    """Marks a teacher notification as read (vanishes from dashboard box; kept in full history)."""
    notif = TeacherNotification.query.get_or_404(notif_id)
    if notif.teacher_id != current_user.id and not current_user.is_admin:
        abort(403)
    try:
        notif.is_read = True
        db.session.commit()
    except Exception:
        db.session.rollback()
    return redirect(request.referrer or url_for('teacher.teacher_dashboard'))


@teacher.route('/teacher/notification/<int:notif_id>/delete', methods=['POST'])
@login_required
def delete_teacher_notification(notif_id):
    """Deletes a teacher notification from their inbox."""
    notif = TeacherNotification.query.get_or_404(notif_id)
    if notif.teacher_id != current_user.id and not current_user.is_admin:
        abort(403)
    try:
        db.session.delete(notif)
        db.session.commit()
        flash(_('Notification dismissed.'), 'info')
    except Exception as e:
        db.session.rollback()
        flash(_('Error dismissing notification: %(error)s', error=str(e)), 'danger')
    return redirect(request.referrer or url_for('teacher.teacher_dashboard'))


@teacher.route('/admin/notification/<int:notif_id>/delete', methods=['POST'])
@login_required
def delete_admin_notification(notif_id):
    """Allows an Admin to dismiss a notification from the Admin panel."""
    if not current_user.is_admin:
        abort(403)
    notif = AdminNotification.query.get_or_404(notif_id)
    try:
        db.session.delete(notif)
        db.session.commit()
        flash(_('Notification dismissed.'), 'info')
    except Exception as e:
        db.session.rollback()
        flash(_('Error dismissing notification: %(error)s', error=str(e)), 'danger')
    return redirect(request.referrer or url_for('teacher.teacher_dashboard'))


@teacher.route('/teacher/toggle_name_visibility', methods=['POST'])
@login_required
def toggle_name_visibility():
    """
    TEACHER NAME VISIBILITY TOGGLE (GLOBAL)
    """
    target_uid = request.form.get('target_user_id', type=int)
    if target_uid and target_uid != current_user.id:
        if not current_user.is_admin:
            abort(403)
        target_user = User.query.get_or_404(target_uid)
    else:
        target_user = current_user

    target_user.show_name_on_subject = not target_user.show_name_on_subject

    try:
        SubjectTeacher.query.filter_by(teacher_id=target_user.id).update(
            {'show_name': target_user.show_name_on_subject}
        )
        db.session.commit()
        status = _('shown') if target_user.show_name_on_subject else _('hidden')
        flash(_('Your name will be %(status)s on all your subject pages.', status=status), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error updating setting: %(error)s', error=str(e)), 'danger')

    return redirect(request.referrer or url_for('teacher.teacher_dashboard'))


@teacher.route('/subject/<int:subject_id>/toggle_my_name', methods=['POST'])
@login_required
def toggle_subject_name_visibility(subject_id):
    """
    PER-SUBJECT INDIVIDUAL TEACHER NAME VISIBILITY TOGGLE
    """
    target_uid = request.form.get('teacher_id', type=int)
    if target_uid and target_uid != current_user.id:
        if not current_user.is_admin:
            abort(403)
    else:
        target_uid = current_user.id

    assignment = SubjectTeacher.query.filter_by(
        subject_id=subject_id,
        teacher_id=target_uid
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
            gender=form.gender.data or None,
            birth_date=form.birth_date.data,
            bio=form.bio.data.strip() if form.bio.data else None,
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
        target_staff.gender = form.gender.data or None
        target_staff.birth_date = form.birth_date.data
        target_staff.bio = form.bio.data.strip() if form.bio.data else None
        target_staff.show_name_on_subject = form.show_name_on_subject.data
        target_staff.profile_public = bool(form.profile_public.data)
        target_staff.profile_show_name = bool(form.profile_show_name.data)
        target_staff.profile_show_bio = bool(form.profile_show_bio.data)
        target_staff.profile_show_age = bool(form.profile_show_age.data)
        target_staff.profile_show_gender = bool(form.profile_show_gender.data)

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
    We delete in this order: Notifications -> Results -> Questions -> Pages -> Subjects -> User.
    """
    if not current_user.is_admin:
        abort(403)

    target_staff = User.query.get_or_404(teacher_id)

    # 1. Logic Check: Cannot delete self
    if target_staff.id == current_user.id:
        flash(_('Security Violation: You cannot delete your own account.'), 'danger')
        return redirect(url_for('teacher.teacher_dashboard'))

    try:
        # 2. Clean up notifications, student ownership/sharing, review links, private exam creators, and comment authorship
        TeacherNotification.query.filter(
            (TeacherNotification.teacher_id == target_staff.id) |
            (TeacherNotification.sender_id == target_staff.id)
        ).delete(synchronize_session=False)
        StudentTeacher.query.filter_by(teacher_id=target_staff.id).delete()
        Student.query.filter_by(created_by_id=target_staff.id).update({'created_by_id': None})
        PrivateExam.query.filter_by(created_by_id=target_staff.id).update({'created_by_id': None})
        TeacherRequest.query.filter_by(reviewed_by_id=target_staff.id).update({'reviewed_by_id': None})
        PageComment.query.filter_by(author_user_id=target_staff.id).update({'author_user_id': None})
        SubjectTeacher.query.filter_by(teacher_id=target_staff.id).delete()

        # 3. Iterate through owned Subjects
        subjects_to_clear = Subject.query.filter_by(teacher_id=target_staff.id).all()

        for subj in subjects_to_clear:
            # A. Clean up Notifications referencing this subject
            TeacherNotification.query.filter_by(related_subject_id=subj.id).delete()
            AdminNotification.query.filter_by(related_subject_id=subj.id).delete()

            # B. Clean up Exam Results
            ExamResult.query.filter_by(subject_id=subj.id).delete()

            # C. Clean up Public & Private Questions (before Pages due to page_id FK)
            Question.query.filter_by(subject_id=subj.id).delete()
            pe_ids = [pe.id for pe in PrivateExam.query.filter_by(subject_id=subj.id).all()]
            pq_ids = [pq.id for pq in PrivateQuestion.query.filter_by(subject_id=subj.id).all()]
            if pe_ids:
                PrivateExamQuestion.query.filter(PrivateExamQuestion.private_exam_id.in_(pe_ids)).delete(synchronize_session=False)
            if pq_ids:
                PrivateExamQuestion.query.filter(PrivateExamQuestion.private_question_id.in_(pq_ids)).delete(synchronize_session=False)
            PrivateQuestion.query.filter_by(subject_id=subj.id).delete()
            PrivateExam.query.filter_by(subject_id=subj.id).delete()

            # D. Clean up Comments (replies first), Resources & Pages
            pages_found = Page.query.filter_by(subject_id=subj.id).all()
            for p in pages_found:
                PageComment.query.filter(PageComment.page_id == p.id, PageComment.parent_id.isnot(None)).delete(synchronize_session=False)
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
    FULL ADMIN INSPECTOR VIEW OF A TEACHER'S DASHBOARD

    Renders the exact same dashboard context seen by `teacher_record` so
    Admins can inspect everything (notifications, profile, stats, students, subjects).
    """
    if not current_user.is_admin:
        abort(403)

    teacher_record = User.query.get_or_404(teacher_id)
    ctx = _build_teacher_dashboard_context(teacher_record, view_as_admin=True)
    return render_template('teacher/dashboard.html', **ctx)


# ==============================================================================
# TEACHER -> ADMIN MESSAGING & TEACHER NOTIFICATIONS PAGE (v0.9.0)
# ==============================================================================

@teacher.route('/teacher/message_admin', methods=['POST'])
@login_required
def send_admin_message():
    """Allows any logged-in Teacher to send a visually distinct message to Admins."""
    form = TeacherToAdminMessageForm()
    if form.validate_on_submit():
        notif = AdminNotification(
            notification_type='teacher_message',
            title=form.title.data.strip(),
            message=form.message.data.strip(),
            actor_type='teacher',
            actor_id=current_user.id,
            actor_name=current_user.username
        )
        try:
            db.session.add(notif)
            db.session.commit()
            flash(_('Your message has been sent to the administrators.'), 'success')
        except Exception as e:
            db.session.rollback()
            flash(_('Error sending message: %(error)s', error=str(e)), 'danger')
    else:
        for errs in form.errors.values():
            for err in errs:
                flash(str(err), 'danger')
    return redirect(url_for('teacher.teacher_dashboard'))


@teacher.route('/teacher/notifications')
@login_required
def teacher_notifications_page():
    """Dedicated full-page notifications view (all read & unread until deleted)."""
    req_tid = request.args.get('teacher_id', type=int)
    if req_tid and current_user.is_admin:
        target_teacher = User.query.get_or_404(req_tid)
    else:
        target_teacher = current_user

    notifs = TeacherNotification.query.filter_by(
        teacher_id=target_teacher.id
    ).order_by(
        TeacherNotification.is_read.asc(),
        TeacherNotification.created_at.desc()
    ).all()
    return render_template(
        'teacher/notifications.html',
        notifications=notifs,
        inspected_teacher=target_teacher if target_teacher.id != current_user.id else None
    )


@teacher.route('/teacher/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_teacher_notifications_read():
    target_uid = request.form.get('teacher_id', type=int)
    if target_uid and target_uid != current_user.id:
        if not current_user.is_admin:
            abort(403)
    else:
        target_uid = current_user.id

    try:
        TeacherNotification.query.filter_by(teacher_id=target_uid, is_read=False).update({'is_read': True})
        db.session.commit()
        flash(_('All notifications marked as read.'), 'success')
    except Exception:
        db.session.rollback()
    return redirect(request.referrer or url_for('teacher.teacher_notifications_page'))


# ==============================================================================
# HIDDEN / STUDENT-CODE-ONLY EXAM & QUIZ TOGGLES (v0.9.0)
# ==============================================================================

@teacher.route('/subject/<int:subject_id>/toggle_exam_restriction', methods=['POST'])
@login_required
def toggle_subject_exam_restriction(subject_id):
    subj = Subject.query.get_or_404(subject_id)
    if not can_edit_subject(subj):
        abort(403)
    try:
        subj.exam_student_only = not bool(subj.exam_student_only)
        db.session.commit()
        msg = _('Final exam is now hidden and restricted to Student Codes.') if subj.exam_student_only else _('Final exam is now public.')
        flash(msg, 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error updating restriction: %(error)s', error=str(e)), 'danger')
    return redirect(request.referrer or url_for('public.subject_detail', slug=subj.slug))


@teacher.route('/page/<int:page_id>/toggle_quiz_restriction', methods=['POST'])
@login_required
def toggle_page_quiz_restriction(page_id):
    page = Page.query.get_or_404(page_id)
    if not can_edit_subject(page.subject):
        abort(403)
    try:
        page.quiz_student_only = not bool(page.quiz_student_only)
        db.session.commit()
        msg = _('Lecture quiz is now hidden and restricted to Student Codes.') if page.quiz_student_only else _('Lecture quiz is now public.')
        flash(msg, 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error updating restriction: %(error)s', error=str(e)), 'danger')
    return redirect(request.referrer or url_for('public.subject_detail', slug=page.subject.slug))


# ==============================================================================
# STUDENT RECORD MANAGEMENT & ADMIN CROSS-TEACHER SHARING (v0.9.0)
# ==============================================================================

@teacher.route('/staff/students', methods=['GET', 'POST'])
@login_required
def manage_students():
    """
    Create and manage code-based Student records.
    - Teachers see only students linked to them in StudentTeacher.
    - Admins see all students and can assign/share any student across teachers.
    """
    form = StudentManageForm()
    all_teachers = User.query.order_by(User.username.asc()).all()

    if form.validate_on_submit():
        code = generate_student_code(8)
        new_student = Student(
            name_en=form.name_en.data.strip(),
            name_ku=form.name_ku.data.strip(),
            birth_date=form.birth_date.data,
            gender=form.gender.data,
            department_en=form.department_en.data.strip(),
            department_ku=form.department_ku.data.strip(),
            student_code=code,
            created_by_id=current_user.id
        )
        try:
            db.session.add(new_student)
            db.session.flush()

            if current_user.is_admin:
                raw_tids = request.form.getlist('teacher_ids')
                tids = []
                for r in raw_tids:
                    try:
                        tid = int(r)
                        if tid not in tids:
                            tids.append(tid)
                    except ValueError:
                        continue
                if not tids:
                    tids = [current_user.id]
                for tid in tids:
                    db.session.add(StudentTeacher(student_id=new_student.id, teacher_id=tid))
            else:
                db.session.add(StudentTeacher(student_id=new_student.id, teacher_id=current_user.id))

            db.session.commit()
            flash(_('Student "%(name)s" created with code %(code)s.', name=new_student.name_en, code=code), 'success')
            return redirect(url_for('teacher.manage_students'))
        except Exception as e:
            db.session.rollback()
            flash(_('Error creating student: %(error)s', error=str(e)), 'danger')

    q_str = (request.args.get('q') or '').strip()
    filter_tid = request.args.get('teacher_id', type=int)
    inspected_teacher = None
    if current_user.is_admin:
        if filter_tid:
            inspected_teacher = User.query.get_or_404(filter_tid)
            query = Student.query.join(StudentTeacher).filter(StudentTeacher.teacher_id == inspected_teacher.id)
        else:
            query = Student.query
    else:
        query = Student.query.join(StudentTeacher).filter(StudentTeacher.teacher_id == current_user.id)

    if q_str:
        query = query.filter(or_(
            Student.name_en.ilike(f'%{q_str}%'),
            Student.name_ku.ilike(f'%{q_str}%'),
            Student.student_code.ilike(f'%{q_str}%'),
            Student.department_en.ilike(f'%{q_str}%'),
            Student.department_ku.ilike(f'%{q_str}%'),
        ))

    students_list = query.order_by(Student.created_at.desc()).all()
    return render_template(
        'teacher/students.html',
        form=form,
        students=students_list,
        all_teachers=all_teachers,
        search_query=q_str,
        inspected_teacher=inspected_teacher
    )


@teacher.route('/staff/students/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    if not current_user.is_admin:
        has_link = StudentTeacher.query.filter_by(student_id=student.id, teacher_id=current_user.id).first()
        if not has_link:
            abort(403)

    form = StudentManageForm(obj=student)
    if form.validate_on_submit():
        student.name_en = form.name_en.data.strip()
        student.name_ku = form.name_ku.data.strip()
        student.birth_date = form.birth_date.data
        student.gender = form.gender.data
        student.department_en = form.department_en.data.strip()
        student.department_ku = form.department_ku.data.strip()
        try:
            db.session.commit()
            flash(_('Student information updated.'), 'success')
            return redirect(url_for('teacher.manage_students'))
        except Exception as e:
            db.session.rollback()
            flash(_('Error updating student: %(error)s', error=str(e)), 'danger')

    return render_template('teacher/edit_student.html', form=form, student=student)


@teacher.route('/staff/students/<int:student_id>/regenerate_code', methods=['POST'])
@login_required
def regenerate_student_code(student_id):
    student = Student.query.get_or_404(student_id)
    if not current_user.is_admin:
        has_link = StudentTeacher.query.filter_by(student_id=student.id, teacher_id=current_user.id).first()
        if not has_link:
            abort(403)

    student.student_code = generate_student_code(8)
    try:
        db.session.commit()
        flash(_('New student code generated: %(code)s', code=student.student_code), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error regenerating code: %(error)s', error=str(e)), 'danger')
    return redirect(url_for('teacher.manage_students'))


@teacher.route('/staff/students/<int:student_id>/delete', methods=['POST'])
@login_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    if not current_user.is_admin:
        has_link = StudentTeacher.query.filter_by(student_id=student.id, teacher_id=current_user.id).first()
        if not has_link:
            abort(403)

    try:
        if current_user.is_admin:
            ExamResult.query.filter_by(student_record_id=student.id).update({'student_record_id': None})
            StudentTeacher.query.filter_by(student_id=student.id).delete()
            db.session.delete(student)
            flash(_('Student deleted permanently.'), 'success')
        else:
            StudentTeacher.query.filter_by(student_id=student.id, teacher_id=current_user.id).delete()
            remaining = StudentTeacher.query.filter_by(student_id=student.id).count()
            if remaining == 0 and student.created_by_id == current_user.id:
                ExamResult.query.filter_by(student_record_id=student.id).update({'student_record_id': None})
                db.session.delete(student)
            flash(_('Student removed from your roster.'), 'success')
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(_('Error deleting student: %(error)s', error=str(e)), 'danger')

    return redirect(url_for('teacher.manage_students'))


@teacher.route('/admin/students/<int:student_id>/teachers', methods=['POST'])
@login_required
def assign_student_teachers(student_id):
    """Admin-only: Assign/share an existing student across one or more teachers."""
    if not current_user.is_admin:
        abort(403)

    student = Student.query.get_or_404(student_id)
    raw_tids = request.form.getlist('teacher_ids')
    selected_tids = set()
    for r in raw_tids:
        try:
            selected_tids.add(int(r))
        except ValueError:
            continue

    if not selected_tids:
        flash(_('Please select at least one teacher.'), 'danger')
        return redirect(url_for('teacher.manage_students'))

    try:
        existing_links = StudentTeacher.query.filter_by(student_id=student.id).all()
        existing_tids = {link.teacher_id for link in existing_links}
        for link in existing_links:
            if link.teacher_id not in selected_tids:
                db.session.delete(link)
        for tid in selected_tids:
            if tid not in existing_tids:
                db.session.add(StudentTeacher(student_id=student.id, teacher_id=tid))
        db.session.commit()
        flash(_('Teacher assignments updated for "%(name)s".', name=student.name_en), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error updating student teachers: %(error)s', error=str(e)), 'danger')

    return redirect(url_for('teacher.manage_students'))


@teacher.route('/admin/students/bulk_share', methods=['POST'])
@login_required
def bulk_share_students():
    """Admin-only: Share all selected students with a target teacher."""
    if not current_user.is_admin:
        abort(403)

    target_tid = request.form.get('target_teacher_id', type=int)
    raw_sids = request.form.getlist('student_ids')
    if not target_tid or not raw_sids:
        flash(_('Select at least one student and a target teacher.'), 'warning')
        return redirect(url_for('teacher.manage_students'))

    target_teacher = User.query.get_or_404(target_tid)
    added = 0
    try:
        for raw_sid in raw_sids:
            try:
                sid = int(raw_sid)
            except ValueError:
                continue
            if not StudentTeacher.query.filter_by(student_id=sid, teacher_id=target_teacher.id).first():
                db.session.add(StudentTeacher(student_id=sid, teacher_id=target_teacher.id))
                added += 1
        db.session.commit()
        flash(_('Shared %(count)s student(s) with %(teacher)s.', count=added, teacher=target_teacher.username), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error sharing students: %(error)s', error=str(e)), 'danger')

    return redirect(url_for('teacher.manage_students'))
