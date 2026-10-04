"""Preserve first-match decisions while returning outside native foreach loops."""
import re
import unittest

from test_hiring import ROOT, agent
from test_deflect import ImpactHarness
from build_bards_hall import extract_function
from majesty_cam.gpl import find_foreach_return_violations


def runtime(file, name):
    source = (ROOT / 'src/gpl' / file).read_text()
    vm = ImpactHarness(re.sub(r'#(\w+)', r'"\1"', extract_function(source, name)))
    vm.calls['getattribute'] = lambda a, key: a.fields.get(key, 0)
    return vm


class SelectionTests(unittest.TestCase):
    def test_burst_accepts_one_enemy_but_not_empty_or_suppressed(self):
        for count, suppressed, expected in ((0, False, 0), (1, False, 1), (2, False, 1), (1, True, 0)):
            vm = runtime('Bards_Spellsinger.gpl', 'Bards_Resonant_Burst_Check')
            vm.calls.update({'checkeffector': lambda *_: suppressed, 'notvalid': lambda _: False,
                'bards_burst_targets': lambda *_: [agent() for _ in range(count)]})
            self.assertEqual(vm.call('Bards_Resonant_Burst_Check', agent(Target=agent())), expected)


    def test_authored_sources_obey_engine_foreach_return_constraint(self):
        for path in (ROOT / 'src/gpl').glob('*.gpl'):
            self.assertEqual(find_foreach_return_violations(path.read_text(), str(path)), (), path.name)

    def test_hiring_prefers_first_local_match_then_first_local_fallback(self):
        fallback = agent(title='Troubadour', available=True)
        unavailable = agent(title='Blade_Dancer', available=False)
        preferred = agent(title='Blade_Dancer', available=True)
        later = agent(title='Blade_Dancer', available=True)
        cases = (([], None, []), ([unavailable], None, [unavailable]),
                 ([fallback, unavailable], fallback, [fallback, unavailable]),
                 ([fallback, unavailable, preferred, later], preferred,
                  [fallback, unavailable, preferred, later]))
        for members, expected, checked in cases:
            vm = runtime('Bards_Hiring.gpl', 'Bards_Hire_Choose')
            visited = []
            vm.calls.update({
                'bards_hire_guild': lambda *_: True,
                'bards_hire_preference': lambda *_: 'Blade_Dancer',
                'bards_hire_available': lambda b, *_: (visited.append(b), b['available'])[1],
                'insidebuilding': lambda _: False,
                'distancebetweenagents': lambda *_: 100,
            })
            self.assertIs(vm.call('Bards_Hire_Choose', agent(), agent(Members=members)), expected)
            self.assertEqual(visited, checked)

    def test_hiring_rolls_once_at_first_eligible_guild_even_when_declined(self):
        for roll, expected in ((0, True), (24, True), (25, False), (99, False)):
            vm = runtime('Bards_Hiring.gpl', 'Bards_Hire_Check')
            patron = agent(ActiveScript='ordinary', StartingScript='ordinary')
            bard = agent()
            guilds = [agent(bard=None), agent(bard=bard), agent(bard=bard)]
            visits, rolls, intents = [], [], []
            use_building = lambda: None
            vm.calls.update({
                'bards_hire_patron_free': lambda _: True,
                'insidebuilding': lambda _: False,
                'ismoving': lambda _: False,
                'bards_hire_choose': lambda _, g: (visits.append(g), g['bard'])[1],
                'mm_simulationtime': lambda: 123456,
                'randomnumber': lambda limit: (rolls.append(limit), roll)[1],
                'use_building': use_building,
                'specifyintent': lambda *args: intents.append(args),
            })
            self.assertEqual(vm.call('Bards_Hire_Check', patron, guilds), expected)
            self.assertEqual(visits, guilds[:2])
            self.assertEqual(rolls, [100])
            self.assertEqual(patron['BardsHireConsideredAt'], 123456)
            if expected:
                self.assertIs(patron['Target'], guilds[1])
                self.assertIs(patron['ActiveScript'], use_building)
                self.assertEqual(len(intents), 1)
            else:
                self.assertNotIn('Target', patron.fields)
                self.assertEqual(patron['ActiveScript'], 'ordinary')
                self.assertEqual(intents, [])

    def test_songs_require_eligible_ally_and_stop_native_queries_at_first_match(self):
        for song, predicate in (('Refrain', 'bards_song_engaged'),
                                ('March', 'bards_march_useful'),
                                ('Valor', 'bards_song_engaged')):
            vm = runtime('Bards_Songs.gpl', 'Bards_Song_Useful')
            caster, fresh, idle, useful, later = [agent() for _ in range(5)]
            refreshed, evaluated = [], []
            vm.calls.update({
                'bards_song_refresh': lambda h, _: (refreshed.append(h), h is not fresh)[1],
                predicate: lambda h: (evaluated.append(h), h is useful)[1],
            })
            for party in ([], [caster], [caster, fresh, idle]):
                self.assertFalse(vm.call('Bards_Song_Useful', caster, party, 'Bards_' + song))
            refreshed.clear()
            evaluated.clear()
            self.assertTrue(vm.call('Bards_Song_Useful', caster,
                                    [caster, fresh, idle, useful, later], 'Bards_' + song))
            self.assertEqual(refreshed, ([caster] if song == 'March' else []) + [fresh, idle, useful])
            self.assertEqual(evaluated, ([caster] if song == 'March' else []) + [idle, useful])

    def test_bounty_requires_positive_amount_on_exact_target(self):
        target, other = agent(), agent()
        zero = agent(ATTRIB_RewardCost=0, ATTRIB_TargetID=target)
        wrong = agent(ATTRIB_RewardCost=100, ATTRIB_TargetID=other)
        one = agent(ATTRIB_RewardCost=1, ATTRIB_TargetID=target)
        for flags, expected in (([], False), ([zero, wrong], False), ([zero, wrong, one], True)):
            vm = runtime('Bards_Renown.gpl', 'Bards_Renown_Has_Bounty')
            vm.calls.update({
                'listobjects': lambda a, kind, radius, output, *args: output.extend(flags),
                'agentnumber': lambda identity: identity,
            })
            self.assertEqual(vm.call('Bards_Renown_Has_Bounty', target), expected)

    def test_street_chooses_first_completed_living_town_building(self):
        dead = agent(title='Marketplace', ATTRIB_FirstStageBuilt=1)
        dead.alive = False
        incomplete = agent(title='Palace', ATTRIB_FirstStageBuilt=0)
        wrong = agent(title='Blacksmith', ATTRIB_FirstStageBuilt=1)
        first = agent(title='Bards_Hall', ATTRIB_FirstStageBuilt=1)
        later = agent(title='Marketplace', ATTRIB_FirstStageBuilt=1)
        for buildings, expected in (([], None), ([dead, incomplete, wrong], None),
                                    ([dead, incomplete, wrong, first, later], first)):
            vm = runtime('Bards_Street.gpl', 'Bards_Street_Town')
            checked = []
            vm.calls.update({
                'listobjects': lambda a, kind, radius, output, *args: output.extend(buildings),
                'bards_hire_alive': lambda b: (checked.append(b), b.alive)[1],
            })
            self.assertIs(vm.call('Bards_Street_Town', agent()), expected)
            self.assertNotIn(later, checked)


if __name__ == '__main__':
    unittest.main()
