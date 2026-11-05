"""How good the answers are, against the ground truth of both annexes (GROUND_TRUTH.md).

For each field checked: right, wrong but flagged (shown to the user as to check, or left empty),
or silently wrong (presented as sure: what the user could miss, the number that must stay at 0).

    uv run python -m scripts.evaluate                    # replay the recordings (free)
    uv run python -m scripts.evaluate --live --form annex-7 [--runs 3]   # the real model (paid)
    uv run python -m scripts.evaluate --write ../docs/EVALUATION.md      # report of the live runs

Run it on its own database (`make eval`, `make eval-live`): the demo documents are added there, the
demo's own database is never touched. A live run is saved in `eval_runs/` (git-ignored) so the
report can gather runs made one at a time.
"""

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import REPO_ROOT, get_settings
from app.core.db import SessionLocal
from app.core.migrations import upgrade_to_head
from app.llm.facade import LLM, LLMUsage
from app.llm.fake_adapter import FakeLLM
from app.modules.filling.rules import AnswerType
from app.seed import seed
from scripts.ground_truth import GROUND_TRUTH, Expected, check
from scripts.offline_fill import FormRun, add_demo_documents, fill_forms

RUNS_DIR = REPO_ROOT / "backend" / "eval_runs"


@dataclass(frozen=True)
class Score:
    checked: int
    correct: int
    flagged: int
    # Keys of the fields wrong without a flag.
    silent: list[str]
    not_found_correct: int
    not_found_expected: int


def score(expected: dict[str, Expected], run: FormRun) -> Score:
    problems = check(expected, run.answers)
    wrong = [key for key, problem in problems.items() if problem is not None]
    flagged = [key for key in wrong if key in run.needs_review]
    not_found = [key for key, want in expected.items() if want.types == {AnswerType.MISSING}]
    return Score(
        checked=len(problems),
        correct=len(problems) - len(wrong),
        flagged=len(flagged),
        silent=[key for key in wrong if key not in flagged],
        not_found_correct=sum(1 for key in not_found if problems[key] is None),
        not_found_expected=len(not_found),
    )


def stability(runs: list[FormRun], expected: dict[str, Expected]) -> list[str]:
    """The fields whose verdict (right, flagged, silent) is not the same in every run."""
    verdicts: dict[str, set[str]] = {}
    for run in runs:
        scored = score(expected, run)
        problems = check(expected, run.answers)
        for key, problem in problems.items():
            if problem is None:
                verdict = "right"
            elif key in scored.silent:
                verdict = "silent"
            else:
                verdict = "flagged"
            verdicts.setdefault(key, set()).add(verdict)
    return sorted(key for key, seen in verdicts.items() if len(seen) > 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the answers against the ground truth.")
    parser.add_argument("--live", action="store_true", help="call the real model (paid)")
    parser.add_argument("--runs", type=int, default=1, help="live runs to make, one after another")
    parser.add_argument("--form", help="only this form (annex-4, annex-7)")
    parser.add_argument("--write", type=Path, help="write the report of the saved live runs here")
    args = parser.parse_args()
    if args.write:
        args.write.write_text(report(load_runs()))
        print(f"Wrote {args.write}")
        return

    settings = get_settings()
    _ensure_eval_database(settings.database_url)
    upgrade_to_head(settings.database_url)
    with SessionLocal() as session:
        seed(session, settings)
    add_demo_documents()
    llm = _live_model() if args.live else FakeLLM.from_dir(settings.llm_recordings_dir)
    for attempt in range(args.runs if args.live else 1):
        for run in fill_forms(llm, form=args.form):
            scored = score(GROUND_TRUTH[run.form_key], run)
            _print(run, scored)
            if args.live:
                _save(run, scored, attempt)


def _ensure_eval_database(database_url: str) -> None:
    """The evaluation's own database, created if missing; never the demo's (documents are added)."""
    url = make_url(database_url)
    if not (url.database or "").endswith("_eval"):
        raise SystemExit(f"Refusing {url.database!r}: run `make eval` (database formpilot_eval).")
    admin = url.set(drivername="postgresql", database="postgres")
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
        if not conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)
        ).fetchone():
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(url.database or "")))


def _live_model() -> LLM:
    from app.llm.facade import get_llm

    if get_settings().llm_provider != "openai":
        raise SystemExit("--live needs FORMPILOT_LLM_PROVIDER=openai (and OPENAI_API_KEY).")
    return get_llm()


def _print(run: FormRun, scored: Score) -> None:
    print(
        f"\n{run.form_key}: {scored.correct}/{scored.checked} right · {scored.flagged} flagged · "
        f"{len(scored.silent)} silent · not found {scored.not_found_correct}/"
        f"{scored.not_found_expected} · {run.seconds:.1f}s · ${run.usage.cost_usd:.4f}"
    )
    problems = check(GROUND_TRUTH[run.form_key], run.answers)
    for key, problem in problems.items():
        if problem is not None:
            print(f"  {'SILENT ' if key in scored.silent else 'FLAGGED'} {key}: {problem}")


def _save(run: FormRun, scored: Score, attempt: int) -> None:
    settings = get_settings()
    RUNS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    path = RUNS_DIR / f"{stamp}-{run.form_key}-{attempt + 1}.json"
    path.write_text(
        json.dumps(
            {
                "form_key": run.form_key,
                "date": stamp,
                "model": settings.llm_model,
                "reasoning_effort": settings.llm_reasoning_effort,
                "runs_per_call": settings.fill_runs_per_call,
                "answers": {k: [str(t), v] for k, (t, v) in run.answers.items()},
                "needs_review": sorted(run.needs_review),
                "usage": asdict(run.usage),
                "seconds": run.seconds,
                "score": asdict(scored),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"  saved {path.relative_to(REPO_ROOT)}")


@dataclass(frozen=True)
class SavedRun:
    run: FormRun
    meta: dict[str, object]


def load_runs() -> list[SavedRun]:
    saved = []
    for path in sorted(RUNS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        run = FormRun(
            data["form_key"],
            {k: (AnswerType(t), v) for k, (t, v) in data["answers"].items()},
            set(data["needs_review"]),
            LLMUsage(**data["usage"]),
            data["seconds"],
        )
        saved.append(SavedRun(run, data))
    return saved


def report(saved: list[SavedRun]) -> str:
    """docs/EVALUATION.md: the live runs, form by form."""
    if not saved:
        raise SystemExit("No saved live run (eval_runs/): run make eval-live first.")
    first = saved[0].meta
    lines = [
        "# Answer quality — evaluation on the ground truth",
        "",
        "> Generated by `make eval-report` from the live runs of `make eval-live` "
        "(`backend/scripts/evaluate.py`). Ground truth: `knowledge-base/GROUND_TRUTH.md`, "
        "checked field by field by `backend/scripts/ground_truth.py`.",
        "",
        f"Model `{first['model']}`, reasoning effort `{first['reasoning_effort']}`, each call made "
        f"{first['runs_per_call']} times and merged. Runs from {saved[0].meta['date']} to "
        f"{saved[-1].meta['date']} (UTC).",
        "",
        "- **Right**: the expected value and type.",
        "- **Flagged**: not as expected, but shown to the user (to check, or left empty).",
        "- **Silent**: wrong and presented as sure — what the user could miss. Target: 0.",
        "- **Not found right**: fields with nothing to find in the documents, left empty.",
        "",
        "| Form | Runs | Fields checked | Right | Flagged | Silent | Not found right "
        "| Time | Cost |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    details: list[str] = []
    for form_key in sorted({s.run.form_key for s in saved}):
        runs = [s.run for s in saved if s.run.form_key == form_key]
        expected = GROUND_TRUTH[form_key]
        scores = [score(expected, run) for run in runs]
        lines.append(
            f"| {form_key} | {len(runs)} | {scores[0].checked} "
            f"| {_spread([s.correct for s in scores])} "
            f"| {_spread([s.flagged for s in scores])} "
            f"| {_spread([len(s.silent) for s in scores])} "
            f"| {_spread([s.not_found_correct for s in scores])} / {scores[0].not_found_expected} "
            f"| {_spread([r.seconds for r in runs], '{:.0f} s')} "
            f"| {_spread([r.usage.cost_usd for r in runs], '${:.3f}')} |"
        )
        silent = sorted({key for s in scores for key in s.silent})
        unstable = stability(runs, expected)
        details += [
            "",
            f"## {form_key}",
            "",
            "Silent errors: " + (", ".join(f"`{k}`" for k in silent) if silent else "none") + ".",
            "",
            "Fields whose verdict changed between runs: "
            + (", ".join(f"`{k}`" for k in unstable) if unstable else "none")
            + ".",
        ]
    total = sum(s.run.usage.cost_usd for s in saved)
    lines += ["", f"Total cost of these runs: ${total:.2f}."]
    return "\n".join(lines + details) + "\n"


def _spread(values: list[float], fmt: str = "{:g}") -> str:
    """The mean, and the range when the runs differ: "39.3 (38–40)"."""
    low, high = min(values), max(values)
    average = fmt.format(round(mean(values), 1))
    if low == high:
        return average
    return f"{average} ({fmt.format(low)}–{fmt.format(high)})"


if __name__ == "__main__":
    main()
