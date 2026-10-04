"""Execute the optional capability contract without changing hero behavior."""
import unittest

from test_hiring import GPLSubset, ROOT, agent
from bards_heroes import PROFILES, hero_data


class HeroCapabilityTests(unittest.TestCase):
    def test_role_and_potion_contract_is_read_only_and_fails_closed(self):
        vm = GPLSubset((ROOT / 'src/gpl/Bards_Hero_Capability.gpl').read_text())
        for title, combat in (('Troubadour', False), ('Spellsinger', True), ('Blade_Dancer', True)):
            hero = agent(title=title, ActiveScript='current-task', Target='current-target')
            before = dict(hero.fields)
            self.assertEqual(vm.call('Bards_Hero_Capability', hero, 'combat'), combat)
            self.assertEqual(vm.call('Bards_Hero_Capability', hero, 'weapon_oil'), title != 'Spellsinger')
            for key in ('bazaar_purchase', 'potion_healing', 'potion_speed', 'potion_strength',
                        'potion_invisibility', 'potion_regeneration', 'potion_shapechange'):
                self.assertTrue(vm.call('Bards_Hero_Capability', hero, key), (title, key))
            for key in ('', 'unknown', 'potion_fire_balm'):
                self.assertFalse(vm.call('Bards_Hero_Capability', hero, key))
            self.assertEqual(hero.fields, before)
        self.assertFalse(vm.call('Bards_Hero_Capability', agent(title='Wizard'), 'combat'))
        self.assertFalse(vm.call('Bards_Hero_Capability', agent(title='Wizard'), 'weapon_oil'))

    def test_all_profiles_use_typed_callback_without_giving_combatants_support(self):
        self.assertEqual(hero_data().count('{Bards_Support_Hero'), 3)
        for title, profile in PROFILES.items():
            fields = profile['gpl_attributes']
            self.assertEqual(fields['HeroCapability'], 'Bards_Hero_Capability')
            self.assertEqual('HeroSupportTick' in fields, title == 'Troubadour')


if __name__ == '__main__':
    unittest.main()
