"""Stock-relative audit of the ability package, not a substitute for a playtest."""
from __future__ import annotations

from pathlib import Path
import re
import copy
import xml.etree.ElementTree as ET
from validate_bards_deflect import check_deflect
from validate_bards_spellsinger import check_spellsinger


# AddAttribute resolves runtime factory names, not GPL declaration keywords.
# beta2 0x56BD10 registers these at 0x56BDB5..0x56BF30; AGENTREF is type 5.
# An unknown type allocates nothing (0x5D43BF), even if GPL compilation succeeds.
DYNAMIC_ATTRIBUTE_TYPES = frozenset({
    'integer', 'float', 'string', 'list', 'agentref', 'boolean', 'coord', 'function',
})


def check_dynamic_attribute_types(source: str, label: str):
    code = re.sub(r'//[^\n]*', '', source)
    calls = re.findall(
        r'\$AddAttribute\s*\(\s*\w+\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"', code, re.I)
    require(len(calls) == len(re.findall(r'\$AddAttribute\s*\(', code, re.I)),
            f'{label}: dynamic attribute declarations must use auditable literal names/types')
    for field, kind in calls:
        require(kind.lower() in DYNAMIC_ATTRIBUTE_TYPES,
                f'{label}: {field} uses unsupported AddAttribute type {kind!r}')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def tokens(source):
    return re.findall(r'"[^"\n]*"|[A-Za-z_#][\w#]*|\d+|[^\s]',
                      re.sub(r'//[^\n]*', '', source))


def stock_equal(actual, expected, label):
    require(tokens(actual) == tokens(expected), f"Unapproved stock lifecycle change: {label}")


def check_abilities(sdk: Path, package: Path, extract_function):
    gpl = package / "GPL"
    source = sdk / "GPLMx"
    abilities = ET.parse(package / "Data/bards_abilities.xml").getroot()
    require(len(abilities) == 37, "Unexpected ability description count")
    require(len({d.get('ID') for d in abilities}) == len(abilities), "Duplicate ability ID")
    overlay = copy.deepcopy(abilities.find('./Description[@Name="Bards_Chronicles_Active"]'))
    original = ET.parse(sdk / 'Data/M_Overlays.xml').find('.//Description[@Name="super_charge_effector"]')
    overlay.attrib = original.attrib.copy()
    for field in ('ImageIDBase', 'DefaultSound'):
        overlay.find('./Engine/' + field).attrib = original.find('./Engine/' + field).attrib.copy()
    def shape(node):
        return node.tag, node.attrib, [shape(child) for child in node]
    require(shape(overlay) == shape(original), 'Chronicles effect must retain full stock Super Charge descriptor')
    healing = ET.parse(sdk / 'Data/M_Overlays.xml').find('.//Description[@Name="healer_healing_effector"]')
    for song in ('Valor', 'March', 'Satire', 'Refrain'):
        flash = copy.deepcopy(abilities.find(f'./Description[@Name="Bards_{song}_Flash"]'))
        flash.attrib = healing.attrib.copy()
        flash.find('./Engine/ImageIDBase').attrib = healing.find('./Engine/ImageIDBase').attrib.copy()
        require(shape(flash) == shape(healing), f'{song} target flash must preserve stock healing lifecycle')

    note = abilities.find('./Description[@Name="Bards_Arcane_Note"]')
    burst = abilities.find('./Description[@Name="Bards_Resonant_Burst"]')
    require(note.find('./Game/CharacterLevel').get('value') == '1', "Arcane Note must start at level 1")
    require(note.find('./Game/TimeoutDuration').get('value') == '1000', "Arcane Note changed stock timeout")
    require(note.find('./Engine/Projectile').get('value') == 'Bards_Arcane_Note_Missile', "Arcane Note has no private projectile")
    require(burst.find('./Game/CharacterLevel').get('value') == '8', "Burst unlock changed")
    require(burst.find('./Game/TimeoutDuration').get('value') == '12000', "Burst default timeout changed")
    require(burst.find('./Game/ValidationScript').get('value') == 'Bards_Resonant_Burst_Check', "Burst cluster validation missing")
    units = ET.parse(package / "Data/bards_units.xml").getroot()
    singer = units.find('./Description[@Name="Spellsinger"]')
    require([s.get('Value') for s in singer.find('./Game/AllowedSpells')] ==
            ['Bards_Arcane_Note', 'Bards_Resonant_Burst', 'Bards_Countermelody'], "Spellsinger attack dispatch changed")
    dancer = units.find('./Description[@Name="Blade_Dancer"]')
    require(all(dancer.find('./Game/' + a).get('value') == v for a, v in (('Dodge', '55'), ('Parry', '65'))),
            "Blade Dancer defensive training changed")
    troubadour = units.find('./Description[@Name="Troubadour"]')
    require([s.get('Value') for s in troubadour.find('./Game/AllowedSpells')] ==
            ['Bards_Valor', 'Bards_March', 'Bards_Satire', 'Bards_Refrain'], 'Troubadour learned song table changed')
    for song, level, duration, cooldown in (('Bards_Valor', '1', '8000', '6000'),
                                            ('Bards_March', '3', '8000', '6000'),
                                            ('Bards_Satire', '5', '6000', '8000'),
                                            ('Bards_Refrain', '8', '10000', '30000')):
        action = abilities.find(f'./Description[@Name="{song}"]')
        for field, expected in (('CharacterLevel', level), ('EffectorDuration', duration), ('TimeoutDuration', cooldown)):
            require(action.find('./Game/' + field).get('value') == expected, f'{song}: incorrect {field}')
        require(not action.findall('./Game/SpellType'), 'Friendly songs must not enter native attack-spell selection')
        require(action.find('./Engine/Script').get('GPLFunction') == song + '_Complete', 'Song callback missing')

    stock_spells = (source / 'TaskModules/Subtasks/mx_Spells.gpl').read_text(encoding='cp1252')
    arcane = (gpl / 'Bards_Arcane_Note.gpl').read_text()
    arcane = arcane.replace("Bards_Echo_Flash", "energy_blast_effector")
    arcane = arcane.replace('Bards_Arcane_Note_Hit', 'Energy_Blast_Hit').replace('"Bards_Arcane_Note"', '"energy_blast"')
    arcane = arcane.replace('$Bards_Arcane_Attack', '$spell_attack')
    arcane = arcane.replace('if ($Bards_Deflect_Spell(ThisAgent, Target)) return;', '')
    stock_equal(arcane, extract_function(stock_spells, 'Energy_Blast_Hit'), 'Arcane Note')
    combat = (gpl / 'Bards_Combat.gpl').read_text()
    stock_combat = (source / 'TaskModules/Subtasks/mx_Make_Attack.gpl').read_text(encoding='cp1252')
    physical = extract_function(combat, 'damage')
    require(physical.index('$Bards_Direct_Damage') > physical.index('dmg -= dmg_stopped;'),
            "Flat combat reduction must follow armor")
    require(physical.index('$Bards_Renown_Hit') < physical.index('$adjustattribute ( defender, #ATTRIB_HP, -dmg );'),
            "Renown contribution must exist before a lethal debit invokes death")
    physical = re.sub(r'\s*if \(critical_effect == FALSE\)\s*dmg \+= \$Bards_Refrain_Bonus\(attacker\);', '', physical)
    physical = re.sub(r'\s*if \(critical_effect == FALSE\)\s*dmg = \$Bards_Direct_Damage\(attacker, defender, dmg\);', '', physical)
    physical = re.sub(r'\s*\$Bards_Renown_Hit\(attacker, defender, dmg\);', '', physical)
    physical = re.sub(r'\s*if \(\$CheckEffector\(attacker, "Bards_Roused_Icon"\)\) dmg \+= 2;', '', physical)
    physical = physical.replace('$Bards_Finale_Record(attacker, defender, dmg);', '')
    physical = physical.replace("if (attacker's \"title\" == \"Blade_Dancer\") dmg += $randomnumber(8) + 1;", '')
    physical = physical.replace(',BardsFlourish;', ';')
    physical = physical.replace('BardsFlourish = $Bards_Consume_Flourish(attacker, defender);', '')
    physical = physical.replace('if (BardsFlourish) dmg += 3;', '')
    physical = physical.replace('if (BardsFlourish && critical_effect == FALSE) dmg_stopped = dmg_stopped / 2;', '')
    stock_equal(physical, extract_function(stock_combat, 'damage'), 'physical damage')
    evaluation = (source / 'DecisionTrees/Modules/mx_target_eval.gpl').read_text(encoding='cp1252')
    estimated = extract_function(combat, 'hero_damage')
    extra = "if (thisagent's \"title\" == \"Blade_Dancer\") value += 8;"
    require(estimated.count(extra) == 1, 'Dancer offhand absent from combat estimate')
    stock_equal(estimated.replace(extra, ''), extract_function(evaluation, 'hero_damage'), 'dual weapon stock AI estimate')

    direct = extract_function(combat, 'Bards_Direct_Spell_Damage').replace('Bards_Direct_Spell_Damage', 'spelldamage')
    direct = re.sub(r'\s*dmg = \$Bards_Direct_Damage\(attacker, defender, dmg\);', '', direct)
    direct = re.sub(r'\s*\$Bards_Renown_Hit\(attacker, defender, dmg\);', '', direct)
    refrain_bonus = 'dmg += $Bards_Refrain_Bonus(attacker);'
    require(direct.count(refrain_bonus) == 1, 'Direct spell Refrain bonus must apply once')
    direct = direct.replace(refrain_bonus, '')
    stock_equal(direct, extract_function(stock_combat, 'spelldamage'), 'direct spell damage')
    stock_equal(extract_function(combat, 'spell_attack').replace('$Bards_Direct_Spell_Damage', '$spelldamage'),
                extract_function(stock_combat, 'spell_attack'), 'spell attack')
    stock_equal(extract_function(combat, 'Bards_Periodic_Spell_Attack').replace('Bards_Periodic_Spell_Attack', 'spell_attack'),
                extract_function(stock_combat, 'spell_attack'), 'periodic spell attack')
    stock_equal(extract_function(combat, 'Vortex_Active').replace('$Bards_Periodic_Spell_Attack', '$spell_attack'),
                extract_function(stock_spells, 'Vortex_Active'), 'Vortex damage exclusion')
    arcane_attack = extract_function(combat, 'Bards_Arcane_Attack').replace('Bards_Arcane_Attack', 'spell_attack')
    arcane_attack = arcane_attack.replace('integer exp_given,hitresult,Dealt;\n\tcoordinate Center;', 'integer exp_given,hitresult;')
    arcane_attack = arcane_attack.replace('Center = $LocationOf(Target);', '').replace('Dealt = $Bards_Arcane_Damage', '$Bards_Direct_Spell_Damage')
    arcane_attack = re.sub(r'if \(Dealt > 0\) begin\s*\$Bards_Resonance_Add\(ThisAgent, Target\);\s*\$Bards_Reverberate\(ThisAgent, Target, Center\);\s*end', '', arcane_attack)
    stock_equal(arcane_attack, extract_function(combat, 'spell_attack'), 'ordinary note proc boundary')
    arcane_damage = extract_function(combat, 'Bards_Arcane_Damage').replace('Bards_Arcane_Damage', 'Bards_Direct_Spell_Damage')
    arcane_damage = arcane_damage.replace(') is integer', ')').replace('return dmg;', '')
    equipment_bonus = ('if (attacker != $nullagent())\n\t\tbegin\n'
        '\t\t\tdmg += $GetAttribute(attacker, #ATTRIB_Weapon_Struct_Bonus);\n'
        '\t\t\tdmg += $GetAttribute(attacker, #ATTRIB_Weapon_Magic_Bonus);\n\t\tend')
    arcane_damage = arcane_damage.replace('\t\t\tif ($CheckEffector(attacker, "Bards_Roused_Icon")) dmg += 2;\n', '')
    require(arcane_damage.count(equipment_bonus) == 1, 'Arcane Note must consume equipment bonuses exactly once')
    require(arcane_damage.index(equipment_bonus) < arcane_damage.index('dmg -= $getattribute'),
            'Arcane Note equipment bonuses must precede armor mitigation')
    arcane_damage = arcane_damage.replace(equipment_bonus, '').replace('dmg += $Bards_Resonance_Count(defender);', '')
    stock_equal(arcane_damage, extract_function(combat, 'Bards_Direct_Spell_Damage'), 'ordinary note damage result')
    echo_damage = extract_function(combat, 'Bards_Echo_Damage').replace('Bards_Echo_Damage', 'Bards_Direct_Spell_Damage')
    echo_damage = echo_damage.replace(') is integer', ')').replace('return dmg;', '')
    stock_equal(echo_damage, extract_function(combat, 'Bards_Direct_Spell_Damage'), 'full independent echo before mitigation')
    echo_attack = extract_function(combat, 'Bards_Echo_Attack').replace('Bards_Echo_Attack', 'spell_attack').replace('Bards_Echo_Damage', 'Bards_Direct_Spell_Damage')
    echo_attack = echo_attack.replace('if ($Bards_Deflect_Spell(ThisAgent, Target)) return;', '')
    echo_attack = echo_attack.replace('integer exp_given,hitresult,Dealt;', 'integer exp_given,hitresult;').replace('Dealt = ', '').replace('if (Dealt > 0) $Bards_Resonance_Add(ThisAgent, Target);', '')
    stock_equal(echo_attack, extract_function(combat, 'spell_attack'), 'nonrecursive echo hit and experience')
    require('$Bards_Reverberate' not in extract_function(combat, 'Bards_Echo_Attack'), 'Echo cannot recurse')
    ordinary = extract_function(combat, 'make_attack').replace('$Bards_Flourish_Target(ThisAgent, Target);', '')
    ordinary = ordinary.replace('$Bards_Ordinary_Damage', '$damage').replace('if (hitresult == 2) $Bards_Try_Riposte(Target, ThisAgent);', '')
    stock_equal(ordinary, extract_function(stock_combat, 'make_attack'), 'ordinary attack and parry reaction boundary')
    riposte = extract_function(combat, 'Bards_Riposte_Attack').replace('Bards_Riposte_Attack', 'make_attack')
    riposte = riposte.replace('$Bards_Finale_Attempt(ThisAgent, Target);', '')
    stock_equal(riposte, extract_function(stock_combat, 'make_attack'), 'nonrecursive stock Riposte resolution')
    require('Bards_Flourish_Damage' not in combat, 'Flourish must use composed global damage')
    periodic_damage = extract_function(combat, 'spelldamage')
    require(periodic_damage.count(refrain_bonus) == 1, 'Periodic outgoing Refrain bonus must apply once')
    stock_equal(periodic_damage.replace(refrain_bonus, ''),
                extract_function(stock_combat, 'spelldamage'), 'periodic incoming damage remains stock')
    player = extract_function(combat, 'player_spell_attack')
    require(player.count('$Bards_Direct_Spell_Damage($nullagent(),target,damage,damage_minimum);') == 1,
            'Target-only direct spells must apply bard mitigation exactly once')
    stock_equal(player.replace('$Bards_Direct_Spell_Damage(', '$spelldamage('),
                extract_function(stock_combat, 'player_spell_attack'), 'target-only direct hit mitigation')
    stock_equal(extract_function(combat, 'Bards_Periodic_Player_Spell_Attack').replace(
                    'Bards_Periodic_Player_Spell_Attack', 'player_spell_attack'),
                extract_function(stock_combat, 'player_spell_attack'), 'periodic target-only resolver')
    stock_spell_source = (source / 'TaskModules/Subtasks/mx_Spells.gpl').read_text(encoding='cp1252')
    stock_equal(extract_function(combat, 'Wind_Storm_Active').replace(
                    'Bards_Periodic_Player_Spell_Attack', 'player_spell_attack'),
                extract_function(stock_spell_source, 'Wind_Storm_Active'), 'stock Wind Storm lifecycle')
    stock_equal(extract_function(combat, 'Damage_Shield_Hit').replace(
                    '$Bards_Direct_Damage($NullAgent(), ThisAgent, #Damage_Shield_Damage)', '#Damage_Shield_Damage'),
                extract_function(stock_spell_source, 'Damage_Shield_Hit'), 'shield retaliation mitigation')
    check_deflect(sdk, gpl, extract_function, stock_equal, require)
    check_spellsinger(sdk, package, extract_function, stock_equal, require)

    require(not list(gpl.glob('Bards_Conquest*.gpl')), 'Retired Conquest code must not ship')

    renown_stock = (gpl / 'Bards_Renown_Stock.gpl').read_text()
    death = extract_function(renown_stock, 'monster_gravestone')
    zoo_check = extract_function(renown_stock, 'zoo_flag_check')
    guard = 'if ($HasAttribute("zoo_agent", ThisAgent) == FALSE) return FALSE;'
    require(zoo_check.count(guard) == 1, 'Base monsters must not enter expansion Zoo field reads')
    stock_equal(zoo_check.replace(guard, ''), extract_function((source/'TaskModules/Buildings/Zoo.gpl').read_text(encoding='cp1252'), 'zoo_flag_check'),
                'optional stock Zoo field guard')
    require(death.index('$Bards_Renown_Defeat') > death.index('if ( deadflag == TRUE )'),
            'Zoo capture must precede Renown defeat')
    death = death.replace('$Bards_Renown_Defeat(thisagent, 1);', '')
    death = re.sub(r'begin\s*deadflag = FALSE;\s*\$Bards_Renown_Captured\(thisagent\);\s*end',
                   'deadflag = FALSE;', death)
    stock_equal(death, extract_function((source / 'mx_Monster_Deaths.gpl').read_text(encoding='cp1252'), 'monster_gravestone'),
                'monster capture/death lifecycle')
    lived = extract_function(renown_stock, 'Bards_Lived_In')
    require(lived.index('$enter_building') < lived.index('$Bards_Renown_Settle') < lived.index('Hero_Gold ='),
            'Renown must settle on entry before native tax/storage')
    lived = lived.replace('Bards_Lived_In', 'Lived_In').replace('$Bards_Renown_Settle(ThisAgent, ThisBuilding);', '')
    stock_equal(lived, extract_function((source / 'TaskModules/Buildings/mx_Lived_In.gpl').read_text(encoding='cp1252'), 'Lived_In'),
                'guild visit ownership and taxation')

    # Every native callback reference in our descriptions resolves to a shipped
    # function. A standalone GPL compile alone permits unresolved external names.
    combined = '\n'.join(p.read_text() for p in gpl.glob('*.gpl'))
    check_dynamic_attribute_types(combined, 'Bards GPL')
    functions = {f.lower() for f in re.findall(r'(?im)^function\s+(\w+)\s*\(', combined)}
    require(not {'attack_flag_poll', 'attack_flag_death_callback'} & functions,
            'Bards must subscribe to flag completion, not replace shared stock flag owners')
    for desc in abilities:
        for item in desc.findall('.//*[@GPLFunction]'):
            callback = item.get('GPLFunction')
            if desc.get('Name') == 'Bards_Crescendo_Icon' and callback == 'Paralytic_Gaze_End':
                # Crescendo deliberately uses the existing stock paralysis
                # expiry callback, available in both datasets.
                for path in (sdk/'GPL/TaskModules/Subtasks/Spells.gpl',
                             sdk/'GPLMx/TaskModules/Subtasks/mx_Spells.gpl'):
                    extract_function(path.read_text(encoding='cp1252'), callback)
                continue
            require(callback.lower() in functions, f'Missing private ability callback: {callback}')
    for reference in re.findall(r'\$(Bards_\w+)', combined):
        generated = {prefix + suffix for prefix in ('bards_contract', 'bards_show', 'bards_audience')
                     for suffix in ('_start', '_state', '_cancel')}
        require(reference.lower() in functions | generated, f'Missing private function: {reference}')
    songs = (gpl / 'Bards_Songs.gpl').read_text()
    code = re.sub(r'//[^\n]*', '', songs)
    require('$CastSpell' not in code and '$Cast(' not in code, 'Song cooldown must not be charged before completion')
    require(code.count('$MM_CommitSpellCooldown(') == 2, 'Only friendly completion and Satire completion may commit')
    completed = extract_function(songs, 'Bards_Song_Complete')
    require(completed.count('$MM_CommitSpellCooldown(') == 1, 'Friendly completion must commit once')
    require(completed.index('$Bards_Song_Useful') < completed.index('$MM_CommitSpellCooldown') < completed.index('$Bards_Valor_Apply'),
            'Completion must revalidate usefulness and commit once before applying the eligible snapshot')
    refresh = extract_function(songs, 'Bards_Song_Refresh')
    require(refresh.index('Remaining < 0') < refresh.index('Remaining <= 2000'), 'Negative timing results must not refresh')
    support = (gpl / 'Bards_Support_Stock.gpl').read_text()
    require('$Bards_Travel_Support' in support and '$Bards_Try_Song' in support, 'Support dispatch missing')
    travel = extract_function(support, 'Bards_Travel_Support')
    travel = travel.replace('\tif ($Bards_Hire_Guard(ThisAgent)) return;\n', '')
    travel = travel.replace('\tif ($Bards_Renown_Return(ThisAgent)) return;\n', '')
    travel = travel.replace('Bards_Travel_Support', 'travel_to_safe').replace('$Bards_Try_Travel_Song', '$TryTravelSpell')
    travel = travel.replace('$Bards_Support_Arrived', '$has_arrived')
    stock_travel = (sdk / 'GPLMx/TaskModules/Characters/mx_Travel_to.gpl').read_text(encoding='cp1252')
    stock_equal(travel, extract_function(stock_travel, 'travel_to_safe'), 'March follow-travel lifecycle')
    arrived = extract_function(support, 'Bards_Support_Arrived').replace('Bards_Support_Arrived', 'has_arrived')
    arrived = arrived.replace('(180 - #follow_support_buffer)', '$gettargetrange(thisagent)')
    stock_equal(arrived, extract_function(stock_travel, 'has_arrived'), 'Support arrival lifecycle')
    require(not re.search(r'=\s*\$attack_object\b', support, re.I), 'Support must not inherit Wizard offensive joining')
    satire = extract_function(songs, 'Bards_Satire_Complete')
    require(satire.count('$MM_CommitSpellCooldown(') == 1 and satire.index('$AgentInList') < satire.index('$MM_CommitSpellCooldown'),
            'Satire must revalidate the threatened party before its single commit')
    rates = (gpl / 'Bards_Rates.gpl').read_text()
    for effect in ('March', 'Satire'):
        apply = extract_function(rates, f'Bards_{effect}_Apply')
        reference = '$MM_ActionBasePeriod' if effect == 'March' else '$MM_UnitMovementBasePeriod'
        require(apply.index('if (Existing == FALSE)') < apply.index(reference) < apply.index('$CreateEffector'),
                'A refresh must retain the original fixed rate deltas')
        if effect == 'March':
            require('#ATTRIB_MovementRateModifier' not in apply and '$MM_UnitMovementBasePeriod' not in apply,
                    'Scaled March must not compound a movement-period modifier')
            require(apply.index('Bards_March_Legacy_Icon') < apply.index('$CreateEffector'),
                    'Legacy March must expire before new scaling applies')
        finish = extract_function(rates, f'Bards_{effect}_End')
        require('$MM_' not in finish, 'Rate expiry must undo the stored delta, not recalculate a new value')
    for filename in ('Bards_Effects.gpl', 'Bards_Renown.gpl', 'Bards_Spellsinger.gpl', 'Bards_Songs.gpl', 'Bards_Rates.gpl', 'Bards_Hiring.gpl', 'Bards_Dancer.gpl', 'Bards_Finale.gpl', 'Bards_Prize_Duel.gpl', 'Bards_Deflect.gpl', 'Bards_Countermelody.gpl', 'Bards_Street.gpl'):
        authored = re.sub(r'//[^\n]*', '', (gpl / filename).read_text())
        if filename == 'Bards_Spellsinger.gpl':
            removal = '$DeleteEffector(Target, "Bards_Reverberation_Icon");'
            require(authored.count(removal) == 1 and removal in extract_function(authored, 'Bards_Crescendo'),
                    'Only Crescendo may consume the target Resonance overlay')
            authored = authored.replace(removal, '')
        if filename == 'Bards_Finale.gpl':
            removal = '$DeleteEffector(Dancer, "Bards_Encore_Icon");'
            require(authored.count(removal) == 2, 'Encore must delete its infinite icon on consume/clear only')
            for callback in ('Bards_Finale_Attempt', 'Bards_Finale_Clear'):
                require(removal in extract_function(authored, callback), 'Encore removal has the wrong owner')
            authored = authored.replace(removal, '')
            removal = '$DeleteEffector(Target, "Bards_Finale_Ready_Icon");'
            require(authored.count(removal) == 1, 'Target marker removal must belong to the release helper')
            require(removal in extract_function(authored, 'Bards_Finale_Unmark'), 'Wrong target marker cleanup owner')
            authored = authored.replace(removal, '')
        require(not re.search(r'\$(?:NewThread|RunThread|SetThreadInterval|DeleteEffector|DeleteGamePiece)\b', authored, re.I),
                f'Custom lifecycle workaround in {filename}')
    hiring = (gpl / 'Bards_Hiring_Stock.gpl').read_text()
    travel_spell = extract_function(hiring, 'TryTravelSpell')
    travel_spell = travel_spell.replace('if ($Bards_Try_Travel_Song(ThisAgent)) return True;', '')
    stock_equal(travel_spell, extract_function((sdk / 'GPLMx/TaskModules/Characters/mx_Travel_to.gpl').read_text(encoding='cp1252'), 'TryTravelSpell'),
                'solo March preserves stock travel spell dispatch and fallback')
    shopping = extract_function(hiring, 'Purchase_Equipment').replace(
        'return $Bards_Hire_Check(ThisAgent, Buildings);', 'return False;')
    stock_equal(shopping, extract_function((source / 'DecisionTrees/Modules/mx_Purchase_Equipment.gpl').read_text(encoding='cp1252'), 'Purchase_Equipment'),
                'stock purchases before hiring')
    pay = extract_function(hiring, 'Bards_Hire_Pay').replace('Bards_Hire_Pay', 'Spend_Gold')
    pay = pay.replace('integer Gold, agent Bard)', 'integer Gold)').replace('$Give_Gold (Bard, Vaporized_Gold);', '$Vaporize_Gold (ThisAgent, Vaporized_Gold);')
    require('Spent_Gold = Gold / 2;' in pay, 'Hiring must split the approved fee equally')
    pay = pay.replace('Spent_Gold = Gold / 2;', 'Spent_Gold = (Gold * $GetAttribute (ThisBuilding, #ATTRIB_TaxRate)) / 100;')
    stock_equal(pay, extract_function((source / 'mx_LowLevel.gpl').read_text(encoding='cp1252'), 'Spend_Gold'),
                'stored-first payment and guild credit with approved equal split')
    for name, path in (('attack_object', 'TaskModules/Characters/mx_Attack_object.gpl'),
                       ('berserk', 'TaskModules/Characters/mx_berserk.gpl'),
                       ('berserk_defend', 'TaskModules/Characters/mx_berserk_defend.gpl'),
                       ('travel_to', 'TaskModules/Characters/mx_Travel_to.gpl'),
                       ('travel_to_safe', 'TaskModules/Characters/mx_Travel_to.gpl'),
                       ('Unit_Dismissed', 'mx_Hero_Deaths.gpl'), ('Unit_Call_Deathscript', 'mx_Hero_Deaths.gpl')):
        actual = extract_function(hiring, name).replace('if ($Bards_Hire_Guard(ThisAgent)) return;', '').replace('$Bards_Hire_Abort(ThisAgent);', '')
        actual = actual.replace('$Bards_Flourish_Reset(ThisAgent);', '').replace('$Bards_Finale_Clear(ThisAgent);', '')
        actual = actual.replace('$Bards_Street_Service(ThisAgent);', '').replace('$Bards_Street_End(ThisAgent);', '')
        actual = actual.replace('$Bards_Weapon_Action(ThisAgent, Target)', '(thisagent\'s "attack_action")')
        actual = actual.replace('if ($Bards_Try_Finale(ThisAgent)) return;', '')
        stock_equal(actual, extract_function((source / path).read_text(encoding='cp1252'), name), name + ' contract boundary')
    lifecycle = (gpl / 'Bards_Hiring.gpl').read_text()
    start = extract_function(lifecycle, 'Bards_Hire_Start')
    require('$Bards_Hire_Pay(Patron, Guild, 200, Bard);' in start, 'Hiring fee must total 200 gold')
    require('$Total_Gold(Patron) < 250' in extract_function(lifecycle, 'Bards_Hire_Patron_Free'),
            'Hiring must leave the existing 50-gold reserve after payment')
    require(start.index('Result != 1') < start.index('$Bards_Hire_Pay') < start.index('Bard\'s "BasicScript"'),
            'Contract registration must succeed before debit and assignment')
    condition = extract_function(lifecycle, 'Bards_Hire_Condition')
    require('$' not in re.sub(r'//[^\n]*', '', condition), 'Hiring condition must not scan or mutate')
    guild_data = (gpl / 'Bards_Building_Data.dat').read_text()
    require(guild_data.count('(Visited_Script Bards_Hall_Visited)') == 3, 'Every guild tier needs the hire visit callback')
