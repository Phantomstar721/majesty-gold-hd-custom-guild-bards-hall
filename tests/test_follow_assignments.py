"""Assignment exclusion across ordinary follow, hiring and Guild quest tasks."""
import re
import unittest
from test_hiring import ROOT, SDK
from test_deflect import ImpactHarness
from test_guild_capacity import unit
from build_bards_hall import extract_function
from bards_heroes import support_hero_prototype, hero_data


class FollowAssignmentTests(unittest.TestCase):
    def test_controlled_zombie_is_rejected_before_home_or_activity_reads(self):
        from bards_abilities import support_functions
        source = extract_function(support_functions(SDK, extract_function), 'Bards_Follow_Check')
        source += (ROOT / 'src/gpl/Bards_Follow.gpl').read_text()
        source = source.replace('#Follow_support_Check_Mod', '2')
        vm = ImpactHarness(re.sub(r'#(\w+)', r'"\1"', source))
        zombie = unit(type='Hero', title='Zombie', subtype='Controlled')
        bard = unit(title='Troubadour', subtype='Hero', team=1)
        def candidates(owner, kind, radius, result, *flags):
            result.append(zombie)
            return 1
        def unexpected(*args):
            self.fail('Rejected controlled unit reached activity/home evaluation')
        vm.calls.update(randomnumber=lambda n: 0, getattribute=lambda *a: 200,
                        listobjects=candidates, notvalid=lambda a: a is None,
                        bards_follow_going_home=unexpected, bards_follow_active=unexpected)
        self.assertFalse(vm.call('Bards_Follow_Check', bard, 'Hero', 100))

    def test_home_comparison_guards_missing_properties_and_preserves_home_visit(self):
        source = (ROOT / 'src/gpl/Bards_Follow.gpl').read_text()
        vm = ImpactHarness(extract_function(source, 'Bards_Follow_Going_Home'))
        use_building = lambda: None
        vm.calls.update(notvalid=lambda a: a is None, use_building=use_building)
        self.assertFalse(vm.call('Bards_Follow_Going_Home', None))
        self.assertFalse(vm.call('Bards_Follow_Going_Home', unit(title='Zombie')))
        home = unit()
        leader = unit(home=home, BackScript=use_building, Target=home)
        self.assertTrue(vm.call('Bards_Follow_Going_Home', leader))
        leader['Target'] = unit()
        self.assertFalse(vm.call('Bards_Follow_Going_Home', leader))

    def test_support_arrival_stops_at_song_range_without_chasing_into_melee(self):
        from bards_abilities import support_functions
        source = extract_function(support_functions(SDK, extract_function), 'Bards_Support_Arrived')
        source = source.replace('#follow_support_buffer', '50')
        # Coordinate locals are unused on the hero-target branch under test.
        source = re.sub(r'\bcoordinate\b', 'integer', source)
        source = re.sub(r'#(\w+)', r'"\1"', source)
        vm = ImpactHarness(source)
        leader = unit(type='Hero')
        bard = unit(target=leader, backscript='support', activescript='travel')
        stopped = []
        vm.calls.update(notvalid=lambda _: False, ismoving=lambda _: True,
                        reachedtargetdistance=lambda h,t,d: 120 <= d,
                        stopmoving=lambda h: stopped.append(h), debugout=lambda *_: None)
        self.assertTrue(vm.call('Bards_Support_Arrived', bard, True))
        self.assertEqual(stopped, [bard])
        self.assertEqual(bard['activescript'], 'support')
        self.assertIs(bard['target'], leader)

    def runtime(self):
        source = (ROOT / 'src/gpl/Bards_Follow.gpl').read_text()
        vm = ImpactHarness(re.sub(r'#(\w+)', r'"\1"', source))
        leader = unit(title='Warrior', subtype='Hero', team=1)
        bard = unit(title='Troubadour', subtype='Hero', team=1,
                    BasicScript='tree', StartingScript='tree', BackTarget=leader)
        followers = [bard]
        def snapshot(owner, kind, radius, result, *flags):
            self.assertEqual(radius, -1)
            self.assertIn('NoHiddenMap', flags)
            result.extend(followers)
            return len(result)
        vm.calls.update(notvalid=lambda a: a is None or not a.alive,
                        getplayerteamnumber=lambda a: a['team'], listobjects=snapshot,
                        addlists=lambda a, b: a + b)
        return vm, bard, leader, followers

    def test_excludes_troubadours_self_dead_and_other_team(self):
        for case in ('self', 'troub', 'dead', 'team'):
            vm, bard, leader, _ = self.runtime()
            if case == 'self': leader = bard
            if case == 'troub': leader['title'] = 'Troubadour'
            if case == 'dead': leader.alive = False
            if case == 'team': leader['team'] = 2
            self.assertFalse(vm.call('Bards_Follow_Target_Eligible', bard, leader), case)

    def test_any_owned_assignment_blocks_second_troub_but_stale_target_does_not(self):
        for task in ('ordinary-follow', 'hired-follow', 'guild-support'):
            vm, bard, leader, followers = self.runtime()
            other = unit(BasicScript=task, StartingScript='tree', BackTarget=leader)
            followers.append(other)
            self.assertFalse(vm.call('Bards_Follow_Target_Eligible', bard, leader), task)
            other['BasicScript'] = 'tree'
            self.assertTrue(vm.call('Bards_Follow_Target_Eligible', bard, leader))
            other['BardsHirePatron'] = leader
            self.assertFalse(vm.call('Bards_Follow_Target_Eligible', bard, leader))
            other.alive = False
            self.assertTrue(vm.call('Bards_Follow_Target_Eligible', bard, leader))

    def test_guild_callback_does_not_own_claim_or_task_fields(self):
        source = (ROOT / 'src/gpl/Bards_Follow.gpl').read_text()
        callback = extract_function(source, 'Bards_Hall_Support_Tick')
        self.assertNotRegex(callback, r'"(?:BasicScript|BackScript|BackTarget|AG\w+)"\s*=')
        self.assertNotIn('$RunThread', source)

    def test_song_exception_requires_current_accepted_support_task(self):
        vm, bard, leader, _ = self.runtime()
        bard['AGAcceptedQuest'] = bard
        bard['AGQuestKind'] = 10
        bard['AGDestination'] = leader
        bard['BasicScript'] = bard['ActiveScript'] = 'guild-support'
        self.assertTrue(vm.call('Bards_Hall_Supporting', bard))
        for field, wrong in (('AGAcceptedQuest', None), ('AGQuestKind', 11),
                             ('AGDestination', bard), ('ActiveScript', 'attack')):
            previous = bard[field]
            bard[field] = wrong
            self.assertFalse(vm.call('Bards_Hall_Supporting', bard), field)
            bard[field] = previous

    def test_support_tick_prioritizes_song_without_replacing_guild_task(self):
        vm, bard, leader, _ = self.runtime()
        bard['AGAcceptedQuest'] = bard
        bard['AGQuestKind'] = 10
        bard['AGDestination'] = leader
        bard['BasicScript'] = bard['ActiveScript'] = 'guild-support'
        calls = []
        vm.calls.update(bards_troubadour_evaluate=lambda h: False,
                        bards_combat_support=lambda h,l: False,
                        ishidden=lambda h: False,
                        bards_try_song=lambda h: (calls.append('song'), True)[1])
        before = dict(bard.fields)
        self.assertTrue(vm.call('Bards_Hall_Support_Tick', bard, leader))
        self.assertEqual(calls, ['song'])
        self.assertEqual(bard.fields, before)

    def test_callback_fields_are_typed_append_only_stock_hero_clone(self):
        source = (SDK / 'GPLMx/mx_prototype.gpl').read_text(encoding='cp1252')
        original, = re.findall(r'(?ims)^prototype hero \(\).*?^end\b', source)
        private = support_hero_prototype(SDK).replace('Bards_Support_Hero', 'hero')
        private = private.replace('\n\tfunction HeroSupportEligible;\n\tfunction HeroSupportTick;\n\tfunction HeroCapability;\n', '')
        private = private.replace("\n\tboolean Should_Kite;\n\tinteger KitingTime;", "")
        self.assertEqual(private.strip(), original.strip())
        self.assertIn('{Bards_Support_Hero', hero_data())


if __name__ == '__main__':
    unittest.main()
