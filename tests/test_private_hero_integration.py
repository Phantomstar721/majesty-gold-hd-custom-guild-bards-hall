"""Exercise Bards declarations against Manager's pure source transforms.

These tests never prepare a merged package/profile or modify another mod.
"""
import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET

from test_hiring import ROOT, SDK, GPLSubset, agent
from build_bards_hall import build_units, extract_function
from bards_abilities import build_descriptions
from bards_recruitment_panel import manager_features

sys.path.insert(0, str(ROOT.parent / 'majesty-gold-hd-cam-merger/src'))
from majesty_cam.gpl import SemanticMergeResult, parse_gpl, add_hero_quest_lifecycle_callbacks
from majesty_cam.gpl_features import parse_gpl_feature
from majesty_cam.private_hero_gpl import validate_bindings, add_spell_evaluation_equivalents


class PrivateHeroIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.features = tuple(parse_gpl_feature(f) for f in manager_features()
                             if f['type'] in {'stock.hero-quest-participant.v1',
                                              'stock.spell-evaluation-equivalent.v1'})
        cls.trees = parse_gpl((ROOT / 'src/gpl/Bards_Hero_Trees.gpl').read_text(), 'Bards trees')
        descriptions = (*ET.fromstring(build_units(SDK)), *build_descriptions(SDK))
        cls.private, cls.spells = validate_bindings([('Bards', cls.features, (cls.trees,), descriptions)])
        cls.stock_trees = {}
        for stock, title in (('mx_healer', 'Healer'), ('mx_cultist', 'Cultist'), ('mx_ranger', 'Ranger')):
            source = (SDK / ('GPLMx/DecisionTrees/' + stock + '.gpl')).read_text(encoding='cp1252')
            cls.stock_trees[stock] = parse_gpl(extract_function(source, title + '_tree'), stock).items[0]
        guild = ROOT.parent / 'majesty-gold-hd-adventurers-guild/src'
        cls.provider = next(f for f in json.loads((guild / 'package/mod-definition.json').read_text())['runtime_features']
                            if f['type'] == 'stock.hero-quest-lifecycle.v1')
        cls.symbols = [cls.provider[field] for field in ('resume_callback_symbol', 'consider_callback_symbol',
                                                       'reset_callback_symbol', 'death_callback_symbol')]
        source = (guild / 'gpl/Adventurer_Guild_Core.gpl').read_text()
        callbacks = '\n'.join(extract_function(source, name) for name in cls.symbols)
        for path, symbol in (('mx_LowLevel.gpl', 'reset_tasks'), ('mx_Hero_Deaths.gpl', 'Unit_Call_Deathscript')):
            callbacks += '\n' + extract_function((SDK / 'GPLMx' / path).read_text(encoding='cp1252'), symbol)
        cls.callbacks = parse_gpl(callbacks, 'quest lifecycle reference').items
        cls.original = SemanticMergeResult(cls.trees.items, ())

    def test_bards_without_quest_provider_remain_independent(self):
        result = add_hero_quest_lifecycle_callbacks(self.original, (), stock_hero_trees=self.stock_trees,
                                                   private_hero_trees=self.private)
        self.assertIs(result, self.original)
        self.assertNotIn('Adventurer_Guild_', ''.join(item.text for item in result.items))

    def integrated(self):
        return add_hero_quest_lifecycle_callbacks(
            SemanticMergeResult((*self.original.items, *self.callbacks), ()),
            [(self.provider['hero_scripts'], *self.symbols)],
            stock_hero_trees=self.stock_trees, private_hero_trees=self.private)

    def test_all_three_receive_resume_and_consider_without_duplicate_cleanup(self):
        # Limit the reference provider selection to its three Bards analogues;
        # unrelated stock trees belong to Manager's own lifecycle tests.
        provider_scripts = self.provider['hero_scripts']
        try:
            self.provider['hero_scripts'] = tuple(self.stock_trees)
            result = self.integrated()
        finally:
            self.provider['hero_scripts'] = provider_scripts
        for title in ('Troubadour', 'Spellsinger', 'Blade_Dancer'):
            item = next(i for i in result.items if i.name == 'Bards_' + title + '_Tree')
            text = item.text.lower()
            resume, consider = ('$' + name.lower() for name in self.symbols[:2])
            self.assertLess(text.index('$bards_hire_guard'), text.index('$check_nearby'))
            self.assertLess(text.index('$check_nearby'), text.index(resume))
            self.assertLess(text.index(resume), text.index('$check_rewards'))
            anchor = '$purchase_bazaar' if title == 'Troubadour' else '$pursue_entertainment'
            self.assertLess(text.index(anchor), text.index(consider))
            self.assertLess(text.index(consider), text.index('$go_home'))
            # Execute the real transformed decision cascade with all earlier
            # choices declining; provider TRUE must own the task immediately.
            for decision in self.symbols[:2]:
                vm = GPLSubset(re.sub(r'#(\w+)', r'"\1"', item.text))
                calls = []
                for name in set(re.findall(r'\$(\w+)', item.text)):
                    def callback(*args, name=name.lower()):
                        calls.append(name)
                        return name == decision.lower()
                    vm.calls[name.lower()] = callback
                vm.call(item.name, agent())
                self.assertEqual(calls[-1], decision.lower())
        reset = next(i.text for i in result.items if i.name.lower() == 'reset_tasks')
        death = next(i.text for i in result.items if i.name.lower() == 'unit_call_deathscript')
        self.assertEqual(reset.count('$' + self.symbols[2] + '('), 1)
        self.assertEqual(death.count('$' + self.symbols[3] + '('), 1)

    def test_private_spells_receive_stock_confidence_only_for_spellsinger(self):
        source = (SDK / 'GPLMx/DecisionTrees/Modules/mx_target_eval.gpl').read_text(encoding='cp1252')
        stock = parse_gpl(extract_function(source, 'spell_extra_value'), 'stock').items[0]
        # Existing selected-mod contribution is retained by the additive path.
        existing = parse_gpl(stock.text.replace('return value;', 'value += 7;\n\treturn value;'), 'existing').items[0]
        result = add_spell_evaluation_equivalents(SemanticMergeResult((existing,), ()), self.spells, stock)
        vm = GPLSubset(result.items[0].text)
        for title, available, expected in (
            ('Spellsinger', set(), 7), ('Spellsinger', {'Bards_Arcane_Note'}, 17),
            ('Spellsinger', {'Bards_Resonant_Burst'}, 37),
            ('Spellsinger', {'Bards_Arcane_Note', 'Bards_Resonant_Burst'}, 47),
            ('Blade_Dancer', {'Bards_Arcane_Note', 'Bards_Resonant_Burst'}, 7),
        ):
            modes = []
            def available_spell(hero, spell, mode):
                modes.append(mode)
                return spell in available
            vm.calls['isspellavailable'] = available_spell
            self.assertEqual(vm.call('spell_extra_value', agent(title=title)), expected)
            self.assertEqual(set(modes), {1})


if __name__ == '__main__':
    unittest.main()
