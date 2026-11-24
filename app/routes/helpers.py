import secrets
from flask import url_for
from flask_login import current_user
from flask_babel import gettext as _


def can_edit_subject(subject, user=current_user):
    """
    Check if a user can edit a subject.

    v0.5.0 - Multi-Teacher Support:
    - Admin can edit any subject
    - Primary teacher (original creator) can edit
    - Any co-teacher assigned to the subject can edit

    Args:
        subject: Subject model instance
        user: User model instance (defaults to current_user)

    Returns:
        bool: True if user has edit permission, False otherwise
    """
    # Admin can edit anything
    if user.is_admin:
        return True

    # Check if user is in the subject's teacher assignments
    from app.models import SubjectTeacher
    assignment = SubjectTeacher.query.filter_by(
        subject_id=subject.id,
        teacher_id=user.id
    ).first()

    return assignment is not None


def _generate_unique_8char_code(length=8):
    """
    Generate an unambiguous uppercase alphanumeric code guaranteed unique across
    Student, CommentGuest, and ExamGuest code tables.
    """
    from app.models import Student, CommentGuest, ExamGuest
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    code_len = max(8, length)
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(code_len))
        if (
            not Student.query.filter_by(student_code=code).first()
            and not CommentGuest.query.filter_by(guest_code=code).first()
            and not ExamGuest.query.filter_by(guest_code=code).first()
        ):
            return code


def generate_student_code(length=8):
    """Generates a cryptographically secure, unique student code (>= 8 chars)."""
    return _generate_unique_8char_code(length)


def generate_comment_guest_code(length=8):
    """Generates a separate 8-char code for lecture comment guests."""
    return _generate_unique_8char_code(length)


def generate_exam_guest_code(length=8):
    """Generates a separate 8-char code for public exam/quiz guests."""
    return _generate_unique_8char_code(length)


def generate_private_exam_token(length=16):
    """Generates a unique URL-safe token for a hidden PrivateExam link."""
    from app.models import PrivateExam
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
    tok_len = max(12, length)
    while True:
        token = ''.join(secrets.choice(alphabet) for _ in range(tok_len))
        if not PrivateExam.query.filter_by(access_token=token).first():
            return token


def can_student_access_subject(student, subject):
    """
    Verify that a Student is authorized to take hidden/restricted exams in `subject`.
    Returns True if `StudentTeacher` links `student.id` to `subject.teacher_id` OR to
    any teacher currently assigned to `subject` via `SubjectTeacher`.
    """
    if not student or not subject:
        return False
    from app.models import StudentTeacher, SubjectTeacher
    subject_teacher_ids = {
        st.teacher_id for st in SubjectTeacher.query.filter_by(subject_id=subject.id).all()
    }
    if subject.teacher_id:
        subject_teacher_ids.add(subject.teacher_id)

    if not subject_teacher_ids:
        return False

    link = StudentTeacher.query.filter(
        StudentTeacher.student_id == student.id,
        StudentTeacher.teacher_id.in_(subject_teacher_ids)
    ).first()
    return link is not None


def _should_show_teacher_in_comment(comment, subject):
    """Determine whether a teacher/admin comment/reply reveals the author's name publicly."""
    if not comment or not comment.is_teacher_reply or not comment.author_user:
        return False
    user = comment.author_user
    from app.models import SubjectTeacher
    assign = SubjectTeacher.query.filter_by(
        subject_id=subject.id,
        teacher_id=user.id
    ).first()
    if assign:
        return bool(assign.show_name)
    return bool(user.show_name_on_subject)


def get_reply_display_name(comment, subject, lang='en'):
    """
    Return the public display name for a teacher/admin comment or reply on a lecture.
    If the teacher has chosen to hide their name (`show_name=False`),
    returns localized 'From Teacher' so anonymity is preserved.
    """
    if not comment or not comment.is_teacher_reply:
        return comment.author_name if comment else ''

    user = comment.author_user
    if not user:
        return _('From Teacher')

    if _should_show_teacher_in_comment(comment, subject):
        return user.display_name(lang)

    return _('From Teacher')


def get_comment_author_profile_url(comment, subject):
    """
    Return public profile URL for a visible teacher comment/reply if their profile is public.
    """
    if not _should_show_teacher_in_comment(comment, subject):
        return None
    user = comment.author_user
    if not user or not bool(user.profile_public):
        return None
    return url_for('public.teacher_public_profile', user_id=user.id)
