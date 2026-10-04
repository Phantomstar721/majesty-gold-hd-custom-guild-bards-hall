"""Exercise Renown through the shared stock flag event, without a mod profile."""
import re
import unittest

from test_hiring import ROOT, SDK, agent
from test_deflect import ImpactHarness
from bards_abilities import renown_functions
from build_bards_hall import extract_function
from majesty_cam.compose import _load_stock_gameplay_event_items
from majesty_cam.gameplay_events import add_gameplay_event_observers
from majesty_cam.gpl import merge_sources, parse_gpl
from bard_job_harness import home, job_source


SOURCE = (ROOT / 'src/gpl/Bards_Renown.gpl').read_text() + job_source()
PAID = '''function Other_FlagPaid(agent Flag, agent Recipient, integer Share)
declare
begin
end
'''


class RenownTests(unittest.TestCase):
    def runtime(self, extra=''):
        vm = ImpactHarness(re.sub(r'#(\w+)', r'"\1"', SOURCE + extra))
        bards = [agent(title='Troubadour', player=1, team=1, ATTRIB_ExperienceLevel=2, Home=home())
                 for _ in range(2)]
        target = agent(player=2, team=2, ATTRIB_LevelXP=100,
                       BardsRenownContributors=bards.copy())
        target.alive = False
        flag = agent(ATTRIB_TargetID=target, ATTRIB_RewardCost=1, gavereward=False, heroes=[])
        vm.calls.update({
            'bards_finale_defeat': lambda *_: None,
            'getattribute': lambda a, key: next((value for name, value in a.fields.items()
                                               if name.casefold() == key.casefold()), 0),
            'setattribute': lambda a, key, value: a.fields.__setitem__(key, value),
            'getunitplayernumber': lambda a: a['player'],
            'getplayerteamnumber': lambda a: a['team'],
            'neutralteamnumber': lambda: 0,
            'agentinlist': lambda a, values: a in values,
            'agentnumber': lambda value: value,
            'distancebetweenagents': lambda bard, _: bard.fields.get('distance', 100),
            'listobjects': lambda a, kind, radius, output, *args: None,
        })
        return vm, flag, target, bards

    def test_home_tier_gates_contribution_award_and_settlement_without_retroactive_credit(self):
        vm, _, target, bards = self.runtime()
        bard, hero = bards[0], agent(player=1, team=1)
        bard['Home'] = home(1)
        target['BardsRenownContributors'] = []
        vm.call('Bards_Renown_Contributor', bard, hero, target)
        self.assertEqual(target['BardsRenownContributors'], [])
        bard['Home'] = home(1, complete=False)
        vm.call('Bards_Renown_Award', bard, target, 2, False)
        self.assertNotIn('BardsRenownGold', bard.fields)
        bard['Home'] = home()
        vm.call('Bards_Renown_Contributor', bard, hero, target)
        self.assertEqual(target['BardsRenownContributors'], [bard])
        vm.call('Bards_Renown_Award', bard, target, 2, False)
        events = []
        vm.calls['give_gold'] = lambda _, amount: events.append(('gold', amount))
        vm.calls['give_exp'] = lambda _, amount: events.append(('xp', amount))
        bard['Home'] = home(1)
        vm.call('Bards_Renown_Settle', bard, bard['Home'])
        self.assertEqual(events, [])
        self.assertEqual(bard['BardsRenownGold'], 50)
        bard['Home'] = home()
        vm.call('Bards_Renown_Settle', bard, bard['Home'])
        vm.call('Bards_Renown_Settle', bard, bard['Home'])
        self.assertEqual(events, [('gold', 50), ('xp', 150)])

    def test_positive_bounty_records_all_bards_before_diplomacy_reverts(self):
        vm, flag, target, bards = self.runtime()
        vm.call('Bards_Renown_Completed_Bounty', flag, target)
        self.assertTrue(target['BardsRenownBounty'])
        self.assertEqual(target['BardsRenownBountyContributors'], bards)
        self.assertTrue(all('BardsRenownGold' not in bard.fields for bard in bards))
        target['team'] = 1
        vm.call('Bards_Renown_Defeat', target, 1)
        vm.call('Bards_Renown_Defeat', target, 1)
        self.assertEqual([(b['BardsRenownGold'], b['BardsRenownXP']) for b in bards],
                         [(25, 75), (25, 75)])

    def test_nonpositive_bounty_cannot_earn_bounty_royalties(self):
        for amount in (0, -1):
            vm, flag, target, bards = self.runtime()
            flag['ATTRIB_RewardCost'] = amount
            vm.call('Bards_Renown_Completed_Bounty', flag, target)
            self.assertNotIn('BardsRenownBounty', target.fields)
            vm.call('Bards_Renown_Defeat', target, 1)
            self.assertTrue(all('BardsRenownGold' not in bard.fields for bard in bards))

    def test_capture_uses_same_rank_gate_and_highest_reward_after_control(self):
        # Equal rank qualifies; rank6+ always qualifies regardless of bard level.
        cases = ((500, 3, False, 75), (500, 4, False, 0),
                 (1500, 5, False, 75), (1500, 6, False, 0),
                 (2000, 100, False, 75), (3500, 100, False, 75),
                 (3501, 100, False, 75), (100, 2, True, 25),
                 (100, 1, True, 75), (900, 3, False, 75))
        for level_xp, bard_level, bounty, expected in cases:
            vm, flag, target, bards = self.runtime()
            for bard in bards:
                bard['ATTRIB_ExperienceLevel'] = bard_level
            target['ATTRIB_LevelXP'] = level_xp
            if bounty:
                vm.call('Bards_Renown_Completed_Bounty', flag, target)
            # Both stock and the restored Zoo transfer ownership synchronously.
            target['player'] = target['team'] = 1
            target.alive = True
            vm.call('Bards_Renown_Captured', target)
            self.assertTrue(target['BardsRenownResolved'])
            self.assertEqual(target['BardsRenownContributors'], [])
            self.assertFalse(target.fields.get('BardsRenownBounty', False))
            self.assertEqual(target.fields.get('BardsRenownBountyContributors', []), [])
            # Repeat capture, escape/recapture and later death cannot pay again.
            vm.call('Bards_Renown_Captured', target)
            target['player'] = target['team'] = 2
            target.alive = False
            vm.call('Bards_Renown_Defeat', target, 1)
            self.assertEqual([(b.fields.get('BardsRenownGold', 0), b.fields.get('BardsRenownXP', 0))
                              for b in bards], [(expected, 250 if expected == 75 else expected * 3)] * 2)

    def test_capture_requires_contribution_living_bard_and_witness_range(self):
        vm, _, target, bards = self.runtime()
        target['ATTRIB_LevelXP'] = 3501
        target['player'] = target['team'] = 1
        target.alive = True
        bards[0].alive = False
        bards[1]['distance'] = 301
        near = agent(title='Troubadour', player=1, team=1, ATTRIB_ExperienceLevel=100, distance=300, Home=home())
        bystander = agent(title='Troubadour', player=1, team=1, ATTRIB_ExperienceLevel=1)
        target['BardsRenownContributors'].append(near)
        vm.call('Bards_Renown_Captured', target)
        for bard in (*bards, bystander):
            self.assertNotIn('BardsRenownGold', bard.fields)
        self.assertEqual((near['BardsRenownGold'], near['BardsRenownXP']), (75, 250))
        vm, _, target, _ = self.runtime()
        del target.fields['BardsRenownContributors']
        vm.call('Bards_Renown_Captured', target)
        self.assertNotIn('BardsRenownResolved', target.fields)

    def test_stock_success_branch_credits_capture_without_running_corpse_tail(self):
        death = extract_function(renown_functions(SDK, extract_function), 'monster_gravestone')
        for captured in (True, False):
            vm, _, target, bards = self.runtime(death)
            target['ATTRIB_LevelXP'] = 900
            target['Activescript'] = 'ordinary'
            target['ActiveScript'] = 'ordinary'  # Stock property names ignore case.
            events = []

            def zoo_check(monster):
                if captured:
                    monster['player'] = monster['team'] = 1
                    monster['type'] = 'Hidden'
                    monster.alive = True
                return captured

            vm.calls.update({
                'zoo_flag_check': zoo_check,
                'stopmoving': lambda _: events.append('stop'),
                'dropgoldinradius': lambda *_: events.append('loot'),
                'resumethread': lambda *_: events.append('resume'),
                'be_dead_2': lambda *_: None,
                'setthreadinterval': lambda *_: events.append('interval'),
                'performaction': lambda *_: events.append('death-action'),
            })
            vm.call('monster_gravestone', target)
            self.assertEqual([b['BardsRenownGold'] for b in bards], [75, 75])
            self.assertEqual(events, ['stop'] if captured else
                             ['stop', 'loot', 'resume', 'interval', 'death-action'])
            self.assertEqual(target['type'], 'Hidden' if captured else 'Dead')

    def event_source(self):
        # Include every emitted Renown stock clone: accidental ownership of
        # either flag function must fail the real shared-event owner check.
        program = renown_functions(SDK, extract_function) + SOURCE + PAID
        subscriptions = {
            'attack-flag-completed': ('Bards_Renown_Completed_Bounty',),
            'reward-flag-paid': ('Other_FlagPaid',),
        }
        stock = _load_stock_gameplay_event_items(SDK.parents[1], subscriptions)
        result = add_gameplay_event_observers(
            merge_sources([], {'bards': [parse_gpl(program)]}), subscriptions, stock)
        # Include generated observer dispatchers, whose private hashed names
        # are owned by the Manager rather than a fixed Bards symbol.
        wanted = {'attack_flag_poll', 'attack_flag_death_callback', 'other_flagpaid'}
        return '\n'.join(item.text for item in result.items
                         if item.normalized_name in wanted or item.normalized_name.startswith('mm_'))

    def test_both_success_paths_observe_even_without_recipients_or_positive_shares(self):
        extra = self.event_source()
        for owner in ('attack_flag_poll', 'Attack_flag_death_callback'):
            for recipient_count in (0, 2):
                vm, flag, target, bards = self.runtime(extra)
                recipients = [agent(subtype='Hero') for _ in range(recipient_count)]
                events = []
                native_callback = vm.calls['bards_renown_completed_bounty']

                def completed(f, t):
                    events.append(('completed', f, t))
                    native_callback(f, t)

                def nearby(a, kind, radius, output, *args):
                    if kind == 'hero' and not args:
                        output.extend(recipients)

                vm.calls.update({
                    'bards_renown_completed_bounty': completed,
                    'listobjects': nearby,
                    'addlists': lambda left, right: left + right,
                    'listsubtypes': lambda values, subtype: values,
                    'give_gold': lambda a, amount: events.append(('credit', a, amount)),
                    'other_flagpaid': lambda f, a, share: events.append(('paid', f, a, share)),
                    'playsound': lambda *args: events.append(('sound',)),
                    'deletegamepiece': lambda f: events.append(('delete',)),
                    'check_revert_teams': lambda f: (target.fields.__setitem__('team', 1),
                                                    events.append(('revert',))),
                })
                vm.call(owner, flag)
                self.assertEqual(events[:2], [('completed', flag, target), ('sound',)])
                self.assertEqual([e for e in events if e[0] == 'paid'],
                                 [('paid', flag, hero, 0) for hero in recipients])
                self.assertEqual(events[-1][0], 'delete' if owner == 'attack_flag_poll' else 'revert')
                self.assertTrue(flag['gavereward'])
                self.assertTrue(target['BardsRenownBounty'])
                vm.call('Bards_Renown_Defeat', target, 1)
                self.assertEqual([b['BardsRenownGold'] for b in bards], [25, 25])

    def test_success_guards_exclude_live_targets_and_repeat_death_notifications(self):
        extra = self.event_source()
        for owner in ('attack_flag_poll', 'Attack_flag_death_callback'):
            for already_paid, target_alive in ((True, False), (False, True)):
                vm, flag, target, _ = self.runtime(extra)
                flag['gavereward'] = already_paid
                target.alive = target_alive
                vm.call(owner, flag)
                self.assertNotIn('BardsRenownBounty', target.fields)


if __name__ == '__main__':
    unittest.main()
