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


def all_payload(entries=382, bits=b'\xff\x07', attr10=False):
    data = b''.join(value.to_bytes(2, 'little')
                    for value in (137, 109, 0, 0, 7, 0, 0, 31))
    data += entries.to_bytes(2, 'little')
    nbytes = (entries + 7) // 8
    data += bits + b'\x00' * (nbytes - len(bits))
    if attr10:
        data += (0).to_bytes(2, 'little')
    data += (103).to_bytes(2, 'little')
    data += (49152).to_bytes(4, 'little')
    data += (49152).to_bytes(4, 'little')
    return data


class ConnectionManagerAllTest(unittest.TestCase):
    def test_rockwell_layout(self):
        self.assertEqual(module_stats.parse_connection_manager_all(all_payload()), {
            'total_connections': 382,
            'connections_used': 11,
            'open_requests': 137,
            'cpu_utilization': 10.3,
            'max_buffer_size': 49152,
            'buffer_remaining': 49152,
        })

    def test_optional_attribute_10(self):
        result = module_stats.parse_connection_manager_all(all_payload(attr10=True))
        self.assertEqual(result['cpu_utilization'], 10.3)
        self.assertEqual(result['max_buffer_size'], 49152)
        self.assertEqual(result['buffer_remaining'], 49152)

    def test_truncated(self):
        self.assertIsNone(module_stats.parse_connection_manager_all(all_payload()[:-1]))

    def test_empty(self):
        self.assertIsNone(module_stats.parse_connection_manager_all(None))
        self.assertIsNone(module_stats.parse_connection_manager_all(b''))


if __name__ == '__main__':
    unittest.main()
