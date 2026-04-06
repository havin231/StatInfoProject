"""
Database Migration Script for v0.4.4
Adds username_kurdish column to user table for bilingual teacher names.

Usage:
    python update_db_v044.py

This script safely adds the username_kurdish column if it doesn't exist.
"""

import sys
import os

# Add the project directory to path
sys.path.insert(0, '/home/StatInfoProject/StatInfoProject')

from app import create_app, db
from sqlalchemy import text

def migrate():
    """Add username_kurdish column to user table."""
    app = create_app()
    
    with app.app_context():
        # Check if column already exists
        try:
            db.session.execute(text("SELECT username_kurdish FROM user LIMIT 1"))
            print("✓ Column 'username_kurdish' already exists. No migration needed.")
            return
        except Exception as e:
            if "Unknown column" in str(e) or "doesn't exist" in str(e):
                print("→ Column 'username_kurdish' does not exist. Adding it now...")
            else:
                print(f"✗ Unexpected error checking column: {e}")
                return
        
        # Add the column
        try:
            db.session.execute(text("""
                ALTER TABLE user 
                ADD COLUMN username_kurdish VARCHAR(20) NULL 
                AFTER show_name_on_subject
            """))
            db.session.commit()
            print("✓ Successfully added 'username_kurdish' column to user table.")
            print("  - Type: VARCHAR(20)")
            print("  - Nullable: YES")
            print("  - Position: After show_name_on_subject")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error adding column: {e}")
            return

if __name__ == "__main__":
    print("=" * 60)
    print("StatInfoProject v0.4.4 Database Migration")
    print("Adding username_kurdish column to user table")
    print("=" * 60)
    migrate()
    print("=" * 60)
