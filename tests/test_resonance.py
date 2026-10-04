"""Run emitted GPL for shared buildup, hit ordering, consumption and expiry."""
import re
import unittest
from test_hiring import ROOT, SDK, GPLSubset, agent
from build_bards_hall import extract_function
from bards_abilities import combat_functions, build_descriptions
from test_deflect import ImpactHarness


class ResonanceTests(unittest.TestCase):
    def runtime(self):
        authored = (ROOT/'src/gpl/Bards_Spellsinger.gpl').read_text()
        effects = (ROOT/'src/gpl/Bards_Effects.gpl').read_text()
        combat = combat_functions(SDK, extract_function)
        program = '\n'.join(extract_function(authored, n) for n in
                            ('Bards_Resonance_Count', 'Bards_Resonance_Add', 'Bards_Crescendo', 'Bards_Resonant_Burst_Hit'))
        program += extract_function(effects, 'Bards_Reverberation_End')
        for n in ('Bards_Arcane_Attack', 'Bards_Echo_Attack', 'Bards_Burst_Attack'):
            program += extract_function(combat, n)
        program = re.sub(r'#(\w+)', r'"\1"', program.replace('coordinate Center;', 'agent Center;'))
        vm = ImpactHarness(program)
        clock, active, events = [0], {}, []
        a = agent(title='Spellsinger', ATTRIB_ExperienceLevel=3)
        b = agent(title='Spellsinger', ATTRIB_ExperienceLevel=8)
        target = agent(Type='Monster')
        def create(t, name, duration):
            active[(id(t), name)] = clock[0]+duration
            events.append(('effect', name, duration))
        def check(t, name):
            return active.get((id(t), name), -1) > clock[0]
        def delete(t, name):
            active.pop((id(t), name), None)
            vm.call('Bards_Reverberation_End', t)
        def damage(caster, t, *_):
            events.append(('note', vm.call('Bards_Resonance_Count', t)))
            return 10
        vm.calls.update({
            'notvalid': lambda a: a is None or not a.alive,
            'notvalid_attacker': lambda a: a is None or not a.alive,
            'getattribute': lambda a,k: a.fields.get(k,0),
            'setattribute': lambda a,k,v: a.fields.__setitem__(k,v),
            'createeffector': create, 'checkeffector': check, 'deleteeffector': delete,
            'freeze_unit': lambda t: events.append(('freeze',t)),
            'specifyintent': lambda *_: None, 'react': lambda *_: None,
            'exp_value': lambda *_: 25, 'spellhit': lambda *_: 1,
            'locationof': lambda t: t, 'bards_arcane_damage': damage,
            'bards_echo_damage': lambda *_: 10,
            'bards_reverberate': lambda *_: None,
            'bards_deflect_spell': lambda *_: False,
            'attack_end': lambda *_: events.append(('xp',)),
        })
        return vm,a,b,target,clock,active,events

    def test_shared_cap_and_pre_hit_bonus(self):
        vm,a,b,t,_,_,events = self.runtime()
        for i in range(8):
            vm.call('Bards_Arcane_Attack', a if i%2 else b,t,10)
        self.assertEqual([e[1] for e in events if e[0]=='note'],[0,1,2,3,4,5,6,6])
        self.assertEqual(vm.call('Bards_Resonance_Count',t),6)
        self.assertEqual(len([e for e in events if e[0]=='xp']),8)

    def test_echo_adds_without_note_bonus_or_recursion(self):
        vm,a,_,t,_,_,events = self.runtime()
        vm.calls['bards_echo_damage'] = lambda *args: events.append(('echo',args[-2])) or 10
        for _ in range(3): vm.call('Bards_Echo_Attack',a,t,10)
        self.assertEqual(vm.call('Bards_Resonance_Count',t),3)
        self.assertEqual([e for e in events if e[0]=='echo'],[('echo',10)]*3)
        self.assertFalse(any(e[0]=='note' for e in events))

    def test_expiry_refresh_and_late_callback(self):
        vm,a,_,t,clock,_,_ = self.runtime()
        vm.call('Bards_Resonance_Add',a,t)
        clock[0]=9999
        vm.call('Bards_Resonance_Add',a,t)
        clock[0]=10000
        self.assertEqual(vm.call('Bards_Resonance_Count',t),2)
        clock[0]=19999
        self.assertEqual(vm.call('Bards_Resonance_Count',t),0)
        vm.call('Bards_Reverberation_End',t)
        vm.call('Bards_Resonance_Add',a,t)
        self.assertEqual(vm.call('Bards_Resonance_Count',t),1)

    def test_burst_consumes_shared_stacks_and_rebuilds(self):
        for stacks in (0,1,6):
            vm,a,b,t,_,_,events = self.runtime()
            for _ in range(stacks): vm.call('Bards_Resonance_Add',a,t)
            events.clear()
            vm.call('Bards_Burst_Attack',b,t,23)
            self.assertEqual(vm.call('Bards_Resonance_Count',t),0)
            self.assertEqual([e[2] for e in events if e[:2]==('effect','Bards_Crescendo_Icon')],
                             [stacks*500] if stacks else [])
            vm.call('Bards_Resonance_Add',a,t)
            self.assertEqual(vm.call('Bards_Resonance_Count',t),1)

    def test_resisted_blocked_or_zero_damage_does_not_build_or_consume(self):
        for action in ('Bards_Arcane_Attack','Bards_Echo_Attack','Bards_Burst_Attack'):
            for result in (2,3):
                vm,a,b,t,_,_,events = self.runtime()
                vm.call('Bards_Resonance_Add',a,t)
                vm.calls['spellhit'] = lambda *_: result
                vm.call(action,b,t,10)
                self.assertEqual(vm.call('Bards_Resonance_Count',t),1)
                self.assertFalse(any(e[0]=='freeze' for e in events))
            vm,a,b,t,_,_,_ = self.runtime()
            vm.call('Bards_Resonance_Add',a,t)
            vm.calls['bards_arcane_damage'] = vm.calls['bards_echo_damage'] = lambda *_: 0
            vm.call(action,b,t,10)
            self.assertEqual(vm.call('Bards_Resonance_Count',t),1)

    def test_area_consumes_each_victim_independently(self):
        vm,a,b,t,_,active,events = self.runtime()
        second = agent(Type='Monster')
        for _ in range(6): vm.call('Bards_Resonance_Add',a,t)
        for _ in range(2): vm.call('Bards_Resonance_Add',b,second)
        vm.calls['bards_burst_targets'] = lambda *_: [t,second]
        vm.call('Bards_Resonant_Burst_Hit',b,t)
        self.assertEqual(active[(id(t),'Bards_Crescendo_Icon')],3000)
        self.assertEqual(active[(id(second),'Bards_Crescendo_Icon')],1000)
        self.assertEqual(vm.call('Bards_Resonance_Count',t),0)
        self.assertEqual(vm.call('Bards_Resonance_Count',second),0)

    def test_unlock_and_dead_building_guards(self):
        vm,a,b,t,_,_,events = self.runtime()
        a['ATTRIB_ExperienceLevel']=2
        vm.call('Bards_Resonance_Add',a,t)
        self.assertEqual(vm.call('Bards_Resonance_Count',t),0)
        for kind in ('Building','Lair'):
            t['Type']=kind
            vm.call('Bards_Resonance_Add',b,t)
            vm.call('Bards_Crescendo',t)
            self.assertEqual(vm.call('Bards_Resonance_Count',t),0)
        t.alive=False
        vm.call('Bards_Resonance_Add',b,t)
        vm.call('Bards_Crescendo',t)
        self.assertFalse(any(e[0]=='freeze' for e in events))
        xml=build_descriptions(SDK)
        for name,level in (('Bards_Arcane_Note','1'),('Bards_Countermelody','5'),('Bards_Resonant_Burst','8')):
            self.assertEqual(xml.find(f'./Description[@Name="{name}"]/Game/CharacterLevel').get('value'),level)


if __name__ == '__main__': unittest.main()
