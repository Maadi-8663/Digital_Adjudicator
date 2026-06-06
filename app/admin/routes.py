"""Admin routes - competition setup, modules, topics, form fields."""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from . import admin_bp, admin_required
from .forms import (
    CreateCompetitionForm, ModuleForm, TopicForm, BulkTopicsForm, FormFieldForm,
    AddJudgeForm, AssignExistingJudgeForm,
)
from .. import db
from ..models import Competition, Module, Topic, FormField, User


# ===== Dashboard =====

@admin_bp.route("/")
@admin_required
def dashboard():
    competitions = (
        Competition.query.filter_by(admin_id=current_user.id)
        .order_by(Competition.created_at.desc()).all()
    )
    return render_template("admin/dashboard.html", competitions=competitions)


# ===== Create competition =====

@admin_bp.route("/competition/new", methods=["GET", "POST"])
@admin_required
def create_competition():
    form = CreateCompetitionForm()
    if form.validate_on_submit():
        t = Competition(
            name=form.name.data.strip(),
            description=(form.description.data or "").strip() or None,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            venue=(form.venue.data or "").strip() or None,
            admin_id=current_user.id,
            status="setup",
        )
        db.session.add(t)
        db.session.commit()
        flash(f"'{t.name}' has been created. Now add modules and topics.", "success")
        return redirect(url_for("admin.competition_detail", competition_id=t.id))
    return render_template("admin/create_competition.html", form=form)


# ===== Competition detail =====

def _own_competition(competition_id: int) -> Competition:
    t = Competition.query.get_or_404(competition_id)
    if t.admin_id != current_user.id:
        abort(403)
    return t


@admin_bp.route("/competition/<int:competition_id>")
@admin_required
def competition_detail(competition_id):
    t = _own_competition(competition_id)
    return render_template("admin/competition_detail.html", t=t)


@admin_bp.route("/competition/<int:competition_id>/status/<new_status>", methods=["POST"])
@admin_required
def change_status(competition_id, new_status):
    t = _own_competition(competition_id)
    valid = set(Competition.STATUS_LABELS.keys())
    if new_status not in valid:
        flash("That status is not recognised.", "error")
        return redirect(url_for("admin.competition_detail", competition_id=t.id))

    # Redirect to setup page instead of letting admin jump straight to in_progress
    if new_status == "in_progress" and t.status == "registration_closed":
        return redirect(url_for("admin.setup", competition_id=t.id))

    # Block opening for registration unless every module is complete
    if new_status == "open_for_registration":
        if not t.modules:
            flash("Add at least one module before opening registration.", "error")
            return redirect(url_for("admin.competition_detail", competition_id=t.id))
        incomplete = t.incomplete_modules
        if incomplete:
            names = ", ".join(m.name for m in incomplete)
            flash(
                f"Cannot open registration. These modules are incomplete: {names}. "
                f"Each module needs at least one topic and at least one judge.",
                "error",
            )
            return redirect(url_for("admin.competition_detail", competition_id=t.id))

    t.status = new_status
    db.session.commit()
    flash(f"Status changed to '{t.status_label}'.", "success")
    return redirect(url_for("admin.competition_detail", competition_id=t.id))


# ===== Modules =====

@admin_bp.route("/competition/<int:competition_id>/module/add", methods=["GET", "POST"])
@admin_required
def add_module(competition_id):
    t = _own_competition(competition_id)
    form = ModuleForm()
    if form.validate_on_submit():
        m = Module(
            competition_id=t.id,
            name=form.name.data.strip(),
            description=(form.description.data or "").strip() or None,
            precedence=len(t.modules) + 1,
        )
        db.session.add(m)
        db.session.commit()
        flash(f"Module '{m.name}' added.", "success")
        return redirect(url_for("admin.module_detail", competition_id=t.id, module_id=m.id))
    return render_template("admin/module_form.html", form=form, t=t, mode="add")


@admin_bp.route("/competition/<int:competition_id>/module/<int:module_id>")
@admin_required
def module_detail(competition_id, module_id):
    t = _own_competition(competition_id)
    m = Module.query.get_or_404(module_id)
    if m.competition_id != t.id:
        abort(404)
    return render_template("admin/module_detail.html", t=t, m=m)


@admin_bp.route("/competition/<int:competition_id>/module/<int:module_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_module(competition_id, module_id):
    t = _own_competition(competition_id)
    m = Module.query.get_or_404(module_id)
    if m.competition_id != t.id:
        abort(404)
    form = ModuleForm(obj=m)
    if form.validate_on_submit():
        m.name = form.name.data.strip()
        m.description = (form.description.data or "").strip() or None
        db.session.commit()
        flash("Module updated.", "success")
        return redirect(url_for("admin.module_detail", competition_id=t.id, module_id=m.id))
    return render_template("admin/module_form.html", form=form, t=t, m=m, mode="edit")


@admin_bp.route("/competition/<int:competition_id>/module/<int:module_id>/delete", methods=["POST"])
@admin_required
def delete_module(competition_id, module_id):
    t = _own_competition(competition_id)
    m = Module.query.get_or_404(module_id)
    if m.competition_id != t.id:
        abort(404)
    db.session.delete(m)
    db.session.commit()
    flash(f"Module '{m.name}' deleted.", "info")
    return redirect(url_for("admin.competition_detail", competition_id=t.id))


# ===== Topics =====

@admin_bp.route("/competition/<int:competition_id>/module/<int:module_id>/topic/add", methods=["GET", "POST"])
@admin_required
def add_topic(competition_id, module_id):
    t = _own_competition(competition_id)
    m = Module.query.get_or_404(module_id)
    if m.competition_id != t.id:
        abort(404)
    form = TopicForm()
    bulk_form = BulkTopicsForm()
    if request.method == "POST":
        if "bulk_submit" in request.form and bulk_form.validate_on_submit():
            lines = [ln.strip() for ln in (bulk_form.topics_block.data or "").splitlines() if ln.strip()]
            base = len(m.topics)
            for i, line in enumerate(lines):
                db.session.add(Topic(module_id=m.id, title=line, display_order=base + i + 1))
            db.session.commit()
            flash(f"{len(lines)} topic(s) added.", "success")
            return redirect(url_for("admin.module_detail", competition_id=t.id, module_id=m.id))
        if "single_submit" in request.form and form.validate_on_submit():
            topic = Topic(
                module_id=m.id,
                title=form.title.data.strip(),
                display_order=len(m.topics) + 1,
            )
            db.session.add(topic)
            db.session.commit()
            flash("Topic added.", "success")
            return redirect(url_for("admin.module_detail", competition_id=t.id, module_id=m.id))
    return render_template(
        "admin/topic_form.html",
        form=form, bulk_form=bulk_form, t=t, m=m,
    )


@admin_bp.route("/competition/<int:competition_id>/module/<int:module_id>/topic/<int:topic_id>/delete", methods=["POST"])
@admin_required
def delete_topic(competition_id, module_id, topic_id):
    t = _own_competition(competition_id)
    m = Module.query.get_or_404(module_id)
    topic = Topic.query.get_or_404(topic_id)
    if m.competition_id != t.id or topic.module_id != m.id:
        abort(404)
    db.session.delete(topic)
    db.session.commit()
    flash("Topic removed.", "info")
    return redirect(url_for("admin.module_detail", competition_id=t.id, module_id=m.id))


# ===== Custom form fields =====

@admin_bp.route("/competition/<int:competition_id>/field/add", methods=["GET", "POST"])
@admin_required
def add_field(competition_id):
    t = _own_competition(competition_id)
    form = FormFieldForm()
    if form.validate_on_submit():
        field = FormField(
            competition_id=t.id,
            label=form.label.data.strip(),
            help_text=(form.help_text.data or "").strip() or None,
            field_type=form.field_type.data,
            required=form.required.data,
            display_order=len(t.form_fields) + 1,
        )
        if field.takes_options:
            opts = [ln.strip() for ln in (form.options_block.data or "").splitlines() if ln.strip()]
            field.options = opts
        db.session.add(field)
        db.session.commit()
        flash(f"Field '{field.label}' added to the participant form.", "success")
        return redirect(url_for("admin.competition_detail", competition_id=t.id))
    return render_template("admin/field_form.html", form=form, t=t, mode="add")


@admin_bp.route("/competition/<int:competition_id>/field/<int:field_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_field(competition_id, field_id):
    t = _own_competition(competition_id)
    field = FormField.query.get_or_404(field_id)
    if field.competition_id != t.id:
        abort(404)
    form = FormFieldForm(obj=field)
    if request.method == "GET":
        if field.takes_options:
            form.options_block.data = "\n".join(field.options)
    if form.validate_on_submit():
        field.label = form.label.data.strip()
        field.help_text = (form.help_text.data or "").strip() or None
        field.field_type = form.field_type.data
        field.required = form.required.data
        if field.takes_options:
            opts = [ln.strip() for ln in (form.options_block.data or "").splitlines() if ln.strip()]
            field.options = opts
        else:
            field.options = []
        db.session.commit()
        flash("Field updated.", "success")
        return redirect(url_for("admin.competition_detail", competition_id=t.id))
    return render_template("admin/field_form.html", form=form, t=t, field=field, mode="edit")


@admin_bp.route("/competition/<int:competition_id>/field/<int:field_id>/delete", methods=["POST"])
@admin_required
def delete_field(competition_id, field_id):
    t = _own_competition(competition_id)
    field = FormField.query.get_or_404(field_id)
    if field.competition_id != t.id:
        abort(404)
    db.session.delete(field)
    db.session.commit()
    flash(f"Field '{field.label}' removed.", "info")
    return redirect(url_for("admin.competition_detail", competition_id=t.id))


# ===== Judges (per module) =====

@admin_bp.route("/competition/<int:competition_id>/module/<int:module_id>/judge/add", methods=["GET", "POST"])
@admin_required
def add_judge(competition_id, module_id):
    t = _own_competition(competition_id)
    m = Module.query.get_or_404(module_id)
    if m.competition_id != t.id:
        abort(404)

    new_form = AddJudgeForm()
    existing_form = AssignExistingJudgeForm()

    # Existing judges that this admin has previously created and that aren't already on this module
    assigned_ids = {j.id for j in m.judges}
    pool = (
        User.query.filter_by(role="judge")
        .filter(~User.id.in_(assigned_ids) if assigned_ids else True)
        .order_by(User.full_name.asc())
        .all()
    )
    existing_form.judge_id.choices = [
        (u.id, f"{u.full_name or u.username}  ({u.username})") for u in pool
    ]

    if request.method == "POST":
        # Form 1: create a brand new judge user and attach to the module
        if "new_judge_submit" in request.form and new_form.validate_on_submit():
            username = new_form.username.data.strip()
            email = f"{username}@judges.local"   # synthetic email for admin-created accounts
            if User.query.filter_by(email=email).first():
                # username collision on synthetic email - extremely unlikely but guard
                from uuid import uuid4
                email = f"{username}-{uuid4().hex[:6]}@judges.local"

            judge = User(
                username=username,
                email=email,
                full_name=new_form.full_name.data.strip(),
                role="judge",
            )
            judge.set_password(new_form.password.data)
            db.session.add(judge)
            db.session.flush()
            m.judges.append(judge)
            db.session.commit()
            flash(
                f"Judge '{judge.full_name}' created and added to {m.name}. "
                f"Hand them their credentials.",
                "success",
            )
            return redirect(url_for("admin.module_detail", competition_id=t.id, module_id=m.id))

        # Form 2: attach an existing judge to this module
        if "assign_submit" in request.form and existing_form.validate_on_submit():
            judge = User.query.get(existing_form.judge_id.data)
            if judge and judge.is_judge and judge.id not in assigned_ids:
                m.judges.append(judge)
                db.session.commit()
                flash(f"{judge.full_name or judge.username} added to {m.name}.", "success")
            return redirect(url_for("admin.module_detail", competition_id=t.id, module_id=m.id))

    return render_template(
        "admin/judge_form.html",
        new_form=new_form, existing_form=existing_form,
        t=t, m=m, pool=pool,
    )


@admin_bp.route("/competition/<int:competition_id>/module/<int:module_id>/judge/<int:judge_id>/remove", methods=["POST"])
@admin_required
def remove_judge(competition_id, module_id, judge_id):
    t = _own_competition(competition_id)
    m = Module.query.get_or_404(module_id)
    if m.competition_id != t.id:
        abort(404)
    judge = User.query.get_or_404(judge_id)
    if judge in m.judges:
        m.judges.remove(judge)
        db.session.commit()
        flash(f"{judge.full_name or judge.username} removed from {m.name}.", "info")
    return redirect(url_for("admin.module_detail", competition_id=t.id, module_id=m.id))


# ===== Setup (order modules and participants before starting) =====

@admin_bp.route("/competition/<int:competition_id>/setup")
@admin_required
def setup(competition_id):
    t = _own_competition(competition_id)
    if t.status not in ("registration_closed", "in_progress"):
        flash("Setup is available once registration is closed.", "info")
        return redirect(url_for("admin.competition_detail", competition_id=t.id))

    # For each module, build the ordered list of applications that selected it
    from ..models import ApplicationModule, Application
    module_rows = []
    for m in t.modules:
        apps = (
            Application.query
            .join(ApplicationModule, ApplicationModule.application_id == Application.id)
            .filter(ApplicationModule.module_id == m.id)
            .order_by(ApplicationModule.turn_position.asc().nullslast(),
                      Application.submitted_at.asc())
            .all()
        )
        # If turn_positions are missing, assign now (in submission order)
        am_rows = (
            ApplicationModule.query
            .filter_by(module_id=m.id)
            .order_by(ApplicationModule.turn_position.asc().nullslast())
            .all()
        )
        for i, row in enumerate(am_rows, start=1):
            if row.turn_position is None:
                row.turn_position = i
        db.session.commit()
        # rebuild apps in current order
        apps = (
            Application.query
            .join(ApplicationModule, ApplicationModule.application_id == Application.id)
            .filter(ApplicationModule.module_id == m.id)
            .order_by(ApplicationModule.turn_position.asc())
            .all()
        )
        module_rows.append({"module": m, "apps": apps})

    return render_template("admin/setup.html", t=t, module_rows=module_rows)


@admin_bp.route("/competition/<int:competition_id>/setup/modules/reorder", methods=["POST"])
@admin_required
def reorder_modules(competition_id):
    """AJAX: receive a JSON list of module IDs in new precedence order."""
    from flask import jsonify
    t = _own_competition(competition_id)
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])

    if not isinstance(ids, list) or len(ids) != len(t.modules):
        return jsonify(ok=False, error="bad payload"), 400

    valid = {m.id for m in t.modules}
    if set(int(i) for i in ids) != valid:
        return jsonify(ok=False, error="ids mismatch"), 400

    for pos, mid in enumerate(ids, start=1):
        m = Module.query.get(int(mid))
        if m and m.competition_id == t.id:
            m.precedence = pos
    db.session.commit()
    return jsonify(ok=True)


@admin_bp.route("/competition/<int:competition_id>/setup/module/<int:module_id>/participants/reorder", methods=["POST"])
@admin_required
def reorder_participants(competition_id, module_id):
    """AJAX: receive a JSON list of application IDs in new turn order for this module."""
    from flask import jsonify
    from ..models import ApplicationModule
    t = _own_competition(competition_id)
    m = Module.query.get_or_404(module_id)
    if m.competition_id != t.id:
        abort(404)

    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if not isinstance(ids, list):
        return jsonify(ok=False, error="bad payload"), 400

    for pos, app_id in enumerate(ids, start=1):
        am = ApplicationModule.query.filter_by(
            application_id=int(app_id), module_id=m.id
        ).first()
        if am:
            am.turn_position = pos
    db.session.commit()
    return jsonify(ok=True)


@admin_bp.route("/competition/<int:competition_id>/setup/confirm", methods=["POST"])
@admin_required
def confirm_and_start(competition_id):
    t = _own_competition(competition_id)
    if t.status != "registration_closed":
        flash("This competition cannot be started right now.", "error")
        return redirect(url_for("admin.competition_detail", competition_id=t.id))
    t.status = "in_progress"
    db.session.commit()
    flash(f"'{t.name}' is now underway.", "success")
    return redirect(url_for("admin.competition_detail", competition_id=t.id))


# ===== Module Execution (run-time) =====

from ..models import Application, ApplicationModule, Score
from datetime import datetime


@admin_bp.route("/competition/<int:competition_id>/module/<int:module_id>/start", methods=["POST"])
@admin_required
def start_module(competition_id, module_id):
    t = _own_competition(competition_id)
    if t.status != "in_progress":
        flash("Start the competition first.", "error")
        return redirect(url_for("admin.competition_detail", competition_id=t.id))

    m = Module.query.get_or_404(module_id)
    if m.competition_id != t.id:
        abort(404)

    # Only one module can be 'current' at a time
    for other in t.modules:
        if other.status == "current" and other.id != m.id:
            flash(f"'{other.name}' is already running. Conclude it first.", "error")
            return redirect(url_for("admin.run_module", competition_id=t.id, module_id=other.id))

    if m.status == "completed":
        flash("That module has already concluded.", "error")
        return redirect(url_for("admin.competition_detail", competition_id=t.id))

    m.status = "current"
    db.session.commit()
    flash(f"'{m.name}' is now underway.", "success")
    return redirect(url_for("admin.run_module", competition_id=t.id, module_id=m.id))


@admin_bp.route("/competition/<int:competition_id>/module/<int:module_id>/run")
@admin_required
def run_module(competition_id, module_id):
    t = _own_competition(competition_id)
    m = Module.query.get_or_404(module_id)
    if m.competition_id != t.id:
        abort(404)

    rows = (
        ApplicationModule.query
        .filter_by(module_id=m.id)
        .order_by(ApplicationModule.turn_position.asc().nullslast())
        .all()
    )

    # Attach the application object to each row for the template
    enriched = []
    for am in rows:
        app = Application.query.get(am.application_id)
        enriched.append({"am": am, "app": app})

    return render_template("admin/run_module.html", t=t, m=m, rows=enriched)


@admin_bp.route("/competition/<int:competition_id>/module/<int:module_id>/conclude", methods=["POST"])
@admin_required
def conclude_module(competition_id, module_id):
    t = _own_competition(competition_id)
    m = Module.query.get_or_404(module_id)
    if m.competition_id != t.id:
        abort(404)
    m.status = "completed"
    db.session.commit()
    flash(f"'{m.name}' has concluded.", "success")
    return redirect(url_for("admin.competition_detail", competition_id=t.id))


@admin_bp.route("/competition/<int:competition_id>/module/<int:module_id>/participant/<int:application_id>/<action>", methods=["POST"])
@admin_required
def participant_action(competition_id, module_id, application_id, action):
    t = _own_competition(competition_id)
    m = Module.query.get_or_404(module_id)
    if m.competition_id != t.id:
        abort(404)
    am = ApplicationModule.query.filter_by(
        application_id=application_id, module_id=m.id
    ).first_or_404()

    if action == "call":
        am.status = "called"
        am.called_at = datetime.utcnow()
        am.topic_id = None
        am.topic_chosen_at = None
        flash("Participant called.", "info")

    elif action == "skip":
        # Move to end of queue
        max_pos = max((x.turn_position or 0) for x in ApplicationModule.query.filter_by(module_id=m.id).all())
        am.turn_position = max_pos + 1
        am.status = "queued"
        am.called_at = None
        am.topic_id = None
        am.topic_chosen_at = None
        flash("Participant moved to the end of the queue.", "info")

    elif action == "disqualify":
        am.status = "disqualified"
        flash("Participant disqualified.", "info")

    elif action == "restore":
        am.status = "queued"
        flash("Participant restored to the queue.", "info")

    elif action == "complete":
        am.status = "completed"
        flash("Participant marked as completed.", "success")

    else:
        flash("Unknown action.", "error")

    db.session.commit()
    return redirect(url_for("admin.run_module", competition_id=t.id, module_id=m.id))


# ===== Status polling (for admin to see live state changes) =====

@admin_bp.route("/competition/<int:competition_id>/module/<int:module_id>/state.json")
@admin_required
def module_state_json(competition_id, module_id):
    from flask import jsonify
    t = _own_competition(competition_id)
    m = Module.query.get_or_404(module_id)
    if m.competition_id != t.id:
        return jsonify(ok=False), 404

    rows = (
        ApplicationModule.query
        .filter_by(module_id=m.id)
        .order_by(ApplicationModule.turn_position.asc().nullslast())
        .all()
    )
    out = []
    for am in rows:
        app = Application.query.get(am.application_id)
        out.append({
            "application_id": app.id,
            "name": app.full_name,
            "institution": app.institution,
            "photo_url": app.photo_url,
            "position": am.turn_position,
            "status": am.status,
            "called_at": am.called_at.isoformat() if am.called_at else None,
            "topic": am.topic.title if am.topic else None,
            "seconds_left": am.call_seconds_left,
        })
    return jsonify(ok=True, rows=out, module_status=m.status)


# ===== Module results (aggregated, admin-only) =====

@admin_bp.route("/competition/<int:competition_id>/module/<int:module_id>/results")
@admin_required
def module_results(competition_id, module_id):
    t = _own_competition(competition_id)
    m = Module.query.get_or_404(module_id)
    if m.competition_id != t.id:
        abort(404)

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
            ratings = [s.rating for s in scores]
            avg = sum(ratings) / len(ratings)
            total = sum(ratings)
        else:
            ratings = []
            avg = None
            total = None
        rows.append({
            "am": am,
            "app": app,
            "scores": scores,
            "avg": avg,
            "total": total,
            "judge_count": len(scores),
        })

    # Sort by total descending; performances with no scores at the bottom
    rows.sort(key=lambda r: (r["total"] if r["total"] is not None else -1), reverse=True)
    # Assign positions (skip if no rating)
    pos = 0
    for r in rows:
        if r["total"] is not None:
            pos += 1
            r["position"] = pos
        else:
            r["position"] = None

    return render_template("admin/module_results.html", t=t, m=m, rows=rows)


# ===== Announcements =====

from .forms import AnnouncementForm
from ..models import Announcement


@admin_bp.route("/competition/<int:competition_id>/announcement/new", methods=["GET", "POST"])
@admin_required
def create_announcement(competition_id):
    t = _own_competition(competition_id)
    form = AnnouncementForm()
    # Visible to: "All modules" (0) or any specific module
    form.module_id.choices = [(0, "All participants and judges")] + [
        (m.id, m.name) for m in t.modules
    ]
    if form.validate_on_submit():
        ann = Announcement(
            competition_id=t.id,
            module_id=form.module_id.data if form.module_id.data else None,
            title=form.title.data.strip(),
            body=(form.body.data or "").strip() or None,
        )
        db.session.add(ann)
        db.session.commit()
        flash("Announcement posted.", "success")
        return redirect(url_for("admin.competition_detail", competition_id=t.id))
    return render_template("admin/announcement_form.html", form=form, t=t)


@admin_bp.route("/competition/<int:competition_id>/announcement/<int:announcement_id>/delete", methods=["POST"])
@admin_required
def delete_announcement(competition_id, announcement_id):
    t = _own_competition(competition_id)
    ann = Announcement.query.get_or_404(announcement_id)
    if ann.competition_id != t.id:
        abort(404)
    db.session.delete(ann)
    db.session.commit()
    flash("Announcement removed.", "info")
    return redirect(url_for("admin.competition_detail", competition_id=t.id))


# ===== Overall competition results =====

@admin_bp.route("/competition/<int:competition_id>/overall")
@admin_required
def overall_results(competition_id):
    t = _own_competition(competition_id)
    return render_template("admin/overall_results.html", t=t, **_build_overall(t))


def _build_overall(t: Competition) -> dict:
    """Build the overall standings: sum of module totals across all modules."""
    from collections import defaultdict
    totals = defaultdict(float)
    counts = defaultdict(int)
    module_breakdown = defaultdict(dict)  # app_id -> { module_id: module_total }

    for m in t.modules:
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
        })
    rows.sort(key=lambda r: r["total"], reverse=True)
    pos = 0
    for r in rows:
        pos += 1
        r["position"] = pos
    return {"rows": rows, "modules": sorted(t.modules, key=lambda m: m.precedence or 0)}
