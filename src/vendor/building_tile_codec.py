"""Unmodified TILE-v3 writer used by the approved Bards building-art pipeline.

Authority: majesty-gold-hd-custom-guild-phantoms-haunt/src/build_phantom_guild.py
Function SHA-256: ad19d2af2ae0620d61b3e4fbf8b39d8d6bd7126b97ce326ed5b56d5f04360ebe
Keep this codec literal; perform Bards geometry changes in bards_building_art.py.
"""
import struct


def encode_indexed_v3_tile_like_original(
    original_tile: bytes,
    pixels: list[list[int]],
    *,
    split_shadow_controls: bool = False,
) -> bytes:
    if len(original_tile) < 26 or struct.unpack_from("<H", original_tile, 0)[0] != 3:
        return original_tile

    height = len(pixels)
    width = len(pixels[0]) if pixels else 0
    header = bytearray(original_tile[:26])
    struct.pack_into("<H", header, 2, height)
    struct.pack_into("<H", header, 4, width)
    struct.pack_into("<H", header, 6, width)

    rows: list[bytes] = []
    for row_pixels in pixels:
        row = bytearray()
        x = 0
        row_width = len(row_pixels)
        while x < row_width:
            if row_pixels[x] == 0:
                x += 1
                continue

            start = x
            values: list[int] = []
            segment_is_shadow = 247 <= row_pixels[x] <= 250
            while x < row_width and row_pixels[x] != 0 and len(values) < 80:
                value_is_shadow = 247 <= row_pixels[x] <= 250
                if split_shadow_controls and values and value_is_shadow != segment_is_shadow:
                    break
                values.append(row_pixels[x])
                x += 1

            next_x = x
            while next_x < row_width and row_pixels[next_x] == 0:
                next_x += 1
            flags = 0 if next_x < row_width else 0x80
            row += struct.pack("<HBB", start + len(values), len(values), flags)
            row += bytes(values)

        if not row:
            row += struct.pack("<HBB", 0, 0, 0x80)
        rows.append(bytes(row))

    output = bytearray(header)
    cursor = height * 4
    for row in rows:
        output += struct.pack("<I", cursor)
        cursor += len(row)
    for row in rows:
        output += row

    palette_mode = struct.unpack_from("<H", original_tile, 20)[0]
    original_palette_offset = struct.unpack_from("<I", original_tile, 22)[0]
    if palette_mode == 1 and 0 <= original_palette_offset < len(original_tile):
        new_palette_offset = len(output)
        struct.pack_into("<I", output, 22, new_palette_offset)
        output += original_tile[original_palette_offset:]

    return bytes(output)
