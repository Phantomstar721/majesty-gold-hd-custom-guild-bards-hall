"""Approved Golden Chorus pixels in the literal stock Super Charge lifecycle."""
import hashlib
import struct
from pathlib import Path

from PIL import Image, ImageOps
from bards_building_art import decode_indices, descriptors, image as building_image
from bards_building_footprint import direction_geometry
from cam_io import Entry, get, name, section, frame_references, u32
from bards_chronicles_motion import MASTER, SIZE, CENTER, NOTE_COUNT, FRAME_COUNT, frames

ROOT = Path(__file__).resolve().parents[1]
SOURCE = b'WRF1super_charge_e'
PRIVATE = b'BCRSChronicles'
SOURCE_SHA256 = '57fb612a14df922fab9633edca411a7c51d23e7ba84ef34fd3b381a44f5e7bb7'
PALETTE = b'BCRSPalette'
# L3 body's root is (223,243), finial is approximately (251,90). Super Charge
# attaches to inherited ABH3 Hotspot-1 point 0, not the owner's body origin.
ROOT_OFFSET = (28, -153)
ATTACHMENT = (13, 14)
OFFSET = tuple(target - anchor for target, anchor in zip(ROOT_OFFSET, ATTACHMENT))


def validate_owner_attachment(imag):
    _, rectangles, _, _ = direction_geometry(descriptors(imag)[400])
    # Native attachment 1 uses point 0. Point 5 is its projection reference.
    if (struct.unpack_from('<hh', rectangles[0]) != ATTACHMENT
            or struct.unpack_from('<hh', rectangles[2]) != (0, 0)):
        raise ValueError('Chronicles owner attachment/projection anchor changed')


def frame_hotspots(pictures):
    """A fixed geometric center: orbiting glyph bounds must not move the ring."""
    for picture in pictures:
        if picture.size != SIZE or picture.mode != 'RGBA':
            raise ValueError('Golden Chorus motion canvas changed')
    hotspot = tuple(value - offset for value, offset in zip(CENTER, OFFSET))
    return [hotspot] * len(pictures)


def indexed_frames():
    pictures = frames()
    atlas = Image.new('RGB', (SIZE[0] * len(pictures), SIZE[1]))
    for i, picture in enumerate(pictures):
        atlas.paste(picture.convert('RGB'), (i*SIZE[0], 0))
    quantized = atlas.quantize(colors=246, method=Image.Quantize.MEDIANCUT,
                               dither=Image.Dither.NONE)
    colors = [(0, 0, 0)] + list(zip(*[iter(quantized.getpalette()[:738])]*3))
    colors += [(0, 0, 0)] * (256-len(colors))
    palette = struct.pack('<4H', 0, 256, 0, 0) + bytes(c for rgb in colors for c in (*rgb, 0))
    planes = []
    for picture in pictures:
        indexed = picture.convert('RGB').quantize(palette=quantized, dither=Image.Dither.NONE)
        planes.append(bytes(v+1 if a >= 80 else 0 for v, a in
                            zip(indexed.tobytes(), picture.getchannel('A').tobytes())))
    return planes, palette


def tile(template, plane, palette_index, hotspot):
    """Literal indexed TILE-v3 rows: exclusive end and low-11-bit run length."""
    header = bytearray(template[:26])
    # These rows are freshly encoded, not the original stock TILE payload.
    # Use the ordinary indexed header also used by Alchemist's private WRF1
    # writer: 0x20 external palette, normal orientation, draw mode 8 with zero
    # parameter. 0x10 is horizontal state; 0x1F00 is a draw-mode parameter.
    struct.pack_into('<5HhhH', header, 0, 3, SIZE[1], SIZE[0], 0, 32, *hotspot, 8)
    struct.pack_into('<H', header, 16, 0)
    struct.pack_into('<HI', header, 20, 0, palette_index)
    rows, offsets = bytearray(), bytearray()
    for y in range(SIZE[1]):
        offsets += struct.pack('<I', 4*SIZE[1]+len(rows))
        row = plane[y*SIZE[0]:(y+1)*SIZE[0]]
        runs, x = [], 0
        while x < SIZE[0]:
            if not row[x]:
                x += 1
                continue
            start = x
            while x < SIZE[0] and row[x]: x += 1
            runs.append((x, row[start:x]))
        if not runs: runs = [(0, b'')]
        for i, (end, pixels) in enumerate(runs):
            rows += struct.pack('<HH', end, len(pixels) | (0x8000 if i == len(runs)-1 else 0)) + pixels
    return bytes(header+offsets+rows)


def append_art(stock, tiles, palettes):
    source = get(stock, b'IMAG', SOURCE)
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('Stock Super Charge animation changed')
    validate_owner_attachment(building_image(stock, b'ABH3'))
    image = bytearray(source)
    original_tiles = section(stock, b'TILE').entries
    planes, palette = indexed_frames()
    palette_index = len(palettes)
    palettes.append(Entry(name(PALETTE), palette))
    refs = frame_references(source, 64)
    if len(refs) != 60: raise ValueError('Stock 30-frame/two-stream loop changed')
    hotspots = frame_hotspots(frames())
    for occurrence, offset in enumerate(refs):
        reference = u32(source, offset)
        stream, frame = divmod(occurrence, 30)
        flags = reference >> 16
        if flags & ~0x6000: raise ValueError('Unknown stock effect transform')
        # Stream 1 is hidden (0x4000) for frames 0..6, not vertically flipped.
        # Keep the complete approved art in always-visible stream 0; preserve
        # the stock companion stream/flags with transparent private payloads.
        plane = planes[frame] if stream == 0 else bytes(SIZE[0]*SIZE[1])
        raster = Image.frombytes('L', SIZE, bytes(plane))
        hotspot = list(hotspots[frame])
        if flags & 0x2000:
            raster = ImageOps.mirror(raster)
            # Native hotspots reflect as W-x, while pixels reflect as W-1-x.
            hotspot[0] = SIZE[0]-hotspot[0]
        payload = tile(original_tiles[reference & 65535].data, raster.tobytes(), palette_index, hotspot)
        if len(tiles) >= 65536: raise ValueError('Chronicles TILE exceeds native low16')
        struct.pack_into('<I', image, offset, (reference & 0xffff0000) | len(tiles))
        tiles.append(Entry(name(f'BCRS{stream}{frame:02d}'.encode()), payload))
    return Entry(name(PRIVATE), bytes(image)), {
        'stock': SOURCE.decode(), 'stock_sha256': SOURCE_SHA256,
        'source': MASTER.relative_to(ROOT).as_posix(),
        'source_sha256': hashlib.sha256(MASTER.read_bytes()).hexdigest(),
        'offset': list(OFFSET), 'frames': 30, 'streams': 2, 'palette_index': palette_index,
        'owner_root_offset': list(ROOT_OFFSET), 'attachment_point': list(ATTACHMENT),
        'visible_payload_stream': 0, 'companion_stream': 'transparent; stock visibility flags retained',
        'frame_hotspots': [list(point) for point in hotspots],
        'motion': {'fixed_center': list(CENTER), 'identical_notes': NOTE_COUNT,
                   'degrees_per_frame': 360 / (NOTE_COUNT * FRAME_COUNT),
                   'loop': 'quarter orbit; identical notes exchange slots at wrap',
                   'playback': 'unmodified stock WRF1'},
    }


def validate_art(stock, output):
    validate_owner_attachment(building_image(output, b'BDG3'))
    tiles = list(section(output, b'TILE').entries)
    actual = get(output, b'IMAG', PRIVATE)
    refs = frame_references(actual, 64)
    first = min(u32(actual, p) & 65535 for p in refs)
    palettes = list(section(output, b'SPLT').entries)
    pindex = next(i for i, p in enumerate(palettes) if p.name.rstrip(b'\0') == PALETTE)
    expected_tiles, expected_palettes = tiles[:first], palettes[:pindex]
    expected, _ = append_art(stock, expected_tiles, expected_palettes)
    if expected.data != actual or expected_tiles[first:] != tiles[first:len(expected_tiles)] or expected_palettes != palettes[:len(expected_palettes)]:
        raise ValueError('Golden Chorus native art differs from its source/registration')
    restored = bytearray(actual)
    original = get(stock, b'IMAG', SOURCE)
    for offset in refs: restored[offset:offset+4] = original[offset:offset+4]
    if bytes(restored) != original: raise ValueError('Chronicles changed stock playback lifecycle')
    for entry in tiles[first:len(expected_tiles)]:
        decode_indices(entry.data, size=SIZE, hotspot=struct.unpack_from('<hh', entry.data, 10))
