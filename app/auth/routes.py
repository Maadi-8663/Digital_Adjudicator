"""Authentication routes: login, register, logout, role landing."""

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from . import auth_bp
from .forms import LoginForm, RegisterForm
from .. import db
from ..models import User


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.role_dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user is None or not user.check_password(form.password.data):
            flash("Those credentials did not match. Try again.", "error")
            return redirect(url_for("auth.login"))

        login_user(user, remember=True)
        flash(f"Welcome back, {user.full_name or user.username}.", "success")
        next_page = request.args.get("next")
        return redirect(next_page or url_for("auth.role_dashboard"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("auth.role_dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            full_name=form.full_name.data.strip(),
            institution=form.institution.data.strip(),
            team_name=(form.team_name.data or "").strip() or None,
            role=form.role.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        login_user(user, remember=True)
        flash("Your account is ready. Welcome to the hall.", "success")
        return redirect(url_for("auth.role_dashboard"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have stepped out of the hall. Until next time.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/dashboard")
@login_required
def role_dashboard():
    """Route to the role-specific dashboard."""
    from flask import current_app
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    if current_user.is_judge:
        return redirect(url_for("judge.dashboard"))
    return redirect(url_for("participant.dashboard"))
