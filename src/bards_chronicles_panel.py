"""Epic Chronicles content and stock resources for Manager's research contract."""
import json
import struct
from pathlib import Path

from bards_panel import control_index, field, geometry, records
from cam_io import append_strings, get

CONTENT = json.loads(Path(__file__).with_name('epic_chronicles_content.json').read_text())
ACTION = 0x7320
PROGRESS = 0x7321
ACTIVE = 0x7322
PRICE = ACTION + 1000
ICON = ACTION + 500


def manager_feature():
    """Stable author declaration; Manager owns payment, saved state and bonuses."""
    return {
        'type': 'manager.kingdom-research.v1',
        'feature_key': CONTENT['key'], 'parent_building': CONTENT['building_title'],
        'action_control_id': ACTION, 'descriptor_template_control_id': 0x139C,
        'required_level': CONTENT['required_guild_level'], 'price': CONTENT['research_price'],
        'gold_bonus_percent': CONTENT['gold_bonus_percent'],
        'experience_bonus_percent': CONTENT['experience_bonus_percent'],
        'progress_control_id': PROGRESS, 'active_display_control_id': ACTIVE,
        'completion_text': CONTENT['name'],
        'active_effector': 'Bards_Chronicles_Active',
    }


def add_research_row(stock, main, labels):
    """Copy AP24's compact bottom row and AP99's ordinary research icon.

    Native purchase, availability, progress and completion belong to Manager.
    This function changes only resource identities, labels and placement.
    """
    menu = records(main)
    krolm = records(get(stock, b'SMNU', b'AP24'))
    research = records(get(stock, b'SMNU', b'AP99'))
    def source(items, control):
        return items[control_index(items, control)]
    action = source(krolm, 0x1F49)
    for tag, old, new in ((6, 0x1F49, ACTION), (7, 1, 57), (0x21, 2, 58),
                          (5, ord('K'), ord('E')), (0x102, ord('K'), ord('E')),
                          (0x10A, ord('G'), ord('E'))):
        action = field(action, tag, old, new)
    price = source(krolm, 0x1184)
    for tag, old, new in ((6, 0x1184, PRICE), (7, 26, 59), (0x21, 27, 58)):
        price = field(price, tag, old, new)
    progress = field(source(krolm, 0x2009), 6, 0x2009, PROGRESS)
    active = field(field(source(krolm, 0x227A), 6, 0x227A, ACTIVE), 7, 28, 60)
    icon = field(source(research, 0x157C), 6, 0x157C, ICON)
    menu[-1:-1] = [geometry(action, 7, 223), geometry(price, 112, 225),
                   geometry(progress, 7, 223), geometry(active, 8, 226),
                   geometry(icon, 1500, 1500)]
    labels = append_strings(labels, {struct.pack('<I', key): text for key, text in {
        57: CONTENT['name'], 58: CONTENT['research_description'],
        59: str(CONTENT['research_price']), 60: CONTENT['name'],
    }.items()})
    return b''.join(menu), labels
