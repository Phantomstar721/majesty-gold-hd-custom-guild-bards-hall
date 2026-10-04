"""Execute actual curse/gate GPL; native spell selection is traced separately."""
import re
import unittest
from test_hiring import ROOT, SDK, GPLSubset, agent
from bards_countermelody import suppression_functions
from build_bards_hall import extract_function


class CountermelodyTests(unittest.TestCase):
    def runtime(self):
        generated = suppression_functions(SDK, extract_function)
        names = ('Bards_Gate_WRc1', 'Bards_Gate_WRg1', 'Bards_Special_Spell',
                 'Bards_Spell_Available', 'Cast', 'Bards_Countermelody_Hit')
        program = '\n'.join(extract_function(generated, name) for name in names)
        program += (ROOT / 'src/gpl/Bards_Countermelody.gpl').read_text()
        effects = (ROOT / 'src/gpl/Bards_Effects.gpl').read_text()
        for name in ('Bards_Countermelody_Apply', 'Bards_Countermelody_End'):
            program += extract_function(effects, name)
        program = program.replace('#spell_exp', '10').replace('#Healer_spell_exp_bonus', '2')
        vm = GPLSubset(re.sub(r'#(\w+)', r'"\1"', program))
        caster = agent(title='Spellsinger', Target=None)
        target = agent(type='Monster', subtype='Monster', ATTRIB_HP=100,
                       ATTRIB_HtoH=60, ATTRIB_Ranged=45)
        caster['Target'] = target
        active, events = set(), []
        vm.calls.update({
            'getattribute': lambda a, key: a.fields.get(key, 0),
            'magicaladjustattribute': lambda a, key, delta: a.fields.__setitem__(key, a.fields.get(key, 0) + delta),
            'notvalid_attacker': lambda a: not a.alive,
            'notvalid': lambda a: a is None or not a.alive,
            'bards_hostile_target': lambda *_: True,
            'checkeffector': lambda a, name: (a, name) in active,
            'createeffector': lambda a, name, duration: (active.add((a, name)), events.append(('effect', duration))),
            'meteor_storm_check': lambda _: 7,
            'isspellavailable': lambda *args: (events.append(('availability', args)), True)[1],
            'getspellattribute': lambda *_: 8,
            'give_exp': lambda *args: events.append(('cast-xp',)),
            'playsound': lambda *args: events.append(('sound',)),
            'castspell': lambda *args: events.append(('cast',)),
            'react': lambda *_: events.append(('react',)),
            'exp_value': lambda *_: 25,
            'spellhit': lambda *_: 1,
            'attack_end': lambda *args: events.append(('combat-xp',)),
        })
        return vm, caster, target, active, events

    def test_gate_defers_original_validation_and_leaves_baseline_attacks_available(self):
        vm, caster, _, active, events = self.runtime()
        self.assertEqual(vm.call('Bards_Gate_WRc1', caster), 1)
        self.assertEqual(vm.call('Bards_Gate_WRg1', caster), 7)
        active.add((caster, 'Bards_Countermelody_Icon'))
        self.assertEqual(vm.call('Bards_Gate_WRc1', caster), 0)
        self.assertEqual(vm.call('Bards_Gate_WRg1', caster), 0)
        self.assertFalse(vm.call('Bards_Spell_Available', caster, 'fire_blast'))
        self.assertTrue(vm.call('Bards_Spell_Available', caster, 'energy_blast'))
        self.assertFalse(vm.call('Bards_Special_Spell', 'Bards_Arcane_Note'))
        self.assertFalse(vm.call('Bards_Special_Spell', 'Double_attack'))
        self.assertEqual(len(events), 1)
        active.clear()  # Native effect removal restores availability by itself.
        self.assertEqual(vm.call('Bards_Gate_WRg1', caster), 7)

    def test_suppressed_cast_never_earns_xp_sound_or_native_cooldown(self):
        vm, caster, target, active, events = self.runtime()
        active.add((caster, 'Bards_Countermelody_Icon'))
        vm.call('Cast', caster, 'fire_blast', target, '')
        self.assertEqual(events, [])
        vm.call('Cast', caster, 'energy_blast', target, '')
        self.assertEqual(events, [('cast-xp',), ('sound',), ('cast',)])

    def test_resistance_and_covered_targets_do_not_apply_twice(self):
        for hit, expected in ((1, 40), (2, 60), (3, 60)):
            vm, caster, target, _, events = self.runtime()
            vm.calls['spellhit'] = lambda _: hit
            vm.call('Bards_Countermelody_Hit', caster, target)
            self.assertEqual(target['ATTRIB_HtoH'], expected)
            self.assertEqual(sum(e[0] == 'combat-xp' for e in events), 1)
            if hit == 1:
                self.assertIn(('effect', 8000), events)
                self.assertEqual(vm.call('Bards_Countermelody_Check', caster), 0)
                vm.call('Bards_Countermelody_Hit', caster, target)
                self.assertEqual(sum(e[0] == 'combat-xp' for e in events), 1)

    def test_native_expiry_reverses_only_our_nonstacking_deltas(self):
        vm, caster, target, active, _ = self.runtime()
        vm.call('Bards_Countermelody_Apply', caster, target)
        vm.call('Bards_Countermelody_Apply', caster, target)
        target['ATTRIB_HtoH'] += 8  # Independent Valor/equipment change.
        active.clear()
        vm.call('Bards_Countermelody_End', target)
        self.assertEqual((target['ATTRIB_HtoH'], target['ATTRIB_Ranged']), (68, 45))

    def test_no_friendly_building_mirror_or_unusable_cast_targets(self):
        for fields in ({'type': 'Building'}, {'ATTRIB_HasEffectMagicMirror': 1},
                       {'ATTRIB_MagicResistance': 100}, {'ATTRIB_HP': 5}):
            vm, caster, target, _, _ = self.runtime()
            target.fields.update(fields)
            self.assertFalse(vm.call('Bards_Countermelody_Target', caster, target), fields)
        vm, caster, target, active, _ = self.runtime()
        vm.calls['bards_hostile_target'] = lambda *_: False
        self.assertEqual(vm.call('Bards_Countermelody_Check', caster), 0)
        active.add((caster, 'Bards_Countermelody_Icon'))
        self.assertEqual(vm.call('Bards_Countermelody_Check', caster), 0)


if __name__ == '__main__':
    unittest.main()
