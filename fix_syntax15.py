import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

# Replace the messy getattr(...) and double self.height_offset_a stuff
content = content.replace("pos_l0 + self.height_offset_a + getattr(self, \"height_offset_a\", 0)", "pos_l0 + getattr(self, 'height_offset_a', 0)")
content = content.replace("pos_l0 + self.height_offset_b + getattr(self, \"height_offset_b\", 0)", "pos_l0 + getattr(self, 'height_offset_b', 0)")
content = content.replace("pos_a_l0 + self.height_offset_a + getattr(self, \"height_offset_a\", 0)", "pos_a_l0 + getattr(self, 'height_offset_a', 0)")
content = content.replace("pos_b_l0 + self.height_offset_b + getattr(self, \"height_offset_b\", 0)", "pos_b_l0 + getattr(self, 'height_offset_b', 0)")
content = content.replace("center_l0 + self.height_offset_a + getattr(self, \"height_offset_a\", 0)", "center_l0 + getattr(self, 'height_offset_a', 0)")
content = content.replace("center_l0 + self.height_offset_b + getattr(self, \"height_offset_b\", 0)", "center_l0 + getattr(self, 'height_offset_b', 0)")


with open('dual_osr_control.py', 'w') as f:
    f.write(content)
