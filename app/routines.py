from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Routine, RoutineDay, RoutineExercise, WorkoutEntry
from app.forms import CSRFOnlyForm, RoutineForm, RoutineDayForm, RoutineExerciseForm

bp = Blueprint("routines", __name__, url_prefix="/routines")


# A ready-made 5-day split so a new user can start training immediately and
# tweak from there instead of building a plan from a blank page.
FIVE_DAY_SPLIT = [
    ("Day 1 — Push (Chest, Shoulders, Triceps)", [
        dict(exercise_name="Barbell Bench Press", sets=4, reps=8, rest_seconds=90),
        dict(exercise_name="Overhead Press", sets=3, reps=10, rest_seconds=75),
        dict(exercise_name="Incline Dumbbell Press", sets=3, reps=10, rest_seconds=75),
        dict(exercise_name="Lateral Raise", sets=3, reps=15, rest_seconds=45),
        dict(exercise_name="Triceps Rope Pushdown", sets=3, reps=12, rest_seconds=45),
        dict(exercise_name="Dips", sets=3, reps=10, rest_seconds=60),
    ]),
    ("Day 2 — Pull (Back, Biceps)", [
        dict(exercise_name="Deadlift", sets=4, reps=6, rest_seconds=120),
        dict(exercise_name="Pull-Up", sets=4, reps=8, rest_seconds=90),
        dict(exercise_name="Barbell Row", sets=3, reps=10, rest_seconds=75),
        dict(exercise_name="Lat Pulldown", sets=3, reps=12, rest_seconds=60),
        dict(exercise_name="Face Pull", sets=3, reps=15, rest_seconds=45),
        dict(exercise_name="Barbell Curl", sets=3, reps=12, rest_seconds=45),
    ]),
    ("Day 3 — Legs", [
        dict(exercise_name="Back Squat", sets=4, reps=8, rest_seconds=120),
        dict(exercise_name="Romanian Deadlift", sets=3, reps=10, rest_seconds=90),
        dict(exercise_name="Leg Press", sets=3, reps=12, rest_seconds=75),
        dict(exercise_name="Walking Lunge", sets=3, reps=12, rest_seconds=60),
        dict(exercise_name="Leg Curl", sets=3, reps=12, rest_seconds=45),
        dict(exercise_name="Standing Calf Raise", sets=4, reps=15, rest_seconds=45),
    ]),
    ("Day 4 — Upper Body", [
        dict(exercise_name="Incline Barbell Press", sets=4, reps=8, rest_seconds=90),
        dict(exercise_name="Seated Cable Row", sets=4, reps=10, rest_seconds=75),
        dict(exercise_name="Arnold Press", sets=3, reps=10, rest_seconds=60),
        dict(exercise_name="Chin-Up", sets=3, reps=10, rest_seconds=75),
        dict(exercise_name="Cable Fly", sets=3, reps=15, rest_seconds=45),
        dict(exercise_name="Hammer Curl", sets=3, reps=12, rest_seconds=45),
    ]),
    ("Day 5 — Lower Body & Core", [
        dict(exercise_name="Front Squat", sets=4, reps=8, rest_seconds=120),
        dict(exercise_name="Hip Thrust", sets=3, reps=10, rest_seconds=90),
        dict(exercise_name="Bulgarian Split Squat", sets=3, reps=10, rest_seconds=60),
        dict(exercise_name="Seated Leg Curl", sets=3, reps=12, rest_seconds=60),
        dict(exercise_name="Hanging Leg Raise", sets=3, reps=15, rest_seconds=45),
        dict(exercise_name="Plank", sets=3, work_seconds=60, rest_seconds=45),
    ]),
]


def _get_owned_routine(routine_id):
    routine = Routine.query.get_or_404(routine_id)
    if routine.user_id != current_user.id:
        abort(403)
    return routine


def _get_owned_day(day_id):
    day = RoutineDay.query.get_or_404(day_id)
    if day.routine.user_id != current_user.id:
        abort(403)
    return day


def _get_owned_exercise(exercise_id):
    exercise = RoutineExercise.query.get_or_404(exercise_id)
    if exercise.day.routine.user_id != current_user.id:
        abort(403)
    return exercise


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@bp.route("/")
@login_required
def list_routines():
    routines = (
        Routine.query.filter_by(user_id=current_user.id)
        .order_by(Routine.created_at.desc())
        .all()
    )
    return render_template(
        "routines/list.html",
        routines=routines,
        csrf_form=CSRFOnlyForm(),
        routine_form=RoutineForm(),
        day_form=RoutineDayForm(),
        exercise_form=RoutineExerciseForm(),
    )


@bp.route("/quick-5day", methods=["POST"])
@login_required
def quick_five_day():
    routine = Routine(user_id=current_user.id, name="5-Day Split")
    db.session.add(routine)
    db.session.flush()

    for day_idx, (day_name, exercises) in enumerate(FIVE_DAY_SPLIT):
        day = RoutineDay(routine_id=routine.id, name=day_name, order_index=day_idx)
        db.session.add(day)
        db.session.flush()
        for ex_idx, ex in enumerate(exercises):
            db.session.add(
                RoutineExercise(
                    routine_day_id=day.id,
                    order_index=ex_idx,
                    weight_unit="kg",
                    **ex,
                )
            )
    db.session.commit()
    flash("5-day split created — customize any exercise below, or hit Start.", "success")
    return redirect(url_for("routines.list_routines"))


@bp.route("/create", methods=["POST"])
@login_required
def create_routine():
    form = RoutineForm()
    if form.validate_on_submit():
        routine = Routine(user_id=current_user.id, name=form.name.data.strip())
        db.session.add(routine)
        db.session.commit()
        flash(f"Created '{routine.name}'. Add a day to get started.", "success")
    else:
        for errors in form.errors.values():
            for err in errors:
                flash(err, "error")
    return redirect(url_for("routines.list_routines"))


@bp.route("/<int:routine_id>/delete", methods=["POST"])
@login_required
def delete_routine(routine_id):
    routine = _get_owned_routine(routine_id)
    day_ids = [d.id for d in routine.days]
    if day_ids:
        WorkoutEntry.query.filter(WorkoutEntry.routine_day_id.in_(day_ids)).update(
            {"routine_day_id": None}, synchronize_session=False
        )
    db.session.delete(routine)
    db.session.commit()
    flash("Split deleted.", "success")
    return redirect(url_for("routines.list_routines"))


@bp.route("/<int:routine_id>/days/add", methods=["POST"])
@login_required
def add_day(routine_id):
    routine = _get_owned_routine(routine_id)
    form = RoutineDayForm()
    if form.validate_on_submit():
        next_index = (routine.days.count() or 0)
        db.session.add(RoutineDay(routine_id=routine.id, name=form.name.data.strip(), order_index=next_index))
        db.session.commit()
        flash("Day added.", "success")
    else:
        for errors in form.errors.values():
            for err in errors:
                flash(err, "error")
    return redirect(url_for("routines.list_routines"))


@bp.route("/days/<int:day_id>/delete", methods=["POST"])
@login_required
def delete_day(day_id):
    day = _get_owned_day(day_id)
    WorkoutEntry.query.filter_by(routine_day_id=day.id).update(
        {"routine_day_id": None}, synchronize_session=False
    )
    db.session.delete(day)
    db.session.commit()
    flash("Day deleted.", "success")
    return redirect(url_for("routines.list_routines"))


@bp.route("/days/<int:day_id>/exercises/add", methods=["POST"])
@login_required
def add_exercise(day_id):
    day = _get_owned_day(day_id)
    form = RoutineExerciseForm()
    if form.validate_on_submit():
        next_index = (day.exercises.count() or 0)
        db.session.add(
            RoutineExercise(
                routine_day_id=day.id,
                exercise_name=form.exercise_name.data.strip(),
                sets=form.sets.data,
                reps=form.reps.data,
                weight=form.weight.data,
                weight_unit=form.weight_unit.data or "kg",
                work_seconds=form.work_seconds.data,
                rest_seconds=form.rest_seconds.data or 60,
                notes=(form.notes.data or "").strip() or None,
                order_index=next_index,
            )
        )
        db.session.commit()
        flash("Exercise added.", "success")
    else:
        for errors in form.errors.values():
            for err in errors:
                flash(err, "error")
    return redirect(url_for("routines.list_routines"))


@bp.route("/exercises/<int:exercise_id>/edit", methods=["POST"])
@login_required
def edit_exercise(exercise_id):
    exercise = _get_owned_exercise(exercise_id)
    form = RoutineExerciseForm()
    if form.validate_on_submit():
        exercise.exercise_name = form.exercise_name.data.strip()
        exercise.sets = form.sets.data
        exercise.reps = form.reps.data
        exercise.weight = form.weight.data
        exercise.weight_unit = form.weight_unit.data or "kg"
        exercise.work_seconds = form.work_seconds.data
        exercise.rest_seconds = form.rest_seconds.data or 60
        exercise.notes = (form.notes.data or "").strip() or None
        db.session.commit()
        flash("Exercise updated.", "success")
    else:
        for errors in form.errors.values():
            for err in errors:
                flash(err, "error")
    return redirect(url_for("routines.list_routines"))


@bp.route("/exercises/<int:exercise_id>/delete", methods=["POST"])
@login_required
def delete_exercise(exercise_id):
    exercise = _get_owned_exercise(exercise_id)
    db.session.delete(exercise)
    db.session.commit()
    flash("Exercise removed.", "success")
    return redirect(url_for("routines.list_routines"))


@bp.route("/days/<int:day_id>/play")
@login_required
def play_day(day_id):
    day = _get_owned_day(day_id)
    exercises = day.exercises.order_by(RoutineExercise.order_index).all()
    if not exercises:
        flash("Add at least one exercise to this day before starting.", "error")
        return redirect(url_for("routines.list_routines"))
    return render_template(
        "routines/player.html",
        day=day,
        exercises=[e.to_dict() for e in exercises],
    )


@bp.route("/days/<int:day_id>/finish", methods=["POST"])
@login_required
def finish_day(day_id):
    """AJAX endpoint the guided player posts to when a session ends —
    logs every exercise the user ticked off as a real WorkoutEntry."""
    day = _get_owned_day(day_id)
    payload = request.get_json(silent=True) or {}
    completed = payload.get("completed", [])

    today = date.today()
    logged = 0
    for item in completed:
        name = (item.get("exercise_name") or "").strip()[:150]
        if not name:
            continue
        db.session.add(
            WorkoutEntry(
                user_id=current_user.id,
                upload_id=None,
                routine_day_id=day.id,
                source="routine",
                exercise_name=name,
                sets=_to_int(item.get("sets")),
                reps=_to_int(item.get("reps")),
                weight=_to_float(item.get("weight")),
                weight_unit=(item.get("weight_unit") or "kg"),
                notes=(item.get("notes") or None),
                entry_date=today,
            )
        )
        logged += 1

    db.session.commit()
    return jsonify({"ok": True, "logged": logged})
