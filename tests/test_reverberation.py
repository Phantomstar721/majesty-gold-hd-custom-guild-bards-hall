"""Exercise actual impact/proc GPL with native damage/resistance mocked."""
import re
import unittest
from test_hiring import ROOT, SDK, GPLSubset, agent
from build_bards_hall import extract_function
from bards_abilities import combat_functions

SOURCE = (ROOT / 'src/gpl/Bards_Spellsinger.gpl').read_text()


class ReverberationTests(unittest.TestCase):
    def runtime(self):
        program = '\n'.join(extract_function(SOURCE, name) for name in ('Bards_Reverberation_Ready', 'Bards_Reverberate'))
        combat = combat_functions(SDK, extract_function)
        program += extract_function(combat, 'Bards_Arcane_Attack')
        # The harness borrows an opaque coordinate token; it does not emulate
        # the map, native query order or projectile travel.
        program = program.replace('coordinate Center;', 'agent Center;')
        program = re.sub(r'#(\w+)', r'"\1"', program)
        vm = GPLSubset(program)
        caster = agent(title='Spellsinger', ATTRIB_ExperienceLevel=3)
        primary, echo = agent(), agent()
        events = []
        clock = [10000]
        vm.calls.update({
            'getattribute': lambda a, key: a[key],
            'notvalid_attacker': lambda a: not a.alive,
            'notvalid': lambda a: not a.alive,
            'mm_simulationtime': lambda: clock[0],
            'mm_simulationelapsed': lambda t: (clock[0] - t) & 0xffffffff,
            'bards_reverberation_target': lambda *_: echo,
            'bards_hostile_target': lambda *_: True,
            'bards_echo_attack': lambda *args: events.append(('echo', args)),
            'bards_resonance_add': lambda *_: None,
            'createeffector': lambda *_: None,
            'playsound': lambda *_: None,
            'react': lambda *_: None,
            'exp_value': lambda *_: 25,
            'spellhit': lambda *_: 1,
            'locationof': lambda _: primary,
            'bards_arcane_damage': lambda *_: 5,
            'attack_end': lambda *args: events.append(('xp', args)),
        })
        return vm, caster, primary, echo, clock, events

    def test_only_positive_successful_ordinary_impacts_proc(self):
        for hit, damage, level, expected in ((1, 5, 3, True), (2, 5, 3, False), (3, 5, 3, False), (1, 0, 3, False), (1, 5, 2, False)):
            vm, caster, primary, _, _, events = self.runtime()
            vm.calls['spellhit'] = lambda _: hit
            vm.calls['bards_arcane_damage'] = lambda *_: damage
            caster['ATTRIB_ExperienceLevel'] = level
            vm.call('Bards_Arcane_Attack', caster, primary, 10)
            self.assertEqual(any(e[0] == 'echo' for e in events), expected)
            self.assertEqual(sum(e[0] == 'xp' for e in events), 1)

    def test_echo_resistance_does_not_grant_fallback_and_commit_precedes_callback(self):
        vm, caster, primary, _, clock, events = self.runtime()
        def resisted(*_):
            self.assertEqual(caster['BardsReverberatedAt'], clock[0])
            vm.call('Bards_Reverberate', caster, primary, primary)  # Reentry.
        vm.calls['bards_echo_attack'] = resisted
        vm.call('Bards_Reverberate', caster, primary, primary)
        self.assertEqual(events, [])

    def test_solo_has_no_second_damage_or_old_debuff(self):
        vm, caster, primary, _, clock, events = self.runtime()
        vm.calls['bards_reverberation_target'] = lambda *_: None
        vm.call('Bards_Reverberate', caster, primary, primary)
        self.assertEqual(events, [])

    def test_killed_primary_can_echo_but_cannot_receive_solo_debuff(self):
        vm, caster, primary, _, _, events = self.runtime()
        primary.alive = False
        vm.call('Bards_Reverberate', caster, primary, primary)
        self.assertEqual([e[0] for e in events], ['echo'])
        vm, caster, primary, _, _, events = self.runtime()
        primary.alive = False
        vm.calls['bards_reverberation_target'] = lambda *_: None
        vm.call('Bards_Reverberate', caster, primary, primary)
        self.assertEqual(events, [])
        self.assertNotIn('BardsReverberatedAt', caster.fields)

    def test_negative_timestamp_bits_are_valid_across_wrap(self):
        vm, caster, primary, _, clock, events = self.runtime()
        caster['BardsReverberatedAt'] = -500
        clock[0] = 5500
        vm.call('Bards_Reverberate', caster, primary, primary)
        self.assertEqual([e[0] for e in events], ['echo'])


if __name__ == '__main__':
    unittest.main()
