"""Binary compatibility checks against the imported, audited CAM writer."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cam_io import Entry, Section, append_strings, name, read, write
from build_bards_hall import load_art_module


class CamCompatibility(unittest.TestCase):
    def test_matches_audited_writer_including_empty_positional_entries(self):
        sections = (
            Section(b"IMAG", bytes(4), (Entry(name(b"TEST"), b"image payload"),)),
            Section(b"TILE", b"\1\0\0\0", (Entry(name(b"old"), b""), Entry(name(b"new"), b"tile"))),
        )
        with tempfile.TemporaryDirectory() as directory:
            ours, reference = Path(directory) / "ours.cam", Path(directory) / "reference.cam"
            write(ours, sections)
            load_art_module(Path(directory)).write_cam(reference, sections)
            self.assertEqual(ours.read_bytes(), reference.read_bytes())
            self.assertEqual(read(ours), sections)

    def test_rejects_incorrect_content_header_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.cam"
            write(path, (Section(b"DATA", bytes(4), (Entry(name(b"TEST"), b"payload"),)),))
            data = bytearray(path.read_bytes())
            struct.pack_into("<I", data, 16, struct.unpack_from("<I", data, 16)[0] + 28)
            path.write_bytes(data)
            with self.assertRaises(ValueError):
                read(path)

    def test_private_strings_preserve_stock_record_bytes(self):
        # Independently encoded one-record stock STRT fixture.
        original = struct.pack("<HHI", 1, 1, 8) + b"ABV1Warriors Guild\0"
        result = append_strings(original, {b"BDG1": "Bards Hall"})
        self.assertEqual(result, struct.pack("<HHII", 2, 1, 12, 31) + b"ABV1Warriors Guild\0BDG1Bards Hall\0")
        with self.assertRaises(ValueError):
            append_strings(original, {b"ABV1": "wrong"})


if __name__ == "__main__":
    unittest.main()
