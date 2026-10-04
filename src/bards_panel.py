"""Audited SMNU record primitives for stock-shaped Bards panel resources.

The Manager owns command dispatch and visibility. This module changes only
resource identity, labels, geometry and the explicitly bound third price ID.
No widget implementation or gameplay callback is synthesized here.
"""
from __future__ import annotations

import struct

THIRD_PRICE_CONTROL = 0x7301


def records(payload: bytes) -> list[bytes]:
    if not payload or len(payload) % 4:
        raise ValueError('SMNU must be a nonempty DWORD-aligned stream')
    result, start = [], 0
    for offset in range(0, len(payload), 4):
        if payload[offset:offset + 4] == b'\xff' * 4:
            result.append(payload[start:offset + 4])
            start = offset + 4
    if start != len(payload) or result[-1] != b'\xff' * 4:
        raise ValueError('SMNU record terminator changed')
    return result


def field(record: bytes, tag: int, old: int, new: int) -> bytes:
    token = struct.pack('<II', tag, old)
    matches = [offset for offset in range(0, len(record) - 7, 4)
               if record[offset:offset + 8] == token]
    if len(matches) != 1:
        raise ValueError(f'Expected one stock SMNU property {tag:#x}/{old:#x}')
    result = bytearray(record)
    struct.pack_into('<I', result, matches[0] + 4, new)
    return bytes(result)


def control_index(items: list[bytes], control: int) -> int:
    token = struct.pack('<II', 6, control)
    matches = [index for index, record in enumerate(items)
               if any(record[offset:offset + 8] == token
                      for offset in range(0, len(record) - 7, 4))]
    if len(matches) != 1:
        raise ValueError(f'Expected one stock SMNU control {control:#x}')
    return matches[0]


def geometry(record: bytes, x: int, y: int, width=None, height=None) -> bytes:
    result = bytearray(record)
    if struct.unpack_from('<I', result, 4)[0] != 2:
        raise ValueError('Stock SMNU rectangle property changed')
    old_width, old_height = struct.unpack_from('<II', result, 16)
    struct.pack_into('<4I', result, 8, x, y,
                     old_width if width is None else width,
                     old_height if height is None else height)
    return bytes(result)
