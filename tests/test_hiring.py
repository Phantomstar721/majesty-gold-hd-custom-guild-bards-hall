"""Run authored hiring/payment and the Manager's actual activity GPL in memory.

No Manager package/profile is composed. Native movement, hidden-state changes
and save files are deliberately outside this small branch/lifecycle harness.
"""
import importlib.util
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT.parent / 'majesty-gold-hd-cam-merger'
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(MANAGER / 'src'))
from build_bards_hall import extract_function
from bards_abilities import hiring_functions
from validate_bards_abilities import DYNAMIC_ATTRIBUTE_TYPES
from majesty_cam.activity_time import activity_source
from majesty_cam.shared_composition import SharedBinding
from majesty_cam.shared_features import StockActivityDuration

spec = importlib.util.spec_from_file_location('bards_hiring_harness', MANAGER / 'tests/gpl_sampler_harness.py')
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
SDK = Path(r'C:\Program Files (x86)\Steam\steamapps\common\Majesty HD\SDK\OriginalQuests')
SOURCE = (ROOT / 'src/gpl/Bards_Hiring.gpl').read_text()


class GPLSubset(harness.SamplerHarness):
    def add_attribute(self, agent, name, kind, value=None):
        # The old permissive mock allocated "agent", which the game rejects.
        # Fail at this boundary rather than masking a subsequent native abort.
        if kind.lower() not in DYNAMIC_ATTRIBUTE_TYPES:
            raise ValueError(f'Unsupported native AddAttribute type: {kind}')
        return super().add_attribute(agent, name, kind, value)

    def expression(self, tokens):
        # These selected functions contain only GPL integer arithmetic.
        return super().expression(tokens).replace(' / ', ' // ')


def agent(**fields):
    value = harness.Agent()
    value.fields.update(fields)
    return value


class HiringTests(unittest.TestCase):
    def runtime(self):
        names = ('Bards_Follow_Intent', 'Bards_Hiring_Is_Open', 'Bards_Hire_Start', 'Bards_Hire_Patron_Free', 'Bards_Is_Bard',
                 'Bards_Hire_Alive', 'Bards_Hire_Release', 'Bards_Hire_Condition',
                 'Bards_Hire_Completed', 'Bards_Hire_Cancelled', 'Bards_Hire_Guard',
                 'Bards_Hire_Abort', 'Bards_Hire_Cancel_Now', 'Bards_Hire_Available',
                 'Bards_Hire_Guild', 'Bards_Hire_Valid', 'Bards_Hire_Assigned', 'Bards_Hire_Wait')
        program = '\n'.join(extract_function(SOURCE, name) for name in names)
        program += extract_function(hiring_functions(SDK, extract_function), 'Bards_Hire_Pay')
        feature = StockActivityDuration('bards-hiring', 'Bards_Contract', 'Bards_Hire_Condition',
                                        'Bards_Hire_Completed', 'Bards_Hire_Cancelled')
        program += activity_source((SharedBinding('test', feature),))
        # The small harness has no constants table; native attribute names remain
        # opaque keys here, rather than inventing their executable numeric IDs.
        program = re.sub(r'#(\w+)', r'"\1"', program)
        vm = GPLSubset(program)
        events = []
        vm.calls.update({
            'bards_try_finale': lambda a: False,
            'getattribute': lambda a, key: a.fields.get(key, 0),
            'adjustattribute': lambda a, key, delta: a.fields.__setitem__(key, a.fields.get(key, 0) + delta),
            'getunitplayernumber': lambda a: a['player'],
            'total_gold': lambda a: a['ATTRIB_Gold'] + a['ATTRIB_StoredGold'],
            'haslowhp': lambda a: False,
            'insidebuilding': lambda a: False,
            'stopmoving': lambda a: None,
            'bards_follow_target_eligible': lambda *_: True,
            'notvalid': lambda a: not a.alive,
            'bards_hire_guild': lambda *_: True,
            'bards_hire_available': lambda b, *_: vm.call('Bards_Contract_State', b, 1) == 0 and b.fields.get('BardsHirePatron') is None,
            'give_gold': lambda a, amount: (events.append(('earn', amount)), a.fields.__setitem__('ATTRIB_Gold', a['ATTRIB_Gold'] + amount)),
            'createeffector': lambda *args: events.append(('effect', args)),
            'specifyintent': lambda *args: None,
            'reset_tasks': lambda a: events.append(('reset', a)),
            'bards_hire_valid': lambda *_: True,
        })
        for name in ('bards_follow_support', 'bards_hired_follow', 'bards_travel_support', 'attack_object', 'travel_to', 'travel_to_safe', 'use_building', 'rest_at_guild', 'done_resting_guild'):
            vm.calls[name] = lambda: None  # Distinct function identities.
        p = agent(title='Warrior', subtype='Hero', player=1, ATTRIB_HP=100, ATTRIB_Gold=40, ATTRIB_StoredGold=210, BackScript='ordinary')
        b = agent(title='Troubadour', player=1, ATTRIB_HP=100, ATTRIB_Gold=0, StartingScript='ordinary')
        b['evaluationscript'] = lambda _: False
        g = agent(title='Bards_Hall', player=1, ATTRIB_HP=500, ATTRIB_Gold=0, ATTRIB_TaxRate=20, ATTRIB_FirstStageBuilt=1)
        b['home'] = g
        return vm, p, b, g, events

    def test_payment_uses_stored_gold_then_purse_and_conserves_fee(self):
        for stored, carried, after_stored, after_carried in ((210, 40, 10, 40), (20, 230, 0, 50)):
            vm, p, b, g, events = self.runtime()
            p['ATTRIB_StoredGold'], p['ATTRIB_Gold'] = stored, carried
            self.assertTrue(vm.call('Bards_Hire_Start', p, b, g))
            self.assertEqual((p['ATTRIB_StoredGold'], p['ATTRIB_Gold']), (after_stored, after_carried))
            self.assertEqual((g['ATTRIB_Gold'], b['ATTRIB_Gold']), (100, 100))
            self.assertEqual(p['ATTRIB_StoredGold'] + p['ATTRIB_Gold'] + g['ATTRIB_Gold'] + b['ATTRIB_Gold'], 250)
            self.assertIs(p['BardsHiredBard'], b)
            self.assertIs(b['BardsHirePatron'], p)
            self.assertFalse(vm.call('Bards_Hire_Start', p, b, g))
            self.assertEqual(sum(e[1] for e in events if e[0] == 'earn'), 100)

    def test_equal_split_does_not_depend_on_ordinary_guild_tax(self):
        for tax_rate in (0, 20, 50, 100):
            vm, p, b, g, events = self.runtime()
            g['ATTRIB_TaxRate'] = tax_rate
            self.assertTrue(vm.call('Bards_Hire_Start', p, b, g))
            self.assertEqual((g['ATTRIB_Gold'], b['ATTRIB_Gold']), (100, 100))
            self.assertEqual(g['ATTRIB_TaxRate'], tax_rate)
            received = [e[1] for e in events if e[0] == 'effect']
            self.assertEqual(received, [(g, 'Got_Gold_Bldg', 0, 100)])

    def test_unaffordable_and_failed_registration_never_charge_or_claim(self):
        for result in (0, -1, -2, -3):
            vm, p, b, g, events = self.runtime()
            vm.calls['bards_contract_start'] = lambda *_, result=result: result
            self.assertFalse(vm.call('Bards_Hire_Start', p, b, g))
            self.assertNotIn('BardsHiredBard', p.fields)
            self.assertNotIn('BardsHirePatron', b.fields)
            self.assertEqual(p['ATTRIB_StoredGold'] + p['ATTRIB_Gold'], 250)
            self.assertEqual(events, [])
        vm, p, b, g, _ = self.runtime()
        p['ATTRIB_Gold'] = 39
        self.assertFalse(vm.call('Bards_Hire_Start', p, b, g))
        self.assertEqual(vm.call('Bards_Contract_State', b, 1), 0)

    def test_term_completes_once_and_both_sides_become_available(self):
        vm, p, b, g, events = self.runtime()
        self.assertTrue(vm.call('Bards_Hire_Start', p, b, g))
        for _ in range(120):
            vm.tick()
        self.assertIs(b['BardsHirePatron'], p)  # First sample grants no time.
        vm.tick()
        self.assertIsNone(b['BardsHirePatron'])
        self.assertIsNone(p['BardsHiredBard'])
        self.assertEqual(b['BasicScript'], 'ordinary')
        self.assertEqual(vm.call('Bards_Contract_State', b, 1), 0)
        before = list(events)
        vm.call('Bards_Hire_Completed', b, p, g, 1)
        self.assertEqual(events, before)

    def test_death_of_either_hero_or_guild_cancels_without_second_payment(self):
        for which in ('patron', 'bard', 'guild'):
            vm, p, b, g, events = self.runtime()
            vm.call('Bards_Hire_Start', p, b, g)
            {'patron': p, 'bard': b, 'guild': g}[which].alive = False
            vm.tick()
            self.assertIsNone(p['BardsHiredBard'])
            self.assertIsNone(b['BardsHirePatron'])
            self.assertEqual(vm.call('Bards_Contract_State', b, 1), 0)
            self.assertEqual(sum(e[1] for e in events if e[0] == 'earn'), 100)
            self.assertEqual(b['BasicScript'], 'ordinary')
            if which == 'bard':
                self.assertFalse(any(e[0] == 'reset' for e in events))

    def test_busy_cancellation_releases_claims_and_retries_on_existing_ai(self):
        vm, p, b, g, _ = self.runtime()
        vm.call('Bards_Hire_Start', p, b, g)
        vm.calls['bards_hire_valid'] = lambda *_: False
        vm.root['MM_ActivityBusy_v1'] = True
        self.assertTrue(vm.call('Bards_Hire_Guard', b))
        self.assertIsNone(p['BardsHiredBard'])
        self.assertIsNone(b['BardsHirePatron'])
        self.assertTrue(b['BardsHireCancelPending'])
        self.assertGreater(vm.call('Bards_Contract_State', b, 1), 0)
        vm.root['MM_ActivityBusy_v1'] = False
        self.assertFalse(vm.call('Bards_Hire_Guard', b))
        self.assertFalse(b['BardsHireCancelPending'])
        self.assertEqual(vm.call('Bards_Contract_State', b, 1), 0)
        self.assertIsNone(p['BardsHiredBard'])
        self.assertIsNone(b['BardsHirePatron'])

    def test_release_preserves_fleeing_and_newer_or_external_assignments(self):
        vm, p, b, g, events = self.runtime()
        vm.call('Bards_Hire_Start', p, b, g)
        b['ActiveScript'] = 'heal_self_fleeing'
        vm.call('Bards_Hire_Abort', p)
        self.assertEqual(b['BasicScript'], 'ordinary')
        self.assertEqual(b['ActiveScript'], 'heal_self_fleeing')
        self.assertFalse(any(e[0] == 'reset' for e in events))
        vm, p, b, g, events = self.runtime()
        vm.call('Bards_Hire_Start', p, b, g)
        b['BasicScript'] = b['ActiveScript'] = 'flee_map'
        vm.call('Bards_Hire_Abort', b)
        self.assertEqual(b['BasicScript'], 'flee_map')
        self.assertEqual(b['ActiveScript'], 'flee_map')

    def test_release_resets_private_follow_travel(self):
        vm, p, b, g, events = self.runtime()
        vm.call('Bards_Hire_Start', p, b, g)
        b['ActiveScript'] = vm.calls['bards_travel_support']
        vm.call('Bards_Hire_Abort', p)
        self.assertEqual(b['BasicScript'], 'ordinary')
        self.assertEqual(sum(e[0] == 'reset' for e in events), 1)
        self.assertIsNone(b['BardsHirePatron'])

    def test_ownership_change_on_any_participant_ends_contract(self):
        for changed in ('patron', 'bard', 'guild'):
            vm, p, b, g, _ = self.runtime()
            vm.call('Bards_Hire_Start', p, b, g)
            vm.calls['bards_hire_guild'] = vm._bind('bards_hire_guild')
            vm.calls['bards_hire_valid'] = vm._bind('bards_hire_valid')
            self.assertFalse(vm.call('Bards_Hire_Guard', b))
            {'patron': p, 'bard': b, 'guild': g}[changed]['player'] = 2
            self.assertTrue(vm.call('Bards_Hire_Guard', b))
            self.assertIsNone(p['BardsHiredBard'])
            self.assertIsNone(b['BardsHirePatron'])

    def test_only_healthy_resting_member_is_available_and_uses_stock_exit(self):
        vm, p, b, g, events = self.runtime()
        b['Target'], b['BasicScript'], b['ActiveScript'] = g, 'ordinary', vm.calls['rest_at_guild']
        b['ATTRIB_MaxHP'] = 100
        vm.calls['insidebuilding'] = lambda a: a is b
        vm.calls['bards_hire_available'] = vm._bind('bards_hire_available')
        b['ATTRIB_HP'] = 99
        self.assertFalse(vm.call('Bards_Hire_Start', p, b, g))
        b['ATTRIB_HP'] = 100
        vm.calls['exit_building'] = lambda *args: events.append(('exit', args))
        self.assertTrue(vm.call('Bards_Hire_Start', p, b, g))
        self.assertEqual(sum(e[0] == 'exit' for e in events), 1)

    def test_paid_companion_waits_through_patron_shop_visit_without_pausing_term(self):
        vm, p, b, g, events = self.runtime()
        vm.call('Bards_Hire_Start', p, b, g)
        p['Target'] = agent(type='Building', ATTRIB_HP=100)
        vm.calls['distancebetweenagents'] = lambda *_: 100
        vm.calls['bards_hire_valid'] = vm._bind('bards_hire_valid')
        vm.calls['insidebuilding'] = lambda a: a is p
        vm.calls['stopmoving'] = lambda a: events.append(('stop', a))
        vm.calls['randomnumber'] = lambda _: 0
        self.assertFalse(vm.call('Bards_Hire_Guard', b))
        self.assertTrue(vm.call('Bards_Hire_Wait', b))
        vm.tick()
        vm.tick()
        self.assertEqual(vm.call('Bards_Contract_Elapsed', b, 1), 1000)
        self.assertIs(b['BardsHirePatron'], p)
        def danger(hero):
            hero['ActiveScript'] = 'self_defense'
            return True
        b['evaluationscript'] = danger
        self.assertTrue(vm.call('Bards_Hire_Wait', b))
        self.assertEqual(b['ActiveScript'], 'self_defense')
        vm.calls['insidebuilding'] = lambda _: False
        self.assertFalse(vm.call('Bards_Hire_Wait', b))


if __name__ == '__main__':
    unittest.main()
