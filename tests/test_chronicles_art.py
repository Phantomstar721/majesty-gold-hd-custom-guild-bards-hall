"""Model native visibility/orientation and building attachment, not a round trip."""
import struct
import unittest
from PIL import Image, ImageOps
from test_building_art import GAME
from cam_io import read, section, get, frame_references, u32
from bards_building_art import decode_indices, image as building_image
from bards_chronicles_art import append_art, indexed_frames, frames as source_frames, frame_hotspots, validate_owner_attachment, SIZE, ROOT_OFFSET, ATTACHMENT, SOURCE
from bards_chronicles_motion import CENTER


class ChroniclesArtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock = read(GAME / 'Data/maindata.cam')
        cls.tiles = list(section(cls.stock, b'TILE').entries)
        cls.palettes = list(section(cls.stock, b'SPLT').entries)
        cls.image, _ = append_art(cls.stock, cls.tiles, cls.palettes)

    def test_stock_flags_timing_and_stream_layout_are_unchanged(self):
        original = get(self.stock, b'IMAG', SOURCE)
        restored = bytearray(self.image.data)
        for p in frame_references(restored, 64):
            self.assertEqual(u32(restored, p) >> 16, u32(original, p) >> 16)
            restored[p:p+4] = original[p:p+4]
        self.assertEqual(restored, original)

    def test_native_hide_and_orientation_leave_every_authored_frame_complete(self):
        authored, _ = indexed_frames()
        hotspots = frame_hotspots(source_frames())
        frames = [bytearray(SIZE[0]*SIZE[1]) for _ in range(30)]
        for i, p in enumerate(frame_references(self.image.data, 64)):
            r = u32(self.image.data, p)
            tile = self.tiles[r & 65535].data
            hotspot = list(struct.unpack_from('<hh', tile, 10))
            pixels = decode_indices(tile, size=SIZE, hotspot=tuple(hotspot))
            if i < 30:
                self.assertFalse(r & 0x40000000, 'Primary stream must always render')
                self.assertEqual(pixels, authored[i])
            else:
                self.assertFalse(any(pixels), 'Companion payload must remain transparent')
            if r & 0x40000000:
                continue  # 0x005E95C3: skip drawing; no vertical reflection.
            plane = Image.frombytes('L', SIZE, pixels)
            current_horizontal = bool(struct.unpack_from('<H', tile, 8)[0] & 0x10)
            if bool(r & 0x20000000) != current_horizontal:
                plane = ImageOps.mirror(plane); hotspot[0] = SIZE[0]-hotspot[0]
            self.assertEqual(tuple(hotspot), hotspots[i % 30])
            result = frames[i % 30]
            for j, value in enumerate(plane.tobytes()):
                if value:
                    self.assertEqual(result[j], 0, 'Streams overdraw the same pixel')
                    result[j] = value
        self.assertEqual([bytes(f) for f in frames], authored)
        self.assertEqual(self.palettes[-1].data[:8], self.palettes[0].data[:8])

    def test_orbiting_notes_do_not_change_geometric_anchor(self):
        pictures = source_frames()
        hotspots = frame_hotspots(pictures)
        self.assertEqual(len(set(hotspots)), 1)
        for hotspot in hotspots:
            for axis in (0, 1):
                self.assertEqual(ATTACHMENT[axis] + CENTER[axis] - hotspot[axis], ROOT_OFFSET[axis])

    def test_fresh_pixels_use_ordinary_indexed_header_for_every_native_frame(self):
        for p in frame_references(self.image.data, 64):
            payload = self.tiles[u32(self.image.data, p) & 65535].data
            self.assertEqual(struct.unpack_from('<5H', payload), (3, SIZE[1], SIZE[0], 0, 32))
            self.assertEqual(struct.unpack_from('<H', payload, 14)[0], 8)

    def test_registration_is_bound_to_actual_hotspot_one_attachment(self):
        owner = building_image(self.stock, b'ABH3')
        validate_owner_attachment(owner)
        wrong = bytearray(owner)
        table = [struct.unpack_from('<II', owner, 24+i*8) for i in range(u32(owner, 20))]
        start = next(start for key, start in table if key == 400)
        direction = u32(owner, start+64)
        struct.pack_into('<h', wrong, start+direction+20, 14)
        with self.assertRaisesRegex(ValueError, 'attachment/projection'):
            validate_owner_attachment(wrong)


if __name__ == '__main__': unittest.main()
