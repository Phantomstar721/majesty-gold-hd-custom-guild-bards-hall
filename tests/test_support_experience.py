"""Exercise the consumer at the Manager's exact stock-award event boundary."""
import re
import unittest
from test_hiring import ROOT, agent
from test_deflect import ImpactHarness


class SupportExperienceTests(unittest.TestCase):
    def runtime(self):
        source = (ROOT / 'src/gpl/Bards_Support_Experience.gpl').read_text()
        vm = ImpactHarness(re.sub(r'#(\w+)', r'"\1"', source))
        follow, travel = lambda: None, lambda: None
        leader = agent(title='Spellsinger', subtype='Hero', team=1, inside=False)
        bard = agent(title='Troubadour', team=1, BackTarget=leader, BasicScript=follow,
                     ActiveScript=travel, BackScript=follow, inside=False, frozen=False,
                     distance=180, guild_support=False, hired_valid=True)
        candidates, awards = [bard], []
        vm.calls.update({
            'notvalid_attacker': lambda h: h is None or not h.alive,
            'getplayerteamnumber': lambda h: h['team'],
            'insidebuilding': lambda h: h['inside'],
            'isfrozen': lambda h: h['frozen'],
            'distancebetweenagents': lambda h, _: h['distance'],
            'bards_hall_supporting': lambda h: h['guild_support'],
            'bards_hire_valid': lambda h, _: h['hired_valid'],
            'bards_follow_support': follow, 'bards_travel_support': travel,
            'listobjects': lambda _, kind, radius, output, *args: output.extend([h for h in candidates if h['distance'] <= radius] if kind == 'Hero' else []),
            'addlists': lambda a, b: a + b,
            'give_exp': lambda h, value: awards.append((h, value)),
        })
        return vm, leader, bard, candidates, awards

    def test_combat_and_exploration_each_pay_half_once_without_debiting_leader(self):
        for callback in ('Bards_CombatXP', 'Bards_ExplorationXP'):
            vm, leader, bard, _, awards = self.runtime()
            vm.call(callback, leader, 251)
            self.assertEqual(awards, [(bard, 125)])

    def test_catching_up_follower_receives_half_at_snapshot_distance_and_range_edge(self):
        for callback in ('Bards_CombatXP', 'Bards_ExplorationXP'):
            for distance in (225, 360):
                vm, leader, bard, _, awards = self.runtime()
                bard['distance'] = distance
                vm.call(callback, leader, 250)
                self.assertEqual(awards, [(bard, 125)])

    def test_does_not_award_inactive_distant_unavailable_or_expired_followers(self):
        for field, value in (('title', 'Blade_Dancer'), ('team', 2), ('BackTarget', None),
                             ('BasicScript', 'starting'), ('ActiveScript', 'wandering'),
                             ('BackScript', 'shopping'), ('inside', True), ('frozen', True),
                             ('distance', 361)):
            vm, leader, bard, _, awards = self.runtime()
            bard[field] = value
            vm.call('Bards_CombatXP', leader, 100)
            self.assertEqual(awards, [], field)
        vm, leader, bard, _, awards = self.runtime()
        bard['BardsHirePatron'], bard['hired_valid'] = leader, False
        vm.call('Bards_ExplorationXP', leader, 250)
        self.assertEqual(awards, [])

    def test_dead_leader_bard_inside_leader_and_troub_leader_do_not_pay(self):
        for choice in ('leader-dead', 'bard-dead', 'inside', 'troub', 'nonhero'):
            vm, leader, bard, _, awards = self.runtime()
            if choice == 'leader-dead': leader.alive = False
            if choice == 'bard-dead': bard.alive = False
            if choice == 'inside': leader['inside'] = True
            if choice == 'troub': leader['title'] = 'Troubadour'
            if choice == 'nonhero': leader['subtype'] = 'Familiar'
            vm.call('Bards_CombatXP', leader, 100)
            self.assertEqual(awards, [])

    def test_duplicate_followers_or_duplicate_visibility_entries_cannot_multiply_xp(self):
        vm, leader, bard, candidates, awards = self.runtime()
        candidates.extend((bard, agent(**bard.fields)))
        vm.call('Bards_CombatXP', leader, 100)
        self.assertEqual(awards, [(bard, 50)])

    def test_guild_support_accepts_private_quest_task_but_keeps_range_guard(self):
        vm, leader, bard, _, awards = self.runtime()
        bard['guild_support'] = True
        bard['BasicScript'] = bard['ActiveScript'] = 'quest-support'
        vm.call('Bards_ExplorationXP', leader, 250)
        self.assertEqual(awards, [(bard, 125)])
        bard['distance'] = 361
        vm.call('Bards_ExplorationXP', leader, 250)
        self.assertEqual(len(awards), 1)

    def test_nonpositive_rewards_and_ordinary_song_awards_have_no_entry_point(self):
        vm, leader, _, _, awards = self.runtime()
        for amount in (0, -1): vm.call('Bards_CombatXP', leader, amount)
        self.assertEqual(awards, [])
        from bards_recruitment_panel import manager_features
        self.assertEqual({f['event'] for f in manager_features() if f['type'] == 'stock.gameplay-event-observer.v1'},
                         {'combat-experience-awarded', 'exploration-experience-awarded'})


if __name__ == '__main__': unittest.main()
