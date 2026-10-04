"""Exercise the authored normal-hit chain and true-parry reaction gates."""
import re
import unittest
from test_hiring import ROOT, GPLSubset, agent

SOURCE = (ROOT / 'src/gpl/Bards_Dancer.gpl').read_text()


class DancerTests(unittest.TestCase):
    def test_flourish_presentation_delegates_one_native_hit_even_if_target_died(self):
        vm, dancer, enemy, _, _ = self.runtime()
        events=[]
        vm.calls['createeffector']=lambda *args: events.append(('effect',args))
        vm.calls['make_attack']=lambda *args: events.append(('attack',args))
        for alive in (True,False):
            events.clear()
            enemy.alive=alive
            vm.call('Bards_Flourish_Attack',dancer,enemy)
            self.assertEqual([e[0] for e in events],['effect','attack'])
            self.assertEqual(events[0][1],(dancer,'Bards_Flourish_Flash',0))
            self.assertEqual(events[1][1],(dancer,enemy))

    def test_flourish_cast_selected_before_third_hit_without_consuming_chain(self):
        vm, dancer, enemy, _, _ = self.runtime()
        dancer['Attack_Action'] = 'basic_attack'
        dancer['BardsDuelTarget'] = enemy
        for hits, expected in ((0, 'basic_attack'), (1, 'basic_attack'), (2, 'Bards_Flourish_Strike')):
            dancer['BardsDuelHits'] = hits
            self.assertEqual(vm.call('Bards_Weapon_Action', dancer, enemy), expected)
            self.assertEqual(dancer['BardsDuelHits'], hits)
        for other in (agent(type='Monster', subtype='Monster'), agent(type='Building', subtype='Guild')):
            self.assertEqual(vm.call('Bards_Weapon_Action', dancer, other), 'basic_attack')
        dancer['ATTRIB_ExperienceLevel'] = 7
        self.assertEqual(vm.call('Bards_Weapon_Action', dancer, enemy), 'basic_attack')

    def runtime(self):
        vm = GPLSubset(re.sub(r'#(\w+)', r'"\1"', SOURCE))
        dancer = agent(title='Blade_Dancer', ATTRIB_ExperienceLevel=8)
        enemy = agent(type='Monster', subtype='Monster', attacktype=1)
        clock, hits = [10000], []
        vm.calls.update({
            'bards_finale_attempt': lambda *_: None,
            'bards_finale_arm': lambda *_: None,
            'getattribute': lambda a, key: a[key],
            'notvalid_attacker': lambda a: not a.alive,
            'notvalid': lambda a: not a.alive,
            'bards_hostile_target': lambda *_: True,
            'isfrozen': lambda _: False,
            'mm_simulationtime': lambda: clock[0],
            'mm_simulationelapsed': lambda t: (clock[0] - t) & 0xffffffff,
            'bards_flourish_damage': lambda *args: hits.append(('flourish', args)),
            'damage': lambda *args: hits.append(('flourish' if vm.call('Bards_Consume_Flourish', *args) else 'normal', args)),
            'bards_riposte_attack': lambda *args: hits.append(('riposte', args)),
            'createeffector': lambda *args: None,
        })
        return vm, dancer, enemy, clock, hits

    def test_every_third_same_target_normal_hit_finishes(self):
        vm, dancer, enemy, clock, hits = self.runtime()
        for _ in range(6):
            vm.call('Bards_Flourish_Target', dancer, enemy)
            vm.call('Bards_Ordinary_Damage', dancer, enemy)
            clock[0] += 1100
        self.assertEqual([hit[0] for hit in hits], ['normal', 'normal', 'flourish'] * 2)

    def test_missed_attack_against_another_target_breaks_old_chain(self):
        vm, dancer, enemy, _, hits = self.runtime()
        for _ in range(2):
            vm.call('Bards_Ordinary_Damage', dancer, enemy)
        vm.call('Bards_Flourish_Target', dancer, agent())  # Hit resolver misses.
        vm.call('Bards_Flourish_Target', dancer, enemy)
        vm.call('Bards_Ordinary_Damage', dancer, enemy)
        self.assertEqual(hits[-1][0], 'normal')
        self.assertEqual(dancer['BardsDuelHits'], 1)

    def test_gap_boundary_and_death_reset(self):
        for gap, expected in ((5000, 'flourish'), (5001, 'flourish'), (120000, 'flourish')):
            vm, dancer, enemy, clock, hits = self.runtime()
            vm.call('Bards_Ordinary_Damage', dancer, enemy)
            vm.call('Bards_Ordinary_Damage', dancer, enemy)
            clock[0] += gap
            vm.call('Bards_Ordinary_Damage', dancer, enemy)
            self.assertEqual(hits[-1][0], expected)
        vm.call('Bards_Flourish_Reset', dancer)
        self.assertIsNone(dancer['BardsDuelTarget'])
        self.assertEqual(dancer['BardsDuelHits'], 0)

    def test_riposte_only_melee_level_three_and_at_most_once_per_four_seconds(self):
        for level, attacktype, expected in ((2, 1, False), (3, 1, True), (8, 2, False), (8, 5, False)):
            vm, dancer, enemy, _, hits = self.runtime()
            effects = []
            vm.calls['createeffector'] = lambda *args: effects.append(args)
            dancer['ATTRIB_ExperienceLevel'], enemy['attacktype'] = level, attacktype
            vm.call('Bards_Try_Riposte', dancer, enemy)
            self.assertEqual(bool(hits), expected)
            self.assertEqual(effects, [(dancer, 'Bards_Riposte_Flash', 0)] if expected else [])
        vm, dancer, enemy, clock, hits = self.runtime()
        vm.call('Bards_Ordinary_Damage', dancer, enemy)
        for advance in (0, 3999, 1):
            clock[0] += advance
            vm.call('Bards_Try_Riposte', dancer, enemy)
        self.assertEqual([hit[0] for hit in hits], ['normal', 'riposte', 'riposte'])
        self.assertEqual(dancer['BardsDuelHits'], 1)


if __name__ == '__main__':
    unittest.main()
