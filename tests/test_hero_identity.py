"""Bard identity, stock lifecycle equivalence, and real decision-branch checks."""
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from test_hiring import ROOT, SDK, GPLSubset, agent
from build_bards_hall import build_units, build_gpl, extract_function
from validate_bards_abilities import stock_equal, require
from validate_bards_heroes import check_heroes
from bards_heroes import PROFILES, describe_hero


class HeroIdentityTests(unittest.TestCase):
    def test_emitted_profiles_and_private_decisions_keep_stock_task_lifecycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            (package / 'Data').mkdir()
            (package / 'Data/bards_units.xml').write_bytes(build_units(SDK))
            build_gpl(SDK, package / 'GPL')
            check_heroes(SDK, package, extract_function, stock_equal, require)

    def test_source_class_cannot_add_gameplay_fields_to_private_profiles(self):
        for title in PROFILES:
            hero = ET.fromstring('<Description><Game><AllowedSpells><Spell Value="charm_monster"/></AllowedSpells>'
                                 '<Flags value="ForeignClassAbility"/><RangedAttack value="999"/>'
                                 '<FutureClassPower value="1"/></Game></Description>')
            describe_hero(hero, title, {'Troubadour':'BDT1','Spellsinger':'BDS1','Blade_Dancer':'BDD1'}[title])
            self.assertIsNone(hero.find('./Game/FutureClassPower'))
            self.assertIsNone(hero.find('./Game/RangedAttack'))
            self.assertIsNone(hero.find('./Game/Flags[@value="ForeignClassAbility"]'))
            self.assertIsNone(hero.find('./Game/AllowedSpells/Spell[@Value="charm_monster"]'))

    def tree(self, title, chosen=None):
        source = extract_function((ROOT / 'src/gpl/Bards_Hero_Trees.gpl').read_text(), 'Bards_' + title + '_Tree')
        source = re.sub(r'#(\w+)', r'"\1"', source)
        vm, calls = GPLSubset(source), []
        for name in set(re.findall(r'\$(\w+)', source)):
            def callback(*args, name=name.lower()):
                calls.append(name)
                return name in ({chosen} if isinstance(chosen, str) else (chosen or set()))
            vm.calls[name.lower()] = callback
        bard = agent(activescript='private_tree')
        vm.call('Bards_' + title + '_Tree', bard)
        return bard, calls, vm

    def test_idle_bards_fall_back_to_stock_wandering_without_source_class_tasks(self):
        for title in PROFILES:
            bard, calls, vm = self.tree(title)
            fallback = {'Spellsinger': 'bards_spellsinger_wander', 'Blade_Dancer': 'bards_dancer_wander'}.get(title, 'hero_wander')
            self.assertIs(bard['activescript'], vm.calls[fallback])
            self.assertFalse(set(calls) & {'seed_resource_check','steal_check','loot_gravestones',
                                          'build_pack','swarm','patrol','collect_resource','heal_others'})

    def test_dancer_ranger_economy_precedes_hunting_and_exploration(self):
        for activity in ('purchase_equipment', 'purchase_bazaar', 'pursue_entertainment'):
            _, calls, _ = self.tree('Blade_Dancer', {activity, 'bards_combat_wandering', 'explore_map'})
            self.assertEqual(calls[-1], activity)
            self.assertNotIn('explore_map', calls)

    def test_dancer_hunts_before_exploration_and_can_return_home_after_decline(self):
        _, calls, _ = self.tree('Blade_Dancer', {'bards_combat_wandering', 'explore_map'})
        self.assertEqual(calls[-1], 'bards_combat_wandering')
        _, calls, _ = self.tree('Blade_Dancer', {'go_home'})
        self.assertIn('explore_map', calls)
        self.assertEqual(calls[-1], 'go_home')

    def test_rest_and_hiring_preempt_optional_private_activities(self):
        for title in PROFILES:
            for chosen in ('rest', 'bards_hire_guard'):
                _, calls, _ = self.tree(title, chosen)
                self.assertEqual(calls[-1], chosen)
                self.assertFalse(set(calls) & {'bards_street_check','bards_prize_duel_check','bards_follow_check'})

    def test_hunting_wins_over_spoils_and_leisure(self):
        for title, competing in (
            ('Blade_Dancer', {'bards_combat_wandering', 'bards_prize_duel_check', 'go_home'}),
            ('Spellsinger', {'bards_combat_wandering', 'pursue_entertainment', 'go_home'}),
            ('Spellsinger', {'raid_lair', 'pursue_entertainment', 'go_home'}),
        ):
            _, calls, _ = self.tree(title, competing)
            self.assertIn(calls[-1], {'bards_combat_wandering', 'raid_lair'})
            self.assertFalse(set(calls) & {'bards_prize_duel_check', 'go_home'})
            if title != 'Blade_Dancer': self.assertNotIn('pursue_entertainment', calls)

    def test_reward_and_emergency_decisions_still_preempt_ordinary_hunting(self):
        for title in ('Spellsinger', 'Blade_Dancer'):
            for urgent in ('check_nearby', 'check_rewards', 'defend_home', 'rest'):
                _, calls, _ = self.tree(title, {urgent, 'bards_combat_wandering', 'bards_prize_duel_check'})
                self.assertEqual(calls[-1], urgent)

    def test_private_optional_activities_remain_available_after_work_declines(self):
        for title, activity in (('Blade_Dancer', 'bards_prize_duel_check'),
                                ('Spellsinger', 'bards_street_check')):
            _, calls, _ = self.tree(title, activity)
            self.assertEqual(calls[-1], activity)
            if title == 'Blade_Dancer':
                self.assertIn('bards_combat_wandering', calls)
            else:
                self.assertIn('purchase_bazaar', calls)
                self.assertNotIn('pursue_entertainment', calls)

    def test_private_troubadour_evaluator_never_casts_source_healer_spells(self):
        source = extract_function((ROOT / 'src/gpl/Bards_Hero_Evaluation.gpl').read_text(), 'Bards_Troubadour_Evaluate')
        vm = GPLSubset(re.sub(r'#(\w+)', r'"\1"', source))
        events = []
        vm.calls.update(listsize=len, flee=lambda *args: events.append('flee'), clearlist=lambda items: items.clear())
        bard = agent(Hostiles=[])
        self.assertFalse(vm.call('Bards_Troubadour_Evaluate', bard))
        self.assertEqual(events, [])
        bard['Hostiles'] = [agent()]
        self.assertTrue(vm.call('Bards_Troubadour_Evaluate', bard))
        self.assertEqual(events, ['flee'])
        self.assertEqual(bard['Hostiles'], [])


if __name__ == '__main__':
    unittest.main()
