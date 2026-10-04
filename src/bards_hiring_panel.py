"""Literal stock MX22 paired buttons, privately labelled for bard hiring."""
import struct
from bards_panel import records, field, geometry
from cam_io import append_strings

CLOSE_HIRING = 0x7340
OPEN_HIRING = 0x7341
# MX22/0x22AC, inspected in DataMX/mx_textdata.cam. No custom artwork.
STOCK_CLOSE = (0,2,7,219,139,21,7,0,33,1,10,2,12,1648512585,13,1005,
               20,4,3,2,3,1024,5,67,6,8876,18,930377318,36,3,
               2147483711,1073741824,1073741824,4294967295)


def add_hiring_row(child, labels):
    menu = records(child)
    template = struct.pack('<'+'I'*len(STOCK_CLOSE), *STOCK_CLOSE)
    for command, caption, tooltip, hotkey in (
            (CLOSE_HIRING,61,62,ord('O')), (OPEN_HIRING,63,64,ord('C'))):
        row = template
        for tag, old, new in ((6,0x22AC,command),(7,0,caption),(0x21,1,tooltip),(5,67,hotkey)):
            row = field(row,tag,old,new)
        menu.insert(-1,geometry(row,7,194))
    labels = append_strings(labels, {struct.pack('<I',k):v for k,v in {
        61:'Hiring: Open',62:'Close hiring at this guild. Existing hired bards finish their contracts.',
        63:'Hiring: Closed',64:'Open hiring at this guild. Heroes may hire an available bard.',
    }.items()})
    return b''.join(menu), labels


def manager_feature():
    return dict(type='stock.mx22-building-open-toggle.v3', toggle_key='hiring',
                parent_building='Bards_Hall', panel_key='bards_recruitment',
                open_command_id=CLOSE_HIRING, close_command_id=OPEN_HIRING,
                state_attribute='BardsHiringClosed', state_callback_symbol='Bards_Hiring_Closed')
