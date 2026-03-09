import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

# 1. Properties
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

# 2. go_to_neutral
new_method = """    def disconnect_all(self):
        if self.ser_a and self.ser_a.is_open:
            self.ser_a.close()
        if self.ser_b and self.ser_b.is_open:
            self.ser_b.close()
        self.connected_a = False
        self.connected_b = False
        logger.info("Disconnected all devices")

    def go_to_neutral(self):
        self.is_initializing = True

        # Calculate neutral positions applying the offsets
        l0_a = max(0, min(9999, 5000 + self.height_offset_a))
        l0_b = max(0, min(9999, 5000 + self.height_offset_b))

        cmd_a = f"L0{l0_a:04d} I1000"
        cmd_b = f"L0{l0_b:04d} I1000"

        self._send_cmd(self.ser_a, cmd_a, self.ws_server_a)
        self._send_cmd(self.ser_b, cmd_b, self.ws_server_b)
        logger.info(f"Initialized to Neutral - A: {l0_a}, B: {l0_b}")
"""
content = re.sub(r'(\s+)def disconnect_all\(self\):.*?logger\.info\("Disconnected all devices"\)', new_method, content, flags=re.DOTALL)

# 3. calculate_frame offset clamp
pattern = r"""            def clamp\(val\):
                return max\(0, min\(9999, int\(val\)\)\)

            cmd_a_parts = \[\]
            cmd_b_parts = \[\]"""
replacement = """            def clamp(val):
                return max(0, min(9999, int(val)))

            # Apply height offset
            center_a_l0 = center_l0 + self.height_offset_a
            center_b_l0 = center_l0 + self.height_offset_b

            cmd_a_parts = []
            cmd_b_parts = []"""
content = re.sub(pattern, replacement, content)

# 4. replacer for L0
def replacer(match):
    old_code = match.group(0)
    lines = old_code.split('\n')
    new_lines = []
    for line in lines:
        if "cmd_a_parts.extend" in line:
            line = re.sub(r'L0\{clamp\(([^)]+)\):04d\}', r'L0{clamp(\1 + getattr(self, "height_offset_a", 0)):04d}', line)
        elif "cmd_b_parts.extend" in line:
            line = re.sub(r'L0\{clamp\(([^)]+)\):04d\}', r'L0{clamp(\1 + getattr(self, "height_offset_b", 0)):04d}', line)
        elif "cmd_a_parts.append" in line:
            line = re.sub(r'L0\{clamp\(([^)]+)\):04d\}', r'L0{clamp(\1 + getattr(self, "height_offset_a", 0)):04d}', line)
        elif "cmd_b_parts.append" in line:
            line = re.sub(r'L0\{clamp\(([^)]+)\):04d\}', r'L0{clamp(\1 + getattr(self, "height_offset_b", 0)):04d}', line)
        new_lines.append(line)
    return '\n'.join(new_lines)

start_idx = content.find('def calculate_frame(self):')
end_idx = content.find('return " ".join(cmd_a_parts), " ".join(cmd_b_parts)') + len('return " ".join(cmd_a_parts), " ".join(cmd_b_parts)')
calculate_frame_str = content[start_idx:end_idx]
new_calculate_frame_str = replacer(re.match(r'.*', calculate_frame_str, re.DOTALL))
content = content[:start_idx] + new_calculate_frame_str + content[end_idx:]

# 5. stop_motion centered
stop_addition = """        # Center devices on stop with offset
        l0_a = max(0, min(9999, 5000 + getattr(self, 'height_offset_a', 0)))
        l0_b = max(0, min(9999, 5000 + getattr(self, 'height_offset_b', 0)))
        self._send_cmd(self.ser_a, f"L0{l0_a:04d} I1000", self.ws_server_a)
        self._send_cmd(self.ser_b, f"L0{l0_b:04d} I1000", self.ws_server_b)
        logger.info("Motion stopped signal sent (waiting for thread to finish in background)")"""
content = re.sub(r'(\s+)# Center devices on stop.*?logger\.info\("Motion stopped signal sent \(waiting for thread to finish in background\)"\)', stop_addition, content, flags=re.DOTALL)

# 6. start_motion clear flag
start_addition = """    def start_motion(self):
        if not self.running:
            self.is_initializing = False  # Clear init flag on actual motion start
            self.running = True
            self.thread = threading.Thread(target=self.motion_loop, daemon=True)
            self.thread.start()
            logger.info("Motion started")"""
content = re.sub(r'(\s+)def start_motion\(self\):.*?logger\.info\("Motion started"\)', start_addition, content, flags=re.DOTALL)

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
