"""
Turns an uploaded PDF's text into a list of workout entries.

Two strategies:
  1. Regex heuristics (always available, no external calls) — handles common
     shorthand like "Bench Press 3x8 @ 60kg" or "Squat: 4 sets x 10 reps, 80kg".
  2. Claude-based extraction (used automatically if ANTHROPIC_API_KEY is set) —
     far more robust against messy, freeform, or inconsistently formatted PDFs.

The PDF is read straight from the uploaded file stream and never touches disk.
"""
import io
import json
import re
from datetime import datetime

import pdfplumber


class ParseError(Exception):
    pass


def extract_text(file_stream) -> str:
    try:
        with pdfplumber.open(io.BytesIO(file_stream.read())) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    except Exception as exc:
        raise ParseError(f"Could not read this PDF: {exc}")

    text = "\n".join(pages).strip()
    if not text:
        raise ParseError("No extractable text found (this may be a scanned/image-only PDF).")
    return text


# --- Regex fallback parser -------------------------------------------------

# Matches lines like:
#   "Bench Press 3x8 @ 60kg"
#   "Squat: 4 sets x 10 reps, 80 kg"
#   "Deadlift 5x5 100lb"
#   "Plank 3x60s"   (sets x duration, no weight)
LINE_PATTERN = re.compile(
    r"""^\s*
    (?P<name>[A-Za-z][A-Za-z0-9\-\/ ]{1,60}?)          # exercise name
    [\s:\-]+
    (?P<sets>\d{1,2})\s*(?:sets?)?\s*[xX×]\s*           # sets
    (?P<reps>\d{1,3})\s*(?:reps?)?                      # reps
    (?:[\s,@]+(?P<weight>\d{1,4}(?:\.\d+)?)\s*(?P<unit>kg|lb|lbs)?)?
    """,
    re.VERBOSE,
)


def parse_with_regex(text: str) -> list[dict]:
    entries = []
    for raw_line in text.splitlines():
        line = raw_line.strip(" \t•-*")
        if not line:
            continue
        match = LINE_PATTERN.match(line)
        if not match:
            continue
        name = match.group("name").strip().title()
        if len(name) < 2:
            continue
        weight = match.group("weight")
        entries.append(
            {
                "exercise_name": name,
                "sets": int(match.group("sets")),
                "reps": int(match.group("reps")),
                "weight": float(weight) if weight else None,
                "weight_unit": (match.group("unit") or "kg").lower().rstrip("s"),
                "notes": None,
                "entry_date": None,
            }
        )
    return entries


# --- Claude-based parser ----------------------------------------------------

EXTRACTION_PROMPT = """You extract structured workout data from raw text pulled from a \
PDF workout log. Return ONLY a JSON array (no markdown fences, no commentary). Each item:
{{"exercise_name": str, "sets": int|null, "reps": int|null, "weight": number|null, \
"weight_unit": "kg"|"lb"|null, "notes": str|null, "entry_date": "YYYY-MM-DD"|null}}
Skip lines that aren't actual exercises (headers, page numbers, etc). If a date heading \
applies to entries below it, apply it as entry_date for those entries.

TEXT:
{text}"""


def parse_with_claude(text: str, api_key: str) -> list[dict]:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(text=text[:12000])}],
    )
    raw = "".join(block.text for block in response.content if hasattr(block, "text")).strip()
    raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ParseError(f"Claude returned unparseable output: {exc}")

    entries = []
    for item in data:
        entry_date = None
        if item.get("entry_date"):
            try:
                entry_date = datetime.strptime(item["entry_date"], "%Y-%m-%d").date()
            except ValueError:
                entry_date = None
        entries.append(
            {
                "exercise_name": str(item.get("exercise_name", "")).strip()[:150] or "Unknown",
                "sets": item.get("sets"),
                "reps": item.get("reps"),
                "weight": item.get("weight"),
                "weight_unit": item.get("weight_unit"),
                "notes": (item.get("notes") or None),
                "entry_date": entry_date,
            }
        )
    return entries


def parse_workout_pdf(file_stream, api_key: str | None = None) -> tuple[list[dict], str]:
    """Returns (entries, method_used)."""
    text = extract_text(file_stream)

    if api_key:
        try:
            entries = parse_with_claude(text, api_key)
            if entries:
                return entries, "claude"
        except Exception:
            pass  # fall through to regex

    entries = parse_with_regex(text)
    if not entries:
        raise ParseError(
            "Couldn't find any recognizable workout lines. Expected a format like "
            "'Bench Press 3x8 @ 60kg' per line."
        )
    return entries, "regex"
