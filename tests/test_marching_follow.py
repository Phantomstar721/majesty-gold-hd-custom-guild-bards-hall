"""Run authored follow/travel song eligibility and completion, without native motion."""
import unittest

from test_hiring import ROOT
from test_deflect import ImpactHarness
from test_guild_capacity import unit
from build_bards_hall import extract_function


class MarchingFollowTests(unittest.TestCase):
    def runtime(self, travel=True, moving=True):
        songs = (ROOT / 'src/gpl/Bards_Songs.gpl').read_text()
        rates = (ROOT / 'src/gpl/Bards_Rates.gpl').read_text()
        program = '\n'.join(extract_function(songs, name) for name in (
            'Bards_Can_Sing', 'Bards_Can_March', 'Bards_Try_Travel_Song',
            'Bards_Try_Song', 'Bards_Song_Useful', 'Bards_Song_Refresh',
            'Bards_Song_Complete'))
        program += extract_function(rates, 'Bards_March_Useful')
        vm = ImpactHarness(program)
        support, journey = lambda: None, lambda: None
        caster = unit(title='Troubadour', ActiveScript=journey if travel else support,
                      BackScript=support, moving=moving, BardsMarchWait=0)
        patron = unit(moving=moving)
        events = []
        vm.calls.update({
            'createeffector': lambda *_: None,
            'bards_follow_support': support, 'bards_travel_support': journey,
            'travel_to': lambda: None, 'travel_to_exp': lambda: None,
            'attack_object': lambda: None,
            'notvalid_attacker': lambda _: False,
            'bards_hire_guard': lambda _: False, 'bards_hall_supporting': lambda _: False, 'haslowhp': lambda _: False,
            'ismoving': lambda h: h['moving'], 'haswaypoints': lambda _: False,
            'checkeffector': lambda *_: False, 'mm_simulationelapsed': lambda _: 3000,
            'isspellavailable': lambda _, s: s == 'Bards_March',
            'bards_song_party': lambda _: [caster, patron],
            'mm_effectorremaining': lambda *_: 0,
            'mm_unitmovementbaseperiod': lambda _: 100,
            'bards_hero_engaged': lambda _: False,
            'bards_satire_target': lambda *_: None,
            'bards_song_wait_update': lambda *_: None,
            'performaction': lambda c, s, t: events.append(('action', s)),
            'mm_commitspellcooldown': lambda c, s: (events.append(('cooldown', s)), 1)[1],
            'bards_march_apply': lambda c, h: events.append(('apply', h)),
            'bards_song_finished': lambda c, s, p: events.append(('finished', s)),
            'bards_song_experience': lambda c, s: events.append(('xp', s)),
        })
        return vm, caster, patron, events

    def test_travel_and_moving_follow_dispatch_march_without_combat(self):
        for travel in (False, True):
            vm, caster, _, events = self.runtime(travel=travel)
            self.assertTrue(vm.call('Bards_Try_Travel_Song' if travel else 'Bards_Try_Song', caster))
            self.assertEqual(events, [('action', 'Bards_March')])

    def test_stationary_party_can_receive_march_before_next_step(self):
        vm, caster, _, events = self.runtime(travel=False, moving=False)
        self.assertTrue(vm.call('Bards_Try_Song', caster))
        self.assertEqual(events, [('action', 'Bards_March')])

    def test_catching_up_outside_party_radius_can_buff_self(self):
        vm, caster, _, events = self.runtime()
        vm.calls['bards_song_party'] = lambda _: [caster]
        self.assertTrue(vm.call('Bards_Try_Travel_Song', caster))
        vm.call('Bards_Song_Complete', caster, 'Bards_March', 'Bards_March_Icon')
        self.assertEqual(events, [('action', 'Bards_March'), ('cooldown', 'Bards_March'),
                                  ('apply', caster), ('finished', 'Bards_March'), ('xp', 'Bards_March')])

    def test_completion_buffs_caster_and_patron_once_without_combat(self):
        vm, caster, patron, events = self.runtime()
        vm.call('Bards_Song_Complete', caster, 'Bards_March', 'Bards_March_Icon')
        self.assertEqual(events, [('cooldown', 'Bards_March'), ('apply', caster),
                                  ('apply', patron), ('finished', 'Bards_March'), ('xp', 'Bards_March')])

    def test_solo_stock_travel_dispatch_and_completion(self):
        from test_hiring import SDK
        from bards_abilities import hiring_functions
        for task in ('travel_to', 'travel_to_exp'):
            vm, caster, _, events = self.runtime()
            caster['ActiveScript'] = vm.calls[task]
            caster['BackScript'] = 'ordinary-task'
            vm.calls['bards_song_party'] = lambda _: [caster]
            self.assertTrue(vm.call('Bards_Try_Travel_Song', caster))
            vm.call('Bards_Song_Complete', caster, 'Bards_March', 'Bards_March_Icon')
            self.assertEqual([e[0] for e in events], ['action', 'cooldown', 'apply', 'finished', 'xp'])
            events.clear()
            caster['BackScript'] = vm.calls['attack_object']
            self.assertFalse(vm.call('Bards_Try_Travel_Song', caster))
            vm.call('Bards_Song_Complete', caster, 'Bards_March', 'Bards_March_Icon')
            self.assertEqual(events, [])
        # Execute the actual stock entry point, including its fallback.
        entry = extract_function(hiring_functions(SDK, extract_function), 'TryTravelSpell')
        vm = ImpactHarness(entry.replace('#list_travel', '4'))
        calls = []
        vm.calls.update(haswaypoints=lambda _: False,
                        bards_try_travel_song=lambda _: True,
                        getbestspell=lambda *args: calls.append('fallback') or 'nothing')
        self.assertTrue(vm.call('TryTravelSpell', caster))
        self.assertEqual(calls, [])
        vm.calls['bards_try_travel_song'] = lambda _: False
        self.assertFalse(vm.call('TryTravelSpell', caster))
        self.assertEqual(calls, ['fallback'])

    def test_combat_or_other_travel_never_receives_follow_exception(self):
        for field in ('ActiveScript', 'BackScript'):
            vm, caster, _, events = self.runtime()
            caster[field] = 'unrelated-task'
            self.assertFalse(vm.call('Bards_Try_Travel_Song', caster))
            vm.call('Bards_Song_Complete', caster, 'Bards_March', 'Bards_March_Icon')
            self.assertEqual(events, [])

    def test_guards_cooldown_waypoints_and_existing_buff_prevent_dispatch(self):
        for call, result in (('notvalid_attacker', True), ('bards_hire_guard', True),
                             ('haslowhp', True), ('checkeffector', True),
                             ('isspellavailable', False), ('haswaypoints', True),
                             ('mm_effectorremaining', 8000)):
            vm, caster, _, events = self.runtime()
            vm.calls[call] = lambda *_, result=result: result
            self.assertFalse(vm.call('Bards_Try_Travel_Song', caster), call)
            self.assertEqual(events, [])

    def test_march_exception_does_not_allow_valor_during_movement(self):
        vm, caster, _, events = self.runtime()
        vm.call('Bards_Song_Complete', caster, 'Bards_Valor', 'Bards_Valor_Icon')
        self.assertEqual(events, [])

    def test_accepted_guild_support_can_cast_without_private_task_identity(self):
        vm, caster, _, events = self.runtime()
        caster['ActiveScript'] = caster['BackScript'] = 'guild-support'
        vm.calls['bards_hall_supporting'] = lambda h: True
        self.assertTrue(vm.call('Bards_Try_Travel_Song', caster))
        vm.call('Bards_Song_Complete', caster, 'Bards_March', 'Bards_March_Icon')
        self.assertEqual(sum(event[0] == 'xp' for event in events), 1)


if __name__ == '__main__':
    unittest.main()
