"""Majesty CAM helpers; positional TILE/SPLT entries must never be compacted."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct

MAGIC = b"CYLBPC  \x01\x00\x01\x00"


@dataclass(frozen=True)
class Entry:
    name: bytes
    data: bytes


@dataclass(frozen=True)
class Section:
    extension: bytes
    padding: bytes
    entries: tuple[Entry, ...]


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def name(value: bytes) -> bytes:
    if not value or len(value) > 20:
        raise ValueError(f"Invalid CAM name: {value!r}")
    return value.ljust(20, b"\0")


def read(path: Path) -> tuple[Section, ...]:
    data = path.read_bytes()
    if len(data) < 20 or data[:12] != MAGIC:
        raise ValueError(f"Not a CAM: {path}")
    section_count = u32(data, 12)
    directory_end = 20 + section_count * 8
    header_end = directory_end + u32(data, 16)
    if directory_end > len(data) or header_end > len(data):
        raise ValueError("CAM header exceeds file")
    result = []
    next_header = directory_end
    for index in range(section_count):
        directory = 20 + index * 8
        extension, start = struct.unpack_from("<4sI", data, directory)
        if start != next_header or start + 8 > header_end:
            raise ValueError("CAM section directory is invalid")
        count = u32(data, start)
        next_header = start + 8 + count * 28
        if next_header > header_end:
            raise ValueError("CAM entry headers exceed content header")
        entries = []
        for ordinal in range(count):
            header = start + 8 + ordinal * 28
            label, offset, size = struct.unpack_from("<20sII", data, header)
            if offset < header_end or offset + size > len(data):
                raise ValueError(f"CAM entry exceeds file: {label!r}")
            entries.append(Entry(label, data[offset:offset + size]))
        result.append(Section(extension, data[start + 4:start + 8], tuple(entries)))
    if next_header != header_end:
        raise ValueError("CAM content-header size mismatch")
    return tuple(result)


def write(path: Path, sections: tuple[Section, ...]) -> None:
    directory_size = 20 + len(sections) * 8
    content_header_size = sum(8 + 28 * len(s.entries) for s in sections)
    header_end = directory_size + content_header_size
    header = bytearray(MAGIC + struct.pack("<II", len(sections), content_header_size))
    section_offset = directory_size
    for section in sections:
        if len(section.extension) != 4 or len(section.padding) != 4:
            raise ValueError("Invalid CAM section shape")
        header.extend(struct.pack("<4sI", section.extension, section_offset))
        section_offset += 8 + 28 * len(section.entries)
    payload = bytearray()
    for section in sections:
        header.extend(struct.pack("<I", len(section.entries)) + section.padding)
        for entry in section.entries:
            header.extend(struct.pack("<20sII", name(entry.name), header_end + len(payload), len(entry.data)))
            payload.extend(entry.data)
    if len(header) != header_end:
        raise ValueError("CAM header size mismatch")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + payload)


def section(sections: tuple[Section, ...], extension: bytes) -> Section:
    return next(s for s in sections if s.extension == extension)


def get(sections: tuple[Section, ...], extension: bytes, label: bytes) -> bytes:
    return next(e.data for e in section(sections, extension).entries if e.name.rstrip(b"\0") == label)


def patch_strings(data: bytes, replacements: dict[int, str]) -> bytes:
    count, version = struct.unpack_from("<HH", data)
    offsets = struct.unpack_from(f"<{count}I", data, 4)
    records = []
    for index, offset in enumerate(offsets):
        key = u32(data, offset)
        end = data.index(b"\0", offset + 4)
        text = replacements.get(index)
        records.append(struct.pack("<I", key) + (text.encode("cp1252") if text is not None else data[offset + 4:end]) + b"\0")
    header = bytearray(struct.pack("<HH", count, version))
    offset = 4 + 4 * count
    for record in records:
        header.extend(struct.pack("<I", offset))
        offset += len(record)
    return bytes(header) + b"".join(records)


def append_strings(data: bytes, additions: dict[bytes, str]) -> bytes:
    """Append private FourCC keys while retaining every stock record in order."""
    count, version = struct.unpack_from("<HH", data)
    records, existing = [], set()
    for offset in struct.unpack_from(f"<{count}I", data, 4):
        end = data.index(b"\0", offset + 4)
        existing.add(data[offset:offset + 4])
        records.append(data[offset:end + 1])
    for key, value in additions.items():
        if len(key) != 4 or key in existing:
            raise ValueError(f"Private string key collides or is invalid: {key!r}")
        records.append(key + value.encode("cp1252") + b"\0")
    header = bytearray(struct.pack("<HH", len(records), version))
    cursor = 4 + 4 * len(records)
    for record in records:
        header.extend(struct.pack("<I", cursor))
        cursor += len(record)
    return bytes(header) + b"".join(records)


def frame_references(blob: bytes, wanted_set: int) -> tuple[int, ...]:
    """Reference-word offsets from the stock direction/stream/frame table."""
    sets = [struct.unpack_from("<II", blob, 24 + i * 8) for i in range(u32(blob, 20))]
    for index, (set_id, start) in enumerate(sets):
        if set_id != wanted_set:
            continue
        end = sets[index + 1][1] if index + 1 < len(sets) else len(blob)
        directions = u32(blob, start)
        pointers = [start + u32(blob, start + 64 + i * 4) for i in range(directions)]
        if not 0 < directions <= 32 or pointers != sorted(set(pointers)):
            raise ValueError("Unrecognized IMAG direction layout")
        result = []
        for d, pointer in enumerate(pointers):
            direction_end = pointers[d + 1] if d + 1 < len(pointers) else end
            counts = u32(blob, pointer + 4)
            frames, streams = counts >> 16, counts & 65535
            first = direction_end - frames * streams * 8
            if frames < 1 or streams < 1 or first < pointer + 8:
                raise ValueError("Unrecognized IMAG frame layout")
            result.extend(range(first + 4, direction_end, 8))
        return tuple(result)
    raise ValueError(f"Missing IMAG set {wanted_set}")
