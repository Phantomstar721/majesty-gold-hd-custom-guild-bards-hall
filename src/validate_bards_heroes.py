"""Audit private bard decisions against their complete stock decision chains."""
import re
import struct
import xml.etree.ElementTree as ET

from bards_heroes import PROFILES, support_hero_prototype


def clean(source):
    return re.sub(r'//[^\n]*', '', source)


def check_heroes(sdk, package, extract_function, stock_equal, require):
    source = sdk / 'GPLMx'
    gpl = package / 'GPL'
    trees = (gpl / 'Bards_Hero_Trees.gpl').read_text()
    evaluations = (gpl / 'Bards_Hero_Evaluation.gpl').read_text()
    data = (gpl / 'Bards_Hero_Data.dat').read_text()
    units = ET.parse(package / 'Data/bards_units.xml').getroot()
    stock_units = ET.parse(sdk / 'Data/M_Characters.xml').getroot()
    prototype = (gpl / 'Bards_Support_Hero_Prototype.gpl').read_text()
    stock_equal(prototype, support_hero_prototype(sdk), 'append-only typed support Hero prototype')
    hunt = (gpl / 'Bards_Hunt_Stock.gpl').read_text()
    stock_hunt = (source / 'DecisionTrees/Modules/mx_Combat_wandering.gpl').read_text(encoding='cp1252')
    for symbol in ('combat_wandering', 'combat_wandering_heroes'):
        block = extract_function(hunt, 'Bards_' + symbol)
        block = block.replace('Bards_' + symbol, symbol)
        candidate = 'monster' if symbol == 'combat_wandering' else 'hero'
        block = block.replace('\n\tinteger current_best_distance;', '')
        block = block.replace('\n\tcurrent_best_distance = 100000;', '')
        block = block.replace('#NotMyTeam, #CheckSubtypes, "Hero"', '#NotMyTeam')
        block = re.sub(r'if \(temp_score > 0\)\s*if \(\$distanceBetweenAgents\(thisagent,' + candidate +
                       r'\) < current_best_distance\)', 'if (temp_score > current_best_score)', block)
        block = re.sub(r'\s*current_best_distance = \$distanceBetweenAgents\(thisagent,' + candidate + r'\);', '', block)
        stock_equal(block, extract_function(stock_hunt, symbol),
                    'Bard hunting preserves stock lifecycle outside approved nearest/filter substitutions: ' + symbol)
    require('#CheckSubtypes, "Hero"' in extract_function(hunt, 'Bards_combat_wandering_heroes'),
            'Bard ordinary hero hunts must exclude civilians')
    require(hunt.count('if (temp_score > 0)') == 3 and hunt.count('< current_best_distance)') == 3,
            'Bard hunts must choose nearest viable candidates in both champion and ordinary passes')
    binary_path = package / 'Data/Bards.bcd'
    if binary_path.exists():
        declarations = re.findall(r'(?im)^\s*(string|integer|float|function|boolean|list|agent|coordinate)\s+(\w+)\s*;', clean(prototype), re.I)
        kinds = {'integer': 1, 'float': 2, 'string': 3, 'list': 4, 'agent': 5, 'boolean': 6, 'coordinate': 7, 'function': 8}
        layout = b''.join(struct.pack('<5I', 20, 1, kinds[k.lower()], 0, 0xffffffff) for k, _ in declarations)
        record = (b'Bards_Support_Hero\0' + struct.pack('<5I', 20 + len(layout) + 12, 1, 11, 0, len(declarations))
                  + layout + struct.pack('<3I', 0, 0, 0xffffffff))
        require(binary_path.read_bytes().count(record) == 1, 'Compiled support callback fields lack their native function types')
    exclusions = {
        'Healer': ('Heal_Others', 'Follow_Heal_Check', 'Seed_Resource_Check'),
        'Cultist': ('Build_Pack', 'Swarm', 'Patrol', 'Steal_Check', 'Seed_Resource_Check'),
        'Ranger': ('defend_building', 'Collect_resource', 'follow_support_check', 'Journey_Offmap_Check'),
    }
    for title, base in (('Troubadour', 'Healer'), ('Spellsinger', 'Cultist'), ('Blade_Dancer', 'Ranger')):
        expected = clean(extract_function((source / f'DecisionTrees/mx_{base}.gpl').read_text(encoding='cp1252'), base + '_tree'))
        expected = re.sub(r'(?im)^\s*if\s*\(\$(?:' + '|'.join(exclusions[base]) + r')\s*\([^\n]*\n', '\n', expected)
        expected = re.sub(r'\bif\s+\(', 'if (', expected)
        actual = extract_function(trees, 'Bards_' + title + '_Tree')
        actual = re.sub(r'(?i)function\s+Bards_' + title + '_Tree', 'function ' + base + '_tree', actual, count=1)
        actual = actual.replace('if ($Bards_Hire_Guard(ThisAgent)) return;', '')
        actual = actual.replace('$Bards_combat_wandering(', '$Combat_wandering(').replace('$Bards_combat_wandering_heroes(', '$combat_wandering_heroes(')
        if title == 'Troubadour':
            renown = 'if ($Bards_Renown_Return(ThisAgent)) return;'
            require(actual.count(renown) == 1 and actual.index(renown) < actual.index('$Bards_Follow_Check'),
                    'Approved Renown return must precede new follow selection')
            actual = actual.replace(renown, '')
            actual = actual.replace('if ($Bards_Follow_Check(ThisAgent, "Spellsinger", 60) == FALSE)', '')
            actual = actual.replace('if ($Bards_Follow_Check(ThisAgent, "Hero", 100) == FALSE)', '')
            expected = expected.replace('"Inn", 20', '"Inn", 10').replace('"Royal_gardens", 50', '"Royal_gardens", 20').replace('Go_home(thisagent,90)', 'Go_home(thisagent,30)')
        if title == 'Spellsinger':
            actual = actual.replace('$Bards_Spellsinger_Wander', '$hero_wander')
            actual = actual.replace('$Bards_Street_Service(ThisAgent);', '')
            actual = actual.replace('if ($Bards_Street_Check(ThisAgent) == FALSE)', '')
            expected = expected.replace('Combat_wandering(thisagent,85)', 'Combat_wandering(thisagent,50)').replace('combat_wandering_heroes(thisagent,85)', 'combat_wandering_heroes(thisagent,50)').replace('"Royal_gardens", 50', '"Royal_gardens", 20').replace('Go_home(thisagent,30)', 'Go_home(thisagent,15)')
            for call in ('pursue_entertainment(thisagent)', 'Go_home(thisagent,15)'):
                line = 'if ($' + call + ' == False)'
                expected = expected.replace(line, '')
                expected = expected.replace('if ($raid_enemy_building(thisagent,20) == False)', 'if ($raid_enemy_building(thisagent,20) == False)\n' + line) if call.startswith('pursue') else expected.replace('if ($pursue_entertainment(thisagent) == False)', 'if ($pursue_entertainment(thisagent) == False)\n' + line)
            expected = expected.replace('if ($Raid_lair(thisagent,20) == False)', 'if ($Raid_lair(thisagent,20) == False)\nif ($explore_map(thisagent,80) == False)')
        if title == 'Blade_Dancer':
            actual = actual.replace('function Ranger_tree', 'function ranger_tree')
            actual = actual.replace('$Bards_Dancer_Wander', '$hero_wander')
            prize = 'if ($Bards_Prize_Duel_Check(thisagent,25) == FALSE)'
            require(actual.count(prize) == 1 and
                    actual.index('$Hall_Champs_Check') < actual.index(prize) < actual.index('$Combat_wandering'),
                    'Approved local Prize Duel choice must follow champion calls and precede ordinary hunts')
            actual = actual.replace(prize, '')
            hunt = 'if ($Combat_wandering(thisagent,75) == False)'
            heroes = 'if ($combat_wandering_heroes(thisagent,55) == False)'
            require(expected.count(hunt) == 1 and expected.count(heroes) == 1, 'Stock Ranger hunt anchors changed')
            expected = expected.replace(hunt, '').replace(heroes, '')
            expected = expected.replace('if ($explore_map(thisagent,95) == false)',
                hunt.replace(',75)', ',95)') + '\n' + heroes + '\nif ($explore_map(thisagent,95) == false)')
        stock_equal(actual, expected, title + ' decision order, arguments and fallback')

        block = re.search(r'(?ims)^\[' + title + r'\].*?^\[end\]', data).group()
        fields = dict(re.findall(r'^\s*\((\w+)\s+([^\s()]+)\)\s*$', block, re.M))
        require(fields == PROFILES[title]['gpl_attributes'], title + ' GPL profile differs from explicit authority')
        for key in ('activeScript', 'basicscript', 'StartingScript'):
            require(fields[key] == 'Bards_' + title + '_Tree', title + ' can return to a source-class tree')
        require(fields['evaluationScript'] == 'Bards_' + title + '_Evaluate', title + ' retains a source-class evaluator')
        require(fields['Poison_Weapon_Chance'] == '0', title + ' retains unapproved weapon-poison purchasing')
        require(not set(fields) & {'Num_Followers', 'Max_Followers', 'Immune_to_poison', 'Reborn_Counter'},
                title + ' retains source-class capability data')
        hero = units.find(f'./Description[@Name="{title}"]/Game')
        reference = 'Ranger' if title == 'Troubadour' else 'Rogue'
        movement = units.find(f'./Description[@Name="{title}"]/Engine/Attachment[@kind="Movement"]')
        stock_movement = stock_units.find(f'./Description[@Name="{reference}"]/Engine/Attachment[@kind="Movement"]')
        require(movement.attrib == stock_movement.attrib, title + ' movement differs from ' + reference)
        for key, value in PROFILES[title]['native_attributes'].items():
            require(hero.find(key).get('value') == value, title + ' native profile differs: ' + key)
        armor = hero.find('AllowedArmor')
        require((None if armor is None else armor.get('value')) == PROFILES[title]['armor'],
                title + ' armor identity differs from its explicit profile')

    forbidden = r'\$(?:Seed_Resource_Check|Seed_Resource|Collect_Resource|Loot_Gravestones|Steal_Check|Go_Steal|Build_Pack|Swarm|Patrol|Heal_Others|Follow_Heal_Check|Eval_For_Healing|Healer_Eval_Nearby|cultist_eval_nearby)\b'
    wander = (gpl / 'Bards_Wander_Stock.gpl').read_text()
    wander = wander.replace('Bards_Spellsinger_Wander', 'hero_wander').replace('"counter" < 2', '"counter" < #wander_limit')
    stock_equal(wander, extract_function((source / 'TaskModules/Characters/mx_hero_wander.gpl').read_text(encoding='cp1252'), 'hero_wander'),
                'Spellsinger stock wandering completion with a shorter fallback')
    dancer_wander = (gpl / 'Bards_Dancer_Wander_Stock.gpl').read_text().replace('Bards_Dancer_Wander', 'Bards_Spellsinger_Wander')
    require(dancer_wander == (gpl / 'Bards_Wander_Stock.gpl').read_text(), 'Dancer two-step fallback differs from audited stock clone')
    support = (gpl / 'Bards_Support_Stock.gpl').read_text()
    require(not re.search(forbidden, clean(trees + evaluations + support), re.I), 'Bard decisions reference a source-class special activity')
    require(not re.search(r'"(?:healer_heal|turn_undead_healer|charm_monster|poison_plants)"', clean(trees + evaluations), re.I),
            'Bard evaluation references an unapproved class spell/resource')
    stock_eval = (source / 'DecisionTrees/Modules/mx_target_eval.gpl').read_text(encoding='cp1252')
    ordinary = extract_function(stock_eval, 'eval_enemies_nearby')
    for title in ('Spellsinger', 'Blade_Dancer'):
        actual = extract_function(evaluations, 'Bards_' + title + '_Evaluate').replace('Bards_' + title + '_Evaluate', 'eval_enemies_nearby')
        stock_equal(actual, ordinary, title + ' stock combat evaluation')
    healer = clean(extract_function(stock_eval, 'Healer_Eval_Nearby'))
    expected = 'function Bards_Troubadour_Evaluate (agent ThisAgent) is Boolean declare begin ' + healer[healer.index('If ($listsize'):]
    stock_equal(extract_function(evaluations, 'Bards_Troubadour_Evaluate'), expected,
                'Troubadour stock noncombatant flee/clear/return tail')
    dancer = units.find('./Description[@Name="Blade_Dancer"]/Game')
    require(dancer.find('AllowedWeapon').get('value') == 'Longsword' and dancer.find('RangedAttack') is None
            and int(dancer.find('Attack').get('value')) > 0, 'Dancer must be an equipped melee combatant')
    require(PROFILES['Spellsinger']['gpl_attributes']['PrimaryStat'] == 'ATTRIB_Intelligence',
            'Spellsinger must grow as a spellcaster')
