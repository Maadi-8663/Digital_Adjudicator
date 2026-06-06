"""Forms for the admin blueprint."""

from flask_wtf import FlaskForm
from wtforms import (
    StringField, IntegerField, DateField, SelectField, SubmitField,
    TextAreaField, BooleanField, SelectMultipleField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError


# ===== Competition =====

class CreateCompetitionForm(FlaskForm):
    name = StringField(
        "Competition Name",
        validators=[DataRequired(), Length(min=3, max=200)],
        render_kw={"placeholder": "e.g. UET Open 2026 - Literary Festival"},
    )
    description = TextAreaField(
        "About the Competition",
        validators=[Optional(), Length(max=4000)],
        render_kw={"placeholder": "What the competition is about, the audience, the prizes...", "rows": 4},
    )
    start_date = DateField("Start Date", validators=[DataRequired()], format="%Y-%m-%d")
    end_date   = DateField("End Date",   validators=[DataRequired()], format="%Y-%m-%d")
    venue = StringField(
        "Venue (optional)",
        validators=[Optional(), Length(max=200)],
        render_kw={"placeholder": "e.g. Old Building Auditorium, UET New Campus"},
    )
    submit = SubmitField("Create Competition")

    def validate_end_date(self, field):
        if self.start_date.data and field.data and field.data < self.start_date.data:
            raise ValidationError("End date cannot fall before the start date.")


# ===== Module =====

class ModuleForm(FlaskForm):
    name = StringField(
        "Module Name",
        validators=[DataRequired(), Length(min=2, max=120)],
        render_kw={"placeholder": "e.g. English Debate, Urdu Humorous, Bait Bazi"},
    )
    description = TextAreaField(
        "Description (optional)",
        validators=[Optional(), Length(max=2000)],
        render_kw={"placeholder": "Format, rules, what participants should expect...", "rows": 3},
    )
    submit = SubmitField("Save Module")


# ===== Topic =====

class TopicForm(FlaskForm):
    title = TextAreaField(
        "Topic / Motion",
        validators=[DataRequired(), Length(min=3, max=500)],
        render_kw={"placeholder": "THBT...   /   Translate one of these famous quotes...", "rows": 2},
    )
    submit = SubmitField("Save Topic")


class BulkTopicsForm(FlaskForm):
    """Paste many topics at once, one per line."""
    topics_block = TextAreaField(
        "Topics (one per line)",
        validators=[DataRequired(), Length(min=3, max=10000)],
        render_kw={"placeholder": "Topic 1\nTopic 2\nTopic 3\n...", "rows": 8},
    )
    submit = SubmitField("Add All")


# ===== Custom form field =====

class FormFieldForm(FlaskForm):
    label = StringField(
        "Field Label",
        validators=[DataRequired(), Length(min=2, max=160)],
        render_kw={"placeholder": "e.g. Phone Number, T-shirt Size, Years of Experience"},
    )
    help_text = StringField(
        "Helper Text (optional)",
        validators=[Optional(), Length(max=300)],
        render_kw={"placeholder": "Short hint shown under the field"},
    )
    field_type = SelectField(
        "Field Type",
        choices=[
            ("text",          "Short text"),
            ("textarea",      "Long text"),
            ("number",        "Number"),
            ("single_select", "Single choice (radio)"),
            ("multi_select",  "Multiple choice (checkboxes)"),
            ("image",         "Image upload"),
        ],
        validators=[DataRequired()],
    )
    required = BooleanField("Required field")
    options_block = TextAreaField(
        "Options (one per line, for choice fields only)",
        validators=[Optional(), Length(max=2000)],
        render_kw={"placeholder": "Option 1\nOption 2\nOption 3", "rows": 4},
    )
    submit = SubmitField("Save Field")

    def validate_options_block(self, field):
        if self.field_type.data in ("single_select", "multi_select"):
            opts = [ln.strip() for ln in (field.data or "").splitlines() if ln.strip()]
            if len(opts) < 2:
                raise ValidationError("Choice fields need at least two options.")


# ===== Judge =====

class AddJudgeForm(FlaskForm):
    full_name = StringField(
        "Judge's Full Name",
        validators=[DataRequired(), Length(min=2, max=120)],
        render_kw={"placeholder": "e.g. Sir Usman Ghani"},
    )
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=3, max=64)],
        render_kw={"placeholder": "Hand this to the judge in person"},
    )
    password = StringField(
        "Password",
        validators=[DataRequired(), Length(min=6, max=128)],
        render_kw={"placeholder": "At least six characters"},
    )
    submit = SubmitField("Create Judge")

    def validate_username(self, field):
        from ..models import User
        if User.query.filter_by(username=field.data.strip()).first():
            raise ValidationError("That username is already taken.")


class AssignExistingJudgeForm(FlaskForm):
    judge_id = SelectField(
        "Choose an existing judge",
        coerce=int,
        validators=[DataRequired()],
    )
    submit = SubmitField("Add to Module")


# ===== Announcement =====

class AnnouncementForm(FlaskForm):
    title = StringField(
        "Title",
        validators=[DataRequired(), Length(min=2, max=200)],
        render_kw={"placeholder": "e.g. Lunch break at 1:30 pm"},
    )
    body = TextAreaField(
        "Message",
        validators=[Optional(), Length(max=4000)],
        render_kw={"placeholder": "Anything participants and judges should know.", "rows": 4},
    )
    module_id = SelectField(
        "Visible to",
        coerce=int,
        validators=[Optional()],
    )
    submit = SubmitField("Post Announcement")
