import re
import unittest
from test_hiring import ROOT, SDK, GPLSubset, agent
from build_bards_hall import extract_function
from bards_abilities import support_functions


class RenownReturnTests(unittest.TestCase):
    def runtime(self):
        source = extract_function((ROOT/'src/gpl/Bards_Renown.gpl').read_text(), 'Bards_Renown_Return')
        vm = GPLSubset(source)
        leader = agent(engaged=False)
        bard = agent(title='Troubadour', BardsRenownGold=300, BasicScript='follow',
                     StartingScript='tree', BackTarget=leader, engaged=False,
                     inside=False, hired=False, unlocked=True)
        events = []
        vm.calls.update({
            'bards_jobs_unlocked': lambda h: h['unlocked'],
            'insidebuilding': lambda h: h['inside'],
            'bards_hire_assigned': lambda h: h['hired'],
            'bards_song_engaged': lambda h: h['engaged'],
            'notvalid': lambda h: h is None or not h.alive,
            'reset_tasks': lambda h: events.append('reset'),
            'go_home': lambda h,chance: events.append(('home',chance)) or True,
        })
        return vm, bard, leader, events

    def test_threshold_uses_pending_gold_and_releases_ordinary_follow(self):
        for gold in (0,299,300,1450):
            vm,bard,leader,events = self.runtime()
            bard['BardsRenownGold'] = gold
            bard['ATTRIB_Gold'] = 99999
            self.assertEqual(vm.call('Bards_Renown_Return',bard),gold>=300)
            self.assertEqual(events, ['reset',('home',100)] if gold>=300 else [])
            self.assertEqual(bard['BardsRenownGold'],gold)
            if gold>=300:
                self.assertEqual(bard['BasicScript'],'tree')
                self.assertIsNone(bard['BackTarget'])

    def test_combat_and_owned_tasks_defer_without_losing_tales(self):
        for blocker in ('self_combat','leader_combat','inside','hired','quest','no_guild'):
            vm,bard,leader,events = self.runtime()
            if blocker=='self_combat': bard['engaged']=True
            elif blocker=='leader_combat': leader['engaged']=True
            elif blocker=='quest': bard['AGAcceptedQuest']=bard
            elif blocker=='no_guild': bard['unlocked']=False
            else: bard[blocker]=True
            self.assertFalse(vm.call('Bards_Renown_Return',bard),blocker)
            self.assertEqual(events,[])
            self.assertEqual(bard['BardsRenownGold'],300)
            self.assertIs(bard['BackTarget'],leader)

    def test_dispatch_covers_follow_travel_and_normal_decisions(self):
        code = support_functions(SDK,extract_function)
        for name in ('Bards_Follow_Support','Bards_Travel_Support'):
            self.assertIn('$Bards_Renown_Return(ThisAgent)',extract_function(code,name))
        tree=extract_function((ROOT/'src/gpl/Bards_Hero_Trees.gpl').read_text(),'Bards_Troubadour_Tree')
        self.assertLess(tree.index('$Bards_Renown_Return'),tree.index('$Bards_Follow_Check'))

if __name__ == '__main__': unittest.main()
