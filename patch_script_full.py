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
            line = re.sub(r'L0\{clamp\(([^)]+)\):04d\}', r'L0{clamp(\1 + self.height_offset_a):04d}', line)
        elif "cmd_b_parts.extend" in line:
            line = re.sub(r'L0\{clamp\(([^)]+)\):04d\}', r'L0{clamp(\1 + self.height_offset_b):04d}', line)
        elif "cmd_a_parts.append" in line:
            line = re.sub(r'L0\{clamp\(([^)]+)\):04d\}', r'L0{clamp(\1 + self.height_offset_a):04d}', line)
        elif "cmd_b_parts.append" in line:
            line = re.sub(r'L0\{clamp\(([^)]+)\):04d\}', r'L0{clamp(\1 + self.height_offset_b):04d}', line)
        new_lines.append(line)
    return '\n'.join(new_lines)

start_idx = content.find('def calculate_frame(self):')
end_idx = content.find('return " ".join(cmd_a_parts), " ".join(cmd_b_parts)') + len('return " ".join(cmd_a_parts), " ".join(cmd_b_parts)')
calculate_frame_str = content[start_idx:end_idx]
new_calculate_frame_str = replacer(re.match(r'.*', calculate_frame_str, re.DOTALL))
content = content[:start_idx] + new_calculate_frame_str + content[end_idx:]

# 5. stop_motion centered
stop_addition = """        # Center devices on stop with offset
        l0_a = max(0, min(9999, 5000 + self.height_offset_a))
        l0_b = max(0, min(9999, 5000 + self.height_offset_b))
        self._send_cmd(self.ser_a, f"L0{l0_a:04d} I1000", self.ws_server_a)
        self._send_cmd(self.ser_b, f"L0{l0_b:04d} I1000", self.ws_server_b)
        logger.info("Motion stopped and devices centered (with offset)")"""
content = re.sub(r'(\s+)# Center devices on stop.*?logger\.info\("Motion stopped and devices centered"\)', stop_addition, content, flags=re.DOTALL)

# 6. start_motion clear flag
start_addition = """    def start_motion(self):
        if not self.running:
            self.is_initializing = False  # Clear init flag on actual motion start
            self.running = True
            self.thread = threading.Thread(target=self.motion_loop, daemon=True)
            self.thread.start()
            logger.info("Motion started")"""
content = re.sub(r'(\s+)def start_motion\(self\):.*?logger\.info\("Motion started"\)', start_addition, content, flags=re.DOTALL)

# 7. GUI Section
gui_addition = """
        # --- Calibration Section ---
        calib_frame = ttk.LabelFrame(self.root, text="Calibration & Initialization")
        calib_frame.pack(fill="x", padx=10, pady=5)

        self.btn_init = ttk.Button(calib_frame, text="INITIALIZE (Go to Neutral)", command=self.go_to_neutral)
        self.btn_init.pack(fill="x", padx=5, pady=5)

        ttk.Label(calib_frame, text="Height Offset A (L0):").pack(anchor="w", padx=5)
        self.height_offset_a_var = tk.DoubleVar(value=0.0)
        self.height_offset_a_scale = ttk.Scale(calib_frame, from_=-500, to=500, variable=self.height_offset_a_var, command=self.update_params)
        self.height_offset_a_scale.pack(fill="x", padx=5, pady=2)

        ttk.Label(calib_frame, text="Height Offset B (L0):").pack(anchor="w", padx=5)
        self.height_offset_b_var = tk.DoubleVar(value=0.0)
        self.height_offset_b_scale = ttk.Scale(calib_frame, from_=-500, to=500, variable=self.height_offset_b_var, command=self.update_params)
        self.height_offset_b_scale.pack(fill="x", padx=5, pady=2)

        # Start/Stop"""
content = re.sub(r'\s*# Start/Stop', gui_addition, content)

# 8. GUI Methods
gui_method_addition = """    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.combo_a['values'] = ports
        self.combo_b['values'] = ports
        if ports:
            if not self.port_a.get(): self.combo_a.current(0)
            if not self.port_b.get(): self.combo_b.current(0)

    def go_to_neutral(self):
        if self.controller.running:
            logger.warning("Stop motion before initializing")
            return
        self.controller.go_to_neutral()"""
content = re.sub(r'(\s+)def refresh_ports\(self\):.*?if not self\.port_b\.get\(\): self\.combo_b\.current\(0\)', gui_method_addition, content, flags=re.DOTALL)

# 9. GUI update_params
update_addition = """    def update_params(self, _=None):
        self.controller.speed = self.speed_var.get()
        self.controller.stroke = self.stroke_var.get()
        self.controller.base_squeeze = self.base_squeeze_var.get()
        self.controller.ankle_angle_offset = self.ankle_offset_var.get()
        self.controller.roll_angle_offset = self.roll_offset_var.get()
        self.controller.pitch_amp = self.pitch_amp_var.get()
        self.controller.roll_amp = self.roll_amp_var.get()
        self.controller.twist_amp = self.twist_amp_var.get()
        self.controller.reverse_l2 = self.reverse_l2_var.get()
        self.controller.tilt_compensation = self.tilt_comp_var.get()

        # Height Offsets
        self.controller.height_offset_a = int(self.height_offset_a_var.get())
        self.controller.height_offset_b = int(self.height_offset_b_var.get())

        # Update devices immediately if in initialization mode
        if getattr(self.controller, 'is_initializing', False) and not self.controller.running:
            self.controller.go_to_neutral()"""
content = re.sub(r'(\s+)def update_params\(self, _=None\):.*?self\.controller\.tilt_compensation = self\.tilt_comp_var\.get\(\)', update_addition, content, flags=re.DOTALL)

with open('dual_osr_control.py', 'w') as f:
    f.write(content)


with open('tests/test_dual_osr_control.py', 'r') as f:
    test_content = f.read()

# Test mock
test_addition = """        gui.reverse_l2_var.get.return_value = True
        gui.tilt_comp_var = MagicMock()
        gui.tilt_comp_var.get.return_value = 10.0

        gui.height_offset_a_var = MagicMock()
        gui.height_offset_a_var.get.return_value = 100.0
        gui.height_offset_b_var = MagicMock()
        gui.height_offset_b_var.get.return_value = -100.0"""
test_content = re.sub(r'(\s+)gui\.reverse_l2_var\.get\.return_value = True\s+gui\.tilt_comp_var = MagicMock\(\)\s+gui\.tilt_comp_var\.get\.return_value = 10\.0', test_addition, test_content)

# Test assertion
assertion_addition = """        self.assertEqual(gui.controller.tilt_compensation, 10.0)
        self.assertEqual(gui.controller.height_offset_a, 100)
        self.assertEqual(gui.controller.height_offset_b, -100)"""
test_content = re.sub(r'(\s+)self\.assertEqual\(gui\.controller\.tilt_compensation, 10\.0\)', assertion_addition, test_content)

with open('tests/test_dual_osr_control.py', 'w') as f:
    f.write(test_content)
