# AGENT SKILL: StatInfoPRO LMS Specialist

> [!IMPORTANT]
> **MAINTENANCE RULES:**
> 1. This `SKILL.md` file MUST be updated after EVERY change to the codebase to maintain an accurate source of truth for the agent.
> 2. Whenever a change or new feature is added, **VersionDetails.txt** MUST be updated with the details, changes, and improvements.
> 3. Whenever a change or new feature is added, a new versioned snapshot folder (e.g. `version_0.4.2`) MUST be created inside `/home/havin/Documents/statinfopro/` copying all current project files.
> 4. Ensure the File Organization (Git, PythonAnywhere, Local) inside this file remains up to date.


## 1. PROJECT IDENTITY & CONTEXT
- **System Name:** StatInfoProject (StatInfoPRO)
- **Current Version:** 0.9.1 (2026-11-24)
- **Deployment:** PythonAnywhere (Linux/Bash/MySQL).
- **Primary Language:** Python 3.10 / Flask 3.0.0.
- **Frontend:** HTML5, Bootstrap 5.3, Jinja2, Custom CSS Variables.
- **Context:** A bilingual (English/Kurdish) Learning Management System for the University of Sulaimani.

## RECENT CHANGES (v0.9.1)
- **Admin Full Teacher Dashboard Inspector & Unread-Only Notification Boxes**:
  - Updated `view_teacher()` (`GET /admin/view_teacher/<id>`) via `_build_teacher_dashboard_context()` so Admins see the complete teacher dashboard (profile, unread inbox, students count, stats/students/notifications links, and subject toggles) and added `?teacher_id=` support for Admin views.
  - Small notification boxes in `admin_dashboard.html` and `teacher/dashboard.html` now show ONLY unread notifications (`is_checked=False` / `is_read=False`), while full read & unread history persists permanently on `/admin/notifications` and `/teacher/notifications`.
- **Comment Modal Fix, Direct Teacher Comments & Optional Comment Guest Codes**:
  - Moved `#commentDetailsModal` in `page.html` outside `.card` backdrop-filter containers and appended it to `document.body` on `DOMContentLoaded` to eliminate modal backdrop stacking/grayed-out lockup.
  - Logged-in Teachers and Admins can post top-level comments and replies directly with no extra questions, honoring anonymity (`From Teacher` / `لە لایەن مامۆستاوە`).
  - Added optional 8-character `CommentGuest` code creation and reuse (`generate_comment_code='1'`, `guest_mode='code'`).
- **Question Bank Save Fix, RTL Removal & Dedicated Hidden Exams Bank**:
  - Fixed `NoneType` `int()` crash in `save_questions_api()` via `_safe_optional_int()` when adding new questions with `page_id=None`.
  - Removed manual `RTL` toggle/column from `QuestionForm`, `builder.html`, `import_preview.html`, and CSV exports (RTL auto-detects from Kurdish text).
  - Added `PrivateExam`, `PrivateQuestion`, and `PrivateExamQuestion` with `/teacher/builder/private_exams` (`teacher/private_builder.html`), multi-link assignments, and Student-Code-gated `/exam/link/<token>` routes.
- **Public Teacher Profiles & Optional Exam Guest Codes**:
  - Added 5 privacy flags on `User` (`profile_public`, `profile_show_name`, `profile_show_bio`, `profile_show_age`, `profile_show_gender`), `/teacher/<id>/profile` (`teacher_profile.html`, 404 when `profile_public=False`), and clickable teacher names on subjects/lessons/comments.
  - Added `ExamGuest` model & opt-in 8-character guest exam codes for public exams/quizzes (strictly separate from `Student` codes and blocked from hidden Student-Code exams).
- **21-CSV Full Backup, Kurdish Translations & Testing**:
  - Upgraded `export_full_backup()` and `restore_system()` to 21 CSVs (`17_private_exams.csv`–`21_exam_guests.csv`), updated 76 new Kurdish strings (0 remaining), compiled `messages.mo`, and added `tests/test_v091_features.py` (46/46 tests pass).

## RECENT CHANGES (v0.9.0)
- **Logical Audit Fixes & Dual-Language Exam Engine**:
  - Fixed live Statistics persistence: `submit_exam()` now persists `ExamResult` rows (`score`, `correct_count`, `total_questions`, `page_id`, `student_record_id`, `taker_name`, `taker_birth_date`, `taker_gender`) so public, teacher, and admin stats update immediately.
  - Fixed partial-answer 100% grading exploit: grades against the full `expected_questions` pool and enforces required fields on `exam.html` (`requestSubmit`/`reportValidity`).
  - Added dual-language Question Bank ("two language faces"): `question_text_kurdish`, `option_a_kurdish`–`option_d_kurdish` in `Question`, spreadsheet bulk editor (`builder.html` / `save_questions_api`), single question form (`QuestionForm`), and CSV export/import (accepting both `'Answer'` and `'Ans'` headers and safe against NaN cells).
  - Fixed `Page.title_kurdish` & `SiteInfo.title_kurdish` DB columns and UI rendering, bilingual homepage search (including Kurdish titles/descriptions), bilingual `/public/stats`, duplicate slug checks on `edit_subject`, Command/Tool CSV NaN sanitization, and `base.html` `main.index` -> `public.index` fallback.
- **Zero-Loss 16-CSV Full Backup & Restore**:
  - Removed the corrupting `.replace('rn', '\n')` string bug in `restore_system()` (words like `learn`, `modern`, `pattern`).
  - Expanded `export_full_backup()` and `restore_system()` to cover all 16 model exports (`1_users.csv` through `16_teacher_notifications.csv`, preserving PK/FK hierarchy) alongside strict bottom-up `_wipe_all_non_user_tables()`.
- **Teacher & Admin View-Only Statistics Hubs**:
  - Added `/teacher/stats` (`teacher/stats.html`) scoped to assigned subjects and linked students, with non-destructive checkbox subject filtering.
  - Added `/admin/stats` (`admin/stats.html`) and `/admin/stats/export` CSV download with subject, teacher, exam-type, taker-type, gender, search, and date-range filters.
- **Code-Based Students & Hidden Student-Only Exams/Quizzes**:
  - Added `Student` (`student_record` table, no login/password) and `StudentTeacher` models managed via `/staff/students`, auto-generating unique `>= 8` char `student_code`s, searchable by EN/KU name, department, or code, and shareable across teachers by Admins (`/admin/students/<id>/teachers`, `/admin/students/bulk_share`).
  - Added `Subject.exam_student_only` and `Page.quiz_student_only` toggles plus `exam_gate.html` and `POST /subject/<slug>/unlock_exam`.
  - Exam/quiz taker form now captures either `Student Code` OR guest details (`taker_name` optional, `taker_birth_date` & `taker_gender` required).
- **Public Teacher Signup Requests, Teacher-to-Admin Messaging & Permanent Notifications**:
  - Added public `/teacher/apply` (`TeacherRequestForm`, `TeacherRequest` model) and Admin approval/rejection hub `/admin/teacher-requests`.
  - Added `POST /teacher/message_admin` (`TeacherToAdminMessageForm`) rendered with distinct primary badge/subtle styling in Admin notifications.
  - Removed 3-day auto-deletion of `AdminNotification` entries; added permanent `/admin/notifications` and `/teacher/notifications` hubs.
- **Redesigned Collapsible Lecture Comments & Anonymous-Aware Teacher Replies**:
  - Collapsed lesson comments behind `#commentsToggleBtn` / `#commentsCollapse` on `page.html`, collecting metadata (`author_name`, `author_birth_date`, optional `personality_info`) in `#commentDetailsModal` when clicking Send.
  - Added threaded Teacher/Admin replies (`POST /subject/<slug>/page/<page_id>/comment/<comment_id>/reply`); anonymous teachers display `"From Teacher"` (`لە لایەن مامۆستاوە`) publicly while Admins see real identity in `/admin/comments`.
  - Replaced individual comment cards in the Admin sidebar with an unread comment counter (`is_read_by_admin`) linking to `/admin/comments`.
- **Complete Kurdish Translations & Testing**:
  - Updated 258 Sorani Kurdish translations (0 remaining) and compiled `.mo`.
  - Updated `tests/test_exam.py` and `tests/test_v080_features.py`, fixed Chart.js `_("Average Score")` `%` formatting crash, and added `tests/test_v090_features.py` (all 38 tests pass).

## RECENT CHANGES (v0.8.0)
- **Complete Kurdish Translations**:
  - Extracted and updated all 98 new/fuzzy strings in `app/translations/ku/LC_MESSAGES/messages.po` (0 untranslated/fuzzy remaining) and compiled `messages.mo`.
- **Teacher & Admin Comment Notification System + Admin Messaging**:
  - Added `TeacherNotification` model (`teacher_id`, `sender_id`, `notification_type`, `title`, `message`, `related_subject_id`, `related_page_id`, `is_read`, `created_at`).
  - Posting a lecture comment now dispatches rich notifications (Subject, Lesson, Author, Birth Date/Age, Optional Bio, Comment, and direct View Lesson link) to both `AdminNotification` and `TeacherNotification` for all teachers assigned to that subject.
  - Added `AdminMessageForm` and `POST /admin/message_teacher` allowing Admins to write messages to a specific teacher or All Teachers; rendered with visually distinct warning/gold styling (`bg-warning-subtle`, `border-warning`) in `teacher/dashboard.html` compared to lecture comment alerts (`border-info`).
  - Added mark-read and dismiss routes for teacher and admin notifications, plus bottom-up cleanup of `TeacherNotification` in `delete_page`, `delete_subject`, `delete_teacher`, `restore_system`, and `wipe_clean`.
- **Admin Notification Box Dark Mode Fix & Direct Subject Edit**:
  - Fixed `admin_dashboard.html` notifications card to use dark-mode-safe Bootstrap 5.3 semantic classes (`card-accent`, `bg-body-tertiary`, `text-body-emphasis`) instead of hardcoded `bg-light`/`text-dark`, and fixed display of `notification_type`, `title`, and `message`.
  - Added an **Edit** button (`/teacher/edit/subject/<id>`) directly on every subject card in `admin_dashboard.html` (and synced `SubjectTeacher` on edit).
- **Staff Birth Date, Optional Bio, Self-Profile Editing & Comment Birth Date**:
  - Added `birth_date` (DATE) and `bio` (TEXT) columns to `User` (`app/models.py`) and `author_birth_date` (DATE) to `PageComment`, with safe auto-migrations in `app/__init__.py`.
  - Replaced raw age input on lecture comments (`CommentForm`, `page.html`) with `author_birth_date` (`<input type="date">`, validated 5–120 years, not in future).
  - Added `TeacherProfileForm` and `POST /teacher/profile/update` so teachers and admins can update their own name, Kurdish name, birth date, optional bio, and password directly from their dashboard.
  - Updated `TeacherSignupForm`, `TeacherEditForm`, `admin_dashboard.html`, and `admin/edit_teacher.html` with optional `birth_date` and `bio`.
- **Testing**:
  - Updated `tests/test_v070_features.py` and added `tests/test_v080_features.py` (30/30 tests passing).

## RECENT CHANGES (v0.7.0)
- **Single Locked Theme (Removed Cyber Command)**:
  - Removed `[data-theme="cyber"]` CSS rules from `app/static/css/variables.css` and `app/static/style.css`.
  - Locked `data-theme="glass"` in `app/templates/base.html`, removed `setTheme()` and Cyber logo attributes, and cleared any legacy `app_theme` in `localStorage`.
  - Removed Interface Theme switcher cards from `admin_dashboard.html` and `teacher/dashboard.html` (Light/Dark mode toggle remains).
- **Multi-Teacher Subject Assignment & Individual Name Visibility**:
  - Added `POST /admin/subject/<subject_id>/teachers` (`manage_subject_teachers`) and collapsible multi-teacher checkbox assignment UI in `admin_dashboard.html`, plus multi-teacher selection in `add_subject()`.
  - Fixed stale/former teacher bug: removing a teacher or transferring a subject via `transfer_subject()` now deletes the former teacher's `SubjectTeacher` row so only currently assigned teachers can appear on `subject.html`.
  - Added per-subject individual visibility toggle `POST /subject/<subject_id>/toggle_my_name` on `teacher/dashboard.html` and synced global `toggle_name_visibility()` with `SubjectTeacher.show_name`.
  - Updated `subject_detail()` and `subject.html` to compute and render `visible_teachers` cleanly without trailing commas or empty labels.
- **Public Lecture Comment System**:
  - Added `PageComment` model (`page_id`, `author_name`, `author_age`, optional `personality_info`, `comment_text`, `created_at`) in `app/models.py` and `CommentForm` in `app/forms.py`.
  - Added `POST /subject/<slug>/page/<page_id>/comment` (rate-limited, CSRF-protected) in `app/routes/public.py` and staff moderation `POST /teacher/comment/delete/<comment_id>` in `app/routes/content.py`.
  - Added `#comments-section` UI in `app/templates/page.html` and bottom-up `PageComment` cleanup in `delete_page`, `delete_subject`, `delete_teacher`, `restore_system`, and `wipe_clean`.
- **Scroll-Preserving Language Toggle on Lesson Pages**:
  - Added floating language toggle button (`#floatingLangToggle`) in `app/templates/page.html`.
  - Added `sessionStorage` scroll-position save/restore logic in `app/templates/base.html` for all `/set-lang/` links so users stay at the same vertical reading position after switching languages.
- **Testing**:
  - Added `tests/test_v070_features.py` covering all 5 features (25/25 tests passing).

## RECENT CHANGES (v0.6.1)
- **Complete Student Removal & Blueprint Cleanup**:
  - Permanently removed `app/routes/student.py` and migrated public course/lecture/exam routes (`/subject/<slug>`, `/subject/<slug>/page/<page_id>`, `/subject/<slug>/exam`, `/subject/<slug>/lecture/<page_id>/quiz`, `/subject/<slug>/exam/submit`) into `app/routes/public.py`.
  - Removed deprecated student models (`Student`, `StudentAnswer`, `StudentPinnedSubject`, `LessonProgress`, `ExamProgress`) from `app/models.py` and simplified `ExamResult` to anonymous subject-level exam scores.
  - Removed deprecated student redirect routes (`/student/login`, `/student/signup`, `/student/settings`, `/admin/students`), `generate_access_code()` helper, and student locale/migration fallbacks in `app/__init__.py`.
  - Updated backup/restore/wipe logic in `app/routes/analytics.py` and template wording to remove all remaining student references.
- **Security, Config & Stability Audit Fixes**:
  - Replaced hardcoded `SECRET_KEY` fallback in `config.py` with `secrets.token_hex(32)` when unset.
  - Replaced hardcoded `debug=True` in `run.py` with `FLASK_DEBUG` environment variable control (defaulting to `False`).
  - Restricted `/test-lang` debug endpoint in `app/routes/public.py` to authenticated admins (`@login_required` + `is_admin`).
  - Added `is_public` visibility checks to `view_page`, `take_exam`, and `submit_exam`, plus subject-ownership validation for `page_id` and submitted question IDs.
  - Fixed `NameError` in `app/routes/teacher.py` (`delete_teacher`, `view_teacher`), added `try/except` + rollback for notification cleanup, fixed bottom-up deletion order (`Question` -> `Resource` -> `Page` -> `SubjectTeacher` -> `Subject`) in `delete_subject` and `delete_teacher`, and synced `SubjectTeacher` on `transfer_subject`.
  - Guarded `import_questions_step1` against empty/NaN answer cells and validated `subject` query params in `builder_info` / `builder_exam`.
  - Verified full test suite: 20/20 tests passing.

## RECENT CHANGES (v0.6.0)
- **Student Accounts & Management Removal**:
  - Removed student sign-up page (`student_signup.html`) and registration route (`/student/signup`).
  - Removed student login page (`student_login.html`) and route (`/student/login`). Deprecated student endpoints gracefully redirect to staff login (`/login`).
  - Removed student management system in Admin HQ: `/admin/students`, `/admin/edit/student/<id>`, `/admin/delete/student/<id>`, `/admin/delete/all/students`, and bulk student CSV import.
  - Removed `StudentForm`, `StudentSignupForm`, `StudentSettingsForm`, and `StudentEditForm` from `app/forms.py`.
  - Removed student analysis in teacher and admin pages: removed `/teacher/analytics`, `/teacher/analytics/student/<id>`, `/teacher/export/grades`, and `/teacher/export/student/answers/<id>`.
  - Removed "Class Insights" card, student ranking, and at-risk calculations from Teacher Dashboard.
  - Removed "Manage Students" and "Global Analytics" buttons from Admin HQ (`admin_dashboard.html`).
  - Removed "Total Students" metric from public stats (`stats.html`), replaced with Total Subjects count.
  - Removed student pinning and lesson progress tracking.
  - Updated exam engine: quizzes and exams can now be taken by visitors/learners without accounts, with instant grade calculation and flash notification feedback.
  - Cleaned up templates: deleted deprecated `app/templates/student/` directory, `student_signup.html`, `student_login.html`, `admin/students.html`, `admin/edit_student.html`, `teacher/analytics.html`, and `teacher/student_detail.html`.
  - Updated and verified test suite: 20/20 tests passing (100% pass rate).

## RECENT CHANGES (v0.5.0)
- **Multi-Teacher & Platform Features**:
  - Multi-teacher support for subjects via `SubjectTeacher` association model.
  - Admin notification system for system operations.
  - Responsive video embedding and mobile optimization.

## RECENT CHANGES (v0.4.4)
- **Teacher Kurdish Name Support**: Added `username_kurdish` field to User model for bilingual teacher name display:
  - `User`: `username_kurdish` (VARCHAR 20, nullable)
  - `TeacherSignupForm`: Added `username_kurdish` field with optional validator
  - `TeacherEditForm`: Added `username_kurdish` field for editing existing teachers
  - Updated `add_teacher()` and `edit_teacher()` routes to save Kurdish names
  - Updated `edit_teacher.html` template with Kurdish name input field
  - Updated `subject.html` to display Kurdish teacher name when locale is 'ku'
  - Added Kurdish translation "ناوی مامۆستا (کوردی)" for the form label

## RECENT CHANGES (v0.4.3)
- **Bilingual Form Enhancement**: Added Kurdish text input fields to all content-related forms:
  - `SubjectForm`: `name_kurdish`, `description_kurdish`
  - `PageForm`: `title_kurdish`
  - `InfoPageForm`: `title_kurdish`
  - `ResourceForm`: `title_kurdish`
  - `ToolForm`: `title_kurdish`, `description_kurdish`
  - `CommandForm`: `title_kurdish`, `description_kurdish`
- **Database Schema Update**: Added Kurdish columns to models:
  - `Subject`: `name_kurdish` (VARCHAR 100), `description_kurdish` (TEXT)
  - `Resource`: `title_kurdish` (VARCHAR 100)
  - `SystemCommand`: `title_kurdish` (VARCHAR 100), `description_kurdish` (TEXT)
  - `Tool`: `title_kurdish` (VARCHAR 100), `description_kurdish` (TEXT)
- **Route Updates**: Updated all create/edit routes to save/load Kurdish fields from forms to database
- **Migration Script**: Created `update_db_v043.py` for safe database schema migration
- **Translation Update**: Added 86 missing translation entries to Kurdish .po file
- **Template Updates**: Updated all relevant templates to display new Kurdish input fields

## 2. FILE STRUCTURE ARCHITECTURE

### File Categories
- **Git only (GitHub Repository)**:
  - Application logic: `app/`, `config.py`, `run.py`, `requirements.txt`
  - Localization files: `babel.cfg`, `app/translations/ku/LC_MESSAGES/messages.po`
  - Git files: `.gitignore`
  - Documentation and Logs: `SKILL.md`, `VersionDetails.txt`
  - Tests: `tests/`

- **Do NOT push to GitHub (One-time/Local only)**:
  - One-time migration scripts (deleted after use)
  - Local `.env` files with credentials
  - Cache folders: `__pycache__/`, `.pytest_cache/`
- **PythonAnywhere only (Server Production)**:
  - Production `.env` (contains actual production databse credentials and secrets)
  - Server logs (automatically generated by PythonAnywhere)
- **Local only (Development Machine)**:
  - Local `.env` (local dev secrets)
  - Virtual environments: `.venv_safe/`, `.venv_test/`

StatInfoProject_PlayGround (Project Root)
├── SKILL.md                  # This knowledge base
├── config.py                 # Production Config (MySQL connection + Pool Recycling)
├── requirements.txt          # Deps: Pandas, OpenPyXL, PyMySQL, Flask-Login
├── run.py                    # WSGI Entry Point
├── Elite-Prompter-Agent.md   # AI Prompt Engineering Guide
└── app/
    ├── __init__.py           # App Factory, Blueprints, Extensions (DB, Bcrypt, CSRF)
    ├── models.py             # Database Schema (Source of Truth)
    ├── forms.py              # WTForms definitions
    ├── routes/               # Blueprint Architecture (Modular Routing)
    │   ├── __init__.py        # Blueprint registry
    │   ├── admin.py          # Admin management routes
    │   ├── analytics.py      # Analytics and reporting
    │   ├── auth.py           # Authentication (login/logout)
    │   ├── content.py        # Content management (subjects, pages, questions)
    │   ├── helpers.py        # Utility functions
    │   ├── public.py         # Public routes (homepage, about, stats, courses, exams)
    │   ├── teacher.py        # Teacher dashboard and tools
    │   └── toolbase.py       # External tools management
    ├── static/
    │   ├── style.css         # CSS Variables for Themes (Glass/Cyber)
    │   ├── Logo/             # Branding Assets
    │   │   ├── Light_CyberCommand.svg
    │   │   ├── light_AcademicGlass.svg
    │   │   ├── Dark_CyberCommand.svg
    │   │   └── Dark_AcademicGlass.svg (Default Favicon)
    │   └── uploads/          # (Unused - We use text links for external resources)
    ├── translations/         # Babel Translations (.po, .mo files)
    └── templates/
        ├── about.html        # Editable Bilingual CMS Page
        ├── admin_dashboard.html # Admin HQ Dashboard
        ├── base.html         # Master Layout (MathJax, Navbar, Flash, Favicon, Locked Glass Theme)
        ├── exam.html         # Taking Bilingual Exam / Quiz Interface
        ├── exam_gate.html    # Student Code Gate for Hidden Exams/Quizzes
        ├── index.html        # Public Homepage & Bilingual Search
        ├── login.html        # Staff Login
        ├── page.html         # Lecture View (Video/Resources/Text/Collapsible Comments)
        ├── setup.html        # Initial Headmaster Setup
        ├── stats.html        # Public Analytics
        ├── subject.html      # Subject Overview & Syllabus
        ├── teacher_apply.html # Public Teacher Signup Request Form
        ├── teacher_profile.html # Public Teacher Profile (Respecting Privacy Switches)
        ├── toolbase.html     # Bilingual External Tools Directory
        ├── admin/
        │   ├── commands.html         # System Documentation Hub
        │   ├── comments.html         # Lecture Comments Moderation & Reply Hub
        │   ├── edit_about.html       # Bilingual About Editor
        │   ├── edit_teacher.html     # Edit Staff Account
        │   ├── import_preview.html   # Batch Import Confirmation UI
        │   ├── notifications.html    # Permanent Admin Notifications Hub
        │   ├── restore_center.html   # 21-CSV Backup/Restore & Wipe Center
        │   ├── stats.html            # Detailed Admin Statistics & CSV Export
        │   └── teacher_requests.html # Teacher Signup Request Approval Queue
        └── teacher/
            ├── builder.html          # Lecture Editor & Bilingual Question Bank Spreadsheet
            ├── dashboard.html        # Teacher Workspace & Profile Hub (Also Admin Inspector View)
            ├── edit_student.html     # Edit Code-Based Student Record
            ├── notifications.html    # Teacher Notifications Hub
            ├── private_builder.html  # Hidden Exam Bank Sheet & Auto-Generated Multi-Links
            ├── stats.html            # Teacher-Scoped Statistics Hub
            └── students.html         # Code-Based Student Roster & Admin Sharing
3. DATABASE SCHEMA (STRICT RULES)

Database Engine: MySQL (Production) / SQLite (Dev).
Constraint: InnoDB Engine (Enforces Foreign Keys).

Models & Fields (21 SQLAlchemy Models)

- User: id, username (String 100), username_kurdish (String 100, nullable), email, password_hash, gender (String 20, nullable), is_admin (Bool), show_name_on_subject (Bool, default=False), preferred_lang (String, default='en'), birth_date (Date, nullable), bio (Text, nullable), profile_public (Bool, default=True), profile_show_name (Bool, default=True), profile_show_bio (Bool, default=True), profile_show_age (Bool, default=True), profile_show_gender (Bool, default=True).
- TeacherRequest (`teacher_request`): id, name_en, name_ku, email, password_hash, gender, birth_date, bio (nullable), reason, status ('pending' | 'approved' | 'rejected'), reviewed_by_id (FK user.id), reviewed_at, admin_note, created_at.
- Subject: id, name, name_kurdish (VARCHAR 100, nullable), slug, description, description_kurdish (TEXT, nullable), teacher_id (FK user.id), is_public (Bool, default=True), exam_student_only (Bool, default=False).
- SubjectTeacher: id, subject_id (FK subject.id), teacher_id (FK user.id), is_primary (Bool), show_name (Bool, default=True), added_at. Unique (subject_id, teacher_id).
- Page (Lecture): id, title (VARCHAR 200), title_kurdish (VARCHAR 200, nullable), content_body (HTML), content_body_kurdish (HTML), subject_id (FK subject.id), quiz_student_only (Bool, default=False). Relationship: resources (Cascade Delete), questions (Backref), comments (Order by created_at).
- Resource: id, title, title_kurdish (VARCHAR 100, nullable), link, page_id (FK page.id).
- Question: id, question_text, option_a..option_d, question_text_kurdish (nullable), option_a_kurdish..option_d_kurdish (nullable), correct_answer, subject_id (FK subject.id), page_id (Nullable FK page.id), is_kurdish (Bool legacy).
- PrivateExam (`private_exam`): id, subject_id (FK subject.id), title, title_kurdish, access_token (String 32, unique), is_active (Bool), created_by_id (FK user.id), created_at.
- PrivateQuestion (`private_question`): id, subject_id (FK subject.id), question_text, question_text_kurdish, option_a..d, option_a_kurdish..d_kurdish, correct_answer, created_at.
- PrivateExamQuestion (`private_exam_question`): id, private_exam_id (FK private_exam.id), private_question_id (FK private_question.id). Unique (private_exam_id, private_question_id).
- Student (`student_record`): id, name_en, name_ku, birth_date (Date), gender, department_en, department_ku, student_code (String 16, unique, >= 8 chars, no password/login), created_by_id (FK user.id), created_at.
- StudentTeacher (`student_teacher`): id, student_id (FK student_record.id), teacher_id (FK user.id), assigned_at. Unique (student_id, teacher_id).
- CommentGuest (`comment_guest`): id, guest_code (String 16, unique), author_name, author_birth_date (Date), personality_info, created_at.
- ExamGuest (`exam_guest`): id, guest_code (String 16, unique), taker_name, taker_birth_date (Date), taker_gender, created_at.
- ExamResult: id, score (0-100), correct_count (nullable), total_questions (nullable), date_submitted, subject_id (FK subject.id), page_id (Nullable FK page.id), private_exam_id (Nullable FK private_exam.id), student_record_id (Nullable FK student_record.id), exam_guest_id (Nullable FK exam_guest.id), taker_name (nullable), taker_birth_date (nullable), taker_gender (nullable).
- PageComment (`page_comment`): id, page_id (FK page.id), parent_id (Self-FK page_comment.id, nullable), author_user_id (FK user.id, nullable), comment_guest_id (FK comment_guest.id, nullable), is_teacher_reply (Bool), is_read_by_admin (Bool), author_name, author_birth_date (Date), author_age (Integer, nullable legacy), personality_info (TEXT, nullable), comment_text (TEXT), created_at.
- AdminNotification: id, notification_type ('question_added' | 'question_edited' | 'page_added' | 'page_edited' | 'teacher_message' | 'teacher_request' | 'comment_added'), title, message, actor_type, actor_id, actor_name, related_subject_id, related_page_id, related_question_id, is_checked, checked_at, delete_scheduled_at, is_deleted, created_at (small box displays unread only; `/admin/notifications` persists until deleted).
- TeacherNotification: id, teacher_id (FK user.id), sender_id (FK user.id, nullable), notification_type ('comment' | 'admin_message'), title, message, related_subject_id, related_page_id, is_read, created_at (small box displays unread only; `/teacher/notifications` persists until deleted).
- SiteInfo: id, key, title, title_kurdish (VARCHAR 200, nullable), content, content_kurdish (HTML, nullable), last_updated.
- SystemCommand: id, title, title_kurdish (VARCHAR 100, nullable), command_text, description, description_kurdish (TEXT, nullable). Bulk Import Supported via `/admin/system/commands/import`.
- Tool: id, title, title_kurdish (VARCHAR 100, nullable), link, description, description_kurdish (TEXT, nullable), created_at.

4. CRITICAL LOGIC PATTERNS
A. The "Bottom-Up" Deletion Protocol (Anti-Crash)

To prevent IntegrityError 1451 (Foreign Key Fails), ALWAYS delete in this order:

StudentAnswers (The leaves)

ExamResults (The branches)

Questions / Resources

Pages / Lectures

Subjects / Students

Users (The trunk)

B. The "Ghost Exam" Filter

When rendering student history (student_detail_view in routes.py), verify:
if len(result.answers) > 0.

If an exam result exists but has 0 answers (because questions were deleted), it is a "Ghost".

Action: Do not render card. Optionally delete the record silently.

C. Bulk Import Engine (Memory-Only)

Workflow: User uploads file -> Pandas reads stream -> Preview Rendered -> User Confirms -> JSON sent to Backend -> DB Commit.

Constraint: Never save uploaded files to static/uploads to save disk quota.

Encoding: Always use utf-8-sig (BOM) for CSV read/write to support Kurdish characters in Excel.

Strict Quoting: Use csv.QUOTE_ALL to prevent commas in questions from breaking columns.

D. The "Keep-Alive" Heartbeat

Route: /keep_alive.

Function: Returns simple JSON. Used by UptimeRobot to ping every 5 minutes.

Goal: Prevents PythonAnywhere from putting the WSGI process to sleep (Cold Start prevention).

E. Dual-Mode Exam Engine

Route: take_exam(slug, page_id=None)

Logic:

If page_id exists: Query Question.query.filter_by(page_id=page_id). (Lecture Quiz).

If page_id is None: Query Question.query.filter_by(subject_id=subject.id). (Final Exam).

If page_id is None: Query Question.query.filter_by(subject_id=subject.id). (Final Exam).

F. Full System Restore Strategy (Zero-Loss 21-CSV Backup)

Routes: `/admin/export/full_backup` (ZIP download) & `/admin/system/restore` (UI: `restore_center.html`).

Logic:
1. Wipe: `_wipe_all_non_user_tables()` deletes rows in strict InnoDB bottom-up FK order, then `1_users.csv` upserts/syncs users safely.
2. Rehydrate: Streams UTF-8-SIG CSVs from the backup ZIP, normalizing line endings cleanly (`\r\n`/`\r` -> `\n` without touching `rn` substrings).
3. Strict Dependency Order (21 CSVs):
   `1_users.csv` -> `14_teacher_requests.csv` -> `2_subjects.csv` -> `3_subject_teachers.csv` -> `8_students.csv` -> `13_student_teachers.csv` -> `4_pages.csv` -> `5_resources.csv` -> `6_questions.csv` -> `17_private_exams.csv` -> `18_private_questions.csv` -> `19_private_exam_questions.csv` -> `20_comment_guests.csv` -> `21_exam_guests.csv` -> `7_results.csv` -> `12_comments.csv` (parents before replies) -> `9_commands.csv` -> `10_siteinfo.csv` -> `11_tools.csv` -> `15_admin_notifications.csv` -> `16_teacher_notifications.csv`.

Backup Compatibility: Backwards compatible with v0.6–v0.9.0 backup ZIPs while preserving 100% of v0.9.1 fields and foreign keys.

G. The Translation Toggle Fix (v2.x)

- `select_locale()` in `__init__.py`: Session ALWAYS takes priority over DB `preferred_lang`. If `session['lang']` is set, return it immediately without querying the DB.
- **CRITICAL**: Flask-Babel caches locale on first access. Must call `flask_babel.refresh()` in `/set_lang/<lang>` route after session update to force cache refresh.
- Added `has_request_context()` checking in `select_locale()` to prevent RuntimeError when accessing session outside request context.
- The canonical Kurdish locale identifier is `ku`. This string must be consistent across `select_locale()`, `set_lang()` route, and all Jinja2 comparisons in `base.html`.
- Always run `pybabel compile -d app/translations` after editing `.po` files.
- Debug endpoint `/test-lang` provides real-time translation verification and locale debugging information.

5. UI/UX STANDARDS

Bilingual Support:

Questions marked is_kurdish=True must have CSS class .rtl-question.

CSS in exam.html handles flex-direction reversal and text alignment.

Brand Name Consistency:
The brand name "StatInfoProject" must be wrapped in a container (e.g., `<div>`) with `style="direction: ltr !important;"` in the navbar. This prevents Bootstrap's RTL flexbox from reversing the character order in Kurdish mode while allowing "StatInfo" (white) and "Project" (green) to be styled independently.

Rich Text Editor (TinyMCE) Standards:
We use TinyMCE configured with open-source settings to mimic MS Word.
- Always include the full suite of open-source plugins (e.g. `anchor`, `pagebreak`, `wordcount`).
- Use `content_style` to constrain the editor body to `max-width: 21cm` and `min-height: 29.7cm` (A4 proportions) on a grey `#f0f2f5` html background to simulate a physical page.
- Enable `browser_spellcheck`, full `menubar`, and `contextmenu`.
- **Video Support**: Added mobile-responsive video embedding with auto-detection for YouTube/Vimeo URLs.
- **Mobile Optimization**: Videos automatically wrapped in responsive containers with 16:9 aspect ratio and proper mobile scaling.
- **Toolbar Enhancement**: Added "Video" and "Responsive Video" buttons to TinyMCE toolbar for easy video embedding.

Dark Mode:

Use var(--bg-body) and var(--text-main) CSS variables.

Never use hardcoded #fff or #000 for text/backgrounds.

Use text-body-emphasis instead of text-dark.

Mobile Responsive:

mjx-container { overflow-x: auto } (MathJax scroll).

img { max-width: 100% !important; height: auto } (Prevent image blowout).

**Video Responsive**: All embedded videos automatically use responsive containers with 16:9 aspect ratio. Videos scale properly on mobile devices with Bootstrap 5 breakpoints. Support for YouTube, Vimeo, and direct embeds with mobile-optimized loading.

6. MAINTENANCE COMMANDS CHEAT SHEET

Execute these in the PythonAnywhere Bash Console.

Database Operations (Python Shell)
code
Python
download
content_copy
expand_less
# 1. Safe Schema Update (Create missing tables)
from app import create_app, db
app = create_app()
with app.app_context():
    db.create_all()
exit()

# 2. Nuclear Reset (WIPE ALL DATA)
from app import create_app, db
app = create_app()
with app.app_context():
    db.drop_all()
    db.create_all()
exit()
Server Operations (Bash)

Activate Env: workon my-virtualenv

Sync Code: git pull

Install Libs: pip install --no-cache-dir -r requirements.txt

Clear Cache: rm -rf ~/.cache/pip

Access SQL: mysql -u StatInfoProject -h StatInfoProject.mysql.pythonanywhere-services.com -p 'StatInfoProject$school_db'

Custom Scripts

Fix Grading Error: python regrade_all.py (Scans all answers against current Question Answer Key and updates scores).

Convert SQL to Backup: python convert_sql_to_backup.py (Converts database to CSV backup format).

Update Database Schema: python update_db.py (Handles database migrations).

Update Database Schema v0.4.3: python update_db_v043.py (Adds Kurdish bilingual columns to Subject, Resource, SystemCommand, and Tool tables).

Fix Quote Encoding: python fix_quotes.py (Fixes Kurdish character encoding issues).

Add Subject Public Flag: python add_subject_is_public.py (Adds is_public column to subjects).

Drop Group ID: python drop_group_id.py (Removes deprecated group_id column).

Compile Translations: pybabel compile -d app/translations (Compiles .po files to .mo for Kurdish translations).

7. ERROR DICTIONARY

Error 1451 (IntegrityError): You tried to delete a parent row (like a Student or Question) without deleting the children (Answers) first. See "Bottom-Up Deletion".

Error 500 (Internal Server): Usually a Jinja template trying to access a variable that wasn't passed by routes.py. Check route context.

Error 2013 (Lost Connection): MySQL timeout. Ensure pool_recycle: 280 is in config.py.


## 8. DEPLOYMENT AUTOMATION
**Git Credentials:**
- Username: `havin231`
- Token: Configured via GitHub Personal Access Token (stored in Git credentials / environment).

**Auto-Push Protocol:**
After every significant change, run:
```bash
git add .
git commit -m "feat: [Description of change]"
git push
```
