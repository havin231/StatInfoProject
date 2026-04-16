import secrets
import string
from flask_login import current_user


def generate_access_code(length=6):
    """
    Generates a cryptographically secure random alphanumeric code.
    Used for student login tokens to ensure unique identification.

    Args:
        length (int): Length of the code. Default is 6 characters.

    Returns:
        str: A random string like 'A9X2B1'.
    """
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


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
