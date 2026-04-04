from app.routes.public import public
from app.routes.auth import auth
from app.routes.student import student
from app.routes.teacher import teacher
from app.routes.admin import admin
from app.routes.content import content
from app.routes.analytics import analytics
from app.routes.toolbase import tools

# All blueprints, ready for registration in the app factory
all_blueprints = [public, auth, student, teacher, admin, content, analytics, tools]
