import csv
import io
import zipfile
from datetime import datetime
from flask import Blueprint, render_template, url_for, flash, redirect, request, abort, Response
from flask_babel import gettext as _, get_locale
from flask_login import login_required, current_user
from sqlalchemy import desc

from app import db
from app.models import (
    User, Subject, Page, Question, ExamResult,
    SiteInfo, Resource, SystemCommand, Tool,
    SubjectTeacher, AdminNotification, PageComment, TeacherNotification,
    Student, StudentTeacher, TeacherRequest
)
from app.forms import InfoPageForm, RestoreBackupForm, WipeCleanForm

analytics = Blueprint('analytics', __name__)


def _parse_date(val):
    if not val:
        return None
    for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(val.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_dt(val, default_now=False):
    if not val:
        return datetime.utcnow() if default_now else None
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(val.strip(), fmt)
        except ValueError:
            continue
    return datetime.utcnow() if default_now else None


def _compute_stats_payload(results_list, subjects_list, lang):
    """Build aggregated KPIs, chart datasets, gender & age breakdowns from ExamResult rows."""
    total_attempts = len(results_list)
    avg_score = round(sum(r.score for r in results_list) / total_attempts, 1) if total_attempts else 0
    pass_count = sum(1 for r in results_list if r.score >= 50)
    fail_count = total_attempts - pass_count
    final_count = sum(1 for r in results_list if r.page_id is None)
    quiz_count = total_attempts - final_count

    # Per-subject aggregation
    subj_buckets = {s.id: [] for s in subjects_list}
    for r in results_list:
        if r.subject_id in subj_buckets:
            subj_buckets[r.subject_id].append(r.score)

    chart_labels = []
    chart_values = []
    for s in subjects_list:
        scores = subj_buckets.get(s.id, [])
        if scores:
            chart_labels.append(s.display_name(lang))
            chart_values.append(round(sum(scores) / len(scores), 1))

    # Gender & Age breakdowns
    gender_counts = {'male': 0, 'female': 0, 'unknown': 0}
    age_groups = {'<18': 0, '18-22': 0, '23-30': 0, '30+': 0, 'unknown': 0}
    for r in results_list:
        g = (r.resolved_gender or '').lower()
        if g in ('male', 'female'):
            gender_counts[g] += 1
        else:
            gender_counts['unknown'] += 1

        age = r.taker_age
        if age is None:
            age_groups['unknown'] += 1
        elif age < 18:
            age_groups['<18'] += 1
        elif age <= 22:
            age_groups['18-22'] += 1
        elif age <= 30:
            age_groups['23-30'] += 1
        else:
            age_groups['30+'] += 1

    return {
        'total_attempts': total_attempts,
        'avg_score': avg_score,
        'pass_count': pass_count,
        'fail_count': fail_count,
        'final_count': final_count,
        'quiz_count': quiz_count,
        'chart_labels': chart_labels,
        'chart_values': chart_values,
        'gender_counts': gender_counts,
        'age_groups': age_groups,
    }


def _student_stats_rows(students_list, results_list):
    """Aggregate attempts and average scores per Student record."""
    by_sid = {}
    for r in results_list:
        if r.student_record_id:
            by_sid.setdefault(r.student_record_id, []).append(r)

    rows = []
    for stu in students_list:
        stu_res = by_sid.get(stu.id, [])
        attempts = len(stu_res)
        avg = round(sum(r.score for r in stu_res) / attempts, 1) if attempts else None
        rows.append({
            'student': stu,
            'attempts': attempts,
            'avg_score': avg,
            'last_date': stu_res[0].date_submitted if stu_res else None
        })
    return rows


# ==============================================================================
# SECTION 11: TEACHER & ADMIN STATISTICS PAGES (v0.9.0)
# ==============================================================================

@analytics.route('/teacher/analytics')
@login_required
def teacher_analytics():
    """Redirect legacy analytics route to the new Teacher Statistics page."""
    return redirect(url_for('analytics.teacher_stats'))


@analytics.route('/teacher/stats')
@login_required
def teacher_stats():
    """
    TEACHER-SCOPED STATISTICS PAGE (View-Only Subject Picker)
    Shows only the logged-in teacher's assigned subjects and their linked students.
    """
    lang = get_locale().language
    assignments = SubjectTeacher.query.filter_by(teacher_id=current_user.id).all()
    teacher_subjects = [a.subject for a in assignments if a.subject]
    allowed_ids = [s.id for s in teacher_subjects]

    selected_ids = [sid for sid in request.args.getlist('subjects', type=int) if sid in allowed_ids]
    active_ids = selected_ids if selected_ids else allowed_ids
    active_subjects = [s for s in teacher_subjects if s.id in active_ids]

    if active_ids:
        results = ExamResult.query.filter(
            ExamResult.subject_id.in_(active_ids)
        ).order_by(ExamResult.date_submitted.desc()).all()
    else:
        results = []

    my_students = Student.query.join(StudentTeacher).filter(
        StudentTeacher.teacher_id == current_user.id
    ).order_by(Student.name_en.asc()).all()

    payload = _compute_stats_payload(results, active_subjects, lang)
    student_rows = _student_stats_rows(my_students, results)

    return render_template(
        'teacher/stats.html',
        all_subjects=teacher_subjects,
        selected_ids=active_ids,
        results=results,
        student_rows=student_rows,
        **payload
    )


def _filtered_admin_results_and_context():
    lang = get_locale().language
    all_subjects = Subject.query.order_by(Subject.name.asc()).all()
    all_teachers = User.query.order_by(User.username.asc()).all()

    selected_ids = [sid for sid in request.args.getlist('subjects', type=int)]
    valid_sids = {s.id for s in all_subjects}
    selected_ids = [sid for sid in selected_ids if sid in valid_sids]

    teacher_id = request.args.get('teacher_id', type=int)
    gender_filter = (request.args.get('gender') or 'all').strip().lower()
    taker_type = (request.args.get('taker_type') or 'all').strip().lower()
    exam_type = (request.args.get('exam_type') or 'all').strip().lower()
    dept_filter = (request.args.get('department') or '').strip().lower()

    active_subjects = [s for s in all_subjects if s.id in selected_ids] if selected_ids else list(all_subjects)
    if teacher_id:
        t_sub_ids = {st.subject_id for st in SubjectTeacher.query.filter_by(teacher_id=teacher_id).all()}
        active_subjects = [s for s in active_subjects if s.id in t_sub_ids or s.teacher_id == teacher_id]

    active_ids = [s.id for s in active_subjects]
    query = ExamResult.query
    if active_ids:
        query = query.filter(ExamResult.subject_id.in_(active_ids))
    else:
        query = query.filter(db.literal(False))

    if exam_type == 'final':
        query = query.filter(ExamResult.page_id.is_(None))
    elif exam_type == 'quiz':
        query = query.filter(ExamResult.page_id.isnot(None))

    if taker_type == 'student':
        query = query.filter(ExamResult.student_record_id.isnot(None))
    elif taker_type == 'guest':
        query = query.filter(ExamResult.student_record_id.is_(None))

    raw_results = query.order_by(ExamResult.date_submitted.desc()).all()

    # Apply resolved demographic & department filters cleanly
    filtered_results = []
    for r in raw_results:
        if gender_filter in ('male', 'female') and (r.resolved_gender or '').lower() != gender_filter:
            continue
        if dept_filter:
            if not r.student_record:
                continue
            d_en = (r.student_record.department_en or '').lower()
            d_ku = (r.student_record.department_ku or '').lower()
            if dept_filter not in d_en and dept_filter not in d_ku:
                continue
        filtered_results.append(r)

    all_students = Student.query.order_by(Student.name_en.asc()).all()
    if dept_filter:
        all_students = [
            s for s in all_students
            if dept_filter in (s.department_en or '').lower() or dept_filter in (s.department_ku or '').lower()
        ]
    if gender_filter in ('male', 'female'):
        all_students = [s for s in all_students if (s.gender or '').lower() == gender_filter]

    payload = _compute_stats_payload(filtered_results, active_subjects, lang)
    student_rows = _student_stats_rows(all_students, filtered_results)

    # Department averages across student attempts
    dept_buckets = {}
    for r in filtered_results:
        if r.student_record:
            d_name = r.student_record.display_department(lang)
            dept_buckets.setdefault(d_name, []).append(r.score)
    dept_stats = [
        {'name': d, 'attempts': len(scores), 'avg': round(sum(scores) / len(scores), 1)}
        for d, scores in sorted(dept_buckets.items())
    ]

    return {
        'all_subjects': all_subjects,
        'all_teachers': all_teachers,
        'selected_ids': active_ids if selected_ids else [s.id for s in all_subjects],
        'teacher_id': teacher_id,
        'gender_filter': gender_filter,
        'taker_type': taker_type,
        'exam_type': exam_type,
        'department_filter': request.args.get('department', ''),
        'results': filtered_results,
        'student_rows': student_rows,
        'dept_stats': dept_stats,
        **payload
    }


@analytics.route('/admin/stats')
@login_required
def admin_stats():
    """ADMIN FULL GRANULAR STATISTICS PAGE."""
    if not current_user.is_admin:
        abort(403)
    ctx = _filtered_admin_results_and_context()
    return render_template('admin/stats.html', **ctx)


@analytics.route('/admin/stats/export')
@login_required
def export_admin_stats():
    """Export filtered Admin statistics attempt log as UTF-8 BOM CSV."""
    if not current_user.is_admin:
        abort(403)
    ctx = _filtered_admin_results_and_context()
    s_obj = io.StringIO()
    s_obj.write('\ufeff')
    w = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
    w.writerow([
        'Attempt_ID', 'Date_Submitted', 'Subject', 'Exam_Type', 'Lecture_Title',
        'Taker_Type', 'Student_Code', 'Name_EN', 'Name_KU', 'Department_EN',
        'Department_KU', 'Gender', 'Birth_Date', 'Age', 'Correct', 'Total', 'Score_Percent'
    ])
    for r in ctx['results']:
        stu = r.student_record
        w.writerow([
            r.id,
            r.date_submitted.strftime('%Y-%m-%d %H:%M:%S'),
            r.subject.name if r.subject else '',
            'Lecture Quiz' if r.page_id else 'Final Exam',
            r.page.title if r.page else '',
            'Student' if stu else 'Guest',
            stu.student_code if stu else '',
            stu.name_en if stu else (r.taker_name or 'Anonymous'),
            stu.name_ku if stu else '',
            stu.department_en if stu else '',
            stu.department_ku if stu else '',
            r.resolved_gender or '',
            (stu.birth_date if stu else r.taker_birth_date) or '',
            r.taker_age if r.taker_age is not None else '',
            r.correct_count if r.correct_count is not None else '',
            r.total_questions if r.total_questions is not None else '',
            r.score
        ])
    ts = datetime.now().strftime('%Y_%m_%d_%H%M')
    return Response(
        s_obj.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=StatInfo_Stats_{ts}.csv'}
    )


# ==============================================================================
# ZERO-LOSS FULL SYSTEM BACKUP & RESTORE (ALL 14 TABLES / 16 CSV FILES)
# ==============================================================================

@analytics.route('/admin/export/full_backup')
@login_required
def export_full_backup():
    """
    GENERATES COMPLETE ZERO-LOSS ZIP SYSTEM BACKUP.
    Exports every single table and every single column so nothing is lost on restore.
    """
    if not current_user.is_admin:
        abort(403)

    binary_stream = io.BytesIO()

    def write_csv(filename, headers, rows):
        s_obj = io.StringIO()
        s_obj.write('\ufeff')
        w = csv.writer(s_obj, quoting=csv.QUOTE_ALL)
        w.writerow(headers)
        for r in rows:
            w.writerow(r)
        master_zip.writestr(filename, s_obj.getvalue())

    with zipfile.ZipFile(binary_stream, 'w', zipfile.ZIP_DEFLATED) as master_zip:
        # 1. Users
        write_csv(
            '1_users.csv',
            ['ID', 'Name', 'Name_KU', 'Email', 'Password_Hash', 'Gender', 'Birth_Date', 'Bio',
             'Is_Admin', 'Show_Name_On_Subject', 'Preferred_Lang'],
            [[u.id, u.username, u.username_kurdish or '', u.email, u.password_hash,
              u.gender or '', u.birth_date.isoformat() if u.birth_date else '',
              u.bio or '', u.is_admin, u.show_name_on_subject, u.preferred_lang or 'en']
             for u in User.query.order_by(User.id.asc()).all()]
        )

        # 2. Subjects
        write_csv(
            '2_subjects.csv',
            ['ID', 'Name', 'Name_KU', 'Slug', 'Description', 'Description_KU',
             'Teacher_ID', 'Is_Public', 'Exam_Student_Only'],
            [[s.id, s.name, s.name_kurdish or '', s.slug, s.description or '',
              s.description_kurdish or '', s.teacher_id, s.is_public, bool(s.exam_student_only)]
             for s in Subject.query.order_by(Subject.id.asc()).all()]
        )

        # 3. SubjectTeacher
        write_csv(
            '3_subject_teachers.csv',
            ['ID', 'Subject_ID', 'Teacher_ID', 'Is_Primary', 'Show_Name', 'Added_At'],
            [[st.id, st.subject_id, st.teacher_id, st.is_primary, st.show_name,
              st.added_at.isoformat(sep=' ') if st.added_at else '']
             for st in SubjectTeacher.query.order_by(SubjectTeacher.id.asc()).all()]
        )

        # 4. Pages (Lectures)
        write_csv(
            '4_pages.csv',
            ['ID', 'Subject_ID', 'Title', 'Title_KU', 'Content_EN', 'Content_KU', 'Quiz_Student_Only'],
            [[p.id, p.subject_id, p.title, p.title_kurdish or '', p.content_body,
              p.content_body_kurdish or '', bool(p.quiz_student_only)]
             for p in Page.query.order_by(Page.id.asc()).all()]
        )

        # 5. Resources
        write_csv(
            '5_resources.csv',
            ['ID', 'Page_ID', 'Title', 'Title_KU', 'Link'],
            [[r.id, r.page_id, r.title, r.title_kurdish or '', r.link]
             for r in Resource.query.order_by(Resource.id.asc()).all()]
        )

        # 6. Questions (Dual EN & KU faces)
        write_csv(
            '6_questions.csv',
            ['ID', 'Subject_ID', 'Page_ID', 'Question_Text', 'Question_Text_KU',
             'Option_A', 'Option_B', 'Option_C', 'Option_D',
             'Option_A_KU', 'Option_B_KU', 'Option_C_KU', 'Option_D_KU',
             'Correct', 'Is_Kurdish'],
            [[q.id, q.subject_id, q.page_id if q.page_id else '',
              q.question_text, q.question_text_kurdish or '',
              q.option_a, q.option_b, q.option_c, q.option_d,
              q.option_a_kurdish or '', q.option_b_kurdish or '',
              q.option_c_kurdish or '', q.option_d_kurdish or '',
              q.correct_answer, q.is_kurdish]
             for q in Question.query.order_by(Question.id.asc()).all()]
        )

        # 7. ExamResults
        write_csv(
            '7_results.csv',
            ['ID', 'Subject_ID', 'Page_ID', 'Student_Record_ID', 'Score',
             'Correct_Count', 'Total_Questions', 'Taker_Name', 'Taker_Birth_Date',
             'Taker_Gender', 'Date_Submitted'],
            [[r.id, r.subject_id, r.page_id if r.page_id else '',
              r.student_record_id if r.student_record_id else '', r.score,
              r.correct_count if r.correct_count is not None else '',
              r.total_questions if r.total_questions is not None else '',
              r.taker_name or '',
              r.taker_birth_date.isoformat() if r.taker_birth_date else '',
              r.taker_gender or '',
              r.date_submitted.isoformat(sep=' ') if r.date_submitted else '']
             for r in ExamResult.query.order_by(ExamResult.id.asc()).all()]
        )

        # 8. Students
        write_csv(
            '8_students.csv',
            ['ID', 'Name_EN', 'Name_KU', 'Birth_Date', 'Gender', 'Department_EN',
             'Department_KU', 'Student_Code', 'Created_By_ID', 'Created_At'],
            [[s.id, s.name_en, s.name_ku, s.birth_date.isoformat(), s.gender,
              s.department_en, s.department_ku, s.student_code,
              s.created_by_id if s.created_by_id else '',
              s.created_at.isoformat(sep=' ') if s.created_at else '']
             for s in Student.query.order_by(Student.id.asc()).all()]
        )

        # 9. SystemCommands
        write_csv(
            '9_commands.csv',
            ['ID', 'Title', 'Title_KU', 'Command', 'Description', 'Description_KU'],
            [[c.id, c.title, c.title_kurdish or '', c.command_text,
              c.description or '', c.description_kurdish or '']
             for c in SystemCommand.query.order_by(SystemCommand.id.asc()).all()]
        )

        # 10. SiteInfo
        write_csv(
            '10_siteinfo.csv',
            ['ID', 'Key', 'Title', 'Title_KU', 'Content', 'Content_KU', 'Last_Updated'],
            [[i.id, i.key, i.title, i.title_kurdish or '', i.content or '',
              i.content_kurdish or '', i.last_updated.isoformat(sep=' ') if i.last_updated else '']
             for i in SiteInfo.query.order_by(SiteInfo.id.asc()).all()]
        )

        # 11. Tools
        write_csv(
            '11_tools.csv',
            ['ID', 'Title', 'Title_KU', 'Link', 'Description', 'Description_KU', 'Created_At'],
            [[t.id, t.title, t.title_kurdish or '', t.link, t.description or '',
              t.description_kurdish or '', t.created_at.isoformat(sep=' ') if t.created_at else '']
             for t in Tool.query.order_by(Tool.id.asc()).all()]
        )

        # 12. PageComments (Parents first, then replies)
        parents = PageComment.query.filter(PageComment.parent_id.is_(None)).order_by(PageComment.id.asc()).all()
        replies = PageComment.query.filter(PageComment.parent_id.isnot(None)).order_by(PageComment.id.asc()).all()
        write_csv(
            '12_comments.csv',
            ['ID', 'Page_ID', 'Parent_ID', 'Author_User_ID', 'Is_Teacher_Reply',
             'Is_Read_By_Admin', 'Author_Name', 'Author_Birth_Date', 'Author_Age',
             'Personality_Info', 'Comment_Text', 'Created_At'],
            [[c.id, c.page_id, c.parent_id if c.parent_id else '',
              c.author_user_id if c.author_user_id else '',
              bool(c.is_teacher_reply), bool(c.is_read_by_admin),
              c.author_name,
              c.author_birth_date.isoformat() if c.author_birth_date else '',
              c.author_age if c.author_age is not None else '',
              c.personality_info or '', c.comment_text,
              c.created_at.isoformat(sep=' ') if c.created_at else '']
             for c in (parents + replies)]
        )

        # 13. StudentTeacher
        write_csv(
            '13_student_teachers.csv',
            ['ID', 'Student_ID', 'Teacher_ID', 'Assigned_At'],
            [[st.id, st.student_id, st.teacher_id,
              st.assigned_at.isoformat(sep=' ') if st.assigned_at else '']
             for st in StudentTeacher.query.order_by(StudentTeacher.id.asc()).all()]
        )

        # 14. TeacherRequest
        write_csv(
            '14_teacher_requests.csv',
            ['ID', 'Name_EN', 'Name_KU', 'Email', 'Password_Hash', 'Gender',
             'Birth_Date', 'Bio', 'Reason', 'Status', 'Reviewed_By_ID',
             'Reviewed_At', 'Admin_Note', 'Created_At'],
            [[tr.id, tr.name_en, tr.name_ku, tr.email, tr.password_hash, tr.gender,
              tr.birth_date.isoformat(), tr.bio or '', tr.reason, tr.status,
              tr.reviewed_by_id if tr.reviewed_by_id else '',
              tr.reviewed_at.isoformat(sep=' ') if tr.reviewed_at else '',
              tr.admin_note or '',
              tr.created_at.isoformat(sep=' ') if tr.created_at else '']
             for tr in TeacherRequest.query.order_by(TeacherRequest.id.asc()).all()]
        )

        # 15. AdminNotification
        write_csv(
            '15_admin_notifications.csv',
            ['ID', 'Notification_Type', 'Title', 'Message', 'Actor_Type', 'Actor_ID',
             'Actor_Name', 'Related_Subject_ID', 'Related_Page_ID', 'Related_Question_ID',
             'Is_Checked', 'Checked_At', 'Created_At'],
            [[an.id, an.notification_type, an.title, an.message, an.actor_type or '',
              an.actor_id if an.actor_id is not None else '', an.actor_name or '',
              an.related_subject_id if an.related_subject_id else '',
              an.related_page_id if an.related_page_id else '',
              an.related_question_id if an.related_question_id else '',
              bool(an.is_checked),
              an.checked_at.isoformat(sep=' ') if an.checked_at else '',
              an.created_at.isoformat(sep=' ') if an.created_at else '']
             for an in AdminNotification.query.order_by(AdminNotification.id.asc()).all()]
        )

        # 16. TeacherNotification
        write_csv(
            '16_teacher_notifications.csv',
            ['ID', 'Teacher_ID', 'Sender_ID', 'Notification_Type', 'Title', 'Message',
             'Related_Subject_ID', 'Related_Page_ID', 'Is_Read', 'Created_At'],
            [[tn.id, tn.teacher_id, tn.sender_id if tn.sender_id else '',
              tn.notification_type, tn.title, tn.message,
              tn.related_subject_id if tn.related_subject_id else '',
              tn.related_page_id if tn.related_page_id else '',
              bool(tn.is_read),
              tn.created_at.isoformat(sep=' ') if tn.created_at else '']
             for tn in TeacherNotification.query.order_by(TeacherNotification.id.asc()).all()]
        )

    binary_stream.seek(0)
    current_time_str = datetime.now().strftime("%Y_%m_%d_%H%M")
    backup_file_name = f"StatInfo_FULL_BACKUP_{current_time_str}.zip"

    return Response(
        binary_stream.getvalue(),
        mimetype='application/zip',
        headers={"Content-Disposition": f"attachment;filename={backup_file_name}"}
    )


def _wipe_all_non_user_tables():
    """Delete all domain tables in strict InnoDB bottom-up foreign-key order."""
    db.session.query(TeacherNotification).delete()
    db.session.query(AdminNotification).delete()
    PageComment.query.filter(PageComment.parent_id.isnot(None)).delete(synchronize_session=False)
    db.session.query(PageComment).delete()
    db.session.query(ExamResult).delete()
    db.session.query(Question).delete()
    db.session.query(Resource).delete()
    db.session.query(Page).delete()
    db.session.query(StudentTeacher).delete()
    db.session.query(Student).delete()
    db.session.query(SubjectTeacher).delete()
    db.session.query(Subject).delete()
    db.session.query(TeacherRequest).delete()
    db.session.query(SiteInfo).delete()
    db.session.query(SystemCommand).delete()
    db.session.query(Tool).delete()


@analytics.route('/admin/system/restore', methods=['GET', 'POST'])
@login_required
def restore_system():
    """
    FULL ZERO-LOSS SYSTEM RESTORE ROUTE.
    Wipes DB in strict bottom-up FK order and re-hydrates all tables in top-down order.
    Backwards compatible with older v0.6-v0.8 backups while preserving 100% of v0.9.0 data.
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
            zip_buffer = io.BytesIO(file.read())

            with zipfile.ZipFile(zip_buffer, 'r') as archive:
                file_list = archive.namelist()
                required_files = ['1_users.csv', '2_subjects.csv']
                if not all(f in file_list for f in required_files):
                    flash(_('Invalid Backup Format. Missing core CSV files.'), 'danger')
                    return redirect(request.url)

                # 1. Wipe existing domain tables bottom-up
                try:
                    _wipe_all_non_user_tables()
                    db.session.commit()
                except Exception as wipe_err:
                    db.session.rollback()
                    flash(_('Pre-Restore Wipe Failed: %(error)s', error=str(wipe_err)), 'danger')
                    return redirect(request.url)

                def stream_csv(filename):
                    if filename not in file_list:
                        return
                    with archive.open(filename) as f:
                        text = io.TextIOWrapper(f, encoding='utf-8-sig', newline='')
                        reader = csv.DictReader(text)
                        for row in reader:
                            yield row

                def clean_newlines(text):
                    if not text:
                        return text
                    return text.replace('\r\n', '\n').replace('\r', '\n')

                # A. Users (Upsert + remove stale users not in backup)
                restored_uids = set()
                for row in stream_csv('1_users.csv'):
                    uid = int(row['ID'])
                    restored_uids.add(uid)
                    existing = User.query.get(uid)
                    target = existing if existing else User(id=uid)
                    target.username = row['Name']
                    target.username_kurdish = row.get('Name_KU') or None
                    target.email = row['Email']
                    target.password_hash = row['Password_Hash']
                    target.gender = row.get('Gender') or None
                    target.birth_date = _parse_date(row.get('Birth_Date', ''))
                    target.bio = row.get('Bio') or None
                    target.is_admin = (row.get('Is_Admin') == 'True')
                    target.show_name_on_subject = (row.get('Show_Name_On_Subject') == 'True')
                    target.preferred_lang = row.get('Preferred_Lang') or 'en'
                    if not existing:
                        db.session.add(target)
                db.session.commit()

                if restored_uids:
                    User.query.filter(~User.id.in_(restored_uids)).delete(synchronize_session=False)
                    db.session.commit()

                # B. TeacherRequests
                for row in stream_csv('14_teacher_requests.csv'):
                    db.session.add(TeacherRequest(
                        id=int(row['ID']),
                        name_en=row['Name_EN'],
                        name_ku=row['Name_KU'],
                        email=row['Email'],
                        password_hash=row['Password_Hash'],
                        gender=row['Gender'],
                        birth_date=_parse_date(row['Birth_Date']),
                        bio=row.get('Bio') or None,
                        reason=row['Reason'],
                        status=row.get('Status') or 'pending',
                        reviewed_by_id=int(row['Reviewed_By_ID']) if row.get('Reviewed_By_ID') else None,
                        reviewed_at=_parse_dt(row.get('Reviewed_At', '')),
                        admin_note=row.get('Admin_Note') or None,
                        created_at=_parse_dt(row.get('Created_At', ''), default_now=True)
                    ))
                db.session.commit()

                # C. Subjects
                for row in stream_csv('2_subjects.csv'):
                    db.session.add(Subject(
                        id=int(row['ID']),
                        name=row['Name'],
                        name_kurdish=row.get('Name_KU') or None,
                        slug=row['Slug'],
                        description=clean_newlines(row.get('Description', '')),
                        description_kurdish=clean_newlines(row.get('Description_KU', '')) or None,
                        teacher_id=int(row['Teacher_ID']),
                        is_public=(row.get('Is_Public', 'True') == 'True'),
                        exam_student_only=(row.get('Exam_Student_Only', 'False') == 'True')
                    ))
                db.session.commit()

                # D. SubjectTeachers (or auto-reconstruct from Subject.teacher_id on older backups)
                if '3_subject_teachers.csv' in file_list:
                    for row in stream_csv('3_subject_teachers.csv'):
                        db.session.add(SubjectTeacher(
                            id=int(row['ID']),
                            subject_id=int(row['Subject_ID']),
                            teacher_id=int(row['Teacher_ID']),
                            is_primary=(row.get('Is_Primary') == 'True'),
                            show_name=(row.get('Show_Name', 'True') == 'True'),
                            added_at=_parse_dt(row.get('Added_At', ''), default_now=True)
                        ))
                else:
                    for subj in Subject.query.all():
                        db.session.add(SubjectTeacher(
                            subject_id=subj.id,
                            teacher_id=subj.teacher_id,
                            is_primary=True,
                            show_name=bool(subj.teacher.show_name_on_subject) if subj.teacher else True
                        ))
                db.session.commit()

                # E. Students
                for row in stream_csv('8_students.csv'):
                    db.session.add(Student(
                        id=int(row['ID']),
                        name_en=row['Name_EN'],
                        name_ku=row['Name_KU'],
                        birth_date=_parse_date(row['Birth_Date']),
                        gender=row['Gender'],
                        department_en=row['Department_EN'],
                        department_ku=row['Department_KU'],
                        student_code=row['Student_Code'],
                        created_by_id=int(row['Created_By_ID']) if row.get('Created_By_ID') else None,
                        created_at=_parse_dt(row.get('Created_At', ''), default_now=True)
                    ))
                db.session.commit()

                # F. StudentTeachers
                for row in stream_csv('13_student_teachers.csv'):
                    db.session.add(StudentTeacher(
                        id=int(row['ID']),
                        student_id=int(row['Student_ID']),
                        teacher_id=int(row['Teacher_ID']),
                        assigned_at=_parse_dt(row.get('Assigned_At', ''), default_now=True)
                    ))
                db.session.commit()

                # G. Pages (Lectures)
                batch = []
                for row in stream_csv('4_pages.csv'):
                    batch.append(Page(
                        id=int(row['ID']),
                        subject_id=int(row['Subject_ID']),
                        title=row['Title'],
                        title_kurdish=row.get('Title_KU') or None,
                        content_body=clean_newlines(row['Content_EN']),
                        content_body_kurdish=clean_newlines(row.get('Content_KU', '')) or None,
                        quiz_student_only=(row.get('Quiz_Student_Only', 'False') == 'True')
                    ))
                    if len(batch) >= 50:
                        db.session.add_all(batch)
                        db.session.commit()
                        batch = []
                if batch:
                    db.session.add_all(batch)
                    db.session.commit()

                # H. Resources
                for row in stream_csv('5_resources.csv'):
                    db.session.add(Resource(
                        id=int(row['ID']),
                        page_id=int(row['Page_ID']),
                        title=row['Title'],
                        title_kurdish=row.get('Title_KU') or None,
                        link=row['Link']
                    ))
                db.session.commit()

                # I. Questions
                batch = []
                for row in stream_csv('6_questions.csv'):
                    pid = int(row['Page_ID']) if row.get('Page_ID') else None
                    batch.append(Question(
                        id=int(row['ID']),
                        subject_id=int(row['Subject_ID']),
                        page_id=pid,
                        question_text=clean_newlines(row['Question_Text']),
                        question_text_kurdish=clean_newlines(row.get('Question_Text_KU', '')) or None,
                        option_a=clean_newlines(row['Option_A']),
                        option_b=clean_newlines(row['Option_B']),
                        option_c=clean_newlines(row['Option_C']),
                        option_d=clean_newlines(row['Option_D']),
                        option_a_kurdish=clean_newlines(row.get('Option_A_KU', '')) or None,
                        option_b_kurdish=clean_newlines(row.get('Option_B_KU', '')) or None,
                        option_c_kurdish=clean_newlines(row.get('Option_C_KU', '')) or None,
                        option_d_kurdish=clean_newlines(row.get('Option_D_KU', '')) or None,
                        correct_answer=row['Correct'],
                        is_kurdish=(row.get('Is_Kurdish') == 'True')
                    ))
                    if len(batch) >= 100:
                        db.session.add_all(batch)
                        db.session.commit()
                        batch = []
                if batch:
                    db.session.add_all(batch)
                    db.session.commit()

                # J. ExamResults
                batch = []
                for row in stream_csv('7_results.csv'):
                    batch.append(ExamResult(
                        id=int(row['ID']),
                        subject_id=int(row['Subject_ID']),
                        page_id=int(row['Page_ID']) if row.get('Page_ID') else None,
                        student_record_id=int(row['Student_Record_ID']) if row.get('Student_Record_ID') else None,
                        score=int(row['Score']),
                        correct_count=int(row['Correct_Count']) if row.get('Correct_Count') else None,
                        total_questions=int(row['Total_Questions']) if row.get('Total_Questions') else None,
                        taker_name=row.get('Taker_Name') or None,
                        taker_birth_date=_parse_date(row.get('Taker_Birth_Date', '')),
                        taker_gender=row.get('Taker_Gender') or None,
                        date_submitted=_parse_dt(row.get('Date_Submitted', ''), default_now=True)
                    ))
                    if len(batch) >= 100:
                        db.session.add_all(batch)
                        db.session.commit()
                        batch = []
                if batch:
                    db.session.add_all(batch)
                    db.session.commit()

                # K. PageComments (Top-level parents first, then replies)
                reply_rows = []
                for row in stream_csv('12_comments.csv'):
                    if row.get('Parent_ID'):
                        reply_rows.append(row)
                        continue
                    db.session.add(PageComment(
                        id=int(row['ID']),
                        page_id=int(row['Page_ID']),
                        parent_id=None,
                        author_user_id=int(row['Author_User_ID']) if row.get('Author_User_ID') else None,
                        is_teacher_reply=(row.get('Is_Teacher_Reply') == 'True'),
                        is_read_by_admin=(row.get('Is_Read_By_Admin') == 'True'),
                        author_name=row['Author_Name'],
                        author_birth_date=_parse_date(row.get('Author_Birth_Date', '')),
                        author_age=int(row['Author_Age']) if row.get('Author_Age') else None,
                        personality_info=row.get('Personality_Info') or None,
                        comment_text=clean_newlines(row['Comment_Text']),
                        created_at=_parse_dt(row.get('Created_At', ''), default_now=True)
                    ))
                db.session.commit()

                for row in reply_rows:
                    db.session.add(PageComment(
                        id=int(row['ID']),
                        page_id=int(row['Page_ID']),
                        parent_id=int(row['Parent_ID']),
                        author_user_id=int(row['Author_User_ID']) if row.get('Author_User_ID') else None,
                        is_teacher_reply=(row.get('Is_Teacher_Reply') == 'True'),
                        is_read_by_admin=(row.get('Is_Read_By_Admin') == 'True'),
                        author_name=row['Author_Name'],
                        author_birth_date=_parse_date(row.get('Author_Birth_Date', '')),
                        author_age=int(row['Author_Age']) if row.get('Author_Age') else None,
                        personality_info=row.get('Personality_Info') or None,
                        comment_text=clean_newlines(row['Comment_Text']),
                        created_at=_parse_dt(row.get('Created_At', ''), default_now=True)
                    ))
                db.session.commit()

                # L. Commands, SiteInfo, Tools
                for row in stream_csv('9_commands.csv'):
                    cmd_kwargs = {
                        'title': row['Title'],
                        'title_kurdish': row.get('Title_KU') or None,
                        'command_text': row['Command'],
                        'description': clean_newlines(row.get('Description', '')) or None,
                        'description_kurdish': clean_newlines(row.get('Description_KU', '')) or None
                    }
                    if row.get('ID'):
                        cmd_kwargs['id'] = int(row['ID'])
                    db.session.add(SystemCommand(**cmd_kwargs))

                for row in stream_csv('10_siteinfo.csv'):
                    info_kwargs = {
                        'key': row['Key'],
                        'title': row['Title'],
                        'title_kurdish': row.get('Title_KU') or None,
                        'content': clean_newlines(row.get('Content', '')),
                        'content_kurdish': clean_newlines(row.get('Content_KU', '')) or None,
                        'last_updated': _parse_dt(row.get('Last_Updated', ''), default_now=True)
                    }
                    if row.get('ID'):
                        info_kwargs['id'] = int(row['ID'])
                    db.session.add(SiteInfo(**info_kwargs))
                db.session.commit()

                for row in stream_csv('11_tools.csv'):
                    db.session.add(Tool(
                        id=int(row['ID']),
                        title=row['Title'],
                        title_kurdish=row.get('Title_KU') or None,
                        link=row['Link'],
                        description=clean_newlines(row.get('Description', '')) or None,
                        description_kurdish=clean_newlines(row.get('Description_KU', '')) or None,
                        created_at=_parse_dt(row.get('Created_At', ''), default_now=True)
                    ))
                db.session.commit()

                # M. AdminNotifications & TeacherNotifications
                for row in stream_csv('15_admin_notifications.csv'):
                    db.session.add(AdminNotification(
                        id=int(row['ID']),
                        notification_type=row['Notification_Type'],
                        title=row['Title'],
                        message=clean_newlines(row['Message']),
                        actor_type=row.get('Actor_Type') or None,
                        actor_id=int(row['Actor_ID']) if row.get('Actor_ID') else None,
                        actor_name=row.get('Actor_Name') or None,
                        related_subject_id=int(row['Related_Subject_ID']) if row.get('Related_Subject_ID') else None,
                        related_page_id=int(row['Related_Page_ID']) if row.get('Related_Page_ID') else None,
                        related_question_id=int(row['Related_Question_ID']) if row.get('Related_Question_ID') else None,
                        is_checked=(row.get('Is_Checked') == 'True'),
                        checked_at=_parse_dt(row.get('Checked_At', '')),
                        created_at=_parse_dt(row.get('Created_At', ''), default_now=True)
                    ))

                for row in stream_csv('16_teacher_notifications.csv'):
                    db.session.add(TeacherNotification(
                        id=int(row['ID']),
                        teacher_id=int(row['Teacher_ID']),
                        sender_id=int(row['Sender_ID']) if row.get('Sender_ID') else None,
                        notification_type=row['Notification_Type'],
                        title=row['Title'],
                        message=clean_newlines(row['Message']),
                        related_subject_id=int(row['Related_Subject_ID']) if row.get('Related_Subject_ID') else None,
                        related_page_id=int(row['Related_Page_ID']) if row.get('Related_Page_ID') else None,
                        is_read=(row.get('Is_Read') == 'True'),
                        created_at=_parse_dt(row.get('Created_At', ''), default_now=True)
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
    """WIPE ALL DATA - Factory Reset in strict InnoDB bottom-up order."""
    if not current_user.is_admin:
        abort(403)

    form = WipeCleanForm()

    if form.validate_on_submit():
        try:
            _wipe_all_non_user_tables()
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
        info_record.title_kurdish = edit_form.title_kurdish.data
        info_record.content = edit_form.content.data
        info_record.content_kurdish = edit_form.content_kurdish.data
        db.session.commit()
        flash(_('Public Information Page Updated.'), 'success')
        return redirect(url_for('teacher.teacher_dashboard'))

    return render_template('admin/edit_about.html', form=edit_form)
