"""Reject runtime factory names that the GPL compiler itself accepts."""
import unittest

from test_hiring import GPLSubset, ROOT, agent
from validate_bards_abilities import check_dynamic_attribute_types


class DynamicAttributeTests(unittest.TestCase):
    def test_authored_dynamic_fields_use_native_factory_names(self):
        for path in (ROOT / 'src/gpl').glob('*.gpl'):
            with self.subTest(path=path.name):
                check_dynamic_attribute_types(path.read_text(), path.name)

    def test_declaration_keywords_are_not_runtime_factory_names(self):
        for invalid, correct in (('agent', 'agentref'), ('coordinate', 'coord')):
            source = f'$AddAttribute(Hero, "Reference", "{invalid}");'
            with self.assertRaisesRegex(ValueError, 'unsupported AddAttribute type'):
                check_dynamic_attribute_types(source, 'regression')
            check_dynamic_attribute_types(source.replace(invalid, correct), 'native')

    def test_harness_rejects_invalid_type_and_keeps_agentref_identity(self):
        vm = GPLSubset('')
        hero, town = agent(), agent()
        with self.assertRaisesRegex(ValueError, 'Unsupported native AddAttribute type'):
            vm.add_attribute(hero, 'Town', 'agent', town)
        self.assertNotIn('Town', hero.fields)
        vm.add_attribute(hero, 'Town', 'agentref', town)
        self.assertIs(hero['Town'], town)


if __name__ == '__main__':
    unittest.main()
