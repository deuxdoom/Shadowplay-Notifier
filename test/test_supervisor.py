import os
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from component.watcher import WatchSupervisor


class FakeWatcher:
    def __init__(self, sink):
        self.sink = sink
        self.dirs = []
        self.interval = 0.01

    def prime(self):
        pass

    def emit(self, **event):
        self.sink(event)

    def tick(self):
        pass


class SupervisorTests(unittest.TestCase):
    def test_replaced_watcher_cannot_publish_late_event(self):
        events, watchers = [], []

        def make(_settings, sink):
            watcher = FakeWatcher(sink)
            watchers.append(watcher)
            return watcher

        supervisor = WatchSupervisor(events.append)
        with patch("component.watcher.make_watcher", side_effect=make):
            supervisor.start({})
            supervisor.start({})
            watchers[0].sink({"kind": "stale"})
            watchers[1].sink({"kind": "current"})
            time.sleep(0.02)
            supervisor.stop(1.0)
        self.assertNotIn("stale", [event.get("kind") for event in events])
        self.assertIn("current", [event.get("kind") for event in events])
        self.assertIsNone(supervisor.thread)


if __name__ == "__main__":
    unittest.main(verbosity=2)
