"""Art-fitted Inactive geometry using the proven Adventurers Guild stock path.

Native IsoFootprintRectManager requests set 8, falling back to Inactive (208).
Hotspot-1 (400) is attachment metadata and must not be used for collision.
See docs/building-footprint.md for the executable trace and lifecycle.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

from cam_io import u32

SOURCE = Path(__file__).with_name('descriptions') / 'building-footprints.json'
KRYPTA_SHA256 = '1204ba0e7e44b6900fde45b5ee87311e2e3f64d6696a570521370345df88311f'
KRYPTA_RECT = (-129, 14, 157, 168)
KRYPTA_POINTS = ((16, -6), (-45, 15), (-127, 56), (-132, 127), (-44, 183),
                 (43, 129), (91, 153), (159, 108), (159, 74))


def contains_point(point, vertices):
    """Strict interior check; the native movement target must lie inside."""
    x, y = point
    inside = False
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        if (a[1] > y) != (b[1] > y):
            if x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
                inside = not inside
    return inside


def direction_geometry(chunk):
    """Native v4 masks, int16 rectangles, then counted int32 XY polygons.

    Adapted from Adventurers Guild's build_art_sources.direction_geometry.
    Preserve everything after geometry, including metadata and frame records.
    """
    if len(chunk) < 88 or u32(chunk, 0) != 1 or u32(chunk, 64) != 68:
        raise ValueError('Building footprint direction topology changed')
    direction = 68
    rectangle_mask, polygon_mask = struct.unpack_from('<II', chunk, direction + 8)
    if rectangle_mask & ~7 or polygon_mask & ~3:
        raise ValueError('Building footprint geometry masks changed')
    cursor, rectangles, polygons = direction + 20, {}, {}
    for index in range(3):
        if rectangle_mask & (1 << index):
            if cursor + 8 > len(chunk):
                raise ValueError('Building footprint rectangle is truncated')
            rectangles[index] = chunk[cursor:cursor + 8]
            cursor += 8
    for index in range(2):
        if polygon_mask & (1 << index):
            if cursor + 4 > len(chunk):
                raise ValueError('Building footprint polygon is truncated')
            count = u32(chunk, cursor)
            end = cursor + 4 + count * 8
            if count < 3 or end > len(chunk):
                raise ValueError('Building footprint polygon is invalid')
            polygons[index] = chunk[cursor:end]
            cursor = end
    frame_word = u32(chunk, direction + 4)
    frame_bytes = (frame_word >> 16) * (frame_word & 0xffff) * 8
    if frame_bytes == 0 or cursor > len(chunk) - frame_bytes:
        raise ValueError('Building footprint overlaps animation frames')
    return direction, rectangles, polygons, cursor


def validate_shape(shape):
    """Keep stock winding and reject bounds errors, crossings and duplicates."""
    points = shape['polygon_points']
    if (not 3 <= len(points) <= 32
            or any(len(p) != 2 or any(type(v) is not int or not -32768 <= v <= 32767
                                     for v in p) for p in points)
            or len({tuple(p) for p in points}) != len(points)):
        raise ValueError('Private building footprint geometry is invalid')
    if shape['rectangle'] != [min(x for x, _ in points), min(y for _, y in points),
                              max(x for x, _ in points), max(y for _, y in points)]:
        raise ValueError('Private building placement rectangle must bound its polygon')
    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    edges = list(zip(points, points[1:] + points[:1]))
    if sum(a[0] * b[1] - b[0] * a[1] for a, b in edges) >= 0:
        raise ValueError('Private building footprint winding changed')
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if j <= i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if (max(min(a[0], b[0]), min(c[0], d[0])) <= min(max(a[0], b[0]), max(c[0], d[0]))
                    and max(min(a[1], b[1]), min(c[1], d[1])) <= min(max(a[1], b[1]), max(c[1], d[1]))
                    and cross(a, b, c) * cross(a, b, d) <= 0
                    and cross(c, d, a) * cross(c, d, b) <= 0):
                raise ValueError('Private building footprint edges intersect')
    # Stock $Move(agent) can terminate at the building's own position. Keep it
    # inside the blocking shape so the stock IsAdjacent/build loop can finish.
    # The v1 art-only fit excluded (0,0), stranding a peasant at his destination.
    if not contains_point((0, 0), points):
        raise ValueError('Building movement origin must remain inside its footprint')


def load_footprints(manifest, path=SOURCE):
    result = json.loads(path.read_text(encoding='utf-8'))
    if (result['schema_version'] != 1 or result['set_id'] != 208
            or result['reference']['package'] != manifest['package']
            or result['reference']['hotspot'] != manifest['registration']['hotspot_signed']
            or set(result['levels']) != {'1', '2', '3'}):
        raise ValueError('Private building footprint source or registration changed')
    objects = {obj['key']: obj for obj in manifest['objects']}
    for level, shape in result['levels'].items():
        validate_shape(shape)
        for role in ('inactive', 'build-1'):
            if shape['reference_tiles'][role] != objects[f'level-{level}-{role}']['tile_sha256']:
                raise ValueError('Private footprint no longer matches its reference artwork')
    return result


def patch_inactive(source, stock_authority, authority_chunk, shape):
    """Replace only rect 0 and polygon data, retaining stock Krypta's mask.

    Same serializer as Adventurers Guild's apply_building_footprint. Bards'
    existing IMAG directory writer already rebuilds absolute offsets afterward.
    """
    if hashlib.sha256(stock_authority).hexdigest() != KRYPTA_SHA256:
        raise ValueError('Stock Inactive footprint authority changed')
    direction, rectangles, _, tail = direction_geometry(source)
    _, stock_rectangles, stock_polygons, _ = direction_geometry(authority_chunk)
    expected_polygon = struct.pack('<I', len(KRYPTA_POINTS)) + b''.join(
        struct.pack('<ii', *p) for p in KRYPTA_POINTS)
    if (stock_rectangles.get(0) != struct.pack('<4h', *KRYPTA_RECT)
            or stock_polygons != {0: expected_polygon} or set(rectangles) != {0, 1, 2}):
        raise ValueError('Stock Inactive footprint authority changed')
    validate_shape(shape)
    rectangles[0] = struct.pack('<4h', *shape['rectangle'])
    polygon = struct.pack('<I', len(shape['polygon_points'])) + b''.join(
        struct.pack('<ii', *p) for p in shape['polygon_points'])
    prefix = bytearray(source[:direction + 20])
    struct.pack_into('<I', prefix, direction + 12, u32(authority_chunk, direction + 12))
    return bytes(prefix) + b''.join(rectangles[i] for i in sorted(rectangles)) + polygon + source[tail:]
