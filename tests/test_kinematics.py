import unittest
import sys
import os
import math

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from unittest.mock import MagicMock
sys.modules['serial'] = MagicMock()
sys.modules['serial.tools'] = MagicMock()
sys.modules['serial.tools.list_ports'] = MagicMock()
sys.modules['websockets'] = MagicMock()
sys.modules['tkinter'] = MagicMock()

import dual_osr_control

class TestKinematics(unittest.TestCase):
    def setUp(self):
        self.controller = dual_osr_control.DualOSRController()
        # Set standard baseline parameters
        self.controller.speed = 1.0  # 1 Hz -> 2*pi phase per second
        self.controller.stroke = 50.0 # 50% amp -> 2500
        self.controller.base_squeeze = 50.0 # 50% center -> 4999
        self.controller.ankle_angle_offset = 50.0 # 50% center R2 -> 4999
        self.controller.roll_angle_offset = 50.0 # 50% center R1 -> 4999
        self.controller.pitch_amp = 0.0
        self.controller.roll_amp = 0.0
        self.controller.twist_amp = 0.0
        self.controller.tilt_compensation = 0.0
        self.controller.reverse_l2 = False
        self.controller.phase_shift = 0

    def parse_tcode(self, cmd):
        # Parses a string like "L05000 L25000 R24999" into a dictionary
        parts = cmd.split()
        res = {}
        for p in parts:
            axis = p[:2]
            val = int(p[2:])
            res[axis] = val
        return res

    def test_v_stroke_pure_center(self):
        self.controller.motion_mode = "v_stroke"
        self.controller.stroke = 0.0 # No motion

        cmd_a, cmd_b = self.controller.calculate_frame(0.0)

        a = self.parse_tcode(cmd_a)
        b = self.parse_tcode(cmd_b)

        # Center L0 is 4999 (50% of 9999)
        self.assertEqual(a['L0'], 4999)
        self.assertEqual(b['L0'], 4999)
        # Center L2 is 5000 (fixed nominal center)
        self.assertEqual(a['L2'], 5000)
        self.assertEqual(b['L2'], 5000)
        # Center R2 is 4999
        self.assertEqual(a['R2'], 4999)
        self.assertEqual(b['R2'], 4999)

    def test_v_stroke_motion(self):
        self.controller.motion_mode = "v_stroke"
        self.controller.stroke = 50.0 # Amp is 2500

        # At t=0.25, phase is 2*pi * 1 * 0.25 = pi/2. sin(pi/2) = 1
        # pos_l0 = center_l0 + amp_l0 = 4999 + 2500 = 7499
        cmd_a, cmd_b = self.controller.calculate_frame(0.25)

        a = self.parse_tcode(cmd_a)

        self.assertEqual(a['L0'], 7499)

        # L2 compensation: pos_l2 = center_l2 - (z_motion * l2_mult)
        # z_motion = 2500. pos_l2 = 5000 - 2500 = 2500
        self.assertEqual(a['L2'], 2500)

    def test_tilt_compensation(self):
        self.controller.motion_mode = "v_stroke"
        self.controller.stroke = 0.0 # No motion
        self.controller.tilt_compensation = 20.0 # 20% offset on L2 base -> 5000 + 1000 = 6000

        cmd_a, cmd_b = self.controller.calculate_frame(0.0)
        a = self.parse_tcode(cmd_a)

        self.assertEqual(a['L2'], 6000)

    def test_clamping(self):
        self.controller.motion_mode = "v_stroke"
        self.controller.base_squeeze = 100.0 # Center L0 is 9999
        self.controller.stroke = 100.0 # Amp is 5000
        # Normal max would be 14999. Should clamp to 9999.

        cmd_a, cmd_b = self.controller.calculate_frame(0.25)
        a = self.parse_tcode(cmd_a)

        # We also need to test if the center clamp logic limits it.
        # Actually in code:
        # if center_l0 + amp_l0 > 9999: center_l0 = 9999 - amp_l0
        # center = 9999, amp = 5000 -> center becomes 4999.
        # So pos_l0 = 4999 + 5000 = 9999.
        self.assertEqual(a['L0'], 9999)


    def test_phase_shift(self):
        self.controller.motion_mode = "alternating_step"
        self.controller.speed = 1.0
        self.controller.stroke = 50.0 # amp = 2500
        self.controller.phase_shift = 180 # pi radians difference

        # t = 0.25 -> phase_a = pi/2, sin = 1
        # phase_b = pi/2 + pi = 3pi/2, sin = -1
        cmd_a, cmd_b = self.controller.calculate_frame(0.25)
        a = self.parse_tcode(cmd_a)
        b = self.parse_tcode(cmd_b)

        self.assertEqual(a['L0'], 4999 + 2500)
        self.assertEqual(b['L0'], 4999 - 2500)

if __name__ == '__main__':
    unittest.main()
