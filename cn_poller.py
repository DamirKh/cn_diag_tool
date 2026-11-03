"""Sequential ControlNet poller: one CIP session, one node at a time."""
import logging
import threading
import time

import pycomm3
from PyQt6.QtCore import QThread, pyqtSignal
from pycomm3 import CommError, RequestError, ResponseError
from pycomm3.logger import configure_default_logger

import cip_request
import module_stats
from counter_math import CounterTracker

configure_default_logger(logging.WARNING)

log = logging.getLogger(__name__)

INSUFFICIENT_RESOURCE = "Insufficient resource"
MODULE_STATS_INTERVAL = 5.0
MODULE_STATS_PACE = 0.01
_RESOURCE_ERROR = object()


def _hex(value):
    if value is None:
        return 'None'
    try:
        return bytes(value).hex()
    except TypeError:
        return repr(value)


def route_path(full_path):
    """Returns the CIP path part of an '<address>/bp/...' path."""
    return full_path.split('/', 1)[1] if '/' in full_path else full_path


def is_insufficient_resource(error):
    return INSUFFICIENT_RESOURCE.lower() in str(error).lower()


class ControlNetPoller(QThread):
    counters_read_done = pyqtSignal(int, dict)
    leds_read_done = pyqtSignal(int, dict)
    module_stats_read = pyqtSignal(int, dict)
    non_fatal_error = pyqtSignal(int, str)
    connection_lost = pyqtSignal(int, str)

    def __init__(self, base_path, node_paths, cycle_time=1.5, driver_factory=None, parent=None):
        super().__init__(parent)
        self._base_path = base_path.rstrip('/')
        self._node_paths = {int(node): path for node, path in node_paths.items()}
        self._cycle_time = self._clamp_cycle(cycle_time)
        self._seed_path = next(iter(self._node_paths.values()), f'{self._base_path}/0')
        self._route_paths = {node: route_path(path) for node, path in self._node_paths.items()}
        self._trackers = {node: CounterTracker() for node in self._node_paths}
        self._driver_factory = driver_factory or pycomm3.CIPDriver
        self._stop_event = False
        self._pause = False
        self._reset_nodes = set()
        self._module_stats_enabled = False
        self._module_stats_interval = MODULE_STATS_INTERVAL
        self._last_module_stats = 0.0
        self._module_stats_logged = set()
        self._module_stats_unsupported = set()
        self._lock = threading.Lock()

    @property
    def node_count(self):
        return len(self._node_paths)

    @property
    def cycle_time(self):
        return self._get_cycle_time()

    def stop(self):
        self._stop_event = True

    def pause(self, paused):
        with self._lock:
            self._pause = bool(paused)

    def reset_counters(self, nodes=None):
        with self._lock:
            if nodes is None:
                self._reset_nodes.update(self._node_paths)
            else:
                self._reset_nodes.update(int(node) for node in nodes)

    def set_cycle_time(self, seconds):
        with self._lock:
            self._cycle_time = self._clamp_cycle(seconds)

    def set_module_stats_enabled(self, enabled):
        with self._lock:
            self._module_stats_enabled = bool(enabled)
        if enabled:
            self._last_module_stats = 0.0

    def run(self):
        driver = None
        lost_reported = False
        try:
            while not self._stop_event:
                if self._is_paused():
                    self._sleep(0.2)
                    continue
                if driver is None:
                    try:
                        driver = self._driver_factory(self._seed_path)
                        driver.open()
                    except Exception as e:
                        log.error(f"ControlNet poller: failed to connect: {e}")
                        if not lost_reported:
                            self.connection_lost.emit(0, str(e))
                            lost_reported = True
                        self._close(driver)
                        driver = None
                        self._sleep(2.0)
                        continue
                    lost_reported = False
                    log.info(f"ControlNet poller connected to {self._seed_path}")
                try:
                    self._poll_cycle(driver)
                except CommError as e:
                    log.error(f"ControlNet poller: connection lost: {e}")
                    if not lost_reported:
                        self.connection_lost.emit(0, str(e))
                        lost_reported = True
                    self._close(driver)
                    driver = None
                    self._sleep(2.0)
                except Exception as e:
                    log.exception(f"ControlNet poller: unexpected error: {e}")
                    if not lost_reported:
                        self.connection_lost.emit(0, str(e))
                        lost_reported = True
                    self._close(driver)
                    driver = None
                    self._sleep(2.0)
        finally:
            self._close(driver)

    def _poll_cycle(self, driver):
        if self._stop_event or self._is_paused():
            return
        nodes = sorted(self._node_paths)
        if not nodes:
            return
        cycle_start = time.monotonic()
        per_request = max(0.005, min(0.05, self._get_cycle_time() / (2 * len(nodes))))
        for node in nodes:
            if self._stop_event:
                return
            if self._is_paused():
                return
            reset = self._take_reset(node)
            if self._poll_counters(driver, node, reset):
                self._sleep(per_request)
                self._poll_led(driver, node)
            self._sleep(per_request)
        now = time.monotonic()
        if (self._is_module_stats_enabled()
                and now - self._last_module_stats >= self._module_stats_interval
                and now - cycle_start <= self._get_cycle_time() * 2):
            self._poll_module_stats(driver)
            self._last_module_stats = time.monotonic()
        elapsed = time.monotonic() - cycle_start
        self._sleep(max(0.0, self._get_cycle_time() - elapsed))

    def _poll_counters(self, driver, node, reset):
        request = self._request(
            cip_request.cn_diag_counters_reset if reset else cip_request.cn_diag_counters,
            node,
        )
        started = time.monotonic()
        try:
            response = driver.generic_message(**request)
        except (ResponseError, RequestError) as e:
            self._log_error(node, request['name'], e)
            return not is_insufficient_resource(e)
        reply_time = time.monotonic() - started
        if response.error:
            self._log_error(node, request['name'], response.error)
            return not is_insufficient_resource(response.error)
        try:
            counters = cip_request.ControlNetCounters.decode(response.value)
        except Exception as e:
            self._log_error(node, f"{request['name']} decode", e)
            return True
        current = time.monotonic()
        tracker = self._trackers[node]
        if reset:
            tracker.reset_average(current)
        data = tracker.compute_rates(counters, current)
        data['reply_time'] = int(reply_time * 1_000_000)
        self.counters_read_done.emit(node, data)
        return True

    def _poll_led(self, driver, node):
        request = self._request(cip_request.cn_diag_LED, node)
        try:
            response = driver.generic_message(**request)
        except (ResponseError, RequestError) as e:
            self._log_error(node, request['name'], e)
            return
        if response.error:
            self._log_error(node, request['name'], response.error)
            return
        try:
            leds = cip_request.ControlNetLED.decode(response.value)
        except Exception as e:
            self._log_error(node, f"{request['name']} decode", e)
            return
        self.leds_read_done.emit(node, leds)

    def _poll_module_stats(self, driver):
        nodes = sorted(self._node_paths)
        for node in nodes:
            if self._stop_event or not self._is_module_stats_enabled():
                return
            if node in self._module_stats_unsupported:
                continue
            stats = self._read_node_stats(driver, node)
            if stats is None:
                return
            self.module_stats_read.emit(node, stats)

    def _read_node_stats(self, driver, node):
        entry = self._read_cm_attr(driver, node, 9)
        if entry is _RESOURCE_ERROR:
            return None
        open_requests = self._read_cm_attr(driver, node, 1)
        if open_requests is _RESOURCE_ERROR:
            return None
        cpu_rockwell = self._read_cm_attr(driver, node, 11)
        if cpu_rockwell is _RESOURCE_ERROR:
            return None
        max_buffer = self._read_cm_attr(driver, node, 12)
        if max_buffer is _RESOURCE_ERROR:
            return None
        remaining = self._read_cm_attr(driver, node, 13)
        if remaining is _RESOURCE_ERROR:
            return None

        cpu_generic = None
        if max_buffer is not None and remaining is not None:
            cpu_raw = cpu_rockwell
            max_raw = max_buffer
            rem_raw = remaining
        else:
            cpu_generic = self._read_cm_attr(driver, node, 10)
            if cpu_generic is _RESOURCE_ERROR:
                return None
            cpu_raw = cpu_generic
            max_raw = cpu_rockwell
            rem_raw = max_buffer

        total, used = module_stats.parse_connection_entry_list(entry)
        stats = {
            'total_connections': total,
            'connections_used': used,
            'open_requests': module_stats.parse_uint(open_requests),
            'cpu_utilization': module_stats.cpu_percent(cpu_raw) if cpu_raw is not None else None,
            'max_buffer_size': module_stats.parse_udint(max_raw) if max_raw is not None else None,
            'buffer_remaining': module_stats.parse_udint(rem_raw) if rem_raw is not None else None,
        }
        if all(value is None for value in stats.values()):
            self._module_stats_unsupported.add(node)
        if node not in self._module_stats_logged:
            self._module_stats_logged.add(node)
            log.info(
                'CM [%02d] raw: 9=%s 1=%s 10=%s 11=%s 12=%s 13=%s',
                node, _hex(entry), _hex(open_requests), _hex(cpu_generic),
                _hex(cpu_rockwell), _hex(max_buffer), _hex(remaining))
            log.info('CM [%02d] parsed: %s', node, stats)
        return stats

    def _read_cm_attr(self, driver, node, attribute):
        self._sleep(MODULE_STATS_PACE)
        request = dict(cip_request.connection_manager)
        request['attribute'] = attribute
        request['route_path'] = self._route_paths[node]
        request['name'] = f'CONNECTION_MANAGER_ATTR_{attribute} [{node:02}]'
        try:
            response = driver.generic_message(**request)
        except (ResponseError, RequestError) as e:
            if is_insufficient_resource(e):
                log.error(f"{request['name']}: {e}")
                return _RESOURCE_ERROR
            log.debug(f"{request['name']}: {e}")
            return None
        if response.error:
            if is_insufficient_resource(response.error):
                log.error(f"{request['name']}: {response.error}")
                return _RESOURCE_ERROR
            log.debug(f"{request['name']}: {response.error}")
            return None
        return response.value

    def _request(self, template, node):
        request = dict(template)
        request['route_path'] = self._route_paths[node]
        request['name'] = f"{template['name']} [{node:02}]"
        return request

    def _log_error(self, node, name, error):
        log.error(f"{name}: {error}")
        self.non_fatal_error.emit(node, str(error))

    def _take_reset(self, node):
        with self._lock:
            if node in self._reset_nodes:
                self._reset_nodes.discard(node)
                return True
        return False

    def _is_paused(self):
        with self._lock:
            return self._pause

    def _is_module_stats_enabled(self):
        with self._lock:
            return self._module_stats_enabled

    def _get_cycle_time(self):
        with self._lock:
            return self._cycle_time

    def _sleep(self, seconds):
        end = time.monotonic() + max(0.0, seconds)
        while not self._stop_event and time.monotonic() < end:
            time.sleep(max(0.0, min(0.1, end - time.monotonic())))

    @staticmethod
    def _close(driver):
        if driver is None:
            return
        try:
            driver.close()
        except Exception:
            pass

    @staticmethod
    def _clamp_cycle(seconds):
        return max(0.5, min(10.0, float(seconds)))
