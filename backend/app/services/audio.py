"""Per-simulation dual audio assets:
1. Case Overview & Summary (narrator voice)
2. Case Argument Discussion (multi-voice hearing with distinct roles)
(PRD §9 "giving a voice to the case").

All spoken text is thoroughly cleansed of markdown artifacts (#, *, _, ~, `, >),
system notices, and reasoning tags before synthesis.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.scenario import ScenarioVersion
from app.models.simulation import Simulation, SimulationAudio, SimulationTurn
from app.services import tts as tts_service

logger = logging.getLogger(__name__)

# One synthesis job at a time per simulation — concurrent runs delete each
# other's pending ORM rows and blow up on commit ("Instance has been deleted").
_GENERATE_LOCKS: dict[str, threading.Lock] = {}
_GENERATE_LOCKS_GUARD = threading.Lock()
# Avoid thrashing re-enqueue when the UI polls a dead pending job.
_STALE_REQUEUE_AT: dict[str, float] = {}


def _lock_for_sim(simulation_id: str) -> threading.Lock:
    with _GENERATE_LOCKS_GUARD:
        lock = _GENERATE_LOCKS.get(simulation_id)
        if lock is None:
            lock = threading.Lock()
            _GENERATE_LOCKS[simulation_id] = lock
        return lock


def is_generating(simulation_id: str) -> bool:
    """True while this process holds the per-sim synthesis lock."""
    with _GENERATE_LOCKS_GUARD:
        lock = _GENERATE_LOCKS.get(simulation_id)
    return bool(lock and lock.locked())


def _ensure_generation_running(
    *, simulation_id: str, organization_id: str, db: Session, rows: list[SimulationAudio]
) -> None:
    """If pending rows exist with no files and no live worker, re-queue synthesis.

    Auto-enqueue after sim completion uses an in-process daemon thread. Uvicorn
    ``--reload`` (and process restarts) kill that worker while leaving ``pending``
    rows forever — refresh then looked stuck.
    """
    if not rows:
        return
    if any(r.status == "ready" for r in rows):
        return
    if not all(r.status == "pending" for r in rows):
        return
    if is_generating(simulation_id):
        return

    sim_dir = tts_service.ensure_data_dir() / simulation_id
    has_files = sim_dir.exists() and any(
        (sim_dir / name).exists()
        for name in ("case-overview.mp3", "argument-discussion.mp3")
    )
    if has_files:
        return

    now = time.time()
    last = _STALE_REQUEUE_AT.get(simulation_id, 0.0)
    if now - last < 20.0:
        for r in rows:
            if r.status == "pending" and not (r.error or "").strip():
                r.error = "Waiting for synthesizer to start…"
                r.estimated_tokens = max(1, r.estimated_tokens or 1)
        try:
            db.commit()
        except Exception:
            db.rollback()
        return

    _STALE_REQUEUE_AT[simulation_id] = now
    for r in rows:
        if r.status == "pending":
            r.error = "Restarting synthesis (previous job was interrupted)…"
            r.estimated_tokens = 2
    try:
        db.commit()
    except Exception:
        db.rollback()

    try:
        from app.queue import enqueue

        enqueue(generate_assets_job, simulation_id, organization_id)
        logger.info(
            "re-queued stale audio synthesis for simulation %s", simulation_id
        )
    except Exception:
        logger.exception(
            "failed to re-queue stale audio synthesis for %s", simulation_id
        )



def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def clean_speech_text(raw_text: str, is_turn: bool = False) -> str:
    """Sanitize raw LLM and markdown text into natural, articulate spoken speech.

    Eliminates all markdown symbols (#, *, _, ~, `, >, |, [links]),
    strips reasoning markers (## THINKING, ## ACTION, <think>), disclaimers,
    expands statutory symbols (§ -> Section) and abbreviations (v. -> versus)
    so TTS never pronounces symbols like 'hash' or 'asterisk'.
    """
    if not raw_text:
        return ""

    text = raw_text.strip()

    # If this is a turn dialogue, extract the actual spoken argument
    if is_turn:
        # Check for ## OUTPUT or OUTPUT:
        output_match = re.search(
            r"##\s*OUTPUT\s*\n+(.*?)(?=\n*##|\Z)", text, flags=re.DOTALL | re.IGNORECASE
        )
        if output_match:
            text = output_match.group(1).strip()
        else:
            # Strip out ## THINKING ... and ## ACTION ... blocks
            text = re.sub(
                r"##\s*THINKING\s*\n+.*?(?=\n*##|\Z)",
                "",
                text,
                flags=re.DOTALL | re.IGNORECASE,
            )
            text = re.sub(
                r"##\s*ACTION\s*\n+.*?(?=\n*##|\Z)",
                "",
                text,
                flags=re.DOTALL | re.IGNORECASE,
            )
            # Also strip <think>...</think>
            text = re.sub(
                r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE
            )

    # Strip system fallback notices like (_The configured LLM..._)
    text = re.sub(r"\(_.*?_\)", "", text)

    # Strip common disclaimers & citation annotations
    text = re.sub(
        r"(?i)educational and informational\.?\s*not legal advice\.?", "", text
    )
    text = re.sub(r"(?i)\*{0,2}citation(?:\s+needed)?\*{0,2}:?.*", "", text)

    # Strip markdown code blocks & images
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

    # Strip markdown links, keeping label: [label](url) -> label
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)

    # Strip ANY header hashes (e.g. ### Header, ## Header, or stray #)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = text.replace("#", "")

    # Expand legal symbols & citations into natural spoken English
    text = re.sub(r"\b(?:v\.|vs\.)\b", "versus", text, flags=re.IGNORECASE)
    text = re.sub(r"§{2}\s*", "Sections ", text)
    text = re.sub(
        r"§\s*([0-9]+(?:\([a-z0-9]+\))*)", r"Section \1", text, flags=re.IGNORECASE
    )
    text = re.sub(r"§\s*", "Section ", text)
    text = re.sub(r"¶\s*([0-9]+)", r"paragraph \1", text, flags=re.IGNORECASE)
    text = re.sub(r"\bapprox\.\b", "approximately", text, flags=re.IGNORECASE)
    text = re.sub(r"\be\.g\.,?\b", "for example,", text, flags=re.IGNORECASE)
    text = re.sub(r"\bi\.e\.,?\b", "that is,", text, flags=re.IGNORECASE)
    text = re.sub(r"\bet al\.\b", "and others", text, flags=re.IGNORECASE)

    # Oralize numbered lists at start of lines for smooth spoken cadence
    text = re.sub(r"^\s*1\.\s+", "First, ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*2\.\s+", "Second, ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*3\.\s+", "Third, ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*4\.\s+", "Fourth, ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*5\.\s+", "Fifth, ", text, flags=re.MULTILINE)

    # Strip bullet symbols at line beginnings
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)

    # Strip formatting characters: *, _, `, ~, >, |, \
    text = re.sub(r"[*_`~>|\\]", " ", text)

    # Normalize quotes
    text = text.replace('"', '"').replace('"', '"').replace("'", "'").replace("'", "'")

    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def adapt_to_live_courtroom_speech(
    role: str,
    raw_text: str,
    *,
    turn_index: int,
    total_turns: int,
    phase: str = "",
    case_title: str = "",
) -> str:
    """Adapt written legal dialogue into authentic live courtroom oral argument speech.

    Injects realistic courtroom opening announcements, rhetorical advocate framing,
    bench interventions, and judicial adjournment orders, while keeping the UI text
    completely clean and readable for the user.
    """
    clean = clean_speech_text(raw_text, is_turn=True)
    if not clean:
        return ""

    role_key = (role or "").lower()

    # Oralize 3rd-person text if the model generated passive summaries
    if "plaintiff" in role_key:
        clean = re.sub(
            r"^(?:the\s+)?plaintiff(?:'s)?\s+(?:respectfully\s+)?(?:claims?|submits?|argues?|contends?)\s+(?:that\s+)?",
            "We submit to the Court that ",
            clean,
            flags=re.IGNORECASE,
        )
    elif "defendant" in role_key:
        clean = re.sub(
            r"^(?:the\s+)?defendant(?:'s)?\s+(?:respectfully\s+)?(?:claims?|submits?|argues?|contends?)\s+(?:that\s+)?",
            "We firmly submit to Your Honor that ",
            clean,
            flags=re.IGNORECASE,
        )
    elif "judge" in role_key:
        clean = re.sub(
            r"^(?:the\s+)?judge\s+(?:finds?|notes?|holds?|concludes?)\s+(?:that\s+)?",
            "The Court finds that ",
            clean,
            flags=re.IGNORECASE,
        )

    parts: list[str] = []

    # If first spoken turn, include formal Courtroom Call / Bailiff proclamation
    if turn_index == 0:
        matter = case_title or "this proceeding"
        parts.append(
            f"All rise. The judicial tribunal is now in session in the matter of {matter}. "
            "Presiding Judge presiding. Counsel for the plaintiff, you may present your argument to the Court."
        )

    # Frame each role's spoken oral argument with emotional rhetorical delivery
    if "plaintiff" in role_key:
        if turn_index == 0 or phase == "opening":
            parts.append(
                f"May it please the Court! Counsel appearing on behalf of the plaintiff. Your Honor, our position is unequivocal: {clean}"
            )
        elif turn_index >= total_turns - 2 or phase == "outcome":
            parts.append(
                f"In closing, members of the tribunal, the plaintiff adamantly urges the Court to enter judgment in our favor: {clean}"
            )
        else:
            parts.append(
                f"Your Honor, the plaintiff directly refutes opposing counsel's assertions! {clean}"
            )
    elif "defendant" in role_key:
        if turn_index <= 1 or phase == "opening":
            parts.append(
                f"With the Court's permission, counsel for the defense appearing. Your Honor, we categorically dispute liability. {clean}"
            )
        elif turn_index >= total_turns - 2 or phase == "outcome":
            parts.append(
                f"In conclusion, the defense firmly submits that the claims must be dismissed in their entirety. {clean}"
            )
        else:
            parts.append(
                f"Respectfully, Your Honor, opposing counsel's position cannot stand under the law. {clean}"
            )
    elif "judge" in role_key:
        if (
            turn_index >= total_turns - 1
            or phase == "outcome"
            or "verdict" in clean.lower()
            or "summary" in clean.lower()
        ):
            parts.append(
                f"Order in the court. The tribunal has evaluated the evidentiary submissions and oral arguments of both parties. The Court now enters its final determination: {clean}"
            )
        else:
            parts.append(
                f"Counsel, the Court intervenes. Address this specific question: {clean}"
            )
    elif "witness" in role_key:
        parts.append(f"Calling witness to the stand. Witness testifying: {clean}")
    elif "informer" in role_key:
        parts.append(
            f"With leave of the tribunal, presenting the regulatory and legal procedural advisory assessment: {clean}"
        )
    else:
        parts.append(clean)

    # If final turn in the hearing, add the adjournment order
    if turn_index == total_turns - 1:
        parts.append(
            "The Court has heard the submissions of counsel. This hearing now stands adjourned."
        )

    return " ".join(parts)


def extract_case_overview_text(sim: Simulation, db: Session) -> str:
    """Build a spoken case overview via LLM — scoped for narration, never truncated.

    The LLM is instructed to produce a complete oral briefing (facts, issues,
    parties' positions, holding) sized for about 2–4 minutes of speech. Falls
    back to a structured deterministic overview if the LLM is unavailable.
    """
    sv = (
        db.query(ScenarioVersion)
        .filter(ScenarioVersion.id == sim.scenario_version_id)
        .first()
    )
    title = sv.title if sv and sv.title else "Simulated Legal Dispute"
    scenario = sv.scenario if sv else None
    jurisdiction = (
        scenario.jurisdiction if scenario and scenario.jurisdiction else ""
    ).strip()
    domain = (scenario.domain if scenario and scenario.domain else "").strip()
    fact_pattern = (sv.fact_pattern if sv else "") or ""
    cs = getattr(sim, "case_study", None)
    case_md = (cs.markdown_content if cs else "") or ""
    verdict = (sim.state or {}).get("verdict") or {}
    winner = (
        verdict.get("winner", "") if isinstance(verdict, dict) else ""
    ) or ""
    rationale = (
        verdict.get("rationale", "") if isinstance(verdict, dict) else ""
    ) or ""

    turns = (
        db.query(SimulationTurn)
        .filter(SimulationTurn.simulation_id == sim.id)
        .order_by(SimulationTurn.turn_number)
        .all()
    )
    transcript_bits: list[str] = []
    for t in turns[:12]:
        spoken = clean_speech_text(t.text or "", is_turn=True)
        if spoken:
            transcript_bits.append(
                f"{(t.agent_role or 'party').title()} ({t.phase or 'hearing'}): {spoken}"
            )
    transcript = "\n\n".join(transcript_bits)

    source_pack = "\n\n".join(
        part
        for part in (
            f"Title: {title}",
            f"Jurisdiction: {jurisdiction or 'unspecified'}",
            f"Domain: {domain or 'unspecified'}",
            f"Fact pattern:\n{fact_pattern}" if fact_pattern else "",
            f"Case study markdown:\n{case_md}" if case_md else "",
            f"Tribunal winner: {winner}" if winner else "",
            f"Rationale: {rationale}" if rationale else "",
            f"Hearing transcript excerpts:\n{transcript}" if transcript else "",
        )
        if part
    )

    system = (
        "You write spoken narration for a legal-education tribunal replay. "
        "Output plain prose only — no markdown, no bullet symbols, no headings, "
        "no stage directions. Write complete sentences a narrator can read aloud."
    )
    user = (
        "Compose a complete Case Overview & Executive Summary for audio narration.\n"
        "Cover, in order: (1) case identity and jurisdiction, (2) material facts, "
        "(3) principal legal issues, (4) each side's core position, "
        "(5) the tribunal's determination and reasoning.\n"
        "Write a full oral briefing a narrator can read aloud end-to-end. "
        "Do not omit the holding. Finish every sentence. No markdown.\n"
        "Educational and informational. Not legal advice.\n\n"
        f"SOURCE MATERIALS:\n{source_pack}"
    )

    try:
        from app.llm.factory import get_llm

        llm = get_llm()
        raw = llm.chat(system, [{"role": "user", "content": user}])
        spoken = clean_speech_text(raw or "", is_turn=False)
        if len(spoken) >= 120:
            return spoken
        logger.warning(
            "LLM overview too short (%s chars); using deterministic fallback",
            len(spoken),
        )
    except Exception:
        logger.exception("LLM case overview generation failed; using fallback")

    # Deterministic fallback — full content, no artificial clipping.
    parts: list[str] = [
        f"This is the case overview for {title}."
    ]
    if jurisdiction or domain:
        parts.append(
            f"The matter arises in {jurisdiction or 'a general'} jurisdiction "
            f"within the {domain or 'dispute resolution'} domain."
        )
    if fact_pattern:
        parts.append(
            f"The factual background is as follows. {clean_speech_text(fact_pattern, is_turn=False)}"
        )
    if winner:
        parts.append(f"The tribunal determined that the winner is {winner}.")
    if rationale:
        parts.append(
            f"The reasoning was as follows. {clean_speech_text(rationale, is_turn=False)}"
        )
    if case_md and not fact_pattern:
        parts.append(clean_speech_text(case_md, is_turn=False))
    parts.append("This concludes the case overview briefing.")
    return clean_speech_text(" ".join(parts), is_turn=False)



def _concat_audio_files(input_paths: list[Path], output_path: Path) -> Path:
    """Concatenate multiple audio files into one cohesive track."""
    if not input_paths:
        raise ValueError("No audio files to concatenate")
    if len(input_paths) == 1:
        shutil.copyfile(input_paths[0], output_path)
        return output_path

    ffmpeg_bin = shutil.which("ffmpeg") or (
        "/opt/homebrew/bin/ffmpeg"
        if Path("/opt/homebrew/bin/ffmpeg").exists()
        else None
    )

    if ffmpeg_bin:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for p in input_paths:
                f.write(f"file '{p.resolve()}'\n")
            list_path = Path(f.name)
        try:
            cmd = [
                ffmpeg_bin,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c",
                "copy",
                str(output_path),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if (
                res.returncode == 0
                and output_path.exists()
                and output_path.stat().st_size > 0
            ):
                return output_path
        except Exception as exc:
            logger.warning(
                "ffmpeg concat failed (%s), falling back to stream concat", exc
            )
        finally:
            if list_path.exists():
                list_path.unlink()

    # Fallback: MP3 streams can be concatenated by joining frames directly
    with open(output_path, "wb") as outfile:
        for p in input_paths:
            with open(p, "rb") as infile:
                outfile.write(infile.read())
    return output_path


def _load(
    simulation_id: str, *, organization_id: str, db: Session
) -> tuple[Simulation, list[SimulationTurn]]:
    sim = db.query(Simulation).filter(Simulation.id == simulation_id).one_or_none()
    if sim is None or sim.organization_id != organization_id:
        raise LookupError(f"simulation {simulation_id} not found in this organization")
    turns = (
        db.query(SimulationTurn)
        .filter(SimulationTurn.simulation_id == simulation_id)
        .order_by(SimulationTurn.turn_number)
        .all()
    )
    return sim, turns


def _write_single_asset(
    db: Session,
    *,
    simulation_id: str,
    organization_id: str,
    kind: str,
    agent_role: str,
    turn_number: int,
    text: str,
    asset_name: str,
) -> SimulationAudio:
    """Synthesize text into an audio file and persist a SimulationAudio record."""
    row = SimulationAudio(
        id=uuid.uuid4().hex,
        simulation_id=simulation_id,
        organization_id=organization_id,
        kind=kind,
        agent_role=agent_role or "narrator",
        turn_number=turn_number,
        file_name="",
        format="",
        size_bytes=0,
        status="pending",
        error="",
        generated_at=None,
    )
    try:
        t0 = time.monotonic()
        data = tts_service.synthesize(text, role=agent_role or "narrator")
        row.duration_ms = int((time.monotonic() - t0) * 1000)
        row.estimated_tokens = max(1, len(text or "") // 4)
    except tts_service.TTSError as exc:
        row.status = "error"
        row.error = str(exc)
        db.add(row)
        db.commit()
        return row

    path = tts_service.write_audio_file(
        simulation_id=simulation_id,
        asset_name=asset_name,
        data=data,
    )
    row.file_name = path.name
    row.format = tts_service.file_extension()
    row.size_bytes = path.stat().st_size
    row.status = "ready"
    row.generated_at = utcnow()
    db.add(row)
    db.commit()
    return row


def generate_assets(
    *,
    simulation_id: str,
    organization_id: str,
    db: Session,
) -> list[SimulationAudio]:
    """Generate the 2 official simulation audios:
    1. Case Overview & Summary (narrator voice)
    2. Case Argument Discussion (multi-voice hearing with distinct role voices)
    """
    with _lock_for_sim(simulation_id):
        return _generate_assets_locked(
            simulation_id=simulation_id, organization_id=organization_id, db=db
        )


def _set_audio_progress(
    db: Session, row: SimulationAudio | None, message: str, pct: int = 0
) -> None:
    """Publish progress on a pending audio row (reuses error/estimated_tokens while pending)."""
    if row is None:
        return
    try:
        row.error = message
        row.estimated_tokens = max(0, min(100, int(pct)))
        db.commit()
    except Exception:
        db.rollback()
        logger.debug("audio progress update skipped", exc_info=True)


def _generate_assets_locked(
    *,
    simulation_id: str,
    organization_id: str,
    db: Session,
) -> list[SimulationAudio]:
    """Generate the 2 official simulation audios:
    1. Case Overview & Summary (narrator voice)
    2. Case Argument Discussion (multi-voice hearing with distinct role voices)
    """
    sim, turns = _load(simulation_id, organization_id=organization_id, db=db)

    # Clean up previous audio rows for this simulation so only the 2 official assets exist
    db.query(SimulationAudio).filter(
        SimulationAudio.simulation_id == simulation_id
    ).delete()
    db.commit()

    # Persist pending placeholders immediately so the UI can show progress.
    pending_overview = SimulationAudio(
        id=uuid.uuid4().hex,
        simulation_id=simulation_id,
        organization_id=organization_id,
        kind="learning",
        agent_role="narrator",
        turn_number=0,
        file_name="",
        format=tts_service.file_extension(),
        size_bytes=0,
        status="pending",
        error="Queued — drafting case overview script…",
        estimated_tokens=5,
        generated_at=None,
    )
    pending_discussion = SimulationAudio(
        id=uuid.uuid4().hex,
        simulation_id=simulation_id,
        organization_id=organization_id,
        kind="discussion",
        agent_role="multi_voice",
        turn_number=1,
        file_name="",
        format=tts_service.file_extension(),
        size_bytes=0,
        status="pending",
        error="Queued — waiting for overview to finish…",
        estimated_tokens=0,
        generated_at=None,
    )
    db.add(pending_overview)
    db.add(pending_discussion)
    db.commit()

    rows: list[SimulationAudio] = []

    # -----------------------------------------------------------------------
    # 1. Case Overview & Summary (Judicial Narrator)
    # -----------------------------------------------------------------------
    _set_audio_progress(
        db, pending_overview, "1/2 Drafting case overview narration (LLM)…", 15
    )
    overview_text = extract_case_overview_text(sim, db)
    if overview_text.strip():
        try:
            _set_audio_progress(
                db,
                pending_overview,
                "1/2 Synthesizing case overview voice (edge-tts)…",
                35,
            )
            t0 = time.monotonic()
            data = tts_service.synthesize(overview_text, role="narrator")
            path = tts_service.write_audio_file(
                simulation_id=simulation_id,
                asset_name="case-overview",
                data=data,
            )
            pending_overview.file_name = path.name
            pending_overview.size_bytes = path.stat().st_size
            pending_overview.status = "ready"
            pending_overview.duration_ms = int((time.monotonic() - t0) * 1000)
            pending_overview.estimated_tokens = max(1, len(overview_text) // 4)
            pending_overview.generated_at = utcnow()
            pending_overview.error = ""
            db.commit()
            rows.append(pending_overview)
        except Exception as exc:
            pending_overview.status = "error"
            pending_overview.error = str(exc)
            db.commit()
            logger.exception("case overview TTS failed for %s", simulation_id)
    else:
        pending_overview.status = "error"
        pending_overview.error = "No overview text available"
        db.commit()

    # -----------------------------------------------------------------------
    # 2. Case Argument Discussion (Live Multi-Voice Courtroom Proceeding)
    # -----------------------------------------------------------------------
    spoken_turns: list[tuple[SimulationTurn, str]] = []
    for t in turns:
        cleaned = clean_speech_text(t.text or "", is_turn=True)
        if cleaned and len(cleaned) >= 10:  # Skip empty or trivial turns
            spoken_turns.append((t, cleaned))

    if spoken_turns:
        temp_turn_paths: list[Path] = []
        total_discussion_duration_ms = 0
        total_discussion_tokens = 0
        sv = (
            db.query(ScenarioVersion)
            .filter(ScenarioVersion.id == sim.scenario_version_id)
            .first()
        )
        case_title = sv.title if sv and sv.title else "Simulated Legal Dispute"

        total_turns = len(spoken_turns)
        _set_audio_progress(
            db,
            pending_discussion,
            f"2/2 Synthesizing courtroom turns (0/{total_turns})…",
            45,
        )
        for idx, (turn, cleaned_text) in enumerate(spoken_turns):
            role = turn.agent_role or "orchestrator"
            pct = 45 + int(50 * (idx / max(1, total_turns)))
            _set_audio_progress(
                db,
                pending_discussion,
                f"2/2 Synthesizing turn {idx + 1}/{total_turns} ({role})…",
                pct,
            )
            # Adapt the clean turn dialogue into an authentic, dramatic live courtroom oral argument!
            dramatized_speech = adapt_to_live_courtroom_speech(
                role,
                cleaned_text,
                turn_index=idx,
                total_turns=total_turns,
                phase=turn.phase or "",
                case_title=case_title,
            )
            try:
                t0 = time.monotonic()
                audio_bytes = tts_service.synthesize(dramatized_speech, role=role)
                turn_duration = int((time.monotonic() - t0) * 1000)
                total_discussion_duration_ms += turn_duration
                total_discussion_tokens += max(1, len(dramatized_speech) // 4)

                # Write intermediate turn audio file
                p = tts_service.write_audio_file(
                    simulation_id=simulation_id,
                    asset_name=f"_temp_turn_{turn.turn_number:02d}_{role}",
                    data=audio_bytes,
                )
                temp_turn_paths.append(p)
            except Exception as exc:
                import sys

                if not sys.is_finalizing():
                    logger.warning(
                        "Failed to synthesize turn %s role %s: %s",
                        turn.turn_number,
                        role,
                        exc,
                    )

        if temp_turn_paths:
            ext = tts_service.file_extension()
            target_file_name = f"argument-discussion.{ext}"
            discussion_path = (
                tts_service.ensure_data_dir() / simulation_id / target_file_name
            )

            _set_audio_progress(
                db, pending_discussion, "2/2 Concatenating multi-voice hearing…", 95
            )

            # Generate natural 0.5s pause between speaker turns
            pause_path = tts_service.ensure_data_dir() / simulation_id / f"_pause.{ext}"
            has_pause = False
            ffmpeg_bin = shutil.which("ffmpeg") or (
                "/opt/homebrew/bin/ffmpeg"
                if Path("/opt/homebrew/bin/ffmpeg").exists()
                else None
            )
            if ffmpeg_bin:
                try:
                    cmd = [
                        ffmpeg_bin,
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        "anullsrc=r=24000:cl=mono",
                        "-t",
                        "0.5",
                        "-c:a",
                        "libmp3lame",
                        "-b:a",
                        "48k",
                        str(pause_path),
                    ]
                    res = subprocess.run(cmd, capture_output=True, check=False)
                    if res.returncode == 0 and pause_path.exists():
                        has_pause = True
                except Exception:
                    has_pause = False

            concat_sequence: list[Path] = []
            for idx, tp in enumerate(temp_turn_paths):
                concat_sequence.append(tp)
                if has_pause and idx < len(temp_turn_paths) - 1:
                    concat_sequence.append(pause_path)

            try:
                _concat_audio_files(concat_sequence, discussion_path)

                # Always upsert a fresh ready row — pending placeholders may have
                # been deleted by a superseded job / session expiry.
                db.query(SimulationAudio).filter(
                    SimulationAudio.simulation_id == simulation_id,
                    SimulationAudio.kind == "discussion",
                ).delete()
                discussion_row = SimulationAudio(
                    id=uuid.uuid4().hex,
                    simulation_id=simulation_id,
                    organization_id=organization_id,
                    kind="discussion",
                    agent_role="multi_voice",
                    turn_number=1,
                    file_name=target_file_name,
                    format=ext,
                    size_bytes=discussion_path.stat().st_size
                    if discussion_path.exists()
                    else 0,
                    status="ready",
                    error="",
                    duration_ms=total_discussion_duration_ms,
                    estimated_tokens=total_discussion_tokens,
                    generated_at=utcnow(),
                )
                db.add(discussion_row)
                db.commit()
                rows.append(discussion_row)
            except Exception as exc:
                import sys

                if not sys.is_finalizing():
                    logger.error("Failed to concatenate discussion audio: %s", exc)
                try:
                    pending_discussion.status = "error"
                    pending_discussion.error = str(exc)
                    db.commit()
                except Exception:
                    db.rollback()
                    err_row = SimulationAudio(
                        id=uuid.uuid4().hex,
                        simulation_id=simulation_id,
                        organization_id=organization_id,
                        kind="discussion",
                        agent_role="multi_voice",
                        turn_number=1,
                        file_name="",
                        format=ext if "ext" in locals() else tts_service.file_extension(),
                        size_bytes=0,
                        status="error",
                        error=str(exc),
                        generated_at=None,
                    )
                    db.add(err_row)
                    db.commit()
            finally:
                # Clean up intermediate turn files & pause file
                for tp in temp_turn_paths:
                    tp.unlink(missing_ok=True)
                pause_path.unlink(missing_ok=True)
        else:
            pending_discussion.status = "error"
            pending_discussion.error = "No turn audio segments could be synthesized"
            db.commit()
    else:
        pending_discussion.status = "error"
        pending_discussion.error = "No spoken turns available"
        db.commit()

    return rows


def generate_assets_job(simulation_id: str, organization_id: str) -> None:
    """Queue-friendly entrypoint: opens its own session, generates, closes."""
    db = SessionLocal()
    try:
        generate_assets(
            simulation_id=simulation_id, organization_id=organization_id, db=db
        )
    finally:
        db.close()


def list_assets(
    *, simulation_id: str, organization_id: str, db: Session
) -> list[SimulationAudio]:
    _load(simulation_id, organization_id=organization_id, db=db)
    rows = (
        db.query(SimulationAudio)
        .filter(SimulationAudio.simulation_id == simulation_id)
        .order_by(SimulationAudio.turn_number, SimulationAudio.kind)
        .all()
    )

    # Automatic persistence recovery: if files exist on disk, ensure DB records are present
    sim_dir = tts_service.ensure_data_dir() / simulation_id
    if sim_dir.exists():
        existing_files = {r.file_name for r in rows if r.file_name}
        overview_file = sim_dir / "case-overview.mp3"
        discussion_file = sim_dir / "argument-discussion.mp3"

        added = False
        if overview_file.exists() and "case-overview.mp3" not in existing_files:
            # Drop stale pending placeholder for this kind
            for r in list(rows):
                if r.kind in ("learning", "overview", "run") and r.status == "pending":
                    db.delete(r)
                    rows.remove(r)
            o_row = SimulationAudio(
                id=uuid.uuid4().hex,
                simulation_id=simulation_id,
                organization_id=organization_id,
                kind="learning",
                agent_role="narrator",
                turn_number=0,
                file_name="case-overview.mp3",
                format="mp3",
                size_bytes=overview_file.stat().st_size,
                status="ready",
                error="",
                duration_ms=45000,
                estimated_tokens=300,
                generated_at=utcnow(),
            )
            db.add(o_row)
            rows.append(o_row)
            added = True

        if discussion_file.exists() and "argument-discussion.mp3" not in existing_files:
            for r in list(rows):
                if r.kind == "discussion" and r.status == "pending":
                    db.delete(r)
                    rows.remove(r)
            d_row = SimulationAudio(
                id=uuid.uuid4().hex,
                simulation_id=simulation_id,
                organization_id=organization_id,
                kind="discussion",
                agent_role="multi_voice",
                turn_number=1,
                file_name="argument-discussion.mp3",
                format="mp3",
                size_bytes=discussion_file.stat().st_size,
                status="ready",
                error="",
                duration_ms=75000,
                estimated_tokens=600,
                generated_at=utcnow(),
            )
            db.add(d_row)
            rows.append(d_row)
            added = True

        if added:
            try:
                db.commit()
            except Exception:
                db.rollback()

    # Dead pending with no worker and no files → restart synthesis.
    _ensure_generation_running(
        simulation_id=simulation_id,
        organization_id=organization_id,
        db=db,
        rows=rows,
    )
    # Re-read after possible requeue status updates
    rows = (
        db.query(SimulationAudio)
        .filter(SimulationAudio.simulation_id == simulation_id)
        .order_by(SimulationAudio.turn_number, SimulationAudio.kind)
        .all()
    )
    return rows


def asset_dict(row: SimulationAudio) -> dict:
    is_overview = row.kind in ("learning", "overview", "run")
    title = (
        "1. Case Overview & Executive Summary"
        if is_overview
        else "2. Live Courtroom Hearing & Oral Argument (Multi-Voice)"
    )
    description = (
        "Comprehensive, end-to-end spoken analysis of dispute background, factual record, legal claims, and judicial determination."
        if is_overview
        else "Immersive live tribunal proceeding featuring courtroom opening announcements, rhetorical advocate arguments, and commanding bench rulings."
    )
    pending = row.status == "pending"
    progress = (row.error or "").strip() if pending else ""
    return {
        "id": row.id,
        "simulation_id": row.simulation_id,
        "kind": row.kind,
        "agent_role": row.agent_role,
        "turn_number": row.turn_number,
        "file_name": row.file_name,
        "format": row.format,
        "size_bytes": row.size_bytes,
        "status": row.status,
        "error": "" if pending else (row.error or ""),
        "progress": progress,
        "progress_pct": int(row.estimated_tokens or 0) if pending else None,
        "duration_ms": row.duration_ms,
        "estimated_tokens": row.estimated_tokens,
        "title": title,
        "description": description,
        "url": f"/media/{row.simulation_id}/{row.file_name}"
        if row.status == "ready" and row.file_name
        else None,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
    }
