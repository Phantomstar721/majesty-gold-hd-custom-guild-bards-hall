"""Exercise the emitted spell GPL at the existing native damage boundary."""
import re
import unittest

from test_hiring import SDK, GPLSubset, agent
from build_bards_hall import extract_function
from bards_abilities import combat_functions


class DamageHarness(GPLSubset):
    def expression(self, tokens):
        # The shared sampler harness does not tokenize stock subtraction
        # assignment; preserve its integer arithmetic when executing damage.
        return super().expression(tokens).replace(' - = ', ' -= ')


class EquipmentDamageTests(unittest.TestCase):
    def resolve(self, function, quality=0, magic=0, armor=0, base=4, roused=False, refrain=False, resonance=0):
        source = combat_functions(SDK, extract_function)
        program = extract_function(source, function)
        globals_text = (SDK / 'GPLMx/mx_Globals.gpl').read_text(encoding='cp1252')
        for constant in ('intelligence_div', 'armor_magic_mult'):
            value = re.search(r'(?im)^\s*expression\s+#' + constant + r'\s+(\d+)', globals_text)
            if value is None:
                raise AssertionError('Stock constant not found: ' + constant)
            program = re.sub('#' + constant + r'\b', value.group(1), program, flags=re.I)
        program = re.sub(r'#(\w+)', r'"\1"', program)
        vm = DamageHarness(program)
        attacker = agent(type='hero', ATTRIB_intelligence=20,
                         ATTRIB_Weapon_Struct_Bonus=quality,
                         ATTRIB_Weapon_Magic_Bonus=magic,
                         ATTRIB_WeaponBasicDamage=base)
        defender = agent(subtype='hero', ATTRIB_armor_magic_bonus=armor)
        debits = []
        vm.calls.update({
            'checkeffector': lambda _, effect: (roused and effect == 'Bards_Roused_Icon') or (refrain and effect == 'Bards_Refrain_Icon'),
            'getattribute': lambda a, key: a[key],
            'randomnumber': lambda _: 4,
            'adjustattribute': lambda a, key, amount: debits.append(amount),
            'bards_direct_damage': lambda _a, _d, damage: max(0, damage),
            'bards_renown_hit': lambda *_: None,
            'bards_resonance_count': lambda _: resonance,
            'bards_refrain_bonus': lambda source: 3 if source is attacker and refrain else 0,
        })
        vm.call(function, attacker, defender, 10, 1)
        self.assertEqual(len(debits), 1)
        return -debits[0]

    def test_resonance_adds_flat_primary_damage_only(self):
        for stacks in (1,3,6):
            self.assertEqual(self.resolve('Bards_Arcane_Damage',resonance=stacks),
                             self.resolve('Bards_Arcane_Damage')+stacks)
            for function in ('Bards_Echo_Damage','Bards_Direct_Spell_Damage','spelldamage'):
                self.assertEqual(self.resolve(function,resonance=stacks),self.resolve(function))

    def test_primary_uses_both_bonuses_once_and_does_not_clamp_loot(self):
        baseline = self.resolve('Bards_Arcane_Damage')
        for quality, magic in ((1, 0), (0, 3), (3, 3), (5, 7)):
            self.assertEqual(self.resolve('Bards_Arcane_Damage', quality, magic),
                             baseline + quality + magic)

    def test_base_weapon_damage_is_not_added_to_the_spell(self):
        self.assertEqual(self.resolve('Bards_Arcane_Damage', base=100),
                         self.resolve('Bards_Arcane_Damage', base=4))

    def test_refrain_strengthens_primary_echo_area_and_periodic_damage_once(self):
        for function in ('Bards_Arcane_Damage', 'Bards_Echo_Damage', 'Bards_Direct_Spell_Damage', 'spelldamage'):
            self.assertEqual(self.resolve(function, refrain=True), self.resolve(function) + 3, function)
            self.assertEqual(self.resolve(function, armor=100, refrain=True), 0, function)

    def test_enchanted_armor_mitigates_upgrade_damage(self):
        self.assertEqual(self.resolve('Bards_Arcane_Damage', 3, 3, armor=100), 0)

    def test_roused_strengthens_primary_instrument_only(self):
        self.assertEqual(self.resolve('Bards_Arcane_Damage', roused=True),
                         self.resolve('Bards_Arcane_Damage') + 2)
        for function in ('Bards_Echo_Damage', 'Bards_Direct_Spell_Damage'):
            self.assertEqual(self.resolve(function, roused=True), self.resolve(function))

    def test_echo_now_uses_full_spell_roll(self):
        self.assertEqual(self.resolve('Bards_Echo_Damage'), self.resolve('Bards_Direct_Spell_Damage'))

    def test_echo_and_general_area_spell_ignore_equipment(self):
        for function in ('Bards_Echo_Damage', 'Bards_Direct_Spell_Damage'):
            self.assertEqual(self.resolve(function, 5, 7), self.resolve(function))


if __name__ == '__main__':
    unittest.main()
