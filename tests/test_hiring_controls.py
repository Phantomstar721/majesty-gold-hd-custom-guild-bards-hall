import re
import struct
import unittest
from test_hiring import ROOT, SDK, GPLSubset, agent
from build_bards_hall import extract_function
from bards_hiring_panel import STOCK_CLOSE
from bards_panel import records, control_index
from cam_io import read, get


class HiringControlTests(unittest.TestCase):
    def runtime(self):
        source=(ROOT/'src/gpl/Bards_Hiring.gpl').read_text()
        vm=GPLSubset(re.sub(r'#(\w+)',r'"\1"',source))
        return vm

    def test_missing_state_is_open_and_each_guild_is_independent(self):
        vm=self.runtime()
        first,second=agent(),agent()
        self.assertTrue(vm.call('Bards_Hiring_Is_Open',first))
        first['BardsHiringClosed']=True
        self.assertFalse(vm.call('Bards_Hiring_Is_Open',first))
        self.assertTrue(vm.call('Bards_Hiring_Is_Open',second))
        first['BardsHiringClosed']=False
        self.assertTrue(vm.call('Bards_Hiring_Is_Open',first))

    def test_closed_guild_rejects_available_bard_before_assignment(self):
        vm=self.runtime()
        guild=agent(BardsHiringClosed=True)
        vm.calls['bards_hire_alive']=lambda _:True
        vm.calls['bards_is_bard']=lambda _:True
        self.assertFalse(vm.call('Bards_Hire_Available',agent(),agent(),guild))
        # Active contract validity deliberately does not read the admission flag.
        source=(ROOT/'src/gpl/Bards_Hiring.gpl').read_text()
        for name in ('Bards_Hire_Valid','Bards_Hire_Condition','Bards_Hire_Guild'):
            self.assertNotIn('Bards_Hiring_Is_Open',extract_function(source,name))

    def test_intent_distinguishes_paid_and_voluntary_support_for_all_types(self):
        vm=self.runtime()
        vm.calls['specifyintent']=lambda hero,value:hero.__setitem__('intent',value)
        for title in ('Troubadour','Spellsinger','Blade_Dancer'):
            hero=agent(title=title)
            vm.call('Bards_Follow_Intent',hero)
            self.assertEqual(hero['intent'],'intent_following_and_supporting')
            hero['BardsHirePatron']=agent()
            vm.call('Bards_Follow_Intent',hero)
            self.assertEqual(hero['intent'],'Bards_Intent_Hired_Support')

    def test_button_template_is_literal_stock(self):
        stock=read(SDK.parent.parent/'DataMX/mx_textdata.cam')
        menu=records(get(stock,b'SMNU',b'MX22'))
        expected=menu[control_index(menu,0x22AC)]
        self.assertEqual(struct.pack('<'+'I'*len(STOCK_CLOSE),*STOCK_CLOSE),expected)

if __name__=='__main__':unittest.main()
