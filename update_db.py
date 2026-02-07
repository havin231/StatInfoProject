from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Starting database migration...")
    
    # 1. Add 'email' column
    try:
        print("Adding 'email' column...")
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE student ADD COLUMN email VARCHAR(120) UNIQUE DEFAULT NULL"))
            conn.commit()
        print("✓ 'email' column added.")
    except Exception as e:
        print(f"⚠ Could not add 'email' column (might already exist): {e}")

    # 2. Add 'created_at' column
    try:
        print("Adding 'created_at' column...")
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE student ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
            conn.commit()
        print("✓ 'created_at' column added.")
    except Exception as e:
        print(f"⚠ Could not add 'created_at' column: {e}")

    # 3. Add 'updated_at' column
    try:
        print("Adding 'updated_at' column...")
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE student ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
            conn.commit()
        print("✓ 'updated_at' column added.")
    except Exception as e:
         # Fallback for SQLite or if ON UPDATE not supported easily in raw SQL without trigger
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE student ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
                conn.commit()
            print("✓ 'updated_at' column added (simple default).")
        except Exception as e2:
             print(f"⚠ Could not add 'updated_at' column: {e2}")

    print("Migration complete.")
