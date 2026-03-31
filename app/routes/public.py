from datetime import datetime
from flask import Blueprint, render_template, url_for, flash, redirect, request, jsonify, session
from flask_babel import gettext as _
from flask_login import current_user
from sqlalchemy import func, or_

from app import db, bcrypt, limiter
from app.models import User, Student, Subject, ExamResult, SiteInfo, Page
from app.forms import SetupForm

public = Blueprint('public', __name__)

# ==============================================================================
# SECTION 1: SYSTEM UTILITIES & CORE SETUP
# ==============================================================================

@public.route('/keep_alive')
def keep_alive():
    """
    THE HEARTBEAT ROUTE (The 'Secret Door')

    Purpose:
    This route provides a lightweight endpoint for UptimeRobot to ping.
    It resets the PythonAnywhere sleep timer without querying the database.

    Returns:
        JSON response indicating server health.
    """
    return jsonify(
        status="alive",
        timestamp=datetime.utcnow().isoformat(),
        version="2.0.4",
        message="StatInfoPRO System is active."
    )


@public.route('/setup', methods=['GET', 'POST'])
@limiter.limit("10/minute")
def setup():
    """
    SYSTEM INITIALIZATION ROUTE

    Purpose:
    Allows the creation of the primary Administrator (Headmaster).
    Blocked once an admin already exists in the system.
    """
    # 1. Verification: Does an administrator already exist?
    existing_admin = User.query.filter_by(is_admin=True).first()

    if existing_admin:
        flash(_('System is already initialized. Access to setup is restricted.'), 'warning')
        return redirect(url_for('auth.login'))

    # 2. Setup Form
    form = SetupForm()

    # 3. Validation and User Creation
    if form.validate_on_submit():

        # Verify email uniqueness
        check_email = User.query.filter_by(email=form.email.data).first()
        if check_email:
            flash(_('Error: This email is already registered in our systems.'), 'danger')
            return render_template('setup.html', form=form)

        # Secure password hashing using Bcrypt
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')

        # Create user object
        master_admin = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=hashed_password,
            is_admin=True
        )

        try:
            db.session.add(master_admin)
            db.session.commit()
            flash(_('Admin Account Created! Please login to begin managing the school.'), 'success')
            return redirect(url_for('auth.login'))
        except Exception as database_error:
            db.session.rollback()
            flash(_('Critical Database Error: %(error)s', error=str(database_error)), 'danger')

    return render_template('setup.html', form=form)


# ==============================================================================
# SECTION 2: PUBLIC USER INTERFACE
# ==============================================================================

@public.route('/')
def index():
    """
    HOMEPAGE

    Lists all academic subjects currently offered, with support for search.
    """
    search_query = request.args.get('q', '').strip()
    
    if search_query:
        subject_list = Subject.query.filter(
            Subject.is_public == True,
            or_(
                Subject.name.ilike(f'%{search_query}%'),
                Subject.description.ilike(f'%{search_query}%')
            )
        ).all()
        
        page_list = Page.query.join(Subject).filter(
            Subject.is_public == True,
            or_(
                Page.title.ilike(f'%{search_query}%'),
                Page.content_body.ilike(f'%{search_query}%'),
                Page.content_body_kurdish.ilike(f'%{search_query}%')
            )
        ).all()
    else:
        subject_list = Subject.query.filter_by(is_public=True).all()
        page_list = []

    return render_template('index.html', subjects=subject_list, pages=page_list, search_query=search_query)


@public.route('/about')
def about():
    """
    ABOUT US PAGE

    Content is dynamically fetched from the SiteInfo model.
    """
    site_content = SiteInfo.query.filter_by(key='about').first()
    return render_template('about.html', info=site_content)


@public.route('/public/stats')
def public_stats():
    """
    ANALYTICS OVERVIEW (PUBLIC)

    Calculates high-level metrics for public display using SQL aggregations.
    """
    # 1. Subject performance aggregation
    subject_scores = db.session.query(
        Subject.name,
        func.avg(ExamResult.score)
    ).join(ExamResult).group_by(Subject.id).all()

    # 2. Extract labels and rounded values for Chart.js
    chart_labels = [row[0] for row in subject_scores]
    chart_values = [round(row[1], 1) for row in subject_scores]

    # 3. Global counters
    total_completed_exams = ExamResult.query.count()
    total_registered_students = Student.query.count()

    # 4. Global Average score
    avg_aggregate = db.session.query(func.avg(ExamResult.score)).scalar()
    global_average_percent = round(avg_aggregate, 1) if avg_aggregate else 0

    # 5. Success/Failure metrics
    passing_grade_count = ExamResult.query.filter(ExamResult.score >= 50).count()
    failing_grade_count = ExamResult.query.filter(ExamResult.score < 50).count()

    return render_template(
        'stats.html',
        labels=chart_labels,
        values=chart_values,
        total_exams=total_completed_exams,
        total_students=total_registered_students,
        global_average=global_average_percent,
        pass_count=passing_grade_count,
        fail_count=failing_grade_count
    )

@public.route('/set-lang/<lang>')
def set_lang(lang):
    """
    Sets the user's preferred language.
    Stored in session FIRST (always), then persisted to DB for cross-device use.
    """
    from flask import current_app

    ALLOWED_LANGS = ['en', 'ku']

    if lang not in ALLOWED_LANGS:
        flash(_('Invalid language selected.'), 'danger')
        return redirect(request.referrer or url_for('public.index'))
    
    # 1. SESSION FIRST — this is the single source of truth for select_locale()
    session['lang'] = lang
    current_app.logger.info(f"set_lang: session['lang'] set to '{lang}'")

    # 2. Persist to DB for cross-device/cross-session recall
    if current_user and current_user.is_authenticated and hasattr(current_user, 'preferred_lang'):
        try:
            current_user.preferred_lang = lang
            db.session.commit()
            current_app.logger.info(f"set_lang: User {current_user.id} preferred_lang updated to '{lang}'")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"set_lang: Failed to update user preferred_lang: {e}")
    else:
        # Check student session
        student_id = session.get('student_id')
        if student_id:
            try:
                student = db.session.get(Student, student_id)
                if student:
                    student.preferred_lang = lang
                    db.session.commit()
                    current_app.logger.info(f"set_lang: Student {student_id} preferred_lang updated to '{lang}'")
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"set_lang: Failed to update student preferred_lang: {e}")
    
    flash(_('Language changed successfully.'), 'success')
    return redirect(request.referrer or url_for('public.index'))

