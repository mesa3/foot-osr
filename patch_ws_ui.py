import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

# Make sure we only replace the else block in `toggle_motion`
gui_stop_replacement = """        else:
            self.controller.stop_motion()
            try:
                if self.controller.ws_server_a:
                    self.controller.ws_server_a.stop()
                    self.controller.ws_server_a = None
                if self.controller.ws_server_b:
                    self.controller.ws_server_b.stop()
                    self.controller.ws_server_b = None
            except Exception as e:
                logger.error(f"Error stopping WebSockets: {e}")
            self.btn_start.config(text="START MOTION")"""

content = re.sub(r'(\s+)else:\s+self\.controller\.stop_motion\(\).*?self\.btn_start\.config\(text="START MOTION"\)', gui_stop_replacement, content, flags=re.DOTALL)

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
