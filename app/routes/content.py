import json
import pandas as pd
from flask import Blueprint, render_template, url_for, flash, redirect, request, abort, jsonify, Response
from flask_babel import gettext as _
from flask_login import login_required, current_user
import csv
import io

from app import db
from app.models import (
    User, Subject, Page, Question, Resource, ExamResult,
    SystemCommand, SubjectTeacher, AdminNotification, PageComment, TeacherNotification
)
from app.forms import SubjectForm, PageForm, QuestionForm, BulkImportForm, ResourceForm
from app.routes.helpers import can_edit_subject

content = Blueprint('content', __name__)

# ==============================================================================
# SECTION 8: BULK IMPORT ENGINE (WITH LANGUAGE & LECTURE LOGIC)
# ==============================================================================

@content.route('/teacher/import/questions/<int:subject_id>', methods=['POST'])
@login_required
def import_questions_step1(subject_id):
    """
    BULK QUESTION IMPORT (STEP 1: PARSING)

    Logic:
    - Parses the question table.
    - Fetches current Subject Lectures to populate the Batch Settings dropdown.
    """
    # 1. Permission and Context check (v0.5.0 - Multi-Teacher Support)
    target_subject = Subject.query.get_or_404(subject_id)
    if not can_edit_subject(target_subject):
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

            # Define required structure (accept both 'answer' and 'ans' headers)
            if 'answer' not in data_frame.columns and 'ans' in data_frame.columns:
                data_frame['answer'] = data_frame['ans']

            required_fields = ['question', 'opt a', 'opt b', 'opt c', 'opt d', 'answer']
            missing_fields = [f for f in required_fields if f not in data_frame.columns]

            if missing_fields:
                flash(_('Import Error: Missing columns: %(fields)s', fields=", ".join(missing_fields)), 'danger')
                return redirect(url_for('content.builder_exam', subject=target_subject.id))

            def clean_cell(val):
                return '' if pd.isna(val) else str(val).strip()

            # Prepare Preview
            question_preview_data = []
            for _, row in data_frame.iterrows():
                raw_ans = clean_cell(row['answer']).upper()
                ans_char = raw_ans[0] if raw_ans and raw_ans[0] in ('A', 'B', 'C', 'D') else 'A'
                question_preview_data.append({
                    'question_text': clean_cell(row['question']),
                    'option_a': clean_cell(row['opt a']),
                    'option_b': clean_cell(row['opt b']),
                    'option_c': clean_cell(row['opt c']),
                    'option_d': clean_cell(row['opt d']),
                    'question_text_kurdish': clean_cell(row.get('question_ku', '')) if 'question_ku' in data_frame.columns else '',
                    'option_a_kurdish': clean_cell(row.get('opt a_ku', '')) if 'opt a_ku' in data_frame.columns else '',
                    'option_b_kurdish': clean_cell(row.get('opt b_ku', '')) if 'opt b_ku' in data_frame.columns else '',
                    'option_c_kurdish': clean_cell(row.get('opt c_ku', '')) if 'opt c_ku' in data_frame.columns else '',
                    'option_d_kurdish': clean_cell(row.get('opt d_ku', '')) if 'opt d_ku' in data_frame.columns else '',
                    'correct_answer': ans_char
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
            flash(_('Processing Error: %(error)s', error=str(file_err)), 'danger')
            return redirect(url_for('content.builder_exam', subject=target_subject.id))

    flash(_('Invalid request or file format.'), 'danger')
    return redirect(url_for('content.builder_exam', subject=target_subject.id))


@content.route('/common/import/confirm', methods=['POST'])
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

        # 2. Handle Question Commit (Includes Batch Language and Lecture)
        if import_category == 'question':
            subj_id_str = request.form.get('subject_id')
            subject_record = Subject.query.get_or_404(int(subj_id_str))

            if not can_edit_subject(subject_record):
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
                    question_text=q_row.get('question_text', ''),
                    option_a=q_row.get('option_a', ''),
                    option_b=q_row.get('option_b', ''),
                    option_c=q_row.get('option_c', ''),
                    option_d=q_row.get('option_d', ''),
                    question_text_kurdish=q_row.get('question_text_kurdish') or None,
                    option_a_kurdish=q_row.get('option_a_kurdish') or None,
                    option_b_kurdish=q_row.get('option_b_kurdish') or None,
                    option_c_kurdish=q_row.get('option_c_kurdish') or None,
                    option_d_kurdish=q_row.get('option_d_kurdish') or None,
                    correct_answer=q_row['correct_answer'],
                    subject_id=subject_record.id,
                    page_id=global_pid,     # Linked to specific lecture
                    is_kurdish=mark_kurdish # Applied globally per your request
                ))
                q_save_count += 1

            if not current_user.is_admin and q_save_count > 0:
                db.session.add(AdminNotification(
                    notification_type='question_added',
                    title=f"{subject_record.name} — Questions Imported",
                    message=f"{current_user.username} imported {q_save_count} question(s) into {subject_record.name}.",
                    actor_type='teacher',
                    actor_id=current_user.id,
                    actor_name=current_user.username,
                    related_subject_id=subject_record.id,
                    related_page_id=global_pid
                ))

            db.session.commit()
            flash(_('Batch Processed: %(count)s questions assigned to bank.', count=q_save_count), 'success')
            return redirect(url_for('content.builder_exam', subject=subject_record.id))

        # 4. Handle System Command Commit
        elif import_category == 'command':
            if not current_user.is_admin:
                abort(403)

            cmd_save_count = 0
            for cmd_row in parsed_data:
                db.session.add(SystemCommand(
                    title=cmd_row['title'],
                    title_kurdish=cmd_row.get('title_kurdish') or None,
                    command_text=cmd_row['command_text'],
                    description=cmd_row.get('description', ''),
                    description_kurdish=cmd_row.get('description_kurdish') or None
                ))
                cmd_save_count += 1

            db.session.commit()
            flash(_('Batch Processed: %(count)s system commands documented.', count=cmd_save_count), 'success')
            return redirect(url_for('admin.admin_command_center'))

    except Exception as commit_error:
        db.session.rollback()
        flash(_('Critical Commit Failure: %(error)s', error=str(commit_error)), 'danger')
        return redirect(url_for('teacher.teacher_dashboard'))

    return redirect(url_for('teacher.teacher_dashboard'))


# ==============================================================================
# SECTION 9: SUBJECT & CONTENT MANAGEMENT
# ==============================================================================

@content.route('/teacher/add_subject', methods=['POST'])
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
            flash(_('Error: The URL Slug must be unique across all subjects.'), 'danger')
        else:
            # Support assigning multiple teachers at creation time
            raw_ids = request.form.getlist('teacher_ids')
            selected_ids = []
            for raw in raw_ids:
                try:
                    tid = int(raw)
                    if tid not in selected_ids:
                        selected_ids.append(tid)
                except ValueError:
                    continue

            primary_tid = form.teacher_id.data
            if primary_tid and primary_tid not in selected_ids:
                selected_ids.insert(0, primary_tid)
            if not selected_ids:
                selected_ids = [primary_tid]

            new_subj = Subject(
                name=form.name.data,
                name_kurdish=form.name_kurdish.data,
                slug=form.slug.data,
                description=form.description.data,
                description_kurdish=form.description_kurdish.data,
                teacher_id=selected_ids[0]
            )
            try:
                db.session.add(new_subj)
                db.session.flush()

                assigned_users = User.query.filter(User.id.in_(selected_ids)).all()
                user_map = {u.id: u for u in assigned_users}
                for tid in selected_ids:
                    if tid in user_map:
                        u = user_map[tid]
                        db.session.add(SubjectTeacher(
                            subject_id=new_subj.id,
                            teacher_id=tid,
                            is_primary=(tid == selected_ids[0]),
                            show_name=bool(u.show_name_on_subject)
                        ))
                db.session.commit()
                flash(_('Subject "%(name)s" created successfully.', name=form.name.data), 'success')
            except Exception as e:
                db.session.rollback()
                flash(_('Error creating subject: %(error)s', error=str(e)), 'danger')

    return redirect(url_for('teacher.teacher_dashboard'))


@content.route('/teacher/edit/subject/<int:subject_id>', methods=['GET', 'POST'])
@login_required
def edit_subject(subject_id):
    """Edits subject metadata."""
    subj_record = Subject.query.get_or_404(subject_id)

    if not can_edit_subject(subj_record):
        abort(403)

    form = SubjectForm(obj=subj_record)

    # Restrict dropdown based on role
    if current_user.is_admin:
         form.teacher_id.choices = [(t.id, t.username) for t in User.query.all()]
    else:
         form.teacher_id.choices = [(current_user.id, current_user.username)]

    if form.validate_on_submit():
        duplicate_slug = Subject.query.filter(
            Subject.slug == form.slug.data,
            Subject.id != subj_record.id
        ).first()
        if duplicate_slug:
            flash(_('Error: The URL Slug must be unique across all subjects.'), 'danger')
            return render_template('teacher/builder.html', form=form, title="Edit Subject Details", subject=subj_record)

        subj_record.name = form.name.data
        subj_record.name_kurdish = form.name_kurdish.data
        subj_record.slug = form.slug.data
        subj_record.description = form.description.data
        subj_record.description_kurdish = form.description_kurdish.data

        if current_user.is_admin and form.teacher_id.data:
            new_primary_tid = form.teacher_id.data
            subj_record.teacher_id = new_primary_tid
            SubjectTeacher.query.filter_by(subject_id=subj_record.id, is_primary=True).update({'is_primary': False})
            existing_assign = SubjectTeacher.query.filter_by(
                subject_id=subj_record.id, teacher_id=new_primary_tid
            ).first()
            if existing_assign:
                existing_assign.is_primary = True
            else:
                teacher_obj = User.query.get(new_primary_tid)
                db.session.add(SubjectTeacher(
                    subject_id=subj_record.id,
                    teacher_id=new_primary_tid,
                    is_primary=True,
                    show_name=bool(teacher_obj.show_name_on_subject) if teacher_obj else False
                ))

        db.session.commit()
        flash(_('Subject information updated.'), 'success')
        return redirect(url_for('teacher.teacher_dashboard'))

    return render_template('teacher/builder.html', form=form, title="Edit Subject Details", subject=subj_record)


@content.route('/teacher/delete/subject/<int:subject_id>')
@login_required
def delete_subject(subject_id):
    """
    SAFE SUBJECT DELETION (BOTTOM-UP ORDER)

    Removes:
    1. Admin Notifications
    2. Exam Results
    3. Questions (before Pages due to page_id FK)
    4. Resources & Pages/Lectures
    5. SubjectTeacher assignments
    6. Subject record
    """
    subj_record = Subject.query.get_or_404(subject_id)

    if not can_edit_subject(subj_record):
        abort(403)

    try:
        # A. Clear notifications referencing this subject
        TeacherNotification.query.filter_by(related_subject_id=subj_record.id).delete()
        AdminNotification.query.filter_by(related_subject_id=subj_record.id).delete()

        # B. Clear exam results
        ExamResult.query.filter_by(subject_id=subj_record.id).delete()

        # C. Clear Question bank (before Pages because Question.page_id references Page.id)
        Question.query.filter_by(subject_id=subj_record.id).delete()

        # D. Clear Resources, Comments (replies first), and Lectures
        pages_list = Page.query.filter_by(subject_id=subj_record.id).all()
        for p in pages_list:
            PageComment.query.filter(PageComment.page_id == p.id, PageComment.parent_id.isnot(None)).delete(synchronize_session=False)
            PageComment.query.filter_by(page_id=p.id).delete()
            Resource.query.filter_by(page_id=p.id).delete()
            db.session.delete(p)

        # E. Clear teacher assignments
        SubjectTeacher.query.filter_by(subject_id=subj_record.id).delete()

        # F. Purge Subject
        db.session.delete(subj_record)
        db.session.commit()
        flash(_('Subject "%(name)s" and all internal content has been deleted.', name=subj_record.name), 'success')

    except Exception as e:
        db.session.rollback()
        flash(_('Deletion failed: %(error)s', error=str(e)), 'danger')

    return redirect(url_for('teacher.teacher_dashboard'))


@content.route('/teacher/builder/info', methods=['GET', 'POST'])
@login_required
def builder_info():
    """Route to add a new lecture page."""
    sid_param = request.args.get('subject', type=int)
    if not sid_param:
        abort(404)
    subj_record = Subject.query.get_or_404(sid_param)

    if not can_edit_subject(subj_record):
        abort(403)

    form = PageForm()
    form.subject_id.choices = [(subj_record.id, subj_record.name)]

    if request.method == 'GET':
        form.subject_id.data = subj_record.id

    if form.validate_on_submit():
        new_page_record = Page(
            title=form.title.data,
            title_kurdish=form.title_kurdish.data,
            content_body=form.content_body.data,
            content_body_kurdish=form.content_body_kurdish.data,
            subject_id=subj_record.id
        )
        db.session.add(new_page_record)
        db.session.flush()
        if not current_user.is_admin:
            db.session.add(AdminNotification(
                notification_type='page_added',
                title=f"{subj_record.name} — {new_page_record.title}",
                message=f"{current_user.username} added lecture '{new_page_record.title}' to {subj_record.name}.",
                actor_type='teacher',
                actor_id=current_user.id,
                actor_name=current_user.username,
                related_subject_id=subj_record.id,
                related_page_id=new_page_record.id
            ))
        db.session.commit()
        flash(_('Lecture content published.'), 'success')
        return redirect(url_for('teacher.teacher_dashboard'))

    return render_template('teacher/builder.html', form=form, title="Create New Lecture", subject=subj_record)


@content.route('/teacher/edit/page/<int:page_id>', methods=['GET', 'POST'])
@login_required
def edit_page(page_id):
    """Route to edit lecture content and manage multiple resources."""
    target_page = Page.query.get_or_404(page_id)

    if not can_edit_subject(target_page.subject):
        abort(403)

    form = PageForm(obj=target_page)
    form.subject_id.choices = [(target_page.subject.id, target_page.subject.name)]

    # Resource management form
    res_form_instance = ResourceForm()

    if form.validate_on_submit():
        target_page.title = form.title.data
        target_page.title_kurdish = form.title_kurdish.data
        target_page.content_body = form.content_body.data
        target_page.content_body_kurdish = form.content_body_kurdish.data
        if not current_user.is_admin:
            db.session.add(AdminNotification(
                notification_type='page_edited',
                title=f"{target_page.subject.name} — {target_page.title}",
                message=f"{current_user.username} updated lecture '{target_page.title}' in {target_page.subject.name}.",
                actor_type='teacher',
                actor_id=current_user.id,
                actor_name=current_user.username,
                related_subject_id=target_page.subject.id,
                related_page_id=target_page.id
            ))
        db.session.commit()
        flash(_('Changes saved.'), 'success')
        return redirect(url_for('public.subject_detail', slug=target_page.subject.slug))

    return render_template(
        'teacher/builder.html',
        form=form,
        title="Edit Lecture Content",
        subject=target_page.subject,
        page=target_page,
        resource_form=res_form_instance
    )


@content.route('/teacher/delete/page/<int:page_id>')
@login_required
def delete_page(page_id):
    """Purges a single lecture."""
    target_page = Page.query.get_or_404(page_id)

    if not can_edit_subject(target_page.subject):
        abort(403)

    subject_slug_ref = target_page.subject.slug
    try:
        TeacherNotification.query.filter_by(related_page_id=target_page.id).delete()
        AdminNotification.query.filter_by(related_page_id=target_page.id).delete()
        ExamResult.query.filter_by(page_id=target_page.id).update({'page_id': None})
        PageComment.query.filter(PageComment.page_id == target_page.id, PageComment.parent_id.isnot(None)).delete(synchronize_session=False)
        PageComment.query.filter_by(page_id=target_page.id).delete()
        Resource.query.filter_by(page_id=target_page.id).delete()
        Question.query.filter_by(page_id=target_page.id).update({'page_id': None})
        db.session.delete(target_page)
        db.session.commit()
        flash(_('Lecture deleted.'), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error deleting lecture: %(error)s', error=str(e)), 'danger')

    return redirect(url_for('public.subject_detail', slug=subject_slug_ref))


@content.route('/teacher/comment/delete/<int:comment_id>', methods=['POST'])
@login_required
def delete_page_comment(comment_id):
    """Allows subject teachers or admins to remove a comment (and its replies) on a lecture."""
    comment = PageComment.query.get_or_404(comment_id)
    target_page = comment.page
    target_subject = target_page.subject

    if not can_edit_subject(target_subject):
        abort(403)

    slug = target_subject.slug
    page_id = target_page.id

    try:
        PageComment.query.filter_by(parent_id=comment.id).delete()
        db.session.delete(comment)
        db.session.commit()
        flash(_('Comment deleted.'), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error deleting comment: %(error)s', error=str(e)), 'danger')

    next_url = request.form.get('next')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect(url_for('public.view_page', slug=slug, page_id=page_id) + '#comments-section')


@content.route('/subject/<slug>/page/<int:page_id>/comment/<int:comment_id>/reply', methods=['POST'])
@login_required
def reply_page_comment(slug, page_id, comment_id):
    """Allows teachers (assigned to subject) or admins to reply to a visitor's comment."""
    from app.forms import CommentReplyForm
    target_subject = Subject.query.filter_by(slug=slug).first_or_404()
    target_page = Page.query.get_or_404(page_id)
    parent_comment = PageComment.query.get_or_404(comment_id)

    if target_page.subject_id != target_subject.id or parent_comment.page_id != target_page.id:
        abort(404)

    if not can_edit_subject(target_subject):
        abort(403)

    form = CommentReplyForm()
    if form.validate_on_submit():
        reply = PageComment(
            page_id=target_page.id,
            parent_id=parent_comment.id,
            author_user_id=current_user.id,
            is_teacher_reply=True,
            is_read_by_admin=True,
            author_name=current_user.username,
            comment_text=form.comment_text.data.strip()
        )
        try:
            db.session.add(reply)
            db.session.commit()
            flash(_('Reply posted.'), 'success')
        except Exception as e:
            db.session.rollback()
            flash(_('Error posting reply: %(error)s', error=str(e)), 'danger')
    else:
        flash(_('Reply text cannot be empty.'), 'danger')

    next_url = request.form.get('next')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect(url_for('public.view_page', slug=slug, page_id=page_id) + '#comments-section')


@content.route('/teacher/resource/add/<int:page_id>', methods=['POST'])
@login_required
def add_resource(page_id):
    """Logic to attach a link to a lecture."""
    target_page = Page.query.get_or_404(page_id)

    if not can_edit_subject(target_page.subject):
        abort(403)

    form = ResourceForm()
    if form.validate_on_submit():
        new_res = Resource(
            title=form.title.data,
            title_kurdish=form.title_kurdish.data,
            link=form.link.data,
            page_id=target_page.id
        )
        db.session.add(new_res)
        db.session.commit()
        flash(_('Learning resource attached.'), 'success')
    else:
        flash(_('Attachment Error: Title and Link are required.'), 'danger')

    return redirect(url_for('content.edit_page', page_id=target_page.id))


@content.route('/teacher/resource/delete/<int:resource_id>')
@login_required
def delete_resource(resource_id):
    """Logic to remove an attached link."""
    target_res = Resource.query.get_or_404(resource_id)
    parent_page_id = target_res.page_id

    if not can_edit_subject(target_res.page.subject):
        abort(403)

    db.session.delete(target_res)
    db.session.commit()
    flash(_('Resource removed.'), 'success')
    return redirect(url_for('content.edit_page', page_id=parent_page_id))


# ==============================================================================
# SECTION 10: QUESTION BANK MANAGEMENT
# ==============================================================================

@content.route('/teacher/builder/exam', methods=['GET'])
@login_required
def builder_exam():
    """Displays the Bulk Spreadsheet Editor for Questions."""
    sid_param = request.args.get('subject', type=int)
    if not sid_param:
        abort(404)
    target_subject = Subject.query.get_or_404(sid_param)

    if not can_edit_subject(target_subject):
        abort(403)

    form = QuestionForm()
    import_form = BulkImportForm()

    # Prepare lecture list for the spreadsheet column
    subject_lectures_list = [{'id': p.id, 'title': p.title} for p in Page.query.filter_by(subject_id=target_subject.id).all()]

    # Use direct query instead of relationship for reliability after restoration
    existing_questions_data = []
    all_questions = Question.query.filter_by(subject_id=target_subject.id).all()
    for question in all_questions:
        existing_questions_data.append({
            'id': question.id,
            'text': question.question_text,
            'a': question.option_a,
            'b': question.option_b,
            'c': question.option_c,
            'd': question.option_d,
            'text_ku': question.question_text_kurdish or '',
            'a_ku': question.option_a_kurdish or '',
            'b_ku': question.option_b_kurdish or '',
            'c_ku': question.option_c_kurdish or '',
            'd_ku': question.option_d_kurdish or '',
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


@content.route('/teacher/api/save_questions/<int:subject_id>', methods=['POST'])
@login_required
def save_questions_api(subject_id):
    """The AJAX backend that saves the Bulk Editor grid data (supports dual EN & KU faces)."""
    target_subject = Subject.query.get_or_404(subject_id)
    if not can_edit_subject(target_subject):
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    incoming_json_data = request.get_json()
    if incoming_json_data is None:
        return jsonify({'status': 'error', 'message': 'Payload Empty'}), 400

    try:
        # Determine which IDs were sent
        sent_ids = [q['id'] for q in incoming_json_data if q.get('id')]

        # 1. Clean up deleted questions (unlink AdminNotification FK first)
        current_db_questions = Question.query.filter_by(subject_id=target_subject.id).all()
        for q_db in current_db_questions:
            if q_db.id not in sent_ids:
                AdminNotification.query.filter_by(related_question_id=q_db.id).update({'related_question_id': None})
                db.session.delete(q_db)

        # 2. Process UPSERT (Update or Insert)
        for data_row in incoming_json_data:
            text_content = (data_row.get('text') or '').strip()
            text_ku = (data_row.get('text_ku') or '').strip()
            if not text_content and not text_ku:
                continue

            # Handle Foreign Key for Lecture
            pid_val = data_row.get('page_id')
            if pid_val == "" or pid_val == "None" or pid_val == 0:
                pid_val = None
            else:
                pid_val = int(pid_val)

            kurdish_flag = bool(data_row.get('is_kurdish', False))

            if data_row.get('id'):
                target_q = Question.query.get(data_row['id'])
                if target_q and target_q.subject_id == target_subject.id:
                    target_q.question_text = text_content
                    target_q.option_a = data_row.get('a', '')
                    target_q.option_b = data_row.get('b', '')
                    target_q.option_c = data_row.get('c', '')
                    target_q.option_d = data_row.get('d', '')
                    target_q.question_text_kurdish = text_ku or None
                    target_q.option_a_kurdish = (data_row.get('a_ku') or '').strip() or None
                    target_q.option_b_kurdish = (data_row.get('b_ku') or '').strip() or None
                    target_q.option_c_kurdish = (data_row.get('c_ku') or '').strip() or None
                    target_q.option_d_kurdish = (data_row.get('d_ku') or '').strip() or None
                    target_q.correct_answer = data_row.get('correct', 'A')
                    target_q.page_id = pid_val
                    target_q.is_kurdish = kurdish_flag
            else:
                db.session.add(Question(
                    question_text=text_content,
                    option_a=data_row.get('a', ''),
                    option_b=data_row.get('b', ''),
                    option_c=data_row.get('c', ''),
                    option_d=data_row.get('d', ''),
                    question_text_kurdish=text_ku or None,
                    option_a_kurdish=(data_row.get('a_ku') or '').strip() or None,
                    option_b_kurdish=(data_row.get('b_ku') or '').strip() or None,
                    option_c_kurdish=(data_row.get('c_ku') or '').strip() or None,
                    option_d_kurdish=(data_row.get('d_ku') or '').strip() or None,
                    correct_answer=data_row.get('correct', 'A'),
                    subject_id=target_subject.id,
                    page_id=pid_val,
                    is_kurdish=kurdish_flag
                ))

        if not current_user.is_admin:
            db.session.add(AdminNotification(
                notification_type='question_edited',
                title=f"{target_subject.name} — Question Bank Updated",
                message=f"{current_user.username} updated the question bank for {target_subject.name}.",
                actor_type='teacher',
                actor_id=current_user.id,
                actor_name=current_user.username,
                related_subject_id=target_subject.id
            ))

        db.session.commit()
        return jsonify({'status': 'success'})

    except Exception as fatal_api_err:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(fatal_api_err)}), 500


@content.route('/teacher/export/questions/<int:subject_id>', methods=['GET'])
@login_required
def export_questions_csv(subject_id):
    """Exports bilingual Question Bank for a subject. Uses strict quoting and BOM."""
    target_subject = Subject.query.get_or_404(subject_id)
    if not can_edit_subject(target_subject):
        abort(403)

    string_io_obj = io.StringIO()
    string_io_obj.write('\ufeff') # BOM for Excel UTF-8
    csv_writer_obj = csv.writer(string_io_obj, quoting=csv.QUOTE_ALL)

    csv_writer_obj.writerow([
        'Question', 'Opt A', 'Opt B', 'Opt C', 'Opt D',
        'Question_KU', 'Opt A_KU', 'Opt B_KU', 'Opt C_KU', 'Opt D_KU',
        'Answer', 'Kurdish'
    ])
    for q in target_subject.questions:
        csv_writer_obj.writerow([
            q.question_text, q.option_a, q.option_b, q.option_c, q.option_d,
            q.question_text_kurdish or '', q.option_a_kurdish or '',
            q.option_b_kurdish or '', q.option_c_kurdish or '', q.option_d_kurdish or '',
            q.correct_answer, "True" if q.is_kurdish else "False"
        ])

    return Response(
        string_io_obj.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={target_subject.slug}_questions.csv"}
    )


@content.route('/teacher/edit/question/<int:question_id>', methods=['GET', 'POST'])
@login_required
def edit_question(question_id):
    """Edit a single bilingual question manually."""
    target_q = Question.query.get_or_404(question_id)
    if not can_edit_subject(target_q.subject):
        abort(403)

    form = QuestionForm(obj=target_q)
    form.subject_id.choices = [(target_q.subject.id, target_q.subject.name)]

    # Get available lectures for dropdown
    form.page_id.choices = [(0, "(None - General Exam)")] + [(p.id, p.title) for p in target_q.subject.pages]

    if form.validate_on_submit():
        target_q.question_text = (form.question_text.data or '').strip()
        target_q.option_a = (form.option_a.data or '').strip()
        target_q.option_b = (form.option_b.data or '').strip()
        target_q.option_c = (form.option_c.data or '').strip()
        target_q.option_d = (form.option_d.data or '').strip()
        target_q.question_text_kurdish = (form.question_text_kurdish.data or '').strip() or None
        target_q.option_a_kurdish = (form.option_a_kurdish.data or '').strip() or None
        target_q.option_b_kurdish = (form.option_b_kurdish.data or '').strip() or None
        target_q.option_c_kurdish = (form.option_c_kurdish.data or '').strip() or None
        target_q.option_d_kurdish = (form.option_d_kurdish.data or '').strip() or None
        target_q.correct_answer = form.correct_answer.data
        target_q.is_kurdish = form.is_kurdish.data

        if form.page_id.data == 0:
            target_q.page_id = None
        else:
            target_q.page_id = form.page_id.data

        if not current_user.is_admin:
            db.session.add(AdminNotification(
                notification_type='question_edited',
                title=f"{target_q.subject.name} — Question Edited",
                message=f"{current_user.username} edited a question in {target_q.subject.name}.",
                actor_type='teacher',
                actor_id=current_user.id,
                actor_name=current_user.username,
                related_subject_id=target_q.subject.id,
                related_page_id=target_q.page_id,
                related_question_id=target_q.id
            ))

        db.session.commit()
        flash(_('Question updated.'), 'success')
        return redirect(url_for('public.subject_detail', slug=target_q.subject.slug))

    return render_template('teacher/builder.html', form=form, title="Modify Question", subject=target_q.subject)


@content.route('/teacher/delete/question/<int:question_id>')
@login_required
def delete_question(question_id):
    """Single question deletion logic."""
    target_q = Question.query.get_or_404(question_id)
    if not can_edit_subject(target_q.subject):
        abort(403)

    subject_slug_ref = target_q.subject.slug
    try:
        AdminNotification.query.filter_by(related_question_id=target_q.id).update({'related_question_id': None})
        db.session.delete(target_q)
        db.session.commit()
        flash(_('Question removed from bank.'), 'success')
    except Exception as e:
        db.session.rollback()
        flash(_('Error during question deletion: %(error)s', error=str(e)), 'danger')

    return redirect(url_for('public.subject_detail', slug=subject_slug_ref))
