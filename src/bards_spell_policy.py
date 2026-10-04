"""Bards providers for opt-in foreign projectile and special-spell callbacks."""
import json
from pathlib import Path


def spell_policy_features():
    policy = json.loads(Path(__file__).with_name('spell_policy_content.json').read_text())
    discovery = {key: value for key, value in policy.items()
                 if key not in ('schema_version', 'note', 'references')}
    discovery.update(type='stock.spell-policy-discovery.v1', feature_key='bards-spell-classification')
    return [
        {'type': 'stock.spell-origin.v1', 'feature_key': 'bards-refrain-origin'},
        {'type': 'stock.source-context-dispatch.v1', 'feature_key': 'refrain_player_spell',
         'target_symbol': 'player_spell_attack', 'parameter_types': ['agent', 'integer', 'integer'],
         'callback_symbol': 'Bards_PlayerSpellAttackAttributed'},
        {'type': 'stock.source-context-dispatch.v1', 'feature_key': 'refrain_periodic_player',
         'target_symbol': 'Bards_Periodic_Player_Spell_Attack', 'parameter_types': ['agent', 'integer', 'integer'],
         'callback_symbol': 'Bards_PeriodicPlayerAttributed'},
        discovery,
        {'type': 'stock.spell-policy-provider.v1',
         'feature_key': 'bards-deflect', 'policy': 'block-direct-projectile',
         'callback_symbol': 'Bards_Deflect_Spell'},
        {'type': 'stock.spell-policy-provider.v1',
         'feature_key': 'bards-countermelody', 'policy': 'suppress-special-spell',
         'callback_symbol': 'Bards_Suppress_Special'},
    ]
