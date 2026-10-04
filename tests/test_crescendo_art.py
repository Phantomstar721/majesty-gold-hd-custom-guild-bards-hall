"""Protect the overhead anchor and stock timed-overlay descriptor."""
import copy
import unittest
import xml.etree.ElementTree as ET
from test_hiring import SDK
from bards_crescendo_art import description, frames, SIZE, CENTER, HOTSPOT


class CrescendoArtTests(unittest.TestCase):
    def test_private_overlay_retains_stock_overhead_lifecycle(self):
        stock=ET.parse(SDK/'Data/M_Overlays.xml').getroot()
        original=stock.find('.//Description[@Name="blessing_icon"]')
        actual=description(stock)
        self.assertEqual(actual.find('./Engine/Script').get('GPLFunction'),'Paralytic_Gaze_End')
        self.assertEqual(actual.find('./Game/StackPriority').get('value'),'1')
        self.assertIsNone(actual.find('./Engine/AttachmentPointID'))
        actual.attrib=original.attrib.copy()
        for field in ('ImageIDBase','Script'):
            actual.find('./Engine/'+field).attrib=original.find('./Engine/'+field).attrib.copy()
        self.assertEqual(ET.tostring(actual),ET.tostring(original))

    def test_frames_keep_one_anchor_and_continuous_visibility(self):
        pictures=frames(10)
        self.assertEqual(HOTSPOT,(CENTER[0],CENTER[1]+4))
        self.assertEqual(len(pictures),10)
        for p in pictures:
            self.assertEqual(p.size,SIZE)
            self.assertGreater(sum(a>=80 for a in p.getchannel('A').getdata()),60)


if __name__=='__main__':unittest.main()
