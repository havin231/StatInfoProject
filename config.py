import os
from dotenv import load_dotenv

# Get the directory where this config file is located
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Load environment variables from .env file in project root
env_path = os.path.join(BASE_DIR, '.env')
load_dotenv(env_path)

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'academic-minimalist-secure-key-2025'

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///dev.db'

    # FIX: This recycles database connections to prevent timeouts
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True
    }

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')

    # --- BABEL / i18n CONFIGURATION ---
    BABEL_DEFAULT_LOCALE = 'en'
    BABEL_TRANSLATION_DIRECTORIES = os.path.join(BASE_DIR, 'app', 'translations')
    LANGUAGES = ['en', 'ku']