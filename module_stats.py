"""Parsing helpers for the CIP Connection Manager object (class 0x06)."""


def parse_uint(value):
    if not value or len(value) < 2:
        return None
    return int.from_bytes(value[:2], 'little')


def parse_udint(value):
    if not value or len(value) < 4:
        return None
    return int.from_bytes(value[:4], 'little')


def cpu_percent(value):
    raw = parse_uint(value)
    return None if raw is None else raw / 10.0


def parse_connection_entry_list(value):
    """Returns (total_entries, used_entries) from attr 9 of class 0x06."""
    if not value or len(value) < 2:
        return None, None
    total = int.from_bytes(value[:2], 'little')
    nbytes = (total + 7) // 8
    bits = bytes(value[2:2 + nbytes])
    if len(bits) < nbytes:
        return total, None
    remainder = total % 8
    if remainder and bits:
        bits = bits[:-1] + bytes([bits[-1] & ((1 << remainder) - 1)])
    used = sum(byte.bit_count() for byte in bits)
    return total, used


def parse_connection_manager_all(value):
    """Parses a class 0x06 Get_Attributes_All response.

    Layout used by Rockwell ControlNet modules: attrs 1-8 (UINT), attr 9
    (entry list), optional attr 10 (UINT), attr 11 (UINT), attr 12/13 (UDINT).
    """
    if not value:
        return None
    data = bytes(value)
    if len(data) < 28:
        return None
    entries = parse_uint(data[16:18])
    if entries is None:
        return None
    nbytes = (entries + 7) // 8
    pos = 18 + nbytes
    if len(data) == pos + 10:
        cpu_pos = pos
    elif len(data) == pos + 12:
        cpu_pos = pos + 2
    else:
        return None
    total, used = parse_connection_entry_list(data[16:pos])
    cpu = parse_uint(data[cpu_pos:cpu_pos + 2])
    return {
        'total_connections': total,
        'connections_used': used,
        'open_requests': parse_uint(data[0:2]),
        'cpu_utilization': None if cpu is None else cpu / 10.0,
        'max_buffer_size': parse_udint(data[cpu_pos + 2:cpu_pos + 6]),
        'buffer_remaining': parse_udint(data[cpu_pos + 6:cpu_pos + 10]),
    }
