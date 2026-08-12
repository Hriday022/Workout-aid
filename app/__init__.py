import logging
import os
from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import inspect, text

from config import Config
from app.extensions import db, login_manager, csrf


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Render sits behind a reverse proxy — needed for correct scheme/host detection.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.auth import bp as auth_bp
    from app.workouts import bp as workouts_bp
    from app.routines import bp as routines_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(workouts_bp)
    app.register_blueprint(routines_bp)

    @app.route("/")
    def index():
        from flask import redirect, url_for
        from flask_login import current_user

        if current_user.is_authenticated:
            return redirect(url_for("workouts.dashboard"))
        return redirect(url_for("auth.login"))

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors.html", code=403, message="You don't have access to that."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors.html", code=404, message="Page not found."), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template("errors.html", code=413, message="File too large (10MB max)."), 413

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled server error")
        return render_template("errors.html", code=500, message="Something went wrong on our end."), 500

    if not app.debug and not app.testing:
        logging.basicConfig(level=logging.INFO)

    with app.app_context():
        db.create_all()
        _ensure_schema()

    return app


def _ensure_schema():
    """Adds new columns to tables that already existed before the routines/
    splits feature shipped, so existing SQLite/Postgres databases don't need
    a full migration tool for this one addition."""
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()
    if "workout_entries" not in table_names:
        return

    existing_cols = {c["name"] for c in inspector.get_columns("workout_entries")}
    statements = []
    if "routine_day_id" not in existing_cols:
        statements.append("ALTER TABLE workout_entries ADD COLUMN routine_day_id INTEGER")
    if "source" not in existing_cols:
        statements.append("ALTER TABLE workout_entries ADD COLUMN source VARCHAR(20) DEFAULT 'manual'")

    if statements:
        with db.engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
