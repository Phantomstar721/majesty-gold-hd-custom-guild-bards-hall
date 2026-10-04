"""Approved Spellsinger takes and exact stock phase properties, without leaks."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
from test_hiring import ROOT, SDK
from bards_audio import build_audio, checked_wave
from build_bards_hall import build_units
from cam_io import get, read, section


class SpellsingerAudioTests(unittest.TestCase):
    def test_cultist_clone_and_literal_wizard_cast(self):
        game = SDK.parent.parent
        bank = ROOT/'audio/spellsinger-v1'
        picks = json.loads((bank/'selected-takes.json').read_text())['selections']
        self.assertEqual([p['take'] for p in picks], [1,3,3,4,2,3,3,1,2,1,3])
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            build_audio(game, output)
            xml = ET.parse(output/'bards_sounds.xml')
            stock_xml = ET.parse(SDK/'Data/M_Sounds.xml')
            native = stock_xml.find('.//Description[@ID="CT01"]')
            actual = xml.find('.//Description[@ID="BSV1"]')
            self.assertEqual(actual.get('Name'), 'SingerV')
            waves = read(output/'bards_voices.cam')
            self.assertEqual(len(section(waves, b'WAVE').entries), 36)
            stock_keys = {e.name[:4] for e in section(read(game/'Data/voices.cam'), b'WAVE').entries}
            self.assertFalse(stock_keys & {e.name[:4] for e in section(waves, b'WAVE').entries})
            self.assertEqual(len(section(read(output/'bards_sounddesc.cam'), b'DSND').entries), 3)
            for item in picks:
                field = actual.find(f'./Engine/Phase[@ID="{item["phase"]}"]/Wave')
                self.assertEqual(get(waves, b'WAVE', field.get('value').encode()),
                                 checked_wave(bank/item['file'], item['sha256']))
            original = get(read(game/'Data/sounddesc.cam'), b'DSND', b'CT01Cultist')
            restored = get(read(output/'bards_sounddesc.cam'), b'DSND', b'BSV1SingerV')
            restored = restored.replace(b'BSV1',b'CT01').replace(b'SingerV',b'Cultist')
            for phase in actual.findall('./Engine/Phase'):
                key = phase.get('ID')
                old = (stock_xml.find('.//Description[@ID="WZ01"]/Engine/Phase[@ID="VFX_CAST_SPELL1"]')
                       if key == 'VFX_CAST_SPELL1' else native.find(f'./Engine/Phase[@ID="{key}"]'))
                private_wave = phase.find('Wave').get('value')
                old_wave = old.find('Wave').get('value')
                if key in ('VFX_SPECIAL1','VFX_JIHAD'):
                    self.assertEqual(private_wave, 'SV00')
                elif key in ('Attack','GetHit'):
                    self.assertEqual(private_wave, old_wave)
                restored = restored.replace(private_wave.encode(), old_wave.encode(), 1)
                phase.find('Wave').set('value', old_wave)
                self.assertEqual(ET.tostring(phase), ET.tostring(old))
            position = restored.index(b'GVP0')
            wizard = get(read(game/'Data/sounddesc.cam'), b'DSND', b'WZ01Wizard')
            start = wizard.index(b'WZCL') - 4
            self.assertEqual(restored[position:position+60], wizard[start:start+60])
            restored = bytearray(restored[:position] + restored[position+60:])
            for offset in (4,20):
                struct.pack_into('<I', restored, offset, struct.unpack_from('<I', original, offset)[0])
            struct.pack_into('<I', restored, restored.index(b'PRIM')+24, 14)
            self.assertEqual(bytes(restored), original)
            engine = actual.find('Engine')
            engine.remove(engine.find('./Phase[@ID="VFX_CAST_SPELL1"]'))
            actual.attrib = native.attrib.copy()
            self.assertEqual(ET.tostring(actual).strip(), ET.tostring(native).strip())

    def test_unit_uses_private_bank(self):
        root = ET.fromstring(build_units(SDK))
        expected = {'Troubadour':'TroubV', 'Blade_Dancer':'DancV', 'Spellsinger':'SingerV'}
        for hero,bank in expected.items():
            self.assertEqual(root.find(f'.//Description[@Name="{hero}"]/Engine/DefaultSound').get('value'), bank)


if __name__ == '__main__':
    unittest.main()
