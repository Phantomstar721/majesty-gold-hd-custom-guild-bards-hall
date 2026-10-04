"""Native resource contracts for the private three-choice panel, without UI."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from bards_panel import THIRD_PRICE_CONTROL, control_index, records
from build_bards_hall import build_text
from cam_io import get, read
from validate_bards_hall import strings

GAME = Path(r'C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock = read(GAME / 'Data/textdata.cam')
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'panel.cam'
            build_text(GAME, output)
            cls.private = read(output)
        cls.menu = records(get(cls.private, b'SMNU', b'CGBD'))

    def control(self, value):
        return self.menu[control_index(self.menu, value)]

    def rectangle(self, value):
        return struct.unpack_from('<4I', self.control(value), 8)

    def test_constructor_controls_survive_and_legacy_actions_are_offscreen(self):
        for control in (0x22CE, 0x1F49, 0x1181, 0x1F18, 0x1F0E,
                        0x1F11, 0x1F12, 0x1F13, 0x1F14):
            self.assertEqual(self.rectangle(control)[:2], (1500, 1500))
        for control in (0x1F56, 0x1F57, 0x1F47, 0x1F4F, 0x1E28,
                        0x1F44, 0x1F46, 0x1F4A, 0x1F4B):
            self.control(control)
        self.assertEqual(len(self.menu), len(records(get(self.stock, b'SMNU', b'AP52'))) + 15)

    def test_stock_frame_sockets_match_repair_positions(self):
        self.assertIn(struct.pack('<II', 13, 1000), self.control(1))
        for control, expected in ((0x1F5A, (2, 126, 22, 17)),
                                  (0x1F5B, (178, 126, 22, 17))):
            self.assertEqual(self.rectangle(control), expected)
        for control in (0x1F58, 0x1F59):
            x, y, w, h = self.rectangle(control)
            self.assertEqual((w, h), (22, 17))
            self.assertEqual(y, 144)

    def test_upgrade_labels_and_all_recruit_prices_have_private_text(self):
        labels = strings(get(self.private, b'STRT', b'CGBD'))
        for key, expected in ((0, b'Blade Dancer'), (4, b'Troubadour'),
                              (12, b'Spellsinger'), (7, b'500'), (32, b'500'),
                              (47, b'LVL'), (51, b'Upgrade the Bards Hall.')):
            self.assertEqual(labels[struct.pack('<I', key)], expected)

    def test_upgrade_widgets_keep_stock_behavior_and_geometry(self):
        wizard = records(get(self.stock, b'SMNU', b'AP53'))
        for control in (0x1F47, 0x1F4F, 0x1E28):
            original = wizard[control_index(wizard, control)]
            actual = self.control(control)
            self.assertEqual(len(actual), len(original))
            # The caption values follow property 7 at byte 24. Level and
            # upgrade button also have a tooltip value following tag 0x21.
            allowed = set(range(28, 32))
            if control != 0x1F4F:
                allowed.update(range(36, 40))
            differences = {i for i, (a, b) in enumerate(zip(actual, original)) if a != b}
            self.assertLessEqual(differences, allowed)

    def test_same_three_produces_and_shared_slots_survive_each_upgrade(self):
        import xml.etree.ElementTree as ET
        from build_bards_hall import build_units
        root = ET.fromstring(build_units(GAME / 'SDK/OriginalQuests'))
        for level in range(1, 4):
            guild = root.find(f'./Description[@Name="Bards_Hall{level}"]')
            self.assertEqual([row.get('ID') for row in guild.find('./Game/Produces')],
                             ['Troubadour', 'Spellsinger', 'Blade_Dancer'])
            self.assertEqual(guild.find('./Game/MaxGuildMembers').get('value'), str(2 + 2 * level))
            self.assertEqual(guild.find('./Game/DialogID').get('value'), 'CGBD')

    def test_palace_buildability_matches_stock_wizard_upgrade_chain(self):
        import xml.etree.ElementTree as ET
        from build_bards_hall import build_units
        sdk = GAME / 'SDK/OriginalQuests'
        private = ET.fromstring(build_units(sdk))
        stock = ET.parse(sdk / 'Data/M_Buildings.xml').getroot()
        for level in range(1, 4):
            bard = private.find(f'./Description[@Name="Bards_Hall{level}"]')
            wizard = stock.find(f'./Description[@Name="Wizards_Guild{level}"]')
            stock_flag = wizard.find('./Game/Flags[@value="NotBuildable"]')
            self.assertEqual(bard.find('./Game/Flags[@value="NotBuildable"]') is not None,
                             stock_flag is not None)
            for field in ('UpgradeTo', 'UpgradeFrom'):
                reference, actual = wizard.find('./Game/' + field), bard.find('./Game/' + field)
                if reference is None:
                    self.assertIsNone(actual)
                else:
                    self.assertEqual(actual.get('value'),
                                     reference.get('value').replace('Wizards_Guild', 'Bards_Hall'))


if __name__ == '__main__':
    unittest.main()
