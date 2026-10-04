"""Stock widget ownership and layout checks for the proposed two-panel resource."""
import struct
import tempfile
import unittest
from pathlib import Path

from test_panel import GAME
from bards_panel import control_index, field, records
from bards_recruitment_panel import CHILD_DIALOG, OPEN_RECRUIT, ROWS, build_candidate
from bards_chronicles_panel import ACTION, PROGRESS, ACTIVE, PRICE, ICON, manager_feature
from build_bards_hall import build_text
from cam_io import get, read


class RecruitmentSubpanelTests(unittest.TestCase):
    def test_hiring_pair_retains_manager_stock_selector_contract(self):
        from test_hiring import MANAGER
        from majesty_cam.compose import _validate_mx22_toggle_controls
        from majesty_cam.stock_controller_registry import ResolvedBuildingOpenToggleRecord
        toggle = ResolvedBuildingOpenToggleRecord('hiring', int.from_bytes(b'CGBD','little'),
                    0x7340, 0x7341, 'AP52', 'BardsHiringClosed', 'Bards_Hiring_Closed',
                    int.from_bytes(b'BDRC','little'))
        _validate_mx22_toggle_controls(b''.join(self.child), toggle, owner='bards', panel_label='BDRC')
        for command in (0x7340,0x7341):
            self.assertEqual(self.rect(self.child,command),(7,194,139,21))

    @classmethod
    def setUpClass(cls):
        cls.stock = records(get(read(GAME / 'Data/textdata.cam'), b'SMNU', b'AP52'))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'candidate.cam'
            build_text(GAME, path)
            candidate = read(path)
            review_path = Path(temp) / 'review.cam'
            build_candidate(GAME, review_path)
            review = read(review_path)
            for panel in (b'CGBD', CHILD_DIALOG):
                for kind in (b'SMNU', b'STRT'):
                    assert get(candidate, kind, panel) == get(review, kind, panel)
        cls.main = records(get(candidate, b'SMNU', b'CGBD'))
        cls.child = records(get(candidate, b'SMNU', CHILD_DIALOG))

    def record(self, panel, control):
        return panel[control_index(panel, control)]

    def rect(self, panel, control):
        return struct.unpack_from('<4I', self.record(panel, control), 8)

    def test_main_utility_controls_are_literal_stock_not_moved(self):
        for control in (1, 0x1F5D, 0x1F42, 0x1F58, 0x1F59, 0x1F5A, 0x1F5B,
                        0x1F40, 0x1F41, 0x1F46, 0x1F4A, 0x1F4E):
            self.assertEqual(self.record(self.main, control).replace(b'BDTI', b'INTI'),
                             self.record(self.stock, control))

    def test_main_has_no_visible_recruit_commands_or_detached_prices(self):
        for command, price, *_ in ROWS:
            self.assertEqual(self.rect(self.main, command)[:2], (1500, 1500))
            self.assertEqual(self.rect(self.main, price)[:2], (1500, 1500))
        self.assertEqual(self.rect(self.main, OPEN_RECRUIT), (103, 196, 93, 26))
        self.assertEqual(self.rect(self.main, 0x1F44), (7, 196, 93, 26))

    def test_main_counts_do_not_overlap_portrait_utilities_or_actions(self):
        ids = (0x1F4B, 0x1F5D, 0x1F42, 0x1F58, 0x1F59, 0x1F5A, 0x1F5B,
               0x1F19, 0x1F1A, 0x1F52, 0x1F1B, 0x1F1C, 0x1F0D,
               OPEN_RECRUIT, 0x1F44, 0x1F47, 0x1F4F, 0x1E28, ACTION)
        for i, control in enumerate(ids):
            x, y, w, h = self.rect(self.main, control)
            self.assertLessEqual(x + w, 202)
            self.assertLessEqual(y + h, 245)
            for other in ids[i + 1:]:
                if {control, other} == {0x1F47, 0x1F4F}:
                    continue  # literal stock upgrade quote meets button by 1px
                xx, yy, ww, hh = self.rect(self.main, other)
                self.assertFalse(x < xx + ww and xx < x + w and y < yy + hh and yy < y + h,
                                 f'Overlap between {control:#x} and {other:#x}')

    def test_full_recruit_widgets_keep_stock_text_font_art_flags_and_inside_prices(self):
        template = self.record(self.stock, 0x1389)
        small_font = struct.unpack('<I', b'fnt7')[0]
        self.assertIn(struct.pack('<II', 0x12, small_font), self.record(self.stock, 0x1388))
        template = field(template, 0x12, struct.unpack('<I', b'fnt4')[0], small_font)
        for command, price, _, _, _, y in ROWS:
            actual = self.record(self.child, command)
            # Compare by audited DWORD fields to avoid accepting any font,
            # rendering, caption rectangle or image edits beyond the audited
            # stock AP52 compact-recruitment font above.
            a = struct.unpack('<' + 'I' * (len(actual) // 4), actual)
            b = struct.unpack('<' + 'I' * (len(template) // 4), template)
            permitted_words = {2, 3, 12, 14, 34, 36, 45, 47}
            self.assertEqual(len(a), len(b))
            self.assertTrue(all(i in permitted_words or av == bv for i, (av, bv) in enumerate(zip(a, b))))
            self.assertEqual(self.rect(self.child, command), (7, y, 189, 27))
            px, py, pw, ph = self.rect(self.child, price)
            self.assertGreaterEqual(px, 7)
            self.assertGreaterEqual(py, y)
            self.assertLessEqual(px + pw, 196)
            self.assertLessEqual(py + ph, y + 27)

    def test_child_has_back_shared_queue_and_no_visible_building_controls(self):
        self.assertEqual(self.rect(self.child, 0x1F4D), (3, 223, 25, 20))
        self.assertEqual(self.rect(self.child, 0x1F56), (7, 160, 189, 27))
        self.assertEqual(self.rect(self.child, 0x1F57), (10, 164, 182, 20))
        for control in (0x1F4B, 0x1F5D, 0x1F42, 0x1F58, 0x1F59, 0x1F47):
            self.assertEqual(self.rect(self.child, control)[:2], (1500, 1500))

    def test_chronicles_controls_remain_primary_and_quote_is_inside_action(self):
        for control in (ACTION, PROGRESS, ACTIVE, PRICE, ICON):
            self.record(self.main, control)
            with self.assertRaises(ValueError):
                self.record(self.child, control)
        self.assertEqual(self.rect(self.main, ACTION), (7, 223, 139, 21))
        self.assertEqual(self.rect(self.main, PROGRESS), (7, 223, 140, 21))
        self.assertEqual(self.rect(self.main, ICON)[:2], (1500, 1500))
        x, y, w, h = self.rect(self.main, ACTION)
        px, py, pw, ph = self.rect(self.main, PRICE)
        self.assertTrue(x <= px and y <= py and px + pw <= x + w and py + ph <= y + h)

    def test_chronicles_declares_approved_rules_and_stable_saved_identity(self):
        self.assertEqual(manager_feature(), {
            'type': 'manager.kingdom-research.v1', 'feature_key': 'epic-chronicles',
            'parent_building': 'Bards_Hall', 'action_control_id': 0x7320,
            'descriptor_template_control_id': 0x139C, 'required_level': 3, 'price': 3000,
            'gold_bonus_percent': 15, 'experience_bonus_percent': 15,
            'progress_control_id': 0x7321, 'active_display_control_id': 0x7322,
            'completion_text': 'Epic Chronicles',
            'active_effector': 'Bards_Chronicles_Active',
        })


if __name__ == '__main__':
    unittest.main()
