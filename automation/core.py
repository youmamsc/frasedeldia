"""Deterministic editorial rules; no external calls."""
from __future__ import annotations

from datetime import date, timedelta
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

LANGS = {
    "en": {"title": "La Frase del Día — English", "language": "en", "voice": "en-GB-RyanNeural",
           "description": "Spicy Spanish expressions explained in English. Real pronunciation and shameless humour."},
    "fr": {"title": "La Frase del Día — Français", "language": "fr", "voice": "fr-FR-HenriNeural",
           "description": "Le vrai espagnol de la rue : expressions épicées, humour et prononciation."},
    "it": {"title": "La Frase del Día — Italiano", "language": "it", "voice": "it-IT-DiegoNeural",
           "description": "Lo spagnolo vero: espressioni colorite, esempi e humor."},
    "es": {"title": "Del Español al Inglés — La Frase del Día", "language": "es", "voice": "es-ES-AlvaroNeural",
           "description": "¿From lost to the river? Aprende a decir en inglés lo que de verdad dirías en español."},
}
SPANISH_VOICE = "es-ES-AlvaroNeural"
ENGLISH_VOICE = "en-GB-RyanNeural"
ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM = "http://www.w3.org/2005/Atom"
ET.register_namespace("itunes", ITUNES)
ET.register_namespace("atom", ATOM)


def upcoming_monday(today: date) -> date:
    """Always schedule the NEXT Monday, even if called on Monday."""
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def approved_for(entries: list[dict], when: date) -> dict | None:
    matching = [x for x in entries if x.get("date") == when.isoformat() and x.get("status") in ("approved", "published")]
    return matching[-1] if matching else None


def next_unused(catalog: list[dict], entries: list[dict], excluded: set[str] | None = None) -> dict:
    used = {e["expression"].casefold() for e in entries} | {x.casefold() for x in (excluded or set())}
    for item in catalog:
        if item["expression"].casefold() not in used:
            return item
    raise RuntimeError("Catálogo agotado: añade más expresiones auténticas antes de generar la semana siguiente")


def validate_parts(language: str, phrase: dict, parts: list) -> list[dict]:
    if language not in LANGS or not isinstance(parts, list) or not 5 <= len(parts) <= 12:
        raise ValueError("Unsupported language or invalid number of spoken segments")
    clean = []
    for item in parts:
        if not isinstance(item, dict) or item.get("voice") not in {"host", "spanish", "english"}:
            raise ValueError("Invalid speaker")
        text = str(item.get("text", "")).strip()
        if not 1 <= len(text) <= 380:
            raise ValueError("Invalid segment length")
        clean.append({"voice": item["voice"], "text": text})
    total_words = sum(len(item["text"].split()) for item in clean)
    if not 55 <= total_words <= 145:
        raise ValueError(f"Invalid total spoken words: {total_words}")
    if phrase["expression"].casefold() not in " ".join(x["text"] for x in clean).casefold():
        raise ValueError("The approved Spanish expression must be said aloud")
    if language == "es":
        if clean[0]["voice"] != "english":
            raise ValueError("The Spanish-language show must begin in English with the literal calque")
        if not clean[0]["text"].casefold().startswith(phrase["literal_en"].casefold()):
            raise ValueError("The literal English translation must be the first words")
    return clean


def rss_xml(language: str, episodes: list[dict], owner_email: str, base_url: str) -> bytes:
    """Generate valid four-channel podcast RSS. Explicit language for adult idioms."""
    show = LANGS[language]
    root = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(root, "channel")
    for tag, value in [
        ("title", show["title"]), ("link", base_url + "/" + language + "/"),
        ("description", show["description"]), ("language", show["language"])
    ]:
        ET.SubElement(channel, tag).text = value
    for tag, value in [("author", "La Frase del Día"), ("explicit", "true"), ("type", "episodic")]:
        ET.SubElement(channel, f"{{{ITUNES}}}{tag}").text = value
    ET.SubElement(channel, f"{{{ITUNES}}}category", {"text": "Education"})
    ET.SubElement(channel, f"{{{ITUNES}}}image", {"href": f"{base_url}/{language}/cover.png"})
    owner = ET.SubElement(channel, f"{{{ITUNES}}}owner")
    ET.SubElement(owner, f"{{{ITUNES}}}name").text = "La Frase del Día"
    ET.SubElement(owner, f"{{{ITUNES}}}email").text = owner_email
    ET.SubElement(channel, f"{{{ATOM}}}link", {"href": f"{base_url}/{language}/feed.xml", "rel": "self", "type": "application/rss+xml"})
    for episode in sorted(episodes, key=lambda x: x["date"], reverse=True):
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = episode["title"]
        ET.SubElement(item, "description").text = episode["description"]
        ET.SubElement(item, "pubDate").text = format_datetime(__import__("datetime").datetime.fromisoformat(episode["published_at"]))
        url = f'{base_url}/{language}/episodes/{episode["date"]}.mp3'
        ET.SubElement(item, "guid", {"isPermaLink": "true"}).text = url
        ET.SubElement(item, "enclosure", {"url": url, "length": str(episode["bytes"]), "type": "audio/mpeg"})
        ET.SubElement(item, f"{{{ITUNES}}}explicit").text = "true"
        ET.SubElement(item, f"{{{ITUNES}}}duration").text = str(round(episode["duration"]))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
