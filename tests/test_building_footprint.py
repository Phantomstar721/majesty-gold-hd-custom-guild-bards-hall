"""Protect the native collision boundary, entrance and unrelated art streams."""
import copy
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import bards_building_art as art
import bards_building_footprint as footprint
from cam_io import read, section, u32


def contains(point, vertices):
    x, y = point
    inside = False
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        if (a[1] > y) != (b[1] > y):
            if x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
                inside = not inside
    return inside


class BuildingFootprintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock = read(Path(r'C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/Data/maindata.cam'))
        cls.manifest, cls.mapping = art.load_handoff()
        cls.geometry = footprint.load_footprints(cls.manifest)
        cls.authority = art.image(cls.stock, b'ABT1')
        cls.authority_inactive = art.descriptors(cls.authority)[208]
        cls.tiles = list(section(cls.stock, b'TILE').entries)
        cls.images, _ = art.append_buildings(cls.stock, cls.tiles,
            list(section(cls.stock, b'SPLT').entries), art.image(cls.stock, b'ABV1'))

    def test_native_geometry_changes_only_blocking_and_placement(self):
        indices = {obj['key']: next(i for i, tile in enumerate(self.tiles)
                   if tile.name == art.object_name(obj)) for obj in self.manifest['objects']}
        for level, building in enumerate(self.images, 1):
            with self.subTest(level=level):
                _, old_sets = art.template_sets(self.stock, level, art.image(self.stock, b'ABV1'))
                for row in self.mapping['sets']:
                    if row['level'] == level:
                        old_sets[row['set']] = art.patch_stream(old_sets[row['set']], row, indices)
                old_sets[400] = art.patch_stream(old_sets[400], {
                    'direction': 0, 'stream': 0, 'direction_anchor': [0, 0],
                    'objects': [f'level-{level}-inactive'], 'holds': [1], 'frame_metadata': [0]}, indices)
                new_sets = art.descriptors(building.data)
                self.assertEqual(list(old_sets), list(new_sets))
                self.assertNotIn(8, new_sets)
                for sid in old_sets:
                    if sid != 208:
                        self.assertEqual(old_sets[sid], new_sets[sid], sid)
                before, after = old_sets[208], new_sets[208]
                _, old_rects, _, old_tail = footprint.direction_geometry(before)
                _, rects, polygons, tail = footprint.direction_geometry(after)
                shape = self.geometry['levels'][str(level)]
                self.assertEqual({0}, set(polygons))
                self.assertEqual(struct.pack('<4h', *shape['rectangle']), rects[0])
                self.assertEqual(shape['polygon_points'], [list(p) for p in struct.iter_unpack('<ii', polygons[0][4:])])
                self.assertEqual({k: rects[k] for k in (1, 2)}, {k: old_rects[k] for k in (1, 2)})
                self.assertEqual(before[:80], after[:80])
                self.assertEqual(before[84:88], after[84:88])
                self.assertEqual(before[old_tail:], after[tail:])
                self.assertEqual(after, footprint.patch_inactive(after, self.authority, self.authority_inactive, shape))
                cursor = 24 + 8 * len(new_sets)
                for order, data in enumerate(new_sets.values()):
                    self.assertEqual(cursor, u32(building.data, 28 + 8 * order))
                    cursor += len(data)
                self.assertEqual(len(building.data), cursor)

    def test_stage_steps_masonry_blocked_and_exterior_clear_at_every_level(self):
        for level, shape in self.geometry['levels'].items():
            points = shape['polygon_points']
            for group, expected in (('blocked', True), ('clear', False)):
                for label, point in shape['coverage_probes'][group].items():
                    with self.subTest(level=level, region=label):
                        self.assertEqual(expected, contains(point, points))
            self.assertTrue(contains((59, 104), points))  # unchanged stock entrance
            _, _, polygons, _ = footprint.direction_geometry(art.descriptors(
                art.image(self.stock, f'ABH{level}'.encode()))[208])
            old = list(struct.iter_unpack('<ii', polygons[0][4:]))
            # A neighborhood around the exposed stage corner, not a single point.
            for dx in (-8, 0, 8):
                for dy in (-8, 0, 8):
                    self.assertTrue(contains((-31 + dx, 135 + dy), points))
            self.assertFalse(contains((-31, 135), old))
            self.assertFalse(contains((67, 163), old))  # old front steps unblocked

    def test_invalid_geometry_and_changed_reference_rejected(self):
        shape = self.geometry['levels']['1']
        reversed_shape = copy.deepcopy(shape)
        reversed_shape['polygon_points'].reverse()
        with self.assertRaisesRegex(ValueError, 'winding'):
            footprint.validate_shape(reversed_shape)
        bounds = copy.deepcopy(shape)
        bounds['rectangle'][0] -= 1
        with self.assertRaisesRegex(ValueError, 'rectangle'):
            footprint.validate_shape(bounds)
        crossing = copy.deepcopy(shape)
        crossing['polygon_points'][2], crossing['polygon_points'][4] = (
            crossing['polygon_points'][4], crossing['polygon_points'][2])
        with self.assertRaisesRegex(ValueError, 'intersect'):
            footprint.validate_shape(crossing)
        duplicate = copy.deepcopy(shape)
        duplicate['polygon_points'].append(duplicate['polygon_points'][0])
        with self.assertRaisesRegex(ValueError, 'invalid'):
            footprint.validate_shape(duplicate)
        authority = bytearray(self.authority)
        authority[-1] ^= 1
        with self.assertRaisesRegex(ValueError, 'authority'):
            footprint.patch_inactive(self.authority_inactive, bytes(authority), self.authority_inactive, shape)
        changed_art = copy.deepcopy(self.manifest)
        next(o for o in changed_art['objects'] if o['key'] == 'level-3-inactive')['tile_sha256'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'reference artwork'):
            footprint.load_footprints(changed_art)
        with self.assertRaisesRegex(ValueError, 'polygon is invalid'):
            footprint.direction_geometry(self.authority_inactive[:140])

    def test_stock_move_target_and_rear_approach_are_not_cut_off(self):
        for level, shape in self.geometry['levels'].items():
            with self.subTest(level=level):
                # The live stuck builder and Guild both occupied grid (1044,
                # 1016). V1's bounds started four rows south, so IsAdjacent's
                # first rectangle-overlap check could never reach its bitmap.
                self.assertTrue(contains((0, 0), shape['polygon_points']))
                self.assertLess(shape['rectangle'][1], 0)
                self.assertEqual([[61, -7], [-64, -3], [-96, 7], [-100, 69]],
                                 shape['polygon_points'][:4])
                _, _, polygons, _ = footprint.direction_geometry(art.descriptors(
                    art.image(self.stock, f'ABH{level}'.encode()))[208])
                old = list(struct.iter_unpack('<ii', polygons[0][4:]))
                for x in range(-100, 120, 4):
                    for y in range(-8, 133, 4):
                        if contains((x, y), old):
                            self.assertTrue(contains((x, y), shape['polygon_points']), (x, y))
                # The prior art-only fit is simple and correctly wound; it
                # must still fail because its native movement origin is clear.
                art_only = copy.deepcopy(shape)
                art_only['polygon_points'] = [[x, y + 80] for x, y in shape['polygon_points']]
                art_only['rectangle'][1] += 80
                art_only['rectangle'][3] += 80
                with self.assertRaisesRegex(ValueError, 'movement origin'):
                    footprint.validate_shape(art_only)

    def test_rejects_exact_disconnected_footprint_from_stuck_builder_capture(self):
        failed_v1 = {
            'rectangle': [-99, 59, 121, 179],
            'polygon_points': [[13, 59], [-59, 73], [-97, 95], [-99, 127],
                [-39, 153], [-5, 143], [21, 179], [51, 179], [119, 164],
                [119, 135], [121, 119], [121, 87], [77, 67]],
        }
        with self.assertRaisesRegex(ValueError, 'movement origin'):
            footprint.validate_shape(failed_v1)


if __name__ == '__main__':
    unittest.main()
