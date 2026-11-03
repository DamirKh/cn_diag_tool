"""Tests for the single-session ControlNet scan (no hardware required)."""
import unittest
from unittest.mock import patch

import cn_lib


class FakeTag:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error


class FakeDriver:
    def __init__(self, errors=None):
        self.calls = []
        self.errors = errors or {}
        self.opened = False
        self.closed = False

    def open(self):
        self.opened = True

    def close(self):
        self.closed = True

    def generic_message(self, **kwargs):
        self.calls.append(kwargs)
        node = int(kwargs['name'].split('[')[1].rstrip(']'))
        if node in self.errors:
            return FakeTag(error=self.errors[node])
        if node in (1, 2):
            return FakeTag(value=f'serial-{node}'.encode())
        return FakeTag(error='No node')


class ScanCnTest(unittest.TestCase):
    def test_uses_one_session_and_per_node_routes(self):
        driver = FakeDriver()
        with patch('cn_lib.CIPDriver', return_value=driver) as driver_class, \
                patch.object(cn_lib.cip_request.MyModuleIdentityObject, 'decode',
                             side_effect=lambda value: {'serial': value.decode()}):
            found, paths, identity = cn_lib.scan_cn(
                '10.0.0.1/bp/0/cnet', p=lambda *args: None, max_node_num=3)

        driver_class.assert_called_once_with('10.0.0.1/bp/0/cnet/0')
        self.assertTrue(driver.opened)
        self.assertTrue(driver.closed)
        self.assertEqual(len(driver.calls), 4)
        self.assertEqual([call['route_path'] for call in driver.calls], [
            'bp/0/cnet/0', 'bp/0/cnet/1', 'bp/0/cnet/2', 'bp/0/cnet/3',
        ])
        self.assertEqual([call['name'] for call in driver.calls], [
            'Who [00]', 'Who [01]', 'Who [02]', 'Who [03]',
        ])
        self.assertEqual(found, [1, 2])
        self.assertEqual(paths, {
            'serial-1': '10.0.0.1/bp/0/cnet/1',
            'serial-2': '10.0.0.1/bp/0/cnet/2',
        })
        self.assertEqual(identity[1]['serial'], 'serial-1')

    def test_insufficient_resource_is_logged_with_node(self):
        driver = FakeDriver({2: 'Insufficient resource'})
        with patch('cn_lib.CIPDriver', return_value=driver), \
                patch.object(cn_lib.cip_request.MyModuleIdentityObject, 'decode',
                             side_effect=lambda value: {'serial': value.decode()}):
            with self.assertLogs('cn_lib', level='ERROR') as logs:
                found, _, _ = cn_lib.scan_cn(
                    '10.0.0.1/bp/0/cnet', p=lambda *args: None, max_node_num=2)

        self.assertEqual(found, [1])
        self.assertTrue(any('Who [02]: Insufficient resource' in line
                            for line in logs.output))


if __name__ == '__main__':
    unittest.main()
