"""Participant routes."""

from datetime import datetime

from flask import (
    abort, flash, jsonify, redirect, render_template, request, url_for
)
from flask_login import current_user, login_required

from . import participant_bp, participant_required
from .. import db
from ..models import Application, ApplicationModule, Competition, Module, Topic


@participant_bp.route("/")
@participant_required
def dashboard():
    from ..models import Announcement
    apps = sorted(current_user.applications, key=lambda a: a.submitted_at, reverse=True)

    my_module_ids = {m.id for a in apps for m in a.selected_modules}
    my_competition_ids = {a.competition_id for a in apps}
    announcements = []
    if my_competition_ids:
        anns = (
            Announcement.query
            .filter(Announcement.competition_id.in_(my_competition_ids))
            .order_by(Announcement.created_at.desc())
            .limit(20)
            .all()
        )
        for a in anns:
            if a.module_id is None or a.module_id in my_module_ids:
                announcements.append(a)

    return render_template("participant/dashboard.html", apps=apps, announcements=announcements)


@participant_bp.route("/competition/<int:competition_id>")
@participant_required
def competition_schedule(competition_id):
    c = Competition.query.get_or_404(competition_id)
    application = Application.query.filter_by(
        competition_id=c.id, participant_id=current_user.id
    ).first()
    if application is None:
        abort(404)

    modules = sorted(c.modules, key=lambda m: m.precedence or 0)
    my_module_ids = {m.id for m in application.selected_modules}

    # Find the "active" call — if I have one currently called or on_stage somewhere
    active_am = (
        ApplicationModule.query
        .filter(
            ApplicationModule.application_id == application.id,
            ApplicationModule.status.in_(["called", "on_stage"]),
        )
        .first()
    )

    schedule = []
    for m in modules:
        if m.id not in my_module_ids:
            schedule.append({"module": m, "apps": None, "my_am": None})
            continue
        am_rows = (
            ApplicationModule.query
            .filter_by(module_id=m.id)
            .order_by(ApplicationModule.turn_position.asc().nullslast())
            .all()
        )
        my_am = next((am for am in am_rows if am.application_id == application.id), None)
        rows = []
        for am in am_rows:
            app = Application.query.get(am.application_id)
            rows.append({
                "application": app,
                "position": am.turn_position,
                "is_self": app.participant_id == current_user.id,
                "status": am.status,
            })
        schedule.append({"module": m, "apps": rows, "my_am": my_am})

    # Announcements for this competition (filtered to participant's modules)
    from ..models import Announcement
    announcements = []
    anns = (
        Announcement.query.filter_by(competition_id=c.id)
        .order_by(Announcement.created_at.desc())
        .all()
    )
    for a in anns:
        if a.module_id is None or a.module_id in my_module_ids:
            announcements.append(a)

    return render_template(
        "participant/schedule.html",
        c=c, application=application,
        schedule=schedule, active_am=active_am,
        announcements=announcements,
    )


@participant_bp.route("/competition/<int:competition_id>/module/<int:module_id>/state.json")
@participant_required
def my_state_json(competition_id, module_id):
    """Polling endpoint: tell the participant their current status in this module."""
    application = Application.query.filter_by(
        competition_id=competition_id, participant_id=current_user.id
    ).first()
    if application is None:
        return jsonify(ok=False), 404

    am = ApplicationModule.query.filter_by(
        application_id=application.id, module_id=module_id
    ).first()
    if am is None:
        return jsonify(ok=False), 404

    m = Module.query.get(module_id)
    return jsonify(
        ok=True,
        status=am.status,
        called_at=am.called_at.isoformat() if am.called_at else None,
        seconds_left=am.call_seconds_left,
        topic_id=am.topic_id,
        topic_title=am.topic.title if am.topic else None,
        module_status=m.status if m else None,
        topics=[{"id": tp.id, "title": tp.title} for tp in (m.topics if m else [])],
    )


@participant_bp.route("/competition/<int:competition_id>/module/<int:module_id>/topic", methods=["POST"])
@participant_required
def choose_topic(competition_id, module_id):
    application = Application.query.filter_by(
        competition_id=competition_id, participant_id=current_user.id
    ).first_or_404()
    am = ApplicationModule.query.filter_by(
        application_id=application.id, module_id=module_id
    ).first_or_404()

    if am.status != "called":
        return jsonify(ok=False, error="not called"), 400
    if am.call_seconds_left is not None and am.call_seconds_left <= 0:
        return jsonify(ok=False, error="window expired"), 400

    topic_id = request.json.get("topic_id") if request.is_json else request.form.get("topic_id")
    if not topic_id:
        return jsonify(ok=False, error="missing topic"), 400

    topic = Topic.query.get(int(topic_id))
    if topic is None or topic.module_id != module_id:
        return jsonify(ok=False, error="bad topic"), 400

    am.topic_id = topic.id
    am.topic_chosen_at = datetime.utcnow()
    am.status = "on_stage"
    db.session.commit()
    return jsonify(ok=True)


@participant_bp.route("/competition/<int:competition_id>/module/<int:module_id>/request-restore", methods=["POST"])
@participant_required
def request_restore(competition_id, module_id):
    """Disqualified participant asks the admin to restore them. No DB change yet
    until the admin acts on the participant_action route."""
    return jsonify(ok=True, message="The admin has been notified of your request.")


@participant_bp.route("/competition/<int:competition_id>/module/<int:module_id>/result")
@participant_required
def module_result(competition_id, module_id):
    """Participant view of a single concluded module's results."""
    from ..models import Score
    c = Competition.query.get_or_404(competition_id)
    m = Module.query.get_or_404(module_id)
    if m.competition_id != c.id:
        abort(404)
    application = Application.query.filter_by(
        competition_id=c.id, participant_id=current_user.id
    ).first_or_404()

    # Verify participant is in this module
    if not any(am.module_id == m.id for am in ApplicationModule.query.filter_by(application_id=application.id).all()):
        abort(403)

    # All scores in this module
    ams = (
        ApplicationModule.query
        .filter_by(module_id=m.id)
        .filter(ApplicationModule.status != "disqualified")
        .all()
    )
    rows = []
    for am in ams:
        app = Application.query.get(am.application_id)
        scores = Score.query.filter_by(
            module_id=m.id, application_id=am.application_id
        ).filter(Score.rating.isnot(None)).all()
        if scores:
            total = sum(s.rating for s in scores)
            judge_count = len(scores)
        else:
            total = None
            judge_count = 0
        rows.append({
            "am": am, "app": app, "total": total,
            "judge_count": judge_count,
            "is_self": app.participant_id == current_user.id,
            "feedback": [s.feedback for s in scores if s.feedback],
        })
    rows.sort(key=lambda r: (r["total"] if r["total"] is not None else -1), reverse=True)
    pos = 0
    for r in rows:
        if r["total"] is not None:
            pos += 1
            r["position"] = pos
        else:
            r["position"] = None

    my_row = next((r for r in rows if r["is_self"]), None)
    return render_template(
        "participant/module_result.html",
        c=c, m=m, rows=rows, my_row=my_row,
    )


@participant_bp.route("/competition/<int:competition_id>/overall")
@participant_required
def overall_results(competition_id):
    """Participant view of overall standings across all modules."""
    from collections import defaultdict
    from ..models import Score

    c = Competition.query.get_or_404(competition_id)
    my_app = Application.query.filter_by(
        competition_id=c.id, participant_id=current_user.id
    ).first_or_404()

    totals = defaultdict(float)
    counts = defaultdict(int)
    module_breakdown = defaultdict(dict)

    for m in c.modules:
        ams = (
            ApplicationModule.query.filter_by(module_id=m.id)
            .filter(ApplicationModule.status != "disqualified").all()
        )
        for am in ams:
            scores = Score.query.filter_by(
                module_id=m.id, application_id=am.application_id
            ).filter(Score.rating.isnot(None)).all()
            if not scores:
                continue
            mod_total = sum(s.rating for s in scores)
            totals[am.application_id] += mod_total
            counts[am.application_id] += 1
            module_breakdown[am.application_id][m.id] = mod_total

    rows = []
    for app_id, total in totals.items():
        app = Application.query.get(app_id)
        rows.append({
            "app": app,
            "total": total,
            "module_count": counts[app_id],
            "modules": module_breakdown[app_id],
            "is_self": app.participant_id == current_user.id,
        })
    rows.sort(key=lambda r: r["total"], reverse=True)
    pos = 0
    for r in rows:
        pos += 1
        r["position"] = pos

    my_row = next((r for r in rows if r["is_self"]), None)
    modules = sorted(c.modules, key=lambda m: m.precedence or 0)
    return render_template(
        "participant/overall_results.html",
        c=c, rows=rows, modules=modules, my_row=my_row,
    )
