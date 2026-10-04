"""Approved per-hero Bazaar declarations; Manager owns stock effect lifecycle."""

def bazaar_features() -> list[dict]:
    return [
        {
            'type': 'stock.bazaar-potion-policy.v1',
            'feature_key': 'bards-bazaar-' + title.lower().replace('_', '-'),
            'hero_title': title,
            'potions': {
                'speed': True, 'fire-balm': False, 'strength': title == 'Blade_Dancer',
                'regeneration': True, 'invisibility': True, 'shapeshift': True,
            },
            'shapeshift': {'preset': 'minotaur' if title == 'Blade_Dancer' else 'medusa'},
            'private_actions': {},
        }
        for title in ('Troubadour', 'Spellsinger', 'Blade_Dancer')
    ]
