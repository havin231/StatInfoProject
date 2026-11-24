import secrets
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


def generate_student_code(length=8):
    """
    Generates a cryptographically secure, unique student code of at least `length` characters
    using unambiguous uppercase alphanumeric characters.
    """
    from app.models import Student
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    code_len = max(8, length)
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(code_len))
        if not Student.query.filter_by(student_code=code).first():
            return code


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


def get_reply_display_name(comment, subject, lang='en'):
    """
    Return the public display name for a teacher/admin reply on a lecture comment.
    If the teacher has chosen to hide their name on this subject (`show_name=False`),
    returns localized 'From Teacher' so anonymity is preserved.
    """
    if not comment or not comment.is_teacher_reply:
        return comment.author_name if comment else ''

    user = comment.author_user
    if not user:
        return _('From Teacher')

    from app.models import SubjectTeacher
    assign = SubjectTeacher.query.filter_by(
        subject_id=subject.id,
        teacher_id=user.id
    ).first()

    show = False
    if assign:
        show = bool(assign.show_name)
    elif user.is_admin and user.show_name_on_subject:
        show = True

    if show:
        return user.username_kurdish if (lang == 'ku' and user.username_kurdish) else user.username

    return _('From Teacher')
