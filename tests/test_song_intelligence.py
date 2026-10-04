"""Execute song potency, mixed-caster refresh and reversal in the GPL harness."""
import re
import unittest
from test_hiring import ROOT, GPLSubset, agent
from build_bards_hall import extract_function


class SongIntelligenceTests(unittest.TestCase):
    def runtime(self):
        effects = (ROOT/'src/gpl/Bards_Effects.gpl').read_text()
        rates = (ROOT/'src/gpl/Bards_Rates.gpl').read_text()
        source = '\n'.join(extract_function(effects, n) for n in
                           ('Bards_Song_Intelligence_Step', 'Bards_Valor_Apply', 'Bards_Valor_End'))
        source += '\n'.join(extract_function(rates, n) for n in ('Bards_Satire_Apply', 'Bards_Satire_End'))
        vm = GPLSubset(re.sub(r'#(\w+)', r'"\1"', source))
        active = {}
        def adjust(h, key, delta):
            h.fields[key] = h.fields.get(key, 0) + delta
        vm.calls.update({
            'getattribute': lambda h,k: h.fields.get(k, 0),
            'checkeffector': lambda h,n: n in active,
            'createeffector': lambda h,n,t: active.__setitem__(n, active.get(n, 0)+1),
            'magicaladjustattribute': adjust, 'adjustattribute': adjust,
            'mm_unitmovementbaseperiod': lambda h: 100,
            'mm_actionbaseperiod': lambda a: 1000,
            'bards_primary_action': lambda h: 'basic_attack',
            'bards_rate_delta': lambda b,p,d: b*p//d,
        })
        return vm, active

    def test_curve_boundaries(self):
        vm, _ = self.runtime()
        for intel, expected in ((-10,0),(20,0),(22,0),(23,0),(24,1),(25,1),
                                (26,2),(27,2),(28,3),(29,3),(30,4),(1000,4)):
            self.assertEqual(vm.call('Bards_Song_Intelligence_Step', agent(ATTRIB_Intelligence=intel)), expected)

    def test_mixed_casters_never_stack_or_downgrade_and_cleanup_exactly(self):
        for song, attribute, baseline, maximum in (
                ('Valor','ATTRIB_HtoH',8,12), ('Satire','ATTRIB_Strength',-5,-7)):
            vm, active = self.runtime()
            hero = agent(**{attribute: 50, 'ATTRIB_MagicResistance': 17,
                            'ATTRIB_MovementRateModifier': 40, 'ATTRIB_ActionRateModifier': 60})
            low, high = agent(ATTRIB_Intelligence=22), agent(ATTRIB_Intelligence=30)
            vm.call(f'Bards_{song}_Apply', low, hero)
            self.assertEqual(hero[attribute], 50+baseline)
            vm.call(f'Bards_{song}_Apply', high, hero)
            for caster in (low, high, low, low):
                before = dict(active)
                vm.call(f'Bards_{song}_Apply', caster, hero)
                if caster is low:
                    self.assertEqual(active, before, 'Weaker cast must not refresh duration or flash')
                self.assertEqual(hero[attribute], 50+maximum)
                self.assertIs(hero[f'Bards{song}Source'], high)
            if song == 'Valor':
                self.assertEqual(hero['ATTRIB_MagicResistance'],31)
            # Caster stats/lifetime no longer control reversal.
            high['ATTRIB_Intelligence'] = 0
            high.alive = False
            active.clear()
            vm.call(f'Bards_{song}_End', hero)
            self.assertEqual(hero[attribute],50)
            self.assertEqual(hero['ATTRIB_MagicResistance'],17)
            self.assertEqual(hero['ATTRIB_MovementRateModifier'],40)
            self.assertEqual(hero['ATTRIB_ActionRateModifier'],60)
            vm.call(f'Bards_{song}_Apply', low, hero)
            self.assertEqual(hero[attribute],50+baseline)

if __name__ == '__main__':
    unittest.main()
