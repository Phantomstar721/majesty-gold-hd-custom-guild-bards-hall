"""Private stock hero sound dispatch with selected actor recordings."""
import copy
import hashlib
import io
import json
import struct
from pathlib import Path
import wave
import xml.etree.ElementTree as ET
from cam_io import Entry, Section, get, name, read, write

ROOT=Path(__file__).resolve().parents[1]
AUDIO=ROOT/'audio/troubadour-v1'
SOUND_ID='BT01'
SOUND_NAME='TroubV'  # Same byte length as Healer; native HEAD sizes unchanged.


def checked_wave(path, expected):
    payload=path.read_bytes()
    assert hashlib.sha256(payload).hexdigest()==expected, f'Audio changed: {path}'
    with wave.open(io.BytesIO(payload),'rb') as w:
        assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getcomptype())==(1,2,22050,'NONE')
        assert w.getnframes()>0
    return payload


def build_audio(game, destination):
    manifest=json.loads((AUDIO/'manifest.json').read_text())
    selection=json.loads((AUDIO/'runtime-selection.json').read_text())
    stock=ET.parse(game/'SDK/OriginalQuests/Data/M_Sounds.xml').getroot()
    sound=copy.deepcopy(stock.find('.//Description[@ID="HR01"]'))
    sound.attrib.update(ID=SOUND_ID,Name=SOUND_NAME)
    dsnd=get(read(game/'Data/sounddesc.cam'),b'DSND',b'HR01Healer')
    assert dsnd.count(b'HR01')==1 and dsnd.count(b'Healer')==1
    private=dsnd.replace(b'HR01',SOUND_ID.encode()).replace(b'Healer',SOUND_NAME.encode())
    entries=[]
    for i,clip in enumerate(manifest['clips'],1):
        phase=clip['phase']; wave_id=f'TV{i:02d}'
        chosen=selection['clips'][phase]
        payload=checked_wave(AUDIO/chosen['file'],chosen['sha256'])
        entries.append(Entry(name(wave_id.encode()),payload))
        field=sound.find(f'./Engine/Phase[@ID="{phase}"]/Wave')
        old=field.get('value').encode();assert private.count(old)==1
        private=private.replace(old,wave_id.encode());field.set('value',wave_id)
    # No idle-gesture recording was supplied. Preserve the native cue slot and
    # cooldown group, but avoid leaking the stock Healer's spoken idle line.
    silent=io.BytesIO()
    with wave.open(silent,'wb') as w:
        w.setparams((1,2,22050,0,'NONE','not compressed'));w.writeframes(bytes(4410))
    entries.append(Entry(name(b'TV00'),silent.getvalue()))
    field=sound.find('./Engine/Phase[@ID="VFX_SPECIAL1"]/Wave')
    assert private.count(field.get('value').encode())==1
    private=private.replace(field.get('value').encode(),b'TV00');field.set('value','TV00')
    assert len(private)==len(dsnd)
    destination.mkdir(parents=True,exist_ok=True)
    write(destination/'bards_voices.cam',(Section(b'WAVE',bytes(4),tuple(entries)),))
    write(destination/'bards_sounddesc.cam',(Section(b'DSND',bytes(4),(Entry(name(b'BT01TroubV'),private),)),))
    root=ET.Element('Majesty');root.append(sound)
    ET.ElementTree(root).write(destination/'bards_sounds.xml',encoding='utf-8',xml_declaration=True)
    build_dancer_audio(game, destination)
    build_spellsinger_audio(game, destination)


def add_stock_cast_phase(base, caster, cast_wave=b'PNCL', expected_count=13):
    """Insert a literal stock caster phase into a native bank lacking one.

    Existing native phase records remain byte-identical. Update only the two
    enclosing DATA/DSND byte sizes and the phase count for the inserted record.
    """
    assert base[:4] == caster[:4] == b'DSND'
    assert base[16:20] == caster[16:20] == b'DATA'
    assert b'GVP0' not in base
    start = caster.index(cast_wave) - 4
    cast = caster[start:start + 60]
    assert cast[:12] == b'GVP0' + cast_wave + b'SG21' and caster[start + 60:start + 64] == b'EDH0'
    insertion = base.index(b'GVS0') + 60
    assert base[insertion:insertion + 4] == b'EDH0'
    output = bytearray(base[:insertion] + cast + base[insertion:])
    for offset in (4, 20):
        struct.pack_into('<I', output, offset, struct.unpack_from('<I', base, offset)[0] + len(cast))
    count_offset = base.index(b'PRIM') + 24
    assert struct.unpack_from('<I', base, count_offset)[0] == expected_count
    struct.pack_into('<I', output, count_offset, expected_count + 1)
    return bytes(output)


def build_dancer_audio(game, destination):
    """Append the private Rogue clone without changing the Troubadour bank."""
    bank = ROOT / 'audio/blade-dancer-v1'
    selection = json.loads((bank / 'selected-takes.json').read_text(encoding='utf-8'))
    assert len(selection['selections']) == 11
    stock = ET.parse(game / 'SDK/OriginalQuests/Data/M_Sounds.xml').getroot()
    sound = copy.deepcopy(stock.find('.//Description[@ID="RE01"]'))
    sound.attrib.update(ID='BDV1', Name='DancV')  # Same byte length as Rogue.
    paladin = stock.find('.//Description[@ID="PN01"]')
    phases = sound.find('Engine')
    special = phases.find('./Phase[@ID="VFX_SPECIAL1"]')
    phases.insert(list(phases).index(special) + 1,
                  copy.deepcopy(paladin.find('./Engine/Phase[@ID="VFX_CAST_SPELL1"]')))
    stock_cam = read(game / 'Data/sounddesc.cam')
    original = get(stock_cam, b'DSND', b'RE01Rogue')
    private = add_stock_cast_phase(original, get(stock_cam, b'DSND', b'PN01Paladin'))
    assert private.count(b'RE01') == private.count(b'Rogue') == 1
    private = private.replace(b'RE01', b'BDV1').replace(b'Rogue', b'DancV')
    waves = list(read(destination / 'bards_voices.cam')[0].entries)
    seen = set()
    for item in selection['selections']:
        phase = item['phase']
        assert phase not in seen and item['take'] in (1, 2, 3)
        seen.add(phase)
        field = phases.find(f'./Phase[@ID="{phase}"]/Wave')
        assert field is not None, phase
        wave_id = f"DV{item['number']:02d}"
        old = field.get('value').encode()
        assert private.count(old) == 1
        private = private.replace(old, wave_id.encode())
        field.set('value', wave_id)
        waves.append(Entry(name(wave_id.encode()), checked_wave(bank / item['file'], item['sha256'])))
    # No idle-special spoken cue was approved: keep its native slot/group silent.
    silence = get(read(destination / 'bards_voices.cam'), b'WAVE', b'TV00')
    waves.append(Entry(name(b'DV00'), silence))
    field = phases.find('./Phase[@ID="VFX_SPECIAL1"]/Wave')
    assert private.count(field.get('value').encode()) == 1
    private = private.replace(field.get('value').encode(), b'DV00')
    field.set('value', 'DV00')
    assert len(private) == len(original) + 60
    sounds = list(read(destination / 'bards_sounddesc.cam')[0].entries)
    sounds.append(Entry(name(b'BDV1DancV'), private))
    assert len({e.name for e in waves}) == len(waves)
    assert len({e.name for e in sounds}) == len(sounds)
    write(destination / 'bards_voices.cam', (Section(b'WAVE', bytes(4), tuple(waves)),))
    write(destination / 'bards_sounddesc.cam', (Section(b'DSND', bytes(4), tuple(sounds)),))
    root = ET.parse(destination / 'bards_sounds.xml').getroot()
    root.append(sound)
    ET.ElementTree(root).write(destination / 'bards_sounds.xml', encoding='utf-8', xml_declaration=True)


def build_spellsinger_audio(game, destination):
    """Private Cultist sound bank, with Wizard's literal stock cast phase."""
    bank = ROOT / 'audio/spellsinger-v1'
    selection = json.loads((bank/'selected-takes.json').read_text(encoding='utf-8'))
    manifest = json.loads((bank/'manifest.json').read_text(encoding='utf-8'))
    assert len(selection['selections']) == 11
    stock = ET.parse(game/'SDK/OriginalQuests/Data/M_Sounds.xml').getroot()
    sound = copy.deepcopy(stock.find('.//Description[@ID="CT01"]'))
    sound.attrib.update(ID='BSV1', Name='SingerV')  # Same length as Cultist.
    phases = sound.find('Engine')
    special = phases.find('./Phase[@ID="VFX_SPECIAL1"]')
    phases.insert(list(phases).index(special) + 1, copy.deepcopy(
        stock.find('.//Description[@ID="WZ01"]/Engine/Phase[@ID="VFX_CAST_SPELL1"]')))
    native = read(game/'Data/sounddesc.cam')
    original = get(native, b'DSND', b'CT01Cultist')
    private = add_stock_cast_phase(original, get(native, b'DSND', b'WZ01Wizard'), b'WZCL', 14)
    assert private.count(b'CT01') == private.count(b'Cultist') == 1
    private = private.replace(b'CT01', b'BSV1').replace(b'Cultist', b'SingerV')
    waves = list(read(destination/'bards_voices.cam')[0].entries)
    seen = set()
    for item, row in zip(selection['selections'], manifest['clips']):
        assert item['phase'] not in seen
        seen.add(item['phase'])
        assert (item['number'], item['key'], item['phase']) == (row['number'], row['key'], row['phase'])
        assert 1 <= item['take'] <= len(row['takes'])
        take = row['takes'][item['take'] - 1]
        assert item['file'] == take['file'] and item['sha256'] == take['output']['sha256']
        wave_id = f"SV{item['number']:02d}"
        field = phases.find(f'./Phase[@ID="{item["phase"]}"]/Wave')
        assert field is not None, item['phase']
        old = field.get('value').encode()
        assert private.count(old) == 1
        private = private.replace(old, wave_id.encode())
        field.set('value', wave_id)
        waves.append(Entry(name(wave_id.encode()), checked_wave(bank/item['file'], item['sha256'])))
    # No actor rebirth/idle or Jihad cue was approved. Keep the native slots and
    # their groups, but never leak those unrelated Cultist spoken lines.
    waves.append(Entry(name(b'SV00'), get(read(destination/'bards_voices.cam'), b'WAVE', b'TV00')))
    for key in ('VFX_SPECIAL1', 'VFX_JIHAD'):
        field = phases.find(f'./Phase[@ID="{key}"]/Wave')
        assert private.count(field.get('value').encode()) == 1
        private = private.replace(field.get('value').encode(), b'SV00')
        field.set('value', 'SV00')
    assert len(private) == len(original) + 60
    sounds = list(read(destination/'bards_sounddesc.cam')[0].entries)
    sounds.append(Entry(name(b'BSV1SingerV'), private))
    assert len({e.name for e in waves}) == len(waves)
    assert len({e.name for e in sounds}) == len(sounds)
    write(destination/'bards_voices.cam', (Section(b'WAVE', bytes(4), tuple(waves)),))
    write(destination/'bards_sounddesc.cam', (Section(b'DSND', bytes(4), tuple(sounds)),))
    root = ET.parse(destination/'bards_sounds.xml').getroot()
    root.append(sound)
    ET.ElementTree(root).write(destination/'bards_sounds.xml', encoding='utf-8', xml_declaration=True)
