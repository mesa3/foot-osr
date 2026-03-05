import unittest
from unittest.mock import MagicMock, patch, ANY
import sys
import os
import threading
import asyncio
import math

# Use absolute paths to ensure the module under test is importable
# regardless of where the test is run from.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Mocking modules that might be missing in the environment
def setup_mocks():
    mock_serial = MagicMock()
    mock_serial_tools = MagicMock()
    sys.modules['serial'] = mock_serial
    sys.modules['serial.tools'] = mock_serial_tools
    sys.modules['serial.tools.list_ports'] = MagicMock()
    sys.modules['websockets'] = MagicMock()

setup_mocks()

import dual_osr_control

class TestTCodeWSServer(unittest.TestCase):
    def setUp(self):
        self.port = 8766
        self.server = dual_osr_control.TCodeWSServer(self.port)

    def test_init(self):
        self.assertEqual(self.server.port, self.port)
        self.assertEqual(self.server.clients, set())
        self.assertFalse(self.server.running)

    @patch('dual_osr_control.threading.Thread')
    def test_start(self, mock_thread):
        self.server.start()
        self.assertTrue(self.server.running)
        mock_thread.assert_called_once()
        self.assertTrue(mock_thread.call_args[1]['daemon'])

    def test_stop(self):
        self.server.running = True
        self.server.loop = MagicMock()
        self.server.server = MagicMock()

        self.server.stop()

        self.assertFalse(self.server.running)
        self.server.loop.call_soon_threadsafe.assert_called()

    @patch('dual_osr_control.asyncio.run_coroutine_threadsafe')
    def test_broadcast(self, mock_run_coroutine):
        self.server.running = True
        self.server.loop = MagicMock()
        self.server.clients = {MagicMock()}

        self.server.broadcast("test message")

        mock_run_coroutine.assert_called_once()

class TestDualOSRController(unittest.TestCase):
    def setUp(self):
        self.controller = dual_osr_control.DualOSRController()

    def test_init(self):
        self.assertIsNone(self.controller.ws_server_a)
        self.assertIsNone(self.controller.ws_server_b)
        self.assertIsNone(self.controller.ser_a)
        self.assertIsNone(self.controller.ser_b)
        self.assertFalse(self.controller.running)
        self.assertEqual(self.controller.speed, 1.0)
        self.assertEqual(self.controller.stroke, 50.0)
        self.assertEqual(self.controller.offset, 50.0)
        self.assertEqual(self.controller.phase_shift, 180)
        self.assertFalse(self.controller.connected_a)
        self.assertFalse(self.controller.connected_b)

    @patch('dual_osr_control.serial.Serial')
    def test_connect_device_a(self, mock_serial_class):
        mock_ser = MagicMock()
        mock_serial_class.return_value = mock_ser

        result = self.controller.connect_device_a("COM1")

        self.assertTrue(result)
        self.assertTrue(self.controller.connected_a)
        mock_serial_class.assert_called_with("COM1", 921600, timeout=0.1)

    @patch('dual_osr_control.serial.Serial')
    def test_connect_device_a_failure(self, mock_serial_class):
        mock_serial_class.side_effect = Exception("Connection error")

        result = self.controller.connect_device_a("COM1")

        self.assertFalse(result)
        self.assertFalse(self.controller.connected_a)

    @patch('dual_osr_control.serial.Serial')
    def test_connect_device_b(self, mock_serial_class):
        mock_ser = MagicMock()
        mock_serial_class.return_value = mock_ser

        result = self.controller.connect_device_b("COM2")

        self.assertTrue(result)
        self.assertTrue(self.controller.connected_b)
        mock_serial_class.assert_called_with("COM2", 921600, timeout=0.1)

    def test_send_cmd(self):
        mock_ser = MagicMock()
        mock_ser.is_open = True
        mock_ws = MagicMock()

        self.controller._send_cmd(mock_ser, "L05000", mock_ws)

        mock_ws.broadcast.assert_called_with("L05000\n")
        mock_ser.write.assert_called_with(b"L05000\n")

    def test_disconnect_all(self):
        self.controller.ser_a = MagicMock()
        self.controller.ser_a.is_open = True
        self.controller.ser_b = MagicMock()
        self.controller.ser_b.is_open = True
        self.controller.connected_a = True
        self.controller.connected_b = True
        self.controller.running = True

        self.controller.disconnect_all()

        self.assertFalse(self.controller.running)
        self.controller.ser_a.close.assert_called()
        self.controller.ser_b.close.assert_called()
        self.assertFalse(self.controller.connected_a)
        self.assertFalse(self.controller.connected_b)

class TestDualOSRGui(unittest.TestCase):
    @patch('dual_osr_control.tk.Tk')
    def test_gui_init(self, mock_tk):
        root = MagicMock()
        # Mocking methods by directly setting them on the class BEFORE patching
        # This is a bit unusual but let's try.
        with patch('dual_osr_control.DualOSRGui.create_widgets') as mock_create_widgets, \
             patch('dual_osr_control.serial.tools.list_ports.comports', return_value=[]):

            gui = dual_osr_control.DualOSRGui(root)

            self.assertIsInstance(gui.controller, dual_osr_control.DualOSRController)
            self.assertTrue(mock_create_widgets.called)

    @patch('dual_osr_control.tk.Tk')
    def test_update_params(self, mock_tk):
        root = MagicMock()
        with patch.object(dual_osr_control.DualOSRGui, 'create_widgets'), \
             patch.object(dual_osr_control.DualOSRGui, 'refresh_ports'):
            gui = dual_osr_control.DualOSRGui(root)

            gui.speed_var = MagicMock()
            gui.speed_var.get.return_value = 2.0
            gui.stroke_var = MagicMock()
            gui.stroke_var.get.return_value = 75.0
            gui.offset_var = MagicMock()
            gui.offset_var.get.return_value = 25.0
            gui.mode_var = MagicMock()
            gui.mode_var.get.return_value = "sync"
            gui.pitch_amp_var = MagicMock()
            gui.pitch_amp_var.get.return_value = 50.0
            gui.roll_amp_var = MagicMock()
            gui.roll_amp_var.get.return_value = 50.0
            gui.twist_amp_var = MagicMock()
            gui.twist_amp_var.get.return_value = 50.0
            gui.base_squeeze_var = MagicMock()
            gui.base_squeeze_var.get.return_value = 50.0
            gui.ankle_offset_var = MagicMock()
            gui.ankle_offset_var.get.return_value = 50.0
            gui.roll_offset_var = MagicMock()
            gui.roll_offset_var.get.return_value = 50.0
            gui.reverse_l2_var = MagicMock()
            gui.reverse_l2_var.get.return_value = True

            gui.update_params()

            self.assertEqual(gui.controller.speed, 2.0)
            self.assertEqual(gui.controller.stroke, 75.0)
            self.assertEqual(gui.controller.base_squeeze, 50.0)
            self.assertEqual(gui.controller.ankle_angle_offset, 50.0)
            self.assertEqual(gui.controller.roll_angle_offset, 50.0)
            self.assertEqual(gui.controller.pitch_amp, 50.0)
            self.assertEqual(gui.controller.roll_amp, 50.0)
            self.assertEqual(gui.controller.twist_amp, 50.0)
            self.assertEqual(gui.controller.phase_shift, 180)
            self.assertEqual(gui.controller.reverse_l2, True)

if __name__ == '__main__':
    unittest.main()
