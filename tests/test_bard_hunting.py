"""Execute emitted hunt decisions against distance, suitability and class cases."""
import re
import unittest

from test_hiring import SDK, agent
from test_deflect import ImpactHarness
from build_bards_hall import extract_function
from bards_heroes import bard_hunting


class BardHuntingTests(unittest.TestCase):
    def runtime(self, candidates):
        program = bard_hunting(SDK, extract_function).replace('#champs_mod', '30')
        program = re.sub(r'#(\w+)', r'"\1"', program)
        vm = ImpactHarness(program)
        queries, intents = [], []

        def objects(bard, kind, radius, result, *filters):
            queries.append((kind, radius, filters))
            result.extend(c for c in candidates if c['type'] == kind and c.alive
                          and c['enemy'] and
                          ('CheckSubtypes' not in filters or c['subtype'].lower() == 'hero'))

        vm.calls.update(listobjects=objects, randomnumber=lambda _: 0,
                        target_eval=lambda _, c: c['score'],
                        distancebetweenagents=lambda _, c: c['distance'],
                        checkeffector=lambda c, _: c['champion'],
                        specifyintent=lambda _, intent: intents.append(intent),
                        attack_object=lambda _: None)
        return vm, queries, intents

    def candidate(self, distance, score=10, kind='monster', subtype='Animal',
                  champion=False, enemy=True, alive=True):
        result = agent(distance=distance, score=score, type=kind, subtype=subtype,
                       champion=champion, enemy=enemy)
        result.alive = alive
        return result

    def test_nearest_viable_target_wins_over_distant_easy_target_for_any_bard(self):
        distant = self.candidate(4900, score=300)
        dangerous = self.candidate(10, score=-5)
        nearby = self.candidate(300, score=8)
        for title in ('Spellsinger', 'Blade_Dancer', 'Troubadour'):
            vm, queries, _ = self.runtime([distant, dangerous, nearby])
            bard = agent(title=title)
            self.assertTrue(vm.call('Bards_combat_wandering', bard, 95))
            self.assertIs(bard['target'], nearby)
            self.assertIs(bard['activescript'], vm.calls['attack_object'])
            self.assertEqual(queries[0][1], -1)

    def test_civilians_allies_and_dead_targets_are_not_ordinary_hero_hunts(self):
        peasant = self.candidate(10, 500, 'hero', 'Henchman')
        taxman = self.candidate(20, 500, 'hero', 'Henchman')
        ally = self.candidate(30, 100, 'hero', 'Hero', enemy=False)
        corpse = self.candidate(40, 100, 'hero', 'Hero', alive=False)
        distant = self.candidate(4900, 500, 'hero', 'Hero')
        nearby = self.candidate(500, 8, 'hero', 'Hero')
        vm, queries, _ = self.runtime([peasant, taxman, ally, corpse, distant, nearby])
        bard = agent()
        self.assertTrue(vm.call('Bards_combat_wandering_heroes', bard, 55))
        self.assertIs(bard['target'], nearby)
        self.assertIn('NotMyTeam', queries[0][2])
        self.assertEqual(queries[0][2][-2:], ('CheckSubtypes', 'Hero'))

    def test_champion_call_priority_still_uses_nearest_viable_champion(self):
        ordinary = self.candidate(10)
        distant = self.candidate(4000, champion=True)
        nearby = self.candidate(900, champion=True)
        unsuitable = self.candidate(200, score=-100, champion=True)
        vm, _, intents = self.runtime([ordinary, distant, nearby, unsuitable])
        bard = agent()
        self.assertTrue(vm.call('Bards_combat_wandering', bard, 95))
        self.assertIs(bard['target'], nearby)
        self.assertEqual(intents, ['Intent_Heeding_Champion_call'])

    def test_no_viable_target_declines_without_replacing_existing_task(self):
        for name, candidates in (
            ('Bards_combat_wandering', [self.candidate(100, score=0)]),
            ('Bards_combat_wandering_heroes', [self.candidate(100, 50, 'hero', 'Henchman')]),
        ):
            vm, _, intents = self.runtime(candidates)
            previous = agent()
            bard = agent(target=previous, activescript='existing')
            self.assertFalse(vm.call(name, bard, 100))
            self.assertIs(bard['target'], previous)
            self.assertEqual(bard['activescript'], 'existing')
            self.assertEqual(intents, [])


if __name__ == '__main__':
    unittest.main()
