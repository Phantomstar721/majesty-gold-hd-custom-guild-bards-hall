"""Selected takes, private stock dispatch, and preservation of both native banks."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
from test_hiring import ROOT, SDK
from bards_audio import build_audio, checked_wave
from build_bards_hall import build_units
from cam_io import read, section, get


class DancerAudioTests(unittest.TestCase):
    def test_selected_audio_preserves_stock_rogue_and_cast_slot(self):
        game = SDK.parent.parent
        picks = json.loads((ROOT/'audio/blade-dancer-v1/selected-takes.json').read_text())['selections']
        self.assertEqual([p['take'] for p in picks], [1,3,3,1,1,3,1,1,3,3,3])
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            build_audio(game, output)
            xml = ET.parse(output/'bards_sounds.xml')
            stock_xml = ET.parse(SDK/'Data/M_Sounds.xml')
            native = stock_xml.find('.//Description[@ID="RE01"]')
            actual = xml.find('.//Description[@ID="BDV1"]')
            self.assertEqual(actual.get('Name'), 'DancV')
            waves = read(output/'bards_voices.cam')
            self.assertEqual(len([e for e in section(waves, b'WAVE').entries if e.name[:2] in (b'TV',b'DV')]), 24)
            stock_keys = {e.name[:4] for e in section(read(game/'Data/voices.cam'), b'WAVE').entries}
            self.assertFalse(stock_keys & {e.name[:4] for e in section(waves, b'WAVE').entries})
            original = get(read(game/'Data/sounddesc.cam'), b'DSND', b'RE01Rogue')
            restored = get(read(output/'bards_sounddesc.cam'), b'DSND', b'BDV1DancV')
            restored = restored.replace(b'BDV1', b'RE01').replace(b'DancV', b'Rogue')
            for item in picks:
                field = actual.find(f'./Engine/Phase[@ID="{item["phase"]}"]/Wave')
                self.assertEqual(get(waves, b'WAVE', field.get('value').encode()),
                                 checked_wave(ROOT/'audio/blade-dancer-v1'/item['file'], item['sha256']))
            for phase in actual.findall('./Engine/Phase'):
                key = phase.get('ID')
                old = (stock_xml.find('.//Description[@ID="PN01"]/Engine/Phase[@ID="VFX_CAST_SPELL1"]')
                       if key == 'VFX_CAST_SPELL1' else native.find(f'./Engine/Phase[@ID="{key}"]'))
                private_wave = phase.find('Wave').get('value')
                old_wave = old.find('Wave').get('value')
                restored = restored.replace(private_wave.encode(), old_wave.encode())
                phase.find('Wave').set('value', old_wave)
                self.assertEqual(ET.tostring(phase), ET.tostring(old))
            # Remove exactly the literal Paladin cast record and restore lengths/count.
            position = restored.index(b'GVP0')
            paladin = get(read(game/'Data/sounddesc.cam'), b'DSND', b'PN01Paladin')
            start = paladin.index(b'PNCL') - 4
            self.assertEqual(restored[position:position+60], paladin[start:start+60])
            restored = bytearray(restored[:position] + restored[position+60:])
            for offset in (4,20):
                struct.pack_into('<I', restored, offset, struct.unpack_from('<I', original, offset)[0])
            struct.pack_into('<I', restored, restored.index(b'PRIM')+24, 13)
            self.assertEqual(bytes(restored), original)
            engine = actual.find('Engine')
            engine.remove(engine.find('./Phase[@ID="VFX_CAST_SPELL1"]'))
            actual.attrib = native.attrib.copy()
            self.assertEqual(ET.tostring(actual).strip(), ET.tostring(native).strip())

    def test_only_dancer_uses_private_dancer_bank(self):
        root = ET.fromstring(build_units(SDK))
        self.assertEqual(root.find('.//Description[@Name="Blade_Dancer"]/Engine/DefaultSound').get('value'), 'DancV')
        self.assertEqual(root.find('.//Description[@Name="Troubadour"]/Engine/DefaultSound').get('value'), 'TroubV')
        self.assertEqual(root.find('.//Description[@Name="Spellsinger"]/Engine/DefaultSound').get('value'), 'SingerV')


if __name__ == '__main__':
    unittest.main()
