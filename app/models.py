from datetime import datetime, date
from app import db, login_manager
from flask_login import UserMixin


def calculate_age(birth_date):
    """Return integer age in years for a given date, or None."""
    if not birth_date:
        return None
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

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
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)

    # Permission Flag: If True, user can manage other users and global settings
    is_admin = db.Column(db.Boolean, default=False)

    # NEW: Display name on subject pages (with teacher's consent)
    show_name_on_subject = db.Column(db.Boolean, default=False)

    # NEW: Kurdish name for bilingual display
    username_kurdish = db.Column(db.String(100), nullable=True)

    # Preferred Language for UI (e.g., 'en', 'ku')
    preferred_lang = db.Column(db.String(10), default='en')

    # Profile Info (v0.8.0 / v0.9.0 / v0.9.1): Optional Gender, Birth Date, Bio & Privacy
    gender = db.Column(db.String(20), nullable=True)
    birth_date = db.Column(db.Date, nullable=True)
    bio = db.Column(db.Text, nullable=True)

    profile_public = db.Column(db.Boolean, default=True)
    profile_show_name = db.Column(db.Boolean, default=True)
    profile_show_bio = db.Column(db.Boolean, default=True)
    profile_show_age = db.Column(db.Boolean, default=True)
    profile_show_gender = db.Column(db.Boolean, default=True)

    # Relationship: A teacher teaches many Subjects
    subjects = db.relationship('Subject', backref='teacher', lazy=True)

    def display_name(self, lang='en'):
        return self.username_kurdish if (lang == 'ku' and self.username_kurdish) else self.username

    @property
    def age(self):
        return calculate_age(self.birth_date)

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

    # Restriction Flag (v0.9.0): If True, Final Exam is hidden & requires an authorized Student Code
    exam_student_only = db.Column(db.Boolean, default=False)

    # Foreign Key: Link to the Teacher who owns this subject
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relationships: Children of this Subject
    pages = db.relationship('Page', backref='subject', lazy=True)
    questions = db.relationship('Question', backref='subject', lazy=True)
    results = db.relationship('ExamResult', backref='subject', lazy=True)

    # Bilingual Support: Kurdish translations
    name_kurdish = db.Column(db.String(100), nullable=True)
    description_kurdish = db.Column(db.Text, nullable=True)

    def display_name(self, lang='en'):
        return self.name_kurdish if (lang == 'ku' and self.name_kurdish) else self.name

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
    title = db.Column(db.String(200), nullable=False)
    title_kurdish = db.Column(db.String(200), nullable=True)

    # Content Body: Stores HTML content from the Rich Text Editor
    content_body = db.Column(db.Text, nullable=False)
    content_body_kurdish = db.Column(db.Text, nullable=True)

    # Restriction Flag (v0.9.0): If True, Lecture Quiz is hidden & requires an authorized Student Code
    quiz_student_only = db.Column(db.Boolean, default=False)

    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)

    # TASK 4 Relationship: Links questions specifically to this lecture/chapter
    questions = db.relationship('Question', backref='page', lazy=True)

    # Resources: Multiple links per page
    resources = db.relationship('Resource', backref='page', lazy=True, cascade="all, delete-orphan")

    # Comments: Public visitor comments on this lecture
    comments = db.relationship('PageComment', backref='page', lazy=True, cascade="all, delete-orphan")

    def display_title(self, lang='en'):
        return self.title_kurdish if (lang == 'ku' and self.title_kurdish) else self.title

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
    Supports dual English & Kurdish faces (v0.9.0).
    """
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    question_text_kurdish = db.Column(db.Text, nullable=True)

    # The 4 multiple-choice options (English)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)

    # The 4 multiple-choice options (Kurdish face)
    option_a_kurdish = db.Column(db.String(200), nullable=True)
    option_b_kurdish = db.Column(db.String(200), nullable=True)
    option_c_kurdish = db.Column(db.String(200), nullable=True)
    option_d_kurdish = db.Column(db.String(200), nullable=True)

    # The correct answer key: 'A', 'B', 'C', or 'D'
    correct_answer = db.Column(db.String(1), nullable=False)

    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)

    # Optional link to a specific Page/Lecture.
    page_id = db.Column(db.Integer, db.ForeignKey('page.id'), nullable=True)

    # Legacy fallback flag for Kurdish Language
    is_kurdish = db.Column(db.Boolean, default=False)

    def get_text(self, lang='en'):
        if lang == 'ku':
            return self.question_text_kurdish or self.question_text
        return self.question_text or self.question_text_kurdish

    def get_option(self, letter, lang='en'):
        letter = (letter or 'A').upper()
        en_map = {'A': self.option_a, 'B': self.option_b, 'C': self.option_c, 'D': self.option_d}
        ku_map = {'A': self.option_a_kurdish, 'B': self.option_b_kurdish, 'C': self.option_c_kurdish, 'D': self.option_d_kurdish}
        if lang == 'ku':
            return ku_map.get(letter) or en_map.get(letter, '')
        return en_map.get(letter) or ku_map.get(letter, '')

    def use_rtl(self, lang='en'):
        return (lang == 'ku' and bool(self.question_text_kurdish)) or bool(self.question_text_kurdish and not self.question_text)

    def __repr__(self):
        return f"Question('{self.question_text[:20]}...', Correct: {self.correct_answer})"

# ==========================================
# 6. EXAM RESULT MODEL (Live Stats & Attempt Log)
# ==========================================
class ExamResult(db.Model):
    """
    Represents the final score of a visitor or student's exam/quiz attempt.
    """
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, nullable=False) # Percentage (0-100)
    correct_count = db.Column(db.Integer, nullable=True)
    total_questions = db.Column(db.Integer, nullable=True)
    date_submitted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False, index=True)
    page_id = db.Column(db.Integer, db.ForeignKey('page.id'), nullable=True)  # NULL = Final Exam, set = Lecture Quiz
    private_exam_id = db.Column(db.Integer, db.ForeignKey('private_exam.id'), nullable=True)
    student_record_id = db.Column(db.Integer, db.ForeignKey('student_record.id'), nullable=True, index=True)
    exam_guest_id = db.Column(db.Integer, db.ForeignKey('exam_guest.id'), nullable=True, index=True)

    # Guest taker info (when not using a Student Code)
    taker_name = db.Column(db.String(100), nullable=True)
    taker_birth_date = db.Column(db.Date, nullable=True)
    taker_gender = db.Column(db.String(20), nullable=True)

    # Relationships
    page = db.relationship('Page', foreign_keys=[page_id])
    private_exam = db.relationship('PrivateExam', foreign_keys=[private_exam_id], backref='results')
    student_record = db.relationship('Student', foreign_keys=[student_record_id], backref='exam_results')
    exam_guest = db.relationship('ExamGuest', foreign_keys=[exam_guest_id], backref='exam_results')

    @property
    def taker_age(self):
        if self.student_record:
            return self.student_record.age
        if self.exam_guest:
            return self.exam_guest.age
        return calculate_age(self.taker_birth_date)

    @property
    def resolved_gender(self):
        if self.student_record:
            return self.student_record.gender
        if self.exam_guest:
            return self.exam_guest.taker_gender
        return self.taker_gender

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
    title = db.Column(db.String(200), default="About Us")
    title_kurdish = db.Column(db.String(200), nullable=True)
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
        'page_added', 'page_edited',
        'teacher_message', 'teacher_request',
        'comment_added'
    ]

    id = db.Column(db.Integer, primary_key=True)

    # Notification content
    notification_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)

    # Actor information (who triggered the notification)
    actor_type = db.Column(db.String(20))  # 'teacher', 'visitor', 'system'
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


# ==========================================
# 12. PAGE COMMENT MODEL (v0.7.0 / v0.8.0 / v0.9.0)
# ==========================================
class PageComment(db.Model):
    """
    Represents a public comment or teacher/admin reply on a Lecture (Page).
    Requires author name, birth date, and comment text; personality_info is optional.
    """
    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.Integer, db.ForeignKey('page.id'), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('page_comment.id'), nullable=True, index=True)
    author_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    comment_guest_id = db.Column(db.Integer, db.ForeignKey('comment_guest.id'), nullable=True)
    is_teacher_reply = db.Column(db.Boolean, default=False)
    is_read_by_admin = db.Column(db.Boolean, default=False, index=True)

    author_name = db.Column(db.String(100), nullable=False)
    author_birth_date = db.Column(db.Date, nullable=True)
    author_age = db.Column(db.Integer, nullable=True)
    personality_info = db.Column(db.Text, nullable=True)
    comment_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    replies = db.relationship(
        'PageComment',
        backref=db.backref('parent', remote_side=[id]),
        lazy=True,
        order_by='PageComment.created_at.asc()'
    )
    author_user = db.relationship('User', foreign_keys=[author_user_id])
    comment_guest = db.relationship('CommentGuest', foreign_keys=[comment_guest_id], backref='comments')

    @property
    def display_age(self):
        if self.author_birth_date:
            return calculate_age(self.author_birth_date)
        return self.author_age

    def __repr__(self):
        return f"PageComment('{self.author_name}', Born: {self.author_birth_date}, Page ID: {self.page_id})"


# ==========================================
# 13. TEACHER NOTIFICATION MODEL (v0.8.0)
# ==========================================
class TeacherNotification(db.Model):
    """
    Stores notifications for individual teachers:
    - 'comment': New visitor comment posted on one of their lectures.
    - 'admin_message': Direct announcement/message written by an Admin (visually distinct).
    """
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    notification_type = db.Column(db.String(30), nullable=False, default='comment')
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)

    related_subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)
    related_page_id = db.Column(db.Integer, db.ForeignKey('page.id'), nullable=True)

    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    teacher = db.relationship('User', foreign_keys=[teacher_id], backref='notifications')
    sender = db.relationship('User', foreign_keys=[sender_id])
    related_subject = db.relationship('Subject', foreign_keys=[related_subject_id])
    related_page = db.relationship('Page', foreign_keys=[related_page_id])

    def __repr__(self):
        return f"TeacherNotification({self.notification_type} -> Teacher {self.teacher_id}: {self.title})"


# ==========================================
# 14. TEACHER SIGNUP REQUEST MODEL (v0.9.0)
# ==========================================
class TeacherRequest(db.Model):
    """
    Public teacher registration requests awaiting Admin approval.
    """
    __tablename__ = 'teacher_request'

    id = db.Column(db.Integer, primary_key=True)
    name_en = db.Column(db.String(100), nullable=False)
    name_ku = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    password_hash = db.Column(db.String(60), nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    bio = db.Column(db.Text, nullable=True)
    reason = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    admin_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id])

    @property
    def age(self):
        return calculate_age(self.birth_date)

    def __repr__(self):
        return f"TeacherRequest('{self.name_en}', Status: {self.status})"


# ==========================================
# 15. STUDENT RECORD MODEL (v0.9.0 - Code-Based, No Login)
# ==========================================
class Student(db.Model):
    """
    Code-based student records managed by Teachers & Admins (no password/login).
    Named 'student_record' to avoid colliding with any legacy pre-v0.6.1 MySQL 'student' table.
    """
    __tablename__ = 'student_record'

    id = db.Column(db.Integer, primary_key=True)
    name_en = db.Column(db.String(100), nullable=False)
    name_ku = db.Column(db.String(100), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    department_en = db.Column(db.String(100), nullable=False)
    department_ku = db.Column(db.String(100), nullable=False)
    student_code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    created_by = db.relationship('User', foreign_keys=[created_by_id])

    @property
    def age(self):
        return calculate_age(self.birth_date)

    def display_name(self, lang='en'):
        return self.name_ku if (lang == 'ku' and self.name_ku) else self.name_en

    def display_department(self, lang='en'):
        return self.department_ku if (lang == 'ku' and self.department_ku) else self.department_en

    def __repr__(self):
        return f"Student('{self.name_en}', Code: {self.student_code})"


# ==========================================
# 16. STUDENT-TEACHER ASSIGNMENT MODEL (v0.9.0)
# ==========================================
class StudentTeacher(db.Model):
    """
    Links code-based Students to authorized Teachers.
    Admins can share students across multiple teachers so one code unlocks
    multiple teachers' hidden exams and appears in their stats.
    """
    __tablename__ = 'student_teacher'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_record.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('Student', backref=db.backref('teacher_links', lazy=True))
    teacher = db.relationship('User', backref=db.backref('student_links', lazy=True))

    __table_args__ = (db.UniqueConstraint('student_id', 'teacher_id'),)

    def __repr__(self):
        return f"StudentTeacher(Student: {self.student_id}, Teacher: {self.teacher_id})"


# ==========================================
# 17. PRIVATE / HIDDEN EXAMS & QUESTION BANK (v0.9.1)
# ==========================================
class PrivateExam(db.Model):
    """
    Auto-generated link for hidden student-only exams & quizzes.
    Multiple PrivateQuestions can be assigned to one or more PrivateExams.
    """
    __tablename__ = 'private_exam'

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    title_kurdish = db.Column(db.String(200), nullable=True)
    access_token = db.Column(db.String(32), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subject = db.relationship('Subject', backref=db.backref('private_exams', lazy=True))
    created_by = db.relationship('User', foreign_keys=[created_by_id])

    def display_title(self, lang='en'):
        return self.title_kurdish if (lang == 'ku' and self.title_kurdish) else self.title

    @property
    def assigned_questions(self):
        return [
            link.private_question
            for link in sorted(self.question_links, key=lambda l: l.id)
            if link.private_question is not None
        ]

    def __repr__(self):
        return f"PrivateExam('{self.title}', Token: {self.access_token})"


class PrivateQuestion(db.Model):
    """
    Dedicated question bank sheet for hidden/private exam links.
    Separate from the public Question table.
    """
    __tablename__ = 'private_question'

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False, index=True)
    question_text = db.Column(db.Text, nullable=False)
    question_text_kurdish = db.Column(db.Text, nullable=True)

    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)

    option_a_kurdish = db.Column(db.String(200), nullable=True)
    option_b_kurdish = db.Column(db.String(200), nullable=True)
    option_c_kurdish = db.Column(db.String(200), nullable=True)
    option_d_kurdish = db.Column(db.String(200), nullable=True)

    correct_answer = db.Column(db.String(1), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subject = db.relationship('Subject', backref=db.backref('private_questions', lazy=True))

    def get_text(self, lang='en'):
        return Question.get_text(self, lang)

    def get_option(self, letter, lang='en'):
        return Question.get_option(self, letter, lang)

    def use_rtl(self, lang='en'):
        return (lang == 'ku' and bool(self.question_text_kurdish)) or bool(self.question_text_kurdish and not self.question_text)

    def __repr__(self):
        return f"PrivateQuestion('{self.question_text[:20]}...', Correct: {self.correct_answer})"


class PrivateExamQuestion(db.Model):
    """Many-to-many link assigning PrivateQuestions to one or more PrivateExam links."""
    __tablename__ = 'private_exam_question'

    id = db.Column(db.Integer, primary_key=True)
    private_exam_id = db.Column(db.Integer, db.ForeignKey('private_exam.id'), nullable=False, index=True)
    private_question_id = db.Column(db.Integer, db.ForeignKey('private_question.id'), nullable=False, index=True)

    private_exam = db.relationship('PrivateExam', backref=db.backref('question_links', lazy=True))
    private_question = db.relationship('PrivateQuestion', backref=db.backref('exam_links', lazy=True))

    __table_args__ = (db.UniqueConstraint('private_exam_id', 'private_question_id'),)


# ==========================================
# 18. GUEST COMMENT & GUEST EXAM CODE MODELS (v0.9.1)
# ==========================================
class CommentGuest(db.Model):
    """
    Separate optional 8-char identity codes for lecture comment guests so they do not
    need to re-enter their details every time they comment.
    """
    __tablename__ = 'comment_guest'

    id = db.Column(db.Integer, primary_key=True)
    guest_code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    author_name = db.Column(db.String(100), nullable=False)
    author_birth_date = db.Column(db.Date, nullable=False)
    personality_info = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"CommentGuest('{self.author_name}', Code: {self.guest_code})"


class ExamGuest(db.Model):
    """
    Separate optional 8-char identity codes for public exam/quiz guests
    (strictly separate from registered Student codes and CommentGuest codes).
    """
    __tablename__ = 'exam_guest'

    id = db.Column(db.Integer, primary_key=True)
    guest_code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    taker_name = db.Column(db.String(100), nullable=True)
    taker_birth_date = db.Column(db.Date, nullable=False)
    taker_gender = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def age(self):
        return calculate_age(self.taker_birth_date)

    def __repr__(self):
        return f"ExamGuest('{self.taker_name or 'Guest'}', Code: {self.guest_code})"
