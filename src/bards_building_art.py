"""Integrate approved indexed art using literal stock building descriptors."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

from PIL import Image
from cam_io import Entry, get, name, section, u32
from bards_building_footprint import load_footprints, patch_inactive

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / 'art/building/bards-guild-v1/handoff/bards-guild-west-shadows-r1-v1'
MANIFEST_SHA256 = 'dc092c802198e6b7fbe14a783bfc9cb7d5c9bf744e133be652ffee98b75c3ea5'
ARCHIVE_SHA256 = '7e26cd25f91f247bf306db99652314bd70b5dbb9838f179b9f355a705a981d9f'
PALETTE_NAME = b'BDG1BuildingPalette'
# The cleanup handoff is already at the approved in-game size. Preserve its
# encoded native bytes; applying the earlier 5:4 transform again is incorrect.
SOURCE_SIZE = WORLD_SIZE = (480, 480)
SOURCE_HOTSPOT = WORLD_HOTSPOT = (223, 243)


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_handoff():
    require(digest((HANDOFF / 'manifest.json').read_bytes()) == MANIFEST_SHA256,
            'Building handoff manifest changed')
    require(digest(HANDOFF.with_suffix('.zip').read_bytes()) == ARCHIVE_SHA256,
            'Building handoff archive changed')
    manifest = json.loads((HANDOFF / 'manifest.json').read_text())
    files = manifest['files']
    actual = {p.relative_to(HANDOFF).as_posix() for p in HANDOFF.rglob('*') if p.is_file()}
    require(actual == set(files) | {'manifest.json'}, 'Missing or unlisted building handoff file')
    aggregate = []
    for relative, record in sorted(files.items()):
        path = (HANDOFF / relative).resolve()
        require(path.is_relative_to(HANDOFF.resolve()), 'Building handoff path escapes package')
        payload = path.read_bytes()
        require(len(payload) == record['bytes'] and digest(payload) == record['sha256'],
                f'Building handoff file changed: {relative}')
        aggregate.append(f"{relative}\t{record['bytes']}\t{record['sha256']}\n")
    require(digest(''.join(aggregate).encode()) == manifest['aggregate_sha256'], 'Building aggregate changed')
    require(len(manifest['objects']) == 61, 'Expected 61 approved building objects')
    require(manifest['registration']['canvas'] == list(SOURCE_SIZE)
            and manifest['registration']['hotspot_signed'] == list(SOURCE_HOTSPOT)
            and manifest['registration']['receiver_scale'] == [1, 1],
            'The approved cleanup handoff must be consumed at its final native size')
    require(all(obj['canvas'] == list(SOURCE_SIZE) and obj['hotspot_signed'] == list(SOURCE_HOTSPOT)
                for obj in manifest['objects']), 'Building objects do not share the approved registration')
    mapping = json.loads((HANDOFF / manifest['mapping']).read_text())
    return manifest, mapping


def image(stock, prefix):
    return next(e.data for e in section(stock, b'IMAG').entries if e.name.startswith(prefix))


def descriptors(blob):
    count = u32(blob, 20)
    table = [struct.unpack_from('<II', blob, 24 + i * 8) for i in range(count)]
    require(table[0][1] == 24 + count * 8, 'Unexpected IMAG table gap')
    require([offset for _, offset in table] == sorted({offset for _, offset in table}),
            'Unexpected IMAG set order')
    return {key: blob[start:table[i + 1][1] if i + 1 < count else len(blob)]
            for i, (key, start) in enumerate(table)}


def frame_words(descriptor, direction=0, stream=0):
    directions = u32(descriptor, 0)
    require(0 <= direction < directions <= 32, 'Invalid direction count')
    pointers = [u32(descriptor, 64 + i * 4) for i in range(directions)]
    begin = pointers[direction]
    end = pointers[direction + 1] if direction + 1 < directions else len(descriptor)
    count = u32(descriptor, begin + 4)
    frames, streams = count >> 16, count & 65535
    require(frames > 0 and 0 <= stream < streams, 'Invalid frame/stream count')
    start = end - frames * streams * 8 + stream * frames * 8
    require(start >= begin + 8, 'Invalid frame table')
    return begin, tuple(start + i * 8 for i in range(frames))


def patch_stream(descriptor, row, indices):
    result = bytearray(descriptor)
    direction, offsets = frame_words(result, row['direction'], row['stream'])
    require(list(struct.unpack_from('<hh', result, direction)) == row['direction_anchor'],
            'Approved direction anchor differs from stock')
    require(len(offsets) == len(row['objects']) and row['holds'] == [1] * len(offsets),
            'Approved occurrences do not match stock playback frames')
    for offset, obj, metadata in zip(offsets, row['objects'], row['frame_metadata']):
        require(u32(result, offset) == metadata, 'Approved frame metadata differs from stock')
        require(indices[obj] < 65536, 'Private TILE index exceeds native reference field')
        struct.pack_into('<I', result, offset + 4, (u32(result, offset + 4) & 0xffff0000) | indices[obj])
    return bytes(result)


def template_sets(stock, level, ui):
    market = image(stock, f'ABH{level}'.encode())
    sets = descriptors(market)
    # Higher Marketplace tiers also contain special event flags. This guild
    # uses only event zero; no inherited special-event actors are retained.
    sets = {key: value for key, value in sets.items() if key & 0xffffff not in (193, 194)}
    sets[192] = descriptors(image(stock, b'ABY1'))[192]
    sets[0x010000c0] = descriptors(image(stock, b'ABV1'))[0x010000c0]
    for key in (1000, 1002):
        sets[key] = descriptors(ui)[key]
    return market[:20], sets


def make_images(stock, ui, mapping, indices):
    manifest, _ = load_handoff()
    footprints = load_footprints(manifest)
    authority = image(stock, b'ABT1')
    authority_inactive = descriptors(authority)[208]
    result = []
    for level in (1, 2, 3):
        header, sets = template_sets(stock, level, ui)
        for row in mapping['sets']:
            if row['level'] == level:
                sets[row['set']] = patch_stream(sets[row['set']], row, indices)
        # Hotspot-1 is attachment data, not the native blocking polygon.
        sets[400] = patch_stream(sets[400], {
            'direction': 0, 'stream': 0, 'direction_anchor': [0, 0],
            'objects': [f'level-{level}-inactive'], 'holds': [1], 'frame_metadata': [0],
        }, indices)
        require(8 not in sets, 'Unexpected footprint override before Inactive fallback')
        sets[208] = patch_inactive(sets[208], authority, authority_inactive,
                                   footprints['levels'][str(level)])
        offset = 24 + 8 * len(sets)
        table = bytearray()
        for key, payload in sets.items():
            table.extend(struct.pack('<II', key, offset))
            offset += len(payload)
        result.append(Entry(name(f'BDG{level}Bards Hall'.encode()),
                            header + struct.pack('<I', len(sets)) + table + b''.join(sets.values())))
    return result


def object_name(obj):
    return name(f"BDG{obj['level']}{obj['role']}".encode())


def append_buildings(stock, tiles, palettes, ui):
    manifest, mapping = load_handoff()
    require(digest(section(stock, b'SPLT').entries[0].data) == manifest['palettes']['0']['sha256'],
            'Stage stock palette dependency changed')
    palette_index = len(palettes)
    palettes.append(Entry(name(PALETTE_NAME), (HANDOFF / 'palette/bards-building.splt').read_bytes()))
    indices = {}
    for obj in manifest['objects']:
        payload = bytearray((HANDOFF / obj['tile_path']).read_bytes())
        require(u32(payload, 22) == obj['palette_ref'], 'Approved TILE palette reference changed')
        if obj['palette_ref'] == 0xffffffff:
            struct.pack_into('<I', payload, 22, palette_index)
        else:
            require(obj['palette_ref'] == 0, 'Unknown stage palette dependency')
        indices[obj['key']] = len(tiles)
        tiles.append(Entry(object_name(obj), bytes(payload)))
    require(set(indices) == {key for row in mapping['sets'] for key in row['objects']},
            'Missing or unused approved building object')
    return make_images(stock, ui, mapping, indices), {
        'package': manifest['package'], 'manifest_sha256': MANIFEST_SHA256,
        'body_palette_index': palette_index, 'objects': len(indices),
        'activity_frames': {'windows': 8, 'stage': 6},
        'stock_damage_and_attachment_auxiliaries': 'Marketplace level 1/2/3',
        'footprint': {'source': 'src/descriptions/building-footprints.json',
                      'revision': load_footprints(manifest)['revision'],
                      'ownership': 'native Inactive rectangle 0 and polygon 0',
                      'stock_layout': 'Temple to Krypta single polygon; Adventurers Guild method'},
        'world_art_scale': 1.25, 'receiver_scale': [1, 1], 'world_canvas': list(WORLD_SIZE),
        'world_hotspot': list(WORLD_HOTSPOT),
        'scale_filter': 'none: approved native TILE bytes; palette-reference relocation only',
        'native_gameplay_review': 'pending',
    }


def decode_indices(payload, *, size=SOURCE_SIZE, hotspot=SOURCE_HOTSPOT):
    """Stock TILE-v3 indexed RLE: exclusive x-end and low-11-bit run length."""
    version, height, width = struct.unpack_from('<3H', payload)
    require(version == 3 and (width, height) == size, 'Unexpected building TILE canvas')
    require(struct.unpack_from('<hh', payload, 10) == hotspot, 'Building hotspot changed')
    require(struct.unpack_from('<H', payload, 20)[0] == 0, 'Building palette must be external')
    plane = bytearray(width * height)
    offsets = [26 + u32(payload, 26 + y * 4) for y in range(height)]
    for y, start in enumerate(offsets):
        end = offsets[y + 1] if y + 1 < height else len(payload)
        require(26 + height * 4 <= start <= end <= len(payload), 'Invalid RLE row offset')
        x_previous = 0
        while True:
            require(start + 4 <= end, 'Truncated RLE row')
            x_end, packed = struct.unpack_from('<HH', payload, start)
            count = packed & 2047
            start += 4
            require(x_previous <= x_end - count <= x_end <= width and start + count <= end,
                    'Invalid RLE run')
            plane[y * width + x_end - count:y * width + x_end] = payload[start:start + count]
            start += count
            x_previous = x_end
            if packed & 32768:
                require(start == end, 'Trailing RLE bytes')
                break
    return bytes(plane)


def validate_buildings(stock, output):
    manifest, mapping = load_handoff()
    palettes, tiles = section(output, b'SPLT').entries, section(output, b'TILE').entries
    palette_index = next(i for i, entry in enumerate(palettes) if entry.name.rstrip(b'\0') == PALETTE_NAME)
    require(palette_index >= len(section(stock, b'SPLT').entries), 'Building palette overwrites stock')
    require(palettes[palette_index].data == (HANDOFF / 'palette/bards-building.splt').read_bytes(),
            'Private building palette changed')
    require(digest(palettes[0].data) == manifest['palettes']['0']['sha256'], 'Stage palette changed')
    tile_lookup = {entry.name: (i, entry.data) for i, entry in enumerate(tiles)}
    indices = {}
    for obj in manifest['objects']:
        index, payload = tile_lookup[object_name(obj)]
        require(index >= len(section(stock, b'TILE').entries), 'Building TILE overwrites stock')
        original = (HANDOFF / obj['tile_path']).read_bytes()
        expected_palette = palette_index if obj['palette_ref'] == 0xffffffff else 0
        require(u32(payload, 22) == expected_palette and payload[:22] == original[:22]
                and payload[26:] == original[26:], 'Building TILE changed outside palette-reference relocation')
        with Image.open(HANDOFF / obj['indexed_path']) as approved:
            require(approved.mode == 'P' and approved.size == SOURCE_SIZE, 'Invalid approved indexed PNG')
            require(decode_indices(original) == approved.tobytes(), 'Source building indices differ from approval')
            require(decode_indices(payload) == approved.tobytes(),
                    'Integrated building differs from the approved final-size indexed plane')
        indices[obj['key']] = index
    # Expected stock descriptors include the untouched auxiliary stream of
    # Disappear, fire attachments and frame metadata, plus the art-fitted
    # Inactive rectangle/polygon through the stock footprint mechanism.
    ui = get(output, b'IMAG', b'BDG1Bards Hall')
    for expected in make_images(stock, ui, mapping, indices):
        require(get(output, b'IMAG', expected.name.rstrip(b'\0')) == expected.data,
                'Building lifecycle descriptor or approved occurrence mapping changed')
