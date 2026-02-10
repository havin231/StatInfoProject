from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Starting database migration for 'is_public' column on Subject table...")
    
    try:
        with db.engine.connect() as conn:
            # Check if column exists first to avoid error? 
            # Or just try to add it. MySQL might error if it exists.
            # Simple approach: Try to add it.
            conn.execute(text("ALTER TABLE subject ADD COLUMN is_public BOOLEAN DEFAULT 1"))
            conn.commit()
        print("✓ 'is_public' column added successfully.")
    except Exception as e:
        print(f"⚠ Could not add 'is_public' column (might already exist): {e}")

    print("Migration complete.")
