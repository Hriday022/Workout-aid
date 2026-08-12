from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, PasswordField, IntegerField, FloatField, SelectField, DateField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange


class SignupForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        "Confirm password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")]
    )


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])


class UploadForm(FlaskForm):
    pdf_file = FileField(
        "Workout PDF",
        validators=[FileRequired(), FileAllowed(["pdf"], "PDF files only.")],
    )


class WorkoutEntryForm(FlaskForm):
    exercise_name = StringField("Exercise", validators=[DataRequired(), Length(max=150)])
    sets = IntegerField("Sets", validators=[Optional(), NumberRange(min=0, max=999)])
    reps = IntegerField("Reps", validators=[Optional(), NumberRange(min=0, max=9999)])
    weight = FloatField("Weight", validators=[Optional(), NumberRange(min=0)])
    weight_unit = SelectField(
        "Unit", choices=[("kg", "kg"), ("lb", "lb")], validators=[Optional()]
    )
    entry_date = DateField("Date", validators=[Optional()])
    notes = StringField("Notes", validators=[Optional(), Length(max=300)])


class CSRFOnlyForm(FlaskForm):
    """Used purely to render a CSRF token on delete/action buttons that have
    no other fields."""
    pass


class RoutineForm(FlaskForm):
    name = StringField("Split name", validators=[DataRequired(), Length(max=120)])


class RoutineDayForm(FlaskForm):
    name = StringField("Day name", validators=[DataRequired(), Length(max=120)])


class RoutineExerciseForm(FlaskForm):
    exercise_name = StringField("Exercise", validators=[DataRequired(), Length(max=150)])
    sets = IntegerField("Sets", validators=[Optional(), NumberRange(min=0, max=99)])
    reps = IntegerField("Reps", validators=[Optional(), NumberRange(min=0, max=999)])
    weight = FloatField("Weight", validators=[Optional(), NumberRange(min=0)])
    weight_unit = SelectField(
        "Unit", choices=[("kg", "kg"), ("lb", "lb")], validators=[Optional()]
    )
    work_seconds = IntegerField("Hold/work (sec)", validators=[Optional(), NumberRange(min=0, max=3600)])
    rest_seconds = IntegerField("Timer (sec)", validators=[Optional(), NumberRange(min=5, max=3600)])
    notes = StringField("Notes", validators=[Optional(), Length(max=300)])
