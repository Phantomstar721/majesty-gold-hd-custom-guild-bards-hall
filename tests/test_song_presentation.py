"""Presentation routing must not change action timing or effect ownership."""
import json
import struct
import unittest
from test_hiring import ROOT
from cam_io import Entry, name
from bards_world_effects import patch_hero_cast, ONESHOTS

class SongPresentationTests(unittest.TestCase):
    def test_deflect_preserves_approved_peak_shape(self):
        from PIL import Image
        from bards_world_effects import animation_source, strip_frames
        source=animation_source('deflect')
        self.assertEqual(source.name,'deflect-pilot-r2.png')
        approved=Image.open(ROOT/'art/dancer-effects-v1/deflect-native.png').convert('RGBA')
        frames=strip_frames('deflect',(28,24))
        self.assertEqual(frames[1].tobytes(),approved.tobytes())
        for frame in frames:
            self.assertEqual(frame.convert('RGB').tobytes(),frames[1].convert('RGB').tobytes())

    def test_dancer_cast_has_no_shared_finale_flash_or_body_changes(self):
        authority=json.loads((ROOT/'reference/healer-package-authority-v2.json').read_text())
        records=authority['package_contract']['cast_secondary_stream']['occurrences']
        blob=bytes(max(r['reference_offset'] for r in records)+4)
        tiles=[Entry(name(b'unused'),b''),Entry(name(b'BDZ00000'),b'')]
        changed=patch_hero_cast(blob,'BDD1',authority,tiles)
        allowed=set()
        for r in records:
            offset=r['reference_offset']
            allowed.update(range(offset,offset+4))
            self.assertEqual(struct.unpack_from('<I',changed,offset)[0],1)
        self.assertTrue(all(a==b for i,(a,b) in enumerate(zip(blob,changed)) if i not in allowed))

    def test_dancer_effect_descriptions_have_distinct_stock_owned_images(self):
        from test_hiring import SDK
        from bards_abilities import build_descriptions
        root=build_descriptions(SDK)
        for ability,prefix in [('Deflect','BDF1'),('Riposte','BRP1'),('Flourish','BFL1'),('Finale','BFX5')]:
            effect=root.find(f'./Description[@Name="Bards_{ability}_Flash"]')
            self.assertEqual(effect.find('./Engine/ImageIDBase').get('value'),prefix)

    def test_troub_and_singer_have_separate_cast_art_without_body_changes(self):
        authority=json.loads((ROOT/'reference/healer-package-authority-v2.json').read_text())
        records=authority['package_contract']['cast_secondary_stream']['occurrences']
        blob=bytes(max(r['reference_offset'] for r in records)+4)
        tiles=[Entry(name(f'{prefix}{n:04d}'.encode()),b'') for prefix in ('BFX6','BFX5','BFX1') for n in range(28)]
        singer=patch_hero_cast(blob,'BDS1',authority,tiles)
        changed=patch_hero_cast(blob,'BDT1',authority,tiles)
        allowed=set()
        for r in records:
            if r['frame']>=5: continue
            allowed.update(range(r['metadata_offset'],r['metadata_offset']+4))
            allowed.update(range(r['reference_offset'],r['reference_offset']+4))
            tile=tiles[struct.unpack_from('<I',changed,r['reference_offset'])[0]]
            self.assertTrue(tile.name.startswith(b'BFX6'))
            singer_tile=tiles[struct.unpack_from('<I',singer,r['reference_offset'])[0]]
            self.assertTrue(singer_tile.name.startswith(b'BFX1'))
        self.assertTrue(all(a==b for i,(a,b) in enumerate(zip(blob,changed)) if i not in allowed))
        self.assertTrue(all(a==b for i,(a,b) in enumerate(zip(blob,singer)) if i not in allowed))

    def test_recipient_flash_is_not_a_new_buff_or_cast_action(self):
        for song,file in [('Valor','Bards_Effects.gpl'),('Refrain','Bards_Effects.gpl'),
                          ('March','Bards_Rates.gpl'),('Satire','Bards_Rates.gpl')]:
            source=(ROOT/'src/gpl'/file).read_text()
            self.assertEqual(source.count(f'$CreateEffector(Recipient, "Bards_{song}_Flash", 0);'),1)
            row=next(r for r in ONESHOTS if r[0]==f'Bards_{song}_Flash')
            self.assertEqual(row[2],'healer_healing_effector')
        street=(ROOT/'src/gpl/Bards_Street.gpl').read_text()
        self.assertIn('$CreateEffector(Singer, "Bards_Song_Flash", 0);',street)

if __name__=='__main__': unittest.main()
