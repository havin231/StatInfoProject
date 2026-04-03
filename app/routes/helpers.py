import secrets
import string


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
