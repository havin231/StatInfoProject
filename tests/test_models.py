"""
Tests for database models: creation, relationships, and data integrity.
"""
from app.models import User, Student, Subject, Page, Question, ExamResult, StudentAnswer
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


def test_student_creation(app, db, sample_student):
    """Student is created with access code and timestamps."""
    assert sample_student.id is not None
    assert sample_student.access_code == 'ABC123'
    assert sample_student.email == 'student@test.com'
    assert sample_student.created_at is not None


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


def test_exam_result_cascade(app, db, sample_student, sample_subject, sample_questions):
    """ExamResult + StudentAnswer cascade works correctly."""
    # Create an exam result
    result = ExamResult(
        score=67,
        student_id=sample_student.id,
        subject_id=sample_subject.id
    )
    db.session.add(result)
    db.session.flush()

    # Create student answers
    for q in sample_questions:
        answer = StudentAnswer(
            student_id=sample_student.id,
            question_id=q.id,
            exam_id=result.id,
            selected_option='A',
            is_correct=True
        )
        db.session.add(answer)
    db.session.commit()

    # Verify
    assert result.id is not None
    assert len(result.answers) == 3
    assert result.student.full_name == 'Test Student'
    assert result.subject.name == 'Mathematics'
