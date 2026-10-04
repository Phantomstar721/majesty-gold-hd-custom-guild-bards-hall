"""Presentation must refer to owned identities without manufacturing spells."""
import unittest
import xml.etree.ElementTree as ET
from test_hiring import SDK
from bards_abilities import build_descriptions
from bards_ability_ui import features
from majesty_cam.hero_info import parse_hero_info


class AbilityUITests(unittest.TestCase):
    def test_private_spell_and_effect_images_do_not_shadow_base_or_expansion(self):
        from cam_io import read, section
        game = SDK.parent.parent
        stock_ids = {entry.name[:4] for path in
                     (game/'Data/interfacedata.cam', game/'DataMX/mx_interfacedata.cam')
                     for entry in section(read(path), b'IMAG').entries}
        for row in features():
            self.assertNotIn(row['image_id'].encode('ascii'), stock_ids,
                             f"{row['feature_key']} shadows a stock IMAG")

    def test_flourish_is_stock_physical_action_with_cast_presentation(self):
        import copy
        from bards_abilities import description
        stock = ET.parse(SDK / 'Data/M_Actions.xml').getroot()
        expected = description(stock, 'basic_attack')
        actual = copy.deepcopy(next(d for d in build_descriptions(SDK) if d.get('Name') == 'Bards_Flourish_Strike'))
        actual.attrib = expected.attrib.copy()
        self.assertEqual(actual.find('./Engine/ImageSet').get('value'), 'Cast')
        actual.find('./Engine/ImageSet').set('value', 'Attack')
        self.assertEqual(actual.find('./Engine/Script').get('GPLFunction'), 'Bards_Flourish_Attack')
        actual.find('./Engine/Script').set('GPLFunction', 'make_attack')
        self.assertEqual(actual.find('./Game/ValidationScript').get('value'), 'Bards_Flourish_Check')
        actual.remove(actual.find('Game'))
        self.assertEqual(ET.tostring(actual), ET.tostring(expected))

    def test_passive_encore_and_finale_use_the_approved_effect_art(self):
        from bards_ability_ui import append_art, approved_enchantment_masters
        used = []
        def encode(art, template, master, size):
            used.append(master)
            return template
        append_art(SDK.parent.parent, [], None, encode)
        approved = approved_enchantment_masters()
        self.assertEqual(used[12:14], [approved['roused'], approved['encore']])

    def test_encore_roused_art_requires_review_and_matching_bytes(self):
        import hashlib
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from bards_ability_ui import approved_enchantment_masters
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            art = root / 'art/encore-roused-icons-v1'
            art.mkdir(parents=True)
            master = art / 'sample.png'
            master.write_bytes(b'reviewed')
            proof = dict(runtime_custom_art_approved=False, masters={key: dict(
                file=master.name, sha256=hashlib.sha256(master.read_bytes()).hexdigest())
                for key in ('encore', 'roused')})
            status = art / 'review-status.json'
            with patch('bards_ability_ui.ROOT', root):
                status.write_text(json.dumps(proof))
                self.assertEqual(approved_enchantment_masters(), {})
                proof.update(runtime_custom_art_approved=True)
                status.write_text(json.dumps(proof))
                with self.assertRaisesRegex(ValueError, 'explicit visual approval'):
                    approved_enchantment_masters()
                proof['approval_record'] = 'User approved both native-size samples'
                status.write_text(json.dumps(proof))
                self.assertEqual(set(approved_enchantment_masters()), {'encore', 'roused'})
                master.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'approved revision'):
                    approved_enchantment_masters()

    def test_approved_runtime_art_rejects_changed_bytes(self):
        import hashlib
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from bards_ability_ui import approved_masters, SKILLS
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            art = root / 'art/ability-icons-v2'
            art.mkdir(parents=True)
            (art / 'approved.png').write_bytes(b'approved sample')
            proof = dict(runtime_custom_art_approved=True, bulk_generation_approved=True,
                         approval_record='explicit user sample approval',
                         masters={key: dict(file='approved.png', sha256=hashlib.sha256(b'approved sample').hexdigest())
                                  for key, *_ in SKILLS})
            (art / 'approval.json').write_text(json.dumps(proof))
            with patch('bards_ability_ui.ROOT', root):
                self.assertEqual(set(approved_masters()), {r[0] for r in SKILLS})
                (art / 'approved.png').write_bytes(b'unreviewed replacement')
                with self.assertRaisesRegex(ValueError, 'has changed'): approved_masters()

    def test_all_private_abilities_avoid_every_stock_description_identity(self):
        stock = {(d.get('type'), d.get('ID')) for p in (SDK / 'Data').glob('*.xml')
                 for d in ET.parse(p).getroot().iter('Description')}
        for d in build_descriptions(SDK):
            self.assertNotIn((d.get('type'), d.get('ID')), stock, d.get('Name'))

    def test_dancer_rows_are_display_only_and_unlock_at_actual_levels(self):
        rows = [r for r in features() if r['subject_id'] == 'BDD1']
        self.assertEqual([r['unlock_level'] for r in rows], [1, 3, 5, 8, 8])
        self.assertTrue(all(r['kind'] == 'passive' for r in rows))
        actions = [d.get('Name') for d in build_descriptions(SDK) if d.get('type') == 'Action']
        self.assertFalse(any(name in actions for name in ('Riposte', 'Deflect', 'Dueling_Flourish')))

    def test_every_icon_has_private_identity_and_effects_use_live_overlays(self):
        rows = features()
        for row in rows: parse_hero_info(row)
        self.assertEqual(len({r['image_id'] for r in rows}), len(rows))
        overlays = {d.get('ID') for d in build_descriptions(SDK) if d.get('subType') == 'Overlay'}
        active = [r for r in rows if r['kind'] == 'enchantment']
        self.assertEqual(len(active), 9)
        self.assertTrue(all(r['subject_id'] in overlays and r['unlock_level'] == 0 for r in active))
        self.assertEqual({r['subject_id'] for r in active if r['display_text'] == 'Marching Song'}, {'BME1', 'BME2'})

    def test_unapproved_art_is_not_consumed_and_stock_pixels_are_literal(self):
        from bards_ability_ui import append_art
        from cam_io import read, section, get
        from pathlib import Path
        from unittest.mock import patch
        game = SDK.parent.parent
        tiles = []
        with patch('bards_ability_ui.approved_masters', return_value={}), patch('bards_ability_ui.approved_enchantment_masters', return_value={}):
            images = append_art(game, tiles, None, None)
        stock_tiles = {e.data for path in ('Data/interfacedata.cam', 'DataMX/mx_interfacedata.cam')
                       for e in section(read(game / path), b'TILE').entries}
        self.assertEqual(len(images), len(features()))
        self.assertTrue(all(t.data in stock_tiles for t in tiles))


if __name__ == '__main__': unittest.main()
