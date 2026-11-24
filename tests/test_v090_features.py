"""
Tests for v0.9.0 features and logical fixes:
1. Live ExamResult persistence & view-only Teacher/Admin statistics pages + CSV export.
2. Dual-language (English + Kurdish) Question Bank + CSV export/import roundtrip (including 'Ans' alias).
3. Code-based Students (>=8 char code), teacher scoping, Admin cross-teacher sharing, and student-code-only exams/quizzes.
4. Public Teacher Signup Request (/teacher/apply) + Admin approval & login.
5. Teacher-to-Admin messaging & permanent Admin notifications (no 3-day auto-delete).
6. Collapsible lecture comments & Teacher replies (named vs anonymous 'From Teacher').
7. Zero-loss 16-CSV Backup -> Wipe -> Restore across all models, Kurdish strings, and 'rn' text preservation.
"""
import io
import json
import zipfile
from datetime import date, datetime, timedelta

from app import bcrypt
from app.models import (
    User, Subject, SubjectTeacher, Page, Resource, Question,
    Student, StudentTeacher, ExamResult, PageComment,
    SiteInfo, SystemCommand, Tool, TeacherRequest,
    AdminNotification, TeacherNotification
)


def _create_teacher(db, username, email, password='teacher2pw'):
    pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    u = User(
        username=username,
        username_kurdish=username,
        email=email,
        password_hash=pw_hash,
        gender='male',
        is_admin=False,
        show_name_on_subject=True,
    )
    db.session.add(u)
    db.session.commit()
    return u


def test_live_stats_and_teacher_admin_filters(client, db, admin_user, teacher_user, sample_subject, sample_page, sample_questions):
    """Exam/quiz submissions update public, teacher-scoped, and admin detailed statistics + CSV export."""
    t2 = _create_teacher(db, 'DrAzad', 'azad@test.com')
    db.session.add(SubjectTeacher(subject_id=sample_subject.id, teacher_id=teacher_user.id, is_primary=True, show_name=True))

    other_subj = Subject(
        name='Probability',
        name_kurdish='ئەگەر',
        slug='probability',
        description='Other subject',
        teacher_id=t2.id,
        is_public=True,
    )
    db.session.add(other_subj)
    db.session.flush()
    db.session.add(SubjectTeacher(subject_id=other_subj.id, teacher_id=t2.id, is_primary=True, show_name=True))

    quiz_q = Question(
        question_text='Sample Quiz Q',
        option_a='Right', option_b='Wrong', option_c='Wrong2', option_d='Wrong3',
        correct_answer='A',
        subject_id=sample_subject.id,
        page_id=sample_page.id,
    )
    db.session.add(quiz_q)
    db.session.commit()

    # Submit final exam + lecture quiz
    client.post(f'/subject/{sample_subject.slug}/exam/submit', data={
        'taker_mode': 'guest',
        'taker_name': 'Hewa',
        'taker_birth_date': '2004-02-01',
        'taker_gender': 'male',
        f'q_{sample_questions[0].id}': 'A',
        f'q_{sample_questions[1].id}': 'A',
        f'q_{sample_questions[2].id}': 'B',
    })
    client.post(f'/subject/{sample_subject.slug}/exam/submit', data={
        'page_id': str(sample_page.id),
        'taker_mode': 'guest',
        'taker_birth_date': '2005-03-04',
        'taker_gender': 'female',
        f'q_{quiz_q.id}': 'A',
    })

    # Public stats reflect live submissions
    pub_stats = client.get('/public/stats')
    assert pub_stats.status_code == 200
    assert b'Mathematics' in pub_stats.data

    # Teacher stats scoped to assigned subjects only, view-only checkbox filter works
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    t_stats = client.get('/teacher/stats')
    assert t_stats.status_code == 200
    assert b'Mathematics' in t_stats.data
    assert b'Probability' not in t_stats.data

    t_stats_filtered = client.get(f'/teacher/stats?subjects={sample_subject.id}')
    assert t_stats_filtered.status_code == 200
    assert b'Hewa' in t_stats_filtered.data
    client.get('/logout')

    # Admin stats & CSV export
    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    a_stats = client.get('/admin/stats?gender=male')
    assert a_stats.status_code == 200
    assert b'Hewa' in a_stats.data

    csv_resp = client.get('/admin/stats/export')
    assert csv_resp.status_code == 200
    assert 'text/csv' in csv_resp.mimetype
    csv_text = csv_resp.data.decode('utf-8-sig')
    assert 'Hewa' in csv_text
    assert 'Mathematics' in csv_text


def test_bilingual_question_bank_and_csv_roundtrip(client, db, teacher_user, sample_subject):
    """Questions store dual EN & KU faces, render per active locale, and roundtrip cleanly via CSV."""
    db.session.add(SubjectTeacher(subject_id=sample_subject.id, teacher_id=teacher_user.id, is_primary=True, show_name=True))
    db.session.commit()

    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    api_resp = client.post(
        f'/teacher/api/save_questions/{sample_subject.id}',
        data=json.dumps([{
            'text': 'What is variance?',
            'a': 'Spread', 'b': 'Mean', 'c': 'Median', 'd': 'Mode',
            'text_ku': 'ڤاریانس چییە؟',
            'a_ku': 'بڵاوبوونەوە', 'b_ku': 'ناوەند', 'c_ku': 'ناوەڕاست', 'd_ku': 'مۆد',
            'correct': 'A',
            'page_id': '',
            'is_kurdish': False,
        }]),
        content_type='application/json',
    )
    assert api_resp.status_code == 200
    assert api_resp.get_json()['status'] == 'success'

    # Export CSV
    exp_resp = client.get(f'/teacher/export/questions/{sample_subject.id}')
    assert exp_resp.status_code == 200
    exp_text = exp_resp.data.decode('utf-8-sig')
    assert 'Question_KU' in exp_text
    assert 'Answer' in exp_text
    assert 'ڤاریانس چییە؟' in exp_text

    # Re-import using 'Ans' alias header as well
    sample_csv = (
        '"Question","Opt A","Opt B","Opt C","Opt D",'
        '"Question_KU","Opt A_KU","Opt B_KU","Opt C_KU","Opt D_KU","Ans"\n'
        '"What is mean?","Avg","Sum","Max","Min",'
        '"ناوەندی ژمێرەیی چییە؟","تێکڕا","کۆ","زۆرترین","کەمترین","B"\n'
    ).encode('utf-8-sig')
    step1 = client.post(
        f'/teacher/import/questions/{sample_subject.id}',
        data={'file': (io.BytesIO(sample_csv), 'questions.csv')},
        content_type='multipart/form-data',
    )
    assert step1.status_code == 200
    assert b'What is mean?' in step1.data
    assert 'ناوەندی ژمێرەیی چییە؟'.encode('utf-8') in step1.data

    imported_payload = json.dumps([{
        'question_text': 'What is mean?',
        'option_a': 'Avg', 'option_b': 'Sum', 'option_c': 'Max', 'option_d': 'Min',
        'question_text_kurdish': 'ناوەندی ژمێرەیی چییە؟',
        'option_a_kurdish': 'تێکڕا', 'option_b_kurdish': 'کۆ',
        'option_c_kurdish': 'زۆرترین', 'option_d_kurdish': 'کەمترین',
        'correct_answer': 'B',
    }])
    confirm_resp = client.post(
        '/common/import/confirm',
        data={
            'import_type': 'question',
            'subject_id': str(sample_subject.id),
            'bulk_lecture_id': '',
            'data': imported_payload,
        },
        follow_redirects=True,
    )
    assert confirm_resp.status_code == 200
    assert Question.query.filter_by(subject_id=sample_subject.id).count() == 2
    client.get('/logout')

    # Verify EN vs KU rendering on public exam page
    en_exam = client.get(f'/subject/{sample_subject.slug}/exam')
    assert b'What is variance?' in en_exam.data

    client.get('/set-lang/ku')
    ku_exam = client.get(f'/subject/{sample_subject.slug}/exam')
    assert 'ڤاریانس چییە؟'.encode('utf-8') in ku_exam.data
    assert b'dir="rtl"' in ku_exam.data


def test_students_sharing_and_hidden_exams_quizzes(client, db, admin_user, teacher_user, sample_subject, sample_page, sample_questions):
    """Teachers manage code-based students (>=8 chars), lock exams/quizzes, and Admin shares codes across teachers."""
    t2 = _create_teacher(db, 'SecondTeacher', 'teacher2@test.com')
    db.session.add(SubjectTeacher(subject_id=sample_subject.id, teacher_id=teacher_user.id, is_primary=True, show_name=True))

    t2_subject = Subject(
        name='Econometrics',
        slug='econometrics',
        description='T2 subject',
        teacher_id=t2.id,
        is_public=True,
        exam_student_only=True,
    )
    db.session.add(t2_subject)
    db.session.flush()
    db.session.add(SubjectTeacher(subject_id=t2_subject.id, teacher_id=t2.id, is_primary=True, show_name=True))
    db.session.commit()

    # Teacher 1 creates Student Zana and hides both exam & lecture quiz
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    create_resp = client.post('/staff/students', data={
        'name_en': 'Zana Ali',
        'name_ku': 'زانا عەلی',
        'birth_date': '2003-04-10',
        'gender': 'male',
        'department_en': 'Statistics',
        'department_ku': 'ئامار',
    }, follow_redirects=True)
    assert create_resp.status_code == 200

    zana = Student.query.filter_by(name_en='Zana Ali').first()
    assert zana is not None
    assert len(zana.student_code) >= 8
    assert StudentTeacher.query.filter_by(student_id=zana.id, teacher_id=teacher_user.id).first() is not None

    client.post(f'/subject/{sample_subject.id}/toggle_exam_restriction', follow_redirects=True)
    client.post(f'/page/{sample_page.id}/toggle_quiz_restriction', follow_redirects=True)
    db.session.refresh(sample_subject)
    db.session.refresh(sample_page)
    assert sample_subject.exam_student_only is True
    assert sample_page.quiz_student_only is True
    client.get('/logout')

    # Teacher 2 creates an unrelated student Bana
    client.post('/login', data={'email': 'teacher2@test.com', 'password': 'teacher2pw'})
    client.post('/staff/students', data={
        'name_en': 'Bana Omar',
        'name_ku': 'بانا عومەر',
        'birth_date': '2004-06-20',
        'gender': 'female',
        'department_en': 'IT',
        'department_ku': 'ئایتی',
    })
    bana = Student.query.filter_by(name_en='Bana Omar').first()
    client.get('/logout')

    # Visitor hits gated exam & quiz -> sees Student Code gate, NOT questions
    gated_exam = client.get(f'/subject/{sample_subject.slug}/exam')
    assert gated_exam.status_code == 200
    assert b'What is 1 + 1?' not in gated_exam.data
    assert b'Student Code' in gated_exam.data

    gated_quiz = client.get(f'/subject/{sample_subject.slug}/lecture/{sample_page.id}/quiz')
    assert gated_quiz.status_code == 200
    assert b'Student Code' in gated_quiz.data

    # Bana's code MUST be rejected on Teacher 1's subject
    bad_unlock = client.post(
        f'/subject/{sample_subject.slug}/unlock_exam',
        data={'student_code': bana.student_code},
        follow_redirects=True,
    )
    assert b'Invalid or unauthorized Student Code' in bad_unlock.data

    # Zana's code unlocks Teacher 1's exam & submits as student
    good_unlock = client.post(
        f'/subject/{sample_subject.slug}/unlock_exam',
        data={'student_code': zana.student_code},
        follow_redirects=True,
    )
    assert b'What is 1 + 1?' in good_unlock.data

    submit_student_exam = client.post(
        f'/subject/{sample_subject.slug}/exam/submit',
        data={
            'taker_mode': 'student',
            'student_code': zana.student_code,
            f'q_{sample_questions[0].id}': 'A',
            f'q_{sample_questions[1].id}': 'A',
            f'q_{sample_questions[2].id}': 'A',
        },
        follow_redirects=True,
    )
    assert b'Examination Submitted. Score: 3/3 (100%)' in submit_student_exam.data
    res = ExamResult.query.filter_by(student_record_id=zana.id).first()
    assert res is not None and res.score == 100

    # Admin shares Zana with Teacher 2 -> Zana's code now unlocks Teacher 2's hidden exam
    deny_t2_before = client.post(
        f'/subject/{t2_subject.slug}/unlock_exam',
        data={'student_code': zana.student_code},
        follow_redirects=True,
    )
    assert b'Invalid or unauthorized Student Code' in deny_t2_before.data

    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    share_resp = client.post(
        '/admin/students/bulk_share',
        data={'student_ids': [str(zana.id)], 'target_teacher_id': str(t2.id)},
        follow_redirects=True,
    )
    assert share_resp.status_code == 200
    client.get('/logout')

    allow_t2_after = client.post(
        f'/subject/{t2_subject.slug}/unlock_exam',
        data={'student_code': zana.student_code},
        follow_redirects=True,
    )
    assert b'Exam unlocked for Zana Ali' in allow_t2_after.data


def test_public_teacher_apply_and_admin_approval(client, db, admin_user):
    """Applicant submits /teacher/apply, Admin approves in /admin/teacher-requests, teacher can log in."""
    apply_resp = client.post('/teacher/apply', data={
        'name_en': 'Narin Azad',
        'name_ku': 'نارین ئازاد',
        'email': 'narin@test.com',
        'password': 'narinpass123',
        'confirm_password': 'narinpass123',
        'gender': 'female',
        'birth_date': '1991-06-15',
        'bio': 'Applied statistics instructor.',
        'reason': 'I want to teach applied biostatistics online.',
    }, follow_redirects=True)
    assert apply_resp.status_code == 200
    assert b'Your teacher application has been submitted!' in apply_resp.data

    req = TeacherRequest.query.filter_by(email='narin@test.com').first()
    assert req is not None and req.status == 'pending'
    assert AdminNotification.query.filter_by(notification_type='teacher_request').count() == 1

    # Admin reviews and approves
    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    queue_page = client.get('/admin/teacher-requests')
    assert queue_page.status_code == 200
    assert b'Narin Azad' in queue_page.data

    approve_resp = client.post(f'/admin/teacher-requests/{req.id}/approve', follow_redirects=True)
    assert approve_resp.status_code == 200
    assert b'Teacher account approved' in approve_resp.data
    client.get('/logout')

    # Approved teacher logs in with chosen password
    login_resp = client.post('/login', data={'email': 'narin@test.com', 'password': 'narinpass123'}, follow_redirects=True)
    assert login_resp.status_code == 200
    assert b'Logged in successfully' in login_resp.data


def test_teacher_to_admin_messaging_and_permanent_notifications(client, db, admin_user, teacher_user):
    """Teachers can message Admins; Admin notifications persist indefinitely (>3 days) unless deleted."""
    # Insert an older notification (> 10 days old)
    old_notif = AdminNotification(
        notification_type='page_added',
        title='Old Lecture Created',
        message='Created 10 days ago.',
        actor_type='teacher',
        actor_id=teacher_user.id,
        actor_name=teacher_user.username,
        created_at=datetime.utcnow() - timedelta(days=10),
    )
    db.session.add(old_notif)
    db.session.commit()

    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    msg_resp = client.post('/teacher/message_admin', data={
        'title': 'Need Lab Link Update',
        'message': 'Please check external SPSS dataset mirror.',
    }, follow_redirects=True)
    assert msg_resp.status_code == 200
    assert b'Your message has been sent to the administrators.' in msg_resp.data
    client.get('/logout')

    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    dash = client.get('/teacher/dashboard')
    assert dash.status_code == 200
    assert b'Teacher Message' in dash.data
    assert b'bg-primary-subtle' in dash.data
    assert b'Need Lab Link Update' in dash.data

    notif_page = client.get('/admin/notifications')
    assert notif_page.status_code == 200
    assert b'Old Lecture Created' in notif_page.data
    assert b'Need Lab Link Update' in notif_page.data

    # Old notification was NOT auto-deleted; remains until explicitly deleted
    assert db.session.get(AdminNotification, old_notif.id) is not None
    client.post(f'/admin/notification/{old_notif.id}/delete', follow_redirects=True)
    assert db.session.get(AdminNotification, old_notif.id) is None


def test_collapsible_comments_and_teacher_replies(client, db, admin_user, teacher_user, sample_subject, sample_page):
    """Lecture comments collapse by default with metadata modal; teacher replies honor show_name or show 'From Teacher'."""
    db.session.add(SubjectTeacher(subject_id=sample_subject.id, teacher_id=teacher_user.id, is_primary=True, show_name=True))
    db.session.commit()

    page_resp = client.get(f'/subject/{sample_subject.slug}/page/{sample_page.id}')
    assert page_resp.status_code == 200
    assert b'id="commentsCollapse"' in page_resp.data
    assert b'id="commentDetailsModal"' in page_resp.data

    # Visitor leaves a comment
    client.post(f'/subject/{sample_subject.slug}/page/{sample_page.id}/comment', data={
        'author_name': 'Kawa',
        'author_birth_date': '2004-07-01',
        'comment_text': 'Can you share the formula sheet?',
    })
    parent_comment = PageComment.query.filter_by(author_name='Kawa').first()
    assert parent_comment is not None

    # Teacher replies while name is SHOWN
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    reply_resp = client.post(
        f'/subject/{sample_subject.slug}/page/{sample_page.id}/comment/{parent_comment.id}/reply',
        data={'comment_text': 'Yes, added to resources below!'},
        follow_redirects=True,
    )
    assert reply_resp.status_code == 200
    assert b'Yes, added to resources below!' in reply_resp.data
    assert b'TestTeacher' in reply_resp.data

    # Teacher hides their name on this subject -> public sees 'From Teacher' instead of real name
    client.post(f'/subject/{sample_subject.id}/toggle_my_name', follow_redirects=True)
    client.get('/logout')

    anon_view = client.get(f'/subject/{sample_subject.slug}/page/{sample_page.id}')
    assert b'Yes, added to resources below!' in anon_view.data
    assert b'From Teacher' in anon_view.data
    assert b'TestTeacher' not in anon_view.data

    # Kurdish UI displays Sorani 'لە لایەن مامۆستاوە'
    client.get('/set-lang/ku')
    ku_view = client.get(f'/subject/{sample_subject.slug}/page/{sample_page.id}')
    assert 'لە لایەن مامۆستاوە'.encode('utf-8') in ku_view.data

    # Admin still sees real author identity in /admin/comments
    client.get('/set-lang/en')
    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    admin_comments = client.get('/admin/comments')
    assert admin_comments.status_code == 200
    assert b'TestTeacher' in admin_comments.data


def test_full_system_backup_wipe_and_restore_zero_loss(client, db, admin_user, teacher_user, sample_subject, sample_page, sample_questions):
    """Full 16-CSV backup -> wipe_clean -> setup/restore preserves all models, Kurdish strings, and 'rn' words."""
    sample_subject.name_kurdish = 'بیرکاری'
    sample_subject.exam_student_only = True
    sample_page.title_kurdish = 'وانەی یەکەم'
    sample_page.quiz_student_only = True
    sample_page.content_body = '<p>Students learn modern regression patterns.</p>'
    sample_questions[0].question_text_kurdish = '١ + ١ چەندە؟'
    sample_questions[0].option_a_kurdish = '٢'

    st = SubjectTeacher(subject_id=sample_subject.id, teacher_id=teacher_user.id, is_primary=True, show_name=True)
    res = Resource(title='Video Guide', title_kurdish='ڤیدیۆی ڕێنمایی', link='https://example.com', page_id=sample_page.id)
    student = Student(
        name_en='Salar Bakr', name_ku='سالار بەکر',
        birth_date=date(2002, 5, 5), gender='male',
        department_en='Statistics', department_ku='ئامار',
        student_code='STAT9988', created_by_id=teacher_user.id,
    )
    site_about = SiteInfo(
        key='about', title='About StatInfo', title_kurdish='دەربارەی ئێمە',
        content='<p>About EN</p>', content_kurdish='<p>دەربارە</p>',
    )
    cmd = SystemCommand(title='Check Logs', title_kurdish='پشکنینی تۆمار', command_text='tail -n 20 err.log', description='Logs')
    tool = Tool(title='JASP', title_kurdish='جاسپ', link='https://jasp-stats.org', description='Stats tool')
    treq = TeacherRequest(
        name_en='Rebin Tariq', name_ku='ڕێبین تاریق', email='rebin@test.com',
        password_hash=bcrypt.generate_password_hash('pw12345').decode('utf-8'),
        gender='male', birth_date=date(1990, 1, 1), reason='Want to teach econometrics.',
    )

    db.session.add_all([st, res, student, site_about, cmd, tool, treq])
    db.session.flush()

    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher_user.id))
    db.session.add(ExamResult(
        score=100, correct_count=3, total_questions=3,
        subject_id=sample_subject.id, student_record_id=student.id,
    ))
    parent_c = PageComment(
        page_id=sample_page.id, author_name='Lana',
        author_birth_date=date(2005, 2, 2), comment_text='Great learn note',
        is_read_by_admin=False,
    )
    db.session.add(parent_c)
    db.session.flush()
    db.session.add(PageComment(
        page_id=sample_page.id, parent_id=parent_c.id, author_user_id=teacher_user.id,
        is_teacher_reply=True, is_read_by_admin=True,
        author_name=teacher_user.username, comment_text='Thanks!',
    ))
    db.session.add(AdminNotification(
        notification_type='teacher_message', title='Notice', message='Backup verify',
        actor_type='teacher', actor_id=teacher_user.id, actor_name=teacher_user.username,
    ))
    db.session.add(TeacherNotification(
        teacher_id=teacher_user.id, sender_id=admin_user.id,
        notification_type='admin_message', title='Admin Hello', message='Check schedule',
    ))
    db.session.commit()

    # 1. Export full backup
    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    backup_resp = client.get('/admin/export/full_backup')
    assert backup_resp.status_code == 200
    zip_bytes = backup_resp.data

    with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
        names = set(zf.namelist())
        assert '1_users.csv' in names
        assert '14_teacher_requests.csv' in names
        assert '15_admin_notifications.csv' in names
        assert '16_teacher_notifications.csv' in names
        assert len(names) == 16

    # 2. Wipe clean & re-initialize temp admin to reach restore endpoint
    wipe_resp = client.post('/admin/system/wipe_clean', data={'confirm_wipe': 'y'}, follow_redirects=True)
    assert wipe_resp.status_code == 200
    assert Subject.query.count() == 0
    assert Student.query.count() == 0
    assert PageComment.query.count() == 0

    client.post('/setup', data={
        'username': 'TempAdmin',
        'email': 'temp@test.com',
        'password': 'temppassword',
        'confirm_password': 'temppassword',
    })
    client.post('/login', data={'email': 'temp@test.com', 'password': 'temppassword'})

    # 3. Restore backup ZIP
    restore_resp = client.post(
        '/admin/system/restore',
        data={
            'backup_file': (io.BytesIO(zip_bytes), 'backup.zip'),
            'confirm_wipe': 'y',
        },
        content_type='multipart/form-data',
        follow_redirects=True,
    )
    assert restore_resp.status_code == 200

    # Verify zero-loss restoration across all 14 tables & 'rn' intact
    restored_subj = Subject.query.filter_by(slug='mathematics').first()
    assert restored_subj is not None
    assert restored_subj.name_kurdish == 'بیرکاری'
    assert restored_subj.exam_student_only is True

    restored_page = Page.query.filter_by(subject_id=restored_subj.id).first()
    assert restored_page.title_kurdish == 'وانەی یەکەم'
    assert restored_page.quiz_student_only is True
    assert 'learn modern regression patterns' in restored_page.content_body

    restored_q = Question.query.filter_by(subject_id=restored_subj.id).first()
    assert restored_q.question_text_kurdish is not None

    restored_student = Student.query.filter_by(student_code='STAT9988').first()
    assert restored_student is not None and restored_student.name_ku == 'سالار بەکر'
    assert StudentTeacher.query.filter_by(student_id=restored_student.id).count() == 1

    assert ExamResult.query.filter_by(student_record_id=restored_student.id, score=100).count() == 1
    assert Resource.query.filter_by(title_kurdish='ڤیدیۆی ڕێنمایی').count() == 1
    assert PageComment.query.count() == 2
    assert PageComment.query.filter_by(is_teacher_reply=True).count() == 1
    assert SiteInfo.query.filter_by(key='about', title_kurdish='دەربارەی ئێمە').count() == 1
    assert SystemCommand.query.filter_by(title_kurdish='پشکنینی تۆمار').count() == 1
    assert Tool.query.filter_by(title_kurdish='جاسپ').count() == 1
    assert TeacherRequest.query.filter_by(email='rebin@test.com').count() == 1
    assert AdminNotification.query.filter_by(title='Notice').count() == 1
    assert TeacherNotification.query.filter_by(title='Admin Hello').count() == 1
