"""
Tests for v0.8.0 features:
1. Complete Kurdish translations for new features.
2. Comment notifications sent to both Admins and assigned Teachers with full context.
3. Admin notification box dark mode fix (no hardcoded bg-light/text-dark).
4. Admin subject edit button directly on subject cards.
5. Admin direct messaging to teachers (visually distinct in teacher notifications).
6. Teacher & Admin optional birth date and bio fields.
7. Comment form uses birth date instead of raw age.
8. Teacher self-service profile editing (name, birth date, bio, password) in dashboard.
"""
from datetime import date
from app import bcrypt
from app.models import (
    User, SubjectTeacher, AdminNotification, TeacherNotification, PageComment
)


def test_comment_creates_admin_and_teacher_notifications(client, db, admin_user, teacher_user, sample_subject, sample_page):
    """Posting a lecture comment notifies both Admins and all assigned Teachers with full details."""
    db.session.add(SubjectTeacher(subject_id=sample_subject.id, teacher_id=teacher_user.id, is_primary=True, show_name=True))
    db.session.commit()

    resp = client.post(
        f'/subject/{sample_subject.slug}/page/{sample_page.id}/comment',
        data={
            'author_name': 'Soran',
            'author_birth_date': '2003-08-20',
            'personality_info': 'Loves statistics',
            'comment_text': 'Could you explain step 2 again?',
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Verify AdminNotification has full details
    admin_notifs = AdminNotification.query.filter_by(notification_type='comment_added').all()
    assert len(admin_notifs) == 1
    an = admin_notifs[0]
    assert sample_subject.name in an.message
    assert sample_page.title in an.message
    assert 'Soran' in an.message
    assert '2003-08-20' in an.message
    assert 'Loves statistics' in an.message
    assert 'Could you explain step 2 again?' in an.message

    # Verify TeacherNotification was created for teacher_user
    t_notifs = TeacherNotification.query.filter_by(teacher_id=teacher_user.id, notification_type='comment').all()
    assert len(t_notifs) == 1
    assert 'Soran' in t_notifs[0].message
    assert sample_page.title in t_notifs[0].message

    # Verify Admin dashboard displays the comment notification & has dark-mode safe markup + Edit button
    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    admin_dash = client.get('/teacher/dashboard')
    assert admin_dash.status_code == 200
    assert b'Soran' in admin_dash.data
    assert b'bg-light' not in admin_dash.data
    assert f'/teacher/edit/subject/{sample_subject.id}'.encode() in admin_dash.data


def test_admin_message_to_teacher_is_visually_distinct(client, db, admin_user, teacher_user):
    """Admin can message teachers and it renders distinctly in teacher notifications."""
    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    resp = client.post(
        '/admin/message_teacher',
        data={
            'recipient_id': str(teacher_user.id),
            'title': 'Exam Schedule Notice',
            'message': 'Please finalize midterm questions by Friday.',
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b'Message sent to TestTeacher' in resp.data
    client.get('/logout')

    # Verify teacher sees visually distinct admin_message notification
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    t_dash = client.get('/teacher/dashboard')
    assert t_dash.status_code == 200
    assert b'Admin Message' in t_dash.data
    assert b'bg-warning-subtle' in t_dash.data
    assert b'Exam Schedule Notice' in t_dash.data
    assert b'Please finalize midterm questions by Friday.' in t_dash.data

    # Teacher can mark read and dismiss
    notif = TeacherNotification.query.filter_by(teacher_id=teacher_user.id).first()
    assert notif.is_read is False
    client.post(f'/teacher/notification/{notif.id}/read')
    db.session.refresh(notif)
    assert notif.is_read is True

    client.post(f'/teacher/notification/{notif.id}/delete')
    assert TeacherNotification.query.get(notif.id) is None


def test_teacher_self_profile_update_name_birthdate_bio_password(client, db, teacher_user):
    """Teacher can update own name, Kurdish name, birth date, bio, and password from dashboard."""
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    resp = client.post(
        '/teacher/profile/update',
        data={
            'username': 'UpdatedTeacher',
            'username_kurdish': 'مامۆستای نوێ',
            'birth_date': '1992-04-12',
            'bio': 'Passionate mathematics instructor.',
            'new_password': 'newsecretpassword',
            'confirm_password': 'newsecretpassword',
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b'Your profile has been updated successfully' in resp.data

    db.session.refresh(teacher_user)
    assert teacher_user.username == 'UpdatedTeacher'
    assert teacher_user.username_kurdish == 'مامۆستای نوێ'
    assert teacher_user.birth_date == date(1992, 4, 12)
    assert teacher_user.bio == 'Passionate mathematics instructor.'
    assert bcrypt.check_password_hash(teacher_user.password_hash, 'newsecretpassword')

    # Log out and verify login works with the new password
    client.get('/logout')
    login_resp = client.post(
        '/login',
        data={'email': 'teacher@test.com', 'password': 'newsecretpassword'},
        follow_redirects=True,
    )
    assert login_resp.status_code == 200
    assert b'Logged in successfully' in login_resp.data


def test_comment_rejects_future_birth_date(client, db, sample_subject, sample_page):
    """Comment with a future birth date is rejected."""
    client.post(
        f'/subject/{sample_subject.slug}/page/{sample_page.id}/comment',
        data={
            'author_name': 'TimeTraveler',
            'author_birth_date': '2099-01-01',
            'comment_text': 'From the future',
        },
        follow_redirects=True,
    )
    assert PageComment.query.filter_by(author_name='TimeTraveler').count() == 0


def test_kurdish_translations_render_for_new_features(client, admin_user, sample_subject, sample_page):
    """Switching locale to Kurdish renders translated labels for comments, notifications, and messaging."""
    client.get('/set-lang/ku')
    page_resp = client.get(f'/subject/{sample_subject.slug}/page/{sample_page.id}')
    assert page_resp.status_code == 200
    assert 'گفتوگۆی وانە'.encode('utf-8') in page_resp.data
    assert 'بەرواری لەدایکبوونت'.encode('utf-8') in page_resp.data

    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    admin_resp = client.get('/teacher/dashboard')
    assert admin_resp.status_code == 200
    assert 'ئاگادارکردنەوەکانی بەڕێوەبەر'.encode('utf-8') in admin_resp.data
    assert 'پەیام ناردن بۆ مامۆستایان'.encode('utf-8') in admin_resp.data
