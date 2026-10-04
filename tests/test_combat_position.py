"""Approved two-target positioning uses native movement and existing follow ticks."""
import math
import re
import unittest
from test_hiring import ROOT, agent
from test_deflect import ImpactHarness

class CombatPositionTests(unittest.TestCase):
    def runtime(self):
        source = (ROOT/'src/gpl/Bards_Combat_Position.gpl').read_text()
        vm = ImpactHarness(re.sub(r'\bcoordinate\b', 'integer', source))
        leader, enemy = agent(xy=(0,0)), agent(xy=(300,0))
        caster = agent(xy=(-40,0), Target=leader, Destination=(-40,0), moving=False)
        moves, stops = [], []
        def move(h, point, flags):
            moves.append((point,flags)); h['moving'] = True
        def stop(h):
            stops.append(h); h['moving'] = False
        vm.calls.update(notvalid=lambda h: h is None or not h.alive,
            locationof=lambda h:h['xy'], distancebetweencoords=lambda a,b:int(math.dist(a,b)),
            distancebetweenagents=lambda a,b:int(math.dist(a['xy'],b['xy'])),
            getx=lambda p:p[0], gety=lambda p:p[1], makecoord=lambda x,y:(x,y),
            ismoving=lambda h:h['moving'], move=move, stopmoving=stop)
        return vm,caster,leader,enemy,moves,stops

    def test_intersection_move_preserves_follow_assignment_and_does_not_restart(self):
        vm,h,l,e,moves,stops = self.runtime()
        h['BackTarget'] = l
        self.assertTrue(vm.call('Bards_Combat_Position',h,l,e,180,180))
        point = moves[0][0]
        self.assertLessEqual(math.dist(point,l['xy']),180)
        self.assertLessEqual(math.dist(point,e['xy']),180)
        self.assertIs(h['BackTarget'],l)
        self.assertTrue(vm.call('Bards_Combat_Position',h,l,e,180,180))
        self.assertEqual(len(moves),1)
        h['moving'] = False # obstructed/failed native order is not spammed
        self.assertTrue(vm.call('Bards_Combat_Position',h,l,e,180,180))
        self.assertEqual(len(moves),1)

    def test_arrival_stops_at_cast_range_and_restores_follow_target(self):
        vm,h,l,e,moves,stops = self.runtime()
        vm.call('Bards_Combat_Position',h,l,e,180,180)
        h['xy'] = moves[0][0]
        self.assertFalse(vm.call('Bards_Combat_Position',h,l,e,180,180))
        self.assertEqual(stops,[h])
        self.assertIs(h['Target'],l)

    def test_impossible_overlap_or_lost_follow_range_does_not_chase(self):
        for enemy_xy,caster_xy in (((500,0),(0,0)),((300,0),(-200,0))):
            vm,h,l,e,moves,_ = self.runtime()
            h['xy'],e['xy'] = caster_xy,enemy_xy
            self.assertFalse(vm.call('Bards_Combat_Position',h,l,e,180,180))
            self.assertEqual(moves,[])

    def test_generic_distinct_ranges_and_diagonal_coordinates(self):
        vm,h,l,e,moves,_ = self.runtime()
        e['xy'] = (180,180)
        self.assertTrue(vm.call('Bards_Combat_Position',h,l,e,220,100))
        p=moves[0][0]
        self.assertLessEqual(math.dist(p,l['xy']),100)
        self.assertLessEqual(math.dist(p,e['xy']),220)

    def test_fight_end_cancels_only_owned_approach(self):
        vm,h,l,e,moves,stops = self.runtime()
        vm.call('Bards_Combat_Position',h,l,e,180,180)
        vm.calls.update(insidebuilding=lambda _:False, haslowhp=lambda _:False,
                        bards_song_engaged=lambda _:False)
        self.assertFalse(vm.call('Bards_Combat_Support',h,l))
        self.assertIs(h['Target'],l)
        self.assertEqual(stops,[h])
        vm.call('Bards_Combat_Support',h,l)
        self.assertEqual(stops,[h])

    def test_useful_buff_interrupts_approach_before_next_spell(self):
        vm,h,l,e,moves,stops = self.runtime()
        l['Target'] = e
        vm.call('Bards_Combat_Position',h,l,e,180,180)
        casts=[]
        vm.calls.update(insidebuilding=lambda _:False, haslowhp=lambda _:False,
            bards_song_engaged=lambda _:True, bards_troubadour_evaluate=lambda _:False,
            bards_song_party=lambda _:[l], isspellavailable=lambda _,name:name=='Bards_Valor',
            bards_song_useful=lambda *_:True,
            bards_try_song=lambda caster:casts.append((caster['moving'],caster['Target'])) or True)
        self.assertTrue(vm.call('Bards_Combat_Support',h,l))
        self.assertEqual(casts,[(False,l)])
        self.assertEqual(stops,[h])

    def test_leader_leaving_support_range_cancels_approach(self):
        vm,h,l,e,moves,stops = self.runtime()
        vm.call('Bards_Combat_Position',h,l,e,180,180)
        l['xy'] = (-400,0)
        vm.calls.update(insidebuilding=lambda _:False, haslowhp=lambda _:False,
            bards_song_engaged=lambda _:True, bards_troubadour_evaluate=lambda _:False)
        self.assertFalse(vm.call('Bards_Combat_Support',h,l))
        self.assertIs(h['Target'],l)
        self.assertEqual(stops,[h])

if __name__ == '__main__': unittest.main()
