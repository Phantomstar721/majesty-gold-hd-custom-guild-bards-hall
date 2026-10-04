"""Native UI encoding keeps sparse artwork exact and reserves engine indices."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from build_bards_hall import interface_tile, load_art_module
from cam_io import frame_references, get, read, section, u32

GAME = Path(r'C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')


class InterfaceTileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.art = load_art_module(GAME)
        stock = read(GAME / 'Data/interfacedata.cam')
        imag = get(stock, b'IMAG', b'INBwicons weapons')
        reference = frame_references(imag, u32(imag, 24))[0]
        cls.template = section(stock, b'TILE').entries[u32(imag, reference) & 65535].data

    def encode(self, pixels):
        image = Image.new('RGB', (23, 23))
        image.putdata(pixels)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'icon.png'
            image.save(source)
            return image, interface_tile(self.art, self.template, source, image.size)

    def test_sparse_palette_is_lossless_without_reserved_pixels(self):
        for count in (1, 2, 253):
            with self.subTest(colours=count):
                pixels = [(i % count, (i % count) // 2, 31) for i in range(529)]
                original, encoded = self.encode(pixels)
                decoded = self.art.decode_tile_v1(encoded).convert('RGB')
                self.assertEqual(decoded.tobytes(), original.tobytes())
                plane = encoded[26:555]
                self.assertNotIn(0, plane)
                self.assertNotIn(255, plane)
                self.assertEqual(len(encoded), 555 + 1032)
                self.assertEqual(struct.unpack_from('<I', encoded, 22)[0], 555)

    def test_full_palette_preserves_audited_quantizer_bytes(self):
        pixels = [(i % 256, i // 256, (i * 31) % 256) for i in range(529)]
        original, encoded = self.encode(pixels)
        reference = self.art.quantize_interface(original, 'icon.png')
        self.assertEqual(encoded[26:], reference['plane'] + reference['palette'])


if __name__ == '__main__':
    unittest.main()
