from flask import Blueprint, render_template, url_for, flash, redirect, abort, request
from flask_babel import gettext as _
from flask_login import login_required, current_user

import pandas as pd

from app import db
from app.models import SystemCommand
from app.forms import BulkImportForm, CommandForm

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
