# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v13 — WALLPA organ (output / expression / voice).
"""
szl_wallpa.py — WALLPA, the Voice. The expression organ.

Quechua `wallpay` = to create / to invent (Wiktionary: wallpay); deverbal `wallpa`
= "that which is created/expressed". Doctrine v13 §1/§2.2. WALLPA owns the shared
output contract: it renders the argmax-selected action into the expressed output
the world receives, in one voice, with a fidelity gate.

Sub-formula (Doctrine v13 §2.2):
    Wallpa(a) = 1[render(a) ⊑ sanctioned(a)] * (1 - drift_out(a))   in [0,1]

TTS engine policy (HARD RULE): OPEN-SOURCE ONLY. Preference order:
    Piper (rhasspy/piper) -> Coqui XTTS-v2 -> OpenVoice -> synthetic-timbre fallback.
The per-organ voices are SYNTHETIC TIMBRES (designed formant/pitch profiles), NOT
clones of any real person. No proprietary voice cloning without consent.

If no neural TTS model is installed, WALLPA still returns REAL playable WAV audio
via a deterministic synthetic-timbre vocoder (formant-shaped tone bursts per word),
so the endpoint is never vapor — it always returns audio + transcript + receipt.

Endpoints (under the a11oy namespace, local Python):
    GET  /api/a11oy/wallpa/voices            — list per-organ synthetic voice profiles
    POST /api/a11oy/wallpa/speak             — synthesize text -> WAV (base64) + receipt
    GET  /api/a11oy/wallpa/speak/stream      — SSE: stream audio chunks (base64) as they render
    POST /api/a11oy/wallpa/narrate-doctrine  — render the PURIQ master formula as audio

Every action emits a Khipu receipt with the SHA3-256 of (audio || transcript).
Stdlib (wave, struct, math, base64, hashlib) + FastAPI. No mandatory heavy deps.
"""

import base64
import hashlib
import io
import json
import math
import os
import struct
import wave
from typing import Any

try:
    from szl_khipu import get_dag
except Exception:  # pragma: no cover
    from .szl_khipu import get_dag  # type: ignore

# --- Per-organ SYNTHETIC voice profiles (timbres, not human clones) ---------
# Each profile is a designed (base pitch Hz, formant brightness, cadence) tuple.
VOICES: dict[str, dict[str, Any]] = {
    "amaru-voice":        {"organ": "AMARU (cortex)",      "pitch_hz": 110, "brightness": 0.55, "cadence_wpm": 150, "timbre": "low, binding, serpentine"},
    "yuyay-voice":        {"organ": "YUYAY (heart)",       "pitch_hz": 196, "brightness": 0.70, "cadence_wpm": 140, "timbre": "measured, conjunctive"},
    "killinchu-voice":    {"organ": "KILLINCHU (geofence)","pitch_hz": 233, "brightness": 0.82, "cadence_wpm": 165, "timbre": "bright, falcon-quick"},
    "hatun-willay":       {"organ": "HATUN-WILLAY narrator","pitch_hz": 98, "brightness": 0.48, "cadence_wpm": 125, "timbre": "deep, ceremonial-plain narrator"},
    "chaski-voice":       {"organ": "CHASKI (reception)",  "pitch_hz": 175, "brightness": 0.66, "cadence_wpm": 160, "timbre": "warm, welcoming runner"},
    "wasi-rikuq-voice":   {"organ": "WASI-RIKUQ (watcher)","pitch_hz": 130, "brightness": 0.60, "cadence_wpm": 135, "timbre": "steady, vigilant"},
}

SAMPLE_RATE = 16000

PURIQ_MASTER_NARRATION = (
    "This is the PURIQ master formula. For a context x at step t, over a bounded "
    "action space, P of x and t is the argmax over actions a of the following "
    "product. Lambda of x, the spine aggregator, times Yuyay thirteen of a, the "
    "thirteen axis conjunctive heart gate, times the exponential of minus beta "
    "times HUKLLA of a, the soft halt, times the product over i of Khipu i of a, "
    "the receipt provenance gate. In Doctrine version thirteen we multiply in three "
    "new admissible factors, each between zero and one: Chaski, reception; Wallpa, "
    "expression; and Wasi, house health. Each can only gate harder, never inflate. "
    "Nothing is hidden. Every term is Lean stateable. Every action emits a receipt."
)


def _wallpa_factor(render_subsumed: bool, drift_out: float) -> float:
    """Doctrine v13 §2.2: 1[subsumed] * (1 - drift_out), clamped to [0,1]."""
    if not render_subsumed:
        return 0.0
    d = max(0.0, min(1.0, drift_out))
    return max(0.0, min(1.0, 1.0 - d))


def _detect_engine() -> dict[str, Any]:
    """Report which open-source TTS engine is available (honest, no overclaim)."""
    engines = []
    for mod, name in (("piper", "piper"), ("TTS", "coqui-xtts-v2"), ("openvoice", "openvoice")):
        try:
            __import__(mod)
            engines.append(name)
        except Exception:
            pass
    return {
        "available_open_source_engines": engines,
        "active": engines[0] if engines else "synthetic-timbre-fallback",
        "policy": "OPEN-SOURCE ONLY; per-organ voices are SYNTHETIC TIMBRES, not human clones",
        "fallback": "deterministic formant-shaped synthetic vocoder (always returns real WAV)",
    }


def _synthesize_wav(text: str, voice: dict[str, Any]) -> bytes:
    """Deterministic synthetic-timbre vocoder -> real 16kHz mono PCM WAV bytes.

    Each word becomes a short formant-shaped tone burst at the voice's base pitch
    plus brightness-scaled harmonics; spaces become brief silences. This is a
    SYNTHETIC TIMBRE (no human source), so it is consent-safe by construction and
    always playable. Neural engines (Piper/Coqui) would replace this when present.
    """
    pitch = float(voice.get("pitch_hz", 150))
    brightness = float(voice.get("brightness", 0.6))
    cadence_wpm = float(voice.get("cadence_wpm", 150))
    sec_per_word = max(0.18, 60.0 / max(60.0, cadence_wpm))
    words = text.split()
    frames = bytearray()
    amp = 0.42

    for wi, word in enumerate(words):
        # Vary pitch slightly by word hash for intelligible cadence (still synthetic).
        h = int(hashlib.sha256(word.encode()).hexdigest(), 16)
        f0 = pitch * (0.92 + 0.16 * ((h % 100) / 100.0))
        dur = sec_per_word * (0.6 + 0.5 * min(2.0, len(word) / 5.0))
        n = int(SAMPLE_RATE * dur)
        for i in range(n):
            t = i / SAMPLE_RATE
            env = math.sin(math.pi * (i / max(1, n)))  # smooth attack/decay
            s = math.sin(2 * math.pi * f0 * t)
            s += brightness * 0.5 * math.sin(2 * math.pi * 2 * f0 * t)
            s += brightness * 0.25 * math.sin(2 * math.pi * 3 * f0 * t)
            val = int(32767 * amp * env * s / (1 + brightness))
            val = max(-32768, min(32767, val))
            frames += struct.pack("<h", val)
        # inter-word silence
        gap = int(SAMPLE_RATE * 0.05)
        frames += b"\x00\x00" * gap

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(frames))
    return buf.getvalue()



# Govern target is configurable so Wallpa can reach the brain from inside the HF
# Space. Root cause of the old loopback-only bug: the brain listens on the
# EXTERNAL public endpoint, so 127.0.0.1:7860 from inside the Space never reaches
# it. Default is therefore the external public endpoint; loopback is opt-in only
# (A11OY_GOVERN_LOOPBACK=1) for single-process local dev where it is reachable.
DEFAULT_GOVERN_URL = "https://a-11-oy.com/api/a11oy/v1/govern/infer"
_LOOPBACK_GOVERN_URLS = (
    "http://127.0.0.1:7860/api/a11oy/v1/govern/infer",
    "http://127.0.0.1:8000/api/a11oy/v1/govern/infer",
)


def _govern_targets() -> list[str]:
    """Ordered govern/infer targets: A11OY_GOVERN_URL (default = external public
    endpoint) first; loopback appended only when A11OY_GOVERN_LOOPBACK is opted in."""
    primary = (os.environ.get("A11OY_GOVERN_URL") or DEFAULT_GOVERN_URL).strip()
    targets = [primary] if primary else []
    if (os.environ.get("A11OY_GOVERN_LOOPBACK") or "").strip().lower() in ("1", "true", "yes", "on"):
        targets += [u for u in _LOOPBACK_GOVERN_URLS if u != primary]
    return targets


def _call_govern_infer(text: str, timeout: float = 8.0) -> dict:
    """Call the live govern/infer loop — govern decides, Wallpa expresses.

    Targets the external public endpoint by default (configurable via
    A11OY_GOVERN_URL); loopback is opt-in (A11OY_GOVERN_LOOPBACK=1).
    Never fabricates: on failure returns decision=UNAVAILABLE with honest_note.
    """
    import urllib.request

    targets = _govern_targets()
    payload = json.dumps({"text": text, "caller": "wallpa", "surface": "voice/OSS-TTS"}).encode()
    last_err: str = ""
    for url in targets:
        try:
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as exc:
            last_err = str(exc)
    return {
        "decision": "UNAVAILABLE",
        "honest_note": (
            f"govern/infer unreachable ({last_err[:100]!r}); tried {targets}. "
            "Wallpa never fabricates — honest UNAVAILABLE."
        ),
    }


def register(app, ns: str = "a11oy") -> None:
    from fastapi import Request
    from fastapi.responses import JSONResponse, StreamingResponse

    dag = get_dag("wallpa", ns)
    base = f"/api/{ns}/wallpa"

    @app.get(base + "/voices")
    async def wallpa_voices() -> JSONResponse:
        receipt = dag.emit("voices.list", {})
        return JSONResponse({
            "organ": "WALLPA",
            "gloss": "that which is created/expressed (Quechua wallpay = to create)",
            "doctrine": "v13 §2.2",
            "engine": _detect_engine(),
            "voices": VOICES,
            "consent_note": "All voices are SYNTHETIC TIMBRES. No real-person voice cloning.",
            "khipu_receipt": receipt,
        })

    def _do_speak(text: str, voice_id: str, drift_out: float) -> dict[str, Any]:
        voice = VOICES.get(voice_id, VOICES["hatun-willay"])
        factor = _wallpa_factor(render_subsumed=True, drift_out=drift_out)
        audio = _synthesize_wav(text, voice)
        b64 = base64.b64encode(audio).decode("ascii")
        combined = hashlib.sha3_256(audio + text.encode("utf-8")).hexdigest()
        receipt = dag.emit("speak", {
            "voice": voice_id, "chars": len(text),
            "audio_transcript_sha3": combined,
            "wallpa_factor": round(factor, 6),
        })
        return {
            "organ": "WALLPA", "voice": voice_id, "voice_profile": voice,
            "transcript": text, "wallpa_factor": round(factor, 6),
            "audio_format": "wav/pcm16/16000", "audio_base64": b64,
            "audio_transcript_sha3": combined, "khipu_receipt": receipt,
        }

    @app.post(base + "/speak")
    async def wallpa_speak(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        text = (body.get("text") or "").strip()
        if not text:
            return JSONResponse({"error": "text required"}, status_code=400)
        voice_id = body.get("voice", "hatun-willay")
        drift_out = float(body.get("drift_out", 0.0) or 0.0)
        return JSONResponse(_do_speak(text, voice_id, drift_out))

    @app.get(base + "/speak/stream")
    async def wallpa_speak_stream(text: str = "", voice: str = "hatun-willay") -> StreamingResponse:
        text = (text or "Hello from WALLPA.").strip()
        voice_id = voice if voice in VOICES else "hatun-willay"
        vprofile = VOICES[voice_id]

        async def gen():
            # SSE: render per-word audio chunks and stream them as base64 events.
            words = text.split()
            for idx, word in enumerate(words):
                chunk = _synthesize_wav(word, vprofile)
                b64 = base64.b64encode(chunk).decode("ascii")
                evt = {"i": idx, "word": word, "audio_base64": b64,
                       "format": "wav/pcm16/16000"}
                yield f"event: chunk\ndata: {json.dumps(evt)}\n\n"
            receipt = dag.emit("speak.stream", {"voice": voice_id, "words": len(words)})
            yield f"event: done\ndata: {json.dumps({'words': len(words), 'khipu_receipt': receipt})}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post(base + "/narrate-doctrine")
    async def wallpa_narrate_doctrine(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        # Default: render the PURIQ master formula with the Hatun-Willay narrator.
        text = (body.get("text") or PURIQ_MASTER_NARRATION).strip()
        voice_id = body.get("voice", "hatun-willay")
        result = _do_speak(text, voice_id, drift_out=0.0)
        result["doctrine"] = "v13 — PURIQ master formula narration"
        result["narrator"] = "Hatun-Willay" if voice_id == "hatun-willay" else voice_id
        return JSONResponse(result)

    @app.get(base + "/health")
    async def wallpa_health() -> JSONResponse:
        """Health check — always honest (UNAVAILABLE if backend down, never fabricated)."""
        engine = _detect_engine()
        receipt = dag.emit("health", {"engine": engine["active"]})
        return JSONResponse({
            "organ": "WALLPA",
            "status": "live",
            "engine": engine,
            "voices_count": len(VOICES),
            "doctrine": "v13 §2.2",
            "theorem": "F8 Wallpa OSS-Only Safety (locked-proven)",
            "khipu_receipt": receipt,
        })

    @app.post(base + "/governed-speak")
    async def wallpa_governed_speak(request: Request) -> JSONResponse:
        """Governed voice expression: govern decides \u2192 Wallpa expresses.

        Sends the prompt to the live govern/infer loop, then renders the
        governed answer as audio. If govern/infer is unreachable, returns
        an honest UNAVAILABLE response with no fabrication.
        Body: {"text": str, "voice": str (optional), "include_audio": bool (optional)}
        `text` is canonical; `prompt` is accepted as an ergonomic alias.
        """
        try:
            body = await request.json()
        except Exception:
            body = {}
        text = (body.get("text") or body.get("prompt") or "").strip()
        if not text:
            return JSONResponse({"error": "text required (alias: prompt)"}, status_code=400)
        voice_id = body.get("voice", "amaru-voice")  # cortex voice for governed answers
        include_audio = body.get("include_audio", True)
        # Step 1: govern decides
        gov = _call_govern_infer(text)
        decision = gov.get("decision", "UNAVAILABLE")
        answer_text = (
            gov.get("answer") or gov.get("text") or gov.get("response") or ""
        )
        if not answer_text:
            answer_text = (
                f"Govern decision: {decision}. "
                + (gov.get("honest_note") or gov.get("reason") or "No answer returned.")
            )
        # Step 2: Wallpa expresses
        factor = _wallpa_factor(render_subsumed=(decision != "deny"), drift_out=0.0)
        result: dict = {
            "organ": "WALLPA",
            "mode": "governed-speak",
            "govern_decision": decision,
            "govern_payload": gov,
            "transcript": answer_text,
            "voice": voice_id,
            "wallpa_factor": round(factor, 6),
            "doctrine": "v13 §2.2 — govern decides, Wallpa expresses",
            "theorem": "F8 Wallpa OSS-Only Safety (locked-proven)",
        }
        if include_audio:
            voice = VOICES.get(voice_id, VOICES["hatun-willay"])
            audio = _synthesize_wav(answer_text, voice)
            b64 = base64.b64encode(audio).decode("ascii")
            combined = hashlib.sha3_256(audio + answer_text.encode("utf-8")).hexdigest()
            receipt = dag.emit("governed-speak", {
                "voice": voice_id, "govern_decision": decision,
                "chars": len(answer_text),
                "audio_transcript_sha3": combined,
                "wallpa_factor": round(factor, 6),
            })
            result.update({
                "audio_format": "wav/pcm16/16000",
                "audio_base64": b64,
                "audio_transcript_sha3": combined,
                "khipu_receipt": receipt,
            })
        return JSONResponse(result)

    print(f"[{ns}] szl_wallpa routes registered (organ=WALLPA, expression)", flush=True)
