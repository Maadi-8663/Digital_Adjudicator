"""Forms for the authentication blueprint."""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional

from ..models import User


class LoginForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[DataRequired(message="Your username, please."),
                    Length(min=3, max=64)],
        render_kw={"placeholder": "Enter your username", "autocomplete": "username"},
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="A password is required."),
                    Length(min=6, max=128)],
        render_kw={"placeholder": "Enter your password", "autocomplete": "current-password"},
    )
    submit = SubmitField("Sign In")


class RegisterForm(FlaskForm):
    full_name = StringField(
        "Full Name",
        validators=[DataRequired(), Length(min=2, max=120)],
        render_kw={"placeholder": "e.g. Syeda Gul e Zahra Batool Bukhari"},
    )
    email = StringField(
        "Email",
        validators=[DataRequired(), Email(message="That does not look like a valid email."), Length(max=120)],
        render_kw={"placeholder": "name@uet.edu.pk", "autocomplete": "email"},
    )
    institution = StringField(
        "Institution",
        validators=[DataRequired(), Length(min=2, max=120)],
        render_kw={"placeholder": "e.g. UET Lahore - New Campus"},
    )
    role = SelectField(
        "Role",
        choices=[("participant", "Participant")],
        default="participant",
        validators=[DataRequired()],
    )
    team_name = StringField(
        "Team Name",
        validators=[Optional(), Length(max=120)],
        render_kw={"placeholder": "Required for participants only"},
    )
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=3, max=64)],
        render_kw={"placeholder": "Choose a unique username", "autocomplete": "username"},
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=6, max=128, message="At least six characters.")],
        render_kw={"placeholder": "At least six characters", "autocomplete": "new-password"},
    )
    confirm = PasswordField(
        "Confirm Password",
        validators=[DataRequired(),
                    EqualTo("password", message="The passwords do not match.")],
        render_kw={"placeholder": "Type it again", "autocomplete": "new-password"},
    )
    submit = SubmitField("Create Account")

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError("That username is already taken.")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError("An account with that email already exists.")

    def validate_team_name(self, field):
        if self.role.data == "participant" and not (field.data and field.data.strip()):
            raise ValidationError("Participants need a team name.")
