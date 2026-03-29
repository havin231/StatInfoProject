import json
import pandas as pd
from flask import Blueprint, render_template, url_for, flash, redirect, request, abort, jsonify, Response
from flask_login import login_required, current_user
import csv
import io

from app import db
from app.models import User, Subject, Page, Question, Resource, StudentAnswer
from app.forms import SubjectForm, PageForm, QuestionForm, BulkImportForm, ResourceForm
from app.routes.helpers import generate_access_code
from app.models import Student

content = Blueprint('content', __name__)

# ==============================================================================
# SECTION 8: BULK IMPORT ENGINE (WITH LANGUAGE & LECTURE LOGIC)
# ==============================================================================

@content.route('/admin/import/students', methods=['POST'])
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
            if 'name' not in data_frame.columns:
                flash('Import Error: Your file must contain a column named "Name".', 'danger')
                return redirect(url_for('admin.admin_students'))

            # Construct the preview list
            batch_preview_list = []
            for index, row in data_frame.iterrows():
                batch_preview_list.append({
                    'full_name': str(row['name']),
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
            return redirect(url_for('admin.admin_students'))

    flash('File upload failed. Please ensure you selected a valid CSV or Excel file.', 'danger')
    return redirect(url_for('admin.admin_students'))


@content.route('/teacher/import/questions/<int:subject_id>', methods=['POST'])
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
                return redirect(url_for('content.builder_exam', subject=target_subject.id))

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
            return redirect(url_for('content.builder_exam', subject=target_subject.id))

    flash('Invalid request or file format.', 'danger')
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
                    access_code=final_code
                ))
                save_count += 1

            db.session.commit()
            flash(f'Batch Processed: {save_count} students added.', 'success')
            return redirect(url_for('admin.admin_students'))

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
            return redirect(url_for('content.builder_exam', subject=subject_record.id))

    except Exception as commit_error:
        db.session.rollback()
        flash(f'Critical Commit Failure: {str(commit_error)}', 'danger')
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

    return redirect(url_for('teacher.teacher_dashboard'))


@content.route('/teacher/edit/subject/<int:subject_id>', methods=['GET', 'POST'])
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
        return redirect(url_for('teacher.teacher_dashboard'))

    return render_template('teacher/builder.html', form=form, title="Edit Subject Details", subject=subj_record)


@content.route('/teacher/delete/subject/<int:subject_id>')
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
    from app.models import ExamResult
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

    return redirect(url_for('teacher.teacher_dashboard'))


@content.route('/teacher/builder/info', methods=['GET', 'POST'])
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
        return redirect(url_for('teacher.teacher_dashboard'))

    return render_template('teacher/builder.html', form=form, title="Create New Lecture", subject=subj_record)


@content.route('/teacher/edit/page/<int:page_id>', methods=['GET', 'POST'])
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
        return redirect(url_for('student.subject_detail', slug=target_page.subject.slug))

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

    if not current_user.is_admin and target_page.subject.teacher_id != current_user.id:
        abort(403)

    subject_slug_ref = target_page.subject.slug
    db.session.delete(target_page)
    db.session.commit()

    flash('Lecture deleted.', 'success')
    return redirect(url_for('student.subject_detail', slug=subject_slug_ref))


@content.route('/teacher/resource/add/<int:page_id>', methods=['POST'])
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

    return redirect(url_for('content.edit_page', page_id=target_page.id))


@content.route('/teacher/resource/delete/<int:resource_id>')
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
    return redirect(url_for('content.edit_page', page_id=parent_page_id))


# ==============================================================================
# SECTION 10: QUESTION BANK MANAGEMENT
# ==============================================================================

@content.route('/teacher/builder/exam', methods=['GET'])
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


@content.route('/teacher/export/questions/<int:subject_id>', methods=['GET'])
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


@content.route('/teacher/edit/question/<int:question_id>', methods=['GET', 'POST'])
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
        return redirect(url_for('student.subject_detail', slug=target_q.subject.slug))

    return render_template('teacher/builder.html', form=form, title="Modify Question", subject=target_q.subject)


@content.route('/teacher/delete/question/<int:question_id>')
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

    return redirect(url_for('student.subject_detail', slug=subject_slug_ref))
