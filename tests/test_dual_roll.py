"""Run emitted physical damage and stock AI estimates with fixed dice."""
import re
import unittest
from test_hiring import SDK, agent
from test_equipment_damage import DamageHarness
from build_bards_hall import extract_function
from bards_abilities import combat_functions

class DualRollTests(unittest.TestCase):
    def resolve(self, title='Blade_Dancer', function='damage', flourish=False, critical=False, quality=0, magic=0, refrain=False, attacktype=1):
        source=extract_function(combat_functions(SDK, extract_function),function)
        source=re.sub(r'#strength_div\b','8',source)
        source=re.sub(r'#(\w+)',r'"\1"',source)
        source=re.sub(r'\'s "(\w+)"',lambda m:'\'s "'+m[1].lower()+'"',source)
        vm=DamageHarness(source)
        a=agent(title=title,type='hero',subtype='hero',attacktype=attacktype,critical_chance=100 if critical else 0,
                ATTRIB_weapon_basic_damage=12,ATTRIB_Strength=9,
                ATTRIB_weapon_struct_bonus=quality,ATTRIB_weapon_magic_bonus=magic)
        d=agent(title='Test',type='monster',subtype='monster',ATTRIB_MAXHP=100)
        rolls=[];debits=[]
        def roll(n):
            rolls.append(n)
            return max(0,n-1)
        vm.calls.update({'getattribute':lambda a,k:a.fields.get(k,0),'randomnumber':roll,
            'getunitplayernumber':lambda a:1 if a is d else 0,
            'checkeffector':lambda owner,name:owner is a and refrain and name=='Bards_Refrain_Icon','createeffector':lambda *_:None,
            'createspellunit':lambda *_:None,'say':lambda *_:None,'playsound':lambda *_:None,
            'bards_direct_damage':lambda a,d,x:x,'bards_renown_hit':lambda *_:None,
            'bards_finale_record':lambda *_:None,
            'bards_consume_flourish':lambda *_:flourish,
            'bards_refrain_bonus':lambda source:3 if source is a and refrain else 0,
            'adjustattribute':lambda a,k,x:debits.append(x)})
        vm.call(function,a,d)
        self.assertEqual(len(debits),1)
        return -debits[0],rolls

    def test_offhand_once_and_other_heroes_unchanged(self):
        dmg,rolls=self.resolve()
        self.assertEqual(dmg,21)
        self.assertEqual(rolls.count(8),1)
        self.assertEqual(self.resolve(title='Paladin')[0],13)

    def test_upgrades_and_flourish_added_once(self):
        self.assertEqual(self.resolve(quality=3,magic=3)[0],27)
        self.assertEqual(self.resolve(flourish=True)[0],24)

    def test_critical_bypasses_both_weapon_dice(self):
        dmg,rolls=self.resolve(critical=True)
        self.assertEqual(dmg,100)
        self.assertNotIn(12,rolls)
        self.assertNotIn(8,rolls)

    def test_refrain_applies_once_to_armed_and_unarmed_hits(self):
        for title, kind in (('Blade_Dancer', 1), ('Paladin', 1), ('Monk', 0)):
            self.assertEqual(self.resolve(title=title, attacktype=kind, refrain=True)[0],
                             self.resolve(title=title, attacktype=kind)[0] + 3)

    def test_ai_adds_only_dancer_offhand(self):
        source=extract_function(combat_functions(SDK,extract_function),'hero_damage')
        source=source.replace('#strength_div','8')
        source=re.sub(r'#(\w+)',r'"\1"',source)
        source=re.sub(r'\'s "(\w+)"',lambda m:'\'s "'+m[1].lower()+'"',source)
        vm=DamageHarness(source)
        vm.calls.update({'hero_weapon_value':lambda _:18,'getattribute':lambda a,k:9})
        self.assertEqual(vm.call('hero_damage',agent(title='Blade_Dancer')),27)
        self.assertEqual(vm.call('hero_damage',agent(title='Paladin')),19)
