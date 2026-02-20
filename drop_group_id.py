from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE student DROP COLUMN group_id;"))
            conn.commit()
            print("Successfully dropped group_id column.")
    except Exception as e:
        print(f"Error dropping group_id: {e}")
