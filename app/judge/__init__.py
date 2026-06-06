"""Judge blueprint - ballots and scoring (Phase 3)."""

from functools import wraps
from flask import Blueprint, abort
from flask_login import current_user, login_required

judge_bp = Blueprint("judge", __name__, template_folder="../templates/judge")


def judge_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_judge:
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


from . import routes  # noqa: E402,F401
