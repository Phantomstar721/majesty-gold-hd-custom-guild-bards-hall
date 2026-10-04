"""Audit the precise stock boundary of the approved defensive interception."""
import re


def check_deflect(sdk, gpl, extract_function, stock_equal, require):
    root = sdk / 'GPLMx/TaskModules'
    combat = (root / 'Subtasks/mx_Make_Attack.gpl').read_text(encoding='cp1252')
    spells = (root / 'Subtasks/mx_Spells.gpl').read_text(encoding='cp1252')
    source = (gpl / 'Bards_Deflect_Stock.gpl').read_text()
    physical = extract_function(source, 'hit')
    require(physical.index('$Bards_Deflect_Physical') > physical.index('<= attackertohit'),
            'Deflect must follow attacker accuracy')
    require(physical.index('$Bards_Deflect_Physical') < physical.index('> defenderavoid'),
            'Deflect must precede Dodge')
    physical = physical.replace('if ($Bards_Deflect_Physical(attacker, defender)) return 4;', '')
    stock_equal(physical, extract_function(combat, 'hit'), 'physical Deflect boundary')
    spell_hit = extract_function(source, 'Bards_Deflect_Spell_Hit')
    require(spell_hit.index('$Bards_Deflect_Commit') > spell_hit.index('<= attackertohit') and
            spell_hit.index('$Bards_Deflect_Commit') < spell_hit.index('> defenderavoid'),
            'Spell Deflect must sit between stock accuracy and MR')
    spell_hit = spell_hit.replace('Bards_Deflect_Spell_Hit', 'spellhit')
    spell_hit = spell_hit.replace('$Bards_Deflect_Commit(defender);', '').replace('return 4;', '')
    stock_equal(spell_hit, extract_function(combat, 'spellhit'), 'private spell Deflect boundary')
    for original, private in (('spell_attack', 'Bards_Deflect_Spell'),
                              ('player_spell_attack', 'Bards_Deflect_Player')):
        expected = extract_function(combat, original)
        actual = extract_function(source, private)
        actual = re.sub(r'(?im)^function[^\n]+', expected.splitlines()[0], actual, count=1)
        actual = actual.replace('if ($Bards_Deflect_Ready(target) == FALSE) return FALSE;', '')
        actual = actual.replace('return FALSE;', 'return;').replace('return TRUE;', '')
        actual = actual.replace('$Bards_Deflect_Spell_Hit', '$spellhit')
        start = expected.index('\tif (hitresult == 1)')
        end = expected.index('\t$attack_end', start) if original == 'spell_attack' else expected.rindex('\nend')
        damage_branch = expected[start:end]
        anchor = '\t$attack_end' if original == 'spell_attack' else '\nend'
        pos = actual.index(anchor) if original == 'spell_attack' else actual.rindex(anchor)
        actual = actual[:pos] + damage_branch + actual[pos:]
        stock_equal(actual, expected, 'blocked spell lifecycle: ' + private)
    names = ('Energy_Blast_Hit', 'Power_Shock_Hit', 'Acid_Bolt_Hit',
             'Electrical_Fury_Hit', 'Spire_Blast_Hit', 'Ixmil_Blast_Hit',
             'Insect_Swarm_Hit', 'horrify_hit', 'Pestilence_missile_Hit',
             'Infectious_Cloud_Hit', 'Drain_Life_Hit', 'Life_Leach_Hit',
             'Fire_Blast_Hit', 'Fire_Hammer_Hit', 'Fire_Strike_Damage', 'Lightning_Bolt_Damage')
    for name in (*names, 'tower_blast_callback'):
        original = spells if name in names else (root / 'Buildings/mx_Tower.gpl').read_text(encoding='cp1252')
        actual = extract_function(source, name)
        require(actual.count('$Bards_Deflect_') == 1, 'Exactly one interception per impact: ' + name)
        actual = actual.replace('if ($Bards_Deflect_Spell(ThisAgent, Target)) return;', '')
        actual = actual.replace('if ($Bards_Deflect_Player(ThisAgent)) return;', '')
        actual = actual.replace('if ($Bards_Deflect_Spell(ThisAgent, Target) == FALSE)', '')
        stock_equal(actual, extract_function(original, name), 'intercepted impact: ' + name)
    declared = set(re.findall(r'(?im)^function\s+(\w+)', source))
    require(declared == set(names) | {'tower_blast_callback', 'hit', 'Bards_Deflect_Spell_Hit',
                                     'Bards_Deflect_Spell', 'Bards_Deflect_Player'},
            'Unclassified spell/AOE/periodic interception')
    fire = extract_function(source, 'Fire_Blast_Hit')
    hammer = extract_function(source, 'Fire_Hammer_Hit')
    for callback in (fire, hammer):
        require(callback.count('$Does_Resist_Fire') == 1 and
                callback.index('$Does_Resist_Fire') < callback.index('$Bards_Deflect_Spell'),
                'Fire immunity must precede Deflect with exactly one roll')
    require(hammer.index('$Bards_Deflect_Spell') < hammer.index('$CreateMissile') and
            'if ($Bards_Deflect_Spell(ThisAgent, Target)) return;' not in hammer,
            'Fire Hammer return projectile must survive Deflect')
