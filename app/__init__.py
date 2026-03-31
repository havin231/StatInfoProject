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
    """
    Locale selector for Flask-Babel.
    Priority: 1. Session  2. DB (Teacher/Admin)  3. DB (Student)  4. Default 'en'
    
    IMPORTANT: Session ALWAYS takes priority so the language toggle works immediately.
    The DB value is only used as a fallback for users who haven't toggled yet
    (e.g., fresh login from a new browser).
    """
    from flask import current_app, has_request_context
    from flask_login import current_user

    VALID_LOCALES = {'en', 'ku'}

    current_app.logger.debug(f"select_locale() called, has_request_context: {has_request_context()}")

    # Check if we're in request context before accessing session
    if has_request_context():
        # 1. SESSION FIRST — single source of truth for the toggle
        lang = session.get('lang')
        current_app.logger.debug(f"select_locale() session.get('lang'): {lang}")
        if lang and lang in VALID_LOCALES:
            current_app.logger.debug(f"select_locale() returning from session: {lang}")
            return lang
        else:
            current_app.logger.debug(f"select_locale() session lang invalid or missing: {lang}")

        # 3. DB THIRD — Student preferred_lang (fallback only)
        student_id = session.get('student_id')
        if student_id:
            try:
                from app.models import Student
                student = db.session.get(Student, student_id)
                if student and student.preferred_lang and student.preferred_lang in VALID_LOCALES:
                    current_app.logger.debug(f"select_locale() returning from student DB: {student.preferred_lang}")
                    return student.preferred_lang
            except Exception:
                pass
    else:
        current_app.logger.debug("select_locale() no request context, skipping session checks")

    # 2. DB SECOND — Teacher/Admin preferred_lang (fallback only)
    try:
        if current_user and current_user.is_authenticated and hasattr(current_user, 'preferred_lang'):
            db_lang = current_user.preferred_lang
            if db_lang and db_lang in VALID_LOCALES:
                current_app.logger.debug(f"select_locale() returning from user DB: {db_lang}")
                return db_lang
    except Exception:
        pass

    # 4. DEFAULT
    current_app.logger.debug("select_locale() returning default: en")
    return 'en'

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
