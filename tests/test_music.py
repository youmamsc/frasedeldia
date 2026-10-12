import unittest
from src.music import make_jingle


class OriginalMusicTest(unittest.TestCase):
    def test_intro_is_short_and_audible(self):
        sound = make_jingle()
        self.assertGreaterEqual(len(sound), 3000)
        self.assertLessEqual(len(sound), 3300)
        self.assertNotEqual(sound.rms, 0)

    def test_outro_is_shorter_and_audible(self):
        outro = make_jingle(outro=True)
        self.assertGreater(len(outro), 1000)
        self.assertLess(len(outro), 1500)
        self.assertGreater(outro.rms, 0)


if __name__ == "__main__":
    unittest.main()
