import csv
import io
import zipfile
from datetime import datetime
from flask import Blueprint, render_template, url_for, flash, redirect, request, abort, Response
from flask_babel import gettext as _
from flask_login import login_required, current_user
from sqlalchemy import desc

from app import db
from app.models import (
    User, Subject, Page, Question, ExamResult,
    SiteInfo, Resource, SystemCommand, Tool,
    SubjectTeacher, AdminNotification
)
from app.forms import InfoPageForm, RestoreBackupForm, WipeCleanForm

analytics = Blueprint('analytics', __name__)

# ==============================================================================
# SECTION 11: ANALYTICS, EXPORTS & CMS
# ==============================================================================

@analytics.route('/teacher/analytics')
@login_required
def teacher_analytics():
    """Redirect deprecated analytics route to teacher dashboard."""
    return redirect(url_for('teacher.teacher_dashboard'))


@analytics.route('/admin/export/full_backup')
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

        # 2. Subjects (with visibility flag)
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w_obj = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w_obj.writerow(['ID', 'Name', 'Slug', 'Description', 'Teacher_ID', 'Is_Public'])
        for subj in Subject.query.all():
            w_obj.writerow([subj.id, subj.name, subj.slug, subj.description, subj.teacher_id, subj.is_public])
        master_zip.writestr('2_subjects.csv', s_obj.getvalue())

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

        # 7. Exam Results (Anonymous Attempts)
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w_obj = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w_obj.writerow(['ID', 'Subject_ID', 'Score', 'Date_Submitted'])
        for res in ExamResult.query.all():
            w_obj.writerow([res.id, res.subject_id, res.score, res.date_submitted])
        master_zip.writestr('7_results.csv', s_obj.getvalue())

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

        # 11. ToolBase (Tools)
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w_obj = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w_obj.writerow(['ID', 'Title', 'Link', 'Description', 'Created_At'])
        for tool in Tool.query.all():
            w_obj.writerow([tool.id, tool.title, tool.link, tool.description, tool.created_at])
        master_zip.writestr('11_tools.csv', s_obj.getvalue())

    binary_stream.seek(0)
    current_time_str = datetime.now().strftime("%Y_%m_%d_%H%M")
    backup_file_name = f"StatInfo_FULL_BACKUP_{current_time_str}.zip"

    return Response(
        binary_stream.getvalue(),
        mimetype='application/zip',
        headers={"Content-Disposition": f"attachment;filename={backup_file_name}"}
    )


@analytics.route('/admin/system/restore', methods=['GET', 'POST'])
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
            flash(_('No file provided.'), 'danger')
            return redirect(request.url)

        try:
            # 1. READ ZIP (Keep in memory, but process contents as streams)
            zip_buffer = io.BytesIO(file.read())
            
            with zipfile.ZipFile(zip_buffer, 'r') as archive:
                file_list = archive.namelist()
                
                # Validation
                required_files = ['1_users.csv', '2_subjects.csv']
                if not all(f in file_list for f in required_files):
                    flash(_('Invalid Backup Format. Missing core CSV files.'), 'danger')
                    return redirect(request.url)

                # 2. SAFE WIPE (Delete rows in reverse dependency order)
                try:
                    db.session.query(AdminNotification).delete()
                    db.session.query(ExamResult).delete()
                    db.session.query(Question).delete()
                    db.session.query(Resource).delete()
                    db.session.query(Page).delete()
                    db.session.query(SubjectTeacher).delete()
                    db.session.query(Subject).delete()
                    db.session.query(SiteInfo).delete()
                    db.session.query(SystemCommand).delete()
                    db.session.query(Tool).delete()
                    db.session.commit()
                except Exception as wipe_err:
                    db.session.rollback()
                    flash(_('Pre-Restore Wipe Failed: %(error)s', error=str(wipe_err)), 'danger')
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

                # CONTENT SANITIZER - Fixes Windows line ending artifacts
                def sanitize_content(text):
                    """Removes rn/rnrn artifacts from HTML content."""
                    if not text:
                        return text
                    text = text.replace('rnrn', '\n').replace('rn', '\n')
                    text = text.replace('\r\n', '\n').replace('\r', '\n')
                    return text

                # A. Users (Upsert Logic to keep Admin alive)
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

                # B. Subjects (with visibility flag)
                for row in stream_csv('2_subjects.csv'):
                    is_public_val = True
                    if 'Is_Public' in row:
                        is_public_val = (row['Is_Public'] == 'True')
                    db.session.add(Subject(
                        id=int(row['ID']),
                        name=row['Name'],
                        slug=row['Slug'],
                        description=row['Description'],
                        teacher_id=int(row['Teacher_ID']),
                        is_public=is_public_val
                    ))
                db.session.commit()

                # D. Pages (with content sanitization to fix rn artifacts)
                batch = []
                for row in stream_csv('4_pages.csv'):
                    batch.append(Page(
                        id=int(row['ID']),
                        subject_id=int(row['Subject_ID']),
                        title=row['Title'],
                        content_body=sanitize_content(row['Content_EN']),
                        content_body_kurdish=sanitize_content(row['Content_KU'])
                    ))
                    if len(batch) >= 50:
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

                # F. Questions (with content sanitization)
                batch = []
                for row in stream_csv('6_questions.csv'):
                    pid = int(row['Page_ID']) if row['Page_ID'] else None
                    batch.append(Question(
                        id=int(row['ID']),
                        subject_id=int(row['Subject_ID']),
                        page_id=pid,
                        question_text=sanitize_content(row['Question_Text']),
                        option_a=sanitize_content(row['Option_A']),
                        option_b=sanitize_content(row['Option_B']),
                        option_c=sanitize_content(row['Option_C']),
                        option_d=sanitize_content(row['Option_D']),
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
                        content=sanitize_content(row['Content'])
                    ))
                
                db.session.commit()

                # K. Tools (ToolBase)
                for row in stream_csv('11_tools.csv'):
                    c_str = row['Created_At']
                    try:
                        c_obj = datetime.strptime(c_str, '%Y-%m-%d %H:%M:%S.%f')
                    except ValueError:
                        try:
                            c_obj = datetime.strptime(c_str, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            c_obj = datetime.utcnow()

                    db.session.add(Tool(
                        id=int(row['ID']),
                        title=row['Title'],
                        link=row['Link'],
                        description=row['Description'],
                        created_at=c_obj
                    ))
                
                db.session.commit()
                flash(_('SYSTEM RESTORE COMPLETED. Database re-hydrated successfully.'), 'success')
                return redirect(url_for('teacher.teacher_dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(_('CRITICAL RESTORE FAILURE: %(error)s', error=str(e)), 'danger')
            return redirect(request.url)

    return render_template('admin/restore_center.html', form=form)


@analytics.route('/admin/system/wipe_clean', methods=['POST'])
@login_required
def wipe_clean():
    """
    WIPE ALL DATA - Factory Reset.
    Deletes all data from the database, effectively resetting the system
    to a clean state. Redirects to the setup page to create a new admin.
    """
    if not current_user.is_admin:
        abort(403)

    form = WipeCleanForm()

    if form.validate_on_submit():
        try:
            # Delete all data in reverse dependency order
            db.session.query(AdminNotification).delete()
            db.session.query(ExamResult).delete()
            db.session.query(Question).delete()
            db.session.query(Resource).delete()
            db.session.query(Page).delete()
            db.session.query(SubjectTeacher).delete()
            db.session.query(Subject).delete()
            db.session.query(SiteInfo).delete()
            db.session.query(SystemCommand).delete()
            db.session.query(Tool).delete()
            db.session.query(User).delete()
            db.session.commit()

            flash(_('System wiped clean. Please create a new administrator account.'), 'warning')
            return redirect(url_for('public.setup'))

        except Exception as e:
            db.session.rollback()
            flash(_('CRITICAL WIPE FAILURE: %(error)s', error=str(e)), 'danger')
            return redirect(url_for('analytics.restore_system'))

    flash(_('Invalid form submission.'), 'danger')
    return redirect(url_for('analytics.restore_system'))


@analytics.route('/admin/edit/about', methods=['GET', 'POST'])
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
        info_record.content_kurdish = edit_form.content_kurdish.data
        db.session.commit()
        flash(_('Public Information Page Updated.'), 'success')
        return redirect(url_for('teacher.teacher_dashboard'))

    return render_template('admin/edit_about.html', form=edit_form)
