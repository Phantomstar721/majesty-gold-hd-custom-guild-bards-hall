"""Regression boundaries found by the final adversarial review."""
import ast
from pathlib import Path
import re
import sys
import unittest

from test_hiring import ROOT, SDK, agent
from test_deflect import ImpactHarness
from test_equipment_damage import DamageHarness
from bards_abilities import combat_functions, renown_functions, support_functions
from build_bards_hall import extract_function


class ReviewRegressionTests(unittest.TestCase):
    def test_base_monster_never_reads_expansion_zoo_field(self):
        source = renown_functions(SDK, extract_function)
        program = extract_function(source, 'zoo_flag_check')
        vm = ImpactHarness(program)
        self.assertFalse(vm.call('zoo_flag_check', agent(type='Monster')))

    def test_restored_zoo_still_owns_capture_on_base_monsters(self):
        sys.path.insert(0, str(ROOT.parent/'majesty-gold-hd-cam-merger/src'))
        from majesty_cam.gpl_function_merge import merge_function
        zoo = ROOT.parent/'majesty-gold-hd-restore-abandoned-zoo/src/GPL/RestoreAbandonedZoo_Capture.gpl'
        stock = SDK/'GPLMx/mx_Monster_Deaths.gpl'
        merged = merge_function(extract_function(stock.read_text(encoding='cp1252'), 'monster_gravestone'), {
            'Bards': extract_function(renown_functions(SDK, extract_function), 'monster_gravestone'),
            'Zoo': extract_function(zoo.read_text(), 'monster_gravestone')})
        compact = re.sub(r'\s+', '', merged).lower()
        self.assertIn('$restore_stock_zoo_flag_check(thisagent)', compact)
        self.assertIn('$bards_renown_captured(thisagent)', compact)
        self.assertNotIn('hasattribute', compact)

    def test_base_and_expansion_lair_death_keep_spawn_and_cleanup_order(self):
        source = extract_function(renown_functions(SDK, extract_function), 'lair_death')
        for expansion, has_special, list_count, special in (
            (False, False, 0, 'xx'), (False, False, 0, 'Dragon'),
            (True, False, 1, 'Dragon'), (True, True, 0, 'Dragon'),
            (True, False, 0, 'Dragon'),
        ):
            vm = ImpactHarness(re.sub(r'#(\w+)', r'"\1"', source))
            lair = agent(Spawn_function='spawn', Special_Spawn_Type=special)
            if expansion:
                lair['Has_Special_Spawn'] = has_special
            events = []
            def fill(a, result):
                events.append('fill')
                if list_count: result.append('Goblin')
                return list_count
            vm.calls.update(killthread=lambda *_: events.append('kill'),
                fillspeciallairlist=fill, locationof=lambda *_: 0,
                spawnunit=lambda a, name, *_: events.append(name),
                bards_renown_defeat=lambda *_: events.append('renown'),
                getattribute=lambda *_: 20, dropgoldinradius=lambda *_: events.append('gold'),
                chance_drop_equip=lambda *_: events.append('equipment'),
                drop_qitems=lambda *_: events.append('quest-items'),
                building_death=lambda *_: events.append('death'))
            vm.call('lair_death', lair)
            self.assertEqual(events[0], 'kill')
            self.assertEqual(events[-5:], ['renown', 'gold', 'equipment', 'quest-items', 'death'])
            if not expansion: self.assertNotIn('fill', events)
            expected = 'Goblin' if expansion and not has_special and list_count else special
            if expected != 'xx': self.assertIn(expected, events)

    def test_follow_snapshot_is_lazy_and_reused_for_all_candidates(self):
        source = extract_function(support_functions(SDK, extract_function), 'Bards_Follow_Check')
        source += (ROOT/'src/gpl/Bards_Follow.gpl').read_text()
        source = source.replace('#Follow_support_Check_Mod', '2')
        for active in (False, True):
            vm = ImpactHarness(re.sub(r'#(\w+)', r'"\1"', source))
            bard = agent(title='Troubadour', subtype='Hero', team=1)
            leaders = [agent(title='Warrior', subtype='Hero', team=1) for _ in range(24)]
            queries = []
            def query(owner, kind, radius, result, *flags):
                queries.append(radius)
                if radius != -1: result.extend(leaders)
                return len(result)
            vm.calls.update(randomnumber=lambda _: 0, getattribute=lambda *_: 220,
                listobjects=query, notvalid=lambda a: a is None or not a.alive,
                getplayerteamnumber=lambda a: a['team'], addlists=lambda a,b: a+b,
                bards_follow_going_home=lambda _: False, bards_follow_active=lambda _: active,
                bards_follow_support=lambda *_: None,
                listsize=len, listmember=lambda xs,n: xs[n-1], specifyintent=lambda *_: None)
            self.assertEqual(vm.call('Bards_Follow_Check', bard, 'Hero', 100), active)
            self.assertEqual(queries.count(-1), 4 if active else 0)
            if active: self.assertIs(bard['BackTarget'], leaders[0])

    def test_flourish_composes_with_both_alchemist_oils(self):
        sys.path.insert(0, str(ROOT.parent/'majesty-gold-hd-cam-merger/src'))
        from majesty_cam.gpl_function_merge import merge_function
        alchy = ROOT.parent/'majesty-gold-hd-custom-guild-alchemist/src/build_custom_guild_alchemist.py'
        tree = ast.parse(alchy.read_text())
        selected = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name in ('build_alchemist_damage', 'extract_gpl_function')]
        scope = dict(Path=Path, re=re)
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(alchy), 'exec'), scope)
        stock = SDK/'GPLMx/TaskModules/Subtasks/mx_Make_Attack.gpl'
        generated = combat_functions(SDK, extract_function)
        combined = merge_function(extract_function(stock.read_text(encoding='cp1252'), 'damage'),
            {'Bards': extract_function(generated, 'damage'), 'Alchemist': scope['build_alchemist_damage'](stock)})
        self.assertNotIn('Bards_Flourish_Damage', generated)
        self.assertIn('$damage(Attacker, Defender);', (ROOT/'src/gpl/Bards_Dancer.gpl').read_text())
        for proc in ('alchemy_paralytic_oil_begin', 'alchemy_transmutation_oil_hit'):
            self.assertEqual(len(re.findall(r'\$'+proc+r'\s*\(', combined.lower())), 1)
        self.assertEqual(len(re.findall(r'\$\s*bards_consume_flourish\s*\(', combined.lower())), 1)
        self.assertLess(combined.lower().index('bards_consume_flourish'), combined.lower().index('alchemy_'))


if __name__ == '__main__':
    unittest.main()
