from flask import Blueprint, render_template, url_for, flash, redirect, request, session
from flask_babel import gettext as _
from flask_login import login_user, current_user, logout_user

from app import db, bcrypt, limiter
from app.models import Student
from app.forms import LoginForm, StudentSignupForm, StudentSettingsForm
from app.models import User
from app.routes.helpers import generate_access_code

auth = Blueprint('auth', __name__)

# ==============================================================================
# SECTION 3: AUTHENTICATION (STAFF & STUDENTS)
# ==============================================================================

@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("10/minute")
def login():
    """
    STAFF PORTAL LOGIN

    Handles authentication for both Teachers and Administrators.
    Includes 'remember me' cookie support.
    """
    if current_user.is_authenticated:
        return redirect(url_for('teacher.teacher_dashboard'))

    form = LoginForm()

    if form.validate_on_submit():
        user_record = User.query.filter_by(email=form.email.data).first()

        if user_record and bcrypt.check_password_hash(user_record.password_hash, form.password.data):
            login_user(user_record, remember=form.remember.data)
            flash(_('Logged in successfully.'), 'success')
            return redirect(url_for('teacher.teacher_dashboard'))
        else:
            flash(_('Authentication failed. Check credentials.'), 'danger')

    return render_template('login.html', title='Staff Access', form=form)


@auth.route('/student/login', methods=['GET', 'POST'])
@limiter.limit("10/minute")
def student_login():
    """
    STUDENT PORTAL LOGIN

    Authenticates students via Access Code and Password.
    Implements redirection logic for deep links (Task Fix).
    """
    if request.method == 'POST':
        user_token = request.form.get('access_code')
        password = request.form.get('password')
        student_record = Student.query.filter_by(access_code=user_token).first()

        if student_record and student_record.password_hash:
            # Verify password
            if bcrypt.check_password_hash(student_record.password_hash, password):
                # Persistent session identification
                session['student_id'] = student_record.id
                flash(_('Welcome, %(name)s.', name=student_record.full_name), 'success')

                # REDIRECT LOGIC: Support for the 'next' parameter
                target_page = request.args.get('next')
                if target_page and target_page.startswith('/'):
                    return redirect(target_page)

                return redirect(url_for('student.student_dashboard'))
            else:
                flash(_('Invalid password.'), 'danger')
        elif student_record and not student_record.password_hash:
            # Legacy account without password - allow access code only
            session['student_id'] = student_record.id
            flash(_('Welcome, %(name)s. Please set a password for enhanced security.', name=student_record.full_name), 'warning')
            return redirect(url_for('auth.student_settings'))
        else:
            flash(_('The Access Code provided is invalid.'), 'danger')

    return render_template('student_login.html')


@auth.route('/logout')
def logout():
    """
    GLOBAL SESSION TERMINATION

    Clears all active sessions for both staff and students.
    """
    logout_user()
    session.pop('student_id', None)
    flash(_('Session ended.'), 'info')
    return redirect(url_for('public.index'))

# ==============================================================================
# SECTION 3.5: STUDENT SELF-SERVICE (SIGNUP & SETTINGS)
# ==============================================================================

@auth.route('/student/signup', methods=['GET', 'POST'])
def student_signup():
    """
    STUDENT SELF-REGISTRATION
    """
    if 'student_id' in session:
        return redirect(url_for('student.student_dashboard'))
    
    form = StudentSignupForm()
    
    if form.validate_on_submit():
        # Check email uniqueness
        if Student.query.filter_by(email=form.email.data).first():
            flash(_('Error: This email is already registered.'), 'danger')
            return render_template('student_signup.html', form=form)
        
        # Check password complexity
        password = form.password.data
        if not any(c.isupper() for c in password):
            flash(_('Password must contain at least one uppercase letter.'), 'danger')
            return render_template('student_signup.html', form=form)
        if not any(c.islower() for c in password):
            flash(_('Password must contain at least one lowercase letter.'), 'danger')
            return render_template('student_signup.html', form=form)
        if not any(c.isdigit() for c in password):
            flash(_('Password must contain at least one number.'), 'danger')
            return render_template('student_signup.html', form=form)
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
            flash(_('Password must contain at least one special character.'), 'danger')
            return render_template('student_signup.html', form=form)
            
        # Generate unique access code
        new_code = generate_access_code()
        while Student.query.filter_by(access_code=new_code).first():
            new_code = generate_access_code()
            
        new_student = Student(
            full_name=form.full_name.data,
            email=form.email.data,
            access_code=new_code,
            password_hash=bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        )
        
        try:
            db.session.add(new_student)
            db.session.commit()
            
            # Send welcome email
            from flask_mail import Message
            from app import mail
            from app.models import SiteInfo
            
            default_welcome = f"""Welcome to StatInfoPro!

Dear {new_student.full_name},

Your account has been successfully created.

Your Access Code: {new_code}

Please save your access code in a secure place. You will need it to log in to the system.

Best regards,
StatInfoPro Team
"""
            welcome_body = SiteInfo.get_email_template('student_welcome', default_welcome)
            
            # Replace variables in template
            welcome_body = welcome_body.replace('{{name}}', new_student.full_name)
            welcome_body = welcome_body.replace('{{access_code}}', new_code)
            welcome_body = welcome_body.replace('{{email}}', new_student.email or '')
            
            try:
                msg = Message(
                    subject='Welcome to StatInfoPro!',
                    recipients=[new_student.email],
                    body=welcome_body
                )
                mail.send(msg)
            except Exception as email_err:
                # Log error but don't block account creation
                print(f"Failed to send welcome email: {email_err}")
            
            # Auto-login
            session['student_id'] = new_student.id
            flash(_('Account created! Your Access Code is: %(code)s. Please save it!', code=new_code), 'success')
            return redirect(url_for('student.student_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(_('Error creating account: %(error)s', error=str(e)), 'danger')
            
    return render_template('student_signup.html', form=form)

@auth.route('/student/settings', methods=['GET', 'POST'])
def student_settings():
    """
    STUDENT PROFILE SETTINGS
    Allows updating email and access code.
    """
    if 'student_id' not in session:
        return redirect(url_for('auth.student_login'))
        
    student = Student.query.get_or_404(session['student_id'])
    form = StudentSettingsForm()
    
    if request.method == 'GET':
        form.email.data = student.email
        form.access_code.data = student.access_code
        
    if form.validate_on_submit():
        # Check email uniqueness if changed
        if form.email.data != student.email:
            if Student.query.filter_by(email=form.email.data).first():
                flash(_('Error: Email already in use by another student.'), 'danger')
                return render_template('student/settings.html', form=form, student=student)
        
        # Check access code uniqueness if changed
        if form.access_code.data != student.access_code:
            if Student.query.filter_by(access_code=form.access_code.data).first():
                flash(_('Error: Access code already taken.'), 'danger')
                return render_template('student/settings.html', form=form, student=student)
        
        # Handle password change
        if form.new_password.data:
            # Verify current password if one exists
            if student.password_hash:
                if not form.current_password.data or not bcrypt.check_password_hash(student.password_hash, form.current_password.data):
                    flash(_('Current password is incorrect.'), 'danger')
                    return render_template('student/settings.html', form=form, student=student)
            
            # Validate new password complexity
            new_password = form.new_password.data
            if not any(c.isupper() for c in new_password):
                flash(_('New password must contain at least one uppercase letter.'), 'danger')
                return render_template('student/settings.html', form=form, student=student)
            if not any(c.islower() for c in new_password):
                flash(_('New password must contain at least one lowercase letter.'), 'danger')
                return render_template('student/settings.html', form=form, student=student)
            if not any(c.isdigit() for c in new_password):
                flash(_('New password must contain at least one number.'), 'danger')
                return render_template('student/settings.html', form=form, student=student)
            if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in new_password):
                flash(_('New password must contain at least one special character.'), 'danger')
                return render_template('student/settings.html', form=form, student=student)
            
            # Update password
            student.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
                
        student.email = form.email.data
        student.access_code = form.access_code.data
        
        try:
            db.session.commit()
            flash(_('Settings updated successfully.'), 'success')
            return redirect(url_for('student.student_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(_('Error updating settings: %(error)s', error=str(e)), 'danger')
            
    return render_template('student/settings.html', form=form, student=student)


@auth.route('/student/delete_account', methods=['POST'])
def delete_account():
    """
    STUDENT SELF-ACCOUNT DELETION
    
    Soft delete: Clears personal info (name, email, access_code) but keeps exam data.
    The student ID remains for exam result integrity.
    """
    from datetime import datetime
    
    if 'student_id' not in session:
        return redirect(url_for('auth.student_login'))
    
    student = Student.query.get_or_404(session['student_id'])
    
    # Verify confirmation text
    confirmation = request.form.get('confirmation', '').strip()
    if confirmation != 'DELETE':
        flash(_('Please type DELETE to confirm account deletion.'), 'danger')
        return redirect(url_for('auth.student_settings'))
    
    try:
        # Soft delete: Clear personal info but keep ID for exam data integrity
        student.full_name = 'Deleted Student'
        student.email = None
        student.access_code = f'DELETED_{student.id}_{datetime.utcnow().timestamp()}'
        student.is_deleted = True
        
        db.session.commit()
        
        # Clear session
        session.pop('student_id', None)
        
        flash(_('Your account has been deleted. Your exam data has been retained anonymously.'), 'success')
        return redirect(url_for('public.index'))
        
    except Exception as e:
        db.session.rollback()
        flash(_('Error deleting account: %(error)s', error=str(e)), 'danger')
        return redirect(url_for('auth.student_settings'))
