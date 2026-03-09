import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

# Make sure we have the properties in the init
new_props = """
        # Device status
        self.connected_a = False
        self.connected_b = False
        self.current_phase = 0.0

        # Height Offset Parameters (L0 offset)
        self.height_offset_a = 0  # T-Code raw value offset (-9999 to 9999)
        self.height_offset_b = 0
        self.is_initializing = False
"""
content = re.sub(r'(\s+)# Device status\s+self\.connected_a = False\s+self\.connected_b = False\s+self\.current_phase = 0\.0', new_props, content)

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
