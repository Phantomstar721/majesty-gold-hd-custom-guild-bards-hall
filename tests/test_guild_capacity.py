"""Execute the actual stock callbacks with modeled native attribute boundaries.

The native map serialization/order manager are not emulated. This checks callback
ordering and ordinary saved values; native save/load remains an in-game exercise.
"""
import copy
import re
import tempfile
import unittest
from pathlib import Path

from test_hiring import SDK, GPLSubset, agent
from build_bards_hall import extract_function, build_gpl, data_block
from bards_progression import CAPACITY_BY_LEVEL, CAPACITY_PROPERTY, guild_prototype, progression_functions, validate_progression
from validate_bards_abilities import stock_equal, require


class Fields(dict):
    def __getitem__(self, key):
        return super().__getitem__(key.casefold())

    def __setitem__(self, key, value):
        super().__setitem__(key.casefold(), value)

    def __contains__(self, key):
        return super().__contains__(key.casefold())

    def get(self, key, default=None):
        return super().get(key.casefold(), default)


def unit(**values):
    result = agent()
    result.fields = Fields()
    for key, value in values.items():
        result[key] = value
    return result


class GuildCapacityTests(unittest.TestCase):
    def test_all_templates_instantiate_the_typed_private_prototype(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp)
            build_gpl(SDK, package / 'GPL')
            check = lambda: validate_progression(SDK, package, extract_function, data_block, stock_equal, require)
            check()
            declaration = package / 'GPL/Bards_Hall_Prototype.gpl'
            original = declaration.read_text()
            declaration.write_text(original.replace(f'integer {CAPACITY_PROPERTY};', ''))
            with self.assertRaisesRegex(ValueError, 'boundary changed'):
                check()
            declaration.write_text(original)
            data = package / 'GPL/Bards_Building_Data.dat'
            data.write_text(data.read_text().replace('{Bards_Hall_Prototype', '{Guild', 1))
            with self.assertRaisesRegex(ValueError, 'typed private Guild prototype'):
                check()

    def runtime(self, level=1, legendary=False, title='Bards_Hall', with_property=True):
        source = progression_functions(SDK, extract_function)
        vm = GPLSubset(re.sub(r'#(\w+)', r'"\1"', source))
        events = []
        vm.root['Quest_Number'] = 'QNumber_Legendary_Heroes' if legendary else 0
        guild = unit(title=title, subtype='Guild', Level=level,
                     ATTRIB_MaxGuildMembers=CAPACITY_BY_LEVEL[level],
                     ATTRIB_FirstStageBuilt=1, ATTRIB_CurrentStageBuilt=1,
                     ATTRIB_HP=300, ATTRIB_MaxHP=500, ATTRIB_QuickRepair=0,
                     upgradescript='basic_upgrade', birthscript2='guild_birth',
                     NativeStage=level, members=['existing-hero'])
        if with_property:
            # A template value is usable only when the instantiated prototype
            # declares it. This missing contract caused the live capacity1 bug.
            self.assertRegex(guild_prototype(SDK), r'\binteger\s+BardsCompletedCapacity\s*;')
            guild['BardsCompletedCapacity'] = CAPACITY_BY_LEVEL[level]

        def set_attribute(building, key, value):
            building[key] = value
            events.append(('set', key.casefold(), value))

        def advance_template(building):
            events.append(('template', building['NativeStage']))
            building['Level'] = building['NativeStage']
            if building['title'] == 'Bards_Hall':
                building['BardsCompletedCapacity'] = CAPACITY_BY_LEVEL[building['Level']]
            # Audited UpgradeAgentAttributes only updates GPL properties. It
            # deliberately does not reset native MaxGuildMembers here.

        vm.calls.update({
            'getattribute': lambda a, key: a.fields.get(key, 0),
            'setattribute': set_attribute,
            'upgradeagentattributes': advance_template,
            'runthread': lambda script, delay, a: events.append(('dispatch', script, delay, a['ATTRIB_MaxGuildMembers'])),
            'playsound': lambda *args: events.append(('sound', args)),
            'localchatmessage': lambda *args: events.append(('chat', args)),
            'getunitplayernumber': lambda _: 1,
        })
        return vm, guild, events

    @staticmethod
    def begin_upgrade(vm, guild):
        # Audited native description initialization precedes the synchronous
        # building_upgraded callback; GPL template values are still old here.
        guild['NativeStage'] += 1
        guild['ATTRIB_MaxGuildMembers'] = CAPACITY_BY_LEVEL[guild['NativeStage']]
        guild['ATTRIB_CurrentStageBuilt'] = 0
        vm.call('building_upgraded', guild)

    def test_both_upgrades_restore_capacity_before_scheduled_construction(self):
        vm, guild, events = self.runtime()
        for old_capacity, new_capacity in ((4, 6), (6, 8)):
            events.clear()
            self.begin_upgrade(vm, guild)
            self.assertEqual(guild['ATTRIB_MaxGuildMembers'], old_capacity)
            self.assertEqual(events, [('set', 'attrib_maxguildmembers', old_capacity),
                                      ('dispatch', 'basic_upgrade', 1, old_capacity)])
            # These are the two sides of the audited native member-count >= cap
            # comparison, not an independent implementation of native recruitment.
            for members in (old_capacity - 1, old_capacity, new_capacity - 1):
                self.assertEqual(members >= guild['ATTRIB_MaxGuildMembers'], members >= old_capacity)
            events.clear()
            vm.call('BuildingReachedMaxHP', guild)
            self.assertEqual(events[:2], [('template', guild['NativeStage']),
                                          ('set', 'attrib_maxguildmembers', new_capacity)])
            self.assertEqual(guild['ATTRIB_CurrentStageBuilt'], 1)
            self.assertEqual(guild['ATTRIB_MaxGuildMembers'], new_capacity)
            self.assertEqual(guild['members'], ['existing-hero'])
            vm.call('BuildingReachedMaxHP', guild)
            self.assertEqual(guild['ATTRIB_MaxGuildMembers'], new_capacity)

    def test_interruption_keeps_native_cap_and_completed_template_as_ordinary_state(self):
        vm, guild, _ = self.runtime(level=2)
        self.begin_upgrade(vm, guild)
        saved_fields = copy.deepcopy(guild.fields)
        restored = unit(**saved_fields)
        self.assertEqual(restored['ATTRIB_MaxGuildMembers'], 6)
        self.assertEqual(restored['BardsCompletedCapacity'], 6)
        self.assertEqual(restored['Level'], 2)
        self.assertEqual(restored['NativeStage'], 3)
        vm.call('BuildingReachedMaxHP', restored)
        self.assertEqual(restored['ATTRIB_MaxGuildMembers'], 8)

    def test_legendary_exception_applies_at_start_and_after_template_copy(self):
        vm, guild, events = self.runtime(legendary=True)
        self.begin_upgrade(vm, guild)
        self.assertEqual(guild['ATTRIB_MaxGuildMembers'], 1)
        self.assertEqual(events[-1], ('dispatch', 'basic_upgrade', 1, 1))
        events.clear()
        vm.call('BuildingReachedMaxHP', guild)
        self.assertEqual(events[:3], [('template', 2), ('set', 'attrib_maxguildmembers', 6),
                                      ('set', 'attrib_maxguildmembers', 1)])

    def test_repairs_and_first_birth_do_not_apply_upgrade_capacity(self):
        for first_built in (0, 1):
            vm, guild, events = self.runtime(level=2)
            guild['ATTRIB_FirstStageBuilt'] = first_built
            guild['ATTRIB_MaxGuildMembers'] = 19  # Existing scenario value.
            vm.call('BuildingReachedMaxHP', guild)
            self.assertEqual(guild['ATTRIB_MaxGuildMembers'], 19)
            self.assertFalse(any(e[0] == 'template' for e in events))
            self.assertFalse(any(e[:2] == ('set', 'attrib_maxguildmembers') for e in events))

    def test_other_buildings_and_legacy_instances_get_no_guessed_override(self):
        for title, has_property in (('Wizards_Guild', True), ('Bards_Hall', False)):
            vm, guild, events = self.runtime(title=title, with_property=has_property)
            self.begin_upgrade(vm, guild)
            self.assertEqual(events, [('dispatch', 'basic_upgrade', 1, 6)])
        vm, guild, events = self.runtime(title='Wizards_Guild')
        self.begin_upgrade(vm, guild)
        events.clear()
        vm.call('BuildingReachedMaxHP', guild)
        self.assertFalse(any(e[:2] == ('set', 'attrib_maxguildmembers') for e in events))


if __name__ == '__main__':
    unittest.main()
