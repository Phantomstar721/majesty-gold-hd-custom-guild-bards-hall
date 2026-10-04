"""Provider-owned policy and current hero effects through saved spell origins."""
import unittest
import xml.etree.ElementTree as ET
from test_hiring import ROOT, SDK, agent
from test_deflect import ImpactHarness
from build_bards_hall import extract_function
from bards_spell_policy import spell_policy_features
from majesty_cam.spell_policy import parse_feature, SpellPolicyDiscovery
from majesty_cam.spell_origin import SOURCE, parse_feature as parse_origin
from majesty_cam.source_context import parse_feature as parse_context
from validate_bards_abilities import check_dynamic_attribute_types
from bards_abilities import build_descriptions
from bards_countermelody import stock_actions


class SpellPolicyTests(unittest.TestCase):
    def test_unchanged_phantom_winter_transports_source_through_target_only_helper(self):
        from majesty_cam.gpl import parse_gpl, SemanticMergeResult
        from majesty_cam.source_context import compose
        from bards_abilities import combat_functions
        phantom = (ROOT.parent/'majesty-gold-hd-custom-guild-phantoms-haunt/src/gpl/phantom.gpl').read_text()
        root = 'Endless_Winter_Inner_Missile_Hit'
        helper = 'Endless_Winter_Missile_Hit'
        source = '\n'.join(extract_function(phantom, n) for n in (root, helper))
        source += extract_function(combat_functions(SDK, extract_function), 'player_spell_attack')
        before = SemanticMergeResult(parse_gpl(source).items, ())
        feature = next(parse_context(f) for f in spell_policy_features()
                       if f.get('target_symbol') == 'player_spell_attack')
        result = compose(before, (feature,), (root,), None)
        text = '\n'.join(i.text for i in result.items)
        self.assertEqual(extract_function(text, helper), extract_function(source, helper))
        vm = ImpactHarness(text)
        seen = []
        vm.calls.update(createeffector=lambda *_:None, getspellattribute=lambda *_:1,
                        phantom_apply_chill_tier=lambda *_:None,
                        bards_playerspellattackattributed=lambda *args:seen.append(args))
        spell, target = agent(), agent()
        vm.call(root, spell, target)
        self.assertEqual(seen, [(spell, target, 8, 8)])

    def test_central_discovery_accepts_existing_stock_and_guild_packages(self):
        from majesty_cam.spell_discovery import discover
        descriptions = {(a.get('type'), a.get('ID')): a for a in stock_actions(SDK).values()}
        for path in (SDK/'Data/M_Projectiles.xml', SDK/'DataMX/MX_Projectiles.xml'):
            descriptions.update({(a.get('type'), a.get('ID')): a for a in ET.parse(path).getroot()})
        descriptions.update({(a.get('type'), a.get('ID')): a for a in build_descriptions(SDK)})
        for project, package in (('phantoms-haunt', 'CustomGuildPhantomsHaunt'), ('alchemist', 'CustomGuildAlchemist')):
            data = ROOT.parent/('majesty-gold-hd-custom-guild-'+project)/'dist'/package/'Data'
            for path in data.glob('*.xml'):
                descriptions.update({(a.get('type'), a.get('ID')): a for a in ET.parse(path).getroot()})
        bindings = [('Bards', parse_feature(f)) for f in spell_policy_features()
                    if f['type'].startswith('stock.spell-policy-')]
        plan = discover(bindings, list(descriptions.values()))
        self.assertEqual(plan.impacts, ('Ice_Lance_Hit',))
        names = {a.name.casefold() for a in plan.actions}
        self.assertTrue({'call_to_grave', 'frost_armor', 'endless_winter'} <= names)
        self.assertFalse({'ice_lance', 'bards_flourish_strike', 'alchemist_strength_potion'} & names)

    def test_owned_declarations_preserve_basic_physical_and_area_exclusions(self):
        features = [parse_origin(f) if f['type'] == 'stock.spell-origin.v1' else
                    parse_context(f) if f['type'] == 'stock.source-context-dispatch.v1' else parse_feature(f)
                    for f in spell_policy_features()]
        policy = next(f for f in features if isinstance(f, SpellPolicyDiscovery))
        self.assertIn('ice_lance', policy.suppression_exempt_actions)
        self.assertIn('Bards_Flourish_Strike', policy.suppression_exempt_actions)
        self.assertIn('Ice_Lance_Hit', policy.direct_projectile_callbacks)
        self.assertIn('Endless_Winter_Inner_Missile_Hit', policy.area_or_periodic_projectile_callbacks)
        self.assertIn('call_to_grave', policy.suppression_special_actions)

    def test_refrain_tracks_individual_hero_and_child_effects(self):
        check_dynamic_attribute_types(SOURCE, 'Manager spell-origin service')
        program = SOURCE + extract_function((ROOT/'src/gpl/Bards_Effects.gpl').read_text(), 'Bards_Refrain_Bonus')
        vm = ImpactHarness(program)
        hero = agent(type='Invisible', subtype='hero', buff=True)
        other = agent(type='hero', subtype='hero', buff=False)
        spell = agent(type='spell')
        child = agent(type='spell')
        sovereign = agent(type='spell')
        vm.calls['checkeffector'] = lambda h, name: h.fields.get('buff', False)
        self.assertEqual(vm.call('MM_SO_Record', spell, hero), 1)
        self.assertEqual(vm.call('MM_SO_Record', child, spell), 1)
        self.assertEqual(vm.call('Bards_Refrain_Bonus', child), 3)
        self.assertEqual(vm.call('Bards_Refrain_Bonus', other), 0)
        self.assertEqual(vm.call('Bards_Refrain_Bonus', sovereign), 0)
        nonhero = agent(type='Building', subtype='guild', buff=True)
        foreign_origin = agent(type='spell', MM_SpellOrigin_v1=nonhero)
        missing_subtype = agent(type='Building', buff=True)
        missing_origin = agent(type='spell', MM_SpellOrigin_v1=missing_subtype)
        self.assertEqual(vm.call('Bards_Refrain_Bonus', foreign_origin), 0)
        self.assertEqual(vm.call('Bards_Refrain_Bonus', missing_origin), 0)
        hero['buff'] = False
        self.assertEqual(vm.call('Bards_Refrain_Bonus', child), 0)
        hero.alive = False
        self.assertEqual(vm.call('Bards_Refrain_Bonus', child), 0)

    def test_silence_provider_is_read_only_and_uses_current_effect(self):
        source = (ROOT/'src/gpl/Bards_Spell_Policy.gpl').read_text()
        vm = ImpactHarness(source)
        hero = agent(silenced=True)
        before = dict(hero.fields)
        vm.calls['checkeffector'] = lambda h, _: h['silenced']
        for _ in range(3):
            self.assertTrue(vm.call('Bards_Suppress_Special', hero, 'call_to_grave'))
        self.assertEqual(hero.fields, before)
        hero['silenced'] = False
        self.assertFalse(vm.call('Bards_Suppress_Special', hero, 'call_to_grave'))


if __name__ == '__main__': unittest.main()
