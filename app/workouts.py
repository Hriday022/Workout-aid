from itertools import groupby

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import WorkoutUpload, WorkoutEntry, RoutineDay
from app.forms import UploadForm, WorkoutEntryForm
from app.pdf_parser import parse_workout_pdf, ParseError

bp = Blueprint("workouts", __name__, url_prefix="/workouts")


@bp.route("/")
@login_required
def dashboard():
    uploads = (
        WorkoutUpload.query.filter_by(user_id=current_user.id)
        .order_by(WorkoutUpload.uploaded_at.desc())
        .all()
    )
    unassigned_entries = (
        WorkoutEntry.query.filter_by(user_id=current_user.id, upload_id=None, routine_day_id=None)
        .order_by(WorkoutEntry.created_at.desc())
        .all()
    )

    # Sessions logged from the guided routine player, grouped by day + date
    # so a finished workout shows up as one card instead of loose rows.
    routine_entries = (
        WorkoutEntry.query.filter(
            WorkoutEntry.user_id == current_user.id,
            WorkoutEntry.routine_day_id.isnot(None),
        )
        .order_by(WorkoutEntry.entry_date.desc(), WorkoutEntry.routine_day_id, WorkoutEntry.created_at)
        .all()
    )
    sessions = []
    for (day_id, entry_date), group in groupby(
        routine_entries, key=lambda e: (e.routine_day_id, e.entry_date)
    ):
        entries = list(group)
        day = db.session.get(RoutineDay, day_id)
        sessions.append(
            {
                "day_name": day.name if day else "Deleted day",
                "routine_name": day.routine.name if day else "",
                "entry_date": entry_date,
                "entries": entries,
            }
        )

    upload_form = UploadForm()
    entry_form = WorkoutEntryForm()
    return render_template(
        "workouts/dashboard.html",
        uploads=uploads,
        unassigned_entries=unassigned_entries,
        sessions=sessions,
        upload_form=upload_form,
        entry_form=entry_form,
    )


@bp.route("/upload", methods=["POST"])
@login_required
def upload():
    form = UploadForm()
    if not form.validate_on_submit():
        for errors in form.errors.values():
            for err in errors:
                flash(err, "error")
        return redirect(url_for("workouts.dashboard"))

    file = form.pdf_file.data
    try:
        api_key = current_app.config.get("ANTHROPIC_API_KEY")
        entries_data, method = parse_workout_pdf(file.stream, api_key=api_key)
    except ParseError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workouts.dashboard"))

    workout_upload = WorkoutUpload(
        user_id=current_user.id,
        original_filename=file.filename,
        parse_method=method,
        entry_count=len(entries_data),
    )
    db.session.add(workout_upload)
    db.session.flush()  # get workout_upload.id before commit

    for data in entries_data:
        db.session.add(
            WorkoutEntry(
                user_id=current_user.id,
                upload_id=workout_upload.id,
                exercise_name=data["exercise_name"],
                sets=data.get("sets"),
                reps=data.get("reps"),
                weight=data.get("weight"),
                weight_unit=data.get("weight_unit"),
                notes=data.get("notes"),
                entry_date=data.get("entry_date"),
            )
        )
    db.session.commit()

    flash(
        f"Extracted {len(entries_data)} workout entries from {file.filename} "
        f"(via {'Claude' if method == 'claude' else 'pattern matching'}).",
        "success",
    )
    return redirect(url_for("workouts.dashboard"))


@bp.route("/entries/add", methods=["POST"])
@login_required
def add_entry():
    form = WorkoutEntryForm()
    if form.validate_on_submit():
        entry = WorkoutEntry(
            user_id=current_user.id,
            upload_id=None,
            exercise_name=form.exercise_name.data.strip(),
            sets=form.sets.data,
            reps=form.reps.data,
            weight=form.weight.data,
            weight_unit=form.weight_unit.data,
            notes=(form.notes.data or "").strip() or None,
            entry_date=form.entry_date.data,
        )
        db.session.add(entry)
        db.session.commit()
        flash("Entry added.", "success")
    else:
        for errors in form.errors.values():
            for err in errors:
                flash(err, "error")
    return redirect(url_for("workouts.dashboard"))


def _get_owned_entry(entry_id):
    entry = WorkoutEntry.query.get_or_404(entry_id)
    if entry.user_id != current_user.id:
        abort(403)
    return entry


@bp.route("/entries/<int:entry_id>/edit", methods=["POST"])
@login_required
def edit_entry(entry_id):
    entry = _get_owned_entry(entry_id)
    form = WorkoutEntryForm()
    if form.validate_on_submit():
        entry.exercise_name = form.exercise_name.data.strip()
        entry.sets = form.sets.data
        entry.reps = form.reps.data
        entry.weight = form.weight.data
        entry.weight_unit = form.weight_unit.data
        entry.entry_date = form.entry_date.data
        entry.notes = (form.notes.data or "").strip() or None
        db.session.commit()
        flash("Entry updated.", "success")
    else:
        for errors in form.errors.values():
            for err in errors:
                flash(err, "error")
    return redirect(url_for("workouts.dashboard"))


@bp.route("/entries/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete_entry(entry_id):
    entry = _get_owned_entry(entry_id)
    db.session.delete(entry)
    db.session.commit()
    flash("Entry deleted.", "success")
    return redirect(url_for("workouts.dashboard"))


@bp.route("/uploads/<int:upload_id>/delete", methods=["POST"])
@login_required
def delete_upload(upload_id):
    upload_row = WorkoutUpload.query.get_or_404(upload_id)
    if upload_row.user_id != current_user.id:
        abort(403)
    db.session.delete(upload_row)  # cascades to its entries
    db.session.commit()
    flash("Upload and its entries deleted.", "success")
    return redirect(url_for("workouts.dashboard"))
