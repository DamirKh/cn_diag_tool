"""Per-node rate and average math for the ControlNet diagnostic counters."""
import time


class CounterTracker:
    tree_byte_counters = [
        'good_frames_transmitted',
        'good_frames_received',
    ]
    max_frames_per_second = 10000

    def __init__(self, initial_timestamp=None):
        self._previous_counters = {}
        self._previous_timestamp = (
            time.monotonic() if initial_timestamp is None else initial_timestamp
        )
        self._avg_started = None
        self._avg_totals = {}

    def corrected_increment(self, key, previous, value, time_delta):
        """Returns the growth of a counter between two samples."""
        raw = value - previous
        if raw >= 0:
            return raw

        cap = self.max_frames_per_second * max(time_delta, 0.001)
        moduli = (2**24, 2**16, 2**8) if key in self.tree_byte_counters else (2**8,)
        candidates = []
        for modulus in moduli:
            increment = raw + modulus
            if 0 <= increment <= cap and previous >= modulus - cap:
                candidates.append(increment)
        if candidates:
            return min(candidates)
        return max(value, 0)

    def compute_rates(self, counters, current_timestamp):
        """Returns counters enriched with per-second rates and averages since start."""
        time_delta = current_timestamp - self._previous_timestamp
        result = counters.copy()
        for key, value in counters.items():
            if key.startswith('#'):
                continue
            try:
                increment = self.corrected_increment(
                    key, self._previous_counters.get(key, value), value, time_delta)
                rate = increment / time_delta if time_delta > 0 else 0
                result[key + "/s"] = int(rate)
                if key in self.tree_byte_counters:
                    self._avg_totals[key] = self._avg_totals.get(key, 0) + increment
            except TypeError:
                result[key + "/s"] = "N/A"

        if self._avg_started is None:
            self._avg_started = current_timestamp
        else:
            elapsed = current_timestamp - self._avg_started
            if elapsed > 0:
                for key in self.tree_byte_counters:
                    result[key + "_avg"] = self._avg_totals.get(key, 0) / elapsed

        self._previous_counters = counters.copy()
        self._previous_timestamp = current_timestamp
        return result

    def reset_average(self, timestamp=None):
        """Starts a new averaging baseline (called after the module counters reset)."""
        self._avg_totals = {}
        self._avg_started = None
        self._previous_counters = {}
        self._previous_timestamp = time.monotonic() if timestamp is None else timestamp
