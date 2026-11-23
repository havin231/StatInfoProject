# AGENT SKILL: StatInfoPRO LMS Specialist

> [!IMPORTANT]
> **MAINTENANCE RULES:**
> 1. This `SKILL.md` file MUST be updated after EVERY change to the codebase to maintain an accurate source of truth for the agent.
> 2. Whenever a change or new feature is added, **VersionDetails.txt** MUST be updated with the details, changes, and improvements.
> 3. Whenever a change or new feature is added, a new versioned snapshot folder (e.g. `version_0.4.2`) MUST be created inside `/home/havin/Documents/statinfopro/` copying all current project files.
> 4. Ensure the File Organization (Git, PythonAnywhere, Local) inside this file remains up to date.


## 1. PROJECT IDENTITY & CONTEXT
- **System Name:** StatInfoProject (StatInfoPRO)
- **Current Version:** 0.7.0 (2026-11-23)
- **Deployment:** PythonAnywhere (Linux/Bash/MySQL).
- **Primary Language:** Python 3.10 / Flask 3.0.0.
- **Frontend:** HTML5, Bootstrap 5.3, Jinja2, Custom CSS Variables.
- **Context:** A bilingual (English/Kurdish) Learning Management System for the University of Sulaimani.

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
        ├── base.html         # Master Layout (MathJax, Navbar, Flash, Favicon)
        ├── login.html        # Staff Login
        ├── index.html        # Public Homepage
        ├── about.html        # Editable CMS Page
        ├── stats.html        # Public Analytics
        ├── subject.html      # Subject Overview
        ├── page.html         # Lecture View (Video/Resources/Text)
        ├── exam.html         # Taking Exam / Quiz Interface
        ├── admin/
        │   ├── admin_dashboard.html # Main HQ (Buttons for Backup, Commands)
        │   ├── commands.html        # System Documentation Hub
        │   └── import_preview.html  # Batch Import Confirmation UI
        └── teacher/
            ├── dashboard.html       # Teacher View
            └── builder.html         # Multi-tool: Page Editor & Question Bank Spreadsheet
3. DATABASE SCHEMA (STRICT RULES)

Database Engine: MySQL (Production) / SQLite (Dev).
Constraint: InnoDB Engine (Enforces Foreign Keys).

Models & Fields

User: id, username, username_kurdish (String 20, nullable), email, password_hash, is_admin (Bool), show_name_on_subject (Bool, default=False), preferred_lang (String, default='en').

Subject: id, name, name_kurdish (VARCHAR 100, nullable), slug, description, description_kurdish (TEXT, nullable), teacher_id, is_public (Bool, default=True).

Page (Lecture): id, title, content_body (HTML), content_body_kurdish (HTML), subject_id.

Relationship: resources (Cascade Delete), questions (Backref).

Resource: id, title, title_kurdish (VARCHAR 100, nullable), link, page_id.

Question: id, question_text, option_a...option_d, correct_answer, subject_id.

page_id (Nullable): Links question to specific lecture.

is_kurdish (Bool): Triggers RTL styling.

ExamResult: id, score, date_submitted, subject_id (anonymous exam score summary).

SiteInfo: id, key, title, content, content_kurdish (HTML, nullable), last_updated.

SystemCommand: id, title, title_kurdish (VARCHAR 100, nullable), command_text, description, description_kurdish (TEXT, nullable).

Bulk Import Supported: Yes (via `/admin/system/commands/import`). CSV columns: Title, Title_Kurdish (optional), Command, Description (optional), Description_Kurdish (optional).

Tool: id, title, title_kurdish (VARCHAR 100, nullable), link, description, description_kurdish (TEXT, nullable), created_at.

PageComment: id, page_id (FK page.id), author_name (VARCHAR 100), author_age (Integer), personality_info (TEXT, nullable), comment_text (TEXT), created_at.

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

F. Full System Restore Strategy (The Nuclear Option)

Route: /admin/system/restore (UI: restore_center.html)

Logic:
1.  Wipe: db.drop_all() -> db.create_all(). (Top-Down deletion by definition).
2.  Rehydrate: Parse ZIP of CSVs.
3.  Strict Order: User -> Subject -> Student -> Page -> Resource -> Question -> ExamResult -> Answer.

Constraint: Export function now includes `2_subjects.csv` (with `is_public`), and PK/FK columns to ensure lossless restoration.
Backup Compatibility: Only Backups created AFTER Jan 2026 (v2.1) are supported. Old backups are backwards compatible with the `is_public` field.

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
