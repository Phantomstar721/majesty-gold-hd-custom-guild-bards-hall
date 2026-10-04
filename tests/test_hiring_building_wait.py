import re
import unittest
from test_hiring import ROOT, GPLSubset, agent


class BuildingWaitTests(unittest.TestCase):
    def runtime(self):
        vm=GPLSubset(re.sub(r'#(\w+)',r'"\1"',(ROOT/'src/gpl/Bards_Hiring.gpl').read_text()))
        building=agent(type='Building',xy=(1000,1000))
        patron=agent(Target=building,inside=True)
        bard=agent(BardsHirePatron=patron,Target=patron,BackTarget=patron,
                   moving=False,distance=1000,evaluationscript=lambda h:False)
        events=[]
        def move(h,target,flags):
            h['moving']=True; events.append(('move',target,flags))
        def stop(h):
            h['moving']=False; events.append(('stop',))
        vm.calls.update(bards_hire_alive=lambda h:h is not None and h.alive,
            insidebuilding=lambda h:h['inside'], distancebetweenagents=lambda h,t:h['distance'],
            locationof=lambda h:h['xy'], ismoving=lambda h:h['moving'],
            move=move,stopmoving=stop,randomnumber=lambda _:0)
        return vm,bard,patron,building,events

    def test_remote_hire_moves_once_then_waits_outside(self):
        vm,b,p,g,events=self.runtime()
        self.assertTrue(vm.call('Bards_Hire_Wait',b))
        self.assertEqual(events,[('move',g,'avoid_vehicles')])
        self.assertIs(b['BackTarget'],p)
        vm.call('Bards_Hire_Wait',b)
        self.assertEqual(len(events),1)
        b['distance']=180
        vm.call('Bards_Hire_Wait',b)
        self.assertFalse(b['moving'])
        self.assertIs(b['Target'],p)

    def test_employer_exits_before_arrival(self):
        vm,b,p,g,events=self.runtime()
        vm.call('Bards_Hire_Wait',b)
        p['inside']=False
        self.assertFalse(vm.call('Bards_Hire_Wait',b))
        self.assertIs(b['Target'],p)
        self.assertFalse(b['moving'])

    def test_building_changes_redirect_and_invalid_building_stops(self):
        vm,b,p,g,events=self.runtime()
        vm.call('Bards_Hire_Wait',b)
        other=agent(type='Building',xy=(500,500))
        p['Target']=other
        vm.call('Bards_Hire_Wait',b)
        self.assertIs(events[-1][1],other)
        other.alive=False
        vm.call('Bards_Hire_Wait',b)
        self.assertEqual(events[-1],('stop',))
        self.assertIs(b['BackTarget'],p)

    def test_defense_takes_priority_and_no_contract_mutation(self):
        vm,b,p,g,events=self.runtime()
        b['evaluationscript']=lambda h:True
        self.assertTrue(vm.call('Bards_Hire_Wait',b))
        self.assertEqual(events,[])
        self.assertIs(b['BardsHirePatron'],p)

if __name__=='__main__': unittest.main()
