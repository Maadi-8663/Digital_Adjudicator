"""Public routes - homepage, competition browse, application flow."""

import os
import uuid
from datetime import datetime

from flask import (
    abort, current_app, flash, redirect, render_template, request, url_for
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from . import public_bp
from .. import db, csrf
from ..models import (
    Application, ApplicationModule, FieldResponse, FormField,
    Module, Competition,
)


ALLOWED_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}


def _allowed_image(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTS


def _save_image(file, subfolder: str) -> str | None:
    """Save an uploaded image and return the URL-relative path under /static."""
    if not file or not file.filename:
        return None
    if not _allowed_image(file.filename):
        return None

    name_only = secure_filename(file.filename)
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    unique = uuid.uuid4().hex[:8]
    new_name = f"{stamp}_{unique}_{name_only}"

    upload_dir = os.path.join(current_app.root_path, "static", "uploads", subfolder)
    os.makedirs(upload_dir, exist_ok=True)

    path = os.path.join(upload_dir, new_name)
    file.save(path)
    return f"uploads/{subfolder}/{new_name}"


# ===== Homepage =====

@public_bp.route("/")
def home():
    # Redirect admins and judges to their own dashboards on root
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        if current_user.is_judge:
            return redirect(url_for("judge.dashboard"))

    open_now = (
        Competition.query.filter_by(status="open_for_registration")
        .order_by(Competition.start_date.asc()).all()
    )
    underway = (
        Competition.query.filter_by(status="in_progress")
        .order_by(Competition.start_date.desc()).all()
    )
    registration_closed = (
        Competition.query.filter_by(status="registration_closed")
        .order_by(Competition.start_date.desc()).all()
    )
    completed = (
        Competition.query.filter_by(status="completed")
        .order_by(Competition.end_date.desc()).limit(6).all()
    )

    my_apps = []
    if current_user.is_authenticated and current_user.is_participant:
        my_apps = (
            Application.query.filter_by(participant_id=current_user.id)
            .order_by(Application.submitted_at.desc()).all()
        )

    return render_template(
        "public/home.html",
        open_now=open_now,
        underway=underway,
        registration_closed=registration_closed,
        completed=completed,
        my_apps=my_apps,
    )


# ===== Competition detail (public) =====

@public_bp.route("/competition/<int:competition_id>")
def competition_detail(competition_id):
    t = Competition.query.get_or_404(competition_id)
    if not t.is_public:
        abort(404)

    already_applied = False
    if current_user.is_authenticated and current_user.is_participant:
        already_applied = Application.query.filter_by(
            competition_id=t.id, participant_id=current_user.id
        ).first() is not None

    return render_template(
        "public/competition_detail.html",
        t=t, already_applied=already_applied,
    )


# ===== Apply =====

@public_bp.route("/competition/<int:competition_id>/apply", methods=["GET", "POST"])
@login_required
def apply(competition_id):
    t = Competition.query.get_or_404(competition_id)

    if not t.accepts_applications:
        flash("This competition is not accepting applications right now.", "error")
        return redirect(url_for("public.competition_detail", competition_id=t.id))

    if not current_user.is_participant:
        flash("Only participants can apply to competitions.", "error")
        return redirect(url_for("public.competition_detail", competition_id=t.id))

    if Application.query.filter_by(competition_id=t.id, participant_id=current_user.id).first():
        flash("You have already applied to this competition.", "info")
        return redirect(url_for("participant.dashboard"))

    if request.method == "GET":
        return render_template("public/apply.html", t=t, errors=[], values={})

    # ===== POST: process the application =====
    errors: list[str] = []
    values: dict = {}

    full_name = (request.form.get("full_name") or "").strip()
    institution = (request.form.get("institution") or "").strip()
    selected_module_ids = request.form.getlist("modules")
    photo = request.files.get("photo")

    values["full_name"] = full_name
    values["institution"] = institution
    values["modules"] = selected_module_ids

    if not full_name:
        errors.append("Your full name is required.")
    if not institution:
        errors.append("Your institution is required.")
    if not photo or not photo.filename:
        errors.append("Please attach a profile photo.")
    elif not _allowed_image(photo.filename):
        errors.append("Profile photo must be a JPG, PNG, GIF or WEBP image.")
    if not selected_module_ids:
        errors.append("Pick at least one module to participate in.")

    # Validate custom fields
    field_values: dict[int, object] = {}
    for f in t.form_fields:
        key = f"field_{f.id}"
        if f.field_type in ("text", "textarea", "number"):
            val = (request.form.get(key) or "").strip()
            field_values[f.id] = val
            if f.required and not val:
                errors.append(f"'{f.label}' is required.")
        elif f.field_type == "single_select":
            val = request.form.get(key) or ""
            field_values[f.id] = val
            if f.required and not val:
                errors.append(f"'{f.label}' is required.")
        elif f.field_type == "multi_select":
            vals = request.form.getlist(key)
            field_values[f.id] = vals
            if f.required and not vals:
                errors.append(f"'{f.label}' is required.")
        elif f.field_type == "image":
            file = request.files.get(key)
            field_values[f.id] = file
            if f.required and (not file or not file.filename):
                errors.append(f"'{f.label}' is required.")
            elif file and file.filename and not _allowed_image(file.filename):
                errors.append(f"'{f.label}' must be a JPG, PNG, GIF or WEBP image.")

    values["custom"] = {k: v for k, v in field_values.items() if not hasattr(v, "filename")}

    # Validate that selected modules belong to this competition
    valid_module_ids = {str(m.id) for m in t.modules}
    selected_module_ids = [m for m in selected_module_ids if m in valid_module_ids]
    if not selected_module_ids:
        errors.append("Pick at least one module to participate in.")

    if errors:
        return render_template("public/apply.html", t=t, errors=errors, values=values)

    # ===== Save =====
    photo_url = _save_image(photo, "photos")

    application = Application(
        competition_id=t.id,
        participant_id=current_user.id,
        full_name=full_name,
        institution=institution,
        photo_url=photo_url,
        status="applied",
    )
    db.session.add(application)
    db.session.flush()  # get application.id

    for mid in selected_module_ids:
        db.session.add(ApplicationModule(
            application_id=application.id,
            module_id=int(mid),
        ))

    for f in t.form_fields:
        if f.field_type == "multi_select":
            vals = field_values.get(f.id) or []
            value_str = " | ".join(vals)
        elif f.field_type == "image":
            file = field_values.get(f.id)
            value_str = _save_image(file, "field_uploads") if (file and file.filename) else ""
        else:
            value_str = str(field_values.get(f.id) or "")
        if value_str:
            db.session.add(FieldResponse(
                application_id=application.id,
                field_id=f.id,
                value=value_str,
            ))

    db.session.commit()

    flash(f"Your application to '{t.name}' has been received.", "success")
    return redirect(url_for("public.apply_success", competition_id=t.id))


@public_bp.route("/competition/<int:competition_id>/apply/success")
@login_required
def apply_success(competition_id):
    t = Competition.query.get_or_404(competition_id)
    application = Application.query.filter_by(
        competition_id=t.id, participant_id=current_user.id
    ).first_or_404()
    return render_template("public/apply_success.html", t=t, application=application)
