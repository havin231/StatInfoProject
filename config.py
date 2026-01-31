import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'academic-minimalist-secure-key-2025'

    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://StatInfoProject:stat123123@StatInfoProject.mysql.pythonanywhere-services.com/StatInfoProject$school_db'

    # FIX: This recycles database connections to prevent timeouts
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True
    }

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')