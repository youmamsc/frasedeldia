"""Weekly editorial approvals, Telegram polling and four independent RSS publications."""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from .core import LANGS, SPANISH_VOICE, ENGLISH_VOICE, upcoming_monday, approved_for, next_unused, validate_parts, rss_xml

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "state.json"
CATALOG_PATH = ROOT / "data" / "catalog.json"
PUBLIC = ROOT / "public"
PARIS = ZoneInfo("Europe/Paris")
BASE_URL = "https://raw.githubusercontent.com/youmamsc/frasedeldia/main/public"
SHOW_WORDS = {"en": "English", "fr": "français", "it": "italiano", "es": "español"}
TIMEOUT = 90


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def telegram(method: str, **payload) -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
    try:
        response = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=30)
    except requests.RequestException:
        # The request URL contains the token. Never print raw HTTP exceptions.
        raise RuntimeError(f"Telegram {method}: network error (credentials hidden)") from None
    if response.status_code >= 400:
        raise RuntimeError(f"Telegram {method}: HTTP {response.status_code} (credentials hidden)")
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram rejected {method}: {data.get('description', 'unknown error')}")
    return data["result"]


def notify(text: str, markup: dict | None = None) -> dict:
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID missing")
    options = {"chat_id": chat_id, "text": text}
    if markup:
        options["reply_markup"] = markup
    return telegram("sendMessage", **options)


def call_gemini(prompt: str) -> dict:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing")
    model = (os.environ.get("GEMINI_TEXT_MODEL") or "gemini-2.5-flash").strip()
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": key},
        json={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.75, "responseMimeType": "application/json", "maxOutputTokens": 2500}
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    raw = "".join(p.get("text", "") for p in payload["candidates"][0]["content"]["parts"])
    raw = raw.strip()
    return json.loads(raw)


def ai_select(pool: list[dict], count: int) -> list[dict]:
    if len(pool) < count:
        raise RuntimeError("Not enough unused idioms in catalog; extend data/catalog.json")
    prompt = f"""You curate a cheeky, adult comedy podcast for learners of Spanish from SPAIN.
Pick exactly {count} DISTINCT expressions from this numbered pool, balancing funny, vulgar and common sayings.
Choose authentic idioms over obscure ones and avoid repeated themes in a single week.
DO NOT invent any idioms or change spellings. Input array indices are 0-based.
Return JSON ONLY: {{"indices":[0,4,7]}} with exactly {count} valid distinct indices.
Candidates: {json.dumps([x["expression"] for x in pool], ensure_ascii=False)}"""
    data = call_gemini(prompt)
    indices = data.get("indices", [])
    if not isinstance(indices, list) or len(indices) != count:
        raise ValueError("Gemini did not pick the required number of expressions")
    if len(set(str(x) for x in indices)) != count:
        raise ValueError("Gemini selected duplicate expressions")
    if not all(type(i) is int and 0 <= i < len(pool) for i in indices):
        raise ValueError("Gemini returned invalid catalog indices")
    return [pool[i] for i in indices]



def grow_catalog(catalog: list[dict], entries: list[dict]) -> list[dict]:
    """Extend the editorial candidate pool, still requiring human approval."""
    seen = {x["expression"].casefold() for x in catalog}
    seen.update(x["expression"].casefold() for x in entries)
    prompt = f"""Suggest 20 REAL, widely used Spanish-from-Spain colloquial expressions or idioms
suitable for a humorous adult learning podcast. Some can be gently vulgar.
Do not create phrases: every expression must already be used naturally in Spain.
Avoid ANY expression in this existing/used list: {json.dumps(sorted(seen), ensure_ascii=False)}.
Return JSON ONLY as {{"proposals":[{{"expression":"...", "literal_en":"...",
"meaning_es":"..."}}]}}.
literal_en must be a funny word-for-word ENGLISH calque, NOT an idiomatic English translation.
meaning_es must be a very short, accurate explanation in Spanish. No protected-class slurs.
Give 20 truly distinct proposals."""
    new = call_gemini(prompt).get("proposals", [])
    if not isinstance(new, list):
        raise ValueError("Gemini returned an invalid expression catalog")
    added = 0
    for item in new:
        if not isinstance(item, dict):
            continue
        candidate = {field: str(item.get(field, "")).strip() for field in
                     ("expression", "literal_en", "meaning_es")}
        if any(not value or len(value) > 130 for value in candidate.values()):
            continue
        key = candidate["expression"].casefold()
        if key in seen:
            continue
        seen.add(key)
        catalog.append(candidate)
        added += 1
    if added < 7:
        raise RuntimeError("Could not extend the candidate catalog with at least seven new expressions")
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Proposed {added} new candidates; all still require Telegram approval")
    return catalog


def send_proposal(entry: dict) -> None:
    text = (
        "🎙 LA FRASE DEL DÍA — revisión editorial\n"
        f"📅 {entry['date']}\n\n"
        f"🇪🇸 {entry['expression']}\n"
        f"🇬🇧 Traducción literal: {entry['literal_en']}\n"
        f"📝 Significado: {entry['meaning_es']}\n\n"
        "¿La publicamos en inglés, francés, italiano y en el programa español?"
    )
    buttons = {"inline_keyboard": [[
        {"text": "✅ Aprobar", "callback_data": f"a:{entry['id']}"},
        {"text": "🔄 Cambiar", "callback_data": f"r:{entry['id']}"}
    ]]}
    result = notify(text, buttons)
    entry["message_id"] = result["message_id"]


def weekly() -> None:
    state = read_json(STATE_PATH)
    catalog = read_json(CATALOG_PATH)
    monday = upcoming_monday(datetime.now(PARIS).date())
    dates = [(monday + timedelta(days=i)).isoformat() for i in range(7)]
    existing = [x for x in state["entries"] if x["date"] in dates]
    if not existing:
        used = {x["expression"].casefold() for x in state["entries"]}
        pool = [x for x in catalog if x["expression"].casefold() not in used]
        if len(pool) < 7:
            catalog = grow_catalog(catalog, state["entries"])
            pool = [x for x in catalog if x["expression"].casefold() not in used]
        picked = ai_select(pool, 7)
        for i, phrase in enumerate(picked):
            state["entries"].append({
                "id": f"{dates[i]}-1", "date": dates[i],
                **phrase, "status": "pending", "message_id": None
            })
        save_state(state)  # preserve selection even if Telegram fails
    for entry in state["entries"]:
        if entry["date"] in dates and entry["status"] == "pending" and not entry.get("message_id"):
            send_proposal(entry)
            save_state(state)
    print(f"Proposals ready for {dates[0]} through {dates[-1]}")


def on_callback(query: dict, state: dict, catalog: list[dict]) -> None:
    user_id = str(query.get("from", {}).get("id", ""))
    expected_id = str(os.environ.get("TELEGRAM_CHAT_ID", ""))
    incoming_chat = str(query.get("message", {}).get("chat", {}).get("id", ""))
    qid = query.get("id")
    if user_id != expected_id or incoming_chat != expected_id:
        if qid:
            telegram("answerCallbackQuery", callback_query_id=qid, text="No autorizado", show_alert=True)
        return
    action, sep, entry_id = str(query.get("data", "")).partition(":")
    target = next((x for x in state["entries"] if x["id"] == entry_id), None)
    if not sep or action not in {"a", "r"} or not target or target["status"] != "pending":
        if qid:
            telegram("answerCallbackQuery", callback_query_id=qid, text="Propuesta ya procesada")
        return
    if action == "a":
        target["status"] = "approved"
        save_state(state)
        telegram("answerCallbackQuery", callback_query_id=qid, text="✅ Aprobada")
        notify(f"✅ {target['date']}: «{target['expression']}» aprobada para los cuatro podcasts.")
        return
    used = {x["expression"].casefold() for x in state["entries"]}
    pool = [x for x in catalog if x["expression"].casefold() not in used]
    if not pool:
        catalog = grow_catalog(catalog, state["entries"])
        pool = [x for x in catalog if x["expression"].casefold() not in used]
    replacement = ai_select(pool, 1)[0]
    target["status"] = "rejected"
    save_state(state)
    telegram("answerCallbackQuery", callback_query_id=qid, text="🔄 Buscando otra...")
    version = 1 + max(int(x["id"].rsplit("-", 1)[-1]) for x in state["entries"] if x["date"] == target["date"])
    new_entry = {
        "id": f"{target['date']}-{version}", "date": target["date"],
        **replacement, "status": "pending", "message_id": None
    }
    state["entries"].append(new_entry)
    save_state(state)
    send_proposal(new_entry)
    save_state(state)


def poll() -> None:
    state = read_json(STATE_PATH)
    updates = telegram("getUpdates", offset=int(state.get("offset", 0)), limit=100, timeout=0, allowed_updates=["callback_query"])
    catalog = read_json(CATALOG_PATH)
    for update in updates:
        on_callback(update.get("callback_query", {}), state, catalog) if update.get("callback_query") else None
        state["offset"] = max(int(state.get("offset", 0)), int(update["update_id"]) + 1)
        save_state(state)
    # A failed Telegram send must not strand a replacement without buttons.
    for entry in state["entries"]:
        if entry["status"] == "pending" and not entry.get("message_id"):
            send_proposal(entry)
            save_state(state)
    print(f"Processed {len(updates)} Telegram updates")


def create_script(language: str, phrase: dict) -> list[dict]:
    locale = SHOW_WORDS[language]
    is_es = language == "es"
    rules = (
        f"""SPANISH-AUDIENCE EDITION. Start the ENTIRE AUDIO with exactly these words in natural English, not with a greeting:
"{phrase['literal_en']}".
Then switch to Spanish, react incredulously to the absurd literal translation, and explain the original Spanish phrase.
Give the truly IDIOMATIC English equivalent (or sensible English paraphrase if no exact idiom), pronounced IN ENGLISH.
Include two tiny humorous real-life examples, with correct English phrasing pronounced in English.
Use voice="english" for English-only segments, voice="host" for Spanish explanation.
The first element MUST be an English voice segment whose text starts with the literal translation exactly.
This is NOT an English learner podcast; the HOST explains mainly in Spanish, targeting native Spaniards."""
        if is_es else
        f"""FOREIGN-AUDIENCE EDITION. Explain the Spanish expression in {locale}.
Open with a punchy native-language hook. Speak the approved Spanish expression using voice="spanish" exactly.
Explain its meaning (not the word-by-word translation), add a short slow repeat of the Spanish pronunciation
as another "spanish" voice segment, and give TWO cheeky everyday mini-examples in {locale}.
Use voice="host" for narration in {locale}, and "spanish" for Spanish-only chunks.
Audience is learning the Spanish people actually use, not classroom Spanish."""
    )
    prompt = f"""Write one very funny, adult, slightly vulgar but NON-HATEFUL podcast of ~45–60 seconds.
Original approved Spanish expression: "{phrase['expression']}"
Absurd English literal calque: "{phrase['literal_en']}"
Spanish meaning: "{phrase['meaning_es']}"
Locale: {locale}. Castilian pronunciation for Spanish segments. Humour: cheeky, irreverent, slightly dirty,
smart, natural and punchy; never bland. No slurs targeting protected groups, no graphic sexual detail.
No irrelevant intros or promotional material; one crisp closing punchline.
{rules}
Return JSON ONLY with:
{{"parts":[{{"voice":"host|spanish|english","text":"..."}}]}}
5 to 10 short parts total; between 80 and 110 words overall. Each text should be fully spoken text,
with NO sound directions, brackets, markdown or phonetic markup. Keep natural grammar and idiom usage.
Approved Spanish expression must appear verbatim in a spoken part.
Do NOT recommend the absurd literal calque as correct English. When there is no matching English idiom,
give a clear natural equivalent rather than inventing one."""
    data = call_gemini(prompt)
    return validate_parts(language, phrase, data.get("parts"))


async def _speech(parts: list[dict], language: str, path: Path) -> None:
    import edge_tts
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        clips = []
        for i, part in enumerate(parts):
            voice = (
                SPANISH_VOICE if part["voice"] == "spanish"
                else ENGLISH_VOICE if part["voice"] == "english"
                else LANGS[language]["voice"]
            )
            clip = folder / f"part-{i:02d}.mp3"
            await edge_tts.Communicate(part["text"], voice).save(str(clip))
            if not clip.exists() or not clip.stat().st_size:
                raise RuntimeError("TTS produced an empty segment")
            clips.append(clip)
        concat_list = folder / "concat.txt"
        concat_list.write_text("".join(f"file '{p}'\n" for p in clips), encoding="utf-8")
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", str(concat_list), "-c:a", "libmp3lame", "-b:a", "128k", str(path)],
            check=True, timeout=100,
        )


def make_audio(parts: list[dict], language: str, path: Path) -> float:
    from mutagen.mp3 import MP3
    asyncio.run(_speech(parts, language, path))
    seconds = float(MP3(path).info.length)
    if seconds < 20 or seconds > 70:
        raise RuntimeError(f"{language}: {seconds:.1f}s outside acceptable duration 20–70s")
    if seconds > 60:
        speed = seconds / 58.7
        fitted = path.with_suffix(".fitted.mp3")
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(path),
             "-filter:a", f"atempo={speed:.5f}", "-codec:a", "libmp3lame", "-b:a", "128k", str(fitted)],
            check=True, timeout=80,
        )
        shutil.move(fitted, path)
        seconds = float(MP3(path).info.length)
    if seconds > 60 or seconds < 20:
        raise RuntimeError(f"{language}: invalid final audio duration {seconds:.1f}s")
    return round(seconds, 2)


def cover(path: Path, language: str) -> None:
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (3000, 3000), "#22212c")
    draw = ImageDraw.Draw(image)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    title_font = ImageFont.truetype(font_path, 310)
    subtitle_font = ImageFont.truetype(font_path, 155)
    lines = ["LA FRASE", "DEL DÍA"]
    for y, line in [(880, lines[0]), (1260, lines[1])]:
        draw.text((1500, y), line, fill="#ffffff", anchor="mt", font=title_font)
    labels = {"en": "IN ENGLISH", "fr": "EN FRANÇAIS", "it": "IN ITALIANO", "es": "ESPAÑOL → ENGLISH"}
    draw.text((1500, 1900), labels[language], fill="#f5bb65", anchor="mt", font=subtitle_font)
    draw.text((1500, 2450), "HUMOR • IDIOMS • 60 SEC", fill="#ffffff", anchor="mt",
              font=ImageFont.truetype(font_path, 80))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG", optimize=True)


def rebuild_feed(language: str, email: str) -> None:
    folder = PUBLIC / language
    episodes = [read_json(p) for p in (folder / "episodes").glob("*.json")]
    (folder / "feed.xml").write_bytes(rss_xml(language, episodes, email, BASE_URL))


def daily() -> None:
    if os.environ.get("ENABLE_PUBLICATION", "").strip().lower() != "true":
        print("Publication disabled: set repository variable ENABLE_PUBLICATION=true after setup")
        return
    today = datetime.now(PARIS).date()
    state = read_json(STATE_PATH)
    phrase = approved_for(state["entries"], today)
    if phrase is None:
        print(f"No approved expression for {today}; do not publish")
        return
    if phrase["status"] == "published":
        print(f"{today} already published; nothing to do")
        return
    email = os.environ.get("PODCAST_OWNER_EMAIL", "").strip()
    if not email or "@" not in email:
        raise RuntimeError("PODCAST_OWNER_EMAIL missing or invalid; RSS needs ownership email")
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY not configured")
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        generated: dict[str, tuple[Path, dict]] = {}
        for language in LANGS:
            parts = create_script(language, phrase)
            audio = work / f"{language}.mp3"
            duration = make_audio(parts, language, audio)
            metadata = {
                "date": today.isoformat(),
                "title": f"{phrase['expression']} — {today.isoformat()}",
                "description": f"{phrase['expression']}: {phrase['meaning_es']}",
                "expression": phrase["expression"],
                "parts": parts,
                "published_at": datetime.now(PARIS).isoformat(),
                "bytes": audio.stat().st_size,
                "duration": duration,
            }
            generated[language] = audio, metadata
            print(f"Generated {language} in {duration}s")
        # All four must succeed BEFORE committing any public feed files.
        for language, (audio, metadata) in generated.items():
            folder = PUBLIC / language
            episode_folder = folder / "episodes"
            episode_folder.mkdir(parents=True, exist_ok=True)
            shutil.copy2(audio, episode_folder / f"{today.isoformat()}.mp3")
            (episode_folder / f"{today.isoformat()}.json").write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            if not (folder / "cover.png").exists():
                cover(folder / "cover.png", language)
            rebuild_feed(language, email)
    phrase["status"] = "published"
    phrase["published_at"] = datetime.now(PARIS).isoformat()
    save_state(state)
    try:
        notify("🎙 Publicados los cuatro audios y sus RSS de hoy.\n"
               f"🇪🇸 {phrase['expression']}\n"
               "Spotify los incorporará una vez registres cada programa y cuando lea los RSS.")
    except Exception:
        print("Telegram post-publication notification failed; completed publication remains saved")
    print("All four RSS feeds and episode MP3s generated")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "tests"
    if mode == "tests":
        import unittest
        suite = unittest.defaultTestLoader.discover(str(ROOT / "automation" / "tests"))
        if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
            raise SystemExit(1)
        return
    if mode not in {"weekly", "poll", "daily"}:
        raise SystemExit("Mode must be tests, weekly, poll or daily")
    try:
        {"weekly": weekly, "poll": poll, "daily": daily}[mode]()
    except Exception as exc:
        print(f"ERROR in {mode}: {type(exc).__name__}: {str(exc)[:300]}", file=sys.stderr)
        if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
            try:
                notify(f"⚠️ La Frase del Día: fallo en '{mode}'.\n"
                       f"Consulta Actions: {os.environ.get('GH_RUN_URL', 'GitHub')}")
            except Exception:
                pass
        raise


if __name__ == "__main__":
    main()
