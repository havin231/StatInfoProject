from flask import Blueprint, render_template, url_for, flash, redirect, request, session
from flask_babel import gettext as _
from flask_login import login_user, current_user, logout_user

from app import db, bcrypt, limiter
from app.models import User
from app.forms import LoginForm

auth = Blueprint('auth', __name__)

# ==============================================================================
# SECTION 3: AUTHENTICATION (STAFF)
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


@auth.route('/logout')
def logout():
    """
    GLOBAL SESSION TERMINATION

    Clears active staff sessions.
    """
    logout_user()
    session.clear()
    flash(_('Session ended.'), 'info')
    return redirect(url_for('public.index'))


# Graceful redirects for deprecated student auth endpoints
@auth.route('/student/login', methods=['GET', 'POST'])
@auth.route('/student/signup', methods=['GET', 'POST'])
@auth.route('/student/settings', methods=['GET', 'POST'])
def deprecated_student_auth():
    """Redirect deprecated student authentication endpoints to staff login."""
    return redirect(url_for('auth.login'))
