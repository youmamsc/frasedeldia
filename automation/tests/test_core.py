import unittest
from datetime import date
from xml.etree import ElementTree as ET
from automation.core import upcoming_monday, approved_for, next_unused, validate_parts, rss_xml


class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.phrase = {"expression": "De perdidos al río", "literal_en": "From lost to the river", "meaning_es": "Arriesgar"}

    def test_upcoming_week_always_future(self):
        self.assertEqual(upcoming_monday(date(2026, 10, 12)), date(2026, 10, 19))
        self.assertEqual(upcoming_monday(date(2026, 10, 18)), date(2026, 10, 19))

    def test_only_approved_get_published(self):
        self.assertIsNone(approved_for([{"date": "2026-10-19", "status": "pending"}], date(2026, 10, 19)))
        self.assertIsNotNone(approved_for([{"date": "2026-10-19", "status": "approved"}], date(2026, 10, 19)))

    def test_replacement_not_duplicate(self):
        items = [self.phrase, {"expression": "Ni de coña", "literal_en": "No way", "meaning_es": "No"}]
        self.assertEqual(next_unused(items, [{"expression": "De perdidos al río"}])["expression"], "Ni de coña")

    def test_es_starts_with_literal_english(self):
        parts = [
            {"voice": "english", "text": "From lost to the river. What on earth?"},
            {"voice": "host", "text": "En español decimos De perdidos al río, pero ese inglés suena a GPS borracho."},
            {"voice": "english", "text": "In for a penny, in for a pound."},
            {"voice": "host", "text": "Eso se dice cuando ya estás metido hasta el cuello en un lío."},
            {"voice": "host", "text": "Compraste los billetes para Las Vegas, pues paga el hotel y adelante, figura."},
            {"voice": "host", "text": "Y no traduzcas literalmente, que acabas mandando al río a medio Londres."}
        ]
        self.assertEqual(validate_parts("es", self.phrase, parts)[0]["voice"], "english")
        parts[0]["text"] = "Hello world"
        with self.assertRaises(ValueError):
            validate_parts("es", self.phrase, parts)

    def test_rss_has_explicit_feed_and_enclosure(self):
        body = rss_xml("en", [{
            "date": "2026-10-19", "published_at": "2026-10-19T09:17:00+02:00",
            "title": "Ni de coña", "description": "No way", "bytes": 15312, "duration": 52
        }], "podcast@example.com", "https://raw.githubusercontent.com/youmamsc/frasedeldia/main/public")
        root = ET.fromstring(body)
        self.assertEqual(root.find("./channel/item/enclosure").attrib["type"], "audio/mpeg")
        self.assertIn(b"true", body)
        self.assertIn(b"podcast@example.com", body)


if __name__ == "__main__":
    unittest.main()
