"""Stock-relative checks for spell gating and performance lifecycle ownership."""
import copy
import re
import xml.etree.ElementTree as ET
from bards_countermelody import SPECIAL_SPELLS, stock_actions


def shape(element):
    return element.tag, element.attrib, [shape(child) for child in element]


def check_spellsinger(sdk, package, extract_function, stock_equal, require):
    gpl = package / 'GPL'
    source = (gpl / 'Bards_Countermelody_Stock.gpl').read_text()
    stock = stock_actions(sdk)
    gates = ET.parse(package / 'Data/bards_spell_gates.xml').getroot()
    require({d.get('Name').lower() for d in gates} == {name.lower() for name in SPECIAL_SPELLS},
            'Special spell eligibility catalog changed')
    require(len(gates) == len(SPECIAL_SPELLS), 'Duplicate special spell gate')
    for item in gates:
        original = stock[item.get('Name').lower()]
        actual = copy.deepcopy(item)
        script = actual.find('./Game/ValidationScript')
        prior = original.find('./Game/ValidationScript')
        callback = 'Bards_Gate_' + item.get('ID')
        require(script.get('value') == callback, 'Incorrect spell validation wrapper')
        if prior is None:
            actual.find('Game').remove(script)
            expected = '1'
        else:
            script.attrib = dict(prior.attrib)
            expected = '$' + prior.get('value') + '(ThisAgent)'
        require(shape(actual) == shape(original), 'Stock action modified beyond eligibility: ' + item.get('Name'))
        block = extract_function(source, callback)
        stock_equal(block, f'''function {callback}(agent ThisAgent) is integer
declare
begin
    if ($CheckEffector(ThisAgent, "Bards_Countermelody_Icon")) return 0;
    return {expected};
end''', 'stock validation delegation ' + callback)

    originals = {}
    for path in (sdk / 'GPLMx').rglob('*.gpl'):
        body = path.read_text(encoding='cp1252')
        for name in re.findall(r'(?im)^function\s+(\w+)\s*\(', body):
            originals.setdefault(name.lower(), (body, name))
    for name in re.findall(r'(?im)^function\s+(\w+)\s*\(', source):
        if name.startswith('Bards_'):
            continue
        actual = extract_function(source, name)
        body, original_name = originals[name.lower()]
        original = extract_function(body, original_name)
        if name.lower() == 'cast':
            actual = actual.replace('if ($CheckEffector(ThisAgent, "Bards_Countermelody_Icon"))\n        if ($Bards_Special_Spell(SpellName)) return;', '')
        else:
            actual = actual.replace('$Bards_Spell_Available', '$isspellavailable')
            # GPL symbols are case-insensitive; normalize only native spelling.
            original = re.sub(r'(?i)\$isspellavailable', '$isspellavailable', original)
        stock_equal(actual, original, 'direct spell availability: ' + name)
    hit = extract_function(source, 'Bards_Countermelody_Hit')
    hit = hit.replace('function Bards_Countermelody_Hit(agent thisagent, agent target)',
                      'function spell_attack(agent thisagent, agent target,integer damage)')
    hit = hit.replace('if ($Bards_Countermelody_Target(ThisAgent, Target) == FALSE) return;', '')
    hit = hit.replace('$Bards_Countermelody_Apply(thisagent,target);', '$spelldamage(thisagent,target,damage,1);')
    stock_equal(hit, extract_function((sdk / 'GPLMx/TaskModules/Subtasks/mx_Make_Attack.gpl').read_text(encoding='cp1252'), 'spell_attack'),
                'Countermelody resistance/XP lifecycle')
    abilities = ET.parse(package / 'Data/bards_abilities.xml').getroot()
    counter = abilities.find('./Description[@Name="Bards_Countermelody"]')
    for field, expected in (('CharacterLevel', '5'), ('TimeoutDuration', '45000'), ('EffectorDuration', '8000'), ('SpellRank', '4')):
        require(counter.find('./Game/' + field).get('value') == expected, 'Countermelody ' + field)
    for name, images in (('Bards_Street_Play', 'Special'), ('Bards_Street_Attack', 'Attack'),
                         ('Bards_Street_Cast', 'Cast')):
        performance = abilities.find(f'./Description[@Name="{name}"]')
        expected = copy.deepcopy(stock['healer_heal'])
        expected.attrib = dict(performance.attrib)
        expected.find('./Engine/ImageSet').set('value', images)
        expected.find('./Engine/Script').set('GPLFunction', 'Bards_Street_Phrase')
        for child in list(expected.find('Game')):
            expected.find('Game').remove(child)
        require(shape(performance) == shape(expected),
                'Performance must preserve stock completion to Stand without combat: ' + name)
    street = (gpl / 'Bards_Street.gpl').read_text()
    # Check condition helpers transitively: no world scans, timers or state writes.
    for name in ('Bards_Street_Show_Condition', 'Bards_Street_Audience_Condition',
                 'Bards_Street_Active', 'Bards_Street_Eligible', 'Bards_Street_Listener'):
        block = re.sub(r'//[^\n]*', '', extract_function(street, name))
        require(not re.search(r'\$(?:ListObjects|list_enemies_seen|AddAttribute|AdjustAttribute|Give_?Gold|Bards_\w+_(?:Start|Cancel))\b', block, re.I),
                'Mutating/scanning activity condition: ' + name)
        require(not re.search(r"'s\s+\"[^\"]+\"\s*=(?!=)", block), 'Condition changes state: ' + name)
    baseline = (gpl / 'Bards_Baseline.gpl').read_text()
    tree = extract_function((gpl / 'Bards_Hero_Trees.gpl').read_text(), 'Bards_Spellsinger_Tree')
    require(tree.index('$Bards_Street_Check') > tree.index('$Purchase_bazaar') and
            tree.index('$Bards_Street_Check') < tree.index('$Bards_combat_wandering') and
            tree.index('$explore_map') < tree.index('$pursue_entertainment') < tree.index('$Go_home'),
            'Spectacle/combat/exploration must precede optional leisure and home')
