"""Continuity checks for the motion defect: direction, stride and loop seam."""
import math
import unittest
from test_hiring import ROOT
from bards_chronicles_motion import CENTER, RADIUS, FRAME_COUNT, NOTE_COUNT, note_positions, frames


class ChroniclesMotionTests(unittest.TestCase):
    def test_every_step_including_wrap_advances_three_degrees(self):
        for frame in range(FRAME_COUNT):
            current = note_positions(frame)
            following = note_positions(frame+1)
            for i, point in enumerate(current):
                # Four identical notes exchange slots at the quarter-turn seam.
                next_point = following[(i+1) % NOTE_COUNT] if frame == FRAME_COUNT-1 else following[i]
                def angle(p):
                    return math.atan2((p[1]-CENTER[1])/RADIUS[1], (p[0]-CENTER[0])/RADIUS[0])
                advance = (angle(next_point)-angle(point)) % math.tau
                self.assertAlmostEqual(math.degrees(advance), 3, places=10)
                self.assertLess(math.dist(point, next_point), 1.5)

    def test_loop_pose_is_exact_and_native_source_frames_are_all_distinct(self):
        self.assertEqual(note_positions(0), note_positions(30))
        pictures = frames()
        self.assertEqual(len(pictures), 30)
        self.assertEqual(len({p.tobytes() for p in pictures}), 30)
        for picture in pictures:
            self.assertEqual(picture.size, (80, 80))
            self.assertEqual(picture.mode, 'RGBA')
            self.assertEqual(picture.getpixel((0, 0))[3], 0)


if __name__ == '__main__': unittest.main()
