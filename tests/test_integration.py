import unittest
import sys
import os
import time
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def setup_mocks():
    mock_serial = MagicMock()
    mock_serial_tools = MagicMock()
    sys.modules['serial'] = mock_serial
    sys.modules['serial.tools'] = mock_serial_tools
    sys.modules['serial.tools.list_ports'] = MagicMock()
    sys.modules['websockets'] = MagicMock()
    sys.modules['tkinter'] = MagicMock()

setup_mocks()

import dual_osr_control

class TestSystemIntegration(unittest.TestCase):
    @patch('dual_osr_control.serial.Serial')
    def test_full_system_flow(self, mock_serial_class):
        # 1. Setup mock serial ports
        mock_ser_a = MagicMock()
        mock_ser_b = MagicMock()

        # We need to simulate the class returning our mocks
        def side_effect(port, baudrate, timeout):
            if port == "COM1": return mock_ser_a
            if port == "COM2": return mock_ser_b
            return MagicMock()

        mock_serial_class.side_effect = side_effect
        mock_ser_a.is_open = True
        mock_ser_b.is_open = True

        # 2. Initialize GUI (this will init the Controller too)
        root = MagicMock()
        with patch('dual_osr_control.DualOSRGui.create_widgets'), \
             patch('dual_osr_control.serial.tools.list_ports.comports', return_value=[]):
            gui = dual_osr_control.DualOSRGui(root)

        # 3. Connect Devices
        gui.controller.connect_device_a("COM1")
        gui.controller.connect_device_b("COM2")

        self.assertTrue(gui.controller.connected_a)
        self.assertTrue(gui.controller.connected_b)

        # 4. Configure Parameters
        gui.controller.speed = 10.0 # Fast speed to test updates
        gui.controller.motion_mode = "v_stroke"
        gui.controller.stroke = 50.0
        gui.controller.base_squeeze = 50.0
        gui.controller.tilt_compensation = 10.0

        # Prevent threading for test stability by calling the loop body once manually
        # Normally `toggle_motion` starts a thread. We will simulate what the thread does.
        gui.controller.running = True

        # Simulate the first frame calculation
        gui.controller.current_phase = 0.0
        cmd_a_base, cmd_b_base = gui.controller.calculate_frame()
        cmd_a = cmd_a_base + " I20"
        cmd_b = cmd_b_base + " I20"

        # Verify the command strings are well-formed
        self.assertIn("L04999", cmd_a)
        self.assertIn("L25500", cmd_a) # 5000 + 10% * 5000
        self.assertIn("I20", cmd_a)

        # Send commands
        gui.controller._send_cmd(gui.controller.ser_a, cmd_a)
        gui.controller._send_cmd(gui.controller.ser_b, cmd_b)

        # 5. Verify Mock Serial got correct bytes
        mock_ser_a.write.assert_called_with((cmd_a + "\r\n").encode())
        mock_ser_b.write.assert_called_with((cmd_b + "\r\n").encode())

        # 6. Stop System
        gui.controller.stop_motion()
        self.assertFalse(gui.controller.running)

if __name__ == '__main__':
    unittest.main()
