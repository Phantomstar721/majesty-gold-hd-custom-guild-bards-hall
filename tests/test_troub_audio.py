"""Stock voice dispatch, private IDs, exact supplied takes and PCM contract."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from test_hiring import ROOT, SDK
from bards_audio import build_audio, checked_wave, AUDIO
from cam_io import read, section, get


class TroubAudioTests(unittest.TestCase):
    def test_private_audio_preserves_stock_dispatch(self):
        game=SDK.parent.parent
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp);build_audio(game,out)
            xml=ET.parse(out/'bards_sounds.xml')
            original=ET.parse(SDK/'Data/M_Sounds.xml').find('.//Description[@ID="HR01"]')
            actual=xml.find('.//Description')
            self.assertEqual(actual.get('Name'),'TroubV')
            waves=section(read(out/'bards_voices.cam'),b'WAVE').entries
            self.assertEqual(len([e for e in waves if e.name[:2] == b'TV']),12)
            stockwaves={e.name[:4] for e in section(read(game/'Data/voices.cam'),b'WAVE').entries}
            self.assertFalse({e.name[:4] for e in waves}&stockwaves)
            picks=json.loads((AUDIO/'runtime-selection.json').read_text())['clips']
            self.assertEqual(picks['VFX_LEVEL_10']['file'],'revisions/2026-10-03/processed/level10.wav')
            self.assertEqual(picks['Death']['file'],'revisions/2026-10-03/processed/death.wav')
            binary=get(read(out/'bards_sounddesc.cam'),b'DSND',b'BT01TroubV')
            restored=binary.replace(b'BT01',b'HR01').replace(b'TroubV',b'Healer')
            for phase in actual.findall('./Engine/Phase'):
                old=original.find(f'./Engine/Phase[@ID="{phase.get("ID")}"]')
                native=old.find('Wave').get('value');private=phase.find('Wave').get('value')
                if phase.get('ID') in picks:
                    clip=picks[phase.get('ID')]
                    self.assertEqual(get(read(out/'bards_voices.cam'),b'WAVE',private.encode()),
                                     checked_wave(AUDIO/clip['file'],clip['sha256']))
                restored=restored.replace(private.encode(),native.encode())
                phase.find('Wave').set('value',native)
            self.assertEqual(restored,get(read(game/'Data/sounddesc.cam'),b'DSND',b'HR01Healer'))
            actual.attrib=original.attrib.copy()
            self.assertEqual(ET.tostring(actual).strip(),ET.tostring(original).strip())


if __name__=='__main__':unittest.main()
