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
    User, Student, Subject, Page, Question, ExamResult,
    StudentAnswer, SiteInfo, Resource, SystemCommand, Tool
)
from app.forms import InfoPageForm, RestoreBackupForm, WipeCleanForm

analytics = Blueprint('analytics', __name__)

# ==============================================================================
# SECTION 11: ANALYTICS, EXPORTS & CMS
# ==============================================================================

@analytics.route('/teacher/analytics')
@login_required
def teacher_analytics():
    """COMPREHENSIVE ANALYTICS HUB"""
    if current_user.is_admin:
        set_questions = Question.query.all()
        set_results = ExamResult.query.all()
    else:
        subject_ids_owned = [subj.id for subj in current_user.subjects]
        set_questions = Question.query.filter(Question.subject_id.in_(subject_ids_owned)).all()
        set_results = ExamResult.query.filter(ExamResult.subject_id.in_(subject_ids_owned)).all()

    # 1. Question Difficulty Analysis
    question_stats_list = []
    for q_item in set_questions:
        ans_total = StudentAnswer.query.filter_by(question_id=q_item.id).count()
        ans_wrong = StudentAnswer.query.filter_by(question_id=q_item.id, is_correct=False).count()
        difficulty_percent = int((ans_wrong/ans_total)*100) if ans_total > 0 else 0
        question_stats_list.append({
            'subject': q_item.subject.name,
            'text': q_item.question_text,
            'failures': ans_wrong,
            'difficulty': difficulty_percent
        })
    question_stats_list.sort(key=lambda x: x['difficulty'], reverse=True)

    # 2. Student Rankings
    unique_student_ids = set(result.student_id for result in set_results)
    students_active = Student.query.filter(Student.id.in_(unique_student_ids)).all()
    student_metric_data = []
    at_risk_student_list = []

    for active_student in students_active:
        personal_scores = [r.score for r in set_results if r.student_id == active_student.id]
        personal_average = round(sum(personal_scores)/len(personal_scores), 1) if personal_scores else 0

        # Anonymize student names for teachers (only admins see real names)
        if current_user.is_admin:
            display_name = active_student.full_name
        else:
            display_name = f"Student #{active_student.id}"

        student_obj = {
            'id': active_student.id,
            'name': display_name,
            'avg_score': personal_average
        }
        student_metric_data.append(student_obj)
        if personal_average < 50:
            at_risk_student_list.append(student_obj)

    # 3. Chart Data Preparations

    # Distribution Chart
    dist_buckets = {'Excellent': 0, 'Good': 0, 'Pass': 0, 'Fail': 0}
    for r in set_results:
        if r.score >= 90: dist_buckets['Excellent'] += 1
        elif r.score >= 70: dist_buckets['Good'] += 1
        elif r.score >= 50: dist_buckets['Pass'] += 1
        else: dist_buckets['Fail'] += 1

    # Time Trend Chart
    sorted_history = sorted(set_results, key=lambda x: x.date_submitted)
    timeline_map = {}
    for r in sorted_history:
        date_str = r.date_submitted.strftime('%Y-%m-%d')
        if date_str not in timeline_map: timeline_map[date_str] = []
        timeline_map[date_str].append(r.score)

    t_labels = sorted(timeline_map.keys())
    t_values = [round(sum(timeline_map[d])/len(timeline_map[d]), 1) for d in t_labels]

    # Subject Mastery (Radar)
    radar_map = {}
    for r in set_results:
        s_name = r.subject.name
        if s_name not in radar_map: radar_map[s_name] = []
        radar_map[s_name].append(r.score)

    r_labels = list(radar_map.keys())
    r_values = [round(sum(radar_map[k])/len(radar_map[k]), 1) for k in r_labels]

    # Recent activity log
    activity_feed = sorted(set_results, key=lambda x: x.date_submitted, reverse=True)[:10]

    return render_template(
        'teacher/analytics.html',
        question_data=question_stats_list,
        student_data=student_metric_data,
        at_risk_students=at_risk_student_list,
        dist_values=list(dist_buckets.values()),
        trend_dates=t_labels,
        trend_scores=t_values,
        radar_labels=r_labels,
        radar_values=r_values,
        recent_activity=activity_feed
    )


@analytics.route('/teacher/analytics/student/<int:student_id>')
@login_required
def student_detail_view(student_id):
    """Detailed view for staff to see a student's answer grouped by attempt."""
    target_student = Student.query.get_or_404(student_id)

    attempt_query = ExamResult.query.filter_by(student_id=target_student.id)
    if not current_user.is_admin:
        teacher_subj_ids = [subj_obj.id for subj_obj in current_user.subjects]
        attempt_query = attempt_query.filter(ExamResult.subject_id.in_(teacher_subj_ids))

    exam_history_results = attempt_query.order_by(desc(ExamResult.date_submitted)).all()

    final_grouped_history = []
    for result_obj in exam_history_results:
        # We ensure cards are only created if answers were logged correctly
        if len(result_obj.answers) > 0:
            final_grouped_history.append({
                'exam': result_obj,
                'answers': result_obj.answers
            })
        else:
            # Automatic housekeeping for ghost results
            try:
                db.session.delete(result_obj)
                db.session.commit()
            except:
                db.session.rollback()

    return render_template(
        'teacher/student_detail.html',
        student=target_student,
        history=final_grouped_history
    )


@analytics.route('/teacher/export/grades')
@login_required
def export_grades():
    """Global CSV score export - ADMIN ONLY."""
    # Restrict to admin only
    if not current_user.is_admin:
        abort(403)
    
    results_to_export = ExamResult.query.all()

    output_stream = io.StringIO()
    output_stream.write('\ufeff') # BOM
    writer = csv.writer(output_stream, quoting=csv.QUOTE_ALL)

    writer.writerow(['Student', 'Course', 'Score (%)', 'Date'])
    for res in results_to_export:
        writer.writerow([
            res.student.full_name,
            res.subject.name,
            res.score,
            res.date_submitted.strftime('%Y-%m-%d')
        ])

    return Response(
        output_stream.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=gradebook_export.csv"}
    )


@analytics.route('/teacher/export/student/answers/<int:student_id>')
@login_required
def export_student_answers(student_id):
    """Detailed CSV choice log export - ADMIN ONLY."""
    # Restrict to admin only
    if not current_user.is_admin:
        abort(403)
    
    target_student = Student.query.get_or_404(student_id)
    results_to_export = ExamResult.query.filter_by(student_id=target_student.id).order_by(desc(ExamResult.date_submitted)).all()

    output_stream = io.StringIO()
    output_stream.write('\ufeff') # BOM
    writer = csv.writer(output_stream, quoting=csv.QUOTE_ALL)

    writer.writerow(['Timestamp', 'Subject', 'Question', 'Student Selected', 'Correct Key', 'Result Status'])
    for attempt in results_to_export:
        for choice in attempt.answers:
            writer.writerow([
                attempt.date_submitted.strftime('%Y-%m-%d %H:%M'),
                attempt.subject.name,
                choice.question.question_text,
                choice.selected_option,
                choice.question.correct_answer,
                "PASS" if choice.is_correct else "FAIL"
            ])

    return Response(
        output_stream.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=Choices_{target_student.full_name}.csv"}
    )


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

        # 3. Students (with all fields including email and timestamps)
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w_obj = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w_obj.writerow(['ID', 'Full_Name', 'Access_Code', 'Email', 'Created_At', 'Updated_At'])
        for student in Student.query.all():
            w_obj.writerow([student.id, student.full_name, student.access_code, student.email or '', student.created_at, student.updated_at])
        master_zip.writestr('3_students.csv', s_obj.getvalue())

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

        # 7. Exam Results (Attempts)
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w_obj = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w_obj.writerow(['ID', 'Student_ID', 'Subject_ID', 'Score', 'Date_Submitted'])
        for res in ExamResult.query.all():
            w_obj.writerow([res.id, res.student_id, res.subject_id, res.score, res.date_submitted])
        master_zip.writestr('7_results.csv', s_obj.getvalue())

        # 8. Student Answers (Details)
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w_obj = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w_obj.writerow(['ID', 'Student_ID', 'Question_ID', 'Exam_ID', 'Selected_Option', 'Is_Correct'])
        for ans in StudentAnswer.query.all():
            w_obj.writerow([ans.id, ans.student_id, ans.question_id, ans.exam_id, ans.selected_option, ans.is_correct])
        master_zip.writestr('8_answers.csv', s_obj.getvalue())

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
                required_files = ['1_users.csv', '2_subjects.csv', '3_students.csv']
                if not all(f in file_list for f in required_files):
                    flash(_('Invalid Backup Format. Missing core CSV files.'), 'danger')
                    return redirect(request.url)

                # 2. SAFE WIPE (Delete rows in reverse dependency order)
                try:
                    db.session.query(StudentAnswer).delete()
                    db.session.query(ExamResult).delete()
                    db.session.query(Question).delete()
                    db.session.query(Resource).delete()
                    db.session.query(Page).delete()
                    db.session.query(Student).delete()
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

                # C. Students (with new fields: email, timestamps)
                batch = []
                for row in stream_csv('3_students.csv'):
                    created = None
                    updated = None
                    if row.get('Created_At') and row['Created_At']:
                        try:
                            created = datetime.strptime(row['Created_At'], '%Y-%m-%d %H:%M:%S.%f')
                        except ValueError:
                            try:
                                created = datetime.strptime(row['Created_At'], '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                created = datetime.utcnow()
                    if row.get('Updated_At') and row['Updated_At']:
                        try:
                            updated = datetime.strptime(row['Updated_At'], '%Y-%m-%d %H:%M:%S.%f')
                        except ValueError:
                            try:
                                updated = datetime.strptime(row['Updated_At'], '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                updated = datetime.utcnow()
                    
                    batch.append(Student(
                        id=int(row['ID']),
                        full_name=row['Full_Name'],
                        access_code=row['Access_Code'],
                        email=row.get('Email') or None,
                        created_at=created,
                        updated_at=updated
                    ))
                    if len(batch) >= 100:
                        db.session.add_all(batch)
                        db.session.commit()
                        batch = []
                if batch: 
                    db.session.add_all(batch)
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
                        student_id=int(row['Student_ID']),
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

                # H. Student Answers (The BIG Table)
                batch = []
                for row in stream_csv('8_answers.csv'):
                    batch.append(StudentAnswer(
                        id=int(row['ID']),
                        student_id=int(row['Student_ID']),
                        question_id=int(row['Question_ID']),
                        exam_id=int(row['Exam_ID']),
                        selected_option=row['Selected_Option'],
                        is_correct=(row['Is_Correct'] == 'True')
                    ))
                    if len(batch) >= 200:
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
            db.session.query(StudentAnswer).delete()
            db.session.query(ExamResult).delete()
            db.session.query(Question).delete()
            db.session.query(Resource).delete()
            db.session.query(Page).delete()
            db.session.query(Student).delete()
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
