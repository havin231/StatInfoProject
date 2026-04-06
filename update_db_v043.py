"""
Database Migration Script v0.4.3
Adds Kurdish bilingual columns to Subject, Resource, SystemCommand, and Tool models.

Run this script to update the database schema:
    python update_db_v043.py
"""

from app import create_app, db
from app.models import Subject, Resource, SystemCommand, Tool
from sqlalchemy import text

def migrate():
    """Add Kurdish columns to support bilingual content."""
    app = create_app()
    
    with app.app_context():
        # Check if columns already exist before adding
        inspector = db.inspect(db.engine)
        
        # 1. Subject table - add name_kurdish and description_kurdish
        subject_columns = [col['name'] for col in inspector.get_columns('subject')]
        
        if 'name_kurdish' not in subject_columns:
            print("Adding 'name_kurdish' column to Subject table...")
            db.session.execute(text('ALTER TABLE subject ADD COLUMN name_kurdish VARCHAR(100)'))
        else:
            print("Column 'name_kurdish' already exists in Subject table.")
            
        if 'description_kurdish' not in subject_columns:
            print("Adding 'description_kurdish' column to Subject table...")
            db.session.execute(text('ALTER TABLE subject ADD COLUMN description_kurdish TEXT'))
        else:
            print("Column 'description_kurdish' already exists in Subject table.")
        
        # 2. Resource table - add title_kurdish
        resource_columns = [col['name'] for col in inspector.get_columns('resource')]
        
        if 'title_kurdish' not in resource_columns:
            print("Adding 'title_kurdish' column to Resource table...")
            db.session.execute(text('ALTER TABLE resource ADD COLUMN title_kurdish VARCHAR(100)'))
        else:
            print("Column 'title_kurdish' already exists in Resource table.")
        
        # 3. SystemCommand table - add title_kurdish and description_kurdish
        command_columns = [col['name'] for col in inspector.get_columns('system_command')]
        
        if 'title_kurdish' not in command_columns:
            print("Adding 'title_kurdish' column to SystemCommand table...")
            db.session.execute(text('ALTER TABLE system_command ADD COLUMN title_kurdish VARCHAR(100)'))
        else:
            print("Column 'title_kurdish' already exists in SystemCommand table.")
            
        if 'description_kurdish' not in command_columns:
            print("Adding 'description_kurdish' column to SystemCommand table...")
            db.session.execute(text('ALTER TABLE system_command ADD COLUMN description_kurdish TEXT'))
        else:
            print("Column 'description_kurdish' already exists in SystemCommand table.")
        
        # 4. Tool table - add title_kurdish and description_kurdish
        tool_columns = [col['name'] for col in inspector.get_columns('tool')]
        
        if 'title_kurdish' not in tool_columns:
            print("Adding 'title_kurdish' column to Tool table...")
            db.session.execute(text('ALTER TABLE tool ADD COLUMN title_kurdish VARCHAR(100)'))
        else:
            print("Column 'title_kurdish' already exists in Tool table.")
            
        if 'description_kurdish' not in tool_columns:
            print("Adding 'description_kurdish' column to Tool table...")
            db.session.execute(text('ALTER TABLE tool ADD COLUMN description_kurdish TEXT'))
        else:
            print("Column 'description_kurdish' already exists in Tool table.")
        
        # Commit all changes
        db.session.commit()
        print("\n✅ Migration completed successfully!")
        print("Kurdish bilingual columns have been added to the database.")

if __name__ == '__main__':
    migrate()
