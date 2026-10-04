"""Saved March modifiers must expire before the replacement overlay can scale."""
import re
import unittest

from test_hiring import ROOT, SDK, GPLSubset, agent
from build_bards_hall import extract_function
from bards_abilities import build_descriptions


class MarchMigrationTests(unittest.TestCase):
    def runtime(self):
        rates = (ROOT / 'src/gpl/Bards_Rates.gpl').read_text()
        songs = (ROOT / 'src/gpl/Bards_Songs.gpl').read_text()
        source = '\n'.join(extract_function(rates, key) for key in
                           ('Bards_March_Apply', 'Bards_March_End'))
        source += extract_function(songs, 'Bards_Song_Refresh')
        vm = GPLSubset(re.sub(r'#(\w+)', r'"\1"', source))
        hero = agent(ATTRIB_MovementRateModifier=-50, ATTRIB_ActionRateModifier=-200)
        caster = agent()
        effects, events = set(), []

        def create(target, effect, duration):
            self.assertIs(target, hero)
            effects.add(effect)
            events.append((effect, duration))

        vm.calls.update({
            'checkeffector': lambda _, effect: effect in effects,
            'createeffector': create,
            'bards_primary_action': lambda _: 'basic_attack',
            'mm_actionbaseperiod': lambda _: 1200,
            # The branch harness does not implement GPL float locals. Model
            # only this unchanged native float-to-integer conversion; this
            # suite exercises migration/ownership, not native timing math.
            'bards_rate_delta': lambda base, percent, divisor: int(base * percent / divisor) if base > 0 else 0,
            'mm_effectorremaining': lambda *_: 0,
            'adjustattribute': lambda h, key, delta: h.fields.__setitem__(key, h.fields.get(key, 0) + delta),
        })
        return vm, hero, caster, effects, events

    def test_saved_legacy_effect_blocks_new_cast_until_ordinary_cleanup(self):
        vm, hero, caster, effects, events = self.runtime()
        effects.add('Bards_March_Legacy_Icon')
        hero.fields.update(BardsMarchMoveDelta=9, BardsMarchActionDelta=109,
                           BardsMarchSource=caster, ATTRIB_MovementRateModifier=-59,
                           ATTRIB_ActionRateModifier=-309)
        self.assertFalse(vm.call('Bards_Song_Refresh', hero, 'Bards_March_Icon'))
        vm.call('Bards_March_Apply', caster, hero)
        self.assertEqual(events, [])
        self.assertEqual(hero['ATTRIB_MovementRateModifier'], -59)
        effects.remove('Bards_March_Legacy_Icon')
        vm.call('Bards_March_End', hero)
        self.assertEqual(hero['ATTRIB_MovementRateModifier'], -50)
        self.assertEqual(hero['ATTRIB_ActionRateModifier'], -200)
        self.assertTrue(vm.call('Bards_Song_Refresh', hero, 'Bards_March_Icon'))
        vm.call('Bards_March_Apply', caster, hero)
        self.assertIn('Bards_March_Icon', effects)
        self.assertEqual(hero['BardsMarchMoveDelta'], 0)
        self.assertEqual(hero['ATTRIB_MovementRateModifier'], -50)
        self.assertEqual(hero['ATTRIB_ActionRateModifier'], -309)

    def test_refresh_and_expiry_preserve_other_modifiers(self):
        vm, hero, caster, effects, _ = self.runtime()
        vm.call('Bards_March_Apply', caster, hero)
        vm.call('Bards_March_Apply', caster, hero)
        self.assertEqual(hero['ATTRIB_ActionRateModifier'], -309)
        effects.remove('Bards_March_Icon')
        vm.call('Bards_March_End', hero)
        self.assertEqual(hero['ATTRIB_MovementRateModifier'], -50)
        self.assertEqual(hero['ATTRIB_ActionRateModifier'], -200)
        self.assertEqual(hero['BardsMarchMoveDelta'], 0)
        self.assertIsNone(hero['BardsMarchSource'])

    def test_saved_description_keeps_original_callback_and_new_identity_is_distinct(self):
        descriptions = {d.get('ID'): d for d in build_descriptions(SDK)}
        self.assertEqual(descriptions['BME1'].get('Name'), 'Bards_March_Legacy_Icon')
        self.assertEqual(descriptions['BME2'].get('Name'), 'Bards_March_Icon')
        for ident in ('BME1', 'BME2'):
            self.assertEqual(descriptions[ident].find('./Engine/Script').get('GPLFunction'), 'Bards_March_End')

    def test_movement_only_recipient_still_gets_overlay_without_action_base(self):
        vm, hero, caster, effects, _ = self.runtime()
        vm.calls['mm_actionbaseperiod'] = lambda _: 0
        vm.call('Bards_March_Apply', caster, hero)
        self.assertIn('Bards_March_Icon', effects)
        self.assertEqual(hero['BardsMarchMoveDelta'], 0)
        self.assertEqual(hero['BardsMarchActionDelta'], 0)
        self.assertEqual(hero['ATTRIB_MovementRateModifier'], -50)
        self.assertEqual(hero['ATTRIB_ActionRateModifier'], -200)


if __name__ == '__main__':
    unittest.main()
