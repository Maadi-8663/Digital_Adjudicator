"""Participant blueprint - register and follow results (Phase 4)."""

from functools import wraps
from flask import Blueprint, abort
from flask_login import current_user, login_required

participant_bp = Blueprint("participant", __name__, template_folder="../templates/participant")


def participant_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_participant:
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


from . import routes  # noqa: E402,F401
