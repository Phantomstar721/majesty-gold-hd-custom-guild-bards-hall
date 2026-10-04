"""Stock callback preservation and actual Refrain HP debits at bypass boundaries."""
import re
import unittest
from test_hiring import SDK, ROOT, agent
from test_equipment_damage import DamageHarness
from build_bards_hall import extract_function
from bards_abilities import combat_functions
from majesty_cam.spell_origin import SOURCE as ORIGIN_SOURCE

STOCK = (SDK/'GPLMx/TaskModules/Subtasks/mx_Make_Attack.gpl').read_text(encoding='cp1252')
SPELLS = (SDK/'GPLMx/TaskModules/Subtasks/mx_Spells.gpl').read_text(encoding='cp1252')
GENERATED = combat_functions(SDK, extract_function)

class RefrainDamageTests(unittest.TestCase):
    def test_real_origin_gate_preserves_sovereign_damage_and_current_hero_bonus(self):
        for adapter in ('Bards_PlayerSpellAttackAttributed', 'Bards_PeriodicPlayerAttributed'):
            program = '\n'.join(extract_function(GENERATED, n) for n in (adapter, adapter+'Damage'))
            program += ORIGIN_SOURCE
            effects = (ROOT/'src/gpl/Bards_Effects.gpl').read_text()
            program += '\n'.join(extract_function(effects, n) for n in
                                 ('Bards_Refrain_Bonus', 'Bards_Direct_Damage'))
            globals_text = (SDK/'GPLMx/mx_Globals.gpl').read_text(encoding='cp1252')
            for key in ('intelligence_div', 'armor_magic_mult'):
                value = re.search(r'(?im)^\s*expression\s+#'+key+r'\s+(\d+)', globals_text).group(1)
                program = re.sub('#'+key+r'\b', value, program, flags=re.I)
            program = re.sub(r'#(\w+)', r'"\1"', program)
            hero = agent(type='Invisible', subtype='hero', buff=True, player=1, ATTRIB_intelligence=100)
            nonhero = agent(type='Building', subtype='guild', buff=True, player=1)
            child = agent(type='Spell', MM_SpellOrigin_v1=hero, player=1)
            sovereign = agent(type='Spell', player=1, buff=True)
            forged_origin = agent(type='Spell', MM_SpellOrigin_v1=nonhero, player=1)
            for source, expected in ((hero, -13), (child, -13), (sovereign, -10),
                                     (nonhero, -10), (forged_origin, -10)):
                vm = DamageHarness(program)
                target = agent(subtype='hero', buff=False)
                debits, events = [], []
                vm.calls.update(notvalid=lambda a:a is None or not a.alive,
                    react_player_spell=lambda _:events.append('react'), spellhit=lambda _:1,
                    randomnumber=lambda _:9,
                    getattribute=lambda a,k:0 if a is target else self.fail('Caster entered stock attribute math'),
                    checkeffector=lambda a,k:a.fields.get('buff', False),
                    bards_renown_hit=lambda *_:None,
                    adjustattribute=lambda a,k,d:debits.append(d))
                vm.call(adapter, source, target, 20, 1)
                self.assertEqual(debits, [expected], (adapter, source.fields))
                self.assertEqual(events, ['react'])
            # Delayed effects query the present buff, not a captured +3 value.
            hero['buff'] = False
            vm = DamageHarness(program)
            debits = []
            target = agent(subtype='hero', buff=False)
            vm.calls.update(notvalid=lambda a:a is None or not a.alive,
                react_player_spell=lambda _:None, spellhit=lambda _:1, randomnumber=lambda _:9,
                getattribute=lambda *_:0, checkeffector=lambda a,k:a.fields.get('buff', False),
                bards_renown_hit=lambda *_:None, adjustattribute=lambda a,k,d:debits.append(d))
            vm.call(adapter, child, target, 20, 1)
            self.assertEqual(debits, [-10])

    def test_attributed_target_only_damage_preserves_null_attacker_and_bonus_once(self):
        for adapter in ('Bards_PlayerSpellAttackAttributed', 'Bards_PeriodicPlayerAttributed'):
            program = '\n'.join(extract_function(GENERATED, n) for n in (adapter, adapter+'Damage'))
            globals_text = (SDK/'GPLMx/mx_Globals.gpl').read_text(encoding='cp1252')
            for key in ('intelligence_div', 'armor_magic_mult'):
                value = re.search(r'(?im)^\s*expression\s+#'+key+r'\s+(\d+)', globals_text).group(1)
                program = re.sub('#'+key+r'\b', value, program, flags=re.I)
            program = re.sub(r'#(\w+)', r'"\1"', program)
            for armor, expected in ((0, -13), (100, 0)):
                vm = DamageHarness(program)
                source, target = agent(ATTRIB_intelligence=100), agent(subtype='hero')
                debits, origins, attackers = [], [], []
                vm.calls.update(notvalid=lambda _:False, react_player_spell=lambda _:None,
                    spellhit=lambda _:1, randomnumber=lambda _:9,
                    getattribute=lambda a,k: armor if a is target else self.fail('Caster must not enter stock attribute math'),
                    bards_refrain_bonus=lambda a: origins.append(a) or 3,
                    bards_direct_damage=lambda a,t,d: attackers.append(a) or d,
                    bards_renown_hit=lambda *_:None,
                    adjustattribute=lambda a,k,d:debits.append(d))
                vm.call(adapter, source, target, 20, 1)
                self.assertEqual(debits, [expected])
                self.assertEqual(origins, [source])
                self.assertTrue(all(a is None for a in attackers))

    def test_stock_lifecycle_changes_only_damage_dispatch(self):
        changed = extract_function(GENERATED, 'player_spell_attack')
        restored = changed.replace('$Bards_Direct_Spell_Damage(', '$spelldamage(')
        self.assertEqual(restored, extract_function(STOCK, 'player_spell_attack'))
        periodic = extract_function(GENERATED, 'Bards_Periodic_Player_Spell_Attack')
        self.assertEqual(periodic.replace('Bards_Periodic_Player_Spell_Attack', 'player_spell_attack'), restored)
        shield = extract_function(GENERATED, 'Damage_Shield_Hit')
        stock_shield = extract_function(SPELLS, 'Damage_Shield_Hit').split("// --- Gorgon's")[0].rstrip()
        self.assertEqual(shield.replace('$Bards_Direct_Damage($NullAgent(), ThisAgent, #Damage_Shield_Damage)', '#Damage_Shield_Damage').rstrip(), stock_shield)
        wind = extract_function(GENERATED, 'Wind_Storm_Active')
        self.assertEqual(wind.replace('Bards_Periodic_Player_Spell_Attack', 'player_spell_attack'), extract_function(SPELLS, 'Wind_Storm_Active'))

    def resolve(self, name, refrain, roll=9, hit=1, dead=False):
        program = '\n'.join(extract_function(GENERATED,n) for n in
            ('player_spell_attack','Bards_Periodic_Player_Spell_Attack','Bards_Direct_Spell_Damage','Damage_Shield_Hit'))
        program += extract_function(STOCK,'spelldamage')
        program += extract_function((ROOT/'src/gpl/Bards_Effects.gpl').read_text(),'Bards_Direct_Damage')
        globals_text=(SDK/'GPLMx/mx_Globals.gpl').read_text(encoding='cp1252')
        for key in ('intelligence_div','armor_magic_mult','Damage_Shield_Damage'):
            value=re.search(r'(?im)^\s*expression\s+#'+key+r'\s+(\d+)',globals_text).group(1)
            program=re.sub('#'+key+r'\b',value,program,flags=re.I)
        program=re.sub(r'#(\w+)',r'"\1"',program)
        vm=DamageHarness(program); target=agent(subtype='hero'); debits=[]; events=[]
        vm.calls.update(notvalid=lambda _:False, isdead=lambda _:dead,
            react_player_spell=lambda _:events.append('react'), spellhit=lambda _:hit,
            randomnumber=lambda _:roll, getattribute=lambda *_:0,
            checkeffector=lambda _,effect:refrain and effect=='Bards_Refrain_Icon',
            bards_renown_hit=lambda *_:None,
            bards_refrain_bonus=lambda _:0,
            adjustattribute=lambda _,key,amount:debits.append(amount))
        vm.call(name,target,*(() if name=='Damage_Shield_Hit' else (20,1)))
        return debits,events

    def test_direct_hit_reduces_once_and_clamps_zero(self):
        self.assertEqual(self.resolve('player_spell_attack',False),([-10],['react']))
        self.assertEqual(self.resolve('player_spell_attack',True),([-7],['react']))
        self.assertEqual(self.resolve('player_spell_attack',True,roll=0),([0],['react']))
        self.assertEqual(self.resolve('player_spell_attack',True,hit=2),([],['react']))

    def test_periodic_is_unchanged_and_shield_preserves_dead_guard(self):
        self.assertEqual(self.resolve('Bards_Periodic_Player_Spell_Attack',True),([-10],['react']))
        baseline=self.resolve('Damage_Shield_Hit',False)[0][0]
        self.assertEqual(self.resolve('Damage_Shield_Hit',True)[0],[min(0,baseline+3)])
        self.assertEqual(self.resolve('Damage_Shield_Hit',True,dead=True),([],[]))

if __name__=='__main__': unittest.main()
