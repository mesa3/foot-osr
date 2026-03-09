import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

new_method = """    def disconnect_all(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.2)

        if self.ser_a and self.ser_a.is_open:
            self.ser_a.close()
        if self.ser_b and self.ser_b.is_open:
            self.ser_b.close()
        self.connected_a = False
        self.connected_b = False
        logger.info("All devices disconnected")

    def go_to_neutral(self):
        self.is_initializing = True

        # Calculate neutral positions applying the offsets
        l0_a = max(0, min(9999, 5000 + getattr(self, "height_offset_a", 0)))
        l0_b = max(0, min(9999, 5000 + getattr(self, "height_offset_b", 0)))

        cmd_a = f"L0{l0_a:04d} I1000"
        cmd_b = f"L0{l0_b:04d} I1000"

        self._send_cmd(self.ser_a, cmd_a, self.ws_server_a)
        self._send_cmd(self.ser_b, cmd_b, self.ws_server_b)
        logger.info(f"Initialized to Neutral - A: {l0_a}, B: {l0_b}")"""

content = re.sub(r'(\s+)def disconnect_all\(self\):.*?logger\.info\("All devices disconnected"\)', new_method, content, flags=re.DOTALL)

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
