"""Exercise the home-tier gate."""
import re
import unittest

from test_hiring import ROOT, SDK, agent
from test_deflect import ImpactHarness
from bard_job_harness import home, job_source
from build_bards_hall import extract_function


class GuildJobTests(unittest.TestCase):
    def runtime(self):
        source = job_source()
        # These tests return before the stock scoring/coordinate branches.
        # Their unused locals need defaults the small GPL harness supports.
        source = re.sub(r'(?im)^(\s*)float\s+', r'\1integer ', source)
        source = re.sub(r'(?im)^(\s*)coordinate\s+', r'\1agent ', source)
        vm = ImpactHarness(re.sub(r'#(\w+)', r'"\1"', source))
        events = []
        vm.calls.update({
            'getattribute': lambda a, key: a.fields.get(key, 0),
            'getunitplayernumber': lambda a: a['player'],
            'getplayerteamnumber': lambda a: a['player'],
            'neutralteamnumber': lambda: 0,
            'notvalidsteal': lambda a: a is None or not a.alive,
            'reset_tasks': lambda a: (events.append('reset'), a.fields.__setitem__('ActiveScript', 'ordinary')),
            'stopmoving': lambda a: events.append('stop'),
            'debugout': lambda *_: None,
        })
        bard = agent(title='Blade_Dancer', player=1, Home=home(), ActiveScript='conquest', BackScript='return')
        return vm, bard, events

    def test_completed_home_tier_controls_unlock_without_a_cached_state(self):
        vm, bard, _ = self.runtime()
        for level, complete, expected in ((1, True, False), (1, False, False),
                                          (2, True, True), (2, False, True), (3, True, True)):
            bard['Home'] = home(level, complete=complete)
            self.assertEqual(vm.call('Bards_Jobs_Unlocked', bard), expected)
        for guild in (None, home(player=2), home()):
            if guild is not None and guild['player'] == 1:
                guild.alive = False
            bard['Home'] = guild
            self.assertFalse(vm.call('Bards_Jobs_Unlocked', bard))
        bard['Home'] = home()
        self.assertTrue(vm.call('Bards_Jobs_Unlocked', bard))
        del bard.fields['Home']
        self.assertFalse(vm.call('Bards_Jobs_Unlocked', bard))

if __name__ == '__main__':
    unittest.main()
