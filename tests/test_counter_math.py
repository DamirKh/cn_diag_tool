"""Tests for the ControlNet counter rate/average math.

Run from the repository root:
    python -m unittest discover -s tests -v
"""
import unittest

from PyQt6.QtCore import QCoreApplication

import Plc_connection_worker as w


class CounterMathTest(unittest.TestCase):
    def setUp(self):
        self.worker = w.PLCConnectionWorker(1)
        self.worker._previous_counters = {}
        self.worker._previous_timestamp = 0.0

    def feed(self, counters, ts):
        dt = ts - self.worker._previous_timestamp
        result = self.worker._compute_rates(counters, ts, dt)
        self.worker._previous_counters = counters.copy()
        self.worker._previous_timestamp = ts
        return result

    def inc(self, key, previous, value, dt=1.0):
        return self.worker._corrected_increment(key, previous, value, dt)

    # --- increment / wrap detection -------------------------------------

    def test_8bit_wrap(self):
        self.assertEqual(self.inc('noise_hits', 250, 5), 11)

    def test_16bit_wrap(self):
        # some modules keep these counters 16-bit even though the field is wider
        self.assertEqual(self.inc('good_frames_transmitted', 65530, 10), 16)

    def test_24bit_wrap(self):
        self.assertEqual(self.inc('good_frames_transmitted', 2**24 - 10, 5), 15)

    def test_reset_is_not_a_wrap(self):
        # a drop from a non-top value is a reset, not a wrap
        self.assertEqual(self.inc('good_frames_transmitted', 30000, 0), 0)
        self.assertEqual(self.inc('good_frames_transmitted', 1000, 0), 0)

    def test_large_reset_does_not_add_modulus(self):
        # regression: this used to add 2**24 and blow up the average
        self.assertEqual(self.inc('good_frames_transmitted', 1_000_000, 0), 0)

    # --- rates / averages ------------------------------------------------

    def test_first_sample_has_no_average(self):
        r = self.feed({'good_frames_transmitted': 500, 'good_frames_received': 500}, 1.0)
        self.assertNotIn('good_frames_transmitted_avg', r)
        self.assertNotIn('good_frames_received_avg', r)

    def test_average_is_increment_over_elapsed(self):
        self.feed({'good_frames_transmitted': 0, 'good_frames_received': 0}, 0.0)
        r1 = self.feed({'good_frames_transmitted': 100, 'good_frames_received': 200}, 1.0)
        self.assertEqual(r1['good_frames_transmitted_avg'], 100.0)
        self.assertEqual(r1['good_frames_received_avg'], 200.0)
        r2 = self.feed({'good_frames_transmitted': 200, 'good_frames_received': 400}, 2.0)
        self.assertEqual(r2['good_frames_transmitted_avg'], 100.0)
        self.assertEqual(r2['good_frames_received_avg'], 200.0)

    def test_average_survives_reset_without_exploding(self):
        self.feed({'good_frames_transmitted': 30000}, 0.0)
        r1 = self.feed({'good_frames_transmitted': 0}, 1.0)  # reset
        self.assertEqual(r1['good_frames_transmitted/s'], 0)
        self.assertLess(r1['good_frames_transmitted_avg'], 1.0)
        r2 = self.feed({'good_frames_transmitted': 500}, 2.0)
        self.assertEqual(r2['good_frames_transmitted_avg'], 250.0)

    def test_average_with_16bit_wrap(self):
        self.feed({'good_frames_transmitted': 65000}, 0.0)
        r1 = self.feed({'good_frames_transmitted': 100}, 1.0)  # wraps at 2**16: +636
        self.assertEqual(r1['good_frames_transmitted/s'], 636)
        self.assertEqual(r1['good_frames_transmitted_avg'], 636.0)
        r2 = self.feed({'good_frames_transmitted': 700}, 2.0)  # +600 over 2 s
        self.assertEqual(r2['good_frames_transmitted_avg'], 618.0)

    def test_average_with_24bit_wrap(self):
        self.feed({'good_frames_transmitted': 2**24 - 1000}, 0.0)
        r1 = self.feed({'good_frames_transmitted': 500}, 1.0)  # +1000 to wrap, then +500
        self.assertEqual(r1['good_frames_transmitted/s'], 1500)
        r2 = self.feed({'good_frames_transmitted': 1500}, 2.0)  # +1000 over 2 s -> 2500/2
        self.assertEqual(r2['good_frames_transmitted_avg'], 1250.0)

    def test_reset_after_large_value_keeps_average_sane(self):
        self.feed({'good_frames_transmitted': 1_000_000}, 0.0)
        r = self.feed({'good_frames_transmitted': 0}, 1.0)
        self.assertEqual(r['good_frames_transmitted/s'], 0)
        self.assertEqual(r['good_frames_transmitted_avg'], 0.0)

    def test_reset_average_starts_new_baseline(self):
        self.feed({'good_frames_transmitted': 0}, 0.0)
        self.feed({'good_frames_transmitted': 100}, 1.0)  # avg 100
        self.worker._reset_average()
        r = self.feed({'good_frames_transmitted': 1000}, 2.0)  # new baseline sample
        self.assertNotIn('good_frames_transmitted_avg', r)
        r2 = self.feed({'good_frames_transmitted': 1100}, 3.0)  # +100 over 1 s
        self.assertEqual(r2['good_frames_transmitted/s'], 100)
        self.assertEqual(r2['good_frames_transmitted_avg'], 100.0)


def setUpModule():
    global _app
    _app = QCoreApplication.instance() or QCoreApplication([])


if __name__ == '__main__':
    unittest.main()
