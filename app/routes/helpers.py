from flask_login import current_user


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
