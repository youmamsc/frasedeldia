"""Produce four multilingual pilot MP3s, with native pronunciation.

No credentials, paid APIs, Spotify delivery, or MAC FM resources are used.
Edge's public speech endpoint is not an SLA-backed API. An explicit eSpeak
fallback lets listeners detect service outages rather than lose the run.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydub import AudioSegment, effects
from pydub.generators import Sine

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "episodes" / "pilots.json"
OUTPUT = ROOT / "output"
VOICES = {
    "en": "en-GB-RyanNeural",
    "fr": "fr-FR-HenriNeural",
    "it": "it-IT-DiegoNeural",
    "es": "es-ES-AlvaroNeural",
}
FALLBACK_VOICES = {
    "en": "en-gb",
    "fr": "fr",
    "it": "it",
    "es": "es",
}
SILENCE = AudioSegment.silent(duration=250)


def clip_from_espeak(text: str, lang: str, slow: bool) -> AudioSegment:
    command = ["espeak", "-v", FALLBACK_VOICES[lang], "-s", "122" if slow else "155",
               "-a", "160", "--stdout", text]
    completed = subprocess.run(command, check=True, capture_output=True)
    return AudioSegment.from_file(io.BytesIO(completed.stdout), format="wav")


async def clip_from_edge(text: str, lang: str, slow: bool) -> AudioSegment:
    import edge_tts

    rate = "-22%" if slow else "+2%"
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "segment.mp3"
        speech = edge_tts.Communicate(text, voice=VOICES[lang], rate=rate)
        await speech.save(str(path))
        if path.stat().st_size < 100:
            raise RuntimeError("TTS returned an empty segment")
        return AudioSegment.from_file(path, format="mp3")


def sting() -> AudioSegment:
    """An original, simple two-note identification sound (no sampled music)."""
    a = Sine(523).to_audio_segment(duration=130).fade_in(15).fade_out(50)
    b = Sine(784).to_audio_segment(duration=180).fade_in(15).fade_out(90)
    return (a + AudioSegment.silent(duration=30) + b).apply_gain(-16)


def resolve_lang(episode_lang: str, voice: str) -> tuple[str, bool]:
    if voice in ("spanish", "spanish_slow"):
        return "es", voice.endswith("_slow")
    if voice in ("english", "english_slow"):
        return "en", voice.endswith("_slow")
    if voice != "narrator":
        raise ValueError(f"Unknown voice role: {voice}")
    return episode_lang, False


async def run() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "generation_mode": "GitHub Actions pilot: no Telegram / Spotify",
        "episodes": [],
    }
    # This can be forced locally with PILOT_TTS_BACKEND=espeak.
    edge_available = os.getenv("PILOT_TTS_BACKEND", "edge").lower() != "espeak"
    for episode in data["episodes"]:
        language = episode["id"]
        print(f"Producing {language}: {episode['title']}", flush=True)
        chunks = [AudioSegment.silent(duration=130), sting(),
                  AudioSegment.silent(duration=200)]
        engines = set()
        for i, segment in enumerate(episode["segments"], 1):
            lang, slow = resolve_lang(language, segment["voice"])
            if edge_available:
                try:
                    clip = await clip_from_edge(segment["text"], lang, slow)
                    engines.add("edge-tts")
                except Exception as exc:
                    edge_available = False
                    print(f"WARNING: neural TTS failed ({type(exc).__name__}: {exc}); "
                          "using low-quality offline eSpeak fallback.", flush=True)
                    clip = clip_from_espeak(segment["text"], lang, slow)
                    engines.add("espeak-fallback")
            else:
                clip = clip_from_espeak(segment["text"], lang, slow)
                engines.add("espeak-fallback")
            chunks.append(clip)
            pause = int(segment.get("pause_ms", 125))
            chunks.append(AudioSegment.silent(duration=pause))
            print(f"  {i:02d}/{len(episode['segments'])}: "
                  f"{segment['voice']} ({len(clip)}ms)", flush=True)
        chunks += [AudioSegment.silent(duration=120), sting()]
        combined = AudioSegment.empty()
        for chunk in chunks:
            combined += chunk
        combined = effects.normalize(combined, headroom=2.0)
        combined = combined.set_channels(2).set_frame_rate(44100)
        out = OUTPUT / episode["filename"]
        combined.export(out, format="mp3", bitrate="160k",
                        tags={"title": episode["title"], "artist": "Frase del Día",
                              "album": "Podcast Pilots", "genre": "Podcast"})
        duration_sec = round(len(combined) / 1000, 1)
        print(f"  -> {out.name}: {duration_sec}s / {out.stat().st_size} bytes",
              flush=True)
        manifest["episodes"].append({
            "lang": language, "title": episode["title"], "filename": out.name,
            "seconds": duration_sec, "voice_engines": sorted(engines),
            "bytes": out.stat().st_size,
        })
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not edge_available:
        print("WARNING: Some/all segments used eSpeak. See manifest.json.",
              flush=True)


if __name__ == "__main__":
    asyncio.run(run())
