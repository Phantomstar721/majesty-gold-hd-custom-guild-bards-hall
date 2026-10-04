"""Execute the authored GPL selection/refresh branches with mocked native reads.

Uses the workspace Manager's small GPL harness read-only. This does not emulate
native action scheduling, damage, effect cleanup, serialization or animation.
"""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT.parent / 'majesty-gold-hd-cam-merger'
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(MANAGER / 'src'))
from build_bards_hall import extract_function

spec = importlib.util.spec_from_file_location('bards_selection_harness', MANAGER / 'tests/gpl_sampler_harness.py')
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
SOURCE = (ROOT / 'src/gpl/Bards_Songs.gpl').read_text()


class SongSelectionTests(unittest.TestCase):
    def selection(self):
        program = '\n'.join(extract_function(SOURCE, name) for name in ('Bards_Try_Song', 'Bards_Song_Wait_Update'))
        vm = harness.SamplerHarness(program)
        caster, enemy = harness.Agent(), harness.Agent()
        actions = []
        vm.calls.update({
            'checkeffector': lambda *_: False,
            'bards_can_sing': lambda _: True,
            'bards_try_travel_song': lambda _: False,
            'bards_song_party': lambda _: [],
            'bards_song_useful': lambda _, party, song: song != 'Bards_Refrain',
            'bards_satire_target': lambda _, party: enemy,
            'isspellavailable': lambda _, song: True,
            'performaction': lambda _, song, target: actions.append(song),
        })
        return vm, caster, actions

    def test_continuously_useful_songs_wait_at_most_two_other_completions(self):
        vm, caster, actions = self.selection()
        waits = dict.fromkeys(('Bards_Valor', 'Bards_Satire', 'Bards_March'), 0)
        for _ in range(15):
            self.assertTrue(vm.call('Bards_Try_Song', caster))
            selected = actions[-1]
            for song in waits:
                waits[song] = 0 if song == selected else waits[song] + 1
                self.assertLessEqual(waits[song], 2, (actions, song))
            vm.call('Bards_Song_Wait_Update', caster, selected, True, True, True)

    def test_irrelevant_song_is_not_forced_by_old_wait(self):
        vm, caster, actions = self.selection()
        vm.call('Bards_Song_Wait_Update', caster, 'Bards_Valor', True, True, True)
        vm.call('Bards_Song_Wait_Update', caster, 'Bards_Valor', True, True, True)
        vm.calls['bards_song_useful'] = lambda _, party, song: song == 'Bards_Valor'
        vm.calls['bards_satire_target'] = lambda _, party: None
        vm.call('Bards_Try_Song', caster)
        self.assertEqual(actions, ['Bards_Valor'])
        self.assertEqual(caster['BardsMarchWait'], 0)
        self.assertEqual(caster['BardsSatireWait'], 0)

    def test_available_refrain_precedes_ordinary_wait_and_does_not_age_it(self):
        vm, caster, actions = self.selection()
        vm.call('Bards_Song_Wait_Update', caster, 'Bards_Valor', True, True, True)
        before = dict(caster.fields)
        vm.calls['bards_song_useful'] = lambda *_: True
        vm.call('Bards_Try_Song', caster)
        self.assertEqual(actions, ['Bards_Refrain'])
        self.assertEqual(caster.fields, before)

    def test_inactive_or_personally_fighting_caster_dispatches_nothing(self):
        vm, caster, actions = self.selection()
        vm.calls['bards_can_sing'] = lambda _: False
        self.assertFalse(vm.call('Bards_Try_Song', caster))
        self.assertEqual(actions, [])

    def test_countermelody_prevents_new_song_dispatch(self):
        vm, caster, actions = self.selection()
        vm.calls['checkeffector'] = lambda *_: True
        self.assertFalse(vm.call('Bards_Try_Song', caster))
        self.assertEqual(actions, [])

    def test_refresh_rejects_negative_status_and_indefinite_effect(self):
        vm = harness.SamplerHarness(extract_function(SOURCE, 'Bards_Song_Refresh'))
        for remaining in (-4, -3, -2, -1, 0, 1, 1999, 2000, 2001, 8000):
            vm.calls['mm_effectorremaining'] = lambda *_: remaining
            with self.subTest(remaining=remaining):
                self.assertEqual(vm.call('Bards_Song_Refresh', harness.Agent(), 'Bards_Valor_Icon'), 0 <= remaining <= 2000)


if __name__ == '__main__':
    unittest.main()
