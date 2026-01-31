from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, Length, Optional, EqualTo

# ==========================================
# 1. AUTHENTICATION & SETUP
# ==========================================

class LoginForm(FlaskForm):
    """
    Form for staff/admin login.
    """
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class SetupForm(FlaskForm):
    """
    Form for the initial system setup (creating the first Headmaster).
    """
    username = StringField('Headmaster Name', validators=[DataRequired()])
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Create System Admin')

# ==========================================
# 2. ADMIN & USER MANAGEMENT
# ==========================================

class TeacherSignupForm(FlaskForm):
    """
    Form for Admins to create new staff accounts.
    """
    username = StringField('Teacher Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    is_admin = BooleanField('Grant Admin Access')
    submit = SubmitField('Create Account')

class TeacherEditForm(FlaskForm):
    """
    Form for editing existing staff.
    """
    username = StringField('Teacher Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Reset Password (Optional)', validators=[Optional(), Length(min=6)])
    is_admin = BooleanField('Grant Admin Access')
    submit = SubmitField('Update Account')

class StudentForm(FlaskForm):
    """
    Form for registering new students.
    """
    full_name = StringField('Full Name', validators=[DataRequired()])
    access_code = StringField('Access Code (Unique)', validators=[DataRequired()])
    group_id = StringField('Group/Class ID', validators=[DataRequired(), Length(max=20)])
    submit = SubmitField('Add Student')

class StudentEditForm(FlaskForm):
    """
    Form for editing existing student details (Task 1).
    """
    full_name = StringField('Full Name', validators=[DataRequired()])
    access_code = StringField('Access Code', validators=[DataRequired()])
    group_id = StringField('Group/Class ID', validators=[DataRequired(), Length(max=20)])
    submit = SubmitField('Update Student Details')

# ==========================================
# 3. SITE CONTENT (CMS)
# ==========================================

class InfoPageForm(FlaskForm):
    """
    Form for editing static pages like 'About Us'.
    """
    title = StringField('Page Title', default="About Us", validators=[DataRequired()])
    content = TextAreaField('Page Content', validators=[DataRequired()])
    submit = SubmitField('Save Page')

# ==========================================
# 4. ACADEMIC CONTENT
# ==========================================

class SubjectForm(FlaskForm):
    """
    Form for creating/editing Subjects.
    """
    name = StringField('Subject Name', validators=[DataRequired()])
    slug = StringField('Unique Slug (e.g. math-101)', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    teacher_id = SelectField('Assign Teacher', coerce=int)
    submit = SubmitField('Create Subject')

class PageForm(FlaskForm):
    """
    Form for creating study materials (Lectures/Chapters).
    """
    subject_id = SelectField('Select Subject', coerce=int, validators=[DataRequired()])
    title = StringField('Page Title', validators=[DataRequired()])
    content_body = TextAreaField('Content (English)', validators=[DataRequired()])
    content_body_kurdish = TextAreaField('Content (Kurdish)', validators=[Optional()])
    submit = SubmitField('Publish Content')

class QuestionForm(FlaskForm):
    """
    Form for adding/editing a single question.
    """
    subject_id = SelectField('Subject', coerce=int, validators=[DataRequired()])
    page_id = SelectField('Link to Specific Lecture (Optional)', coerce=int)

    question_text = TextAreaField('Question', validators=[DataRequired()])
    option_a = StringField('Option A', validators=[DataRequired()])
    option_b = StringField('Option B', validators=[DataRequired()])
    option_c = StringField('Option C', validators=[DataRequired()])
    option_d = StringField('Option D', validators=[DataRequired()])
    correct_answer = SelectField('Correct Answer', choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')], validators=[DataRequired()])

    # Language Flag
    is_kurdish = BooleanField('Is Kurdish? (Right-to-Left)')

    submit = SubmitField('Save Question')

# ==========================================
# 5. BULK IMPORT & RESOURCES
# ==========================================

class BulkImportForm(FlaskForm):
    """
    Form for uploading CSV or Excel files.
    """
    file = FileField('Upload File (CSV or Excel)', validators=[
        DataRequired(),
        FileAllowed(['csv', 'xlsx', 'xls'], 'Tables only!')
    ])
    submit = SubmitField('Preview Data')

class ResourceForm(FlaskForm):
    """
    Form for adding a single resource link to a page.
    """
    title = StringField('Resource Title (e.g. Watch Video)', validators=[DataRequired()])
    link = StringField('URL (Link)', validators=[DataRequired()])
    submit = SubmitField('Add Resource')

# ==========================================
# 6. SYSTEM MANAGEMENT
# ==========================================

class CommandForm(FlaskForm):
    """
    NEW: Form for adding system commands to the admin cheat-sheet.
    """
    title = StringField('Command Title (e.g. Reset DB)', validators=[DataRequired()])
    command_text = TextAreaField('Command Code', validators=[DataRequired()])
    description = TextAreaField('Description / When to use', validators=[DataRequired()])
    submit = SubmitField('Save Command')

class RestoreBackupForm(FlaskForm):
    """
    NEW: Form for the Full System Restore feature.
    Accepts only .zip files containing the raw CSV dumps.
    """
    backup_file = FileField('Select Backup File (.zip)', validators=[
        DataRequired(),
        FileAllowed(['zip'], 'ZIP Archives Only!')
    ])
    confirm_wipe = BooleanField('I understand this will DELETE ALL CURRENT DATA', validators=[DataRequired()])
    submit = SubmitField('PERFORM FULL RESTORE')

class ToolForm(FlaskForm):
    """
    Form for adding external tool links.
    """
    title = StringField('Tool Name', validators=[DataRequired()])
    link = StringField('Tool URL (https://...)', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    submit = SubmitField('Add Tool')