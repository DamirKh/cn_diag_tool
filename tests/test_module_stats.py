"""Tests for the CIP Connection Manager (class 0x06) value parsers."""
import unittest

import module_stats


class ParseScalarTest(unittest.TestCase):
    def test_uint(self):
        self.assertEqual(module_stats.parse_uint((235).to_bytes(2, 'little')), 235)

    def test_udint(self):
        self.assertEqual(module_stats.parse_udint((70000).to_bytes(4, 'little')), 70000)

    def test_short_or_empty(self):
        self.assertIsNone(module_stats.parse_uint(b''))
        self.assertIsNone(module_stats.parse_uint(b'\x01'))
        self.assertIsNone(module_stats.parse_udint(b'\x01\x02'))

    def test_cpu_percent(self):
        self.assertEqual(module_stats.cpu_percent((235).to_bytes(2, 'little')), 23.5)
        self.assertIsNone(module_stats.cpu_percent(None))


class ConnectionEntryListTest(unittest.TestCase):
    def test_total_and_used(self):
        value = (10).to_bytes(2, 'little') + bytes([0b00000101, 0b00000010])
        self.assertEqual(module_stats.parse_connection_entry_list(value), (10, 3))

    def test_unused_high_bits_are_masked(self):
        value = (9).to_bytes(2, 'little') + bytes([0b11111111, 0b11111111])
        self.assertEqual(module_stats.parse_connection_entry_list(value), (9, 9))

    def test_zero_entries(self):
        value = (0).to_bytes(2, 'little')
        self.assertEqual(module_stats.parse_connection_entry_list(value), (0, 0))

    def test_truncated_bitmap(self):
        value = (16).to_bytes(2, 'little') + bytes([0b00000001])
        self.assertEqual(module_stats.parse_connection_entry_list(value), (16, None))

    def test_empty(self):
        self.assertEqual(module_stats.parse_connection_entry_list(None), (None, None))
        self.assertEqual(module_stats.parse_connection_entry_list(b''), (None, None))


if __name__ == '__main__':
    unittest.main()
