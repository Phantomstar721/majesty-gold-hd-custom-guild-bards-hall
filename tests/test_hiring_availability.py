"""Hiring interrupts only approved tasks and rechecks availability on arrival."""
import re
import unittest
from test_hiring import ROOT, agent
from test_deflect import ImpactHarness


class HiringAvailabilityTests(unittest.TestCase):
    def runtime(self):
        vm = ImpactHarness(re.sub(r'#(\w+)', r'"\1"', (ROOT/'src/gpl/Bards_Hiring.gpl').read_text()))
        for name in ('hero_wander','bards_spellsinger_wander','bards_dancer_wander',
                     'travel_to_exp','travel_to','travel_to_safe','bards_travel_support',
                     'bards_follow_support','rest_at_guild','done_resting_guild'):
            vm.calls[name] = lambda *a: None
        guild = agent(title='Bards_Hall',player=0,ATTRIB_HP=100,ATTRIB_FirstStageBuilt=1)
        patron = agent(title='Wizard',player=0,subtype='Hero',ATTRIB_HP=100)
        bard = agent(title='Blade_Dancer',player=0,home=guild,ATTRIB_HP=90,ATTRIB_MaxHP=100,
            StartingScript='ordinary',BasicScript='ordinary',ActiveScript='ordinary',
            BackScript='ordinary',Target=None,BackTarget=None,inside=False,near=False,engaged=False,low=False)
        guild['Members']=[bard]
        vm.calls.update(getattribute=lambda h,k:h.fields.get(k,0),
            getunitplayernumber=lambda h:h['player'],
            insidebuilding=lambda h:h.fields.get('inside',False),
            distancebetweenagents=lambda h,g:100 if h['near'] else 2000,
            bards_contract_state=lambda h,k:h.fields.get('contract',0),
            bards_follow_target_eligible=lambda *a:True,
            notvalid_attacker=lambda h:not h.alive,
            haslowhp=lambda h:h.fields.get('low',False),
            bards_hero_engaged=lambda h:h.fields.get('engaged',False))
        return vm,patron,bard,guild

    def test_distant_walking_wandering_and_exploring_members_qualify(self):
        for task in ('hero_wander','bards_spellsinger_wander','bards_dancer_wander',
                     'travel_to_exp','travel_to','travel_to_safe'):
            vm,p,b,g=self.runtime()
            b['ActiveScript']=vm.calls[task]
            self.assertTrue(vm.call('Bards_Hire_Available',b,p,g),task)

    def test_protected_tasks_and_claims_are_not_interrupted(self):
        for state in ('combat','quest','contract','low','shopping','flee','performance','travel_shop','travel_fight'):
            vm,p,b,g=self.runtime()
            if state=='combat': b['engaged']=True
            elif state=='quest': b['AGAcceptedQuest']=b
            elif state=='contract': b['contract']=1
            elif state=='low': b['low']=True
            elif state.startswith('travel_'):
                b['ActiveScript']=vm.calls['travel_to']; b['BackScript']=state
            else: b['ActiveScript']=state
            self.assertFalse(vm.call('Bards_Hire_Available',b,p,g),state)

    def test_peaceful_follower_can_switch_but_engaged_leader_is_protected(self):
        vm,p,b,g=self.runtime()
        b['title']='Troubadour'
        b['BasicScript']=vm.calls['bards_follow_support']
        b['BackScript']=b['BasicScript']
        b['ActiveScript']=vm.calls['bards_travel_support']
        leader=agent(ATTRIB_HP=100,engaged=False)
        b['BackTarget']=leader
        self.assertTrue(vm.call('Bards_Hire_Available',b,p,g))
        leader['engaged']=True
        self.assertFalse(vm.call('Bards_Hire_Available',b,p,g))

    def test_recuperating_or_visiting_bard_stays_inside(self):
        vm,p,b,g=self.runtime()
        b['inside']=True; b['Target']=g; b['ActiveScript']=vm.calls['rest_at_guild']
        self.assertFalse(vm.call('Bards_Hire_Available',b,p,g))
        b['ATTRIB_HP']=100
        self.assertTrue(vm.call('Bards_Hire_Available',b,p,g))
        b['Target']=agent()
        self.assertFalse(vm.call('Bards_Hire_Available',b,p,g))

    def test_nearby_precedes_class_and_arrival_reselects(self):
        vm,p,remote,g=self.runtime()
        local=agent(**dict(remote.fields)); local['title']='Spellsinger'; local['near']=True
        g['Members']=[remote,local]
        self.assertIs(vm.call('Bards_Hire_Choose',p,g),local)
        remote['near']=True
        self.assertIs(vm.call('Bards_Hire_Choose',p,g),remote)
        remote['engaged']=True
        self.assertIs(vm.call('Bards_Hire_Choose',p,g),local)
        local['engaged']=True
        self.assertIsNone(vm.call('Bards_Hire_Choose',p,g))

if __name__ == '__main__': unittest.main()
