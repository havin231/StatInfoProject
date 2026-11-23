"""
Tests for v0.7.0 features:
1. Single locked theme (Cyber Command removed).
2. Multi-teacher subject assignment by admin.
3. No stale/former teachers shown + per-teacher individual name visibility.
4. Lecture comment system (name, age, optional personality, comment + moderation).
5. Scroll-preserving floating language toggle on lesson pages.
"""
from app import bcrypt
from app.models import User, SubjectTeacher, PageComment


def _create_second_teacher(db):
    pw_hash = bcrypt.generate_password_hash('teacher2pw').decode('utf-8')
    t2 = User(
        username='SecondTeacher',
        email='teacher2@test.com',
        password_hash=pw_hash,
        is_admin=False,
        show_name_on_subject=True,
    )
    db.session.add(t2)
    db.session.commit()
    return t2


def test_cyber_command_theme_removed(client, admin_user, teacher_user):
    """Cyber Command theme and theme switcher are completely removed."""
    # Public page
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'Cyber Command' not in resp.data
    assert b'setTheme(' not in resp.data
    assert b'data-theme="glass"' in resp.data

    # Admin dashboard
    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    resp_admin = client.get('/teacher/dashboard')
    assert resp_admin.status_code == 200
    assert b'Cyber Command' not in resp_admin.data
    assert b'setTheme(' not in resp_admin.data
    client.get('/logout')

    # Teacher dashboard
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    resp_teacher = client.get('/teacher/dashboard')
    assert resp_teacher.status_code == 200
    assert b'Cyber Command' not in resp_teacher.data
    assert b'setTheme(' not in resp_teacher.data


def test_multi_teacher_assignment_and_no_stale_teachers(client, db, admin_user, teacher_user, sample_subject):
    """Admin can assign multiple teachers; removing or transferring removes former teachers from display."""
    t2 = _create_second_teacher(db)
    teacher_user.show_name_on_subject = True
    db.session.commit()

    # Login as admin and assign BOTH teacher_user and t2 to sample_subject
    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    resp = client.post(
        f'/admin/subject/{sample_subject.id}/teachers',
        data={'teacher_ids': [str(teacher_user.id), str(t2.id)]},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Both should now be shown on the public subject page
    subj_page = client.get(f'/subject/{sample_subject.slug}')
    assert subj_page.status_code == 200
    assert b'TestTeacher' in subj_page.data
    assert b'SecondTeacher' in subj_page.data

    # Now unassign teacher_user so ONLY t2 is assigned
    resp2 = client.post(
        f'/admin/subject/{sample_subject.id}/teachers',
        data={'teacher_ids': [str(t2.id)]},
        follow_redirects=True,
    )
    assert resp2.status_code == 200

    subj_page2 = client.get(f'/subject/{sample_subject.slug}')
    assert b'SecondTeacher' in subj_page2.data
    assert b'TestTeacher' not in subj_page2.data

    # Transfer subject from t2 back to teacher_user -> t2 must no longer appear
    resp3 = client.post(
        f'/admin/transfer/subject/{sample_subject.id}',
        data={'new_teacher_id': str(teacher_user.id)},
        follow_redirects=True,
    )
    assert resp3.status_code == 200

    subj_page3 = client.get(f'/subject/{sample_subject.slug}')
    assert b'TestTeacher' in subj_page3.data
    assert b'SecondTeacher' not in subj_page3.data


def test_individual_teacher_name_visibility(client, db, admin_user, teacher_user, sample_subject):
    """Each teacher assigned to a subject can show/hide their name independently."""
    t2 = _create_second_teacher(db)
    db.session.add(SubjectTeacher(subject_id=sample_subject.id, teacher_id=teacher_user.id, is_primary=True, show_name=True))
    db.session.add(SubjectTeacher(subject_id=sample_subject.id, teacher_id=t2.id, is_primary=False, show_name=True))
    db.session.commit()

    # Teacher 1 hides their own name on this subject
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'teacher123'})
    resp = client.post(f'/subject/{sample_subject.id}/toggle_my_name', follow_redirects=True)
    assert resp.status_code == 200
    client.get('/logout')

    # Subject page should show SecondTeacher, NOT TestTeacher
    subj_page = client.get(f'/subject/{sample_subject.slug}')
    assert b'SecondTeacher' in subj_page.data
    assert b'TestTeacher' not in subj_page.data

    # Teacher 2 hides their name too -> neither shown, no "Taught by:" label
    client.post('/login', data={'email': 'teacher2@test.com', 'password': 'teacher2pw'})
    client.post(f'/subject/{sample_subject.id}/toggle_my_name', follow_redirects=True)
    client.get('/logout')

    subj_page_none = client.get(f'/subject/{sample_subject.slug}')
    assert b'SecondTeacher' not in subj_page_none.data
    assert b'TestTeacher' not in subj_page_none.data
    assert b'Taught by' not in subj_page_none.data


def test_lecture_comment_system(client, db, admin_user, sample_subject, sample_page):
    """Visitors can comment with name, age, optional personality, and comment; staff can delete."""
    # Valid comment WITH optional personality info
    resp = client.post(
        f'/subject/{sample_subject.slug}/page/{sample_page.id}/comment',
        data={
            'author_name': 'Ari',
            'author_age': '21',
            'personality_info': 'Curious math enthusiast',
            'comment_text': 'Great explanation of algebra!',
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b'Ari' in resp.data
    assert b'21' in resp.data
    assert b'Curious math enthusiast' in resp.data
    assert b'Great explanation of algebra!' in resp.data

    # Valid comment WITHOUT optional personality info
    resp2 = client.post(
        f'/subject/{sample_subject.slug}/page/{sample_page.id}/comment',
        data={
            'author_name': 'Dara',
            'author_age': '19',
            'personality_info': '',
            'comment_text': 'Very clear lecture.',
        },
        follow_redirects=True,
    )
    assert resp2.status_code == 200
    assert b'Dara' in resp2.data
    assert b'Very clear lecture.' in resp2.data

    # Missing required age -> rejected
    before_count = PageComment.query.filter_by(page_id=sample_page.id).count()
    assert before_count == 2
    client.post(
        f'/subject/{sample_subject.slug}/page/{sample_page.id}/comment',
        data={
            'author_name': 'NoAge',
            'author_age': '',
            'comment_text': 'Should fail',
        },
        follow_redirects=True,
    )
    assert PageComment.query.filter_by(page_id=sample_page.id).count() == 2

    # Admin can delete a comment
    comment = PageComment.query.filter_by(author_name='Ari').first()
    client.post('/login', data={'email': 'admin@test.com', 'password': 'admin123'})
    del_resp = client.post(f'/teacher/comment/delete/{comment.id}', follow_redirects=True)
    assert del_resp.status_code == 200
    assert PageComment.query.filter_by(page_id=sample_page.id).count() == 1


def test_lesson_scroll_preserving_language_toggle(client, sample_subject, sample_page):
    """Lesson page includes floating language toggle and scroll-preservation logic."""
    resp = client.get(f'/subject/{sample_subject.slug}/page/{sample_page.id}')
    assert resp.status_code == 200
    assert b'id="floatingLangToggle"' in resp.data
    assert b'/set-lang/ku' in resp.data
    assert b'lang_scroll_y' in resp.data
    assert b'lang_scroll_ratio' in resp.data
