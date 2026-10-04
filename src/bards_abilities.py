"""Private ability definitions and stock-owned action/effect lifecycles.

Native timing and the shared activity service retain stock scheduling ownership.
"""
from __future__ import annotations

import copy
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def description(root, title):
    element = root.find(f'.//Description[@Name="{title}"]')
    if element is None:
        raise ValueError(f"Missing stock ability description: {title}")
    return copy.deepcopy(element)


def value(root, path, text):
    item = root.find(path)
    if item is None:
        parent, field = path.rsplit("/", 1)
        item = ET.SubElement(root.find(parent), field)
    item.set("value", str(text))


def build_descriptions(sdk: Path) -> ET.Element:
    actions = ET.parse(sdk / "Data/M_Actions.xml").getroot()
    projectiles = ET.parse(sdk / "Data/M_Projectiles.xml").getroot()
    overlays = ET.parse(sdk / "Data/M_Overlays.xml").getroot()
    output = ET.Element("Majesty")

    # Stock weapon action owns physical hit resolution; only its presentation
    # changes when the existing same-opponent hit chain has reached two hits.
    flourish_action = description(actions, 'basic_attack')
    flourish_action.attrib.update(ID='BFA1', Name='Bards_Flourish_Strike', Description='Dueling Flourish')
    value(flourish_action, './Engine/ImageSet', 'Cast')
    flourish_action.find('./Engine/Script').set('GPLFunction', 'Bards_Flourish_Attack')
    ET.SubElement(flourish_action, 'Game', version='1')
    for field, text in (('Flags','IsSpell'), ('SpellType','Attack'), ('CharacterLevel',8),
                        ('SpellRank',10), ('TimeoutDuration',0), ('ValidationScript','Bards_Flourish_Check')):
        value(flourish_action, './Game/' + field, text)
    output.append(flourish_action)

    finale_action = description(actions, 'healer_heal')
    finale_action.attrib.update(ID='BFA2', Name='Bards_Finale_Cast', Description='Rousing Finale')
    finale_action.find('./Engine/Script').set('GPLFunction', 'Bards_Finale_Complete')
    for item in list(finale_action.find('Game')): finale_action.find('Game').remove(item)
    output.append(finale_action)

    chronicles = description(overlays, 'super_charge_effector')
    chronicles.attrib.update(ID='BCR1', Name='Bards_Chronicles_Active', Description='Epic Chronicles')
    value(chronicles, './Engine/ImageIDBase', 'BCRS')
    value(chronicles, './Engine/DefaultSound', '0')
    output.append(chronicles)

    note = description(actions, "energy_blast")
    note.attrib.update(ID="BNA1", Name="Bards_Arcane_Note", Description="Arcane Note")
    value(note, "./Engine/Projectile", "Bards_Arcane_Note_Missile")
    output.append(note)
    missile = description(projectiles, "energy_blast_missile")
    missile.attrib.update(ID="BNP1", Name="Bards_Arcane_Note_Missile", Description="Arcane Note")
    missile.find("./Engine/Script").set("GPLFunction", "Bards_Arcane_Note_Hit")
    output.append(missile)

    burst = description(actions, "sun_scorch")
    burst.attrib.update(ID="BNA2", Name="Bards_Resonant_Burst", Description="Resonant Burst")
    value(burst, "./Engine/Sound", "Energy_Blast")
    burst.find("./Engine/Script").set("GPLFunction", "Bards_Resonant_Burst_Hit")
    value(burst, "./Game/TimeoutDuration", 12000)
    value(burst, "./Game/CharacterLevel", 8)
    value(burst, "./Game/SpellRank", 3)
    value(burst, "./Game/ValidationScript", "Bards_Resonant_Burst_Check")
    output.append(burst)

    counter = description(actions, 'sun_scorch')
    counter.attrib.update(ID='BCA1', Name='Bards_Countermelody', Description='Countermelody')
    counter.find('./Engine/Script').set('GPLFunction', 'Bards_Countermelody_Hit')
    value(counter, './Engine/Sound', 'Energy_Blast')
    for field, number in (('CharacterLevel', 5), ('SpellRank', 4), ('TimeoutDuration', 45000), ('EffectorDuration', 8000)):
        value(counter, './Game/' + field, number)
    value(counter, './Game/ValidationScript', 'Bards_Countermelody_Check')
    output.append(counter)

    # Presentation-only gestures keep the stock action -> Stand lifecycle.
    # In particular, Attack is an image set, never the basic_attack callback.
    for ident, name, images in (('BPA1', 'Bards_Street_Play', 'Special'),
                                ('BPA2', 'Bards_Street_Attack', 'Attack'),
                                ('BPA3', 'Bards_Street_Cast', 'Cast')):
        performance = description(actions, 'healer_heal')
        performance.attrib.update(ID=ident, Name=name, Description='Street Spectacle')
        value(performance, './Engine/ImageSet', images)
        performance.find('./Engine/Script').set('GPLFunction', 'Bards_Street_Phrase')
        for item in list(performance.find('Game')):
            performance.find('Game').remove(item)
        output.append(performance)

    for private_id, private_name, display, level, duration, cooldown in (
        ('BVA1', 'Bards_Valor', 'Ballad of Valor', 1, 8000, 6000),
        ('BMA1', 'Bards_March', 'Marching Song', 3, 8000, 6000),
        ('BSA1', 'Bards_Satire', 'Cutting Satire', 5, 6000, 8000),
        ('BRA1', 'Bards_Refrain', 'Heroic Refrain', 8, 10000, 30000),
    ):
        song = description(actions, 'healer_heal')
        song.attrib.update(ID=private_id, Name=private_name, Description=display)
        song.find('./Engine/Script').set('GPLFunction', private_name + '_Complete')
        for spell_type in list(song.findall('./Game/SpellType')):
            song.find('./Game').remove(spell_type)
        # Deliberately no Attack category: stock weapon-combat selection cannot
        # start a friendly song. The Healer-derived support task owns dispatch.
        value(song, './Game/CharacterLevel', level)
        value(song, './Game/EffectorDuration', duration)
        value(song, './Game/TimeoutDuration', cooldown)
        output.append(song)

    # Exact duration-owned stock icon/callback shapes. Art stays stock for now.
    # The private apply/end functions preserve native refresh and expiry.
    for original, private_id, private_name, display in (
        ("blessing_icon", "BYV1", "Bards_Valor_Icon", "Ballad of Valor"),
        ("winged_feet_icon", "BME2", "Bards_March_Icon", "Marching Song"),
        ("wither_icon", "BSE1", "Bards_Satire_Icon", "Cutting Satire"),
        ("Rage_icon", "BRE1", "Bards_Refrain_Icon", "Heroic Refrain"),
        ("wither_icon", "BNE1", "Bards_Reverberation_Icon", "Resonance"),
        ("blessing_icon", "BEC1", "Bards_Encore_Icon", "Encore"),
        ("blessing_icon", "BFT1", "Bards_Finale_Ready_Icon", "Finale Ready"),
        ("blessing_icon", "BRS1", "Bards_Roused_Icon", "Roused"),
        ("blessing_icon", "BCE1", "Bards_Countermelody_Icon", "Countermelody"),
    ):
        icon = description(overlays, original)
        icon.attrib.update(ID=private_id, Name=private_name, Description=display)
        icon.find("./Engine/Script").set("GPLFunction", private_name.replace("_Icon", "_End"))
        output.append(icon)
    # Old saves retain BME1 and its exact stored-delta expiry callback. Let that
    # effect finish before any BME2 scale is applied; never stack both versions.
    legacy_march = description(overlays, 'winged_feet_icon')
    legacy_march.attrib.update(ID='BME1', Name='Bards_March_Legacy_Icon', Description='Marching Song')
    legacy_march.find('./Engine/Script').set('GPLFunction', 'Bards_March_End')
    output.append(legacy_march)
    from bards_world_effects import bind_descriptions
    bind_descriptions(output, overlays)
    return output


def clone_arcane_note(sdk: Path, extract_function) -> str:
    stock = (sdk / "GPLMx/TaskModules/Subtasks/mx_Spells.gpl").read_text(encoding="cp1252")
    function = extract_function(stock, "Energy_Blast_Hit")
    function = function.replace("Energy_Blast_Hit", "Bards_Arcane_Note_Hit")
    # Private ordinary-hit resolution preserves the stock roll/XP and adds the
    # approved level-three, non-recursive proc only after positive damage.
    function = re.sub(r'(?i)(GetSpellAttribute\(\s*)"energy_blast"', r'\1"Bards_Arcane_Note"', function)
    function = replace_once(function, '$spell_attack( thisagent, target, 10 );', '$Bards_Arcane_Attack( thisagent, target, 10 );')
    function = function.replace("energy_blast_effector", "Bards_Echo_Flash")
    function = intercept_spell(function)
    return function


def replace_once(source: str, anchor: str, replacement: str) -> str:
    if source.count(anchor) != 1:
        raise ValueError(f"Stock ability anchor changed: {anchor!r}")
    return source.replace(anchor, replacement, 1)


def intercept_spell(function: str, target_only: bool = False) -> str:
    guard = ('if ($Bards_Deflect_Player(ThisAgent)) return;' if target_only else
             'if ($Bards_Deflect_Spell(ThisAgent, Target)) return;')
    return re.sub(r'(?im)^begin\s*$', lambda m: m[0] + '\n\t' + guard + '\n', function, count=1)


def deflect_functions(sdk: Path, extract_function) -> str:
    """Intercept audited impact callbacks; keep shared AOE/DOT resolvers stock."""
    root = sdk / 'GPLMx/TaskModules'
    stock = (root / 'Subtasks/mx_Make_Attack.gpl').read_text(encoding='cp1252')
    spells = (root / 'Subtasks/mx_Spells.gpl').read_text(encoding='cp1252')
    accuracy = '\t\t\tif ($randomnumber(100) > defenderavoid)'
    physical = extract_function(stock, 'hit')
    physical = replace_once(physical, accuracy,
        '\t\t\tif ($Bards_Deflect_Physical(attacker, defender)) return 4;\n' + accuracy)
    spell_hit = extract_function(stock, 'spellhit').replace('function spellhit', 'function Bards_Deflect_Spell_Hit')
    spell_hit = replace_once(spell_hit, accuracy,
        '\t\t\t$Bards_Deflect_Commit(defender);\n\t\t\treturn 4;\n' + accuracy)
    # Called only with a ready Hero defender. Stock spell accuracy is 100, but
    # preserve its RNG draw and miss branch; no MR draw or second attack occurs.
    resolvers = []
    for original, private, params, target in (
        ('spell_attack', 'Bards_Deflect_Spell', 'agent thisagent, agent target', 'target'),
        ('player_spell_attack', 'Bards_Deflect_Player', 'agent target', 'target'),
    ):
        function = extract_function(stock, original)
        function = re.sub(r'(?im)^function[^\n]+', f'function {private}({params}) is boolean', function, count=1)
        function = function.replace('return;', 'return FALSE;')
        function = re.sub(r'(?im)^begin\s*$', lambda m: m[0] +
            f'\n\tif ($Bards_Deflect_Ready({target}) == FALSE) return FALSE;\n', function, count=1)
        function = function.replace('$spellhit(target)', '$Bards_Deflect_Spell_Hit(target)')
        start = function.index('\tif (hitresult == 1)')
        end = function.index('\t$attack_end', start) if original == 'spell_attack' else function.rindex('\nend')
        function = function[:start] + function[end:]
        end = function.rindex('\nend')
        function = function[:end] + '\n\treturn TRUE;' + function[end:]
        resolvers.append(function)

    callbacks = []
    for name in ('Energy_Blast_Hit', 'Power_Shock_Hit', 'Acid_Bolt_Hit',
                 'Electrical_Fury_Hit', 'Spire_Blast_Hit', 'Ixmil_Blast_Hit',
                 'Insect_Swarm_Hit', 'horrify_hit', 'Pestilence_missile_Hit',
                 'Infectious_Cloud_Hit', 'Drain_Life_Hit', 'Life_Leach_Hit'):
        callbacks.append(intercept_spell(extract_function(spells, name)))
    tower = (root / 'Buildings/mx_Tower.gpl').read_text(encoding='cp1252')
    callbacks.append(intercept_spell(extract_function(tower, 'tower_blast_callback')))
    for name in ('Fire_Strike_Damage', 'Lightning_Bolt_Damage'):
        callbacks.append(intercept_spell(extract_function(spells, name), target_only=True))
    fire = extract_function(spells, 'Fire_Blast_Hit')
    anchor = '\t\t\t$createeffector( target, "fire_blast_effector",'
    fire = replace_once(fire, anchor, '\t\t\tif ($Bards_Deflect_Spell(ThisAgent, Target)) return;\n' + anchor)
    callbacks.append(fire)
    hammer = extract_function(spells, 'Fire_Hammer_Hit')
    anchor = '\t\t\t$Spell_Attack ( thisagent, target, 20 + ( $getattribute ( thisagent, #ATTRIB_experienceLevel ) * 2 ));'
    hammer = replace_once(hammer, anchor, '\t\t\tif ($Bards_Deflect_Spell(ThisAgent, Target) == FALSE)\n' + anchor)
    callbacks.append(hammer)
    return '\n'.join((physical, spell_hit, *resolvers, *callbacks))


def combat_functions(sdk: Path, extract_function) -> str:
    stock = (sdk / "GPLMx/TaskModules/Subtasks/mx_Make_Attack.gpl").read_text(encoding="cp1252")
    physical = extract_function(stock, "damage")
    physical = replace_once(physical, 'boolean do_poison,critical_effect;',
                            'boolean do_poison,critical_effect,BardsFlourish;')
    physical = replace_once(physical, '\nbegin\n',
                            '\nbegin\n\tBardsFlourish = $Bards_Consume_Flourish(attacker, defender);\n')
    roll = 'dmg = $randomnumber ( $GetAttribute ( attacker, #ATTRIB_weapon_basic_damage )) + 1;'
    physical = replace_once(physical, roll, roll + '\n\t\t\t\t\t\t\t\tif (attacker\'s "title" == "Blade_Dancer") dmg += $randomnumber(8) + 1;')
    evaluation = (sdk / 'GPLMx/DecisionTrees/Modules/mx_target_eval.gpl').read_text(encoding='cp1252')
    hero_damage = extract_function(evaluation, 'hero_damage')
    hero_damage = replace_once(hero_damage, 'value = $hero_weapon_value(thisagent);',
        'value = $hero_weapon_value(thisagent);\n\tif (thisagent\'s "title" == "Blade_Dancer") value += 8;')
    anchor = 'dmg += $GetAttribute ( attacker, #ATTRIB_weapon_magic_bonus );'
    physical = replace_once(physical, anchor, anchor + '\n\t\t\t\t\t\t\t\tif ($CheckEffector(attacker, "Bards_Roused_Icon")) dmg += 2;')
    physical = replace_once(physical, anchor, anchor + '\n\t\t\t\t\t\t\t\tif (BardsFlourish) dmg += 3;')
    anchor = '\t\tif (( defender\'s "type" == "building" ) || ( defender\'s "type" == "lair" ))'
    physical = replace_once(physical, anchor,
        '\tif (critical_effect == FALSE)\n'
        '\t\tdmg += $Bards_Refrain_Bonus(attacker);\n\n' + anchor)
    anchor = '\t\t\t\tt = dmg_stopped / 4;'
    physical = replace_once(physical, anchor,
        '\t\t\t\tif (BardsFlourish && critical_effect == FALSE) dmg_stopped = dmg_stopped / 2;\n' + anchor)
    anchor = '\tif ( dmg < 0 ) dmg = 0;'
    physical = replace_once(physical, anchor,
        '\tif (critical_effect == FALSE)\n\t\tdmg = $Bards_Direct_Damage(attacker, defender, dmg);\n\n' + anchor)
    # Record the already-resolved positive hit before any critical-hit or poison
    # presentation callback can synchronously invoke the target's death script.
    anchor = '\tif ( dmg > 0 )\n\t\tbegin'
    physical = replace_once(physical, anchor,
        anchor + '\n\t\t\t$Bards_Renown_Hit(attacker, defender, dmg);\n\t\t\t$Bards_Finale_Record(attacker, defender, dmg);')

    periodic_damage = extract_function(stock, "spelldamage")
    anchor = '\t// if defender is hero with enchanted armor, reduce the damage'
    periodic_damage = replace_once(periodic_damage, anchor,
        '\tdmg += $Bards_Refrain_Bonus(attacker);\n\n' + anchor)
    direct_spell = periodic_damage
    direct_spell = re.sub(r'(?im)^function spelldamage', 'function Bards_Direct_Spell_Damage', direct_spell, count=1)
    anchor = '\t$adjustattribute(defender,#ATTRIB_HP,-dmg);'
    direct_spell = replace_once(direct_spell, anchor,
        '\tdmg = $Bards_Direct_Damage(attacker, defender, dmg);\n'
        '\t$Bards_Renown_Hit(attacker, defender, dmg);\n' + anchor)

    spell_attack = extract_function(stock, "spell_attack")
    periodic = re.sub(r'(?im)^function spell_attack', 'function Bards_Periodic_Spell_Attack', spell_attack, count=1)
    spell_attack = replace_once(spell_attack, '$spelldamage(thisagent,target,damage,1);',
                               '$Bards_Direct_Spell_Damage(thisagent,target,damage,1);')
    spells = (sdk / "GPLMx/TaskModules/Subtasks/mx_Spells.gpl").read_text(encoding="cp1252")
    # Stock target-only hits retain their reaction, resistance and roll order.
    # Preserve an exact stock resolver for Wind Storm's repeating damage ticks.
    player_attack = extract_function(stock, 'player_spell_attack')
    periodic_player = player_attack.replace('function player_spell_attack',
                                           'function Bards_Periodic_Player_Spell_Attack', 1)
    player_attack = replace_once(player_attack,
        '$spelldamage($nullagent(),target,damage,damage_minimum);',
        '$Bards_Direct_Spell_Damage($nullagent(),target,damage,damage_minimum);')
    # Source attribution is separate from stock attacker ownership: target-only
    # spells must not acquire Intelligence scaling or attack XP from their caster.
    attributed = []
    for original, adapter, resolver, resolver_name in (
        (player_attack, 'Bards_PlayerSpellAttackAttributed', direct_spell, 'Bards_Direct_Spell_Damage'),
        (periodic_player, 'Bards_PeriodicPlayerAttributed', periodic_damage, 'spelldamage'),
    ):
        damage_name = adapter + 'Damage'
        resolved = re.sub(r'(?im)^function ' + resolver_name + r'\(',
                          'function ' + damage_name + '(agent Source,', resolver, count=1)
        resolved = replace_once(resolved, '$Bards_Refrain_Bonus(attacker)', '$Bards_Refrain_Bonus(Source)')
        attack = re.sub(r'(?im)^function \w+\(', 'function ' + adapter + '(agent Source,', original, count=1)
        attack = replace_once(attack, '$' + resolver_name + '($nullagent(),target,damage,damage_minimum);',
                              '$' + damage_name + '(Source,$nullagent(),target,damage,damage_minimum);')
        attributed.extend((attack, resolved))
    wind = extract_function(spells, 'Wind_Storm_Active')
    wind = replace_once(wind, '$player_spell_attack( target, 24, 10 );',
                        '$Bards_Periodic_Player_Spell_Attack( target, 24, 10 );')
    shield = extract_function(spells, 'Damage_Shield_Hit')
    shield = replace_once(shield,
        '$adjustattribute ( ThisAgent, #ATTRIB_HP, - ( #Damage_Shield_Damage ));',
        '$adjustattribute ( ThisAgent, #ATTRIB_HP, - ( $Bards_Direct_Damage($NullAgent(), ThisAgent, #Damage_Shield_Damage) ));')
    vortex = extract_function(spells, "Vortex_Active")
    vortex = replace_once(vortex, '$spell_attack( thisagent, target, 20 );',
                          '$Bards_Periodic_Spell_Attack( thisagent, target, 20 );')
    arcane_damage = direct_spell.replace('function Bards_Direct_Spell_Damage(agent attacker,agent defender,integer damage, integer damage_minimum)',
        'function Bards_Arcane_Damage(agent attacker,agent defender,integer damage, integer damage_minimum) is integer')
    # The primary Instrument attack consumes stock equipment bonuses once.
    # Keep the stock spell roll/Intelligence, defenses, XP and hit ownership.
    anchor = '\t// if defender is hero with enchanted armor, reduce the damage'
    arcane_damage = replace_once(arcane_damage, anchor,
        '\tif (attacker != $nullagent())\n\t\tbegin\n'
        '\t\t\tdmg += $GetAttribute(attacker, #ATTRIB_Weapon_Struct_Bonus);\n'
        '\t\t\tdmg += $GetAttribute(attacker, #ATTRIB_Weapon_Magic_Bonus);\n'
        '\t\t\tif ($CheckEffector(attacker, "Bards_Roused_Icon")) dmg += 2;\n'
        '\t\tend\n\tdmg += $Bards_Resonance_Count(defender);\n\n' + anchor)
    arcane_damage = replace_once(arcane_damage, '$adjustattribute(defender,#ATTRIB_HP,-dmg);',
                                '$adjustattribute(defender,#ATTRIB_HP,-dmg);\n\treturn dmg;')
    arcane_attack = re.sub(r'(?im)^function spell_attack', 'function Bards_Arcane_Attack', spell_attack, count=1)
    arcane_attack = replace_once(arcane_attack, 'integer exp_given,hitresult;', 'integer exp_given,hitresult,Dealt;\n\tcoordinate Center;')
    arcane_attack = replace_once(arcane_attack, '$Bards_Direct_Spell_Damage(thisagent,target,damage,1);',
        'Center = $LocationOf(Target);\n\t\t\tDealt = $Bards_Arcane_Damage(thisagent,target,damage,1);\n'
        '\t\t\tif (Dealt > 0) begin\n\t\t\t\t$Bards_Resonance_Add(ThisAgent, Target);\n'
        '\t\t\t\t$Bards_Reverberate(ThisAgent, Target, Center);\n\t\t\tend')
    # Stock hit/resist/XP ordering remains intact for echoes and Burst.
    echo_damage = direct_spell.replace('function Bards_Direct_Spell_Damage(agent attacker,agent defender,integer damage, integer damage_minimum)',
        'function Bards_Echo_Damage(agent attacker,agent defender,integer damage, integer damage_minimum) is integer')
    echo_damage = replace_once(echo_damage, '$adjustattribute(defender,#ATTRIB_HP,-dmg);',
                              '$adjustattribute(defender,#ATTRIB_HP,-dmg);\n\treturn dmg;')
    echo_attack = re.sub(r'(?im)^function spell_attack', 'function Bards_Echo_Attack', spell_attack, count=1)
    echo_attack = replace_once(echo_attack, 'integer exp_given,hitresult;', 'integer exp_given,hitresult,Dealt;')
    echo_attack = replace_once(echo_attack, '$Bards_Direct_Spell_Damage(thisagent,target,damage,1);',
        'Dealt = $Bards_Echo_Damage(thisagent,target,damage,1);\n\t\t\tif (Dealt > 0) $Bards_Resonance_Add(ThisAgent, Target);')
    echo_attack = intercept_spell(echo_attack)
    burst_attack = re.sub(r'(?im)^function spell_attack', 'function Bards_Burst_Attack', spell_attack, count=1)
    burst_attack = replace_once(burst_attack, 'integer exp_given,hitresult;', 'integer exp_given,hitresult,Dealt;')
    burst_attack = replace_once(burst_attack, '$Bards_Direct_Spell_Damage(thisagent,target,damage,1);',
        'Dealt = $Bards_Echo_Damage(thisagent,target,damage,1);\n\t\t\tif (Dealt > 0) $Bards_Crescendo(Target);')
    ordinary = extract_function(stock, 'make_attack')
    riposte = re.sub(r'(?im)^function make_attack', 'function Bards_Riposte_Attack', ordinary, count=1)
    riposte = replace_once(riposte, '\t// attacking removes camouflage effect',
        '\t$Bards_Finale_Attempt(ThisAgent, Target);\n\t// attacking removes camouflage effect')
    ordinary = replace_once(ordinary, '\t// attacking removes camouflage effect',
                            '\t$Bards_Flourish_Target(ThisAgent, Target);\n\n\t// attacking removes camouflage effect')
    ordinary = replace_once(ordinary, '$damage(thisagent,target);', '$Bards_Ordinary_Damage(thisagent,target);')
    ordinary = replace_once(ordinary, '$attack_end(thisagent,exp_given);',
                            '$attack_end(thisagent,exp_given);\n\tif (hitresult == 2) $Bards_Try_Riposte(Target, ThisAgent);')
    return '\n'.join((*attributed, physical, hero_damage, periodic_damage, direct_spell, spell_attack, periodic, vortex,
                      player_attack, periodic_player, wind, shield, arcane_damage, arcane_attack,
                      echo_damage, echo_attack, burst_attack, ordinary, riposte))


def renown_functions(sdk: Path, extract_function) -> str:
    """Keep stock death/capture and home visits; observe bounty via the Manager."""
    root = sdk / "GPLMx"
    monsters = (root / "mx_Monster_Deaths.gpl").read_text(encoding="cp1252")
    death = extract_function(monsters, "monster_gravestone")
    zoo_check = extract_function((root/'TaskModules/Buildings/Zoo.gpl').read_text(encoding='cp1252'), 'zoo_flag_check')
    # Guard the optional stock facility at its field owner. Do not early-return
    # from monster_gravestone: another mod may replace its Zoo check with one
    # that supports base monsters without the expansion field.
    zoo_check = replace_once(zoo_check, '\nbegin\n', '\nbegin\n'
        '\tif ($HasAttribute("zoo_agent", ThisAgent) == FALSE) return FALSE;\n')
    anchor = '\t\t\t// give out gold to players'
    death = replace_once(death, anchor, '\t\t\t$Bards_Renown_Defeat(thisagent, 1);\n' + anchor)
    # Capture is an existing alternate branch. Settle its supported deed there,
    # without starting a new task or touching stock charm/death restoration.
    anchor = '\t\tdeadflag = FALSE;'
    death = replace_once(death, anchor,
        '\t\tbegin\n\t\t\tdeadflag = FALSE;\n\t\t\t$Bards_Renown_Captured(thisagent);\n\t\tend')
    wight = extract_function(monsters, "Wight_Res_or_Die")
    anchor = '\t\t\tthisagent\'s "type" = "Waiting_to_die";'
    wight = replace_once(wight, anchor, '\t\t\t$Bards_Renown_Defeat(thisagent, 1);\n' + anchor)
    functions = [death, zoo_check, wight]
    buildings = (root / "mx_Building_Deaths.gpl").read_text(encoding="cp1252")
    for name in ("lair_death", "Lair_Multispawn_Death", "hideout_death"):
        function = extract_function(buildings, name)
        if name == 'lair_death':
            # Base Lair has no expansion list flag. Dispatch its literal stock
            # spawn branch without reading or adding an expansion-only field.
            start = function.index('\t//SpecialLairList')
            stop = function.index('\n\t$dropgoldinradius', start)
            expansion = function[start:stop]
            function = function[:start] + (
                '\tif ($HasAttribute("Has_Special_Spawn", ThisAgent))\n\t\tbegin\n'
                + expansion + '\n\t\tend\n\telse\n'
                '\t\tif (ThisAgent\'s "Special_Spawn_Type" != "xx")\n'
                '\t\t\t$SpawnUnit(ThisAgent, ThisAgent\'s "Special_Spawn_Type", $LocationOf(ThisAgent), "Override");\n'
            ) + function[stop:]
        anchor = '\t$dropgoldinradius(thisagent,$getattribute(thisagent,#ATTRIB_gold));'
        function = replace_once(function, anchor, '\t$Bards_Renown_Defeat(ThisAgent, 2);\n' + anchor)
        functions.append(function)
    function = extract_function(buildings, "building_death")
    anchor = '  \tthisagent\'s "type" = "Dead";'
    function = replace_once(function, anchor,
        '\tif ($GetAttribute(ThisAgent, #ATTRIB_HP) <= 0)\n\t\t$Bards_Renown_Defeat(ThisAgent, 0);\n' + anchor)
    functions.append(function)
    heroes = (root / "mx_Hero_Deaths.gpl").read_text(encoding="cp1252")
    function = extract_function(heroes, "gravestone")
    anchor = '\tthisagent\'s "type" = "Dead";'
    function = replace_once(function, anchor, '\t$Bards_Renown_Defeat(ThisAgent, 0);\n' + anchor)
    functions.append(function)
    # Attack-flag success is shared with other mods' reward observers. The
    # declared stock event owns both flag functions and their cleanup ordering.
    lived = (root / "TaskModules/Buildings/mx_Lived_In.gpl").read_text(encoding="cp1252")
    function = extract_function(lived, "Lived_In")
    function = re.sub(r'(?im)^Function Lived_In', 'Function Bards_Lived_In', function, count=1)
    anchor = '\tHero_Gold = $GetAttribute (ThisAgent, #ATTRIB_Gold);'
    function = replace_once(function, anchor, '\t$Bards_Renown_Settle(ThisAgent, ThisBuilding);\n' + anchor)
    functions.append(function)
    return '\n'.join(functions)


def support_functions(sdk: Path, extract_function) -> str:
    root = sdk / 'GPLMx'
    source = (root / 'DecisionTrees/Modules/mx_Follow_Heal_Check.gpl').read_text(encoding='cp1252')
    selection = extract_function(source, 'follow_support_check')
    selection = re.sub(r'(?i)\bfollow_support_check\b', 'Bards_Follow_Check', selection)
    selection = replace_once(selection, 'list new_potentials,guards;',
                             'list new_potentials,guards,Followers;\n\tboolean FollowersLoaded;')
    selection = replace_once(selection, '\nbegin\n', '\nbegin\n\tFollowersLoaded = FALSE;\n')
    selection = replace_once(selection, '#CheckTitles, WhatToSupport, #MyTeam', '#MyTeam')
    selection = replace_once(selection, 'Foreach Diddly in Potentials do',
        'if (WhatToSupport != "Hero") Potentials = $ListTitles(Potentials, WhatToSupport);\n\t\t\tForeach Diddly in Potentials do\n\t\t\t\tif ($Bards_Follow_Leader_Eligible(ThisAgent, Diddly))')
    selection = replace_once(selection,
        'if (((diddly\'s "backscript" == $use_building) && (diddly\'s "target" == diddly\'s "home")))',
        'if ($Bards_Follow_Going_Home(Diddly))')
    selection = replace_once(selection,
        'if ($ListObjects (Diddly, "Hero", Range, Guards, #CheckTitles, ThisAgent\'s "Title") < #support_max)',
        'if ($Bards_Follow_Active(Diddly))')
    selection = replace_once(selection, 'New_Potentials << Diddly;',
        'begin\n'
        '\t\t\t\t\t\t\t\t\tif (FollowersLoaded == FALSE)\n'
        '\t\t\t\t\t\t\t\t\t\tbegin\n'
        '\t\t\t\t\t\t\t\t\t\t\tFollowers = $Bards_Follow_Snapshot(ThisAgent);\n'
        '\t\t\t\t\t\t\t\t\t\t\tFollowersLoaded = TRUE;\n'
        '\t\t\t\t\t\t\t\t\t\tend\n'
        '\t\t\t\t\t\t\t\t\tif ($Bards_Follow_Assignment_Free(ThisAgent, Diddly, Followers)) New_Potentials << Diddly;\n'
        '\t\t\t\t\t\t\t\tend')
    selection = re.sub(r'(?i)\$follow_support\b', '$Bards_Follow_Support', selection)
    selection = replace_once(selection, 'ThisAgent\'s "BackTarget" = Best_One;',
        'ThisAgent\'s "BackTarget" = Best_One;\n\tThisAgent\'s "Target" = Best_One;')

    follow_source = (root / 'TaskModules/Characters/mx_Follow_Heal.gpl').read_text(encoding='cp1252')
    follow = extract_function(follow_source, 'follow_support')
    follow = re.sub(r'(?i)\bfollow_support\b', 'Bards_Follow_Support', follow)
    follow = replace_once(follow, '\ttarget = ThisAgent\'s "BackTarget";',
                          '\tif ($Bards_Hire_Guard(ThisAgent)) return;\n'
                          '\t$Bards_Follow_Intent(ThisAgent);\n'
                          '\tif ($Bards_Hire_Wait(ThisAgent)) return;\n\ttarget = ThisAgent\'s "BackTarget";')
    follow = replace_once(follow, 'if ($Bards_Hire_Guard(ThisAgent)) return;',
        'if ($Bards_Hire_Guard(ThisAgent)) return;\n\tif ($Bards_Renown_Return(ThisAgent)) return;')
    home = 'if ((target\'s "backScript" == $use_building) && (target\'s "target" == target\'s "home"))'
    follow = replace_once(follow, home, 'if ($Bards_Follow_Going_Home(Target))\n                        if ($Bards_Hire_Assigned(ThisAgent) == FALSE)')
    follow = replace_once(follow, '($getattribute(thisagent,#ATTRIB_maxattackrange) - #follow_support_buffer)',
                          '(180 - #follow_support_buffer)')
    follow = replace_once(follow, 'ThisAgent\'s "ActiveScript" = $Travel_To;',
                          'ThisAgent\'s "Target" = Target;\n\t\t\t\t\t\t\tThisAgent\'s "ActiveScript" = $Bards_Travel_Support;')
    follow = replace_once(follow, '// Am I in Range of target?',
                          'if ($Bards_Combat_Support(ThisAgent, Target)) return;\n\t\t\t\t\t// Am I in Range of target?')
    start = follow.index('\t\t\t\t\t\t\t// see if anyone is attacking me')
    stop = follow.index('\t\t\t\t\t\t\t\t\t\t// I have nothing to do!', start)
    # Preserve the exact stock idle/bored/small-step tail. Only the offensive
    # join decision becomes private noncombatant evaluation followed by songs.
    follow = follow[:start] + '''\t\t\t\t\t\t\tif ($Bards_Troubadour_Evaluate(ThisAgent)) return;
                            if ($Bards_Try_Song(ThisAgent) == FALSE)
                                    begin
''' + follow[stop:]
    travel_source = (root / 'TaskModules/Characters/mx_Travel_to.gpl').read_text(encoding='cp1252')
    travel = extract_function(travel_source, 'travel_to_safe')
    travel = re.sub(r'(?i)\btravel_to_safe\b', 'Bards_Travel_Support', travel)
    travel = replace_once(travel, '\nbegin\n', '\nbegin\n\tif ($Bards_Hire_Guard(ThisAgent)) return;\n')
    travel = replace_once(travel, 'if ($Bards_Hire_Guard(ThisAgent)) return;',
        'if ($Bards_Hire_Guard(ThisAgent)) return;\n\tif ($Bards_Renown_Return(ThisAgent)) return;')
    travel = replace_once(travel, '$TryTravelSpell( thisagent )', '$Bards_Try_Travel_Song( thisagent )')
    travel = replace_once(travel, '$has_arrived(thisagent,true)', '$Bards_Support_Arrived(thisagent,true)')
    arrived = extract_function(travel_source, 'has_arrived')
    arrived = re.sub(r'(?i)\bhas_arrived\b', 'Bards_Support_Arrived', arrived)
    arrived = replace_once(arrived, 'arrivedist = $gettargetrange(thisagent);', 'arrivedist = (180 - #follow_support_buffer);')
    return selection + '\n' + follow + '\n' + travel + '\n' + arrived


def hiring_functions(sdk: Path, extract_function) -> str:
    """Preserve stock shopping, money, follow, travel and death lifecycles."""
    root = sdk / 'GPLMx'
    def read(path, name):
        return extract_function((root / path).read_text(encoding='cp1252'), name)

    shopping = read('DecisionTrees/Modules/mx_Purchase_Equipment.gpl', 'Purchase_Equipment')
    # The existing snapshot is reused only when every stock purchase declined.
    shopping = replace_once(shopping, '\treturn False;\nEnd',
                            '\treturn $Bards_Hire_Check(ThisAgent, Buildings);\nEnd')
    payment = read('mx_LowLevel.gpl', 'Spend_Gold')
    payment = replace_once(payment,
        'Function Spend_Gold (agent ThisAgent, agent ThisBuilding, integer Gold)',
        'Function Bards_Hire_Pay (agent ThisAgent, agent ThisBuilding, integer Gold, agent Bard)')
    # Preserve stock stored-first debit and guild-credit ordering. The approved
    # hire fee splits evenly regardless of the guild's ordinary tax rate; the
    # otherwise vaporized share is the hired existing hero's earnings.
    payment = replace_once(payment,
        'Spent_Gold = (Gold * $GetAttribute (ThisBuilding, #ATTRIB_TaxRate)) / 100;',
        'Spent_Gold = Gold / 2;')
    payment = replace_once(payment, '$Vaporize_Gold (ThisAgent, Vaporized_Gold);',
                            '$Give_Gold (Bard, Vaporized_Gold);')
    payment = payment.replace('//Amount of gold that is vaporized', '//Amount of gold earned by the hired bard')
    payment = payment.replace('//Vaporize the Ramainder of the gold', '//Pay the remainder to the hired bard')
    follow = read('TaskModules/Characters/mx_Follow_Heal.gpl', 'follow_support')
    follow = re.sub(r'(?i)\bfollow_support\b', 'Bards_Hired_Follow', follow)
    follow = replace_once(follow, '\ttarget = ThisAgent\'s "BackTarget";',
                           '\tif ($Bards_Hire_Guard(ThisAgent)) return;\n'
                           '\t$Bards_Follow_Intent(ThisAgent);\n'
                           '\tif ($Bards_Hire_Wait(ThisAgent)) return;\n\ttarget = ThisAgent\'s "BackTarget";')
    home = 'if ((target\'s "backScript" == $use_building) && (target\'s "target" == target\'s "home"))'
    follow = replace_once(follow, home, 'if ($Bards_Follow_Going_Home(Target))\n                        if ($Bards_Hire_Assigned(ThisAgent) == FALSE)')
    follow = replace_once(follow, '($getattribute(thisagent,#ATTRIB_maxattackrange) - #follow_support_buffer)',
                           '(180 - #follow_support_buffer)')
    follow = replace_once(follow, 'ThisAgent\'s "Destination" = $LocationOf (Target);',
                           'ThisAgent\'s "Target" = Target;\n\t\t\t\t\t\t\tThisAgent\'s "Destination" = $LocationOf (Target);')
    travel_spell = read('TaskModules/Characters/mx_Travel_to.gpl', 'TryTravelSpell')
    travel_spell = replace_once(travel_spell,
        '\t\t\t// can I use any helpful travel spells?',
        '\t\t\tif ($Bards_Try_Travel_Song(ThisAgent)) return True;\n'
        '\t\t\t// can I use any helpful travel spells?')
    functions = [shopping, payment, follow, travel_spell]
    for symbol in ('berserk', 'berserk_defend'):
        block = read('TaskModules/Characters/mx_' + symbol + '.gpl', symbol)
        block = re.sub(r'(?im)^begin\s*$', lambda m: m[0] + '\n\tif ($Bards_Try_Finale(ThisAgent)) return;\n', block, count=1)
        functions.append(block)
    # Existing AI entry points, guarded only for a bard with a live contract.
    # No new thread, callback timer or alternate stock combat controller.
    for path, name in (
        ('TaskModules/Characters/mx_Attack_object.gpl', 'attack_object'),
        ('TaskModules/Characters/mx_Travel_to.gpl', 'travel_to'),
        ('TaskModules/Characters/mx_Travel_to.gpl', 'travel_to_safe'),
    ):
        block = read(path, name)
        block = re.sub(r'(?im)^begin\s*$', lambda m: m[0] + '\n\tif ($Bards_Hire_Guard(ThisAgent)) return;\n', block, count=1)
        block = re.sub(r'(?im)^begin\s*$', lambda m: m[0] + '\n\t$Bards_Street_Service(ThisAgent);\n', block, count=1)
        functions.append(block)
    for name in ('Unit_Dismissed', 'Unit_Call_Deathscript'):
        block = read('mx_Hero_Deaths.gpl', name)
        block = re.sub(r'(?im)^begin\s*$', lambda m: m[0] + '\n\t$Bards_Hire_Abort(ThisAgent);\n\t$Bards_Flourish_Reset(ThisAgent);\n\t$Bards_Finale_Clear(ThisAgent);\n', block, count=1)
        block = re.sub(r'(?im)^begin\s*$', lambda m: m[0] + '\n\t$Bards_Street_End(ThisAgent);\n', block, count=1)
        functions.append(block)
    return '\n'.join(functions)
