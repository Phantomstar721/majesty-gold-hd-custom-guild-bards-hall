"""Owned AP78 presentation; never adds a spell or changes its lifecycle."""
import struct
import hashlib
import json
from pathlib import Path

from cam_io import Entry, frame_references, get, name, read, section, u32

ROOT = Path(__file__).resolve().parents[1]
# key, native Action/hero ID, passive unlock (zero = native spell), caption, help
SKILLS = (
    ('valor', 'BVA1', 0, 'Ballad of Valor',
     'Inspires nearby allies to strike more accurately, dodge and parry more skillfully, and resist magic.'),
    ('march', 'BMA1', 0, 'Marching Song',
     'Quickens the steps and actions of nearby allies and the Troubadour himself.'),
    ('satire', 'BSA1', 0, 'Cutting Satire',
     'A mocking song weakens an enemy and slows their movement and actions.'),
    ('refrain', 'BRA1', 0, 'Heroic Refrain',
     'Rallies nearby allies, increasing all damage they deal and reducing the damage they take from enemy hits.'),
    ('note', 'BNA1', 0, 'Arcane Note',
     'Hurls a note of magical force at an enemy. Its power grows with the Spellsinger\'s intellect and Instrument upgrades.'),
    ('reverberation', 'BDS1', 3, 'Reverberation',
     'Arcane Note echoes to another nearby enemy. Notes and echoes build Resonance, making further Arcane Notes more damaging.'),
    ('burst', 'BNA2', 0, 'Resonant Burst',
     'A burst of magical sound damages nearby enemies, consuming their Resonance to stun them with a Crescendo.'),
    ('countermelody', 'BCA1', 0, 'Countermelody',
     'Disrupts an enemy\'s spellcasting and makes their weapon attacks less accurate.'),
    ('training', 'BDD1', 1, 'Duelist Training',
     'Expert footwork and bladework help the Blade Dancer dodge missiles and parry melee attacks.'),
    ('riposte', 'BDD1', 3, 'Riposte',
     'Answers a parried melee attack with a swift counterattack.'),
    ('deflect', 'BDD1', 5, 'Deflect',
     'Turns aside incoming missiles and direct magical attacks.'),
    ('flourish', 'BFA1', 0, 'Dueling Flourish',
     'A succession of three hits against one opponent ends with a powerful strike that pierces armor.'),
)
# Finale and Encore reuse their approved Roused/Encore enchantment artwork.
EXTRA_SKILLS = (
    ('finale', 'BDD1', 8, 'Rousing Finale',
     'A Flourish against any monster prepares an inspiring finish. Slaying that opponent rouses nearby allies and grants Encore.'),
    ('encore', 'BDD1', 8, 'Encore',
     'Carries the triumph of a Finale into the next duel. Her next attack against a monster or enemy hero prepares another inspiring finish.'),
)
EFFECTS = (
    ('valor', 'BYV1', 'Ballad of Valor', 'Inspired to strike more accurately, dodge and parry more skillfully, and resist magic.'),
    ('march', 'BME2', 'Marching Song', 'Moves and acts more quickly.'),
    ('satire', 'BSE1', 'Cutting Satire', 'Weakened by a mocking song, moving and acting more slowly.'),
    ('refrain', 'BRE1', 'Heroic Refrain', 'All damage dealt is increased, and enemy hits inflict less damage.'),
    ('reverberation', 'BNE1', 'Resonance', 'Lingering notes make Arcane Note more damaging. Resonant Burst consumes them to stun this enemy.'),
    ('countermelody', 'BCE1', 'Countermelody', 'Spellcasting is disrupted and weapon attacks are less accurate.'),
    # Saved old March effects remain visible until their ordinary expiry.
    ('march-legacy', 'BME1', 'Marching Song', 'A marching song quickens the hero\'s steps and actions.'),
    ('roused', 'BRS1', 'Roused', 'Inspired to fight more bravely, strike harder, and dodge and parry more skillfully.'),
    ('encore', 'BEC1', 'Encore', 'Her next attack against a monster or enemy hero prepares another Rousing Finale. Slaying that opponent inspires nearby allies.'),
)

# Literal stock placeholders until the user approves a stock-based custom pilot.
# Values identify first frames in INTn (skills) or IX93 (enchantments).
STOCK_SKILLS = dict(zip((row[0] for row in SKILLS),
                       (1002, 1004, 1022, 1021, 1001, 1003, 1005, 1010, 1021, 1013, 1002, 1024)))
STOCK_EFFECTS = dict(zip((row[0] for row in EFFECTS), (1002, 1000, 1008, 1006, 1013, 1003, 1000, 1002, 1013)))
STOCK_SKILLS.update(finale=1021, encore=1013)


def approved_masters():
    """Fail closed on missing, changed or unapproved custom assets."""
    root = ROOT / 'art/ability-icons-v2'
    approval = json.loads((root / 'approval.json').read_text())
    if not approval['runtime_custom_art_approved']:
        return {}
    if not approval['bulk_generation_approved'] or not approval.get('approval_record'):
        raise ValueError('Custom AP78 art needs recorded sample/style approval')
    expected = {row[0] for row in SKILLS}
    if set(approval['masters']) != expected:
        raise ValueError('Approved AP78 master set is incomplete')
    result = {}
    for key, evidence in approval['masters'].items():
        master = (root / evidence['file']).resolve(strict=True)
        if not master.is_relative_to(root.resolve()) or hashlib.sha256(master.read_bytes()).hexdigest() != evidence['sha256']:
            raise ValueError('AP78 art is outside its approved family or has changed')
        result[key] = master
    return result


def features():
    rows = []
    for i, (key, subject, level, caption, tooltip) in enumerate(SKILLS + EXTRA_SKILLS, 1):
        rows.append(dict(type='stock.ap78-info-row.v1', feature_key='skill-' + key,
                         kind='passive' if level else 'spell', subject_id=subject,
                         unlock_level=level, display_text=caption, tooltip_text=tooltip,
                         image_id=f'BS{i:02d}', image_set=1019))
    for i, (key, subject, caption, tooltip) in enumerate(EFFECTS, 1):
        rows.append(dict(type='stock.ap78-info-row.v1', feature_key='effect-' + key,
                         kind='enchantment', subject_id=subject, unlock_level=0,
                         display_text=caption, tooltip_text=tooltip,
                         image_id=f'BX{i:02d}', image_set=1019))
    return rows


def approved_enchantment_masters():
    """Approved Encore/Roused art, shared by their passive skill entries."""
    root = ROOT / 'art/encore-roused-icons-v1'
    approval = json.loads((root / 'review-status.json').read_text())
    if not approval['runtime_custom_art_approved']:
        return {}
    if not approval.get('approval_record') or set(approval['masters']) != {'encore', 'roused'}:
        raise ValueError('Encore/Roused enchantment art needs explicit visual approval')
    result = {}
    for key, evidence in approval['masters'].items():
        master = (root / evidence['file']).resolve(strict=True)
        if not master.is_relative_to(root.resolve()) or hashlib.sha256(master.read_bytes()).hexdigest() != evidence['sha256']:
            raise ValueError('Encore/Roused master differs from its approved revision')
        result[key] = master
    return result


def icon_template(stock, key):
    original = get(stock, b'IMAG', key)
    sets = [struct.unpack_from('<II', original, 24+8*i) for i in range(u32(original, 20))]
    index = next(i for i, entry in enumerate(sets) if entry[0] == 1019)
    start = sets[index][1]
    end = sets[index+1][1] if index+1 < len(sets) else len(original)
    return original[:20] + struct.pack('<III', 1, 1019, 32) + original[start:end]


def append_art(game, tiles, art, interface_tile):
    images = []
    masters = approved_masters()
    enchantment_masters = approved_enchantment_masters()
    stock = read(game / 'Data/interfacedata.cam')
    expansion = read(game / 'DataMX/mx_interfacedata.cam')
    for row in features():
        effect = row['kind'] == 'enchantment'
        archive = expansion if effect else stock
        # Resolve the literal resource name from its exact FourCC.
        key, = [e.name.rstrip(b'\0') for e in section(archive, b'IMAG').entries
                if e.name[:4] == (b'IX93' if effect else b'INTn')]
        original = get(archive, b'IMAG', key)
        image = bytearray(icon_template(archive, key))
        offset, = frame_references(image, 1019)
        key = row['feature_key'].split('-', 1)[1]
        stock_set = (STOCK_EFFECTS if effect else STOCK_SKILLS)[key]
        stock_offset, = frame_references(original, stock_set)
        reference = u32(original, stock_offset)
        if reference >> 16: raise ValueError('Stock AP78 icon transform changed')
        template = section(archive, b'TILE').entries[reference].data
        side = 25 if effect else 24
        if struct.unpack_from('<4H', template) != (1, side, side, side):
            raise ValueError('Stock placeholder dimensions changed')
        # The passive skill and its resulting enchantment share their approved
        # artwork. Finale grants Roused; Encore also has a banked effect row.
        master = enchantment_masters.get(key if key != 'finale' else 'roused')
        if master is None:
            master = masters.get(key.removesuffix('-legacy'))
        if master is not None:
            # Use the exact published static-set template for native encoding.
            template_reference = u32(image, offset)
            template = section(archive, b'TILE').entries[template_reference].data
            encoded = interface_tile(art, template, master, (side, side))
        else:
            encoded = template
        struct.pack_into('<I', image, offset, len(tiles))
        tiles.append(Entry(name(row['image_id'].encode()), encoded))
        images.append(Entry(name(row['image_id'].encode()), bytes(image)))
    return images


def validate(game, package, art, interface_tile):
    actual = read(package / 'Data/bards_interfacedata.cam')
    tiles = list(section(actual, b'TILE').entries)
    start = next(i for i, row in enumerate(tiles) if row.name[:4] == b'BS01')
    expected_tiles = tiles[:start]
    expected_images = append_art(game, expected_tiles, art, interface_tile)
    if expected_tiles != tiles: raise ValueError('Private AP78 TILE art changed')
    for image in expected_images:
        if get(actual, b'IMAG', image.name.rstrip(b'\0')) != image.data:
            raise ValueError('Private AP78 IMAG differs from its literal stock template')
