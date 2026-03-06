import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

content = content.replace("        self.refresh_ports()    def refresh_ports(self):", "        self.refresh_ports()\n\n    def refresh_ports(self):")
content = content.replace("            logger.info(\"Device B disconnected\")    def update_params(self, _=None):", "            logger.info(\"Device B disconnected\")\n\n    def update_params(self, _=None):")
content = content.replace("        logger.info(\"All devices disconnected\")    def start_motion(self):", "        logger.info(\"All devices disconnected\")\n\n    def start_motion(self):")

with open('dual_osr_control.py', 'w') as f:
    f.write(content)

with open('tests/test_dual_osr_control.py', 'r') as f:
    content = f.read()

content = content.replace("gui.reverse_l2_var = MagicMock()        gui.reverse_l2_var.get.return_value = True", "gui.reverse_l2_var = MagicMock()\n        gui.reverse_l2_var.get.return_value = True")
content = content.replace("self.assertEqual(gui.controller.reverse_l2, True)        self.assertEqual(gui.controller.tilt_compensation, 10.0)", "self.assertEqual(gui.controller.reverse_l2, True)\n        self.assertEqual(gui.controller.tilt_compensation, 10.0)")

# Fix indentations
content = content.replace("            gui.reverse_l2_var = MagicMock()\n        gui.reverse_l2_var.get.return_value = True", "            gui.reverse_l2_var = MagicMock()\n            gui.reverse_l2_var.get.return_value = True")
content = content.replace("        gui.tilt_comp_var = MagicMock()", "            gui.tilt_comp_var = MagicMock()")
content = content.replace("        gui.tilt_comp_var.get.return_value = 10.0", "            gui.tilt_comp_var.get.return_value = 10.0")
content = content.replace("        \n        gui.height_offset_a_var = MagicMock()", "            gui.height_offset_a_var = MagicMock()")
content = content.replace("        gui.height_offset_a_var.get.return_value = 100.0", "            gui.height_offset_a_var.get.return_value = 100.0")
content = content.replace("        gui.height_offset_b_var = MagicMock()", "            gui.height_offset_b_var = MagicMock()")
content = content.replace("        gui.height_offset_b_var.get.return_value = -100.0", "            gui.height_offset_b_var.get.return_value = -100.0")

with open('tests/test_dual_osr_control.py', 'w') as f:
    f.write(content)
