"""Admin blueprint - competition setup and management."""

from functools import wraps
from flask import Blueprint, abort
from flask_login import current_user, login_required

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


from . import routes  # noqa: E402,F401
