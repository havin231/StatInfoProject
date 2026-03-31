from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from flask_babel import Babel, get_locale as babel_get_locale
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import session
from config import Config

def select_locale():
    # If the user is logged in natively (teacher/admin) or as student (stored in session somehow),
    # we can check request.
    from flask_login import current_user
    # Try to get from logged-in teacher/admin
    if current_user and current_user.is_authenticated and hasattr(current_user, 'preferred_lang'):
        return current_user.preferred_lang
    # Try to get from student logic
    # The student login system might just set 'student_id' in session
    student_id = session.get('student_id')
    if student_id:
        from app.models import Student
        student = db.session.get(Student, student_id)
        if student and student.preferred_lang:
            return student.preferred_lang
    return session.get('lang', 'en')

# --- EXTENSION INITIALIZATION ---
# We create the extension instances here, but they are not attached to the app yet.
# They will be initialized inside the create_app function.

db = SQLAlchemy()
bcrypt = Bcrypt()
csrf = CSRFProtect()
babel = Babel()
limiter = Limiter(key_func=get_remote_address, default_limits=[])

login_manager = LoginManager()
# The login_view tells Flask-Login where to redirect users if they try to access a protected page.
# 'auth.login' refers to the login route in the 'auth' blueprint.
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info' # Bootstrap class for flash message

def create_app(config_class=Config):
    """
    Application Factory function.
    Creates and configures an instance of the Flask application.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    @app.context_processor
    def inject_locale():
        return dict(get_locale=babel_get_locale)

    # --- INITIALIZE EXTENSIONS ---
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app) # Enables global CSRF protection for forms
    babel.init_app(app, locale_selector=select_locale)
    limiter.init_app(app)

    # --- REGISTER BLUEPRINTS ---
    # Imports are placed here to avoid circular import errors.
    from app.routes import all_blueprints
    for bp in all_blueprints:
        app.register_blueprint(bp)

    # --- DATABASE SETUP ---
    # Automatically create database tables if they don't exist.
    with app.app_context():
        db.create_all()

        # --- AUTO-MIGRATION ---
        # db.create_all() only creates NEW tables, it does NOT add new columns
        # to existing tables. This block handles that safely.
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE subject ADD COLUMN is_public BOOLEAN DEFAULT 1"))
                conn.commit()
            app.logger.info("Migration: 'is_public' column added to subject table.")
        except Exception:
            pass

        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE user ADD COLUMN preferred_lang VARCHAR(10) DEFAULT 'en'"))
                conn.execute(text("ALTER TABLE student ADD COLUMN preferred_lang VARCHAR(10) DEFAULT 'en'"))
                conn.commit()
            app.logger.info("Migration: 'preferred_lang' column added to user and student tables.")
        except Exception:
            pass

    return app
