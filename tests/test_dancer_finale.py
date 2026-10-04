"""Combat attribution, Encore consumption, and native timed-effect boundaries."""
import re
import unittest
from test_hiring import ROOT, SDK, agent
from test_deflect import ImpactHarness
from build_bards_hall import extract_function
from bards_dancer_systems import dancer_systems
from validate_bards_abilities import stock_equal


class FinaleTests(unittest.TestCase):
    def test_target_star_follows_preparation_and_shared_owner_cleanup(self):
        vm, dancer, target, _, effects, _ = self.runtime()
        marker = (id(target), 'Bards_Finale_Ready_Icon')
        vm.call('Bards_Finale_Arm', dancer, target)
        self.assertIn(marker, effects)
        other = agent(title='Blade_Dancer', BardsFinaleTarget=target)
        vm.calls['listobjects'] = lambda owner,kind,radius,result,*flags: result.extend([dancer,other] if kind == 'Hidden' else [])
        vm.call('Bards_Finale_Unmark', dancer)
        self.assertIn(marker, effects)
        vm.call('Bards_Finale_Unmark', other)
        self.assertNotIn(marker, effects)
        vm.call('Bards_Finale_Arm', dancer, target)
        vm.call('Bards_Finale_Attempt', dancer, agent(type='Monster', subtype='Monster', player=2))
        self.assertNotIn(marker, effects)
        dancer['BardsEncore'] = True
        vm.call('Bards_Finale_Attempt', dancer, target)
        self.assertIn(marker, effects)
        vm.call('Bards_Finale_Clear', dancer)
        self.assertNotIn(marker, effects)

    def test_death_only_queues_cast_and_completion_grants_awards_once(self):
        vm, dancer, target, ally, _, events = self.runtime()
        vm.call('Bards_Finale_Attempt', dancer, target)
        vm.call('Bards_Finale_Arm', dancer, target)
        vm.call('Bards_Finale_Record', dancer, target, 20)
        target['ATTRIB_HP'] = 0
        target.alive = False
        vm.call('Bards_Finale_Defeat', target, 1)
        self.assertEqual(events, [])
        self.assertTrue(dancer['BardsFinalePending'])
        self.assertTrue(vm.call('Bards_Try_Finale', dancer))
        self.assertEqual(events, [('cast', 'Bards_Finale_Cast')])
        self.assertFalse(vm.call('Bards_Try_Finale', dancer))
        vm.call('Bards_Finale_Complete', dancer, dancer)
        self.assertTrue(dancer['BardsEncore'])
        self.assertEqual(ally['ATTRIB_Parry'], 5)
        before = list(events)
        vm.call('Bards_Finale_Complete', dancer, dancer)
        self.assertEqual(events, before)

    def test_pending_finale_defers_for_health_and_clears_on_ownership_change(self):
        vm, dancer, _, _, _, events = self.runtime()
        dancer['BardsFinalePending'] = True
        dancer['BardsFinaleOwner'] = 1
        dancer['low'] = True
        self.assertFalse(vm.call('Bards_Try_Finale', dancer))
        self.assertTrue(dancer['BardsFinalePending'])
        self.assertEqual(events, [])
        dancer['low'] = False
        dancer['player'] = 2
        self.assertFalse(vm.call('Bards_Try_Finale', dancer))
        self.assertFalse(dancer['BardsFinalePending'])

    def runtime(self):
        source = (ROOT / 'src/gpl/Bards_Dancer.gpl').read_text()
        source += (ROOT / 'src/gpl/Bards_Finale.gpl').read_text()
        vm = ImpactHarness(re.sub(r'#(\w+)', r'"\1"', source))
        dancer = agent(title='Blade_Dancer', ATTRIB_ExperienceLevel=8, TaskName='', player=1)
        target = agent(type='Monster', subtype='Monster', rank=5, player=2, ATTRIB_HP=20)
        ally = agent(player=1)
        effects, events = set(), []
        def adjust(hero, key, delta):
            hero[key] = hero.fields.get(key, 0) + delta
        vm.calls.update({
            'isvalidgamepiece': lambda a: a is not None,
            'listobjects': lambda owner,kind,radius,result,*flags: result.extend([dancer] if kind == 'Hero' else []),
            'addlists': lambda a,b: a+b,
            'notvalid_attacker': lambda a: a is None or not a.alive,
            'notvalid': lambda a: a is None or not a.alive,
            'getattribute': lambda a, key: a.fields.get(key, 0),
            'getunitplayernumber': lambda a: a['player'],
            'bards_hostile_target': lambda a, b: a['player'] != b['player'],
            'bards_renown_rank': lambda a: a['rank'],
            'bards_song_party': lambda a: [a, ally],
            'checkeffector': lambda a, key: (id(a), key) in effects,
            'createeffector': lambda a, key, duration, *flags: (effects.add((id(a), key)), events.append((key, duration)) if key != 'Bards_Finale_Ready_Icon' else None),
            'deleteeffector': lambda a, key: (effects.discard((id(a), key)), events.append(('delete', key)) if key != 'Bards_Finale_Ready_Icon' else None),
            'magicaladjustattribute': adjust,
            'mm_simulationtime': lambda: 10000,
            'haslowhp': lambda a: a.fields.get('low', False),
            'isfrozen': lambda a: False,
            'performaction': lambda *args: events.append(('cast', args[1])),
            'randomnumber': lambda n: 24,
        })
        return vm, dancer, target, ally, effects, events

    def finish(self, vm, dancer, target):
        vm.call('Bards_Finale_Record', dancer, target, target['ATTRIB_HP'])
        target['ATTRIB_HP'] = 0
        target.alive = False
        vm.call('Bards_Finale_Defeat', target, 1)
        self.assertTrue(dancer['BardsFinalePending'])
        self.assertTrue(vm.call('Bards_Try_Finale', dancer))
        vm.call('Bards_Finale_Complete', dancer, dancer)

    def test_flourish_qualifies_without_requiring_the_third_hit_to_kill(self):
        vm, dancer, target, ally, _, events = self.runtime()
        for _ in range(3):
            vm.call('Bards_Flourish_Target', dancer, target)
            vm.call('Bards_Flourish_Hit', dancer, target)
        self.assertIs(dancer['BardsFinaleTarget'], target)
        vm.call('Bards_Finale_Record', dancer, target, 1)
        self.assertFalse(dancer.fields.get('BardsEncore', False))
        self.finish(vm, dancer, target)
        self.assertTrue(dancer['BardsEncore'])
        self.assertEqual(ally['ATTRIB_Parry'], 5)
        before = list(events)
        vm.call('Bards_Finale_Defeat', target, 1)
        self.assertEqual(events, before)

    def test_encore_consumes_on_attempt_including_miss_and_enemy_hero(self):
        for kind, subtype in [('Monster', 'Monster'), ('Hero', 'Hero')]:
            vm, dancer, target, *_ = self.runtime()
            dancer['BardsEncore'] = True
            target['type'], target['subtype'], target['rank'] = kind, subtype, 1
            vm.call('Bards_Finale_Attempt', dancer, target)  # no hit call: a miss counts
            self.assertFalse(dancer['BardsEncore'])
            self.assertIs(dancer['BardsFinaleTarget'], target)
            self.finish(vm, dancer, target)
            self.assertTrue(dancer['BardsEncore'])

    def test_dead_building_friendly_and_prize_activity_do_not_spend_encore(self):
        for case in ('dead', 'building', 'friend', 'prize'):
            vm, dancer, target, *_ = self.runtime()
            dancer['BardsEncore'] = True
            if case == 'dead': target.alive = False
            if case == 'building': target['type'], target['subtype'] = 'Building', 'Guild'
            if case == 'friend': target['player'] = 1
            if case == 'prize': dancer['TaskName'] = 'Bards_Prize_Duel'
            vm.call('Bards_Finale_Attempt', dancer, target)
            self.assertTrue(dancer['BardsEncore'], case)

    def test_capture_other_killer_and_target_switch_do_not_award(self):
        for case in ('capture', 'other', 'switch'):
            vm, dancer, target, _, _, events = self.runtime()
            vm.call('Bards_Finale_Arm', dancer, target)
            if case == 'switch':
                vm.call('Bards_Finale_Attempt', dancer, agent(type='Monster', subtype='Monster', player=2))
            killer = dancer if case != 'other' else agent(title='Warrior', player=1)
            vm.call('Bards_Finale_Record', killer, target, 20)
            target['ATTRIB_HP'] = 0
            vm.call('Bards_Finale_Defeat', target, 3 if case == 'capture' else 1)
            self.assertFalse(dancer.fields.get('BardsEncore', False), case)
            self.assertEqual(events, [])

    def test_all_monster_ranks_arm_and_owner_change_clears_banked_encore(self):
        vm, dancer, target, *_ = self.runtime()
        for rank in range(9):
            target['rank'] = rank
            vm.call('Bards_Finale_Arm', dancer, target)
            self.assertIs(dancer['BardsFinaleTarget'], target)
        dancer['BardsEncore'], dancer['BardsFinaleOwner'] = True, 9
        vm.call('Bards_Finale_Attempt', dancer, target)
        self.assertFalse(dancer['BardsEncore'])
        self.assertIsNone(dancer['BardsFinaleTarget'])

    def test_banked_encore_has_native_indefinite_entry_until_consumed(self):
        vm, dancer, target, _, effects, _ = self.runtime()
        creates = []
        create = vm.calls['createeffector']
        vm.calls['createeffector'] = lambda *args: (creates.append(args), create(*args))
        vm.call('Bards_Finale_Attempt', dancer, target)
        vm.call('Bards_Finale_Arm', dancer, target)
        self.finish(vm, dancer, target)
        self.assertIn((dancer, 'Bards_Encore_Icon', 1, 'Infinite'), creates)
        self.assertIn((id(dancer), 'Bards_Encore_Icon'), effects)
        target.alive, target['ATTRIB_HP'] = True, 20
        vm.call('Bards_Finale_Attempt', dancer, target)
        self.assertNotIn((id(dancer), 'Bards_Encore_Icon'), effects)
        self.assertFalse(dancer['BardsEncore'])

    def test_native_encore_removal_clears_charge_and_death_clear_removes_entry(self):
        vm, dancer, _, _, effects, _ = self.runtime()
        dancer['BardsEncore'] = True
        vm.call('Bards_Encore_End', dancer)
        self.assertFalse(dancer['BardsEncore'])
        dancer['BardsEncore'] = True
        effects.add((id(dancer), 'Bards_Encore_Icon'))
        vm.call('Bards_Finale_Clear', dancer)
        self.assertFalse(dancer['BardsEncore'])
        self.assertNotIn((id(dancer), 'Bards_Encore_Icon'), effects)

    def test_refresh_does_not_stack_expiry_reverses_and_low_hp_still_retreats(self):
        vm, dancer, _, _, _, events = self.runtime()
        for _ in range(3): vm.call('Bards_Roused_Apply', dancer)
        self.assertEqual(dancer['ATTRIB_Parry'], 5)
        self.assertEqual(dancer['ATTRIB_Dodge'], 5)
        self.assertEqual(events.count(('Bards_Roused_Icon', 120000)), 3)
        self.assertTrue(vm.call('Bards_Roused_Stand', dancer))
        vm.calls['randomnumber'] = lambda n: 25
        self.assertFalse(vm.call('Bards_Roused_Stand', dancer))
        vm.calls['randomnumber'] = lambda n: 0
        dancer['low'] = True
        self.assertFalse(vm.call('Bards_Roused_Stand', dancer))
        vm.call('Bards_Roused_End', dancer)
        self.assertEqual((dancer['ATTRIB_Parry'], dancer['ATTRIB_Dodge']), (0, 0))


class PrizeChoiceHarness(ImpactHarness):
    """Support stock Visit_Building's list removal and counter increment."""
    def run(self, node, env):
        if node[0] == 'simple':
            tokens = node[1]
            if len(tokens) == 3 and tokens[1:] == ['+', '+']:
                env[tokens[0]] += 1
                return
            if len(tokens) >= 4 and tokens[1:3] == ['-', '=']:
                self.value(tokens[:1], env).remove(self.value(tokens[3:], env))
                return
        super().run(node, env)


class PrizeTests(unittest.TestCase):
    def choice_runtime(self, venues, roll=0):
        vm, dancer, _, events = self.runtime()
        source = (ROOT / 'src/gpl/Bards_Prize_Duel.gpl').read_text()
        source += extract_function(dancer_systems(SDK, extract_function), 'Bards_Prize_Duel_Check')
        source = source.replace('#Max_Farthest_Building_Choices', '3')
        choice = PrizeChoiceHarness(re.sub(r'#(\w+)', r'"\1"', source))
        choice.calls.update(vm.calls)
        queries = []
        def objects(owner, kind, radius, result, *filters):
            queries.append((kind, radius, filters))
            result.extend(v for v in venues if v['distance'] <= radius
                          and v['player'] == owner['player']
                          and v['ATTRIB_FirstStageBuilt'] == 1)
        choice.calls.update(listobjects=objects, listsize=len,
                            listmember=lambda values, index: values[index - 1],
                            randomnumber=lambda n: roll if n == 100 else 0,
                            debugout=lambda *_: None, bards_prize_use=lambda *_: None)
        return choice, dancer, queries

    def test_nearby_venue_selection_and_twenty_five_percent_boundary(self):
        local = agent(type='Building', title='Embassy', player=1,
                      ATTRIB_FirstStageBuilt=1, distance=180)
        remote = agent(type='Building', title='Embassy', player=1,
                       ATTRIB_FirstStageBuilt=1, distance=181)
        for roll, expected in ((0, True), (24, True), (25, False), (99, False)):
            vm, dancer, queries = self.choice_runtime([local, remote], roll)
            self.assertEqual(vm.call('Bards_Prize_Duel_Check', dancer, 25), expected)
            if expected:
                self.assertIs(dancer['Target'], local)
                self.assertEqual(dancer['Taskname'], 'Bards_Prize_Duel')
                self.assertIs(dancer['ActiveScript'], vm.calls['bards_prize_use'])
                self.assertEqual(queries, [('Building', 180, ('MyTeam', 'ATTRIB_FirstStageBuilt', 1))])
            else:
                self.assertEqual(queries, [])

    def test_remote_or_ineligible_venues_do_not_replace_ordinary_task(self):
        for fields in ({'distance': 181}, {'title': 'Marketplace'},
                       {'player': 2}, {'ATTRIB_FirstStageBuilt': 0}):
            venue = agent(**{'type': 'Building', 'title': 'Embassy', 'player': 1,
                             'ATTRIB_FirstStageBuilt': 1, 'distance': 50, **fields})
            vm, dancer, _ = self.choice_runtime([venue])
            previous = dancer['Target']
            self.assertFalse(vm.call('Bards_Prize_Duel_Check', dancer, 25))
            self.assertIs(dancer['Target'], previous)
            self.assertEqual(dancer['ActiveScript'], 'visit')

    def test_shared_arrival_and_retreat_remain_stock_outside_private_extensions(self):
        generated = dancer_systems(SDK, extract_function)
        for name, path, addition in (
            ('should_I_run', 'DecisionTrees/Modules/mx_target_eval.gpl',
             'if ($Bards_Roused_Stand(ThisAgent)) return FALSE;'),
            ('gettargetrange', 'TaskModules/Characters/mx_Travel_to.gpl',
             ' || (thisagent\'s "backscript" == $Bards_Prize_Use)'),
        ):
            actual = extract_function(generated, name)
            self.assertEqual(actual.count(addition), 1)
            expected = extract_function((SDK / 'GPLMx' / path).read_text(encoding='cp1252'), name)
            stock_equal(actual.replace(addition, ''), expected, name)
        visit = extract_function(generated, 'Bards_Prize_Visit')
        self.assertLess(visit.index('$Enter_Building'), visit.index('$SetThreadInterval'))
        self.assertLess(visit.index('$SetThreadInterval'), visit.index('= $Bards_Prize_Exit'))
        use = extract_function(generated, 'Bards_Prize_Use')
        self.assertIn('= $travel_to;', use)
        self.assertIn('= $Bards_Prize_Use;', use)
        self.assertIn('$hide(thisagent,target);', use)

    def runtime(self):
        source = (ROOT / 'src/gpl/Bards_Prize_Duel.gpl').read_text()
        generated = dancer_systems(SDK, extract_function)
        for name in ('Bards_Prize_Visit', 'Bards_Prize_Exit'):
            source += extract_function(generated, name)
        vm = ImpactHarness(re.sub(r'#(\w+)', r'"\1"', source))
        venue = agent(type='Building', title='Embassy', player=1, ATTRIB_FirstStageBuilt=1)
        dancer = agent(Target=venue, player=1, ActiveScript='visit', unlocked=True)
        events = []
        vm.calls.update({
            'notvalid': lambda a: a is None or not a.alive,
            'bards_jobs_unlocked': lambda a: a['unlocked'],
            'getattribute': lambda a, key: a.fields.get(key, 0),
            'getplayerteamnumber': lambda a: a['player'],
            'specifyintent': lambda *_: None,
            'enter_building': lambda *_: events.append('enter'),
            'exit_building': lambda *_: events.append('exit'),
            'setthreadinterval': lambda _, duration: events.append(('interval', duration)),
            'randomnumber': lambda n: 64,
            'give_gold': lambda _, amount: events.append(('gold', amount)),
            'give_exp': lambda _, amount: events.append(('xp', amount)),
            'insidebuilding': lambda _: True,
        })
        return vm, dancer, venue, events

    def test_65_percent_boundary_and_stock_exit_before_reward(self):
        for roll, reward in ((0, ('gold', 100)), (64, ('gold', 100)), (65, ('xp', 250)), (99, ('xp', 250))):
            vm, dancer, _, events = self.runtime()
            vm.calls['randomnumber'] = lambda n, value=roll: value
            vm.call('Bards_Prize_Visit', dancer)
            vm.call('Bards_Prize_Exit', dancer)
            self.assertEqual(events, ['enter', ('interval', 15000), ('interval', 'Normal_Cycle'), 'exit', reward])

    def test_destroyed_changed_owner_or_locked_home_cancels_without_reward(self):
        for case in ('dead', 'owner', 'locked'):
            vm, dancer, venue, events = self.runtime()
            if case == 'dead': venue.alive = False
            if case == 'owner': venue['player'] = 2
            if case == 'locked': dancer['unlocked'] = False
            vm.call('Bards_Prize_Exit', dancer)
            self.assertEqual(events, ['exit'])

    def test_venue_filters_do_not_require_a_visitor(self):
        vm, dancer, venue, _ = self.runtime()
        for title in ('Embassy', 'Fairgrounds', 'Adventurer_Guild'):
            venue['title'] = title
            self.assertTrue(vm.call('Bards_Prize_Venue', dancer, venue))
        venue['title'] = 'Guild'
        for member, expected in (('Warrior', True), ('Wizard', True), ('Healer', False), ('Troubadour', False)):
            venue['member_title'] = member
            self.assertEqual(vm.call('Bards_Prize_Venue', dancer, venue), expected)
        venue['ATTRIB_FirstStageBuilt'] = 0
        self.assertFalse(vm.call('Bards_Prize_Venue', dancer, venue))
