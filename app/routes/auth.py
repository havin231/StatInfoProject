from flask import Blueprint, render_template, url_for, flash, redirect, request, session
from flask_babel import gettext as _
from flask_login import login_user, current_user, logout_user

from app import db, bcrypt, limiter
from app.models import User, TeacherRequest, AdminNotification
from app.forms import LoginForm, TeacherRequestForm

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


@auth.route('/teacher/apply', methods=['GET', 'POST'])
@limiter.limit("10/hour")
def teacher_apply():
    """
    PUBLIC TEACHER SIGNUP REQUEST APPLICATION (v0.9.0)

    Collects EN/KU name, email, chosen password (hashed), gender, birth date,
    optional bio, and why they want to sign up. Notifies Admins immediately.
    """
    if current_user.is_authenticated:
        return redirect(url_for('teacher.teacher_dashboard'))

    form = TeacherRequestForm()
    if form.validate_on_submit():
        name_en = form.name_en.data.strip()
        name_ku = form.name_ku.data.strip()
        email = form.email.data.strip().lower()

        if User.query.filter_by(email=email).first() or TeacherRequest.query.filter_by(email=email, status='pending').first():
            flash(_('An account or pending application with this email already exists.'), 'danger')
            return render_template('teacher_apply.html', form=form)

        if User.query.filter_by(username=name_en).first() or TeacherRequest.query.filter_by(name_en=name_en, status='pending').first():
            flash(_('An account or pending application with this English name already exists.'), 'danger')
            return render_template('teacher_apply.html', form=form)

        pw_hash = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        req = TeacherRequest(
            name_en=name_en,
            name_ku=name_ku,
            email=email,
            password_hash=pw_hash,
            gender=form.gender.data,
            birth_date=form.birth_date.data,
            bio=form.bio.data.strip() if form.bio.data else None,
            reason=form.reason.data.strip(),
            status='pending'
        )
        try:
            db.session.add(req)
            db.session.flush()
            db.session.add(AdminNotification(
                notification_type='teacher_request',
                title=f"New Teacher Signup Request: {name_en} ({name_ku})",
                message=(
                    f"Name: {name_en} / {name_ku} | Email: {email}\n"
                    f"Gender: {form.gender.data} | Born: {form.birth_date.data.strftime('%Y-%m-%d')}\n"
                    f"Reason: {req.reason}"
                ),
                actor_type='applicant',
                actor_id=req.id,
                actor_name=name_en
            ))
            db.session.commit()
            flash(_('Your teacher application has been submitted! An administrator will review it soon.'), 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(_('Error submitting application: %(error)s', error=str(e)), 'danger')

    return render_template('teacher_apply.html', form=form)
