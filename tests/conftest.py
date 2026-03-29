"""
Shared test fixtures for the StatInfoPRO test suite.
Uses an in-memory SQLite database for isolated, fast testing.
"""
import pytest
from app import create_app, db as _db, bcrypt
from app.models import User, Student, Subject, Page, Question, ExamResult, StudentAnswer
from config import Config


class TestConfig(Config):
    """Override config for testing."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False  # Disable CSRF for test form submissions
    SERVER_NAME = 'localhost'
    # Disable rate limiting in tests
    RATELIMIT_ENABLED = False


@pytest.fixture(scope='function')
def app():
    """Create a fresh app instance for each test."""
    application = create_app(TestConfig)
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope='function')
def db(app):
    """Provide a database session."""
    return _db


@pytest.fixture(scope='function')
def client(app):
    """Provide a Flask test client."""
    return app.test_client()


@pytest.fixture(scope='function')
def admin_user(app, db):
    """Create an admin user for testing."""
    pw_hash = bcrypt.generate_password_hash('admin123').decode('utf-8')
    admin = User(
        username='TestAdmin',
        email='admin@test.com',
        password_hash=pw_hash,
        is_admin=True
    )
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture(scope='function')
def teacher_user(app, db):
    """Create a regular teacher user for testing."""
    pw_hash = bcrypt.generate_password_hash('teacher123').decode('utf-8')
    teacher = User(
        username='TestTeacher',
        email='teacher@test.com',
        password_hash=pw_hash,
        is_admin=False
    )
    db.session.add(teacher)
    db.session.commit()
    return teacher


@pytest.fixture(scope='function')
def sample_student(app, db):
    """Create a student for testing."""
    student = Student(
        full_name='Test Student',
        access_code='ABC123',
        email='student@test.com'
    )
    db.session.add(student)
    db.session.commit()
    return student


@pytest.fixture(scope='function')
def sample_subject(app, db, teacher_user):
    """Create a subject owned by teacher_user."""
    subject = Subject(
        name='Mathematics',
        slug='mathematics',
        description='A test math course',
        teacher_id=teacher_user.id,
        is_public=True
    )
    db.session.add(subject)
    db.session.commit()
    return subject


@pytest.fixture(scope='function')
def sample_page(app, db, sample_subject):
    """Create a lecture page in the sample subject."""
    page = Page(
        title='Lecture 1: Algebra',
        content_body='<p>Introduction to algebra.</p>',
        content_body_kurdish='<p>ناساندنی ئەلجەبرا</p>',
        subject_id=sample_subject.id
    )
    db.session.add(page)
    db.session.commit()
    return page


@pytest.fixture(scope='function')
def sample_questions(app, db, sample_subject):
    """Create 3 questions for the sample subject."""
    questions = []
    for i in range(3):
        q = Question(
            question_text=f'What is {i+1} + {i+1}?',
            option_a=str((i+1)*2),
            option_b=str((i+1)*3),
            option_c=str((i+1)*4),
            option_d=str((i+1)*5),
            correct_answer='A',
            subject_id=sample_subject.id
        )
        db.session.add(q)
        questions.append(q)
    db.session.commit()
    return questions
