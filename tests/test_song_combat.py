"""Combat songs distinguish attack travel from a fight within stock range."""
import re
import unittest
from test_hiring import ROOT, agent
from test_deflect import ImpactHarness


class SongCombatTests(unittest.TestCase):
    def runtime(self):
        source = (ROOT / 'src/gpl/Bards_Songs.gpl').read_text()
        vm = ImpactHarness(re.sub(r'#(\w+)', r'"\1"', source))
        attack, travel = lambda: None, lambda: None
        hero = agent(type='Hero', Target=None, ActiveScript=travel, BackScript=attack,
                     Hostiles=[], reach=40, distance=1519, ATTRIB_HP=100, ATTRIB_MaxHP=100)
        enemy = agent(type='Lair', Target=None, reach=200)
        hero['Target'] = enemy
        vm.calls.update({
            'attack_object': attack,
            'berserk': lambda: None,
            'berserk_defend': lambda: None,
            'notvalid': lambda h: h is None or not h.alive,
            'bards_hostile_target': lambda h,e: h is not e,
            'distancebetweenagents': lambda h,e: hero['distance'],
            'getattackrange': lambda h: h['reach'],
            'cleanse_hostiles': lambda h: None,
            'agentinlist': lambda h, items: h in items,
            'getattribute': lambda h,k: h[k],
            'bards_song_refresh': lambda *_: True,
            'target_eval': lambda *_: -1,
        })
        return vm, hero, enemy, attack

    def test_distant_queued_attack_does_not_enable_valor_or_refrain(self):
        vm, hero, enemy, attack = self.runtime()
        hero['ATTRIB_HP'] = 10
        for active in (hero['ActiveScript'], attack):
            hero['ActiveScript'] = active
            self.assertFalse(vm.call('Bards_Song_Engaged', hero))
            self.assertFalse(vm.call('Bards_Song_Useful', agent(), [hero], 'Bards_Refrain'))
            self.assertFalse(vm.call('Bards_Song_Useful', agent(), [hero], 'Bards_Valor'))

    def test_weapon_and_spell_range_include_boundary(self):
        for reach in (40, 250):
            vm, hero, enemy, _ = self.runtime()
            hero['reach'] = hero['distance'] = reach
            self.assertTrue(vm.call('Bards_Song_Engaged', hero))
            hero['distance'] += 1
            self.assertFalse(vm.call('Bards_Song_Engaged', hero))

    def test_ranged_defense_and_berserk_enable_all_combat_songs(self):
        for dispatch in ('attack_object', 'berserk', 'berserk_defend'):
            for active in (True, False):
                vm, hero, enemy, _ = self.runtime()
                hero['ActiveScript'] = vm.calls[dispatch] if active else lambda: None
                hero['BackScript'] = (lambda: None) if active else vm.calls[dispatch]
                hero['distance'] = hero['reach'] = 340
                caster = agent()
                vm.calls['bards_satire_eligible'] = lambda *_: True
                self.assertTrue(vm.call('Bards_Song_Useful', caster, [hero], 'Bards_Valor'))
                self.assertTrue(vm.call('Bards_Song_Useful', caster, [hero], 'Bards_Refrain'))
                self.assertEqual(vm.call('Bards_Satire_Targets', caster, [hero]), [enemy])
                hero['distance'] = 1000
                self.assertFalse(vm.call('Bards_Song_Engaged', hero))

    def test_refrain_supports_healthy_ally_against_weaker_enemy(self):
        vm, hero, enemy, attack = self.runtime()
        hero['ActiveScript'] = attack
        hero['distance'] = hero['reach']
        vm.calls['target_eval'] = lambda *_: self.fail('Refrain must not assess enemy strength')
        self.assertTrue(vm.call('Bards_Song_Useful', agent(), [hero], 'Bards_Refrain'))
        vm.calls['bards_song_refresh'] = lambda *_: False
        self.assertFalse(vm.call('Bards_Song_Useful', agent(), [hero], 'Bards_Refrain'))

    def test_incoming_attacker_protects_nonattacking_ally_but_stale_entry_does_not(self):
        vm, hero, enemy, _ = self.runtime()
        hero['Target'] = None
        hero['Hostiles'] = [enemy]
        hero['distance'] = 180
        enemy['type'], enemy['Target'] = 'Monster', hero
        self.assertTrue(vm.call('Bards_Song_Engaged', hero))
        enemy['Target'] = agent()
        self.assertFalse(vm.call('Bards_Song_Engaged', hero))
        enemy['Target'], hero['distance'] = hero, 201
        self.assertFalse(vm.call('Bards_Song_Engaged', hero))

    def test_satire_does_not_pick_queued_target_during_a_different_fight(self):
        vm, hero, distant, _ = self.runtime()
        incoming = agent(type='Monster', Target=hero, reach=200)
        hero['Hostiles'] = [incoming]
        vm.calls['distancebetweenagents'] = lambda h,e: 100 if incoming in (h,e) else 1519
        vm.calls['bards_satire_eligible'] = lambda *_: True
        self.assertEqual(vm.call('Bards_Satire_Targets', agent(), [hero]), [incoming])
