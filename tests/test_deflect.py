"""Execute emitted impact code; native flight, rendering and saves are external."""
from collections import deque
import re
import unittest
from unittest.mock import patch
from test_hiring import ROOT, SDK, GPLSubset, agent, harness
from build_bards_hall import extract_function
from bards_abilities import clone_arcane_note, combat_functions, deflect_functions

STOCK = (SDK / 'GPLMx/TaskModules/Subtasks/mx_Make_Attack.gpl').read_text(encoding='cp1252')
SPELLS = (SDK / 'GPLMx/TaskModules/Subtasks/mx_Spells.gpl').read_text(encoding='cp1252')
GENERATED = deflect_functions(SDK, extract_function)


class ForeachParser(harness._Parser):
    def statement(self):
        if self.tokens[self.pos] == 'foreach':
            self.take()
            variable = self.take()
            self.take('in')
            values = self.until('do')
            return ('foreach', variable, values, self.statement())
        return super().statement()


class ImpactHarness(GPLSubset):
    def __init__(self, program):
        with patch.object(harness, '_Parser', ForeachParser):
            super().__init__(program)

    def run(self, node, env):
        if node[0] == 'foreach':
            for value in list(self.value(node[2], env)):
                env[node[1]] = value
                self.run(node[3], env)
        else:
            super().run(node, env)


class DeflectTests(unittest.TestCase):
    def runtime(self):
        program = GENERATED + (ROOT / 'src/gpl/Bards_Deflect.gpl').read_text()
        program += extract_function((ROOT / 'src/gpl/Bards_Dancer.gpl').read_text(), 'Bards_Dancer_Level')
        for name in ('spellhit', 'spell_attack', 'player_spell_attack'):
            program += extract_function(STOCK, name)
        combat = combat_functions(SDK, extract_function)
        for name in ('make_attack', 'Bards_Echo_Attack'):
            program += extract_function(combat, name)
        program += clone_arcane_note(SDK, extract_function)
        program = program.replace('#Deathmatch_Hero_Magic_Resist', '20')
        program = re.sub(r'#(\w+)', r'"\1"', program)
        vm = ImpactHarness(program)
        caster = agent(title='Ranger', type='hero', subtype='Hero', attacktype=2,
                       Attack_Action='ranger_arrow', ATTRIB_HP=5, ATTRIB_MaxHP=20)
        dancer = agent(title='Blade_Dancer', type='hero', Type='Hero', subtype='Hero',
                       ATTRIB_ExperienceLevel=5, ATTRIB_HP=20, ATTRIB_MaxHP=20,
                       Immune_to_poison=False, immune_to_poison=False)
        clock, events, rolls = [10000], [], deque([1, 99] * 20)

        def random_number(limit):
            result = rolls.popleft()
            self.assertLess(result, limit)
            events.append(('roll', result))
            return result

        def effect(target, name, *args):
            if name == 'Bards_Deflect_Flash':
                self.assertEqual(target['BardsDeflectedAt'], clock[0])
            events.append(('effect', name))

        vm.calls.update({
            'getattribute': lambda a, key: a.fields.get(key, 0),
            'getspellattribute': lambda *_: 0,
            'notvalid_attacker': lambda a: a is None or not a.alive,
            'notvalid': lambda a: a is None or not a.alive,
            'isfrozen': lambda _: False,
            'mm_simulationtime': lambda: clock[0],
            'mm_simulationelapsed': lambda t: (clock[0] - t) & 0xffffffff,
            'gettohit': lambda _: 90,
            'gettoavoid': lambda *_: 55,
            'randomnumber': random_number,
            'react': lambda *_: events.append(('react',)),
            'react_player_spell': lambda *_: events.append(('player-react',)),
            'exp_value': lambda *_: (events.append(('exp-value',)), 25)[1],
            'attack_end': lambda _, xp: events.append(('xp', xp)),
            'spelldamage': lambda *_: events.append(('damage',)),
            'bards_echo_damage': lambda *_: events.append(('echo-damage',)),
            'bards_ordinary_damage': lambda *_: events.append(('weapon-damage',)),
            'bards_arcane_attack': lambda *_: events.append(('note-damage',)),
            'bards_flourish_target': lambda *_: None,
            'bards_try_riposte': lambda *_: events.append(('riposte-check',)),
            'hascamouflage': lambda *_: False,
            'checkeffector': lambda *_: False,
            'createeffector': effect,
            'playsound': lambda *args: events.append(('sound', args[1])),
            'heal': lambda *args: events.append(('heal', args[-1])),
            'poison_begin': lambda *_: events.append(('poison',)),
            'ratman_plague_begin': lambda *_: events.append(('plague',)),
            'does_resist_fire': lambda _: (events.append(('fire-resist',)), False)[1],
            'createmissile': lambda *args: events.append(('missile', args[0])),
        })
        return vm, caster, dancer, clock, events, rolls

    def test_physical_accuracy_then_deflect_then_dodge_when_cooling_down(self):
        vm, caster, dancer, clock, events, rolls = self.runtime()
        vm.call('make_attack', caster, dancer)
        self.assertEqual([e[0] for e in events], ['react', 'roll', 'effect', 'exp-value', 'xp'])
        self.assertEqual(dancer['BardsDeflectedAt'], clock[0])
        events.clear()
        rolls.clear()
        rolls.extend((1, 99))
        vm.call('make_attack', caster, dancer)
        self.assertEqual([e[0] for e in events], ['react', 'roll', 'roll', 'exp-value', 'weapon-damage', 'xp'])

    def test_accuracy_miss_melee_siege_and_unavailable_dancers_do_not_consume(self):
        vm, caster, dancer, _, events, rolls = self.runtime()
        rolls.clear()
        rolls.append(99)
        self.assertEqual(vm.call('hit', caster, dancer), 3)
        self.assertNotIn('BardsDeflectedAt', dancer.fields)
        for mode in ('melee', 'siege', 'low-level', 'frozen', 'ordinary', 'dead'):
            vm, caster, dancer, _, events, _ = self.runtime()
            if mode == 'melee': caster['attacktype'] = 1
            if mode == 'siege': caster['attacktype'], caster['Attack_Action'] = 5, 'Ballista_Bolt'
            if mode == 'low-level': dancer['ATTRIB_ExperienceLevel'] = 4
            if mode == 'frozen': vm.calls['isfrozen'] = lambda _: True
            if mode == 'ordinary': dancer['title'] = 'Warrior'
            if mode == 'dead': dancer.alive = False
            self.assertEqual(vm.call('hit', caster, dancer), 1)
            self.assertNotIn('BardsDeflectedAt', dancer.fields)
            self.assertEqual(sum(e[0] == 'roll' for e in events), 2)

    def test_single_shared_cooldown_exact_boundary_and_signed_wrap(self):
        vm, caster, dancer, clock, events, rolls = self.runtime()
        self.assertTrue(vm.call('Bards_Deflect_Spell', caster, dancer))
        self.assertFalse(vm.call('Bards_Deflect_Physical', caster, dancer))
        clock[0] += 7999
        self.assertFalse(vm.call('Bards_Deflect_Player', dancer))
        clock[0] += 1
        self.assertTrue(vm.call('Bards_Deflect_Physical', caster, dancer))
        self.assertFalse(vm.call('Bards_Deflect_Spell', caster, dancer))
        dancer['BardsDeflectedAt'], clock[0] = -500, 7500
        self.assertTrue(vm.call('Bards_Deflect_Player', dancer))

    def test_direct_spell_interception_blocks_damage_status_and_healing_once(self):
        for callback in ('Energy_Blast_Hit', 'Pestilence_missile_Hit', 'Infectious_Cloud_Hit',
                         'Drain_Life_Hit', 'Life_Leach_Hit', 'Bards_Arcane_Note_Hit'):
            vm, caster, dancer, _, events, _ = self.runtime()
            vm.call(callback, caster, dancer)
            self.assertEqual(events, [('react',), ('exp-value',), ('roll', 1),
                                      ('effect', 'Bards_Deflect_Flash'), ('xp', 25)], callback)

    def test_ordinary_spell_mr_and_attached_payload_remain_stock_during_cooldown(self):
        for callback in ('Energy_Blast_Hit', 'Pestilence_missile_Hit', 'Drain_Life_Hit', 'Life_Leach_Hit'):
            vm, caster, dancer, clock, actual, _ = self.runtime()
            dancer['BardsDeflectedAt'] = clock[0]
            vm.call(callback, caster, dancer)
            reference = ImpactHarness(re.sub(r'#(\w+)', r'"\1"', extract_function(SPELLS, callback)))
            # Same native mocks, but the unmodified stock callback supplies the
            # expected ordering. The shared resolver executes its real stock GPL.
            expected = list(actual)
            actual.clear()
            # Replay the exact RNG sequence used above.
            replay = deque(e[1] for e in expected if e[0] == 'roll')
            vm.calls['randomnumber'] = lambda _: (actual.append(('roll', replay[0])), replay.popleft())[1]
            reference.calls.update(vm.calls)
            reference.call(callback, caster, dancer)
            self.assertEqual(actual, expected, callback)
            self.assertEqual(sum(e[0] == 'xp' for e in actual), 1)

    def test_fire_resistance_once_and_hammer_return_survives_block(self):
        for immune in (False, True):
            for callback in ('Fire_Blast_Hit', 'Fire_Hammer_Hit'):
                vm, caster, dancer, _, events, _ = self.runtime()
                vm.calls['does_resist_fire'] = lambda _: (events.append(('fire-resist',)), immune)[1]
                vm.call(callback, caster, dancer)
                self.assertEqual(sum(e[0] == 'fire-resist' for e in events), 1)
                self.assertEqual('BardsDeflectedAt' in dancer.fields, not immune)
                self.assertFalse(any(e[0] == 'damage' for e in events))
                if callback == 'Fire_Hammer_Hit':
                    self.assertEqual(events[-1], ('missile', 'Fire_Hammer_False_Projectile'))

    def test_player_spells_and_echo_share_block_without_extra_xp_or_payload(self):
        for callback in ('Fire_Strike_Damage', 'Lightning_Bolt_Damage'):
            vm, _, dancer, _, events, _ = self.runtime()
            vm.call(callback, dancer)
            self.assertEqual(events, [('player-react',), ('roll', 1), ('effect', 'Bards_Deflect_Flash')])
        vm, caster, dancer, _, events, _ = self.runtime()
        vm.call('Bards_Echo_Attack', caster, dancer, 10)
        self.assertFalse(any(e[0] == 'echo-damage' for e in events))
        self.assertEqual(sum(e[0] == 'xp' for e in events), 1)


if __name__ == '__main__':
    unittest.main()
