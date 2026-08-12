from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    uploads = db.relationship(
        "WorkoutUpload", backref="user", cascade="all, delete-orphan", lazy="dynamic"
    )
    entries = db.relationship(
        "WorkoutEntry", backref="user", cascade="all, delete-orphan", lazy="dynamic"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class WorkoutUpload(db.Model):
    """Metadata about a parsed PDF. The PDF file itself is never stored on disk —
    only its extracted entries persist, which keeps this safe to run on Render's
    ephemeral filesystem."""

    __tablename__ = "workout_uploads"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=utcnow)
    parse_method = db.Column(db.String(20), default="regex")  # "regex" or "claude"
    entry_count = db.Column(db.Integer, default=0)

    entries = db.relationship(
        "WorkoutEntry", backref="upload", cascade="all, delete-orphan", lazy="dynamic"
    )


class WorkoutEntry(db.Model):
    __tablename__ = "workout_entries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    upload_id = db.Column(db.Integer, db.ForeignKey("workout_uploads.id"), nullable=True, index=True)
    routine_day_id = db.Column(
        db.Integer, db.ForeignKey("routine_days.id", ondelete="SET NULL"), nullable=True, index=True
    )

    exercise_name = db.Column(db.String(150), nullable=False)
    sets = db.Column(db.Integer, nullable=True)
    reps = db.Column(db.Integer, nullable=True)
    weight = db.Column(db.Float, nullable=True)
    weight_unit = db.Column(db.String(10), nullable=True)  # "kg" or "lb"
    notes = db.Column(db.String(300), nullable=True)
    entry_date = db.Column(db.Date, nullable=True)
    # "manual", "pdf", or "routine" — where this logged set came from.
    source = db.Column(db.String(20), default="manual")

    created_at = db.Column(db.DateTime, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "exercise_name": self.exercise_name,
            "sets": self.sets,
            "reps": self.reps,
            "weight": self.weight,
            "weight_unit": self.weight_unit,
            "notes": self.notes,
            "entry_date": self.entry_date.isoformat() if self.entry_date else None,
        }


class Routine(db.Model):
    """A workout split — e.g. 'Push Pull Legs' or a custom 5-day split.
    Holds an ordered set of RoutineDays, each with its own exercises."""

    __tablename__ = "routines"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    days = db.relationship(
        "RoutineDay",
        backref="routine",
        cascade="all, delete-orphan",
        order_by="RoutineDay.order_index",
        lazy="dynamic",
    )


class RoutineDay(db.Model):
    """A single training day within a split (e.g. 'Day 1 — Push')."""

    __tablename__ = "routine_days"

    id = db.Column(db.Integer, primary_key=True)
    routine_id = db.Column(db.Integer, db.ForeignKey("routines.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    order_index = db.Column(db.Integer, default=0)

    exercises = db.relationship(
        "RoutineExercise",
        backref="day",
        cascade="all, delete-orphan",
        order_by="RoutineExercise.order_index",
        lazy="dynamic",
    )
    logged_entries = db.relationship(
        "WorkoutEntry",
        backref="routine_day",
        lazy="dynamic",
    )


class RoutineExercise(db.Model):
    """A planned exercise inside a routine day, with a target timer.

    ``work_seconds`` is used for timed holds (planks, etc.) and doubles as
    the countdown shown in the guided player; ``rest_seconds`` is the
    fallback/rest timer shown when there's no fixed hold time.
    """

    __tablename__ = "routine_exercises"

    id = db.Column(db.Integer, primary_key=True)
    routine_day_id = db.Column(db.Integer, db.ForeignKey("routine_days.id"), nullable=False, index=True)

    exercise_name = db.Column(db.String(150), nullable=False)
    sets = db.Column(db.Integer, nullable=True)
    reps = db.Column(db.Integer, nullable=True)
    weight = db.Column(db.Float, nullable=True)
    weight_unit = db.Column(db.String(10), nullable=True)
    work_seconds = db.Column(db.Integer, nullable=True)
    rest_seconds = db.Column(db.Integer, default=60)
    notes = db.Column(db.String(300), nullable=True)
    order_index = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "exercise_name": self.exercise_name,
            "sets": self.sets,
            "reps": self.reps,
            "weight": self.weight,
            "weight_unit": self.weight_unit or "kg",
            "work_seconds": self.work_seconds,
            "rest_seconds": self.rest_seconds or 60,
            "notes": self.notes,
        }
