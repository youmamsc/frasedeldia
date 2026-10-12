import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PILOTS = json.loads((ROOT / "episodes" / "pilots.json").read_text(encoding="utf-8"))


class PilotScriptsTest(unittest.TestCase):
    def test_exactly_four_languages(self):
        self.assertEqual({x["id"] for x in PILOTS["episodes"]},
                         {"en", "fr", "it", "es"})

    def test_distinct_mp3_names(self):
        filenames = [x["filename"] for x in PILOTS["episodes"]]
        self.assertEqual(len(filenames), len(set(filenames)))
        self.assertTrue(all(x.endswith(".mp3") for x in filenames))

    def test_all_segments_spoken(self):
        for episode in PILOTS["episodes"]:
            with self.subTest(lang=episode["id"]):
                self.assertGreaterEqual(len(episode["segments"]), 8)
                self.assertTrue(all(s["text"].strip() for s in episode["segments"]))
                self.assertTrue(all(s["voice"] in
                                    {"narrator", "spanish", "spanish_slow",
                                     "english", "english_slow"}
                                    for s in episode["segments"]))

    def test_native_spanish_for_teaching(self):
        for episode in PILOTS["episodes"]:
            if episode["id"] != "es":
                self.assertTrue(any(s["voice"] == "spanish_slow"
                                    and "coña" in s["text"]
                                    for s in episode["segments"]))
            else:
                self.assertEqual(episode["segments"][0]["voice"], "english")
                self.assertIn("From lost to the river",
                              episode["segments"][0]["text"])

    def test_no_shared_company_identifiers(self):
        content = json.dumps(PILOTS, ensure_ascii=False).lower()
        self.assertNotIn("msc ", content)


if __name__ == "__main__":
    unittest.main()
