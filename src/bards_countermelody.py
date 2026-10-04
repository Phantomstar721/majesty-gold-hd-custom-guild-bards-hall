"""Stock validation-script wrappers for the explicitly eligible special spells."""
import copy
import re
import xml.etree.ElementTree as ET

# Basic projectiles, physical techniques, potions, items and player powers are
# intentionally absent. Names resolve from the combined stock + expansion data.
SPECIAL_SPELLS = (
    'teleport_short', 'charm_monster', 'shield_of_light', 'iron_will',
    'sun_scorch', 'camouflage', 'meditation', 'hands_of_steel',
    'animate_skeleton', 'fire_shield', 'change_shape', 'aura_of_peace',
    'monk_stone_skin', 'exploding_aura', 'fire_blast', 'force', 'teleport',
    'paralytic_gaze', 'fire_ball', 'resist_magic', 'meteor_storm', 'magic_mirror',
    'Summon_Spider', 'vortex', 'level_leach', 'summon_skeleton', 'get_healer',
    'W_K_teleport', 'flame_shield', 'inferno', 'radiate_energy', 'Gorgon_Petrify',
    'Turn_Undead_Paladin', 'Medusa_Stare', 'Medusa_Slow', 'Mind_warp',
    'Summon_Medusae', 'Terrify', 'Howl_of_Discord', 'Teleport_long',
    'Stonebacks_Shield', 'SBeast_Speed', 'Speed_Monster', 'Wendigo_Blink',
    'Pestilence', 'Damage_Shield', 'Summon_Sbeast', 'Fire_Hammer_Spell',
    'Recall', 'Turn_Undead_Healer',
)


def stock_actions(sdk):
    actions = {}
    for relative in ('Data/M_Actions.xml', 'DataMX/MX_Actions.xml'):
        for item in ET.parse(sdk / relative).getroot():
            actions[item.get('Name').lower()] = item
    return actions


def suppression_descriptions(sdk):
    stock = stock_actions(sdk)
    root = ET.Element('Majesty')
    for name in SPECIAL_SPELLS:
        item = copy.deepcopy(stock[name.lower()])
        game = item.find('Game')
        script = game.find('ValidationScript')
        if script is None:
            script = ET.SubElement(game, 'ValidationScript')
        script.set('value', 'Bards_Gate_' + item.get('ID'))
        root.append(item)
    return root


def suppression_functions(sdk, extract_function):
    stock = stock_actions(sdk)
    blocks = []
    for name in SPECIAL_SPELLS:
        item = stock[name.lower()]
        original = item.find('./Game/ValidationScript')
        fallback = '1' if original is None else '$' + original.get('value') + '(ThisAgent)'
        blocks.append(f'''function Bards_Gate_{item.get('ID')}(agent ThisAgent) is integer
declare
begin
    if ($CheckEffector(ThisAgent, "Bards_Countermelody_Icon")) return 0;
    return {fallback};
end
''')
    blocks.append('''function Bards_Special_Spell(string SpellName) is boolean
declare
begin
'''+''.join(f'    if (SpellName == "{name}") return TRUE;\n' for name in SPECIAL_SPELLS)+'''
    if (SpellName == "control_undead") return TRUE;
    if (SpellName == "Bards_Resonant_Burst") return TRUE;
    if (SpellName == "Bards_Countermelody") return TRUE;
    if (SpellName == "Bards_Valor") return TRUE;
    if (SpellName == "Bards_March") return TRUE;
    if (SpellName == "Bards_Satire") return TRUE;
    if (SpellName == "Bards_Refrain") return TRUE;
    return FALSE;
end

function Bards_Spell_Available(agent ThisAgent, string SpellName) is boolean
declare
begin
    if ($CheckEffector(ThisAgent, "Bards_Countermelody_Icon"))
        if ($Bards_Special_Spell(SpellName)) return FALSE;
    return $IsSpellAvailable(ThisAgent, SpellName);
end
''')
    # Only two-argument availability calls are cast eligibility. Three-argument
    # ignore-timeout queries also decide learning and monster threat; leave them.
    pattern = re.compile(r'\$isspellavailable\s*\(\s*(\w+)\s*,\s*("[^"]+"|\w+)\s*\)', re.I)
    eligible = {name.lower() for name in SPECIAL_SPELLS} | {'control_undead'}
    def replace_availability(match):
        name = match[2]
        if name.startswith('"') and name[1:-1].lower() not in eligible:
            return match[0]
        return f'$Bards_Spell_Available({match[1]}, {name})'
    for path in sorted((sdk / 'GPLMx').rglob('*.gpl')):
        text = path.read_text(encoding='cp1252')
        if not pattern.search(text):
            continue
        for name in re.findall(r'(?im)^function\s+(\w+)\s*\(', text):
            block = extract_function(text, name)
            if pattern.search(re.sub(r'//[^\n]*', '', block)):
                changed = pattern.sub(replace_availability, block)
                if changed != block:
                    blocks.append(changed)
    cast = extract_function((sdk / 'GPLMx/TaskModules/Subtasks/mx_Cast.gpl').read_text(encoding='cp1252'), 'Cast')
    cast = re.sub(r'(?im)^begin\s*$', lambda m: m[0] + '''
    if ($CheckEffector(ThisAgent, "Bards_Countermelody_Icon"))
        if ($Bards_Special_Spell(SpellName)) return;
''', cast, count=1)
    blocks.append(cast)
    combat = (sdk / 'GPLMx/TaskModules/Subtasks/mx_Make_Attack.gpl').read_text(encoding='cp1252')
    hit = extract_function(combat, 'spell_attack')
    hit = hit.replace('function spell_attack(agent thisagent, agent target,integer damage)',
                      'function Bards_Countermelody_Hit(agent thisagent, agent target)')
    hit = hit.replace('$spelldamage(thisagent,target,damage,1);', '$Bards_Countermelody_Apply(thisagent,target);')
    hit = re.sub(r'(?im)^begin\s*$', lambda m: m[0] +
        '\n\tif ($Bards_Countermelody_Target(ThisAgent, Target) == FALSE) return;\n', hit, count=1)
    blocks.append(hit)
    return '\n'.join(blocks)
