#!/usr/bin/env python3
"""Build the stock-Healer-derived Troubadour hero-art package.

This builder is intentionally repo-contained and fail-closed.  It consumes the
tracked approved custom-art handoff, validates a locally owned retail
``maindata.cam``, clones the Healer IMAG topology byte-for-byte, changes only
the 341 authorized low16 TILE references, and publishes a fresh staged package.

It never installs the package and never starts Majesty.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Sequence
import uuid
import xml.etree.ElementTree as ET

try:
    import PIL
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Pillow 11.3.0 is required; use the workspace Python") from exc


REPO = Path(__file__).resolve().parents[1]
RETAIL_CAM = REPO / "working/majesty-authority/Data/maindata.cam"
RETAIL_CAM_SIZE = 91_599_348
RETAIL_CAM_SHA256 = "92b1a4caa111495aebe483e5617c7cc4f291eb1d897877860cfbdbc632a0d213"
HANDOFF = REPO / "assets/source/approved-troubadour-sprite-set-v1"
HANDOFF_MANIFEST_SHA256 = "790c9bf9159bdee50e34c1ed3169fa56a3c773de6c7a4bc0aa2a111b43a2e057"
HANDOFF_CANONICAL_SHA256 = "9911dba07cfe5f8e95025f2ffa84e1034777de96c4687e9b59af7d75f1edf00f"
HANDOFF_PAYLOAD_AGGREGATE = "891ed025c3584b029820fa373ec83b08929782469f21ac02ff73b9758ec90eb2"
PACKAGE_AUTHORITY = REPO / "reference/healer-package-authority-v2.json"
PACKAGE_AUTHORITY_SIZE = 911_803
PACKAGE_AUTHORITY_SHA256 = "43cffc5ae0053c58c6c4104d6db8fd2fb67f74357628e79a9537baada7ea68eb"
PACKAGE_AUTHORITY_CANONICAL = "4101d6b78e6eef733de51fafc0c14a1ce02475e7fe510401434da789d197890d"
APPROVAL = REPO / "checkpoints/indexed-sprite-set-v1-approved.json"
APPROVAL_SIZE = 6_889
APPROVAL_SHA256 = "1ceb9610fb85e98fa2413705e16c7c508234a14326814cd2b48b48d14366662c"
DEFAULT_OUTPUT = REPO / "dist/CustomGuildTroubadour"

CAM_MAGIC = b"CYLBPC  \x01\x00\x01\x00"
CAM_HEADER_SIZE = 20
CAM_DIR_ENTRY_SIZE = 8
CAM_SECTION_HEADER_SIZE = 8
CAM_ENTRY_HEADER_SIZE = 28
RETAIL_SECTION_CONTRACT = (
    (b"IMAG", 52, 380, b"\x00\x00\x00\x00"),
    (b"TILE", 10_700, 17_224, b"\x01\x00\x00\x00"),
    (b"SPLT", 492_980, 854, b"\x01\x00\x00\x00"),
    (b"CUT ", 516_900, 20, b"\x01\x00\x00\x00"),
)
HEALER_IMAG_NAME = b"AVD1Healer"
HEALER_IMAG_INDEX = 146
HEALER_IMAG_OFFSET = 1_131_164
HEALER_IMAG_SIZE = 6_912
HEALER_IMAG_SHA256 = "fe3c003952b2139005ecc534d781b64d853fd7602eaef1093137fe7f8f8db5fd"
PRIVATE_IMAG_NAME = b"TRB1Troubadour"
PRIVATE_SPLT_INDEX = 854
PRIVATE_SPLT_NAME = b"TRB1WorldPalette"
PRIVATE_SPLT_SHA256 = "6f2d32556d535e55750f8bc3086657301bb4b72c97affdaef7330bb2dd1db969"
RETAIL_TILE_COUNT = 17_224
RETAIL_SPLT_COUNT = 854
WORLD_FIRST = 17_224
WORLD_COUNT = 337
PROFILE_INDEX = 17_561
ICON_INDEX = 17_562
PANEL_INDEX = 17_563
PACKAGE_TILE_COUNT = 17_564
PACKAGE_SPLT_COUNT = 855
PROFILE_STOCK_INDEX = 4_370
ICON_STOCK_INDEX = 4_376
PANEL_STOCK_INDEX = 4_377
PANEL_STOCK_SHA256 = "7ba9b81789b4791100981817c68921251dc00a9f51ccbc46977b29db9c45e077"
PANEL_STOCK_SPLT = 378
MINIMAP_STOCK_INDEX = 3_729
SET400_STOCK_INDEX = 4_145
CAST_SECONDARY_SHA256 = "ea6faf508392a31749e16dff7fa79ec8f3b1281de82c883b056f3c661fe0fe5c"
AUTHORIZED_OFFSETS_SHA256 = "d53eb214cc1fc91ecf346a468fbed4dcbfa01f7717fc44055260c3c49ebdb278"
AUTHORIZED_STOCK_WORDS_SHA256 = "5cdff423d4b43c778886223d14df93b3f49ab1002b6d248d730c36f2f192cbf0"
AUTHORIZED_MASK_SHA256 = "9fe109435bba2d6e62b0a5e5495a819df34ec71a098d38bdbfb99b9963754278"
LOW16_ZEROED_IMAG_SHA256 = "e36dc7e6fe928e74e3ae0989fc48fdd72ee743db6abd4b093152626417c37deb"

PACKAGE_SCHEMA = "majesty-troubadour-sprite-package/v1"
PACKAGE_ID = "CustomGuildTroubadour"
PACKAGE_MMXML = "CustomGuildTroubadour.mmxml"
PACKAGE_CAM = "Data/troubadour_maindata.cam"
PACKAGE_MANIFEST = "TroubadourSpritePackage.json"
PACKAGE_UUID = "66f794aa-bcc3-5910-85c6-2da8fd4fa3a0"
EXPECTED_MMXML = f"""<Majesty>
\t<Mod id=\"{{{PACKAGE_UUID}}}\">
\t\t<Name>CustomGuildTroubadour</Name>
\t\t<DisplayName lang=\"en_US\">Custom Guild: Troubadour Hero Art</DisplayName>
\t\t<Description lang=\"en_US\">
\t\t\t<Short>Provides the approved private Troubadour hero sprite resources.</Short>
\t\t\t<Long>Stock-Healer-derived art package for Original Majesty and the Northern Expansion.</Long>
\t\t</Description>
\t\t<DataConfiguration>
\t\t\t<Dataset base=\"Any\">
\t\t\t\t<Load>
\t\t\t\t\t<CAM>Data\\troubadour_maindata.cam</CAM>
\t\t\t\t</Load>
\t\t\t</Dataset>
\t\t</DataConfiguration>
\t</Mod>
</Majesty>
"""

PROFILE_SOURCE_PNG = "interface/troubadour-profile-100x100.png"
ICON_SOURCE_PNG = "interface/troubadour-hero-count-icon-25x25.png"
PROFILE_SOURCE_RGB_SHA256 = "2f20dc03ee1a9f167da246ce555194cda59cb16bea827440d4387f1504e1d42f"
ICON_SOURCE_RGB_SHA256 = "6fa92cd55067292f832d8ac2040ca5815c2605570888fd13ae2860fe68657687"
EMBEDDED_SPLT_HEADER = b"\x00\x00\x00\x01\x00\x00\x00\x00"
VISIBLE_UI_COLOURS = 254
TRANSPARENT_UI_INDEX = 255
INTERFACE_TILE_AUTHORITY = {
    "profile": {
        "source_stock_tile_sha256": "fe83ab8307073c56488a9dc555a577024ad189b9e40458b5e6a7a2982ab1439c",
        "source_stock_header_sha256": "ec767a22baf1d4c545efde4780ad6c63ff6100e719eb40b440fa5e7dad64b634",
        "source_unique_rgb_count": 4_949,
        "weighted_distance_sq_mean": 18.7003,
        "weighted_distance_sq_max": 546,
        "index_plane_sha256": "1a59ab2849aae0886021bbd15475517d06c3b18ed49cbb14a0aa83bc138f08f4",
        "palette_block_sha256": "2319f433da39f4284d6db2dc82d7becb417d3c7c7ef0bef81b133aa1c5c2c7be",
        "visible_palette_rgb_sha256": "0fdd8f42b46142f6ed898263806cde47f66e1824e3b2881392a72da7eb27aa0e",
        "decoded_rgb_sha256": "ee74490ad652be92e9f53a8ab4ae015c576d1b4681a119d2a71985aed5fc1ed6",
        "tile_size": 11_058,
        "tile_sha256": "9c7d4a0a4cc67872dd0bb609dd5205ffd5d9f1375c6cc6b685c88e6becfb7d12",
    },
    "icon": {
        "source_stock_tile_sha256": "831e928073d38e9b6cba66cdc8515887fd9ab193546b28ac47578252f9f35435",
        "source_stock_header_sha256": "86f4a6769d6dc91b2823b843100c678755848d74dc56e98ed4ec59fd8ebe38c8",
        "source_unique_rgb_count": 549,
        "weighted_distance_sq_mean": 7.192,
        "weighted_distance_sq_max": 71,
        "index_plane_sha256": "a4f84d730eeb54385c5e6085a2cb2263f814630d4ea0018a85d9b76a472e364c",
        "palette_block_sha256": "f2121dc7c6c038c0208676091de16ad64a1c07ec0371abde821de79ba6c1a63f",
        "visible_palette_rgb_sha256": "dfbdec157d9b48966b056758b20f949ee3080c1cb2c0185c9094a32e77043787",
        "decoded_rgb_sha256": "772706a63f3e70bb2fa446ac37c37ffae463b48becc0c59446d3bf14187fd9e0",
        "tile_size": 1_683,
        "tile_sha256": "1ba5a0c29564be5201282814e77c47360c46eef35dc73b80ffa6d22635e58737",
    },
}


@dataclass(frozen=True)
class CamEntryIndex:
    name: bytes
    payload_offset: int
    payload_size: int
    entry_header_offset: int


@dataclass(frozen=True)
class CamSectionIndex:
    extension: bytes
    section_offset: int
    padding: bytes
    entries: tuple[CamEntryIndex, ...]


@dataclass(frozen=True)
class CamEntry:
    name: bytes
    data: bytes


@dataclass(frozen=True)
class CamSection:
    extension: bytes
    padding: bytes
    entries: tuple[CamEntry, ...]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def require_file(path: Path, size: int, digest: str, label: str) -> None:
    require(path.is_file(), f"missing {label}: {path}")
    require(path.stat().st_size == size, f"{label} size changed")
    require(sha256_file(path) == digest, f"{label} SHA-256 changed")


def pad_name(name: bytes) -> bytes:
    require(len(name) <= 20 and b"\x00" not in name, f"invalid CAM name: {name!r}")
    return name.ljust(20, b"\x00")


def canonical_hash(value: dict[str, Any]) -> str:
    clone = json.loads(json.dumps(value))
    clone["canonical_sha256"] = "0" * 64
    payload = json.dumps(clone, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return sha256_bytes(payload)


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def parse_cam(data: bytes) -> tuple[CamSectionIndex, ...]:
    require(data[:12] == CAM_MAGIC, "retail CAM magic changed")
    section_count, content_header_size = struct.unpack_from("<II", data, 12)
    require(section_count == 4, f"retail CAM section count changed: {section_count}")
    directory: list[tuple[bytes, int]] = []
    cursor = CAM_HEADER_SIZE
    for _ in range(section_count):
        extension = data[cursor : cursor + 4]
        offset = struct.unpack_from("<I", data, cursor + 4)[0]
        directory.append((extension, offset))
        cursor += CAM_DIR_ENTRY_SIZE
    expected_header_size = sum(
        CAM_SECTION_HEADER_SIZE + count * CAM_ENTRY_HEADER_SIZE
        for _extension, _offset, count, _padding in RETAIL_SECTION_CONTRACT
    )
    require(content_header_size == expected_header_size, "retail CAM content-header size changed")
    sections: list[CamSectionIndex] = []
    for ordinal, ((extension, section_offset), expected) in enumerate(zip(directory, RETAIL_SECTION_CONTRACT)):
        expected_extension, expected_offset, expected_count, expected_padding = expected
        require((extension, section_offset) == (expected_extension, expected_offset), f"retail section directory changed at {ordinal}")
        count = struct.unpack_from("<I", data, section_offset)[0]
        padding = data[section_offset + 4 : section_offset + 8]
        require((count, padding) == (expected_count, expected_padding), f"retail {extension!r} header changed")
        cursor = section_offset + CAM_SECTION_HEADER_SIZE
        entries: list[CamEntryIndex] = []
        for _ in range(count):
            name = data[cursor : cursor + 20]
            payload_offset, payload_size = struct.unpack_from("<II", data, cursor + 20)
            require(payload_offset + payload_size <= len(data), f"retail {extension!r} payload out of bounds")
            entries.append(CamEntryIndex(name, payload_offset, payload_size, cursor))
            cursor += CAM_ENTRY_HEADER_SIZE
        sections.append(CamSectionIndex(extension, section_offset, padding, tuple(entries)))
    return tuple(sections)


def entry_data(data: bytes, entry: CamEntryIndex) -> bytes:
    return data[entry.payload_offset : entry.payload_offset + entry.payload_size]


def find_entry(section: CamSectionIndex, name: bytes) -> tuple[int, CamEntryIndex]:
    matches = [(index, entry) for index, entry in enumerate(section.entries) if entry.name.rstrip(b"\x00") == name]
    require(len(matches) == 1, f"expected one {section.extension!r}/{name!r}, found {len(matches)}")
    return matches[0]


def write_cam(path: Path, sections: Sequence[CamSection]) -> None:
    section_count = len(sections)
    file_header_size = CAM_HEADER_SIZE + section_count * CAM_DIR_ENTRY_SIZE
    content_header_size = sum(CAM_SECTION_HEADER_SIZE + len(section.entries) * CAM_ENTRY_HEADER_SIZE for section in sections)
    payload_cursor = file_header_size + content_header_size
    payload_offsets: list[list[int]] = []
    for section in sections:
        offsets: list[int] = []
        for entry in section.entries:
            require(len(entry.name) == 20, "CAM entry name is not padded to 20 bytes")
            offsets.append(payload_cursor)
            payload_cursor += len(entry.data)
        payload_offsets.append(offsets)

    output = bytearray(CAM_MAGIC)
    output.extend(struct.pack("<II", section_count, content_header_size))
    section_cursor = file_header_size
    for section in sections:
        require(len(section.extension) == 4 and len(section.padding) == 4, "invalid CAM section shape")
        output.extend(section.extension)
        output.extend(struct.pack("<I", section_cursor))
        section_cursor += CAM_SECTION_HEADER_SIZE + len(section.entries) * CAM_ENTRY_HEADER_SIZE
    for section_index, section in enumerate(sections):
        output.extend(struct.pack("<I", len(section.entries)))
        output.extend(section.padding)
        for entry_index, entry in enumerate(section.entries):
            output.extend(entry.name)
            output.extend(struct.pack("<II", payload_offsets[section_index][entry_index], len(entry.data)))
    for section in sections:
        for entry in section.entries:
            output.extend(entry.data)
    require(len(output) == payload_cursor, "CAM writer byte count changed")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(output)


def parse_splt(payload: bytes, label: str) -> list[tuple[int, int, int]]:
    require(len(payload) == 1_032 and payload[:8] == EMBEDDED_SPLT_HEADER, f"invalid SPLT: {label}")
    colours: list[tuple[int, int, int]] = []
    for index in range(256):
        offset = 8 + index * 4
        require(payload[offset + 3] == 0, f"nonzero SPLT fourth byte: {label}/{index}")
        colours.append(tuple(payload[offset : offset + 3]))
    return colours


def tile_header(payload: bytes) -> dict[str, int]:
    require(len(payload) >= 26, "truncated TILE")
    values = struct.unpack_from("<10H", payload, 0)
    return {
        "version": values[0],
        "height": values[1],
        "width": values[2],
        "row_stride": values[3],
        "word4": values[4],
        "hotspot_x": values[5],
        "hotspot_y": values[6],
        "word7": values[7],
        "transparent_index": values[8],
        "word9": values[9],
        "palette_mode": struct.unpack_from("<H", payload, 20)[0],
        "palette_ref": struct.unpack_from("<I", payload, 22)[0],
    }


def box_stats(entries: list[tuple[tuple[int, int, int], int]]) -> tuple[int, int, float]:
    total = sum(count for _rgb, count in entries)
    means = [sum(rgb[channel] * count for rgb, count in entries) / total for channel in range(3)]
    variances = [
        sum(((rgb[channel] - means[channel]) ** 2) * count for rgb, count in entries) / total
        for channel in range(3)
    ]
    ranges = [
        max(rgb[channel] for rgb, _count in entries) - min(rgb[channel] for rgb, _count in entries)
        for channel in range(3)
    ]
    channel = max(range(3), key=lambda value: (variances[value], ranges[value], -value))
    return channel, total, variances[channel] * total


def split_box(entries: list[tuple[tuple[int, int, int], int]]) -> tuple[list[Any], list[Any]]:
    channel, total, _score = box_stats(entries)
    other = tuple(value for value in range(3) if value != channel)
    ordered = sorted(entries, key=lambda item: (item[0][channel], item[0][other[0]], item[0][other[1]]))
    target = total / 2
    running = 0
    split = 1
    for index, (_rgb, count) in enumerate(ordered[:-1], 1):
        running += count
        split = index
        if running >= target:
            break
    return ordered[:split], ordered[split:]


def representative_colour(entries: list[tuple[tuple[int, int, int], int]]) -> tuple[int, int, int]:
    total = sum(count for _rgb, count in entries)
    return tuple(
        max(0, min(255, int(sum(rgb[channel] * count for rgb, count in entries) / total + 0.5)))
        for channel in range(3)
    )


def build_visible_palette(histogram: Counter[tuple[int, int, int]], target_size: int) -> list[tuple[int, int, int]]:
    require(len(histogram) >= target_size, "interface source has too few distinct RGB colours")
    boxes: list[list[tuple[tuple[int, int, int], int]]] = [list(histogram.items())]
    while len(boxes) < target_size:
        candidates = [
            (box_stats(box)[2], box_stats(box)[1], index)
            for index, box in enumerate(boxes)
            if len(box) > 1
        ]
        require(bool(candidates), "weighted median cut ran out of splittable boxes")
        _score, _weight, index = max(candidates)
        left, right = split_box(boxes.pop(index))
        require(bool(left and right), "weighted median cut produced an empty box")
        boxes.extend((left, right))
    colours = list(dict.fromkeys(representative_colour(box) for box in boxes))
    if len(colours) < target_size:
        for rgb, _count in histogram.most_common():
            if rgb not in colours:
                colours.append(rgb)
            if len(colours) == target_size:
                break
    require(len(colours) == target_size and len(set(colours)) == target_size, "interface palette is not exactly 254 distinct colours")
    colours.sort(key=lambda rgb: (299 * rgb[0] + 587 * rgb[1] + 114 * rgb[2], rgb))
    return colours


def colour_distance_sq(source: tuple[int, int, int], target: tuple[int, int, int]) -> int:
    dr, dg, db = source[0] - target[0], source[1] - target[1], source[2] - target[2]
    return 2 * dr * dr + 4 * dg * dg + 3 * db * db


def embedded_palette_block(visible: Sequence[tuple[int, int, int]]) -> bytes:
    require(len(visible) == VISIBLE_UI_COLOURS and len(set(visible)) == VISIBLE_UI_COLOURS, "invalid UI palette")
    output = bytearray(EMBEDDED_SPLT_HEADER)
    for index in range(256):
        rgb = visible[index - 1] if 1 <= index <= VISIBLE_UI_COLOURS else (0, 0, 0)
        output.extend((*rgb, 0))
    require(len(output) == 1_032, "embedded palette block length changed")
    return bytes(output)


def quantize_interface(image: Image.Image, label: str) -> dict[str, Any]:
    require(image.mode == "RGB", f"{label} is not RGB")
    histogram: Counter[tuple[int, int, int]] = Counter(image.getdata())
    visible = build_visible_palette(histogram, VISIBLE_UI_COLOURS)
    mapping: dict[tuple[int, int, int], int] = {}
    weighted_error = 0
    maximum_error = 0
    for rgb, count in histogram.items():
        index = min(
            range(1, VISIBLE_UI_COLOURS + 1),
            key=lambda value: (colour_distance_sq(rgb, visible[value - 1]), value),
        )
        distance = colour_distance_sq(rgb, visible[index - 1])
        mapping[rgb] = index
        weighted_error += distance * count
        maximum_error = max(maximum_error, distance)
    plane = bytes(mapping[rgb] for rgb in image.getdata())
    require(len(plane) == image.width * image.height, f"{label} index plane length changed")
    require(0 not in plane and TRANSPARENT_UI_INDEX not in plane and max(plane) <= 254, f"{label} uses a reserved UI index")
    decoded_rgb = bytes(channel for index in plane for channel in visible[index - 1])
    palette = embedded_palette_block(visible)
    return {
        "plane": plane,
        "palette": palette,
        "visible": visible,
        "decoded_rgb": decoded_rgb,
        "metrics": {
            "algorithm": "frequency-weighted-median-cut-v1",
            "visible_colour_count": VISIBLE_UI_COLOURS,
            "source_unique_rgb_count": len(histogram),
            "source_pixel_count": len(plane),
            "distance": "2*dR^2 + 4*dG^2 + 3*dB^2; lowest visible index wins ties",
            "dither": "none",
            "mapping": "ordinary global nearest; no class/position routing",
            "weighted_distance_sq_mean": weighted_error / len(plane),
            "weighted_distance_sq_max": maximum_error,
            "index_plane_sha256": sha256_bytes(plane),
            "palette_block_sha256": sha256_bytes(palette),
            "visible_palette_rgb_sha256": sha256_bytes(bytes(channel for rgb in visible for channel in rgb)),
            "decoded_rgb_sha256": sha256_bytes(decoded_rgb),
            "index_minimum": min(plane),
            "index_maximum": max(plane),
            "index_0_count": plane.count(0),
            "index_255_count": plane.count(255),
        },
    }


def build_embedded_tile(stock_template: bytes, image: Image.Image, label: str) -> tuple[bytes, dict[str, Any]]:
    header = tile_header(stock_template)
    require(header["version"] == 1 and header["palette_mode"] == 0, f"{label} stock template is not external TILE-v1")
    require((header["width"], header["height"]) == image.size, f"{label} stock template canvas changed")
    require(header["row_stride"] == image.width, f"{label} row stride changed")
    require(header["transparent_index"] == TRANSPARENT_UI_INDEX, f"{label} transparent index changed")
    quantized = quantize_interface(image, label)
    pixel_end = 26 + header["row_stride"] * header["height"]
    output_header = bytearray(stock_template[:26])
    struct.pack_into("<H", output_header, 20, 1)
    struct.pack_into("<I", output_header, 22, pixel_end)
    output = bytes(output_header) + quantized["plane"] + quantized["palette"]
    require(len(output) == pixel_end + 1_032, f"{label} TILE-v1 length changed")
    output_header_record = tile_header(output)
    require(output_header_record["palette_mode"] == 1 and output_header_record["palette_ref"] == pixel_end, f"{label} embedded palette pointer changed")
    record = {
        "source_stock_tile_sha256": sha256_bytes(stock_template),
        "source_stock_header_sha256": sha256_bytes(stock_template[:26]),
        "header": output_header_record,
        **quantized["metrics"],
        "tile_size": len(output),
        "tile_sha256": sha256_bytes(output),
    }
    expected = INTERFACE_TILE_AUTHORITY[label]
    for key, value in expected.items():
        require(record[key] == value, f"{label} deterministic interface authority changed: {key}={record[key]!r}")
    return output, record


def decode_tile_v1(payload: bytes, external_palette: Sequence[tuple[int, int, int]] | None = None) -> Image.Image:
    header = tile_header(payload)
    require(header["version"] == 1 and header["row_stride"] >= header["width"], "invalid TILE-v1")
    pixel_end = 26 + header["row_stride"] * header["height"]
    require(pixel_end <= len(payload), "truncated TILE-v1 pixels")
    raw = payload[26:pixel_end]
    plane = b"".join(
        raw[row * header["row_stride"] : row * header["row_stride"] + header["width"]]
        for row in range(header["height"])
    )
    if header["palette_mode"] == 1:
        require(header["palette_ref"] == pixel_end and len(payload) == pixel_end + 1_032, "invalid embedded TILE-v1 palette")
        palette = parse_splt(payload[pixel_end:], "embedded TILE-v1")
    else:
        require(header["palette_mode"] == 0 and external_palette is not None and len(payload) == pixel_end, "invalid external TILE-v1 palette")
        palette = list(external_palette)
    pixels = [
        (*palette[value], 0 if value == (header["transparent_index"] & 0xFF) else 255)
        for value in plane
    ]
    image = Image.new("RGBA", (header["width"], header["height"]))
    image.putdata(pixels)
    return image


def save_png(path: Path, image: Image.Image) -> dict[str, Any]:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=9, optimize=False)
    payload = buffer.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {"path": path.as_posix(), "size": len(payload), "sha256": sha256_bytes(payload), "canvas": list(image.size), "mode": image.mode}


def load_handoff() -> dict[str, Any]:
    manifest_path = HANDOFF / "manifest.json"
    require_file(manifest_path, 356_589, HANDOFF_MANIFEST_SHA256, "approved handoff manifest")
    subprocess.run(
        [sys.executable, str(HANDOFF / "verify_handoff.py"), "--root", str(HANDOFF)],
        check=True,
        cwd=REPO,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest["canonical_sha256"] == HANDOFF_CANONICAL_SHA256, "handoff canonical hash changed")
    require(manifest["payload_integrity"]["aggregate_sha256"] == HANDOFF_PAYLOAD_AGGREGATE, "handoff payload aggregate changed")
    require(len(manifest["records"]) == WORLD_COUNT, "handoff record count changed")
    return manifest


def load_retail() -> tuple[bytes, tuple[CamSectionIndex, ...]]:
    require_file(RETAIL_CAM, RETAIL_CAM_SIZE, RETAIL_CAM_SHA256, "retail maindata.cam")
    data = RETAIL_CAM.read_bytes()
    sections = parse_cam(data)
    imag, tile, splt, _cut = sections
    require((imag.extension, tile.extension, splt.extension) == (b"IMAG", b"TILE", b"SPLT"), "retail section order changed")
    healer_index, healer_entry = find_entry(imag, HEALER_IMAG_NAME)
    require(healer_index == HEALER_IMAG_INDEX, "Healer IMAG index changed")
    require((healer_entry.payload_offset, healer_entry.payload_size) == (HEALER_IMAG_OFFSET, HEALER_IMAG_SIZE), "Healer IMAG physical authority changed")
    require(sha256_bytes(entry_data(data, healer_entry)) == HEALER_IMAG_SHA256, "Healer IMAG payload changed")
    return data, sections


def load_package_authority() -> dict[str, Any]:
    require_file(PACKAGE_AUTHORITY, PACKAGE_AUTHORITY_SIZE, PACKAGE_AUTHORITY_SHA256, "Healer package authority")
    authority = json.loads(PACKAGE_AUTHORITY.read_text(encoding="utf-8"))
    require(authority["canonical_sha256"] == PACKAGE_AUTHORITY_CANONICAL, "Healer package authority canonical hash changed")
    surface = authority["package_contract"]["authorized_mutation_surface"]
    offsets = surface["ordered_reference_offsets"]
    stock_words = surface["ordered_stock_words"]
    require(len(offsets) == len(stock_words) == 341, "authorized IMAG mutation count changed")
    offsets_bytes = b"".join(struct.pack("<I", value) for value in offsets)
    words_bytes = b"".join(struct.pack("<I", value) for value in stock_words)
    require(sha256_bytes(offsets_bytes) == AUTHORIZED_OFFSETS_SHA256, "authorized offset aggregate changed")
    require(sha256_bytes(words_bytes) == AUTHORIZED_STOCK_WORDS_SHA256, "authorized stock-word aggregate changed")
    return authority


def patch_healer_imag(stock: bytes, authority: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    require(len(stock) == HEALER_IMAG_SIZE and sha256_bytes(stock) == HEALER_IMAG_SHA256, "stock Healer IMAG changed")
    contract = authority["package_contract"]
    primary = contract["primary_occurrences"]
    require(len(primary) == WORLD_COUNT, "primary occurrence count changed")
    replacements: list[tuple[int, int, str]] = []
    for ordinal, occurrence in enumerate(primary):
        require(occurrence["ordinal"] == ordinal, "primary occurrence ordinal changed")
        replacements.append((occurrence["reference_offset"], WORLD_FIRST + ordinal, f"world/{ordinal}"))
    compact = contract["compact_records"]
    replacements.extend(
        (
            (compact["1000"]["reference_offset"], PROFILE_INDEX, "profile/set1000"),
            (compact["400"]["reference_offset"], WORLD_FIRST, "walk-reuse/set400"),
            (compact["1002"]["reference_offset"], ICON_INDEX, "icon/set1002"),
            (compact["1001"]["reference_offset"], PANEL_INDEX, "panel/set1001"),
        )
    )
    replacement_by_offset = {offset: (value, role) for offset, value, role in replacements}
    require(len(replacement_by_offset) == 341, "replacement offsets are not unique")
    surface = contract["authorized_mutation_surface"]
    authorized_offsets = surface["ordered_reference_offsets"]
    require(sorted(replacement_by_offset) == authorized_offsets, "replacement surface differs from authority")

    output = bytearray(stock)
    records: list[dict[str, Any]] = []
    for offset in authorized_offsets:
        original = struct.unpack_from("<I", stock, offset)[0]
        expected = surface["ordered_stock_words"][authorized_offsets.index(offset)]
        require(original == expected, f"stock IMAG word changed at {offset}")
        new_low16, role = replacement_by_offset[offset]
        replacement = (original & 0xFFFF0000) | new_low16
        struct.pack_into("<I", output, offset, replacement)
        require(replacement >> 16 == original >> 16, f"high16 flags changed at {offset}")
        records.append(
            {
                "offset": offset,
                "role": role,
                "stock_word": original,
                "stock_low16": original & 0xFFFF,
                "preserved_high16": original >> 16,
                "private_low16": new_low16,
                "private_word": replacement,
            }
        )
    private = bytes(output)
    changed_mask = bytearray(len(stock))
    for index, (before, after) in enumerate(zip(stock, private)):
        if before != after:
            changed_mask[index] = 1
    allowed_mask = bytearray(len(stock))
    for offset in authorized_offsets:
        allowed_mask[offset] = 1
        allowed_mask[offset + 1] = 1
        require(stock[offset : offset + 2] != private[offset : offset + 2], f"authorized low16 word did not change at {offset}")
    require(
        all(not changed or allowed_mask[index] for index, changed in enumerate(changed_mask)),
        "private IMAG changed bytes outside the authorized low16 surface",
    )
    require(sha256_bytes(bytes(allowed_mask)) == AUTHORIZED_MASK_SHA256, "authorized IMAG byte-mask aggregate changed")
    zeroed = bytearray(private)
    for offset in authorized_offsets:
        zeroed[offset : offset + 2] = b"\x00\x00"
    require(sha256_bytes(bytes(zeroed)) == LOW16_ZEROED_IMAG_SHA256, "private IMAG differs from stock outside authorized low16 words")

    secondary = contract["cast_secondary_stream"]["occurrences"]
    secondary_bytes = b"".join(
        private[record["metadata_offset"] : record["reference_offset"] + 4]
        for record in secondary
    )
    require(len(secondary_bytes) == 576 and sha256_bytes(secondary_bytes) == CAST_SECONDARY_SHA256, "Cast second stream/tail changed")
    minimap = contract["minimap_set300"]
    require(struct.unpack_from("<I", private, minimap["reference_offset"])[0] == minimap["reference_word"], "set300 Minimap changed")
    return private, {
        "source_name": "AVD1Healer",
        "private_name": "TRB1Troubadour",
        "size": len(private),
        "stock_sha256": sha256_bytes(stock),
        "private_sha256": sha256_bytes(private),
        "authorized_word_count": len(records),
        "authorized_low16_byte_count": sum(allowed_mask),
        "actual_changed_byte_count": sum(changed_mask),
        "authorized_offsets_sha256": AUTHORIZED_OFFSETS_SHA256,
        "authorized_stock_words_sha256": AUTHORIZED_STOCK_WORDS_SHA256,
        "allowed_byte_mask_sha256": sha256_bytes(bytes(allowed_mask)),
        "actual_changed_byte_mask_sha256": sha256_bytes(bytes(changed_mask)),
        "stock_equivalence_with_authorized_low16_zeroed_sha256": sha256_bytes(bytes(zeroed)),
        "cast_second_stream_bytes": len(secondary_bytes),
        "cast_second_stream_sha256": sha256_bytes(secondary_bytes),
        "set300_minimap_reference_word": minimap["reference_word"],
        "mutations": records,
    }


def load_rgb_png(path: Path, size: tuple[int, int], rgb_sha256: str, label: str) -> Image.Image:
    with Image.open(path) as source:
        source.load()
        image = source.copy()
    require(image.mode == "RGB" and image.size == size, f"{label} PNG canvas/mode changed")
    require(sha256_bytes(image.tobytes()) == rgb_sha256, f"{label} raw RGB changed")
    return image


def interface_tiles(
    retail_data: bytes,
    tile_section: CamSectionIndex,
) -> tuple[bytes, bytes, bytes, dict[str, Any], Image.Image, Image.Image, Image.Image]:
    profile_template = entry_data(retail_data, tile_section.entries[PROFILE_STOCK_INDEX])
    icon_template = entry_data(retail_data, tile_section.entries[ICON_STOCK_INDEX])
    panel = entry_data(retail_data, tile_section.entries[PANEL_STOCK_INDEX])
    require(sha256_bytes(panel) == PANEL_STOCK_SHA256, "stock selected-unit panel changed")
    profile_image = load_rgb_png(HANDOFF / PROFILE_SOURCE_PNG, (100, 100), PROFILE_SOURCE_RGB_SHA256, "profile")
    icon_image = load_rgb_png(HANDOFF / ICON_SOURCE_PNG, (25, 25), ICON_SOURCE_RGB_SHA256, "icon")
    profile_tile, profile_record = build_embedded_tile(profile_template, profile_image, "profile")
    icon_tile, icon_record = build_embedded_tile(icon_template, icon_image, "icon")
    require(len(profile_tile) == 11_058 and len(icon_tile) == 1_683, "interface TILE-v1 packaged length changed")
    profile_decoded = decode_tile_v1(profile_tile)
    icon_decoded = decode_tile_v1(icon_tile)
    return profile_tile, icon_tile, panel, {
        "profile": profile_record,
        "icon": icon_record,
        "selected_panel": {
            "policy": "byte-exact retail Healer TILE4377 clone",
            "source_stock_tile_index": PANEL_STOCK_INDEX,
            "source_stock_palette_index": PANEL_STOCK_SPLT,
            "tile_size": len(panel),
            "tile_sha256": sha256_bytes(panel),
        },
    }, profile_decoded, icon_decoded, profile_image


def package_file_record(root: Path, relative: Path) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative.as_posix(),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def parse_package_cam(payload: bytes) -> tuple[CamSectionIndex, ...]:
    require(payload[:12] == CAM_MAGIC, "package CAM magic changed")
    section_count, content_header_size = struct.unpack_from("<II", payload, 12)
    require(section_count == 3, "package CAM must contain exactly IMAG/TILE/SPLT")
    expected = (
        (b"IMAG", 1, b"\x00\x00\x00\x00"),
        (b"TILE", PACKAGE_TILE_COUNT, b"\x01\x00\x00\x00"),
        (b"SPLT", PACKAGE_SPLT_COUNT, b"\x01\x00\x00\x00"),
    )
    expected_content = sum(CAM_SECTION_HEADER_SIZE + count * CAM_ENTRY_HEADER_SIZE for _extension, count, _padding in expected)
    require(content_header_size == expected_content, "package CAM content-header size changed")
    directory: list[tuple[bytes, int]] = []
    cursor = CAM_HEADER_SIZE
    for _ in range(section_count):
        directory.append((payload[cursor : cursor + 4], struct.unpack_from("<I", payload, cursor + 4)[0]))
        cursor += CAM_DIR_ENTRY_SIZE
    section_cursor = CAM_HEADER_SIZE + section_count * CAM_DIR_ENTRY_SIZE
    sections: list[CamSectionIndex] = []
    for ordinal, ((extension, offset), (expected_extension, expected_count, expected_padding)) in enumerate(zip(directory, expected)):
        require((extension, offset) == (expected_extension, section_cursor), f"package section directory changed at {ordinal}")
        count = struct.unpack_from("<I", payload, offset)[0]
        padding = payload[offset + 4 : offset + 8]
        require((count, padding) == (expected_count, expected_padding), f"package {extension!r} header changed")
        cursor = offset + CAM_SECTION_HEADER_SIZE
        entries: list[CamEntryIndex] = []
        for _ in range(count):
            name = payload[cursor : cursor + 20]
            payload_offset, payload_size = struct.unpack_from("<II", payload, cursor + 20)
            require(payload_offset + payload_size <= len(payload), f"package {extension!r} payload out of bounds")
            entries.append(CamEntryIndex(name, payload_offset, payload_size, cursor))
            cursor += CAM_ENTRY_HEADER_SIZE
        sections.append(CamSectionIndex(extension, offset, padding, tuple(entries)))
        section_cursor += CAM_SECTION_HEADER_SIZE + count * CAM_ENTRY_HEADER_SIZE
    return tuple(sections)


def validate_package_cam(
    path: Path,
    retail_data: bytes,
    retail_sections: tuple[CamSectionIndex, ...],
    handoff: dict[str, Any],
    private_imag: bytes,
    profile_tile: bytes,
    icon_tile: bytes,
    panel_tile: bytes,
    private_splt: bytes,
) -> dict[str, Any]:
    payload = path.read_bytes()
    imag, tile, splt = parse_package_cam(payload)
    retail_imag, retail_tile, retail_splt, _retail_cut = retail_sections
    require(imag.entries[0].name == pad_name(PRIVATE_IMAG_NAME), "private IMAG CAM name changed")
    require(entry_data(payload, imag.entries[0]) == private_imag, "packaged private IMAG bytes changed")
    for index in range(RETAIL_TILE_COUNT):
        require(tile.entries[index].name == retail_tile.entries[index].name, f"retail TILE placeholder name changed at {index}")
        require(tile.entries[index].payload_size == 0, f"retail TILE slot is not empty fallthrough at {index}")
    for record in handoff["records"]:
        index = record["private_tile_index"]
        entry = tile.entries[index]
        expected = (HANDOFF / record["tile"]["path"]).read_bytes()
        require(entry.name == pad_name(record["cam_name"].encode("ascii")), f"world TILE name changed at {index}")
        require(entry_data(payload, entry) == expected, f"world TILE payload changed at {index}")
    interface_contract = (
        (PROFILE_INDEX, b"TRB1Profile", profile_tile),
        (ICON_INDEX, b"TRB1HeroIcon", icon_tile),
        (PANEL_INDEX, b"TRB1SelectedPanel", panel_tile),
    )
    for index, name, expected_payload in interface_contract:
        entry = tile.entries[index]
        require(entry.name == pad_name(name), f"interface TILE name changed at {index}")
        require(entry_data(payload, entry) == expected_payload, f"interface TILE payload changed at {index}")
    for index in range(RETAIL_SPLT_COUNT):
        source = retail_splt.entries[index]
        packaged = splt.entries[index]
        require(packaged.name == source.name, f"retail SPLT name changed at {index}")
        require(entry_data(payload, packaged) == entry_data(retail_data, source), f"retail SPLT payload changed at {index}")
    require(splt.entries[PRIVATE_SPLT_INDEX].name == pad_name(PRIVATE_SPLT_NAME), "private SPLT name changed")
    require(entry_data(payload, splt.entries[PRIVATE_SPLT_INDEX]) == private_splt, "private SPLT payload changed")
    return {
        "path": PACKAGE_CAM,
        "size": len(payload),
        "sha256": sha256_bytes(payload),
        "sections": [
            {"extension": section.extension.decode("ascii"), "count": len(section.entries), "padding_hex": section.padding.hex()}
            for section in (imag, tile, splt)
        ],
        "retail_tile_placeholders": RETAIL_TILE_COUNT,
        "retail_tile_nonempty_payloads": 0,
        "private_tile_first": WORLD_FIRST,
        "private_tile_last": PANEL_INDEX,
        "private_tile_count": PACKAGE_TILE_COUNT - RETAIL_TILE_COUNT,
        "retail_splt_cloned_byte_exact": RETAIL_SPLT_COUNT,
        "private_splt_index": PRIVATE_SPLT_INDEX,
    }


def build_review(
    root: Path,
    profile: Image.Image,
    icon: Image.Image,
    panel: Image.Image,
) -> dict[str, Any]:
    review_root = root / "Review/interface"
    paths = {
        "profile": Path("Review/interface/troubadour-profile-100x100.png"),
        "icon": Path("Review/interface/troubadour-hero-count-icon-25x25.png"),
        "panel": Path("Review/interface/troubadour-selected-unit-panel-stock-shell-200x245.png"),
        "contact_sheet": Path("Review/interface/troubadour-interface-review.png"),
    }
    for key, image in (("profile", profile), ("icon", icon), ("panel", panel)):
        save_png(root / paths[key], image)
    canvas = Image.new("RGBA", (620, 310), (25, 28, 29, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((20, 12), "Troubadour interface package review", fill=(235, 230, 214, 255))
    checker = Image.new("RGBA", (200, 245), (42, 46, 47, 255))
    checker.alpha_composite(panel, (0, 0))
    canvas.alpha_composite(checker, (20, 46))
    canvas.alpha_composite(profile, (260, 46))
    canvas.alpha_composite(icon.resize((100, 100), Image.Resampling.NEAREST), (390, 46))
    draw.rectangle((258, 44, 361, 147), outline=(210, 198, 164, 255), width=1)
    draw.rectangle((388, 44, 491, 147), outline=(210, 198, 164, 255), width=1)
    draw.text((260, 158), "100x100 decoded profile", fill=(210, 208, 198, 255))
    draw.text((390, 158), "25x25 decoded icon (4x)", fill=(210, 208, 198, 255))
    draw.text((20, 294), "Stock Healer selected-unit panel shell cloned byte-exact", fill=(210, 208, 198, 255))
    save_png(root / paths["contact_sheet"], canvas)
    return {key: package_file_record(root, relative) for key, relative in paths.items()}


def build_mmxml(root: Path) -> dict[str, Any]:
    path = root / PACKAGE_MMXML
    path.write_bytes(EXPECTED_MMXML.encode("utf-8"))
    parsed = ET.fromstring(path.read_text(encoding="utf-8"))
    require(parsed.tag == "Majesty", "MMXML root changed")
    mod = parsed.find("Mod")
    require(mod is not None and mod.attrib == {"id": "{" + PACKAGE_UUID + "}"}, "MMXML Mod id changed")
    cams = [node.text for node in parsed.findall("./Mod/DataConfiguration/Dataset/Load/CAM")]
    require(cams == [r"Data\troubadour_maindata.cam"], "MMXML CAM load set changed")
    require(not parsed.findall(".//Descriptions") and not parsed.findall(".//GPL"), "art-only MMXML acquired gameplay loads")
    return {**package_file_record(root, Path(PACKAGE_MMXML)), "uuid": PACKAGE_UUID, "cam_loads": cams, "role": "declarative art-only loader; no unit/gameplay registration"}


def artifact_inventory(root: Path) -> dict[str, Any]:
    records = [
        package_file_record(root, path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and path.name != PACKAGE_MANIFEST
    ]
    records.sort(key=lambda record: record["path"])
    lines = "\n".join(f"{record['sha256']}  {record['path']}" for record in records) + "\n"
    return {
        "file_count": len(records),
        "total_bytes": sum(record["size"] for record in records),
        "aggregate_sha256": sha256_bytes(lines.encode("utf-8")),
        "aggregate_definition": "SHA-256 of sorted '<sha256>  <package-relative-path>\\n' records; manifest excluded",
        "files": records,
    }


def build(output: Path) -> dict[str, Any]:
    require(output == DEFAULT_OUTPUT.resolve(), f"package output must be exactly {DEFAULT_OUTPUT.resolve()}")
    require(not output.exists(), f"refusing to overwrite existing package: {output}")
    require(PIL.__version__ == "11.3.0", f"Pillow version changed: {PIL.__version__}")
    require_file(APPROVAL, APPROVAL_SIZE, APPROVAL_SHA256, "Gate6 approval")
    handoff = load_handoff()
    authority = load_package_authority()
    retail_data, retail_sections = load_retail()
    retail_imag, retail_tile, retail_splt, _retail_cut = retail_sections
    _healer_index, healer_entry = find_entry(retail_imag, HEALER_IMAG_NAME)
    stock_healer_imag = entry_data(retail_data, healer_entry)
    private_imag, imag_record = patch_healer_imag(stock_healer_imag, authority)
    profile_tile, icon_tile, panel_tile, interface_record, profile_decoded, icon_decoded, _profile_source = interface_tiles(retail_data, retail_tile)
    private_splt = (HANDOFF / handoff["palette"]["path"]).read_bytes()
    require(len(private_splt) == 1_032 and sha256_bytes(private_splt) == PRIVATE_SPLT_SHA256, "handoff private SPLT changed")
    panel_palette = parse_splt(entry_data(retail_data, retail_splt.entries[PANEL_STOCK_SPLT]), "retail SPLT378")
    panel_decoded = decode_tile_v1(panel_tile, panel_palette)

    world_entries: list[CamEntry] = []
    private_tile_records: list[dict[str, Any]] = []
    for record in handoff["records"]:
        ordinal = record["ordinal"]
        require(record["private_tile_index"] == WORLD_FIRST + ordinal, "handoff private index changed")
        payload = (HANDOFF / record["tile"]["path"]).read_bytes()
        require(len(payload) == record["tile"]["size"] and sha256_bytes(payload) == record["tile"]["sha256"], "handoff TILE changed")
        header = tile_header(payload)
        require(header["version"] == 3 and header["palette_mode"] == 0 and header["palette_ref"] == PRIVATE_SPLT_INDEX, "world TILE palette contract changed")
        world_entries.append(CamEntry(pad_name(record["cam_name"].encode("ascii")), payload))
        private_tile_records.append(
            {
                "private_tile_index": WORLD_FIRST + ordinal,
                "ordinal": ordinal,
                "role": f"{record['action']}/{record['direction']}/frame-{record['frame']:02d}",
                "cam_name": record["cam_name"],
                "source_handoff_path": record["tile"]["path"],
                "size": len(payload),
                "sha256": sha256_bytes(payload),
                "header": header,
            }
        )
    require(len(world_entries) == WORLD_COUNT, "world entry count changed")
    interface_entries = (
        CamEntry(pad_name(b"TRB1Profile"), profile_tile),
        CamEntry(pad_name(b"TRB1HeroIcon"), icon_tile),
        CamEntry(pad_name(b"TRB1SelectedPanel"), panel_tile),
    )
    for private_index, role, name, payload in (
        (PROFILE_INDEX, "profile/set1000", "TRB1Profile", profile_tile),
        (ICON_INDEX, "hero-icon/set1002", "TRB1HeroIcon", icon_tile),
        (PANEL_INDEX, "selected-panel/set1001", "TRB1SelectedPanel", panel_tile),
    ):
        private_tile_records.append(
            {
                "private_tile_index": private_index,
                "role": role,
                "cam_name": name,
                "size": len(payload),
                "sha256": sha256_bytes(payload),
                "header": tile_header(payload),
            }
        )
    tile_entries = tuple(
        [CamEntry(entry.name, b"") for entry in retail_tile.entries]
        + world_entries
        + list(interface_entries)
    )
    require(len(tile_entries) == PACKAGE_TILE_COUNT, "package TILE entry count changed")
    splt_entries = tuple(
        [CamEntry(entry.name, entry_data(retail_data, entry)) for entry in retail_splt.entries]
        + [CamEntry(pad_name(PRIVATE_SPLT_NAME), private_splt)]
    )
    require(len(splt_entries) == PACKAGE_SPLT_COUNT, "package SPLT entry count changed")
    sections = (
        CamSection(b"IMAG", b"\x00\x00\x00\x00", (CamEntry(pad_name(PRIVATE_IMAG_NAME), private_imag),)),
        CamSection(b"TILE", b"\x01\x00\x00\x00", tile_entries),
        CamSection(b"SPLT", b"\x01\x00\x00\x00", splt_entries),
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".CustomGuildTroubadour-staging-", dir=output.parent))
    print(f"staging={staging}")
    published = False
    try:
        cam_path = staging / PACKAGE_CAM
        write_cam(cam_path, sections)
        cam_record = validate_package_cam(
            cam_path,
            retail_data,
            retail_sections,
            handoff,
            private_imag,
            profile_tile,
            icon_tile,
            panel_tile,
            private_splt,
        )
        review_record = build_review(staging, profile_decoded, icon_decoded, panel_decoded)
        mmxml_record = build_mmxml(staging)
        manifest: dict[str, Any] = {
            "schema": PACKAGE_SCHEMA,
            "id": PACKAGE_ID,
            "status": "builder-validated",
            "deployment_ready": True,
            "installed_or_launched": False,
            "scope": "hero art resource package only; no Troubadour unit/gameplay registration",
            "private_identity": {
                "image_id_base": "TRB1",
                "imag_name": "TRB1Troubadour",
                "workspace_and_retail_collision_scan": "pass",
                "mod_uuid": PACKAGE_UUID,
            },
            "authorities": {
                "approval": {"path": "checkpoints/indexed-sprite-set-v1-approved.json", "size": APPROVAL_SIZE, "sha256": APPROVAL_SHA256},
                "approved_handoff": {
                    "path": "assets/source/approved-troubadour-sprite-set-v1/manifest.json",
                    "size": 356_589,
                    "sha256": HANDOFF_MANIFEST_SHA256,
                    "canonical_sha256": HANDOFF_CANONICAL_SHA256,
                    "payload_aggregate_sha256": HANDOFF_PAYLOAD_AGGREGATE,
                },
                "healer_package_authority": {
                    "path": "reference/healer-package-authority-v2.json",
                    "size": PACKAGE_AUTHORITY_SIZE,
                    "sha256": PACKAGE_AUTHORITY_SHA256,
                    "canonical_sha256": PACKAGE_AUTHORITY_CANONICAL,
                },
                "retail_maindata_cam": {
                    "path": "working/majesty-authority/Data/maindata.cam",
                    "size": RETAIL_CAM_SIZE,
                    "sha256": RETAIL_CAM_SHA256,
                    "redistributed": False,
                },
                "stock_healer_imag": {
                    "name": "AVD1Healer",
                    "index": HEALER_IMAG_INDEX,
                    "payload_file_offset": HEALER_IMAG_OFFSET,
                    "size": HEALER_IMAG_SIZE,
                    "sha256": HEALER_IMAG_SHA256,
                },
            },
            "mmxml": mmxml_record,
            "cam": cam_record,
            "imag": imag_record,
            "private_tiles": private_tile_records,
            "private_palette": {
                "private_splt_index": PRIVATE_SPLT_INDEX,
                "cam_name": PRIVATE_SPLT_NAME.decode("ascii"),
                "size": len(private_splt),
                "sha256": sha256_bytes(private_splt),
                "world_visible_indices": [1, 246],
                "world_ground_control_indices": [247, 250],
                "world_forbidden_indices": [251, 255],
                "retail_splt_count_cloned_byte_exact": RETAIL_SPLT_COUNT,
            },
            "interface": {
                "derivation_authority": handoff["interface"],
                "tile_v1_contract": {
                    "palette_mode": 1,
                    "palette_ref": "26 + row_stride*height; embedded block begins immediately after pixels",
                    "transparent_index": TRANSPARENT_UI_INDEX,
                    "visible_index_range": [1, 254],
                    "forbidden_pixel_indices": [0, 255],
                    "embedded_palette_layout": "8-byte 0000000100000000 header; 256 RGBx entries; x=0; entries0/255 zero",
                    "quantizer": "deterministic frequency-weighted median cut; 254 colours; no Pillow quantization; no dither",
                    "nearest_mapping": "2*dR^2 + 4*dG^2 + 3*dB^2; lowest visible index tie",
                },
                **interface_record,
            },
            "stock_preservation": {
                "retail_tile_slots_0_through_17223": "names byte-exact; payloads all zero-length fallthrough",
                "retail_splt_slots_0_through_853": "names and payloads byte-exact",
                "cast_second_stream_and_tail": {"bytes": 576, "sha256": CAST_SECONDARY_SHA256, "status": "byte-exact"},
                "set300_minimap": {"tile_index": MINIMAP_STOCK_INDEX, "status": "byte-exact IMAG reference and retail fallthrough"},
                "selected_unit_panel": {"tile_index": PANEL_INDEX, "source_stock_tile_index": PANEL_STOCK_INDEX, "source_sha256": PANEL_STOCK_SHA256, "status": "byte-exact private clone"},
                "set400_walk_reuse": {"private_tile_index": WORLD_FIRST, "status": "stock topology preserved; low16 privateized"},
            },
            "review": review_record,
            "validations": [
                "tracked handoff self-verifier pass",
                "retail CAM physical and hash authority pass",
                "Healer IMAG 341-word low16-only mutation surface pass",
                "Cast second stream/tail byte-exact pass",
                "set300 Minimap byte-exact pass",
                "retail TILE fallthrough/name preservation pass",
                "retail SPLT byte-exact clone pass",
                "custom TILE/SPLT/interface round-trip pass",
                "art-only MMXML parse/load-set pass",
            ],
            "artifact_inventory": {},
            "canonical_sha256": "0" * 64,
        }
        manifest["artifact_inventory"] = artifact_inventory(staging)
        manifest["canonical_sha256"] = canonical_hash(manifest)
        write_json(staging / PACKAGE_MANIFEST, manifest)
        # Re-read the exact published candidate and prove its canonical self-hash.
        reread = json.loads((staging / PACKAGE_MANIFEST).read_text(encoding="utf-8"))
        require(canonical_hash(reread) == reread["canonical_sha256"], "package manifest canonical hash changed on disk")
        require(not output.exists(), "output appeared during staged build")
        staging.replace(output)
        published = True
    finally:
        if not published:
            print(f"FAILED_STAGING_RETAINED={staging}", file=sys.stderr)
    manifest = json.loads((output / PACKAGE_MANIFEST).read_text(encoding="utf-8"))
    print(f"PASS: built {output}")
    print(f"package_manifest_canonical_sha256={manifest['canonical_sha256']}")
    print(f"package_cam_sha256={manifest['cam']['sha256']}")
    return manifest


def diagnose_interface() -> dict[str, Any]:
    handoff = load_handoff()
    _ = handoff
    retail_data, sections = load_retail()
    _imag, tile, _splt, _cut = sections
    profile_tile, icon_tile, panel_tile, interface_record, _profile_decoded, _icon_decoded, _profile_source = interface_tiles(retail_data, tile)
    record = {
        "profile": {**interface_record["profile"], "tile_sha256": sha256_bytes(profile_tile)},
        "icon": {**interface_record["icon"], "tile_sha256": sha256_bytes(icon_tile)},
        "panel": {**interface_record["selected_panel"], "tile_sha256": sha256_bytes(panel_tile)},
    }
    print(json.dumps(record, indent=2))
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--diagnose-interface", action="store_true")
    args = parser.parse_args()
    if args.diagnose_interface:
        diagnose_interface()
        return 0
    build(args.output.resolve())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
