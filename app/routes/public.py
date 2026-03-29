from datetime import datetime
from flask import Blueprint, render_template, url_for, flash, redirect, request, jsonify
from flask_login import current_user
from sqlalchemy import func

from app import db, bcrypt, limiter
from app.models import User, Student, Subject, ExamResult, SiteInfo
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
        flash('System is already initialized. Access to setup is restricted.', 'warning')
        return redirect(url_for('auth.login'))

    # 2. Setup Form
    form = SetupForm()

    # 3. Validation and User Creation
    if form.validate_on_submit():

        # Verify email uniqueness
        check_email = User.query.filter_by(email=form.email.data).first()
        if check_email:
            flash('Error: This email is already registered in our systems.', 'danger')
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
            flash('Admin Account Created! Please login to begin managing the school.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as database_error:
            db.session.rollback()
            flash(f'Critical Database Error: {str(database_error)}', 'danger')

    return render_template('setup.html', form=form)


# ==============================================================================
# SECTION 2: PUBLIC USER INTERFACE
# ==============================================================================

@public.route('/')
def index():
    """
    HOMEPAGE

    Lists all academic subjects currently offered.
    """
    subject_list = Subject.query.filter_by(is_public=True).all()
    return render_template('index.html', subjects=subject_list)


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
