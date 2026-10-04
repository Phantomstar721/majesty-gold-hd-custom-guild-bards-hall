"""Stock-shaped resources for stock.ap52-recruitment-panel.v1.

Manager owns child navigation, input, visibility and the native recruit queue.
"""
from __future__ import annotations

import struct
from pathlib import Path

from bards_hiring_panel import add_hiring_row, manager_feature as hiring_feature
from bards_panel import THIRD_PRICE_CONTROL, control_index, field, geometry, records
from bards_chronicles_panel import add_research_row, manager_feature as chronicles_feature
from cam_io import Entry, Section, append_strings, get, name, read, write

OPEN_RECRUIT = 0x7302
CHILD_DIALOG = b'BDRC'
COUNT_FRAMES = ((0x7310, 17), (0x7311, 77), (0x7312, 137))
ROWS = (
    # Actual loaded Produces order was established by Manager's live trace.
    # Visual order: Troubadour, Spellsinger, Blade Dancer.
    (0x1388, THIRD_PRICE_CONTROL, 4, 5, ord('T'), 64),
    (0x1389, 0x1F51, 12, 13, ord('S'), 96),
    (0x1F48, 0x1752, 0, 1, ord('D'), 128),
)


def _get(menu, control):
    return menu[control_index(menu, control)]


def _put(menu, control, record):
    menu[control_index(menu, control)] = record


def _move(menu, control, x, y, width=None, height=None):
    _put(menu, control, geometry(_get(menu, control), x, y, width, height))


def _upgrade_group(ap53):
    source, indexed, cursor = records(ap53), {}, 0
    for item in source:
        indexed[cursor] = item
        cursor += len(item)
    output = []
    for offset, texts in ((0x8B0, {}), (0x904, {22: 47}),
                           (0x984, {23: 48, 24: 49}),
                           (0xA00, {25: 50, 26: 51}), (0xA98, {27: 52})):
        item = indexed[offset]
        for old, new in texts.items():
            item = field(item, 0x21 if old in (24, 26) else 7, old, new)
        output.append(item)
    return output


def main_panel(ap52, ap53, ap10):
    menu = records(ap52)
    temple = records(ap10)
    # AP52's single-hero counter has a separate INBg/1002 gold frame. Keep
    # its exact static widget and native art; private IDs prevent stock
    # alternate-recruitment visibility from hiding these three decorations.
    count_frame = _get(menu, 3)
    # Main guild keeps literal stock top controls, HP/coffers and frame. Move
    # only recruitment/alternate decorations offscreen for native constructor
    # compatibility; Manager must suppress their parent input/presentation.
    for control in (0x1F48, 0x1389, 0x1388, 0x1752, 0x1F51, 0x1F56, 0x1F57,
                    0x22CE, 0x1F49, 0x1181, 0x1F18, 0x1F0E,
                    0x1F11, 0x1F12, 0x1F13, 0x1F14, 3):
        _move(menu, control, 1500, 1500)
    # Move the whole border with its contents. Portraits use the three-pixel
    # vertical inset of the stock counter, not an independent visual offset.
    # Keep the stock 46x35 frame and 11x27 count rectangle unscaled.
    first_icon = min(control_index(menu, control) for control in (0x1F1A, 0x1F52, 0x1F19))
    menu[first_icon:first_icon] = [geometry(field(count_frame, 6, 3, control), x, 162)
                                  for control, x in COUNT_FRAMES]
    for icon, count, x in ((0x1F1A, 0x1F1C, 22), (0x1F52, 0x1F0D, 82),
                            (0x1F19, 0x1F1B, 142)):
        _move(menu, icon, x, 165)
        _move(menu, count, x + 28, 164, 11, 27)
    trou, dancer = (struct.unpack('<I', x)[0] for x in (b'BDT1', b'BDD1'))
    _put(menu, 0x1F19, field(field(_get(menu, 0x1F19), 12, trou, dancer), 0x21, 27, 26))
    _put(menu, 0x1F1A, field(field(_get(menu, 0x1F1A), 12, dancer, trou), 0x21, 26, 27))
    _put(menu, 0x1F1B, field(_get(menu, 0x1F1B), 0x21, 31, 29))
    _put(menu, 0x1F1C, field(_get(menu, 0x1F1C), 0x21, 29, 31))

    # Literal 93x26 AP10 action controls. Only the new command opens the child;
    # the existing Heroes command continues to open the stock guild roster.
    _move(menu, 0x1F44, 7, 196)
    opener = _get(temple, 0x1F49)
    for tag, old, new in ((6, 0x1F49, OPEN_RECRUIT), (7, 29, 53), (0x21, 30, 54),
                          (5, ord('S'), ord('R')), (0x102, ord('Z'), ord('R')),
                          (0x10A, ord('C'), ord('R')), (13, 1009, 1004)):
        opener = field(opener, tag, old, new)
    menu.insert(-1, geometry(opener, 103, 196))
    # The third quote is kept only as a hidden constructor-compatible binding.
    quote = field(_get(menu, 0x1F51), 6, 0x1F51, THIRD_PRICE_CONTROL)
    menu.insert(-1, quote)
    menu[-1:-1] = _upgrade_group(ap53)
    return b''.join(menu)


def recruitment_panel(ap52, ap53, ap69):
    menu, secondary = records(ap52), records(ap69)
    # Keep every original AP52 control addressable, but use the literal stock
    # AP69 secondary shell. No portrait, health, tax or upgrade UI in the child.
    for index in range(1, len(menu) - 1):
        menu[index] = geometry(menu[index], 1500, 1500)
    # Stock generic secondary frame has no Fervus emblem or baked spell rows.
    _put(menu, 1, field(_get(secondary, 1), 13, 1026, 1024))
    _put(menu, 0x1F45, field(_get(secondary, 0x1F45), 7, 0, 6))
    for control in (0x1F40, 0x1F41):
        _put(menu, control, _get(records(ap52), control))
    heading = field(field(_get(secondary, 2), 7, 13, 55), 6, 2, 0x7303)
    back = field(_get(secondary, 0x1F4D), 0x21, 12, 56)
    menu[-1:-1] = [heading, back]

    original = records(ap52)
    template = _get(original, 0x1389)  # stock full-width 189x27 recruit button
    # AP52's Paladin/Discord recruitment buttons already use fnt7 for long
    # captions. Keep the native RECRUIT + unit-name formatter, but copy that
    # stock font so all three private names fit left of the inside quote.
    small_font = struct.unpack('<I', b'fnt7')[0]
    stock_font = struct.unpack('<I', b'fnt4')[0]
    assert struct.pack('<II', 0x12, small_font) in _get(original, 0x1388)
    template = field(template, 0x12, stock_font, small_font)
    quote = _get(original, 0x1F51)    # stock right-aligned quote inside button
    for command, price, label, tooltip, key, y in ROWS:
        button = template
        for tag, old, new in ((6, 0x1389, command), (7, 12, label), (0x21, 13, tooltip),
                              (5, ord('R'), key), (0x102, ord('A'), key),
                              (0x10A, ord('Z'), key)):
            button = field(button, tag, old, new)
        _put(menu, command, geometry(button, 7, y))
        price_record = geometry(field(quote, 6, 0x1F51, price), 155, y + 4)
        if price == THIRD_PRICE_CONTROL:
            menu.insert(-1, price_record)
        else:
            _put(menu, price, price_record)
    _move(menu, 0x1F56, 7, 160)
    _move(menu, 0x1F57, 10, 164)
    menu[-1:-1] = [geometry(item, 1500, 1500) for item in _upgrade_group(ap53)]
    return b''.join(menu)


def panel_resources(stock, ap52, labels):
    labels = append_strings(labels, {struct.pack('<I', i): text for i, text in {
        53: 'RECRUIT', 54: 'Choose a bard to recruit.', 55: 'RECRUIT HEROES',
        56: "Return to this building's Main Window.",
    }.items()})
    main = main_panel(ap52, get(stock, b'SMNU', b'AP53'), get(stock, b'SMNU', b'AP10'))
    child = recruitment_panel(ap52, get(stock, b'SMNU', b'AP53'), get(stock, b'SMNU', b'AP69'))
    main, labels = add_research_row(stock, main, labels)
    child, labels = add_hiring_row(child, labels)
    return main, child, labels


def build_candidate(game: Path, output: Path):
    """Build a review-only CAM with the same resources as the runtime package."""
    from build_bards_hall import private_panel_resources
    stock = read(game / 'Data/textdata.cam')
    main, child, labels = panel_resources(stock, *private_panel_resources(stock))
    write(output, (
        Section(b'SMNU', bytes(4), (Entry(name(b'CGBD'), main), Entry(name(CHILD_DIALOG), child))),
        Section(b'STRT', bytes(4), (Entry(name(b'CGBD'), labels), Entry(name(CHILD_DIALOG), labels))),
    ))


def manager_features():
    return [
        chronicles_feature(),
        hiring_feature(),
        *({'type': 'stock.typed-boolean-provider.v1', 'feature_key': key,
           'attribute': attribute, 'parameter_types': parameters, 'callback_symbol': callback}
          for key, attribute, parameters, callback in (
              ('capability_provider', 'HeroCapability', ['agent', 'string'], 'Bards_Hero_Capability'),
              ('support_eligible_provider', 'HeroSupportEligible', ['agent', 'agent'], 'Bards_Hall_Support_Eligible'),
              ('support_tick_provider', 'HeroSupportTick', ['agent', 'agent'], 'Bards_Hall_Support_Tick'))),
        *({'type': 'stock.gameplay-event-observer.v1', 'feature_key': key,
           'event': event, 'callback_symbol': callback}
          for key, event, callback in (
              ('support-combat-xp', 'combat-experience-awarded', 'Bards_CombatXP'),
              ('support-exploration-xp', 'exploration-experience-awarded', 'Bards_ExplorationXP'))),
        {'type': 'stock.ap52-recruitment-panel.v1', 'panel_key': 'bards_recruitment',
         'parent_building': 'Bards_Hall', 'third_price_control_id': THIRD_PRICE_CONTROL,
         'source_dialog_id': CHILD_DIALOG.decode(), 'open_command_id': OPEN_RECRUIT},
        *({'type': 'stock.hero-quest-participant.v1', 'feature_key': key + '-quests',
           'hero_script': 'Bards_' + title + '_Tree', 'stock_hero_script': stock}
          for key, title, stock in (('troubadour', 'Troubadour', 'mx_healer'),
                                    ('spellsinger', 'Spellsinger', 'mx_cultist'),
                                    ('blade-dancer', 'Blade_Dancer', 'mx_ranger'))),
        *({'type': 'stock.spell-evaluation-equivalent.v1', 'feature_key': key,
           'private_spell': private, 'stock_spell': stock, 'hero_title': 'Spellsinger'}
          for key, private, stock in (('arcane-note-evaluation', 'Bards_Arcane_Note', 'energy_blast'),
                                      ('resonant-burst-evaluation', 'Bards_Resonant_Burst', 'sun_scorch'))),
    ]
