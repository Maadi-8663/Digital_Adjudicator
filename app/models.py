"""Database models for Digital Adjudicator (stage-speaking competition format)."""

import json
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db


# ===== Users =====

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, judge, participant

    full_name = db.Column(db.String(120))
    institution = db.Column(db.String(120))
    team_name = db.Column(db.String(120))     # legacy, unused
    experience = db.Column(db.String(120))    # for judges
    department = db.Column(db.String(120))    # for admins

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool: return self.role == "admin"
    @property
    def is_judge(self) -> bool: return self.role == "judge"
    @property
    def is_participant(self) -> bool: return self.role == "participant"

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"


# ===== Competition =====

class Competition(db.Model):
    __tablename__ = "competitions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    venue = db.Column(db.String(200))
    cover_image = db.Column(db.String(300))

    # setup, open_for_registration, registration_closed, in_progress, completed
    status = db.Column(db.String(30), default="setup")

    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    admin = db.relationship("User", backref="competitions")

    modules = db.relationship(
        "Module", backref="competition", cascade="all, delete-orphan",
        order_by="Module.precedence",
    )
    form_fields = db.relationship(
        "FormField", backref="competition", cascade="all, delete-orphan",
        order_by="FormField.display_order",
    )
    applications = db.relationship(
        "Application", backref="competition", cascade="all, delete-orphan",
    )
    announcements = db.relationship(
        "Announcement", backref="competition", cascade="all, delete-orphan",
        order_by="Announcement.created_at.desc()",
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    STATUS_LABELS = {
        "setup":                 "In Setup",
        "open_for_registration": "Open for Registration",
        "registration_closed":   "Registration Closed",
        "in_progress":           "In Progress",
        "completed":             "Concluded",
    }

    @property
    def status_label(self) -> str:
        return self.STATUS_LABELS.get(self.status, self.status.title())

    @property
    def is_public(self) -> bool:
        return self.status in ("open_for_registration", "registration_closed", "in_progress", "completed")

    @property
    def accepts_applications(self) -> bool:
        return self.status == "open_for_registration"

    @property
    def all_modules_complete(self) -> bool:
        """A competition is ready to open for registration when every module
        has a name, at least one topic, and at least one judge."""
        return bool(self.modules) and all(m.is_complete for m in self.modules)

    @property
    def incomplete_modules(self) -> list:
        return [m for m in self.modules if not m.is_complete]

    def __repr__(self) -> str:
        return f"<Competition {self.name}>"


# ===== Module-Judge association =====

module_judges = db.Table(
    "module_judges",
    db.Column("module_id", db.Integer, db.ForeignKey("modules.id", ondelete="CASCADE"), primary_key=True),
    db.Column("judge_id",  db.Integer, db.ForeignKey("users.id",   ondelete="CASCADE"), primary_key=True),
)


# ===== Module =====

class Module(db.Model):
    __tablename__ = "modules"

    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey("competitions.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    precedence = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    topics = db.relationship(
        "Topic", backref="module", cascade="all, delete-orphan",
        order_by="Topic.display_order",
    )
    judges = db.relationship(
        "User", secondary=module_judges, backref="judged_modules",
    )
    announcements = db.relationship("Announcement", backref="module")

    @property
    def status_label(self) -> str:
        return {"pending": "Pending", "current": "Currently Running", "completed": "Concluded"}.get(
            self.status, self.status.title()
        )

    @property
    def is_complete(self) -> bool:
        """A module is ready when it has a name, at least one topic, and at least one judge."""
        return bool(self.name and self.topics and self.judges)

    @property
    def missing_pieces(self) -> list[str]:
        missing = []
        if not self.topics: missing.append("at least one topic")
        if not self.judges: missing.append("at least one judge")
        return missing

    def __repr__(self) -> str:
        return f"<Module {self.name}>"


class Topic(db.Model):
    __tablename__ = "topics"

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey("modules.id"), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Topic {self.title[:30]}>"


# ===== Custom form fields =====

class FormField(db.Model):
    __tablename__ = "form_fields"

    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey("competitions.id"), nullable=False)

    label = db.Column(db.String(160), nullable=False)
    help_text = db.Column(db.String(300))
    field_type = db.Column(db.String(30), nullable=False)
    required = db.Column(db.Boolean, default=False)
    options_json = db.Column(db.Text)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    FIELD_TYPE_LABELS = {
        "text":          "Short text",
        "textarea":      "Long text",
        "number":        "Number",
        "single_select": "Single choice",
        "multi_select":  "Multiple choice",
        "image":         "Image upload",
    }

    @property
    def type_label(self) -> str:
        return self.FIELD_TYPE_LABELS.get(self.field_type, self.field_type)

    @property
    def options(self) -> list[str]:
        if not self.options_json:
            return []
        try:
            return json.loads(self.options_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @options.setter
    def options(self, value: list[str]) -> None:
        self.options_json = json.dumps(value) if value else None

    @property
    def takes_options(self) -> bool:
        return self.field_type in ("single_select", "multi_select")

    def __repr__(self) -> str:
        return f"<FormField {self.label}>"


# ===== Participant application =====

class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey("competitions.id"), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    full_name = db.Column(db.String(160))
    institution = db.Column(db.String(160))
    photo_url = db.Column(db.String(300))

    status = db.Column(db.String(20), default="applied")
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    participant = db.relationship("User", backref="applications")

    selected_modules = db.relationship(
        "Module", secondary="application_modules", backref="applications",
    )
    field_responses = db.relationship(
        "FieldResponse", backref="application", cascade="all, delete-orphan",
    )

    @property
    def status_label(self) -> str:
        return {
            "applied":      "Applied",
            "accepted":     "Accepted",
            "disqualified": "Disqualified",
            "withdrawn":    "Withdrawn",
        }.get(self.status, self.status.title())


class ApplicationModule(db.Model):
    __tablename__ = "application_modules"

    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey("modules.id"), primary_key=True)
    turn_position = db.Column(db.Integer)
    # queued, called, on_stage, completed, disqualified, skipped
    status = db.Column(db.String(20), default="queued")

    # Call / topic / performance timeline
    called_at = db.Column(db.DateTime)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"))
    topic_chosen_at = db.Column(db.DateTime)
    speech_started_at = db.Column(db.DateTime)
    speech_paused_at = db.Column(db.DateTime)         # null when running
    speech_total_paused_seconds = db.Column(db.Integer, default=0)
    speech_ended_at = db.Column(db.DateTime)

    topic = db.relationship("Topic")

    STATUS_LABELS = {
        "queued":       "In Queue",
        "called":       "Called to Stage",
        "on_stage":     "On Stage",
        "completed":    "Completed",
        "disqualified": "Disqualified",
        "skipped":      "Skipped (moved to end)",
    }

    @property
    def status_label(self) -> str:
        return self.STATUS_LABELS.get(self.status, self.status.title())

    @property
    def call_seconds_left(self) -> int | None:
        """Seconds remaining out of the 2-minute call window. Negative means expired."""
        if self.status != "called" or self.called_at is None:
            return None
        elapsed = (datetime.utcnow() - self.called_at).total_seconds()
        return int(120 - elapsed)

    @property
    def timer_state(self) -> str:
        """not_started, running, paused, or stopped."""
        if self.speech_ended_at is not None:
            return "stopped"
        if self.speech_started_at is None:
            return "not_started"
        if self.speech_paused_at is not None:
            return "paused"
        return "running"

    @property
    def speech_elapsed_seconds(self) -> int:
        """Live elapsed speech time (subtracting paused intervals)."""
        if self.speech_started_at is None:
            return 0
        end = self.speech_ended_at or self.speech_paused_at or datetime.utcnow()
        raw = (end - self.speech_started_at).total_seconds()
        return max(0, int(raw - (self.speech_total_paused_seconds or 0)))

    @property
    def scoring_seconds_left(self) -> int | None:
        """15-minute rating window starting from speech_ended_at."""
        if self.speech_ended_at is None:
            return None
        elapsed = (datetime.utcnow() - self.speech_ended_at).total_seconds()
        return int(15 * 60 - elapsed)


class Score(db.Model):
    __tablename__ = "scores"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False)
    module_id      = db.Column(db.Integer, db.ForeignKey("modules.id"),      nullable=False)
    judge_id       = db.Column(db.Integer, db.ForeignKey("users.id"),        nullable=False)

    rating = db.Column(db.Float)        # 0-10
    feedback = db.Column(db.Text)
    notes = db.Column(db.Text)          # judge's private notes during speech
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    judge = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint("application_id", "module_id", "judge_id", name="uq_score_per_judge"),
    )


class FieldResponse(db.Model):
    __tablename__ = "field_responses"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey("form_fields.id"), nullable=False)
    value = db.Column(db.Text)

    field = db.relationship("FormField")


# ===== Announcement =====

class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey("competitions.id"), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey("modules.id"), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
