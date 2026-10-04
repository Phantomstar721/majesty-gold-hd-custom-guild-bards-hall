"""Completed-stage capacity at the two literal stock building callbacks."""
from pathlib import Path
import re
import struct

CAPACITY_BY_LEVEL = {1: 4, 2: 6, 3: 8}
CAPACITY_PROPERTY = 'BardsCompletedCapacity'
GUILD_PROTOTYPE = 'Bards_Hall_Prototype'


def stock_guild_prototype(sdk: Path) -> str:
    source = (sdk / 'GPLMx/mx_prototype.gpl').read_text(encoding='cp1252')
    matches = list(re.finditer(r'(?ims)^prototype Guild\(\).*?^end\b', source))
    if len(matches) != 1:
        raise ValueError('Stock Guild prototype boundary changed')
    return matches[0].group() + '\n'


def guild_prototype(sdk: Path) -> str:
    source = stock_guild_prototype(sdk)
    source = _replace_once(source, 'prototype Guild()', f'prototype {GUILD_PROTOTYPE}()')
    return _replace_once(source, '\nbegin\n', f'\n\tinteger {CAPACITY_PROPERTY};\n\nbegin\n')


def validate_compiled_capacity(package, data_block, require):
    """Check the compiler's typed prototype record and DAT constructor records.

    This is deliberately bounded to our literal default-only Guild clone, not
    a generic BCD parser. Record sizes/versions/terminators are checked before
    interpreting its fields; a changed compiler layout fails closed.
    """
    binary = (package / 'Data/Bards.bcd').read_bytes()
    prototype = (package / 'GPL/Bards_Hall_Prototype.gpl').read_text()
    templates = (package / 'GPL/Bards_Building_Data.dat').read_text()
    declarations = re.findall(r'(?im)^\s*(string|integer|function|boolean|list)\s+(\w+)\s*;',
                              re.sub(r'//[^\n]*', '', prototype))
    kinds = {'integer': 1, 'string': 3, 'list': 4, 'boolean': 6, 'function': 8}
    expected = b''.join(struct.pack('<5I', 20, 1, kinds[k.lower()], 0, 0xffffffff)
                        for k, _ in declarations)
    size = 20 + len(expected) + 12
    record = (GUILD_PROTOTYPE.encode() + b'\0' + struct.pack('<5I', size, 1, 11, 0, len(declarations))
              + expected + struct.pack('<3I', 0, 0, 0xffffffff))
    require(binary.count(record) == 1, 'Compiled private Guild prototype lacks its exact typed field layout')
    require(declarations[-1] == ('integer', CAPACITY_PROPERTY), 'Capacity must be the appended integer field')

    for level, capacity in CAPACITY_BY_LEVEL.items():
        name = f'Bards_Hall{level}'
        marker = name.encode() + b'\0'
        require(binary.count(marker) == 1, 'Ambiguous compiled Bards template record')
        start = binary.index(marker) + len(marker)
        size, version = struct.unpack_from('<II', binary, start)
        require(version == 1 and start + size <= len(binary), 'Invalid compiled DAT record header')
        cursor = start + 8
        def string():
            nonlocal cursor
            end = binary.index(0, cursor, start + size)
            value = binary[cursor:end].decode('cp1252')
            cursor = end + 1
            return value
        require(string() == GUILD_PROTOTYPE, 'Compiled Bards template selects an undeclared-field prototype')
        count = struct.unpack_from('<I', binary, cursor)[0]
        cursor += 4
        require(0 < count <= len(declarations), 'Invalid compiled template field count')
        values = {}
        for _ in range(count):
            key, value = string(), string()
            require(key.casefold() not in values, 'Duplicate compiled template assignment')
            values[key.casefold()] = value
        require(cursor + 8 == start + size and binary[cursor:cursor+8] == struct.pack('<2I', 0, 0xffffffff),
                'Compiled template framing changed')
        authored = dict((k.casefold(), v) for k, v in re.findall(r'\((\w+)\s+([^\s()]+)\)', data_block(templates, name)))
        require(values == authored and values[CAPACITY_PROPERTY.casefold()] == str(capacity),
                'Compiled capacity template differs from declared source')

# The native Description advances at upgrade start; the saved GPL template
# advances only at UpgradeAgentAttributes in the stock completion branch.
START_INSERTION = '''\tif (ThisAgent's "title" == "Bards_Hall")
        if ($HasAttribute("BardsCompletedCapacity", ThisAgent))
            begin
                BardsRoot = $RetrieveAgent("GPLAIRoot");
                if (BardsRoot's "Quest_Number" == #QNumber_Legendary_Heroes)
                    $SetAttribute(ThisAgent, #ATTRIB_MaxGuildMembers, 1);
                else
                    $SetAttribute(ThisAgent, #ATTRIB_MaxGuildMembers, ThisAgent's "BardsCompletedCapacity");
            end

'''

COMPLETE_INSERTION = '''
                if (theBuilding's "title" == "Bards_Hall")
                    if ($HasAttribute("BardsCompletedCapacity", theBuilding))
                        $SetAttribute(theBuilding, #ATTRIB_MaxGuildMembers, theBuilding's "BardsCompletedCapacity");
'''


def _replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Stock guild progression boundary changed: ' + old.strip())
    return source.replace(old, new, 1)


def progression_functions(sdk: Path, extract_function) -> str:
    source = (sdk / 'GPLMx/mx_Building_Births.gpl').read_text(encoding='cp1252')
    start = extract_function(source, 'building_upgraded')
    start = _replace_once(start, 'declare\n', 'declare\n\tagent BardsRoot;\n')
    dispatch = '\t$runthread ( thisagent\'s "upgradescript", 1, thisagent );'
    start = _replace_once(start, dispatch, START_INSERTION + dispatch)
    complete = extract_function(source, 'BuildingReachedMaxHP')
    advance = '\t\t\t\t$UpgradeAgentAttributes ( theBuilding );'
    complete = _replace_once(complete, advance, advance + COMPLETE_INSERTION)
    return start + '\n' + complete


def validate_progression(sdk, package, extract_function, data_block, stock_equal, require):
    """Remove only the two audited insertions, then compare to full stock bodies."""
    source = (sdk / 'GPLMx/mx_Building_Births.gpl').read_text(encoding='cp1252')
    generated = (package / 'GPL/Bards_Hall_Progression_Stock.gpl').read_text()
    start = extract_function(generated, 'building_upgraded')
    start = _replace_once(start, START_INSERTION, '')
    start = _replace_once(start, 'declare\n\tagent BardsRoot;\n', 'declare\n')
    stock_equal(start, extract_function(source, 'building_upgraded'), 'synchronous upgrade dispatch')
    complete = extract_function(generated, 'BuildingReachedMaxHP')
    advance = '\t\t\t\t$UpgradeAgentAttributes ( theBuilding );'
    require(advance + COMPLETE_INSERTION in complete, 'Capacity must follow stock template completion')
    complete = _replace_once(complete, COMPLETE_INSERTION, '')
    stock_equal(complete, extract_function(source, 'BuildingReachedMaxHP'), 'construction/repair completion')
    templates = (package / 'GPL/Bards_Building_Data.dat').read_text()
    prototype = (package / 'GPL/Bards_Hall_Prototype.gpl').read_text()
    stripped = _replace_once(prototype, f'\n\tinteger {CAPACITY_PROPERTY};\n', '')
    stripped = _replace_once(stripped, f'prototype {GUILD_PROTOTYPE}()', 'prototype Guild()')
    stock_equal(stripped, stock_guild_prototype(sdk), 'Guild prototype fields/types/order and lifecycle')
    for level, capacity in CAPACITY_BY_LEVEL.items():
        block = data_block(templates, f'Bards_Hall{level}')
        require(re.search(r'\{\s*' + GUILD_PROTOTYPE + r'\b', block) is not None,
                'Bards template must instantiate its typed private Guild prototype')
        require(block.count(f'({CAPACITY_PROPERTY} {capacity})') == 1,
                'Completed-stage template capacity differs from XML author values')
