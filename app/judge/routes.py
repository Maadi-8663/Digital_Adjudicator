"""Judge routes."""

from datetime import datetime

from flask import abort, jsonify, render_template, request
from flask_login import current_user

from . import judge_bp, judge_required
from .. import db
from ..models import (
    Application, ApplicationModule, Competition, Module, Score
)


# ===== Dashboard =====

@judge_bp.route("/")
@judge_required
def dashboard():
    modules = list(current_user.judged_modules)
    seen_ids = set()
    competitions = []
    for m in modules:
        c = m.competition
        if c.id not in seen_ids:
            seen_ids.add(c.id)
            competitions.append(c)
    return render_template(
        "judge/dashboard.html",
        modules=modules, competitions=competitions,
    )


# ===== Module live view =====

def _own_module(module_id: int) -> Module:
    m = Module.query.get_or_404(module_id)
    if current_user not in m.judges:
        abort(403)
    return m


@judge_bp.route("/module/<int:module_id>")
@judge_required
def module_view(module_id):
    m = _own_module(module_id)

    # Currently on-stage performance for this module
    current_am = (
        ApplicationModule.query
        .filter_by(module_id=m.id, status="on_stage")
        .first()
    )
    current_app = Application.query.get(current_am.application_id) if current_am else None
    current_score = None
    if current_am:
        current_score = Score.query.filter_by(
            application_id=current_am.application_id,
            module_id=m.id,
            judge_id=current_user.id,
        ).first()

    # Pending scores: performances where the speech has ended but I haven't submitted a rating
    pending = []
    ended_ams = (
        ApplicationModule.query
        .filter_by(module_id=m.id)
        .filter(ApplicationModule.speech_ended_at.isnot(None))
        .all()
    )
    for am in ended_ams:
        if am.scoring_seconds_left is None or am.scoring_seconds_left <= 0:
            continue
        my_score = Score.query.filter_by(
            application_id=am.application_id,
            module_id=m.id,
            judge_id=current_user.id,
        ).first()
        if my_score and my_score.rating is not None:
            continue  # already submitted
        app = Application.query.get(am.application_id)
        pending.append({"am": am, "app": app, "score": my_score})

    return render_template(
        "judge/module_view.html",
        m=m, current_am=current_am, current_app=current_app,
        current_score=current_score, pending=pending,
    )


# ===== Module state polling (light) =====

@judge_bp.route("/module/<int:module_id>/state.json")
@judge_required
def module_state_json(module_id):
    m = _own_module(module_id)

    current_am = (
        ApplicationModule.query
        .filter_by(module_id=m.id, status="on_stage")
        .first()
    )
    if not current_am:
        return jsonify(ok=True, current=None, module_status=m.status)

    app = Application.query.get(current_am.application_id)
    return jsonify(
        ok=True,
        module_status=m.status,
        current={
            "application_id": app.id,
            "name": app.full_name,
            "institution": app.institution,
            "photo_url": app.photo_url,
            "topic": current_am.topic.title if current_am.topic else None,
            "position": current_am.turn_position,
            "timer_state": current_am.timer_state,
            "elapsed_seconds": current_am.speech_elapsed_seconds,
        },
    )


# ===== Per-performance score polling =====

@judge_bp.route("/module/<int:module_id>/score/<int:application_id>/state.json")
@judge_required
def score_state_json(module_id, application_id):
    m = _own_module(module_id)
    am = ApplicationModule.query.filter_by(
        module_id=m.id, application_id=application_id
    ).first_or_404()
    score = Score.query.filter_by(
        application_id=application_id, module_id=m.id, judge_id=current_user.id
    ).first()

    return jsonify(
        ok=True,
        timer_state=am.timer_state,
        elapsed_seconds=am.speech_elapsed_seconds,
        speech_ended_at=am.speech_ended_at.isoformat() if am.speech_ended_at else None,
        scoring_seconds_left=am.scoring_seconds_left,
        status=am.status,
        notes=(score.notes if score else ""),
        rating=(score.rating if score else None),
        feedback=(score.feedback if score else ""),
        submitted=(score is not None and score.rating is not None),
    )


# ===== Timer controls (shared across all judges of the module) =====

@judge_bp.route("/module/<int:module_id>/timer/<int:application_id>/<action>", methods=["POST"])
@judge_required
def timer_action(module_id, application_id, action):
    m = _own_module(module_id)
    am = ApplicationModule.query.filter_by(
        module_id=m.id, application_id=application_id
    ).first_or_404()

    now = datetime.utcnow()

    if action == "start":
        if am.timer_state == "not_started":
            am.speech_started_at = now
            am.speech_paused_at = None
            am.speech_total_paused_seconds = 0
    elif action == "pause":
        if am.timer_state == "running":
            am.speech_paused_at = now
    elif action == "resume":
        if am.timer_state == "paused":
            pause_seconds = (now - am.speech_paused_at).total_seconds()
            am.speech_total_paused_seconds = (am.speech_total_paused_seconds or 0) + int(pause_seconds)
            am.speech_paused_at = None
    elif action == "stop":
        if am.timer_state in ("running", "paused"):
            if am.timer_state == "paused" and am.speech_paused_at is not None:
                pause_seconds = (now - am.speech_paused_at).total_seconds()
                am.speech_total_paused_seconds = (am.speech_total_paused_seconds or 0) + int(pause_seconds)
                am.speech_paused_at = None
            am.speech_ended_at = now
    else:
        return jsonify(ok=False, error="unknown action"), 400

    db.session.commit()
    return jsonify(
        ok=True,
        timer_state=am.timer_state,
        elapsed_seconds=am.speech_elapsed_seconds,
    )


# ===== Notes autosave (per judge) =====

@judge_bp.route("/module/<int:module_id>/score/<int:application_id>/notes", methods=["POST"])
@judge_required
def save_notes(module_id, application_id):
    m = _own_module(module_id)
    am = ApplicationModule.query.filter_by(
        module_id=m.id, application_id=application_id
    ).first_or_404()

    notes_text = (request.json.get("notes") if request.is_json else request.form.get("notes")) or ""

    score = Score.query.filter_by(
        application_id=application_id, module_id=m.id, judge_id=current_user.id
    ).first()
    if score is None:
        score = Score(
            application_id=application_id, module_id=m.id,
            judge_id=current_user.id, notes=notes_text,
        )
        db.session.add(score)
    else:
        # Don't let notes overwrite if already submitted
        if score.rating is None:
            score.notes = notes_text

    db.session.commit()
    return jsonify(ok=True)


# ===== Final submit: rating + feedback =====

@judge_bp.route("/module/<int:module_id>/score/<int:application_id>/submit", methods=["POST"])
@judge_required
def submit_score(module_id, application_id):
    m = _own_module(module_id)
    am = ApplicationModule.query.filter_by(
        module_id=m.id, application_id=application_id
    ).first_or_404()

    if am.speech_ended_at is None:
        return jsonify(ok=False, error="Speech timer must be stopped before submitting."), 400
    if am.scoring_seconds_left is not None and am.scoring_seconds_left <= 0:
        return jsonify(ok=False, error="The 15-minute scoring window has closed."), 400

    payload = request.json if request.is_json else request.form
    try:
        rating = float(payload.get("rating"))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Rating must be a number from 0 to 10."), 400
    if rating < 0 or rating > 10:
        return jsonify(ok=False, error="Rating must be between 0 and 10."), 400

    feedback = (payload.get("feedback") or "").strip()
    notes_text = (payload.get("notes") or "").strip() or None

    score = Score.query.filter_by(
        application_id=application_id, module_id=m.id, judge_id=current_user.id
    ).first()
    if score is None:
        score = Score(
            application_id=application_id, module_id=m.id, judge_id=current_user.id,
        )
        db.session.add(score)
    if score.rating is not None:
        return jsonify(ok=False, error="You have already submitted a score for this performance."), 400

    score.rating = rating
    score.feedback = feedback
    if notes_text is not None:
        score.notes = notes_text

    db.session.commit()
    return jsonify(ok=True, rating=rating)
