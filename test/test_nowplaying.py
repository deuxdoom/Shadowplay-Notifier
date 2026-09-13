import os
import ssl
import sys
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from component import nowplaying


class NowPlayingLookupTests(unittest.TestCase):
    def test_best_result_skips_wrong_first_hit(self):
        items = [
            {"artistName": "sumika", "trackName": "Honto"},
            {"artistName": "LE SSERAFIM", "trackName": "Made My Night"},
        ]
        picked = nowplaying._best_result(
            items, "LE SSERAFIM", "Made My Night",
            lambda item: item["artistName"], lambda item: item["trackName"])
        self.assertIs(picked, items[1])

    def test_lookup_continues_after_store_failure_and_validates_hit(self):
        wrong = {"artistName": "sumika", "trackName": "Honto",
                 "collectionName": "Vermillion's", "artworkUrl100": "wrong"}
        right = {"artistName": "LE SSERAFIM", "trackName": "Made My Night",
                 "collectionName": "SPAGHETTI", "artworkUrl100": "right/100x100bb"}
        with patch.object(nowplaying, "_search",
                          side_effect=[urllib.error.URLError("offline"), [wrong, right]]), \
                patch.object(nowplaying, "_get", return_value=b"correct-cover") as get, \
                patch.object(nowplaying, "cached_cover") as cache:
            album, cover = nowplaying.lookup_cover(
                "LE SSERAFIM", "Made My Night", ssl.create_default_context(), time.time())
        self.assertEqual((album, cover), ("SPAGHETTI", b"correct-cover"))
        self.assertIn("600x600bb", get.call_args.args[0])
        cache.assert_not_called()

    def test_ambiguous_spotify_cache_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            since = time.time() - 1
            paths = [os.path.join(folder, name) for name in ("one", "two")]
            for index, path in enumerate(paths):
                with open(path, "wb") as stream:
                    stream.write(bytes([65 + index]) * 9000)
                os.utime(path, (since + index, since + index))
            with patch.object(nowplaying, "SPOTIFY_CACHE", folder), \
                    patch.object(nowplaying, "_jpeg_size", return_value=(640, 640)):
                self.assertIsNone(nowplaying.cached_cover(since))
                os.remove(paths[1])
                self.assertEqual(nowplaying.cached_cover(since), b"A" * 9000)

    def test_cover_finishing_after_track_change_is_discarded(self):
        worker = nowplaying.NowPlaying()
        with patch.object(nowplaying, "lookup_cover", return_value=("Album", b"cover")), \
                patch.object(nowplaying, "read_title", return_value="Other - Song"):
            applied = worker._update("Artist", "Track", time.time())
        self.assertFalse(applied)
        self.assertIsNone(worker.track.cover)


if __name__ == "__main__":
    unittest.main(verbosity=2)
