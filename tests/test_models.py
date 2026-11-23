"""
Tests for database models: creation, relationships, and data integrity.
"""
from app.models import User, Subject, Page, Question, ExamResult
from app import bcrypt


def test_user_creation(app, db, admin_user):
    """Admin user is created with correct attributes."""
    assert admin_user.id is not None
    assert admin_user.username == 'TestAdmin'
    assert admin_user.is_admin is True


def test_user_password_hash(app, db, admin_user):
    """Password is hashed, not stored in plaintext."""
    assert admin_user.password_hash != 'admin123'
    assert bcrypt.check_password_hash(admin_user.password_hash, 'admin123')
    assert not bcrypt.check_password_hash(admin_user.password_hash, 'wrong_password')


def test_subject_teacher_relationship(app, db, sample_subject, teacher_user):
    """Subject is correctly linked to its teacher."""
    assert sample_subject.teacher_id == teacher_user.id
    assert sample_subject in teacher_user.subjects


def test_page_subject_relationship(app, db, sample_page, sample_subject):
    """Page belongs to the correct subject."""
    assert sample_page.subject_id == sample_subject.id
    assert sample_page in sample_subject.pages


def test_question_subject_relationship(app, db, sample_questions, sample_subject):
    """Questions are linked to the correct subject."""
    for q in sample_questions:
        assert q.subject_id == sample_subject.id
    assert len(sample_subject.questions) == 3


def test_exam_result_subject_relationship(app, db, sample_subject):
    """Anonymous ExamResult links cleanly to its Subject."""
    result = ExamResult(
        score=85,
        subject_id=sample_subject.id
    )
    db.session.add(result)
    db.session.commit()

    assert result.id is not None
    assert result.score == 85
    assert result.subject.name == 'Mathematics'
