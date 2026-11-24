from datetime import datetime
from flask import Blueprint, render_template, url_for, flash, redirect, abort, request
from flask_babel import gettext as _
from flask_login import login_required, current_user
from sqlalchemy import or_

import pandas as pd

from app import db
from app.models import (
    SystemCommand, AdminNotification, PageComment, Subject, Page,
    TeacherRequest, User
)
from app.forms import BulkImportForm, CommandForm, CommentReplyForm

admin = Blueprint('admin', __name__)


# ==============================================================================
# SECTION 7: SYSTEM COMMAND CENTER & DOCUMENTATION
# ==============================================================================

@admin.route('/admin/system/commands')
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


@admin.route('/admin/system/commands/add', methods=['POST'])
@login_required
def add_command():
    """Logic to add a new command to the documentation."""
    if not current_user.is_admin:
        abort(403)

    form = CommandForm()
    if form.validate_on_submit():
        new_cmd = SystemCommand(
            title=form.title.data,
            title_kurdish=form.title_kurdish.data,
            command_text=form.command_text.data,
            description=form.description.data,
            description_kurdish=form.description_kurdish.data
        )

        try:
            db.session.add(new_cmd)
            db.session.commit()
            flash(_('Maintenance script documented successfully.'), 'success')
        except Exception as e:
            db.session.rollback()
            flash(_('Error: %(error)s', error=str(e)), 'danger')

    return redirect(url_for('admin.admin_command_center'))


@admin.route('/admin/system/commands/delete/<int:cmd_id>')
@login_required
def delete_command(cmd_id):
    """Logic to remove a command from documentation."""
    if not current_user.is_admin:
        abort(403)

    target_cmd = SystemCommand.query.get_or_404(cmd_id)

    try:
        db.session.delete(target_cmd)
        db.session.commit()
        flash(_('Documentation entry removed.'), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error: %(error)s', error=str(e)), 'danger')

    return redirect(url_for('admin.admin_command_center'))


@admin.route('/admin/system/commands/import', methods=['POST'])
@login_required
def import_commands_step1():
    """
    BULK SYSTEM COMMAND IMPORT (STEP 1: PARSING)

    Logic:
    - Reads Excel or CSV into a Pandas DataFrame.
    - Validates presence of 'Title' and 'Command' columns.
    - Generates preview data for admin confirmation.
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
            required_fields = ['title', 'command']
            missing_fields = [f for f in required_fields if f not in data_frame.columns]

            if missing_fields:
                flash(_('Import Error: Missing required columns: %(fields)s', fields=", ".join(missing_fields)), 'danger')
                return redirect(url_for('admin.admin_command_center'))

            # Construct the preview list (safe against NaN)
            def _clean(val):
                return '' if pd.isna(val) else str(val).strip()

            command_preview_list = []
            for index, row in data_frame.iterrows():
                command_preview_list.append({
                    'title': _clean(row['title']),
                    'title_kurdish': _clean(row.get('title_kurdish', '')) if 'title_kurdish' in data_frame.columns else '',
                    'command_text': _clean(row['command']),
                    'description': _clean(row.get('description', '')) if 'description' in data_frame.columns else '',
                    'description_kurdish': _clean(row.get('description_kurdish', '')) if 'description_kurdish' in data_frame.columns else ''
                })

            # Render the intermediate preview page
            return render_template(
                'admin/import_preview.html',
                data=command_preview_list,
                import_type='command',
                title="Verify System Commands Batch"
            )

        except Exception as e:
            flash(_('An error occurred while reading the file: %(error)s', error=str(e)), 'danger')
            return redirect(url_for('admin.admin_command_center'))

    flash(_('File upload failed. Please ensure you selected a valid CSV or Excel file.'), 'danger')
    return redirect(url_for('admin.admin_command_center'))


# ==============================================================================
# ADMIN COMMENTS HUB, PERMANENT NOTIFICATIONS PAGE, & TEACHER REQUESTS (v0.9.0)
# ==============================================================================

@admin.route('/admin/comments')
@login_required
def admin_comments():
    """Dedicated Admin hub for browsing, replying to, and moderating all lecture comments."""
    if not current_user.is_admin:
        abort(403)

    subject_id = request.args.get('subject_id', type=int)
    status = (request.args.get('status') or 'all').strip().lower()
    q_str = (request.args.get('q') or '').strip()

    query = PageComment.query.filter_by(is_teacher_reply=False)
    if subject_id:
        query = query.join(Page).filter(Page.subject_id == subject_id)
    if status == 'unread':
        query = query.filter(PageComment.is_read_by_admin == False)
    if q_str:
        query = query.filter(or_(
            PageComment.author_name.ilike(f'%{q_str}%'),
            PageComment.comment_text.ilike(f'%{q_str}%'),
            PageComment.personality_info.ilike(f'%{q_str}%')
        ))

    comments = query.order_by(PageComment.is_read_by_admin.asc(), PageComment.created_at.desc()).all()
    all_subjects = Subject.query.order_by(Subject.name.asc()).all()
    unread_count = PageComment.query.filter_by(is_teacher_reply=False, is_read_by_admin=False).count()

    return render_template(
        'admin/comments.html',
        comments=comments,
        subjects=all_subjects,
        selected_subject_id=subject_id,
        selected_status=status,
        search_query=q_str,
        unread_count=unread_count,
        reply_form=CommentReplyForm()
    )


@admin.route('/admin/comments/<int:comment_id>/read', methods=['POST'])
@login_required
def mark_comment_read(comment_id):
    if not current_user.is_admin:
        abort(403)
    comment = PageComment.query.get_or_404(comment_id)
    try:
        comment.is_read_by_admin = True
        db.session.commit()
    except Exception:
        db.session.rollback()
    return redirect(request.referrer or url_for('admin.admin_comments'))


@admin.route('/admin/comments/mark_all_read', methods=['POST'])
@login_required
def mark_all_comments_read():
    if not current_user.is_admin:
        abort(403)
    try:
        PageComment.query.filter_by(is_read_by_admin=False).update({'is_read_by_admin': True})
        db.session.commit()
        flash(_('All comments marked as read.'), 'success')
    except Exception:
        db.session.rollback()
    return redirect(request.referrer or url_for('admin.admin_comments'))


@admin.route('/admin/notifications')
@login_required
def admin_notifications_page():
    """Dedicated permanent Admin Notifications page (persists until Admin deletes)."""
    if not current_user.is_admin:
        abort(403)

    notif_type = (request.args.get('type') or 'all').strip()
    query = AdminNotification.query
    if notif_type != 'all':
        query = query.filter_by(notification_type=notif_type)

    notifications = query.order_by(
        AdminNotification.is_checked.asc(),
        AdminNotification.created_at.desc()
    ).all()
    unread_comments_count = PageComment.query.filter_by(
        is_teacher_reply=False,
        is_read_by_admin=False
    ).count()

    return render_template(
        'admin/notifications.html',
        notifications=notifications,
        selected_type=notif_type,
        unread_comments_count=unread_comments_count
    )


@admin.route('/admin/notifications/<int:notif_id>/check', methods=['POST'])
@login_required
def check_admin_notification(notif_id):
    if not current_user.is_admin:
        abort(403)
    notif = AdminNotification.query.get_or_404(notif_id)
    try:
        notif.is_checked = True
        notif.checked_at = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()
    return redirect(request.referrer or url_for('admin.admin_notifications_page'))


@admin.route('/admin/notifications/delete_all', methods=['POST'])
@login_required
def delete_all_admin_notifications():
    if not current_user.is_admin:
        abort(403)
    try:
        count = db.session.query(AdminNotification).delete()
        db.session.commit()
        flash(_('Deleted %(count)s notification(s).', count=count), 'info')
    except Exception as e:
        db.session.rollback()
        flash(_('Error clearing notifications: %(error)s', error=str(e)), 'danger')
    return redirect(request.referrer or url_for('admin.admin_notifications_page'))


@admin.route('/admin/teacher-requests')
@login_required
def admin_teacher_requests():
    """Admin review queue for public Teacher signup applications."""
    if not current_user.is_admin:
        abort(403)

    requests_list = TeacherRequest.query.order_by(
        TeacherRequest.status.asc(),
        TeacherRequest.created_at.desc()
    ).all()
    return render_template('admin/teacher_requests.html', requests=requests_list)


@admin.route('/admin/teacher-requests/<int:req_id>/approve', methods=['POST'])
@login_required
def approve_teacher_request(req_id):
    if not current_user.is_admin:
        abort(403)

    req = TeacherRequest.query.get_or_404(req_id)
    if req.status == 'approved':
        flash(_('This application was already approved.'), 'info')
        return redirect(url_for('admin.admin_teacher_requests'))

    if User.query.filter_by(email=req.email).first():
        flash(_('Error: A user with email "%(email)s" already exists.', email=req.email), 'danger')
        return redirect(url_for('admin.admin_teacher_requests'))
    if User.query.filter_by(username=req.name_en).first():
        flash(_('Error: A user named "%(username)s" already exists.', username=req.name_en), 'danger')
        return redirect(url_for('admin.admin_teacher_requests'))

    new_teacher = User(
        username=req.name_en,
        username_kurdish=req.name_ku,
        email=req.email,
        password_hash=req.password_hash,
        gender=req.gender,
        birth_date=req.birth_date,
        bio=req.bio,
        is_admin=False
    )
    req.status = 'approved'
    req.reviewed_by_id = current_user.id
    req.reviewed_at = datetime.utcnow()
    req.admin_note = (request.form.get('admin_note') or '').strip() or None

    try:
        db.session.add(new_teacher)
        db.session.commit()
        flash(_('Teacher account approved and created for %(name)s.', name=req.name_en), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error approving request: %(error)s', error=str(e)), 'danger')

    return redirect(url_for('admin.admin_teacher_requests'))


@admin.route('/admin/teacher-requests/<int:req_id>/reject', methods=['POST'])
@login_required
def reject_teacher_request(req_id):
    if not current_user.is_admin:
        abort(403)

    req = TeacherRequest.query.get_or_404(req_id)
    req.status = 'rejected'
    req.reviewed_by_id = current_user.id
    req.reviewed_at = datetime.utcnow()
    req.admin_note = (request.form.get('admin_note') or '').strip() or None
    try:
        db.session.commit()
        flash(_('Application rejected.'), 'warning')
    except Exception as e:
        db.session.rollback()
        flash(_('Error rejecting request: %(error)s', error=str(e)), 'danger')
    return redirect(url_for('admin.admin_teacher_requests'))


@admin.route('/admin/teacher-requests/<int:req_id>/delete', methods=['POST'])
@login_required
def delete_teacher_request(req_id):
    if not current_user.is_admin:
        abort(403)

    req = TeacherRequest.query.get_or_404(req_id)
    try:
        db.session.delete(req)
        db.session.commit()
        flash(_('Application record deleted.'), 'info')
    except Exception as e:
        db.session.rollback()
        flash(_('Error deleting record: %(error)s', error=str(e)), 'danger')
    return redirect(url_for('admin.admin_teacher_requests'))
