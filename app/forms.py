from datetime import date
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField, SelectField, DateField
from wtforms.validators import DataRequired, Email, Length, Optional, EqualTo, ValidationError
from flask_babel import lazy_gettext as _l


def validate_birth_date(form, field):
    """Ensure a birth date is realistic (not in the future, age between 5 and 120)."""
    if not field.data:
        return
    today = date.today()
    if field.data > today:
        raise ValidationError(_l('Birth date cannot be in the future.'))
    age = today.year - field.data.year - ((today.month, today.day) < (field.data.month, field.data.day))
    if age < 5 or age > 120:
        raise ValidationError(_l('Please enter a valid birth date (age must be between 5 and 120).'))

# ==========================================
# 1. AUTHENTICATION & SETUP
# ==========================================

class LoginForm(FlaskForm):
    """
    Form for staff/admin login.
    """
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Password'), validators=[DataRequired()])
    remember = BooleanField(_l('Remember Me'))
    submit = SubmitField(_l('Login'))

class SetupForm(FlaskForm):
    """
    Form for the initial system setup (creating the first Headmaster).
    """
    username = StringField(_l('Headmaster Name'), validators=[DataRequired()])
    email = StringField(_l('Email Address'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Password'), validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(_l('Confirm Password'), validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField(_l('Create System Admin'))

# ==========================================
# 2. ADMIN & USER MANAGEMENT
# ==========================================

GENDER_CHOICES_OPTIONAL = [
    ('', _l('Prefer not to say / Optional')),
    ('male', _l('Male')),
    ('female', _l('Female')),
]

GENDER_CHOICES_REQUIRED = [
    ('', _l('Select Gender')),
    ('male', _l('Male')),
    ('female', _l('Female')),
]


class TeacherSignupForm(FlaskForm):
    """
    Form for Admins to create new staff accounts.
    """
    username = StringField(_l('Teacher Name'), validators=[DataRequired(), Length(max=100)])
    username_kurdish = StringField(_l('Teacher Name (Kurdish)'), validators=[Optional(), Length(max=100)])
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Password'), validators=[DataRequired(), Length(min=6)])
    gender = SelectField(_l('Gender (Optional)'), choices=GENDER_CHOICES_OPTIONAL, validators=[Optional()])
    birth_date = DateField(_l('Birth Date (Optional)'), format='%Y-%m-%d', validators=[Optional(), validate_birth_date])
    bio = TextAreaField(_l('Bio (Optional)'), validators=[Optional(), Length(max=500)])
    is_admin = BooleanField(_l('Grant Admin Access'))
    submit = SubmitField(_l('Create Account'))

class TeacherEditForm(FlaskForm):
    """
    Form for editing existing staff.
    """
    username = StringField(_l('Teacher Name'), validators=[DataRequired(), Length(max=100)])
    username_kurdish = StringField(_l('Teacher Name (Kurdish)'), validators=[Optional(), Length(max=100)])
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Reset Password (Optional)'), validators=[Optional(), Length(min=6)])
    gender = SelectField(_l('Gender (Optional)'), choices=GENDER_CHOICES_OPTIONAL, validators=[Optional()])
    birth_date = DateField(_l('Birth Date (Optional)'), format='%Y-%m-%d', validators=[Optional(), validate_birth_date])
    bio = TextAreaField(_l('Bio (Optional)'), validators=[Optional(), Length(max=500)])
    is_admin = BooleanField(_l('Grant Admin Access'))
    show_name_on_subject = BooleanField(_l('Show my name on subject pages'))
    profile_public = BooleanField(_l('Make my teacher profile public'), default=True)
    profile_show_name = BooleanField(_l('Show my name on profile'), default=True)
    profile_show_bio = BooleanField(_l('Show my bio on profile'), default=True)
    profile_show_age = BooleanField(_l('Show my age on profile'), default=True)
    profile_show_gender = BooleanField(_l('Show my gender on profile'), default=True)
    submit = SubmitField(_l('Update Account'))

class TeacherProfileForm(FlaskForm):
    """
    Form for teachers (and admins) to edit their own profile from their dashboard.
    """
    username = StringField(_l('Full Name'), validators=[DataRequired(), Length(min=1, max=100)])
    username_kurdish = StringField(_l('Full Name (Kurdish)'), validators=[Optional(), Length(max=100)])
    gender = SelectField(_l('Gender (Optional)'), choices=GENDER_CHOICES_OPTIONAL, validators=[Optional()])
    birth_date = DateField(_l('Birth Date (Optional)'), format='%Y-%m-%d', validators=[Optional(), validate_birth_date])
    bio = TextAreaField(_l('Bio (Optional)'), validators=[Optional(), Length(max=500)])
    profile_public = BooleanField(_l('Make my teacher profile public'), default=True)
    profile_show_name = BooleanField(_l('Show my name on profile'), default=True)
    profile_show_bio = BooleanField(_l('Show my bio on profile'), default=True)
    profile_show_age = BooleanField(_l('Show my age on profile'), default=True)
    profile_show_gender = BooleanField(_l('Show my gender on profile'), default=True)
    new_password = PasswordField(_l('New Password (Optional)'), validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField(
        _l('Confirm New Password'),
        validators=[Optional(), EqualTo('new_password', message=_l('Passwords must match.'))]
    )
    submit = SubmitField(_l('Save Profile'))

class AdminMessageForm(FlaskForm):
    """
    Form for Admins to send a visually distinct notification message to teachers.
    """
    recipient_id = SelectField(_l('Send To'), coerce=int)
    title = StringField(_l('Message Subject'), validators=[DataRequired(), Length(min=1, max=200)])
    message = TextAreaField(_l('Message'), validators=[DataRequired(), Length(min=1, max=2000)])
    submit = SubmitField(_l('Send Message'))

# ==========================================
# 3. SITE CONTENT (CMS)
# ==========================================

class InfoPageForm(FlaskForm):
    """
    Form for editing static pages like 'About Us'.
    """
    title = StringField(_l('Page Title'), default="About Us", validators=[DataRequired()])
    title_kurdish = StringField(_l('Page Title (Kurdish)'), validators=[Optional()])
    content = TextAreaField(_l('Page Content (English)'), validators=[DataRequired()])
    content_kurdish = TextAreaField(_l('Page Content (Kurdish)'), validators=[Optional()])
    submit = SubmitField(_l('Save Page'))

# ==========================================
# 4. ACADEMIC CONTENT
# ==========================================

class SubjectForm(FlaskForm):
    """
    Form for creating/editing Subjects.
    """
    name = StringField(_l('Subject Name'), validators=[DataRequired()])
    name_kurdish = StringField(_l('Subject Name (Kurdish)'), validators=[Optional()])
    slug = StringField(_l('Unique Slug (e.g. math-101)'), validators=[DataRequired()])
    description = TextAreaField(_l('Description'), validators=[DataRequired()])
    description_kurdish = TextAreaField(_l('Description (Kurdish)'), validators=[Optional()])
    teacher_id = SelectField(_l('Assign Teacher'), coerce=int)
    submit = SubmitField(_l('Create Subject'))

class PageForm(FlaskForm):
    """
    Form for creating study materials (Lectures/Chapters).
    """
    subject_id = SelectField(_l('Select Subject'), coerce=int, validators=[DataRequired()])
    title = StringField(_l('Page Title'), validators=[DataRequired()])
    title_kurdish = StringField(_l('Page Title (Kurdish)'), validators=[Optional()])
    content_body = TextAreaField(_l('Content (English)'), validators=[DataRequired()])
    content_body_kurdish = TextAreaField(_l('Content (Kurdish)'), validators=[Optional()])
    submit = SubmitField(_l('Publish Content'))

class QuestionForm(FlaskForm):
    """
    Form for adding/editing a single bilingual question (English and/or Kurdish faces).
    """
    subject_id = SelectField(_l('Subject'), coerce=int, validators=[DataRequired()])
    page_id = SelectField(_l('Link to Specific Lecture (Optional)'), coerce=int)

    question_text = TextAreaField(_l('Question (English)'), validators=[Optional()])
    option_a = StringField(_l('Option A (English)'), validators=[Optional()])
    option_b = StringField(_l('Option B (English)'), validators=[Optional()])
    option_c = StringField(_l('Option C (English)'), validators=[Optional()])
    option_d = StringField(_l('Option D (English)'), validators=[Optional()])

    question_text_kurdish = TextAreaField(_l('Question (Kurdish)'), validators=[Optional()])
    option_a_kurdish = StringField(_l('Option A (Kurdish)'), validators=[Optional()])
    option_b_kurdish = StringField(_l('Option B (Kurdish)'), validators=[Optional()])
    option_c_kurdish = StringField(_l('Option C (Kurdish)'), validators=[Optional()])
    option_d_kurdish = StringField(_l('Option D (Kurdish)'), validators=[Optional()])

    correct_answer = SelectField(_l('Correct Answer'), choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')], validators=[DataRequired()])

    submit = SubmitField(_l('Save Question'))

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators=extra_validators)
        en_ok = all([
            (self.question_text.data or '').strip(),
            (self.option_a.data or '').strip(),
            (self.option_b.data or '').strip(),
            (self.option_c.data or '').strip(),
            (self.option_d.data or '').strip(),
        ])
        ku_ok = all([
            (self.question_text_kurdish.data or '').strip(),
            (self.option_a_kurdish.data or '').strip(),
            (self.option_b_kurdish.data or '').strip(),
            (self.option_c_kurdish.data or '').strip(),
            (self.option_d_kurdish.data or '').strip(),
        ])
        if not en_ok and not ku_ok:
            self.question_text.errors.append(
                _l('Please fill out at least one complete language version (English or Kurdish) including all 4 options.')
            )
            return False
        return ok

# ==========================================
# 5. BULK IMPORT & RESOURCES
# ==========================================

class BulkImportForm(FlaskForm):
    """
    Form for uploading CSV or Excel files.
    """
    file = FileField(_l('Upload File (CSV or Excel)'), validators=[
        DataRequired(),
        FileAllowed(['csv', 'xlsx', 'xls'], _l('Tables only!'))
    ])
    submit = SubmitField(_l('Preview Data'))

class ResourceForm(FlaskForm):
    """
    Form for adding a single resource link to a page.
    """
    title = StringField(_l('Resource Title (e.g. Watch Video)'), validators=[DataRequired()])
    title_kurdish = StringField(_l('Resource Title (Kurdish)'), validators=[Optional()])
    link = StringField(_l('URL (Link)'), validators=[DataRequired()])
    submit = SubmitField(_l('Add Resource'))

# ==========================================
# 6. SYSTEM MANAGEMENT
# ==========================================

class CommandForm(FlaskForm):
    """
    NEW: Form for adding system commands to the admin cheat-sheet.
    """
    title = StringField(_l('Command Title (e.g. Reset DB)'), validators=[DataRequired()])
    title_kurdish = StringField(_l('Command Title (Kurdish)'), validators=[Optional()])
    command_text = TextAreaField(_l('Command Code'), validators=[DataRequired()])
    description = TextAreaField(_l('Description / When to use'), validators=[DataRequired()])
    description_kurdish = TextAreaField(_l('Description (Kurdish)'), validators=[Optional()])
    submit = SubmitField(_l('Save Command'))

class RestoreBackupForm(FlaskForm):
    """
    NEW: Form for the Full System Restore feature.
    Accepts only .zip files containing the raw CSV dumps.
    """
    backup_file = FileField(_l('Select Backup File (.zip)'), validators=[
        DataRequired(),
        FileAllowed(['zip'], _l('ZIP Archives Only!'))
    ])
    confirm_wipe = BooleanField(_l('I understand this will DELETE ALL CURRENT DATA'), validators=[DataRequired()])
    submit = SubmitField(_l('PERFORM FULL RESTORE'))

class WipeCleanForm(FlaskForm):
    """
    Form for wiping all data and creating a clean site.
    """
    confirm_wipe = BooleanField(_l('I understand this will DELETE ALL DATA permanently'), validators=[DataRequired()])
    submit = SubmitField(_l('WIPE EVERYTHING & START FRESH'))


class ToolForm(FlaskForm):
    """
    Form for adding external tool links.
    """
    title = StringField(_l('Tool Name'), validators=[DataRequired()])
    title_kurdish = StringField(_l('Tool Name (Kurdish)'), validators=[Optional()])
    link = StringField(_l('Tool URL (https://...)'), validators=[DataRequired()])
    description = TextAreaField(_l('Description'), validators=[Optional()])
    description_kurdish = TextAreaField(_l('Description (Kurdish)'), validators=[Optional()])
    submit = SubmitField(_l('Add Tool'))


class CommentForm(FlaskForm):
    """
    Public form for posting a comment on a lecture page.
    Requires name, birth date, and comment; personality info is optional.
    """
    author_name = StringField(_l('Your Name'), validators=[DataRequired(), Length(min=1, max=100)])
    author_birth_date = DateField(_l('Your Birth Date'), format='%Y-%m-%d', validators=[DataRequired(), validate_birth_date])
    personality_info = TextAreaField(_l('About You / Personality (Optional)'), validators=[Optional(), Length(max=500)])
    comment_text = TextAreaField(_l('Your Comment'), validators=[DataRequired(), Length(min=1, max=2000)])
    submit = SubmitField(_l('Post Comment'))


class CommentReplyForm(FlaskForm):
    """
    Form for Teachers & Admins to reply to a visitor's lecture comment.
    """
    comment_text = TextAreaField(_l('Your Reply'), validators=[DataRequired(), Length(min=1, max=2000)])
    submit = SubmitField(_l('Post Reply'))


class TeacherRequestForm(FlaskForm):
    """
    Public signup application form for prospective Teachers.
    """
    name_en = StringField(_l('Full Name (English)'), validators=[DataRequired(), Length(min=2, max=100)])
    name_ku = StringField(_l('Full Name (Kurdish)'), validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField(_l('Email Address'), validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField(_l('Password'), validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        _l('Confirm Password'),
        validators=[DataRequired(), EqualTo('password', message=_l('Passwords must match.'))]
    )
    gender = SelectField(_l('Gender'), choices=GENDER_CHOICES_REQUIRED, validators=[DataRequired()])
    birth_date = DateField(_l('Birth Date'), format='%Y-%m-%d', validators=[DataRequired(), validate_birth_date])
    bio = TextAreaField(_l('Bio (Optional)'), validators=[Optional(), Length(max=500)])
    reason = TextAreaField(_l('Why do you want to sign up as a teacher?'), validators=[DataRequired(), Length(min=10, max=2000)])
    submit = SubmitField(_l('Submit Application'))


class TeacherToAdminMessageForm(FlaskForm):
    """
    Form allowing Teachers to send a direct message to Administrators.
    """
    title = StringField(_l('Subject'), validators=[DataRequired(), Length(min=1, max=200)])
    message = TextAreaField(_l('Message to Administrators'), validators=[DataRequired(), Length(min=1, max=2000)])
    submit = SubmitField(_l('Send to Admins'))


class StudentManageForm(FlaskForm):
    """
    Form for Teachers & Admins to create or edit a code-based Student record.
    """
    name_en = StringField(_l('Student Name (English)'), validators=[DataRequired(), Length(min=1, max=100)])
    name_ku = StringField(_l('Student Name (Kurdish)'), validators=[DataRequired(), Length(min=1, max=100)])
    birth_date = DateField(_l('Birth Date'), format='%Y-%m-%d', validators=[DataRequired(), validate_birth_date])
    gender = SelectField(_l('Gender'), choices=GENDER_CHOICES_REQUIRED, validators=[DataRequired()])
    department_en = StringField(_l('Department (English)'), validators=[DataRequired(), Length(min=1, max=100)])
    department_ku = StringField(_l('Department (Kurdish)'), validators=[DataRequired(), Length(min=1, max=100)])
    submit = SubmitField(_l('Save Student'))


class PrivateExamCreateForm(FlaskForm):
    """Form to create a new auto-generated Hidden Exam / Quiz link."""
    title = StringField(_l('Hidden Exam Title (English)'), validators=[DataRequired(), Length(min=1, max=200)])
    title_kurdish = StringField(_l('Hidden Exam Title (Kurdish)'), validators=[Optional(), Length(max=200)])
    submit = SubmitField(_l('Create Exam & Generate Link'))