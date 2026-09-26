"""Text-to-speech engine for simulation audio (PRD §8.4-ish: "folio →
voice").

Supported providers (``JAIL_TTS_PROVIDER``):
  * ``edge``  – Microsoft Edge neural voices (online). Produces MP3, distinct
    voice per agent role, several narrator variants. Requires ``edge-tts``.
  * ``macos`` – local ``say`` via macOS Speech framework. Offline, but
    produces AIFF only and accepts a subset of voice names.
  * ``none``  – disable synthesis (rows are recorded but no audio is written).

All heavy providers are imported lazily so app startup (and tests) never pay
for their import cost.  Audio is generated to ``settings.tts_data_dir`` and
served back through a static mount (``/media``).
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Voice selection
# ---------------------------------------------------------------------------

# Default role -> voice map. Keys are agent roles from SIM_AGENTS plus two
# synthetic roles used at render time (narrator/plaintiff/… keys are lowercased
# and de-underscored in ``role_for_voice``).
# edge-tts ships with a fixed set of neural voices; we pick audibly-distinct
# voices by pitch/gender/region so the role-play actually sounds multi-actor.
EDGE_VOICE_BY_ROLE = {
    "orchestrator": "en-US-BrianNeural",  # crisp, formal male court crier / bailiff
    "plaintiff": "en-US-AriaNeural",  # expressive, passionate, urgent female advocate
    "defendant": "en-US-GuyNeural",  # sharp, analytical, skeptical male defense counsel
    "judge": "en-US-ChristopherNeural",  # commanding, deep judicial bench authority
    "informer": "en-US-RogerNeural",  # older, distinguished expert advisor
    "witness": "en-GB-SoniaNeural",  # distinct British female witness
    "narrator": "en-US-AndrewNeural",  # smooth, articulate executive case narrator
}

# macOS ``say`` looks up voices by exact name; fall back by same gender/region.
MACOS_VOICE_BY_ROLE = {
    "orchestrator": "Daniel",
    "plaintiff": "Samantha",
    "defendant": "Alex",
    "judge": "Karen",
    "informer": "Fred",
    "witness": "Moira",
    "narrator": "Samantha",
}


# Normalize an agent role string ("informer_2", "judge_questions", …) into a
# stable voice key so every distinct participating agent gets its own voice.
def role_for_voice(role: str) -> str:
    key = (role or "").strip().lower().replace("_", "").replace("-", "")
    # Strip trailing numeric suffixes ("informer" from "informer_2").
    key = "".join(ch for ch in key if not ch.isdigit())
    return key or "orchestrator"


def _parse_voice_overrides(raw: str | None) -> dict[str, str]:
    if not raw or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items()}
    except Exception as exc:
        logger.warning("failed to parse tts_voices JSON (%r): %s", raw, exc)
    return {}


def _edge_voice(role: str, overrides: dict[str, str] | None) -> str:
    if overrides and role_for_voice(role) in overrides:
        return overrides[role_for_voice(role)]
    return EDGE_VOICE_BY_ROLE.get(role_for_voice(role), "en-US-GuyNeural")


def _macos_voice(role: str, overrides: dict[str, str] | None) -> str:
    if overrides and role_for_voice(role) in overrides:
        return overrides[role_for_voice(role)]
    return MACOS_VOICE_BY_ROLE.get(role_for_voice(role), "Alex")


# Role-specific emotional prosody and vocal dynamics (pitch and rate).
# Injects authentic courtroom emotion:
# - Plaintiff: assertive, urgent, pressing argument (+8% rate, +10Hz pitch)
# - Defendant: measured, analytical, deliberate defense pushback (-4% rate, -6Hz pitch)
# - Judge: commanding, authoritative, deliberate bench presence (-8% rate, -12Hz pitch)
# - Informer: calm, professorial regulatory advisor (-3% rate, -5Hz pitch)
# - Witness: earnest, responsive testimony (+4% rate, +8Hz pitch)
# - Orchestrator: formal courtroom bailiff / call to order (-2% rate, -4Hz pitch)
# - Narrator: clear, engaging, steady executive briefing (+1% rate, +0Hz pitch)
ROLE_PROSODY = {
    "plaintiff": {"rate": "+8%", "pitch": "+10Hz"},
    "defendant": {"rate": "-4%", "pitch": "-6Hz"},
    "judge": {"rate": "-8%", "pitch": "-12Hz"},
    "informer": {"rate": "-3%", "pitch": "-5Hz"},
    "witness": {"rate": "+4%", "pitch": "+8Hz"},
    "orchestrator": {"rate": "-2%", "pitch": "-4Hz"},
    "narrator": {"rate": "+1%", "pitch": "+0Hz"},
}


class TTSError(RuntimeError):
    """Raised when the configured provider cannot synthesize audio."""


# ---------------------------------------------------------------------------
# Provider implementations (lazily imported)
# ---------------------------------------------------------------------------


def _synthesize_edge(
    text: str, voice: str, rate: str = "+0%", pitch: str = "+0Hz"
) -> bytes:
    import edge_tts

    async def _run() -> bytes:
        communicate = edge_tts.Communicate(
            text.strip(), voice=voice, rate=rate, pitch=pitch
        )
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                data_bytes = chunk.get("data")
                if isinstance(data_bytes, (bytes, bytearray)):
                    buf.write(data_bytes)
        return buf.getvalue()

    import sys

    if sys.is_finalizing():
        raise TTSError("Interpreter shutdown in progress")

    try:
        data = asyncio.run(_run())
    except Exception as exc:  # network / voice-not-found
        if sys.is_finalizing():
            raise TTSError("Interpreter shutdown in progress") from exc
        raise TTSError(f"edge-tts synthesis failed: {exc}") from exc
    if not data:
        raise TTSError(f"edge-tts returned no audio for voice {voice!r}")
    return data


def _aiff_to_mp3(aiff_bytes: bytes) -> bytes:
    ffmpeg_bin = shutil.which("ffmpeg") or (
        "/opt/homebrew/bin/ffmpeg"
        if Path("/opt/homebrew/bin/ffmpeg").exists()
        else None
    )
    if not ffmpeg_bin:
        return aiff_bytes
    with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as in_f:
        in_path = Path(in_f.name)
        in_path.write_bytes(aiff_bytes)
    out_path = in_path.with_suffix(".mp3")
    try:
        proc = subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-i",
                str(in_path),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "128k",
                str(out_path),
            ],
            capture_output=True,
            timeout=30,
            check=False,
        )
        if proc.returncode == 0 and out_path.exists():
            return out_path.read_bytes()
        return aiff_bytes
    finally:
        in_path.unlink(missing_ok=True)
        out_path.unlink(missing_ok=True)


def _synthesize_macos(text: str, voice: str, target_format: str = "aiff") -> bytes:
    if shutil.which("say") is None:
        raise TTSError("macOS 'say' is not available on this host")
    with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        proc = subprocess.run(
            ["say", "-v", voice, "-o", str(tmp_path), text.strip()],
            capture_output=True,
            timeout=90,
            check=False,
        )
        if proc.returncode != 0:
            raise TTSError(
                f"'say' failed ({proc.returncode}): {proc.stderr.decode(errors='replace')}"
            )
        data = tmp_path.read_bytes()
        if not data:
            raise TTSError(f"'say' produced no audio for voice {voice!r}")
        if target_format == "mp3":
            return _aiff_to_mp3(data)
        return data
    except subprocess.TimeoutExpired as exc:
        raise TTSError(f"'say' timed out: {exc}") from exc
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_enabled() -> bool:
    settings = get_settings()
    return settings.tts_enabled and settings.tts_provider not in ("", "none")


def synthesize(
    text: str,
    *,
    role: str = "narrator",
    voices: dict[str, str] | None = None,
) -> bytes:
    """Synthesize ``text`` to raw audio bytes for the given agent role.

    Returned container depends on the provider (mp3 for ``edge``, AIFF for
    ``macos``).  Raises :class:`TTSError` when the provider is unavailable or
    returns no audio (e.g. provider === "none").
    """
    settings = get_settings()
    if not text or not text.strip():
        raise TTSError("refusing to synthesize empty text")
    if not is_enabled():
        raise TTSError("tts is disabled (JAIL_TTS_ENABLED=false)")
    provider = settings.tts_provider
    voice_map = _parse_voice_overrides(settings.tts_voices)
    voice_overrides: dict[str, str] = {**voice_map, **(voices or {})}
    key = role_for_voice(role)
    prosody = ROLE_PROSODY.get(key, {"rate": "+0%", "pitch": "+0Hz"})
    if provider == "edge":
        try:
            return _synthesize_edge(
                text,
                _edge_voice(role, voice_overrides),
                rate=prosody.get("rate", "+0%"),
                pitch=prosody.get("pitch", "+0Hz"),
            )
        except TTSError as exc:
            if shutil.which("say") is not None:
                logger.warning("edge-tts failed (%s), falling back to macOS say", exc)
                return _synthesize_macos(
                    text, _macos_voice(role, voice_overrides), target_format="mp3"
                )
            raise
    if provider == "macos":
        return _synthesize_macos(text, _macos_voice(role, voice_overrides))
    raise TTSError(f"unsupported tts provider {provider!r}")


def file_extension(provider: str | None = None) -> str:
    settings = get_settings()
    provider = provider or settings.tts_provider
    return "aiff" if provider == "macos" else "mp3"


def ensure_data_dir() -> Path:
    settings = get_settings()
    path = Path(settings.tts_data_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_audio_file(
    *, simulation_id: str, asset_name: str, data: bytes, provider: str | None = None
) -> Path:
    """Persist raw audio bytes into ``tts_data_dir/<simulation_id>/``.

    Returns the written file path.  Existing file of the same asset name is
    overwritten (regeneration).
    """
    ext = file_extension(provider)
    base = ensure_data_dir() / simulation_id
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{asset_name}.{ext}"
    path.write_bytes(data)
    import sys

    if not sys.is_finalizing():
        logger.info("tts wrote %s (%d bytes)", path, len(data))
    return path


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
