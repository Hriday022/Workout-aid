# Gym Tracker

Upload a workout PDF, get the exercises auto-extracted into a CRUD table you can edit and delete from.

## How it works

- **Auth**: signup/login with hashed passwords (Flask-Login + Werkzeug), CSRF-protected forms (Flask-WTF).
- **Upload**: PDF is read straight from the upload stream with `pdfplumber` — it's **never written to disk**,
  so there's nothing lost when Render restarts or redeploys the container.
- **Parsing**: a regex parser handles common shorthand ("Bench Press 3x8 @ 60kg") out of the box. If you set
  `ANTHROPIC_API_KEY`, uploads are parsed with Claude instead, which handles messy/freeform PDFs far better.
- **CRUD**: every extracted exercise becomes an editable, deletable row. You can also delete an entire upload
  (cascades to its entries) or add entries manually.
- **Data isolation**: every query is scoped to `current_user.id` — users only ever see their own data.

## Local setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then edit SECRET_KEY
python wsgi.py                  # runs on http://127.0.0.1:5000
```

Without `DATABASE_URL` set, it uses a local SQLite file (`gym_tracker.db`) — fine for development.

## Deploying to Render

**Option A — one click via Blueprint**
1. Push this project to a GitHub repo.
2. In the Render dashboard: **New → Blueprint**, point it at your repo. `render.yaml` provisions both
   the web service and a free Postgres database automatically.
3. Render will prompt you to set `ANTHROPIC_API_KEY` (optional — leave blank to use the regex parser only).
4. Deploy. `SECRET_KEY` is auto-generated; `DATABASE_URL` is wired to the Postgres instance for you.

**Option B — manual**
1. **New → PostgreSQL** — create a database, copy its "Internal Connection String".
2. **New → Web Service** — connect your repo.
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn wsgi:app`
3. Under Environment, add:
   - `SECRET_KEY` — any random string (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`)
   - `DATABASE_URL` — the connection string from step 1
   - `FLASK_ENV` = `production`
   - `ANTHROPIC_API_KEY` — optional, for Claude-based PDF parsing
4. Deploy.

### Why Postgres and not the SQLite from the original project?

Render's free/starter web services have an **ephemeral filesystem** — anything written to disk (including a
SQLite file) is wiped on every restart or redeploy. Since this app never writes the uploaded PDF to disk either,
switching the *database* to Postgres is the only thing needed for full persistence in production. Local
development still works with zero config using SQLite.

### Why not Vercel?

Vercel's Python runtime is serverless (each request may hit a cold, stateless function) — it doesn't support
a long-running Flask app with a persistent SQLAlchemy/session model the way Render does, and you'd need to
rearchitect around Vercel's function model. Render runs this app largely unchanged.

## Notes for going further

- Schema changes: this uses `db.create_all()` on startup for simplicity. If you start changing models after
  you have real user data, add [Flask-Migrate](https://flask-migrate.readthedocs.io/) instead of relying on that.
- Rate limiting isn't included — consider `Flask-Limiter` on `/auth/login` and `/workouts/upload` before
  a public launch.
- The regex parser only catches "Exercise 3x8 @ 60kg"-style lines. If your PDFs are more freeform (paragraphs,
  tables, inconsistent formatting), set `ANTHROPIC_API_KEY` — it will use Claude for those, per-request.
