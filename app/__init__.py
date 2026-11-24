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
    Priority: 1. Session  2. DB (Teacher/Admin)  3. Default 'en'

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

    # 3. DEFAULT
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
                conn.commit()
            app.logger.info("Migration: 'preferred_lang' column added to user table.")
        except Exception:
            pass

        # v0.8.0 & v0.9.0 safe auto-migrations (SQLite + MySQL compatible)
        for stmt in [
            "ALTER TABLE user ADD COLUMN birth_date DATE",
            "ALTER TABLE user ADD COLUMN bio TEXT",
            "ALTER TABLE user ADD COLUMN gender VARCHAR(20)",
            "ALTER TABLE user MODIFY COLUMN username VARCHAR(100) NOT NULL",
            "ALTER TABLE user MODIFY COLUMN username_kurdish VARCHAR(100) NULL",
            "ALTER TABLE subject ADD COLUMN exam_student_only BOOLEAN DEFAULT 0",
            "ALTER TABLE page ADD COLUMN title_kurdish VARCHAR(200)",
            "ALTER TABLE page ADD COLUMN quiz_student_only BOOLEAN DEFAULT 0",
            "ALTER TABLE site_info ADD COLUMN title_kurdish VARCHAR(200)",
            "ALTER TABLE question ADD COLUMN question_text_kurdish TEXT",
            "ALTER TABLE question ADD COLUMN option_a_kurdish VARCHAR(200)",
            "ALTER TABLE question ADD COLUMN option_b_kurdish VARCHAR(200)",
            "ALTER TABLE question ADD COLUMN option_c_kurdish VARCHAR(200)",
            "ALTER TABLE question ADD COLUMN option_d_kurdish VARCHAR(200)",
            "ALTER TABLE exam_result ADD COLUMN correct_count INTEGER",
            "ALTER TABLE exam_result ADD COLUMN total_questions INTEGER",
            "ALTER TABLE exam_result ADD COLUMN page_id INTEGER",
            "ALTER TABLE exam_result ADD COLUMN student_record_id INTEGER",
            "ALTER TABLE exam_result ADD COLUMN taker_name VARCHAR(100)",
            "ALTER TABLE exam_result ADD COLUMN taker_birth_date DATE",
            "ALTER TABLE exam_result ADD COLUMN taker_gender VARCHAR(20)",
            "ALTER TABLE exam_result MODIFY COLUMN student_id INTEGER NULL",
            "ALTER TABLE page_comment ADD COLUMN author_birth_date DATE",
            "ALTER TABLE page_comment ADD COLUMN parent_id INTEGER",
            "ALTER TABLE page_comment ADD COLUMN author_user_id INTEGER",
            "ALTER TABLE page_comment ADD COLUMN is_teacher_reply BOOLEAN DEFAULT 0",
            "ALTER TABLE page_comment ADD COLUMN is_read_by_admin BOOLEAN DEFAULT 0",
            "ALTER TABLE user ADD COLUMN profile_public BOOLEAN DEFAULT 1",
            "ALTER TABLE user ADD COLUMN profile_show_name BOOLEAN DEFAULT 1",
            "ALTER TABLE user ADD COLUMN profile_show_bio BOOLEAN DEFAULT 1",
            "ALTER TABLE user ADD COLUMN profile_show_age BOOLEAN DEFAULT 1",
            "ALTER TABLE user ADD COLUMN profile_show_gender BOOLEAN DEFAULT 1",
            "ALTER TABLE page_comment ADD COLUMN comment_guest_id INTEGER",
            "ALTER TABLE exam_result ADD COLUMN private_exam_id INTEGER",
            "ALTER TABLE exam_result ADD COLUMN exam_guest_id INTEGER",
        ]:
            try:
                with db.engine.connect() as conn:
                    conn.execute(text(stmt))
                    conn.commit()
            except Exception:
                pass

    return app
