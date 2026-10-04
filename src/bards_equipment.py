"""Mod-owned equipment resources for Manager's stock.equipment.v1 trial.

Only names, private identities and icon frame references are substituted.
Stock owns construction, shopping, attributes, presentation and cleanup.
"""
import json
from pathlib import Path
import struct

from bards_heroes import PROFILES
from cam_io import Entry, frame_references, get, name, read, section, u32

ROOT = Path(__file__).resolve().parents[1]
BINDINGS = {
    'troubadour-instrument': ('BEN1', 'BEI1'),
    'spellsinger-instrument': ('BEN2', 'BEI2'),
    'blade-dancer-dual-wield': ('BEN3', 'BEI3'),
}
HERO_TITLES = {'BDT1': 'Troubadour', 'BDS1': 'Spellsinger', 'BDD1': 'Blade_Dancer'}


def content():
    value = json.loads((ROOT / 'src/equipment_content.json').read_text())
    sets = {item['key']: item for item in value['sets']}
    if len(sets) != len(value['sets']) or set(sets) != set(BINDINGS):
        raise ValueError('Equipment identities differ from the authored binding table')
    for item in sets.values():
        multiplier = 1 if item['kind'] == 'weapon' else 3
        if ([tier['rank'] for tier in item['quality']] != [0, 1, 2, 3] or
                [tier['structural_bonus'] for tier in item['quality']] != [0, 1, 2, 3] or
                [tier['purchase_price'] for tier in item['quality']] != [0, 100*multiplier, 200*multiplier, 300*multiplier] or
                [tier['magic_bonus'] for tier in item['enchantment']] != [0, 1, 2, 3] or
                [tier['purchase_price'] for tier in item['enchantment']] != [0, 200, 400, 800]):
            raise ValueError('stock.equipment.v1 cannot supply custom tier values or prices')
    for assignment in value['hero_assignments']:
        hero = PROFILES[HERO_TITLES[assignment['hero_id']]]
        if assignment['quality_rank'] != 0 or assignment['magic_rank'] != 0:
            raise ValueError('This build preserves stock zero-rank birth')
        for slot in ('weapon', 'armor'):
            key = assignment[slot]
            stock_key = assignment.get('stock_' + slot)
            if key is None:
                if hero[slot] != stock_key:
                    raise ValueError('Stock equipment assignment disagrees with the hero profile')
                continue
            if stock_key is not None:
                raise ValueError('A slot cannot declare both private and stock equipment')
            item = sets[key]
            field = slot.title() + 'BasicDamage'
            if (item['kind'] != slot or item['base_stat']['attribute'] != field or
                    int(hero['native_attributes'][field]) != item['base_stat']['value'] or
                    hero[slot] != item['stock_reference']):
                raise ValueError(f'{key}: equipment and source hero base values disagree')
    return value


def features():
    value = content()
    return [dict(type='stock.equipment.v1', feature_key=item['key'], slot=item['kind'],
                 name_table=BINDINGS[item['key']][0], image_id=BINDINGS[item['key']][1],
                 image_set=1004 if item['kind'] == 'weapon' else 1000,
                 hero_ids=[hero['hero_id'] for hero in value['hero_assignments']
                           if hero[item['kind']] == item['key']])
            for item in value['sets']]


def stock_icon_image(stock, slot):
    key, set_id = (b'INBwicons weapons', 1004) if slot == 'weapon' else (b'INBaarmor icons', 1000)
    original = get(stock, b'IMAG', key)
    sets = [struct.unpack_from('<II', original, 24+8*i) for i in range(u32(original, 20))]
    index = next(i for i, entry in enumerate(sets) if entry[0] == set_id)
    start = sets[index][1]
    end = sets[index+1][1] if index+1 < len(sets) else len(original)
    # Copy the stock header and literal selected set; update only directory size/offset.
    return original[:20] + struct.pack('<III', 1, set_id, 32) + original[start:end]


def append_art(stock, tiles, art, interface_tile):
    images = []
    stock_tiles = next(section.entries for section in stock if section.extension == b'TILE')
    for item in content()['sets']:
        image = bytearray(stock_icon_image(stock, item['kind']))
        set_id = 1004 if item['kind'] == 'weapon' else 1000
        offsets = frame_references(image, set_id)
        if len(offsets) != 4:
            raise ValueError('Stock equipment icon frame count changed')
        for offset, tier in zip(offsets, item['quality']):
            original = u32(image, offset)
            if original >> 16:
                raise ValueError('Stock equipment reference flags changed')
            source = (ROOT / tier['master']).resolve(strict=True)
            if not source.is_relative_to((ROOT / 'art/equipment-v2/source').resolve(strict=True)):
                raise ValueError('Equipment master outside its owned art directory')
            encoded = interface_tile(art, stock_tiles[original].data, source, (23, 23))
            struct.pack_into('<I', image, offset, len(tiles))
            tiles.append(Entry(name((BINDINGS[item['key']][1] + str(tier['rank'])).encode()), encoded))
        images.append(Entry(name(BINDINGS[item['key']][1].encode()), bytes(image)))
    return images


def name_tables(stock_text):
    stock_header = get(stock_text, b'STRT', b'EN01')[:4]
    tables = []
    for item in content()['sets']:
        rows = []
        for tier in item['quality']:
            text = tier['name'].encode('cp1252')
            if not text or len(text) > 128 or b'\0' in text:
                raise ValueError('Equipment name does not fit the stock name contract')
            rows.append(struct.pack('<I', tier['rank']) + text + b'\0')
        header = bytearray(struct.pack('<H', len(rows)) + stock_header[2:4])
        cursor = 4 + 4*len(rows)
        for row in rows:
            header.extend(struct.pack('<I', cursor))
            cursor += len(row)
        tables.append(Entry(name(BINDINGS[item['key']][0].encode()), bytes(header) + b''.join(rows)))
    return tables


def validate(game, package, art):
    stock = read(game / 'Data/interfacedata.cam')
    actual = read(package / 'Data/bards_interfacedata.cam')
    tiles = section(actual, b'TILE').entries
    baseline = section(stock, b'TILE').entries
    equipment_tile_count = sum(len(item['quality']) for item in content()['sets'])
    from bards_ability_ui import features as ability_ui_features
    if (len(tiles) != len(baseline) + 1 + equipment_tile_count + len(ability_ui_features()) or
            [(row.name, row.data) for row in tiles[:len(baseline)]] != [(row.name, b'') for row in baseline]):
        raise ValueError('Equipment packaging changed base interface TILE positions')
    text = read(package / 'Data/bards_gpltext.cam')
    definition = json.loads((package / 'mod-definition.json').read_text())
    declarations = [item for item in definition['runtime_features'] if item['type'] == 'stock.equipment.v1']
    if declarations != features():
        raise ValueError('Equipment registration differs from owned assignments')
    for table in name_tables(read(game / 'Data/gpltext.cam')):
        if get(text, b'STRT', table.name.rstrip(b'\0')) != table.data:
            raise ValueError('Packaged equipment names differ from authored quality names')
    for item, feature in zip(content()['sets'], declarations):
        original = stock_icon_image(stock, item['kind'])
        private = bytearray(get(actual, b'IMAG', feature['image_id'].encode()))
        offsets = frame_references(private, feature['image_set'])
        for offset, tier in zip(offsets, item['quality']):
            tile = tiles[u32(private, offset)]
            if (tile.name.rstrip(b'\0') != (feature['image_id'] + str(tier['rank'])).encode() or
                    len(tile.data) != 1587 or art.decode_tile_v1(tile.data).size != (23, 23)):
                raise ValueError('Equipment frame does not resolve to its authored native icon')
            prepared = ROOT / 'artifacts/equipment-content-v2/tiles' / (Path(tier['icon']).stem + '.tile')
            # This separate authoring build preserves each icon's original master.
            # The native package must match those reviewed bytes when available.
            if prepared.exists() and tile.data != prepared.read_bytes():
                raise ValueError('Packaged equipment icon differs from the reviewed native encoding')
            struct.pack_into('<I', private, offset, u32(original, offset))
        if bytes(private) != original:
            raise ValueError('Equipment image changed stock topology beyond TILE references')
