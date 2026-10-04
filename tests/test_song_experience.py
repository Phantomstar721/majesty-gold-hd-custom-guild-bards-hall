"""Reduced stock cast award once per completed useful song, not per recipient."""
import unittest
from test_hiring import ROOT, SDK, GPLSubset, agent
import test_marching_follow
from build_bards_hall import extract_function


class SongExperienceTests(unittest.TestCase):
    def test_quarter_stock_cast_formula_then_shared_give_exp(self):
        stock = (SDK / 'GPLMx/TaskModules/Subtasks/mx_Cast.gpl').read_text(encoding='cp1252')
        self.assertIn('#Healer_spell_exp_bonus', stock)
        source = extract_function((ROOT / 'src/gpl/Bards_Songs.gpl').read_text(), 'Bards_Song_Experience')
        vm = GPLSubset(source.replace('#spell_exp', '100'))
        levels = {'Bards_Valor': 1, 'Bards_March': 3, 'Bards_Satire': 5, 'Bards_Refrain': 8}
        awards = []
        vm.calls.update(getspellattribute=lambda s, _: levels[s], give_exp=lambda h, x: awards.append(x))
        for spell, level in levels.items():
            vm.call('Bards_Song_Experience', agent(), spell)
            self.assertEqual(awards[-1], 25 * level)

    def test_one_award_per_party_cast_and_none_on_cooldown_failure(self):
        for failed in (False, True):
            vm, bard, patron, events = test_marching_follow.MarchingFollowTests().runtime()
            vm.calls['bards_song_party'] = lambda _: [bard, patron, patron, patron]
            if failed: vm.calls['mm_commitspellcooldown'] = lambda *_: 0
            vm.call('Bards_Song_Complete', bard, 'Bards_March', 'Bards_March_Icon')
            self.assertEqual(sum(e[0] == 'xp' for e in events), 0 if failed else 1)


if __name__ == '__main__':
    unittest.main()
