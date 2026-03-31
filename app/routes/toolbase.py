import pandas as pd
from flask import Blueprint, render_template, url_for, flash, redirect, request, abort
from flask_babel import gettext as _
from flask_login import login_required, current_user
from sqlalchemy import desc

from app import db
from app.models import Tool
from app.forms import ToolForm, BulkImportForm

tools = Blueprint('tools', __name__)

# ==============================================================================
# SECTION: TOOL BASE
# ==============================================================================

@tools.route('/toolbase', methods=['GET', 'POST'])
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
            if not form.link.data:
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
                    flash(_('New tool added successfully.'), 'success')
                    return redirect(url_for('tools.toolbase'))
                except Exception as e:
                    db.session.rollback()
                    flash(_('Error adding tool: %(error)s', error=str(e)), 'danger')

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
                    flash(_('Import Error: CSV must have \"Name\" and \"Link\" columns.'), 'danger')
                    return redirect(url_for('tools.toolbase'))
                
                # Iterate and Add
                count = 0
                for _, row in df.iterrows():
                    t_title = str(row['name']).strip()
                    t_link = str(row['link']).strip()
                    t_desc = str(row.get('description', '')).strip()
                    
                    if t_title and t_link:
                         new_tool = Tool(
                             title=t_title,
                             link=t_link,
                             description=t_desc
                         )
                         db.session.add(new_tool)
                         count += 1
                
                db.session.commit()
                flash(_('Success! Imported %(count)s tools from file.', count=count), 'success')
                return redirect(url_for('tools.toolbase'))

            except Exception as e:
                db.session.rollback()
                flash(_('Import Failed: %(error)s', error=str(e)), 'danger')
            
    all_tools = Tool.query.order_by(desc(Tool.created_at)).all()
    return render_template('toolbase.html', form=form, import_form=import_form, tools=all_tools, is_admin=is_admin)

@tools.route('/toolbase/delete/<int:tool_id>', methods=['POST'])
@login_required
def delete_tool(tool_id):
    if not current_user.is_admin:
        abort(403)
    
    tool = Tool.query.get_or_404(tool_id)
    try:
        db.session.delete(tool)
        db.session.commit()
        flash(_('Tool deleted.'), 'success')
    except:
        db.session.rollback()
        flash(_('Error deleting tool.'), 'danger')
        
    return redirect(url_for('tools.toolbase'))


@tools.route('/toolbase/delete_all', methods=['POST'])
@login_required
def delete_all_tools():
    """
    DELETE ALL TOOLS
    """
    if not current_user.is_admin:
        abort(403)
    
    try:
        num_deleted = db.session.query(Tool).delete()
        db.session.commit()
        flash(_('All tools deleted! (%(count)s removed)', count=num_deleted), 'warning')
    except Exception as e:
        db.session.rollback()
        flash(_('Error deleting all tools: %(error)s', error=str(e)), 'danger')
        
    return redirect(url_for('tools.toolbase'))
