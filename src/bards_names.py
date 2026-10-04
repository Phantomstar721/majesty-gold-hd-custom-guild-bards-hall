"""Private tables consumed by Majesty's existing native name generator."""
import struct

from cam_io import Entry, append_strings, get, name

SHARED = ('Robin', 'Rowan', 'Linden', 'Ash', 'Wren', 'Sage', 'Morgan', 'Riley', 'Vesper')
POOLS = {
    'Troubadour': (
        'NMBT', ('HNT0', 'HNT1', 'HNT2', 'HNT3'),
        ('Alaric', 'Benedict', 'Cedric', 'Corin', 'Dorian', 'Edric', 'Emrys',
         'Felix', 'Finnian', 'Gareth', 'Hugh', 'Jasper', 'Julian', 'Leander',
         'Lucian', 'Merrick', 'Oliver', 'Orin', 'Peregrin', 'Quentin',
         'Roderic', 'Silas', 'Tobias', 'Tristan'),
        ('Echowood', 'Goodfellow', 'Hearthsong', 'Longstride',
         'Merryweather', 'Silverstring', 'Sweetwater', 'Trueheart',
         'Wanderwell', 'Willowharp', 'the Balladeer', 'the Cheerful',
         'the Farwanderer', 'the Golden', 'the Kindly', 'the Merry',
         'the Minstrel', 'the Rambling', 'the Warmhearted', 'the Storyteller',
         'the Wayfarer', 'the Well-Traveled')),
    'Spellsinger': (
        'NMBS', ('HNS0', 'HNS1', 'HNS2', 'HNS3'),
        ('Aurel', 'Bastian', 'Caelan', 'Cassian', 'Cyril', 'Darian', 'Elias',
         'Evander', 'Florian', 'Galen', 'Hadrian', 'Ilarion', 'Aldren',
         'Lorian', 'Lysander', 'Marius', 'Oren', 'Orpheus', 'Osric',
         'Ronan', 'Sorrel', 'Theron', 'Valerian', 'Lucan'),
        ('Chimeweaver', 'Brightchime', 'Clearvoice', 'Dawnsong', 'Goldentongue', 'Brightvoice', 'Songweaver',
         'Embervoice', 'Glasschime', 'Moonsong', 'Runevoice', 'Silvertone',
         'Starcall', 'Stormchord', 'the Chanter', 'the Clear', 'the Echoing',
         'the Harmonic', 'the Melodious', 'the Resonant', 'the Ringing',
         'the Stirring', 'the Sonorous', 'the Splendid', 'the Tuneful',
         'the Thunderous')),
    'Blade_Dancer': (
        'NMBD', ('HND0', 'HND1', 'HND2', 'HND3'),
        ('Adela', 'Alessia', 'Camilla', 'Celeste', 'Claudia', 'Coralie',
         'Dahlia', 'Elena', 'Estelle', 'Fiora', 'Giselle', 'Helena', 'Isadora',
         'Juliette', 'Livia', 'Lucille', 'Mirabel', 'Nerissa', 'Odette',
         'Rosalind', 'Sabine', 'Serena', 'Valeria', 'Viola'),
        ('Brightblade', 'Featherstep', 'Fleetfoot', 'Quickblade', 'Lightfoot',
         'Roseblade', 'Silkstep', 'Silverheel', 'Starstep', 'Swiftstep',
         'Velvetblade', 'Windstep', 'the Audacious', 'the Bold', 'the Daring',
         'the Dazzling', 'the Elegant', 'the Graceful', 'the Nimble',
         'the Peerless', 'the Poised', 'the Gallant', 'the Spirited', 'the Unbowed')),
}


def features():
    return [dict(type='stock.name-generator.v1', generator_id=generator,
                 name_tables=list(tables))
            for generator, tables, _, _ in POOLS.values()]


def name_tables(stock):
    # Preserve stock STRT version and zero-based integer keys. Two unused
    # components stay empty, as in the stock two-part hero generators.
    empty = b'\0\0' + get(stock, b'STRT', b'HN01')[2:4]
    result = []
    for _, tables, given, endings in POOLS.values():
        for table, strings in zip(tables, (given + SHARED,
                                          tuple(' ' + s for s in endings), (), ())):
            result.append(Entry(name(table.encode()), append_strings(
                empty, {struct.pack('<I', i): text for i, text in enumerate(strings)})))
    return result
