from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect 
from config import Config

# --- EXTENSION INITIALIZATION ---
# We create the extension instances here, but they are not attached to the app yet.
# They will be initialized inside the create_app function.

db = SQLAlchemy()
bcrypt = Bcrypt()
csrf = CSRFProtect()

login_manager = LoginManager()
# The login_view tells Flask-Login where to redirect users if they try to access a protected page.
# 'main.login' refers to the login route in the 'main' blueprint.
login_manager.login_view = 'main.login'
login_manager.login_message_category = 'info' # Bootstrap class for flash message

def create_app(config_class=Config):
    """
    Application Factory function.
    Creates and configures an instance of the Flask application.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # --- INITIALIZE EXTENSIONS ---
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app) # Enables global CSRF protection for forms

    # --- REGISTER BLUEPRINTS ---
    # Imports are placed here to avoid circular import errors.
    from app.routes import main
    app.register_blueprint(main)

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
            # Column already exists — this is expected after first run.
            pass

    return app
