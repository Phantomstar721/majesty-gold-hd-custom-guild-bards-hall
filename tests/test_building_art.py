"""Native occurrence, palette and auxiliary preservation for approved buildings."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from bards_building_art import (append_buildings, decode_indices, descriptors,
                                frame_words, image, load_handoff, object_name)
from cam_io import Entry, name, read, section, u32

GAME = Path(r'C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')


class BuildingArtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock = read(GAME / 'Data/maindata.cam')
        cls.manifest, cls.mapping = load_handoff()
        cls.tiles = list(section(cls.stock, b'TILE').entries)
        cls.palettes = list(section(cls.stock, b'SPLT').entries)
        # A deliberately different palette ordinal detects accidental reuse of
        # either the stock or hero slot instead of allocating the new palette.
        for i in range(3):
            cls.palettes.append(Entry(name(f'TEST{i}'.encode()), cls.palettes[0].data))
        cls.expected_palette = len(cls.palettes)
        cls.images, cls.evidence = append_buildings(
            cls.stock, cls.tiles, cls.palettes, image(cls.stock, b'ABV1'))

    def test_final_size_planes_are_exact_without_a_second_enlargement(self):
        from PIL import Image
        from bards_building_art import HANDOFF
        lookup = {tile.name: tile.data for tile in self.tiles}
        for obj in self.manifest['objects']:
            actual = lookup[object_name(obj)]
            approved = (HANDOFF / obj['tile_path']).read_bytes()
            self.assertEqual(struct.unpack_from('<3H', actual, 2), (480, 480, 480))
            self.assertEqual(struct.unpack_from('<hh', actual, 10), (223, 243))
            self.assertEqual(actual[:22], approved[:22])
            self.assertEqual(actual[26:], approved[26:])
            expected = self.expected_palette if obj['palette_ref'] == 0xffffffff else 0
            self.assertEqual(u32(actual, 22), expected)
            with Image.open(HANDOFF / obj['indexed_path']) as plane:
                self.assertEqual(decode_indices(approved), plane.tobytes())
                # Both color and categorical shadow pixels are already native
                # size. A second resize or re-encoding would violate approval.
                self.assertEqual(plane.size, (480, 480))
                self.assertEqual(decode_indices(actual), plane.tobytes())

    def test_activity_parts_keep_independent_stock_lengths_and_no_old_actors(self):
        for building in self.images:
            sets = descriptors(building.data)
            active = {key for key in sets if key & 0xffffff == 192}
            self.assertEqual(active, {192, 0x010000c0})
            self.assertTrue(208 in sets)
            self.assertFalse(any(key & 0xffffff in (193, 194) for key in sets))
            for key, frames in ((192, 8), (0x010000c0, 6)):
                direction, words = frame_words(sets[key])
                self.assertEqual(struct.unpack_from('<hh', sets[key], direction), (0, 0))
                self.assertEqual(len(words), frames)
                refs = [self.tiles[u32(sets[key], pos + 4) & 65535].name for pos in words]
                self.assertTrue(all(ref.startswith(building.name[:4]) for ref in refs))

    def test_disappear_preserves_stock_effect_stream_and_expands_body_only_once(self):
        for level, building in enumerate(self.images, 1):
            private = descriptors(building.data)
            market = descriptors(image(self.stock, f'ABH{level}'.encode()))
            original, actual = market[240], private[240]
            for stream in (0, 1):
                _, old = frame_words(original, stream=stream)
                _, new = frame_words(actual, stream=stream)
                self.assertEqual(len(new), 21)
                if stream == 1:
                    self.assertEqual([actual[pos:pos + 8] for pos in new],
                                     [original[pos:pos + 8] for pos in old])
                else:
                    refs = [self.tiles[u32(actual, pos + 4) & 65535].name.rstrip(b'\0') for pos in new]
                    self.assertEqual(refs, [f'BDG{level}damage-2'.encode()] * 10 +
                                     [f'BDG{level}rubble'.encode()] * 11)
            # All ordinary damage fire attachments retain their entire stock
            # descriptor, including offsets, native frames and TILE references.
            for key in market:
                if key >> 24 and 96 <= (key & 0xffffff) <= 101:
                    self.assertEqual(private[key], market[key])


if __name__ == '__main__':
    unittest.main()
