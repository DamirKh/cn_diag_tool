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
