"""
Database Migration Script for v0.5.0
Adds 5 new tables for major feature implementation:
1. student_pinned_subject - Student pinning subjects
2. lesson_progress - Track lesson completion
3. admin_notification - Admin activity notifications
4. subject_teacher - Multi-teacher subject support
5. exam_progress - Progressive exam submission tracking

Usage:
    python update_db_v050.py
"""

import sys
import os

# Add the project directory to path
sys.path.insert(0, '/home/havin/Documents/statinfopro/StatInfoProject_PlayGround')

from app import create_app, db
from sqlalchemy import text, inspect

def table_exists(table_name):
    """Check if a table already exists in the database."""
    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        return table_name in inspector.get_table_names()

def create_student_pinned_subject():
    """Create student_pinned_subject table."""
    if table_exists('student_pinned_subject'):
        print("✓ Table 'student_pinned_subject' already exists. Skipping.")
        return
    
    app = create_app()
    with app.app_context():
        try:
            db.session.execute(text("""
                CREATE TABLE student_pinned_subject (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    student_id INT NOT NULL,
                    subject_id INT NOT NULL,
                    pinned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES student(id) ON DELETE CASCADE,
                    FOREIGN KEY (subject_id) REFERENCES subject(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_pin (student_id, subject_id),
                    INDEX idx_student (student_id),
                    INDEX idx_subject (subject_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """))
            db.session.commit()
            print("✓ Created 'student_pinned_subject' table")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error creating student_pinned_subject: {e}")

def create_lesson_progress():
    """Create lesson_progress table."""
    if table_exists('lesson_progress'):
        print("✓ Table 'lesson_progress' already exists. Skipping.")
        return
    
    app = create_app()
    with app.app_context():
        try:
            db.session.execute(text("""
                CREATE TABLE lesson_progress (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    student_id INT NOT NULL,
                    page_id INT NOT NULL,
                    is_completed BOOLEAN DEFAULT FALSE,
                    completed_at DATETIME NULL,
                    FOREIGN KEY (student_id) REFERENCES student(id) ON DELETE CASCADE,
                    FOREIGN KEY (page_id) REFERENCES page(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_progress (student_id, page_id),
                    INDEX idx_student (student_id),
                    INDEX idx_page (page_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """))
            db.session.commit()
            print("✓ Created 'lesson_progress' table")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error creating lesson_progress: {e}")

def create_admin_notification():
    """Create admin_notification table."""
    if table_exists('admin_notification'):
        print("✓ Table 'admin_notification' already exists. Skipping.")
        return
    
    app = create_app()
    with app.app_context():
        try:
            db.session.execute(text("""
                CREATE TABLE admin_notification (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    notification_type VARCHAR(50) NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    message TEXT NOT NULL,
                    actor_type VARCHAR(20) NULL,
                    actor_id INT NULL,
                    actor_name VARCHAR(100) NULL,
                    related_subject_id INT NULL,
                    related_page_id INT NULL,
                    related_question_id INT NULL,
                    is_checked BOOLEAN DEFAULT FALSE,
                    checked_at DATETIME NULL,
                    delete_scheduled_at DATETIME NULL,
                    is_deleted BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (related_subject_id) REFERENCES subject(id) ON DELETE SET NULL,
                    FOREIGN KEY (related_page_id) REFERENCES page(id) ON DELETE SET NULL,
                    FOREIGN KEY (related_question_id) REFERENCES question(id) ON DELETE SET NULL,
                    INDEX idx_type (notification_type),
                    INDEX idx_checked (is_checked),
                    INDEX idx_created (created_at),
                    INDEX idx_delete_scheduled (delete_scheduled_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """))
            db.session.commit()
            print("✓ Created 'admin_notification' table")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error creating admin_notification: {e}")

def create_subject_teacher():
    """Create subject_teacher association table."""
    if table_exists('subject_teacher'):
        print("✓ Table 'subject_teacher' already exists. Skipping.")
        return
    
    app = create_app()
    with app.app_context():
        try:
            db.session.execute(text("""
                CREATE TABLE subject_teacher (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    subject_id INT NOT NULL,
                    teacher_id INT NOT NULL,
                    is_primary BOOLEAN DEFAULT FALSE,
                    show_name BOOLEAN DEFAULT TRUE,
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (subject_id) REFERENCES subject(id) ON DELETE CASCADE,
                    FOREIGN KEY (teacher_id) REFERENCES user(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_teacher_subject (subject_id, teacher_id),
                    INDEX idx_subject (subject_id),
                    INDEX idx_teacher (teacher_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """))
            db.session.commit()
            print("✓ Created 'subject_teacher' table")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error creating subject_teacher: {e}")

def create_exam_progress():
    """Create exam_progress table."""
    if table_exists('exam_progress'):
        print("✓ Table 'exam_progress' already exists. Skipping.")
        return
    
    app = create_app()
    with app.app_context():
        try:
            db.session.execute(text("""
                CREATE TABLE exam_progress (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    student_id INT NOT NULL,
                    subject_id INT NOT NULL,
                    page_id INT NULL,
                    submitted_answers JSON NULL,
                    locked_questions JSON NULL,
                    is_completed BOOLEAN DEFAULT FALSE,
                    completed_at DATETIME NULL,
                    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES student(id) ON DELETE CASCADE,
                    FOREIGN KEY (subject_id) REFERENCES subject(id) ON DELETE CASCADE,
                    FOREIGN KEY (page_id) REFERENCES page(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_exam_attempt (student_id, subject_id, page_id),
                    INDEX idx_student (student_id),
                    INDEX idx_subject (subject_id),
                    INDEX idx_completed (is_completed)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """))
            db.session.commit()
            print("✓ Created 'exam_progress' table")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error creating exam_progress: {e}")

def migrate_existing_teachers():
    """Migrate existing subject.teacher_id to subject_teacher table."""
    app = create_app()
    with app.app_context():
        try:
            # Check if subject table has teacher_id column
            result = db.session.execute(text("""
                SELECT COUNT(*) as count 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'subject' 
                AND COLUMN_NAME = 'teacher_id'
            """)).fetchone()
            
            if result[0] == 0:
                print("✓ subject.teacher_id column already removed. Skipping migration.")
                return
            
            # Migrate existing data
            print("→ Migrating existing teacher assignments to subject_teacher table...")
            db.session.execute(text("""
                INSERT INTO subject_teacher (subject_id, teacher_id, is_primary, show_name, added_at)
                SELECT id, teacher_id, TRUE, TRUE, NOW()
                FROM subject
                WHERE teacher_id IS NOT NULL
                AND id NOT IN (SELECT subject_id FROM subject_teacher)
            """))
            db.session.commit()
            print("✓ Migrated existing teacher assignments")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error migrating teachers: {e}")

def migrate():
    """Run all migrations."""
    print("→ Creating new tables...")
    create_student_pinned_subject()
    create_lesson_progress()
    create_admin_notification()
    create_subject_teacher()
    create_exam_progress()
    
    print("\n→ Migrating existing data...")
    migrate_existing_teachers()
    
    print("\n✓ Migration v0.5.0 complete!")
    print("\nNext steps:")
    print("  1. Update app/models.py with new model classes")
    print("  2. Update SKILL.md with new schema documentation")
    print("  3. Restart the application")

if __name__ == "__main__":
    print("=" * 60)
    print("StatInfoProject v0.5.0 Database Migration")
    print("Adding tables for pinned subjects, lesson progress,")
    print("admin notifications, multi-teachers, and exam progress")
    print("=" * 60)
    migrate()
    print("=" * 60)
