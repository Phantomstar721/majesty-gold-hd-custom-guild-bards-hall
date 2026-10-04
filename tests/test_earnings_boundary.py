"""Exercise private settlements through the literal stock gold award helper."""
import re
import unittest

import test_hiring
import test_renown
from build_bards_hall import extract_function


def stock_awarder(events):
    source = (test_hiring.SDK / 'GPLMx/mx_Monster_Deaths.gpl').read_text(encoding='cp1252')
    program = extract_function(source, 'give_gold')
    vm = test_hiring.GPLSubset(re.sub(r'#(\w+)', r'"\1"', program))

    def adjust(recipient, key, amount):
        actual = next((field for field in recipient.fields if field.casefold() == key.casefold()), key)
        recipient[actual] = recipient.fields.get(actual, 0) + amount
        events.append(('credit', recipient, amount))

    vm.calls.update({
        'createeffector': lambda recipient, effect, duration, amount:
            events.append(('display', recipient, amount)),
        'adjustattribute': adjust,
        'debugout': lambda *args: None,
    })
    return lambda recipient, amount: vm.call('give_gold', recipient, amount)


class EarningsBoundaryTests(unittest.TestCase):
    def test_hire_uses_stock_display_then_credit_without_changing_original_debit(self):
        vm, patron, bard, guild, _ = test_hiring.HiringTests().runtime()
        events = []
        vm.calls['give_gold'] = stock_awarder(events)
        self.assertTrue(vm.call('Bards_Hire_Start', patron, bard, guild))
        self.assertEqual(events, [('display', bard, 100), ('credit', bard, 100)])
        self.assertEqual((patron['ATTRIB_StoredGold'], patron['ATTRIB_Gold']), (10, 40))
        self.assertEqual((guild['ATTRIB_Gold'], bard['ATTRIB_Gold']), (100, 100))
        self.assertFalse(vm.call('Bards_Hire_Start', patron, bard, guild))
        self.assertEqual(len(events), 2)

    def test_renown_consumes_ledger_before_stock_award_and_cannot_pay_twice(self):
        vm, _, _, bards = test_renown.RenownTests().runtime()
        bard = bards[0]
        bard['ATTRIB_Gold'] = 0
        bard['BardsRenownGold'], bard['BardsRenownXP'] = 50, 150
        events = []
        award = stock_awarder(events)

        def pay(recipient, amount):
            self.assertEqual((recipient['BardsRenownGold'], recipient['BardsRenownXP']), (0, 0))
            award(recipient, amount)
            vm.call('Bards_Renown_Settle', recipient, recipient['Home'])

        vm.calls['give_gold'] = pay
        vm.calls['give_exp'] = lambda _, amount: events.append(('xp', amount))
        vm.call('Bards_Renown_Settle', bard, bard['Home'])
        self.assertEqual(events, [('display', bard, 50), ('credit', bard, 50), ('xp', 150)])
        self.assertEqual(bard['ATTRIB_Gold'], 50)


if __name__ == '__main__':
    unittest.main()
