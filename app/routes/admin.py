from flask import Blueprint, render_template, url_for, flash, redirect, abort, request
from flask_babel import gettext as _
from flask_login import login_required, current_user

import pandas as pd

from app import db, bcrypt
from app.models import Student, ExamResult, StudentAnswer, SystemCommand
from app.forms import StudentForm, StudentEditForm, BulkImportForm, CommandForm
from app.routes.helpers import generate_access_code

admin = Blueprint('admin', __name__)

# ==============================================================================
# SECTION 6: STUDENT ADMINISTRATION (TASK 1 LOGIC)
# ==============================================================================

@admin.route('/admin/students', methods=['GET', 'POST'])
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

    from flask import request
    form_manual = StudentForm()
    form_batch = BulkImportForm()

    # Pre-generate a password to show in the UI placeholder
    if request.method == 'GET':
        import secrets
        random_password = secrets.token_urlsafe(8)
        form_manual.password.data = random_password

    # Manual Registration Logic
    if form_manual.validate_on_submit():
        # Check email uniqueness
        if form_manual.email.data and Student.query.filter_by(email=form_manual.email.data).first():
            flash(_('Error: This Email is already in use.'), 'danger')
        else:
            # Hash the password
            password_hash = bcrypt.generate_password_hash(form_manual.password.data).decode('utf-8')
            
            new_student = Student(
                full_name=form_manual.full_name.data,
                password_hash=password_hash,
                email=form_manual.email.data
            )
            db.session.add(new_student)
            db.session.commit()
            flash(_('Student "%(name)s" registered successfully.', name=form_manual.full_name.data), 'success')
            return redirect(url_for('admin.admin_students'))

    # Fetch all students for the table (Sorted by Newest First)
    all_students_roster = Student.query.order_by(Student.created_at.desc()).all()

    return render_template(
        'admin/students.html',
        form=form_manual,
        students=all_students_roster,
        import_form=form_batch
    )


@admin.route('/admin/edit/student/<int:student_id>', methods=['GET', 'POST'])
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
        # Check if email was changed and uniqueness
        if form.email.data and student_record.email != form.email.data:
            email_check = Student.query.filter_by(email=form.email.data).first()
            if email_check:
                flash(_('Critical Error: The new email is already assigned to someone else.'), 'danger')
                return render_template('admin/edit_student.html', form=form, student=student_record)

        # Update Record
        student_record.full_name = form.full_name.data
        student_record.email = form.email.data
        
        # Update password if provided
        if form.password.data:
            from app import bcrypt
            student_record.password_hash = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
            flash(_('Password has been updated.'), 'success')

        try:
            db.session.commit()
            flash(_('Student profile updated. All grades and history remain linked.'), 'success')
            return redirect(url_for('admin.admin_students'))
        except Exception as e:
            db.session.rollback()
            flash(_('Database Error: %(error)s', error=str(e)), 'danger')

    return render_template('admin/edit_student.html', form=form, student=student_record)


@admin.route('/admin/delete/student/<int:student_id>')
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
        flash(_('Student "%(name)s" and all their records have been removed.', name=target_student.full_name), 'success')
    except Exception as fatal_err:
        db.session.rollback()
        flash(_('Failed to delete student: %(error)s', error=str(fatal_err)), 'danger')

    return redirect(url_for('admin.admin_students'))


@admin.route('/admin/delete/all/students', methods=['POST'])
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
        flash(_('Database Wipe Successful: %(students)s students, %(results)s exams, and %(answers)s choices deleted.', students=count_students, results=count_results, answers=count_answers), 'success')

    except Exception as critical_wipe_error:
        db.session.rollback()
        flash(_('CRITICAL SYSTEM ERROR during batch wipe: %(error)s', error=str(critical_wipe_error)), 'danger')

    return redirect(url_for('admin.admin_students'))


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
            command_text=form.command_text.data,
            description=form.description.data
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

            # Construct the preview list
            command_preview_list = []
            for index, row in data_frame.iterrows():
                command_preview_list.append({
                    'title': str(row['title']),
                    'command_text': str(row['command']),
                    'description': str(row.get('description', ''))
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
