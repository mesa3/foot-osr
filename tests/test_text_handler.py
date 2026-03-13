import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import logging

# Use absolute paths to ensure the module under test is importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Mocking modules that might be missing in the environment or cause issues
def setup_mocks():
    sys.modules['serial'] = MagicMock()
    sys.modules['serial.tools'] = MagicMock()
    sys.modules['serial.tools.list_ports'] = MagicMock()
    sys.modules['websockets'] = MagicMock()
    sys.modules['tkinter'] = MagicMock()
    sys.modules['tkinter.ttk'] = MagicMock()
    sys.modules['tkinter.scrolledtext'] = MagicMock()

setup_mocks()

import dual_osr_control
import tkinter as tk

class TestTextHandler(unittest.TestCase):
    def setUp(self):
        self.mock_text_widget = MagicMock()
        self.handler = dual_osr_control.TextHandler(self.mock_text_widget)
        self.handler.setFormatter(logging.Formatter('%(message)s'))

    def test_init(self):
        self.assertEqual(self.handler.text_widget, self.mock_text_widget)

    def test_emit(self):
        with patch('dual_osr_control.tk.END', 'end'):
            # Create a log record
            record = logging.LogRecord(
                name='test_logger',
                level=logging.INFO,
                pathname='test_path',
                lineno=10,
                msg='test message',
                args=None,
                exc_info=None
            )

            # Call emit
            self.handler.emit(record)

            # Verify that after was called with 0 and a callable
            self.mock_text_widget.after.assert_called_once_with(0, unittest.mock.ANY)

            # Extract the callback (the 'append' function)
            callback = self.mock_text_widget.after.call_args[0][1]
            self.assertTrue(callable(callback))

            # Reset the mock to check calls within the callback
            self.mock_text_widget.reset_mock()

            # Call the callback
            callback()

            # Verify the sequence of calls on the text_widget
            # 1. configure(state='normal')
            # 2. insert('end', "test message\n")
            # 3. see('end')
            # 4. configure(state='disabled')

            expected_calls = [
                unittest.mock.call.configure(state='normal'),
                unittest.mock.call.insert('end', 'test message\n'),
                unittest.mock.call.see('end'),
                unittest.mock.call.configure(state='disabled')
            ]
            self.mock_text_widget.assert_has_calls(expected_calls)

if __name__ == '__main__':
    unittest.main()
