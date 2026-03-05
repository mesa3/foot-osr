import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

content = content.replace("            self.clients.remove(websocket)    def _start_server(self):", "            self.clients.remove(websocket)\n\n    def _start_server(self):")

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
