"""
Tests for v0.9.1 bug fixes and new features:
1. Admin full Teacher Dashboard inspector view (/admin/view_teacher/<id>) + ?teacher_id= stats/students/notifications.
2. Comment modal (#commentDetailsModal) rendered outside .card backdrop stack + moved to document.body.
3. Logged-in teacher/admin direct commenting & replying without extra personal detail prompts + anonymity honored.
4. Question Bank save API safe against None page_id (fixes NoneType int() crash) + manual RTL toggle/column removed.
5. Dedicated Hidden Exam Bank Sheet (/teacher/builder/private_exams), auto-generated multi-links (/exam/link/<token>), Student Code gating, and Admin/Teacher stats tracking.
6. Public Teacher Profile (/teacher/<id>/profile), clickable teacher links on subjects/lectures, and granular privacy toggles.
7. Read notifications hidden from small dashboard boxes while remaining permanently on /admin/notifications & /teacher/notifications.
8. Optional separate 8-char CommentGuest codes (generated only when checked, reusable, strictly separate from Students/ExamGuests).
9. Optional separate 8-char ExamGuest codes (generated only when checked, reusable, rejected on student-only exams) + 21-CSV full backup/restore.
"""
import io
import json
import zipfile
from datetime import date

from app import bcrypt
from app.models import (
    User, Subject, SubjectTeacher, Page, Question,
    Student, StudentTeacher, ExamResult, PageComment,
    AdminNotification, TeacherNotification,
    PrivateExam, PrivateQuestion, PrivateExamQuestion,
    CommentGuest, ExamGuest
)


def _make_teacher(db, username, email, pw='teacher2pw'):
    u = User(
        username=username,
        username_kurdish=username,
        email=email,
        password_hash=bcrypt.generate_password_hash(pw).decode('utf-8'),
        gender='female',
        birth_date=date(1990, 5, 10),
        bio='Experienced statistician.',
        is_admin=False,
        show_name_on_subject=True,
    )
    db.session.add(u)
    db.session.commit()
    return u


def test_admin_full_teacher_dashboard_view(client, db, admin_user, teacher_user, sample_subject):
    """Admins see every section inside any teacher's dashboard plus teacher-scoped pages."""
    teacher_user.bio = 'Probability & Data Science lecturer'
    db.session.add(SubjectTeacher(subject_id=sample_subject.id, teacher_id=teacher_user.id, is_primary=True, show_name=True))
    stu = Student(
        name_en='Dilan', name_ku='دیلان',
        birth_date=date(2004, 1, 1), gender='female',
        department_en='Stats', department_ku='ئامار',
        student_code='DILAN123', created_by_id=teacher_user.id,
    )
    db.session.add(stu)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=stu.id, teacher_id=teacher_user.id))
    db.session.add(TeacherNotification(
        teacher_id=teacher_user.id, sender_id=admin_user.id,
        notification_type='admin_message', title='Important Staff Note',
        message='Check hidden exams before Monday.', is_read=False,
    ))
    db.session.commit()

    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    resp = client.get(f'/admin/view_teacher/{teacher_user.id}')
    assert resp.status_code == 200
    assert b'Admin Teacher-View Mode' in resp.data
    assert b'Probability &amp; Data Science lecturer' in resp.data
    assert b'Important Staff Note' in resp.data
    assert b'My Students' in resp.data
    assert b'Message Administration' in resp.data
    assert f'/teacher/stats?teacher_id={teacher_user.id}'.encode() in resp.data
    assert f'/staff/students?teacher_id={teacher_user.id}'.encode() in resp.data
    assert f'/teacher/notifications?teacher_id={teacher_user.id}'.encode() in resp.data

    assert client.get(f'/teacher/stats?teacher_id={teacher_user.id}').status_code == 200
    stud_resp = client.get(f'/staff/students?teacher_id={teacher_user.id}')
    assert stud_resp.status_code == 200
    assert b'Dilan' in stud_resp.data


def test_comment_modal_outside_cards_and_direct_teacher_comments(client, db, admin_user, teacher_user, sample_subject, sample_page):
    """Modal lives outside .card wrappers; logged-in staff comment & reply directly without questions."""
    db.session.add(SubjectTeacher(subject_id=sample_subject.id, teacher_id=teacher_user.id, is_primary=True, show_name=True))
    other_teacher = _make_teacher(db, 'VisitingTeacher', 'visit@test.com')
    db.session.commit()

    guest_page = client.get(f'/subject/{sample_subject.slug}/page/{sample_page.id}')
    html = guest_page.data.decode('utf-8')
    assert 'id="commentsCollapse"' in html
    assert 'id="commentDetailsModal"' in html
    # #commentDetailsModal is placed after the closing card containers
    assert html.index('id="commentsCollapse"') < html.index('id="commentDetailsModal"')
    assert 'document.body.appendChild(modalEl)' in html

    # Visitor posts a comment
    client.post(f'/subject/{sample_subject.slug}/page/{sample_page.id}/comment', data={
        'author_name': 'Soran',
        'author_birth_date': '2004-08-08',
        'comment_text': 'Question from guest',
    })
    guest_comment = PageComment.query.filter_by(author_name='Soran').first()
    assert guest_comment is not None

    # Assigned teacher posts a direct top-level comment (NO author_name or birth_date sent)
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    staff_post = client.post(
        f'/subject/{sample_subject.slug}/page/{sample_page.id}/comment',
        data={'comment_text': 'Important clarification for all students!'},
        follow_redirects=True,
    )
    assert staff_post.status_code == 200
    assert b'Important clarification for all students!' in staff_post.data
    direct_row = PageComment.query.filter_by(comment_text='Important clarification for all students!').first()
    assert direct_row is not None and direct_row.is_teacher_reply is True
    client.get('/logout')

    # Second (unassigned) logged-in teacher can also reply directly without extra questions
    client.post('/login', data={'email': 'visit@test.com', 'password': 'teacher2pw'})
    reply_resp = client.post(
        f'/subject/{sample_subject.slug}/page/{sample_page.id}/comment/{guest_comment.id}/reply',
        data={'comment_text': 'Another instructor perspective!'},
        follow_redirects=True,
    )
    assert reply_resp.status_code == 200
    assert b'Another instructor perspective!' in reply_resp.data
    client.get('/logout')

    # Hide primary teacher's name -> their top-level comment displays 'From Teacher' instead of TestTeacher
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    client.post(f'/subject/{sample_subject.id}/toggle_my_name')
    client.get('/logout')

    anon_html = client.get(f'/subject/{sample_subject.slug}/page/{sample_page.id}').data
    assert b'Important clarification for all students!' in anon_html
    assert b'From Teacher' in anon_html
    assert b'TestTeacher' not in anon_html


def test_save_questions_none_page_id_and_rtl_removed(client, db, teacher_user, sample_subject):
    """Adding new questions with page_id=None succeeds without NoneType int() crash; RTL switch is gone."""
    db.session.add(SubjectTeacher(subject_id=sample_subject.id, teacher_id=teacher_user.id, is_primary=True, show_name=True))
    db.session.commit()

    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    builder_page = client.get(f'/teacher/builder/exam?subject={sample_subject.id}')
    assert builder_page.status_code == 200
    assert b'Is Kurdish? (RTL)' not in builder_page.data
    assert b'>RTL<' not in builder_page.data

    # Payload mimicking Add New Question Row (id: None, page_id: None)
    resp = client.post(
        f'/teacher/api/save_questions/{sample_subject.id}',
        data=json.dumps([
            {
                'id': None, 'text': 'New Q without lecture', 'a': '1', 'b': '2', 'c': '3', 'd': '4',
                'text_ku': 'پرسیاری نوێ', 'a_ku': '١', 'b_ku': '٢', 'c_ku': '٣', 'd_ku': '٤',
                'correct': 'B', 'page_id': None,
            },
            {
                'id': '', 'text': 'New Q empty lecture', 'a': 'x', 'b': 'y', 'c': 'z', 'd': 'w',
                'text_ku': '', 'a_ku': '', 'b_ku': '', 'c_ku': '', 'd_ku': '',
                'correct': 'A', 'page_id': '',
            },
        ]),
        content_type='application/json',
    )
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'success'
    assert Question.query.filter_by(subject_id=sample_subject.id).count() == 2


def test_hidden_exam_question_bank_and_multi_links(client, db, admin_user, teacher_user, sample_subject):
    """Teachers create multiple hidden exam links, assign shared questions, gate by Student Code, and record results."""
    db.session.add(SubjectTeacher(subject_id=sample_subject.id, teacher_id=teacher_user.id, is_primary=True, show_name=True))
    stu = Student(
        name_en='Zana', name_ku='زانا', birth_date=date(2003, 5, 5), gender='male',
        department_en='Statistics', department_ku='ئامار',
        student_code='HIDDEN99', created_by_id=teacher_user.id,
    )
    db.session.add(stu)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=stu.id, teacher_id=teacher_user.id))
    db.session.commit()

    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    assert client.get(f'/teacher/builder/private_exams?subject={sample_subject.id}').status_code == 200

    # Create two hidden exam links
    client.post(f'/teacher/private_exam/{sample_subject.id}/create', data={
        'title': 'Group A Hidden Exam', 'title_kurdish': 'تاقیکردنەوەی گرووپی A',
    })
    client.post(f'/teacher/private_exam/{sample_subject.id}/create', data={
        'title': 'Group B Hidden Quiz', 'title_kurdish': 'کویزی گرووپی B',
    })
    pe_a = PrivateExam.query.filter_by(title='Group A Hidden Exam').first()
    pe_b = PrivateExam.query.filter_by(title='Group B Hidden Quiz').first()
    assert pe_a is not None and pe_b is not None

    # Assign Q1 to BOTH links and Q2 only to link A
    save_resp = client.post(
        f'/teacher/api/save_private_questions/{sample_subject.id}',
        data=json.dumps([
            {
                'id': None, 'text': 'Shared Q1', 'a': 'Yes', 'b': 'No', 'c': 'C', 'd': 'D',
                'text_ku': 'پرسیاری هاوبەش', 'a_ku': 'بەڵێ', 'b_ku': 'نەخێر', 'c_ku': 'C', 'd_ku': 'D',
                'correct': 'A', 'exam_ids': [pe_a.id, pe_b.id],
            },
            {
                'id': None, 'text': 'Group A Only Q2', 'a': '10', 'b': '20', 'c': '30', 'd': '40',
                'text_ku': '', 'a_ku': '', 'b_ku': '', 'c_ku': '', 'd_ku': '',
                'correct': 'B', 'exam_ids': [pe_a.id],
            },
        ]),
        content_type='application/json',
    )
    assert save_resp.status_code == 200
    assert len(pe_a.assigned_questions) == 2
    assert len(pe_b.assigned_questions) == 1

    # CSV export works
    exp = client.get(f'/teacher/export/private_questions/{sample_subject.id}')
    assert exp.status_code == 200 and 'Shared Q1' in exp.data.decode('utf-8-sig')
    client.get('/logout')

    # Guest hits hidden exam link -> gated, NOT questions
    gated = client.get(f'/exam/link/{pe_a.access_token}')
    assert gated.status_code == 200
    assert b'Shared Q1' not in gated.data
    assert b'Student Code' in gated.data

    # Unlock with Student Code and submit
    unlock = client.post(f'/exam/link/{pe_a.access_token}/unlock', data={'student_code': 'HIDDEN99'}, follow_redirects=True)
    assert b'Shared Q1' in unlock.data and b'Group A Only Q2' in unlock.data

    q1_id = pe_a.assigned_questions[0].id
    q2_id = pe_a.assigned_questions[1].id
    sub = client.post(f'/exam/link/{pe_a.access_token}/submit', data={
        'taker_mode': 'student', 'student_code': 'HIDDEN99',
        f'q_{q1_id}': 'A', f'q_{q2_id}': 'B',
    }, follow_redirects=True)
    assert b'Examination Submitted. Score: 2/2 (100%)' in sub.data

    res = ExamResult.query.filter_by(private_exam_id=pe_a.id).first()
    assert res is not None and res.student_record_id == stu.id and res.score == 100

    # Admin stats filter & Regenerate link
    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    stats = client.get('/admin/stats?exam_type=private')
    assert b'Group A Hidden Exam' in stats.data

    old_tok = pe_a.access_token
    client.post(f'/teacher/private_exam/{pe_a.id}/regenerate_link')
    db.session.refresh(pe_a)
    assert pe_a.access_token != old_tok
    client.get('/logout')
    assert client.get(f'/exam/link/{old_tok}').status_code == 404


def test_public_teacher_profile_privacy_and_clickable_links(client, db, admin_user, teacher_user, sample_subject, sample_page):
    """Teacher names link to /teacher/<id>/profile; individual hides work; profile_public=False returns 404 to public."""
    teacher_user.bio = 'Multivariate statistics author'
    teacher_user.gender = 'male'
    teacher_user.birth_date = date(1988, 3, 15)
    db.session.add(SubjectTeacher(subject_id=sample_subject.id, teacher_id=teacher_user.id, is_primary=True, show_name=True))
    db.session.commit()

    # Subject and lecture pages link to public teacher profile
    subj_resp = client.get(f'/subject/{sample_subject.slug}')
    page_resp = client.get(f'/subject/{sample_subject.slug}/page/{sample_page.id}')
    expected_href = f'/teacher/{teacher_user.id}/profile'.encode()
    assert expected_href in subj_resp.data
    assert expected_href in page_resp.data

    # All visible initially
    prof = client.get(f'/teacher/{teacher_user.id}/profile')
    assert prof.status_code == 200
    assert b'TestTeacher' in prof.data
    assert b'Multivariate statistics author' in prof.data
    assert b'Male' in prof.data

    # Teacher hides Bio and Gender individually
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    client.post('/teacher/profile/update', data={
        'username': 'TestTeacher',
        'gender': 'male',
        'birth_date': '1988-03-15',
        'bio': 'Multivariate statistics author',
        'profile_public': 'y',
        'profile_show_name': 'y',
        'profile_show_age': 'y',
        # bio & gender omitted -> False
    })
    client.get('/logout')

    prof2 = client.get(f'/teacher/{teacher_user.id}/profile')
    assert prof2.status_code == 200
    assert b'TestTeacher' in prof2.data
    assert b'Multivariate statistics author' not in prof2.data
    assert b'Male' not in prof2.data

    # Teacher disables entire public profile -> 404 for guests, 200 preview for Admin
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    client.post('/teacher/profile/update', data={
        'username': 'TestTeacher', 'gender': 'male', 'birth_date': '1988-03-15',
        # profile_public omitted -> False
    })
    client.get('/logout')

    assert client.get(f'/teacher/{teacher_user.id}/profile').status_code == 404
    assert expected_href not in client.get(f'/subject/{sample_subject.slug}').data

    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    assert client.get(f'/teacher/{teacher_user.id}/profile').status_code == 200


def test_read_notifications_hidden_from_small_box_only(client, db, admin_user, teacher_user):
    """Read notifications leave dashboard small boxes and remain in full notifications hubs."""
    an_unread = AdminNotification(notification_type='teacher_message', title='Unread Admin Box Msg', message='Still unread', is_checked=False)
    an_read = AdminNotification(notification_type='teacher_message', title='Read Admin Msg', message='Already read', is_checked=True)
    tn_unread = TeacherNotification(teacher_id=teacher_user.id, notification_type='admin_message', title='Unread Teacher Box', message='Check now', is_read=False)
    tn_read = TeacherNotification(teacher_id=teacher_user.id, notification_type='admin_message', title='Read Teacher Msg', message='Done reading', is_read=True)
    db.session.add_all([an_unread, an_read, tn_unread, tn_read])
    db.session.commit()

    # Admin dashboard vs /admin/notifications
    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    a_dash = client.get('/teacher/dashboard')
    assert b'Unread Admin Box Msg' in a_dash.data
    assert b'Read Admin Msg' not in a_dash.data
    a_hub = client.get('/admin/notifications')
    assert b'Unread Admin Box Msg' in a_hub.data
    assert b'Read Admin Msg' in a_hub.data
    client.get('/logout')

    # Teacher dashboard vs /teacher/notifications
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    t_dash = client.get('/teacher/dashboard')
    assert b'Unread Teacher Box' in t_dash.data
    assert b'Read Teacher Msg' not in t_dash.data
    t_hub = client.get('/teacher/notifications')
    assert b'Unread Teacher Box' in t_hub.data
    assert b'Read Teacher Msg' in t_hub.data


def test_optional_comment_guest_code_generation_and_reuse(client, db, teacher_user, sample_subject, sample_page):
    """Guest comment codes are opt-in, 8 chars, reusable across comments, and separate from ExamGuest/Student."""
    db.session.add(SubjectTeacher(subject_id=sample_subject.id, teacher_id=teacher_user.id, is_primary=True, show_name=True))
    eg = ExamGuest(guest_code='EXAMONLY1', taker_name='Wrong Type', taker_birth_date=date(2002, 1, 1), taker_gender='male')
    db.session.add(eg)
    db.session.commit()

    # 1. Opt-out -> NO code generated
    client.post(f'/subject/{sample_subject.slug}/page/{sample_page.id}/comment', data={
        'guest_mode': 'details',
        'author_name': 'Nadia', 'author_birth_date': '2004-04-04',
        'comment_text': 'No code requested',
    })
    assert CommentGuest.query.count() == 0

    # 2. Opt-in -> 8-char code generated
    resp_gen = client.post(f'/subject/{sample_subject.slug}/page/{sample_page.id}/comment', data={
        'guest_mode': 'details',
        'author_name': 'Hoshiar', 'author_birth_date': '2003-03-03',
        'personality_info': 'Enjoys calculus',
        'generate_comment_code': '1',
        'comment_text': 'First comment with code',
    }, follow_redirects=True)
    assert CommentGuest.query.count() == 1
    cg = CommentGuest.query.first()
    assert len(cg.guest_code) >= 8
    assert cg.guest_code.encode() in resp_gen.data

    # 3. Reuse CommentGuest code without re-entering name/DOB
    resp_reuse = client.post(f'/subject/{sample_subject.slug}/page/{sample_page.id}/comment', data={
        'guest_mode': 'code',
        'comment_guest_code': cg.guest_code,
        'comment_text': 'Second comment via saved code',
    }, follow_redirects=True)
    assert resp_reuse.status_code == 200
    assert b'Second comment via saved code' in resp_reuse.data
    c2 = PageComment.query.filter_by(comment_text='Second comment via saved code').first()
    assert c2 is not None and c2.comment_guest_id == cg.id and c2.author_name == 'Hoshiar'

    # 4. ExamGuest code MUST NOT work for comment codes
    bad = client.post(f'/subject/{sample_subject.slug}/page/{sample_page.id}/comment', data={
        'guest_mode': 'code',
        'comment_guest_code': 'EXAMONLY1',
        'comment_text': 'Cross-table should fail',
    }, follow_redirects=True)
    assert b'Invalid Comment Guest Code' in bad.data


def test_optional_exam_guest_code_reuse_separation_and_21csv_backup(client, db, admin_user, teacher_user, sample_subject, sample_page, sample_questions):
    """ExamGuest codes are opt-in, reusable for public exams/quizzes, blocked on hidden student exams, and preserved in 21-CSV backup."""
    db.session.add(SubjectTeacher(subject_id=sample_subject.id, teacher_id=teacher_user.id, is_primary=True, show_name=True))
    quiz_q = Question(question_text='Quiz Q1', option_a='A', option_b='B', option_c='C', option_d='D',
                      correct_answer='A', subject_id=sample_subject.id, page_id=sample_page.id)
    pe = PrivateExam(subject_id=sample_subject.id, title='Restricted Link', access_token='PRIVTOKEN1234567', created_by_id=teacher_user.id)
    pq = PrivateQuestion(subject_id=sample_subject.id, question_text='Secret Q', option_a='1', option_b='2',
                         option_c='3', option_d='4', correct_answer='A')
    cg = CommentGuest(guest_code='COMMONLY1', author_name='Comment Only', author_birth_date=date(2002, 2, 2))
    db.session.add_all([quiz_q, pe, pq, cg])
    db.session.flush()
    db.session.add(PrivateExamQuestion(private_exam_id=pe.id, private_question_id=pq.id))
    db.session.commit()

    # 1. Opt-out guest exam -> no ExamGuest created
    client.post(f'/subject/{sample_subject.slug}/exam/submit', data={
        'taker_mode': 'guest', 'taker_birth_date': '2003-01-01', 'taker_gender': 'female',
        f'q_{sample_questions[0].id}': 'A',
    })
    assert ExamGuest.query.count() == 0

    # 2. Opt-in guest exam -> 8-char ExamGuest created, NOT Student
    gen_resp = client.post(f'/subject/{sample_subject.slug}/exam/submit', data={
        'taker_mode': 'guest', 'taker_name': 'Guest Taker', 'taker_birth_date': '2001-09-09',
        'taker_gender': 'male', 'generate_exam_guest_code': '1',
        f'q_{sample_questions[0].id}': 'A', f'q_{sample_questions[1].id}': 'A', f'q_{sample_questions[2].id}': 'A',
    }, follow_redirects=True)
    assert ExamGuest.query.count() == 1 and Student.query.count() == 0
    eg = ExamGuest.query.first()
    assert len(eg.guest_code) >= 8
    assert eg.guest_code.encode() in gen_resp.data

    # 3. Reuse ExamGuest code on Lecture Quiz without re-entering DOB/gender
    reuse_resp = client.post(f'/subject/{sample_subject.slug}/exam/submit', data={
        'page_id': str(sample_page.id),
        'taker_mode': 'guest_code',
        'exam_guest_code': eg.guest_code,
        f'q_{quiz_q.id}': 'A',
    }, follow_redirects=True)
    assert b'Examination Submitted. Score: 1/1 (100%)' in reuse_resp.data
    assert ExamResult.query.filter_by(page_id=sample_page.id, exam_guest_id=eg.id).count() == 1

    # 4. CommentGuest code is rejected as ExamGuest code
    bad_gc = client.post(f'/subject/{sample_subject.slug}/exam/submit', data={
        'taker_mode': 'guest_code', 'exam_guest_code': 'COMMONLY1', f'q_{sample_questions[0].id}': 'A',
    }, follow_redirects=True)
    assert b'Invalid Guest Exam Code' in bad_gc.data

    # 5. ExamGuest code CANNOT unlock PrivateExam or student-only exam
    deny_priv = client.post(f'/exam/link/{pe.access_token}/unlock', data={'student_code': eg.guest_code}, follow_redirects=True)
    assert b'Invalid or unauthorized Student Code' in deny_priv.data

    # 6. Full 21-CSV backup -> wipe -> restore preserves PrivateExam, PrivateQuestion, PrivateExamQuestion, CommentGuest, ExamGuest, and privacy flags
    teacher_user.profile_public = False
    teacher_user.profile_show_bio = False
    db.session.commit()

    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    zip_bytes = client.get('/admin/export/full_backup').data
    with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
        assert len(set(zf.namelist())) == 21

    client.post('/admin/system/wipe_clean', data={'confirm_wipe': 'y'})
    client.post('/setup', data={
        'username': 'Temp', 'email': 'tmp@test.com', 'password': 'tmppassword', 'confirm_password': 'tmppassword',
    })
    client.post('/login', data={'email': 'tmp@test.com', 'password': 'tmppassword'})
    client.post('/admin/system/restore', data={
        'backup_file': (io.BytesIO(zip_bytes), 'backup.zip'), 'confirm_wipe': 'y',
    }, content_type='multipart/form-data', follow_redirects=True)

    assert PrivateExam.query.filter_by(access_token='PRIVTOKEN1234567').count() == 1
    assert PrivateQuestion.query.filter_by(question_text='Secret Q').count() == 1
    assert PrivateExamQuestion.query.count() == 1
    assert CommentGuest.query.filter_by(guest_code='COMMONLY1').count() == 1
    assert ExamGuest.query.filter_by(guest_code=eg.guest_code).count() == 1
    restored_t = User.query.filter_by(email='teacher@test.com').first()
    assert restored_t.profile_public is False and restored_t.profile_show_bio is False
