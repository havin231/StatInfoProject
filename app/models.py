from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin

@login_manager.user_loader
def load_user(user_id):
    """
    Flask-Login helper to retrieve a user object from the database
    using the user_id stored in the session.
    """
    return User.query.get(int(user_id))

# ==========================================
# 1. USER MODEL (Teachers & Admins)
# ==========================================
class User(db.Model, UserMixin):
    """
    Represents the staff members of the system.
    Can be a regular Teacher or a System Administrator.
    """
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)

    # Permission Flag: If True, user can manage other users and global settings
    is_admin = db.Column(db.Boolean, default=False)

    # NEW: Display name on subject pages (with teacher's consent)
    show_name_on_subject = db.Column(db.Boolean, default=False)

    # NEW: Kurdish name for bilingual display
    username_kurdish = db.Column(db.String(20), nullable=True)

    # Preferred Language for UI (e.g., 'en', 'ku')
    preferred_lang = db.Column(db.String(10), default='en')

    # Relationship: A teacher teaches many Subjects
    subjects = db.relationship('Subject', backref='teacher', lazy=True)

    def __repr__(self):
        return f"User('{self.username}', Admin: {self.is_admin})"

# ==========================================
# 2. SUBJECT MODEL
# ==========================================
class Subject(db.Model):
    """
    Represents a specific course (e.g., 'Physics 101').
    Acts as a container for Pages and Questions.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    # URL-friendly identifier (e.g., 'physics-101')
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Visibility Flag: If False, subject is hidden from public home page
    is_public = db.Column(db.Boolean, default=True)

    # Foreign Key: Link to the Teacher who owns this subject
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relationships: Children of this Subject
    pages = db.relationship('Page', backref='subject', lazy=True)
    questions = db.relationship('Question', backref='subject', lazy=True)
    results = db.relationship('ExamResult', backref='subject', lazy=True)

    # Bilingual Support: Kurdish translations
    name_kurdish = db.Column(db.String(100), nullable=True)
    description_kurdish = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"Subject('{self.name}', Slug: {self.slug})"

# ==========================================
# 4. PAGE MODEL (Study Material / Lectures)
# ==========================================
class Page(db.Model):
    """
    Represents a single lesson or study page within a Subject.
    Supports bilingual content (English & Kurdish).
    """
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)

    # Content Body: Stores HTML content from the Rich Text Editor
    content_body = db.Column(db.Text, nullable=False)
    content_body_kurdish = db.Column(db.Text, nullable=True)

    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)

    # TASK 4 Relationship: Links questions specifically to this lecture/chapter
    questions = db.relationship('Question', backref='page', lazy=True)

    # Resources: Multiple links per page
    resources = db.relationship('Resource', backref='page', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"Page('{self.title}', Subject ID: {self.subject_id})"

# ==========================================
# 5. RESOURCE MODEL (Multiple Links)
# ==========================================
class Resource(db.Model):
    """
    Stores multiple external links for a single Page.
    Added in Phase 4 Update.
    Supports bilingual titles (English & Kurdish).
    """
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False) # e.g. "Watch Video"
    title_kurdish = db.Column(db.String(100), nullable=True)  # Kurdish translation
    link = db.Column(db.String(500), nullable=False)  # The URL
    page_id = db.Column(db.Integer, db.ForeignKey('page.id'), nullable=False)

    def __repr__(self):
        return f"Resource('{self.title}', Page ID: {self.page_id})"

# ==========================================
# 6. QUESTION MODEL (Bank)
# ==========================================
class Question(db.Model):
    """
    Represents a multiple-choice question in the Question Bank.
    """
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)

    # The 4 multiple-choice options
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)

    # The correct answer key: 'A', 'B', 'C', or 'D'
    correct_answer = db.Column(db.String(1), nullable=False)

    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)

    # TASK 4: Optional link to a specific Page/Lecture.
    # If NULL, this is a general subject question.
    # If assigned, it only appears in that lecture's quiz.
    page_id = db.Column(db.Integer, db.ForeignKey('page.id'), nullable=True)

    # NEW: Flag for Kurdish Language (Default False/English)
    is_kurdish = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"Question('{self.question_text[:20]}...', Correct: {self.correct_answer})"

# ==========================================
# 6. EXAM RESULT MODEL (Anonymous Summary)
# ==========================================
class ExamResult(db.Model):
    """
    Represents the final score of an anonymous exam attempt.
    """
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, nullable=False) # Percentage (0-100)
    date_submitted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)

    def __repr__(self):
        return f"Result(Subject: {self.subject_id}, Score: {self.score})"

# ==========================================
# 7. SITE INFO MODEL (CMS)
# ==========================================
class SiteInfo(db.Model):
    """
    Stores static site content managed by the Admin.
    Example key: 'about' for the About Us page.
    """
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False) # Unique identifier
    title = db.Column(db.String(100), default="About Us")
    content = db.Column(db.Text, nullable=True) # HTML content
    content_kurdish = db.Column(db.Text, nullable=True)  # Kurdish translation
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ==========================================
# 10. SYSTEM COMMANDS (Documentation)
# ==========================================
class SystemCommand(db.Model):
    """
    Stores server maintenance commands for the Admin Command Center.
    Allows dynamic adding/editing of help commands.
    Supports bilingual content (English & Kurdish).
    """
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False) # e.g. "Restart Server"
    title_kurdish = db.Column(db.String(100), nullable=True)  # Kurdish translation
    command_text = db.Column(db.Text, nullable=False) # e.g. "touch /var/www/..."
    description = db.Column(db.Text, nullable=True)   # Instructions on when to use
    description_kurdish = db.Column(db.Text, nullable=True)  # Kurdish translation

    def __repr__(self):
        return f"Command('{self.title}')"

# ==========================================
# 11. TOOL MODEL (ToolBase)
# ==========================================
class Tool(db.Model):
    """
    Represents an external toollink/page added by the Admin.
    Supports bilingual content (English & Kurdish).
    """
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    title_kurdish = db.Column(db.String(100), nullable=True)  # Kurdish translation
    link = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=True)
    description_kurdish = db.Column(db.Text, nullable=True)  # Kurdish translation
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"Tool('{self.title}')"


# ==========================================
# 10. ADMIN NOTIFICATION MODEL (v0.5.0)
# ==========================================
class AdminNotification(db.Model):
    """
    Stores notifications for admin about system activity.
    Added in v0.5.0 - Feature 3: Admin Notifications.
    """
    NOTIFICATION_TYPES = [
        'question_added', 'question_edited',
        'page_added', 'page_edited'
    ]

    id = db.Column(db.Integer, primary_key=True)

    # Notification content
    notification_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)

    # Actor information (who triggered the notification)
    actor_type = db.Column(db.String(20))  # 'teacher', 'system'
    actor_id = db.Column(db.Integer)
    actor_name = db.Column(db.String(100))

    # Related objects (for linking)
    related_subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)
    related_page_id = db.Column(db.Integer, db.ForeignKey('page.id'), nullable=True)
    related_question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=True)

    # Status and deletion timer
    is_checked = db.Column(db.Boolean, default=False)
    checked_at = db.Column(db.DateTime, nullable=True)
    delete_scheduled_at = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    related_subject = db.relationship('Subject', foreign_keys=[related_subject_id])
    related_page = db.relationship('Page', foreign_keys=[related_page_id])
    related_question = db.relationship('Question', foreign_keys=[related_question_id])

    def __repr__(self):
        return f"AdminNotification({self.notification_type}: {self.title})"


# ==========================================
# 15. SUBJECT TEACHER MODEL (v0.5.0)
# ==========================================
class SubjectTeacher(db.Model):
    """
    Association table linking subjects to multiple teachers.
    Added in v0.5.0 - Feature 6: Multi-Teacher Subjects.
    Replaces the single teacher_id foreign key on Subject.
    """
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)  # Original creator
    show_name = db.Column(db.Boolean, default=True)    # Per-subject visibility
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    subject = db.relationship('Subject', backref='teacher_assignments')
    teacher = db.relationship('User', backref='subject_assignments')

    # Unique constraint - one assignment per teacher per subject
    __table_args__ = (db.UniqueConstraint('subject_id', 'teacher_id'),)

    def __repr__(self):
        return f"SubjectTeacher(Subject: {self.subject_id}, Teacher: {self.teacher_id}, Primary: {self.is_primary})"
