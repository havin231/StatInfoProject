from flask import current_app
from flask_mail import Message
from jinja2 import Template
import secrets
import string

def send_welcome_email(user):
    """
    PHASE 1 & 4: Sends a welcome email to a new teacher/admin.
    Uses dynamic templates stored in SiteInfo.
    """
    from app.models import SiteInfo
    from app import db
    
    site_info = SiteInfo.query.filter_by(key='about').first()
    if not site_info or not site_info.welcome_email_body:
        # Fallback if no template is defined
        subject = "Welcome to StatInfoProject"
        body = f"Hello {user.username},\n\nYour account has been created.\nEmail: {user.email}"
    else:
        try:
            subject_tmpl = Template(site_info.welcome_email_subject or "Welcome to StatInfoProject")
            body_tmpl = Template(site_info.welcome_email_body)
            
            context = {
                'username': user.username,
                'email': user.email,
                'site_url': current_app.config.get('SITE_URL', 'http://localhost:5000')
            }
            
            subject = subject_tmpl.render(**context)
            body = body_tmpl.render(**context)
        except Exception as e:
            current_app.logger.error(f"Email template rendering failed: {e}")
            subject = "Welcome to StatInfoProject"
            body = f"Hello {user.username}, welcome to the platform."

    try:
        msg = Message(subject,
                    recipients=[user.email],
                    html=body if '<html>' in body.lower() else None,
                    body=body if '<html>' not in body.lower() else None)
        current_app.extensions['mail'].send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send welcome email: {e}")
        return False

def generate_access_code(length=8):
    """
    Generates a cryptographically secure random alphanumeric code.
    Updated for Phase 1: 8 characters, non-sequential.
    """
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
