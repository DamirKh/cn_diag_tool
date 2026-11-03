"""Tests for the single-connection ControlNet poller (no hardware required)."""
import unittest

from PyQt6.QtCore import QCoreApplication

from cn_poller import ControlNetPoller


class FakeTag:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error


class FakeDriver:
    def __init__(self, errors=None, cm_values=None, cm_errors=None):
        self.calls = []
        self.errors = errors or {}
        self.cm_values = cm_values or {}
        self.cm_errors = cm_errors or {}
        self.closed = False

    def open(self):
        return True

    def close(self):
        self.closed = True

    def generic_message(self, **kwargs):
        self.calls.append(kwargs)
        name = kwargs['name']
        if kwargs.get('class_code') == 0x06:
            attribute = kwargs['attribute']
            if attribute in self.cm_errors:
                return FakeTag(error=self.cm_errors[attribute])
            if attribute in self.cm_values:
                return FakeTag(value=self.cm_values[attribute])
            return FakeTag(error='Object does not exist')
        for marker, error in self.errors.items():
            if marker in name:
                return FakeTag(error=error)
        if 'COUNTERS' in name:
            return FakeTag(value=bytes(42))
        return FakeTag(value=bytes(6))


def make_poller(nodes=(1, 2), cycle_time=1.0):
    base = '10.0.0.1/bp/0/cnet'
    poller = ControlNetPoller(base, {node: f'{base}/{node}' for node in nodes},
                              cycle_time=cycle_time)
    poller._sleep = lambda seconds: None
    return poller


class ControlNetPollerTest(unittest.TestCase):
    def test_polls_nodes_sequentially_with_their_own_routes(self):
        poller = make_poller()
        driver = FakeDriver()
        counters = []
        leds = []
        poller.counters_read_done.connect(lambda node, data: counters.append((node, data)))
        poller.leds_read_done.connect(lambda node, data: leds.append((node, data)))

        poller._poll_cycle(driver)

        self.assertEqual([call['name'] for call in driver.calls], [
            'CN_DIAG_COUNTERS [01]',
            'CN_DIAG_LED [01]',
            'CN_DIAG_COUNTERS [02]',
            'CN_DIAG_LED [02]',
        ])
        self.assertEqual([call['route_path'] for call in driver.calls], [
            'bp/0/cnet/1', 'bp/0/cnet/1', 'bp/0/cnet/2', 'bp/0/cnet/2',
        ])
        self.assertEqual([node for node, _ in counters], [1, 2])
        self.assertEqual([node for node, _ in leds], [1, 2])
        self.assertIn('good_frames_transmitted/s', counters[0][1])
        self.assertIn('reply_time', counters[0][1])

    def test_insufficient_resource_skips_the_node_and_logs_it(self):
        poller = make_poller()
        driver = FakeDriver({'CN_DIAG_COUNTERS [02]': 'Insufficient resource'})
        errors = []
        poller.non_fatal_error.connect(lambda node, error: errors.append((node, error)))

        with self.assertLogs('cn_poller', level='ERROR') as logs:
            poller._poll_cycle(driver)

        names = [call['name'] for call in driver.calls]
        self.assertIn('CN_DIAG_LED [01]', names)
        self.assertNotIn('CN_DIAG_LED [02]', names)
        self.assertIn((2, 'Insufficient resource'), errors)
        self.assertTrue(any('[02]' in line for line in logs.output))

    def test_reset_counters_is_sent_once(self):
        poller = make_poller(nodes=(1,))
        driver = FakeDriver()
        poller.reset_counters({1})

        poller._poll_cycle(driver)
        self.assertIn('CN_DIAG_COUNTERS_RESET [01]',
                      [call['name'] for call in driver.calls])

        driver.calls.clear()
        poller._poll_cycle(driver)
        names = [call['name'] for call in driver.calls]
        self.assertIn('CN_DIAG_COUNTERS [01]', names)
        self.assertNotIn('CN_DIAG_COUNTERS_RESET [01]', names)

    def test_pause_and_stop_skip_the_cycle(self):
        paused = make_poller()
        paused.pause(True)
        driver = FakeDriver()
        paused._poll_cycle(driver)
        self.assertEqual(driver.calls, [])

        stopped = make_poller()
        stopped.stop()
        driver = FakeDriver()
        stopped._poll_cycle(driver)
        self.assertEqual(driver.calls, [])

    def test_cycle_time_is_clamped(self):
        self.assertEqual(make_poller(cycle_time=0.1).cycle_time, 0.5)
        self.assertEqual(make_poller(cycle_time=60.0).cycle_time, 10.0)

    def test_node_count(self):
        self.assertEqual(make_poller(nodes=(1, 2, 3)).node_count, 3)

    def test_run_opens_and_closes_one_driver(self):
        poller = make_poller(nodes=(1,))

        class StoppingDriver(FakeDriver):
            def generic_message(self, **kwargs):
                poller.stop()
                return super().generic_message(**kwargs)

        driver = StoppingDriver()
        poller._driver_factory = lambda path: driver
        poller.run()

        self.assertTrue(driver.calls)
        self.assertTrue(driver.closed)

    def test_module_stats_per_node(self):
        poller = make_poller(nodes=(1, 2))
        poller.set_module_stats_enabled(True)
        values = {
            1: (123).to_bytes(2, 'little'),
            9: (10).to_bytes(2, 'little') + bytes([0b00000101, 0b00000010]),
            11: (235).to_bytes(2, 'little'),
            12: (65536).to_bytes(4, 'little'),
            13: (41200).to_bytes(4, 'little'),
        }
        driver = FakeDriver(cm_values=values)
        stats = []
        poller.module_stats_read.connect(lambda node, data: stats.append((node, data)))

        poller._poll_module_stats(driver)

        self.assertEqual([node for node, _ in stats], [1, 2])
        for _, data in stats:
            self.assertEqual(data['total_connections'], 10)
            self.assertEqual(data['connections_used'], 3)
            self.assertEqual(data['open_requests'], 123)
            self.assertEqual(data['cpu_utilization'], 23.5)
            self.assertEqual(data['max_buffer_size'], 65536)
            self.assertEqual(data['buffer_remaining'], 41200)
        cm_calls = [call for call in driver.calls if call.get('class_code') == 0x06]
        self.assertEqual({call['route_path'] for call in cm_calls},
                         {'bp/0/cnet/1', 'bp/0/cnet/2'})
        self.assertTrue(all(call['unconnected_send'] for call in cm_calls))

    def test_module_stats_generic_layout(self):
        poller = make_poller(nodes=(1,))
        poller.set_module_stats_enabled(True)
        values = {
            1: (7).to_bytes(2, 'little'),
            9: (8).to_bytes(2, 'little') + bytes([0b00000011]),
            10: (500).to_bytes(2, 'little'),
            11: (2000).to_bytes(4, 'little'),
            12: (3000).to_bytes(4, 'little'),
        }
        driver = FakeDriver(cm_values=values)
        stats = []
        poller.module_stats_read.connect(lambda node, data: stats.append((node, data)))

        poller._poll_module_stats(driver)

        data = stats[0][1]
        self.assertEqual(data['total_connections'], 8)
        self.assertEqual(data['connections_used'], 2)
        self.assertEqual(data['cpu_utilization'], 50.0)
        self.assertEqual(data['max_buffer_size'], 2000)
        self.assertEqual(data['buffer_remaining'], 3000)

    def test_module_stats_resource_error_stops_the_pass(self):
        poller = make_poller(nodes=(1, 2))
        poller.set_module_stats_enabled(True)
        driver = FakeDriver(cm_errors={9: 'Insufficient resource'})
        stats = []
        poller.module_stats_read.connect(lambda node, data: stats.append((node, data)))

        with self.assertLogs('cn_poller', level='ERROR') as logs:
            poller._poll_module_stats(driver)

        self.assertEqual(stats, [])
        self.assertTrue(any('[01]' in line for line in logs.output))

    def test_module_stats_are_polled_only_when_enabled(self):
        poller = make_poller(nodes=(1,))
        values = {
            1: (1).to_bytes(2, 'little'),
            9: (8).to_bytes(2, 'little') + bytes([0b00000001]),
            11: (100).to_bytes(2, 'little'),
            12: (1000).to_bytes(4, 'little'),
            13: (500).to_bytes(4, 'little'),
        }
        driver = FakeDriver(cm_values=values)

        poller._poll_cycle(driver)
        self.assertFalse(any(call.get('class_code') == 0x06 for call in driver.calls))

        driver.calls.clear()
        poller.set_module_stats_enabled(True)
        poller._poll_cycle(driver)
        self.assertTrue(any(call.get('class_code') == 0x06 for call in driver.calls))

    def test_unsupported_node_is_skipped_after_first_attempt(self):
        poller = make_poller(nodes=(1,))
        poller.set_module_stats_enabled(True)
        driver = FakeDriver()

        poller._poll_module_stats(driver)
        self.assertTrue(driver.calls)

        driver.calls.clear()
        poller._poll_module_stats(driver)
        self.assertEqual(driver.calls, [])


def setUpModule():
    global _app
    _app = QCoreApplication.instance() or QCoreApplication([])


if __name__ == '__main__':
    unittest.main()
