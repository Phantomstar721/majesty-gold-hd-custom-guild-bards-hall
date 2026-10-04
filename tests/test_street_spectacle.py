"""Exercise actual performance GPL and shared duration ledger, without a profile."""
import re
import unittest
from test_hiring import ROOT, agent, SDK
from test_deflect import ImpactHarness
from build_bards_hall import extract_function
from majesty_cam.activity_time import activity_source
from majesty_cam.shared_composition import SharedBinding
from majesty_cam.shared_features import StockActivityDuration
from bard_job_harness import home, job_source


class SpectacleTests(unittest.TestCase):
    def runtime(self):
        program = (ROOT / 'src/gpl/Bards_Street.gpl').read_text() + job_source(False)
        hiring = (ROOT / 'src/gpl/Bards_Hiring.gpl').read_text()
        for name in ('Bards_Hire_Alive', 'Bards_Is_Bard', 'Bards_Hire_Guild', 'Bards_Hire_Assigned'):
            program += extract_function(hiring, name)
        features = tuple(SharedBinding('bards', StockActivityDuration(key, prefix,
            callback + '_Condition', callback + '_Completed', callback + '_Cancelled'))
            for key, prefix, callback in (('bards-street-show', 'Bards_Show', 'Bards_Street_Show'),
                                         ('bards-street-audience', 'Bards_Audience', 'Bards_Street_Audience')))
        program += activity_source(features)
        vm = ImpactHarness(re.sub(r'#(\w+)', r'"\1"', program))
        singer = agent(title='Spellsinger', subtype='Hero', player=1, ATTRIB_HP=50,
                       ATTRIB_Gold=0, ATTRIB_SightRange=250, ActiveScript='ordinary', StartingScript='ordinary', Home=home())
        singer['evaluationscript'] = lambda _: False
        town = agent(title='Marketplace', player=1, ATTRIB_HP=500, ATTRIB_FirstStageBuilt=1)
        hero = agent(title='Warrior', subtype='Hero', player=1, ATTRIB_HP=50, ATTRIB_Gold=53)
        peasant = agent(title='Peasant', subtype='henchman', player=1, ATTRIB_HP=50, ATTRIB_Gold=1000)
        nearby, enemies, clock, events = [hero, peasant], [], [100000], []
        def list_objects(caster, kind, radius, result, *args):
            result.extend([town] if kind == 'Building' else nearby)
            return len(result)
        vm.calls.update({
            'createeffector': lambda *_: None,
            'getattribute': lambda a, key: a.fields.get(key, 0),
            'adjustattribute': lambda a, key, delta: a.fields.__setitem__(key, a.fields.get(key, 0) + delta),
            'getunitplayernumber': lambda a: a['player'],
            'insidebuilding': lambda a: a.fields.get('inside', False),
            'ismoving': lambda a: a.fields.get('moving', False),
            'isfrozen': lambda a: a.fields.get('frozen', False),
            'haslowhp': lambda a: a['ATTRIB_HP'] < 20,
            'notvalid_attacker': lambda a: not a.alive,
            'distancebetweenagents': lambda a, b: b.fields.get('distance', 20),
            'listobjects': list_objects,
            'list_enemies_seen': lambda *_: enemies,
            'randomnumber': lambda _: 0,
            'mm_simulationtime': lambda: clock[0],
            'mm_simulationelapsed': lambda t: (clock[0] - t) & 0xffffffff,
            'specifyintent': lambda *args: None,
            'reset_tasks': lambda a: (a.fields.__setitem__('ActiveScript', a['StartingScript']), events.append(('reset', a))),
            'check_rewards': lambda *_: False,
            'defend_home': lambda *_: False,
            'performaction': lambda *args: events.append(('play', args[0])),
            'give_gold': lambda a, amount: (a.fields.__setitem__('ATTRIB_Gold', a['ATTRIB_Gold'] + amount), events.append(('gold', amount))),
            'give_exp': lambda a, amount: events.append(('xp', amount)),
        })
        return vm, singer, town, hero, peasant, nearby, enemies, clock, events

    def start(self):
        state = self.runtime()
        vm, singer = state[:2]
        self.assertTrue(vm.call('Bards_Street_Check', singer))
        vm.call('Bards_Street_Perform', singer)
        vm.call('Bards_Street_Phrase', singer, singer)
        return state

    @staticmethod
    def tick(vm, clock, count):
        for _ in range(count):
            clock[0] += 1000
            vm.tick()

    def test_gestures_alternate_once_per_phrase_with_standing_gaps(self):
        vm, singer, _, _, _, _, _, clock, _ = self.runtime()
        gestures, flashes = [], []
        vm.calls['performaction'] = lambda a, name, target: gestures.append(name)
        vm.calls['createeffector'] = lambda a, name, duration: flashes.append(name)
        self.assertTrue(vm.call('Bards_Street_Check', singer))
        for elapsed, expected in ((0, 1), (100, 1), (2000, 1), (3999, 1),
                                  (4000, 2), (6000, 2), (8000, 3), (10000, 3),
                                  (12000, 4), (14000, 4), (16000, 5), (19999, 5),
                                  (20000, 5)):
            clock[0] = 100000 + elapsed
            vm.call('Bards_Street_Perform', singer)
            self.assertEqual(len(gestures), expected, elapsed)
        self.assertEqual(gestures, ['Bards_Street_Attack', 'Bards_Street_Cast',
                                   'Bards_Street_Attack', 'Bards_Street_Cast', 'Bards_Street_Play'])
        # Cast supplies its notes from the native sprite secondary stream;
        # only the two Attack gestures need a separate flash effector.
        self.assertEqual(flashes, ['Bards_Song_Flash'] * 2)

    def test_old_saved_performance_can_resume_without_a_beat_attribute(self):
        vm, singer, _, _, _, _, enemies, clock, events = self.start()
        del singer.fields['BardsStreetBeat']
        clock[0] += 9000
        vm.call('Bards_Street_Perform', singer)
        self.assertEqual(singer['BardsStreetBeat'], 2)
        enemies.append(agent(title='Rat', player=2, ATTRIB_HP=10))
        vm.call('Bards_Street_Perform', singer)
        self.assertFalse(singer['BardsStreetActive'])
        self.assertEqual(singer['ActiveScript'], 'ordinary')

    def test_real_dwell_settles_one_affordable_tip_and_public_tip(self):
        vm, singer, _, hero, peasant, _, _, clock, events = self.start()
        self.tick(vm, clock, 3)
        self.assertEqual(singer['ATTRIB_Gold'], 0)
        self.tick(vm, clock, 1)
        self.assertEqual((hero['ATTRIB_Gold'], peasant['ATTRIB_Gold'], singer['ATTRIB_Gold']), (50, 1000, 4))
        self.assertEqual(sum(e[1] for e in events if e[0] == 'xp'), 10)
        vm.call('Bards_Street_Phrase', singer, singer)
        self.tick(vm, clock, 5)
        self.assertEqual(singer['ATTRIB_Gold'], 4)
        self.assertEqual(singer['BardsStreetCount'], 2)

    def test_partial_state_from_rejected_town_type_can_start_next_show(self):
        vm, singer, town, *_ = self.runtime()
        # Captured native state: all scalar/list fields exist, but the old
        # "agent" allocation failed and execution stopped at the town write.
        singer.fields.update(BardsStreetActive=False, BardsStreetStartedAt=0,
                             BardsStreetPlayer=1, BardsStreetHP=0,
                             BardsStreetAudience=[], BardsStreetCount=0,
                             BardsStreetGold=0)
        self.assertNotIn('BardsStreetTown', singer.fields)
        self.assertTrue(vm.call('Bards_Street_Check', singer))
        self.assertIs(singer['BardsStreetTown'], town)
        self.assertEqual(singer['BardsStreetHP'], singer['ATTRIB_HP'])
        self.assertTrue(vm.call('Bards_Street_Active', singer))

    def test_home_tier_locks_start_and_cancels_pending_tips_after_rehousing(self):
        for level, complete in ((1, True), (1, False)):
            vm, singer, *_ = self.runtime()
            singer['Home'] = home(level, complete=complete)
            self.assertFalse(vm.call('Bards_Street_Check', singer))
            self.assertNotIn('BardsStreetActive', singer.fields)
        vm, singer, _, hero, _, _, _, clock, events = self.start()
        singer['Home'] = home(1)
        vm.call('Bards_Street_Service', singer)
        self.tick(vm, clock, 4)
        self.assertFalse(singer['BardsStreetActive'])
        self.assertIsNone(hero['BardsStreetHost'])
        self.assertEqual(hero['ATTRIB_Gold'], 53)
        self.assertFalse(any(event[0] in ('gold', 'xp') for event in events))

    def test_leaving_restarts_dwell_and_insufficient_money_cannot_be_charged(self):
        vm, singer, _, hero, peasant, nearby, _, clock, _ = self.start()
        self.tick(vm, clock, 2)
        hero['distance'] = 101
        peasant['inside'] = True
        vm.call('Bards_Street_Phrase', singer, singer)
        self.assertIsNone(hero['BardsStreetHost'])
        hero['distance'] = 20
        vm.call('Bards_Street_Phrase', singer, singer)
        self.tick(vm, clock, 3)
        self.assertEqual(singer['ATTRIB_Gold'], 0)
        hero['ATTRIB_Gold'] = 52
        self.tick(vm, clock, 2)
        self.assertEqual((singer['ATTRIB_Gold'], hero['ATTRIB_Gold']), (0, 52))

    def test_shared_listener_claim_and_daily_cooldown_prevent_overlapping_collection(self):
        vm, singer, _, hero, _, _, _, clock, _ = self.start()
        second = agent(**singer.fields)
        second['BardsStreetAudience'] = []
        second['BardsStreetCount'] = second['BardsStreetGold'] = second['ATTRIB_Gold'] = 0
        vm.call('Bards_Street_Phrase', second, second)
        self.assertEqual(second['BardsStreetAudience'], [])
        self.tick(vm, clock, 4)
        hero['ATTRIB_Gold'] = 100
        vm.call('Bards_Street_Phrase', second, second)
        self.assertEqual(second['BardsStreetAudience'], [])
        self.assertEqual(second['ATTRIB_Gold'], 0)

    def test_interruption_keeps_earned_credit_and_preserves_new_combat_task(self):
        vm, singer, town, hero, _, _, _, clock, events = self.start()
        self.tick(vm, clock, 4)
        key = hero['BardsStreetKey']
        singer['ActiveScript'] = 'combat'
        vm.call('Bards_Street_Service', singer)
        vm.call('Bards_Street_Audience_Completed', hero, singer, town, key)
        self.assertEqual(singer['ActiveScript'], 'combat')
        self.assertEqual(singer['ATTRIB_Gold'], 4)
        self.assertFalse(singer['BardsStreetActive'])
        self.assertEqual(vm.call('Bards_Show_State', singer, 1), 0)

    def test_end_damage_death_and_ownership_change_never_pay_pending_audience(self):
        for mode in ('damage', 'death', 'owner', 'town-owner', 'threat'):
            vm, singer, town, hero, _, _, enemies, clock, _ = self.start()
            if mode == 'damage': singer['ATTRIB_HP'] -= 1
            if mode == 'death': singer.alive = False
            if mode == 'owner': singer['player'] = 2
            if mode == 'town-owner': town['player'] = 2
            if mode == 'threat': enemies.append(agent())
            vm.call('Bards_Street_Perform', singer)
            self.tick(vm, clock, 4)
            self.assertEqual(singer['ATTRIB_Gold'], 0, mode)
            self.assertEqual(hero['ATTRIB_Gold'], 53, mode)

    def test_failed_start_and_busy_cancel_leave_no_paid_or_reusable_claim(self):
        for result in (0, -1, -2, -3):
            vm, singer, *_ = self.runtime()
            vm.calls['bards_show_start'] = lambda *_, result=result: result
            self.assertFalse(vm.call('Bards_Street_Check', singer))
            self.assertNotIn('BardsStreetActive', singer.fields)
        vm, singer, _, hero, _, _, _, clock, _ = self.start()
        vm.root['MM_ActivityBusy_v1'] = True
        vm.call('Bards_Street_End', singer)
        self.assertFalse(singer['BardsStreetActive'])
        self.assertFalse(vm.call('Bards_Street_Check', singer))
        self.assertIs(hero['BardsStreetHost'], singer)
        vm.root['MM_ActivityBusy_v1'] = False
        vm.call('Bards_Street_Service', singer)
        self.assertIsNone(hero['BardsStreetHost'])
        self.assertEqual(vm.call('Bards_Show_State', singer, 1), 0)

    def test_session_caps_and_empty_show_have_no_repeat_or_free_xp(self):
        vm, singer, _, hero, _, nearby, _, clock, events = self.runtime()
        nearby[:] = [agent(**hero.fields) for _ in range(20)]
        self.assertTrue(vm.call('Bards_Street_Check', singer))
        vm.call('Bards_Street_Phrase', singer, singer)
        self.assertEqual(len(singer['BardsStreetAudience']), 10)
        self.tick(vm, clock, 4)
        vm.call('Bards_Street_Phrase', singer, singer)
        self.assertEqual(singer['ATTRIB_Gold'], 30)
        self.assertEqual(sum(e[1] for e in events if e[0] == 'xp'), 50)
        vm, singer, _, _, _, nearby, _, clock, events = self.runtime()
        nearby.clear()
        self.assertTrue(vm.call('Bards_Street_Check', singer))
        vm.call('Bards_Street_Phrase', singer, singer)
        self.tick(vm, clock, 21)
        self.assertFalse(singer['BardsStreetActive'])
        self.assertFalse(any(e[0] in ('gold', 'xp') for e in events))

    def test_nonpaying_or_foreign_audience_exclusions(self):
        vm, singer, _, hero, _, *_ = self.runtime()
        for fields in ({'player': 2}, {'title': 'Caravan'}, {'title': 'Tax_Collector'},
                       {'title': 'Troubadour'}, {'subtype': 'Controlled'}, {'inside': True}):
            listener = agent(**{**hero.fields, **fields})
            self.assertFalse(vm.call('Bards_Street_Listener', singer, listener), fields)

    def test_stale_terminal_callback_cannot_release_or_pay_a_new_listener_claim(self):
        vm, singer, town, hero, _, _, _, _, _ = self.start()
        old_key = hero['BardsStreetKey']
        vm.call('Bards_Audience_Cancel', hero, old_key)
        vm.call('Bards_Street_Phrase', singer, singer)
        self.assertGreater(hero['BardsStreetKey'], old_key)
        vm.call('Bards_Street_Audience_Completed', hero, singer, town, old_key)
        vm.call('Bards_Street_Audience_Cancelled', hero, singer, town, old_key, 1)
        self.assertIs(hero['BardsStreetHost'], singer)
        self.assertEqual(hero['ATTRIB_Gold'], 53)

    def test_reentrant_reward_callback_does_not_pay_twice(self):
        vm, singer, town, hero, peasant, nearby, _, clock, events = self.start()
        peasant['inside'] = True
        vm.calls['give_exp'] = lambda *_: vm.call('Bards_Street_Audience_Completed', hero, singer, town, hero['BardsStreetKey'])
        self.tick(vm, clock, 4)
        self.assertEqual(singer['ATTRIB_Gold'], 3)
        self.assertEqual(hero['ATTRIB_Gold'], 50)


if __name__ == '__main__':
    unittest.main()
