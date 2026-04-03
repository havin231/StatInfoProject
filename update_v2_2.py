import os
from app import db, create_app
from app.models import Subject, SiteInfo
from sqlalchemy import text

def run_migration():
    app = create_app()
    with app.app_context():
        print("Starting Migration v2.2...")
        
        # 1. Add consent_to_display_name to User
        try:
            db.session.execute(text("ALTER TABLE user ADD COLUMN consent_to_display_name BOOLEAN DEFAULT 1"))
            db.session.commit()
            print("Added 'consent_to_display_name' to 'user' table.")
        except Exception as e:
            db.session.rollback()
            print(f"Note: 'consent_to_display_name' might already exist or: {e}")

        # 2. Add bypass_id_req to Student
        try:
            db.session.execute(text("ALTER TABLE student ADD COLUMN bypass_id_req BOOLEAN DEFAULT 0"))
            db.session.commit()
            print("Added 'bypass_id_req' to 'student' table.")
        except Exception as e:
            db.session.rollback()
            print(f"Note: 'bypass_id_req' might already exist or: {e}")

        # 3. Add title_kurdish, content_kurdish, and email fields to SiteInfo
        new_siteinfo_cols = [
            ("title_kurdish", "VARCHAR(100)"),
            ("content_kurdish", "TEXT"),
            ("welcome_email_subject", "VARCHAR(200)"),
            ("welcome_email_body", "TEXT"),
            ("teacher_alert_body", "TEXT")
        ]
        
        for col_name, col_type in new_siteinfo_cols:
            try:
                db.session.execute(text(f"ALTER TABLE site_info ADD COLUMN {col_name} {col_type}"))
                db.session.commit()
                print(f"Added '{col_name}' to 'site_info' table.")
            except Exception as e:
                db.session.rollback()
                print(f"Note: '{col_name}' might already exist or: {e}")

        # 4. Populate default SiteInfo keys for email templates
        about_page = SiteInfo.query.filter_by(key='about').first()
        if not about_page:
            about_page = SiteInfo(key='about', title='About Us', content='Welcome to StatInfoProject.')
            db.session.add(about_page)
            print("Created default 'about' SiteInfo entry.")
        
        if not about_page.welcome_email_subject:
            about_page.welcome_email_subject = "Welcome to StatInfoProject, {username}!"
        if not about_page.welcome_email_body:
            about_page.welcome_email_body = "<h1>Welcome {username}!</h1><p>Your account has been created successfully.</p><p>Login at: {site_url}</p>"
        
        db.session.commit()
        print("Populated default email templates.")
        print("Migration v2.2 complete.")

if __name__ == "__main__":
    run_migration()
