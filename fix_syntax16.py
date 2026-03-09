import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

content = content.replace("pos_a + self.height_offset_a + getattr(self, \"height_offset_a\", 0)", "pos_a + getattr(self, 'height_offset_a', 0)")
content = content.replace("pos_b + self.height_offset_b + getattr(self, \"height_offset_b\", 0)", "pos_b + getattr(self, 'height_offset_b', 0)")

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
