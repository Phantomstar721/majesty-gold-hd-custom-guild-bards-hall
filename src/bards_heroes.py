"""Package-owned hero attributes; stock hero classes supply no gameplay defaults.

The XML/GPL schema, native Hero class, and generic birth/task lifecycle remain
stock. Values are explicit so future kit balancing cannot inherit class skills.
"""
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET

PROFILES = json.loads((Path(__file__).with_name('hero_profiles.json')).read_text())['heroes']


def bard_hunting(sdk, extract_function):
    """Stock hunt dispatch with nearest viable selection and true-hero filtering.

    The stock target_eval remains the suitability gate. pick_closest supplies
    the distance comparison; champion calls retain their separate first pass.
    Queries remain mapwide. No ongoing private hunt state is introduced.
    """
    source = (sdk / 'GPLMx/DecisionTrees/Modules/mx_Combat_wandering.gpl').read_text(encoding='cp1252')
    blocks = []
    for name in ('combat_wandering', 'combat_wandering_heroes'):
        block = extract_function(source, name)
        block = re.sub(r'(?i)\b' + name + r'\b', 'Bards_' + name, block)
        query = ('\t$ListObjects(thisagent,"monster",-1, wandering_monsters,#NotMyTeam);'
                 if name == 'combat_wandering' else
                 '\t$ListObjects(thisagent,"hero",-1,wandering_heroes,#NotMyTeam);')
        if block.count(query) != 1:
            raise ValueError('Stock hunt query changed')
        if name == 'combat_wandering_heroes':
            block = block.replace(query, query.replace('#NotMyTeam);', '#NotMyTeam, #CheckSubtypes, "Hero");'))
        declaration = '\tinteger current_best_score;'
        if block.count(declaration) != 1:
            raise ValueError('Stock hunt declaration changed')
        block = block.replace(declaration, declaration + '\n\tinteger current_best_distance;')
        block = block.replace('current_best_score = 0;', 'current_best_score = 0;\n\tcurrent_best_distance = 100000;')
        candidate = 'monster' if name == 'combat_wandering' else 'hero'
        selection = 'if (temp_score > current_best_score)'
        expected = 2 if name == 'combat_wandering' else 1
        if block.count(selection) != expected:
            raise ValueError('Stock hunt selection changed')
        block = block.replace(selection,
            'if (temp_score > 0)\n' +
            '\t\t\t\t\tif ($distanceBetweenAgents(thisagent,' + candidate + ') < current_best_distance)')
        assignment = 'current_best_score = temp_score;'
        block = block.replace(assignment, assignment +
            '\n\t\t\t\t\t\t\tcurrent_best_distance = $distanceBetweenAgents(thisagent,' + candidate + ');')
        blocks.append(block)
    return '\n'.join(blocks)


def spellsinger_wander(sdk, extract_function):
    """Literal stock fallback, with two steps before reconsidering available work."""
    path = sdk / 'GPLMx/TaskModules/Characters/mx_hero_wander.gpl'
    source = extract_function(path.read_text(encoding='cp1252'), 'hero_wander')
    source = re.sub(r'(?i)\bhero_wander\b', 'Bards_Spellsinger_Wander', source)
    if source.count('#wander_limit') != 1:
        raise ValueError('Stock wander loop changed')
    return source.replace('#wander_limit', '2')


def dancer_wander(sdk, extract_function):
    """Same stock two-step fallback as Singer, with private Dancer identity."""
    return spellsinger_wander(sdk, extract_function).replace('Bards_Spellsinger_Wander', 'Bards_Dancer_Wander')


def describe_hero(hero, title, hero_id):
    profile = PROFILES[title]
    game = hero.find('Game')
    game.clear()
    game.set('version', '1')
    ET.SubElement(game, 'DialogID', value='AP20')
    for key, value in profile['native_attributes'].items():
        ET.SubElement(game, key, value=str(value))
    ET.SubElement(game, 'AttackRange', **profile['attack_range'])
    # These are ordinary flags shared by stock Warrior/Ranger/Wizard/etc.
    # 'Heals' is passive recovery eligibility, not the Healer spell ability.
    for flag in ('Heals', 'HasHPBar', 'CanHighlight'):
        ET.SubElement(game, 'Flags', value=flag)
    ET.SubElement(game, 'HelpID', value='hBD' + hero_id[2])
    ET.SubElement(game, 'AllowedWeapon', value=profile['weapon'])
    if profile['armor']:
        ET.SubElement(game, 'AllowedArmor', value=profile['armor'])
    if profile['spells']:
        spells = ET.SubElement(game, 'AllowedSpells')
        for index, spell in enumerate(profile['spells']):
            ET.SubElement(spells, 'Spell', ID=str(index), Value=spell)


def hero_data():
    result = []
    for title, profile in PROFILES.items():
        values = '\n'.join(f'\t\t({key} {value})' for key, value in profile['gpl_attributes'].items())
        prototype = 'Bards_Support_Hero'
        result.append(f'[{title}]\n\t{{{prototype}\n{values}\n\t}}\n[end]\n')
    return '\n'.join(result)


def support_hero_prototype(sdk):
    """Stock Hero layout, typed Guild callbacks, and optional AI-mod fields."""
    source = (sdk / 'GPLMx/mx_prototype.gpl').read_text(encoding='cp1252')
    block, = re.findall(r'(?ims)^prototype hero \(\).*?^end\b', source)
    block = block.replace('prototype hero ()', 'prototype Bards_Support_Hero ()')
    # Misc Enhancements AI_Combat.attackLogic reads both fields for every
    # combatant, including melee berserk_defend. Its extended Hero prototype
    # cannot extend this independent private class. Preserve its exact types;
    # no kiting implementation is supplied or dispatched by this package.
    return block.replace('\nbegin\n', '\n\tfunction HeroSupportEligible;\n\tfunction HeroSupportTick;\n\tfunction HeroCapability;\n\tboolean Should_Kite;\n\tinteger KitingTime;\n\nbegin\n') + '\n'
