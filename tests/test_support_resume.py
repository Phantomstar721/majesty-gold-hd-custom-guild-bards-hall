"""Exercise stock interruption exits into the private persistent follow task."""
import re
import unittest
from test_hiring import SDK, ROOT
from test_deflect import ImpactHarness
from test_guild_capacity import unit
from build_bards_hall import extract_function
from bards_abilities import support_functions, hiring_functions


class SupportResumeTests(unittest.TestCase):
    def runtime(self, hired=False):
        task = 'Bards_Hired_Follow' if hired else 'Bards_Follow_Support'
        generated = hiring_functions(SDK, extract_function) if hired else support_functions(SDK, extract_function)
        source = extract_function(generated, task)
        hiring = (ROOT/'src/gpl/Bards_Hiring.gpl').read_text()
        source += extract_function(hiring, 'Bards_Follow_Intent')
        source += extract_function(hiring, 'Bards_Hire_Assigned')
        for path, name in (
            ('mx_LowLevel.gpl', 'reset_tasks'),
            ('TaskModules/Buildings/mx_Lived_In.gpl', 'Done_resting_Guild'),
            ('TaskModules/Characters/mx_berserk_defend.gpl', 'berserk_defend'),
        ):
            source += extract_function((SDK / 'GPLMx' / path).read_text(encoding='cp1252'), name)
        source = source.replace('#follow_support_buffer', '20').replace('#followBored', '10')
        vm = ImpactHarness(re.sub(r'#(\w+)', r'"\1"', source))
        for symbol in re.findall(r'\$(\w+)', source):
            vm.calls.setdefault(symbol.lower(), lambda *args: None)
        leader = unit(BackScript='explore', ActiveScript='explore', Target=None,
                      home=None, team=1, Hostiles=[])
        bard = unit(BasicScript=vm.calls[task.lower()], StartingScript='tree', BackTarget=leader,
                    Target=None, ActiveScript='rest', BackScript='rest', team=1,
                    Hostiles=[], Counter=0, intent='seeking-refuge', home=unit(), type='hero')
        if hired: bard['BardsHirePatron'] = leader
        vm.calls.update(
            bards_hire_guard=lambda h: False, bards_hire_wait=lambda h: False,
            notvalid=lambda h: h is None, getplayerteamnumber=lambda h: h['team'],
            haslowhp=lambda h: False, distancebetweenagents=lambda *a: 50,
            bards_troubadour_evaluate=lambda h: False, bards_try_song=lambda h: False,
            randomnumber=lambda n: 0, stopmoving=lambda h: None,
            exit_building=lambda *a: None, debugout=lambda *a: None,
            specifyintent=lambda h, value: h.__setitem__('intent', value),
            list_enemies=lambda *a: None, cleanse_hostiles=lambda *a: None,
            listsize=len, clearlist=lambda values: values.clear(),
        )
        return vm, bard, leader, task

    def test_return_from_home_rest_restores_follow_label_without_reassignment(self):
        for hired in (False, True):
            vm, bard, leader, task = self.runtime(hired)
            bard['Target'] = bard['home']
            vm.call('Done_resting_Guild', bard)
            self.assertIs(bard['ActiveScript'], vm.calls[task.lower()])
            self.assertEqual(bard['intent'], 'seeking-refuge')
            # Hired combat follow looks at a native attack range; keep it in range.
            vm.calls['getattribute'] = lambda *a: 180
            vm.call(task, bard)
            self.assertEqual(bard['intent'], 'Bards_Intent_Hired_Support' if hired else 'intent_following_and_supporting')
            self.assertIs(bard['BackTarget'], leader)
            self.assertIs(bard['BasicScript'], vm.calls[task.lower()])

    def test_no_enemies_berserk_exit_restores_label_on_follow_dispatch(self):
        vm, bard, leader, task = self.runtime()
        bard['intent'] = 'intent_berserk'
        bard['ActiveScript'] = 'berserk_defend'
        vm.call('berserk_defend', bard)
        self.assertIs(bard['ActiveScript'], vm.calls[task.lower()])
        self.assertEqual(bard['intent'], 'intent_berserk')
        vm.call(task, bard)
        self.assertEqual(bard['intent'], 'intent_following_and_supporting')
        self.assertIs(bard['BackTarget'], leader)

    def test_new_danger_keeps_its_intent_and_task(self):
        vm, bard, _, task = self.runtime()
        def danger(h):
            h['intent'] = 'intent_berserk'
            h['ActiveScript'] = 'berserk_defend'
            return True
        vm.calls['bards_troubadour_evaluate'] = danger
        vm.call(task, bard)
        self.assertEqual(bard['intent'], 'intent_berserk')
        self.assertEqual(bard['ActiveScript'], 'berserk_defend')

    def test_contract_cancellation_is_not_overwritten(self):
        vm, bard, _, task = self.runtime()
        vm.calls['bards_hire_guard'] = lambda h: True
        vm.call(task, bard)
        self.assertEqual(bard['intent'], 'seeking-refuge')

    def test_waiting_for_patron_restores_label_before_wait_branch(self):
        vm, bard, _, task = self.runtime()
        vm.calls['bards_hire_wait'] = lambda h: True
        vm.call(task, bard)
        self.assertEqual(bard['intent'], 'intent_following_and_supporting')


if __name__ == '__main__': unittest.main()
