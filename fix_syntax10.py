import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

content = content.replace("            except Exception as e:                logger.error(f\"Error stopping WebSockets: {e}\")", "            except Exception as e:\n                logger.error(f\"Error stopping WebSockets: {e}\")")
content = content.replace("class TCodeWSServer:    def __init__(self, port=8766):", "class TCodeWSServer:\n    def __init__(self, port=8766):")
content = content.replace("            self.clients.remove(websocket)    def _start_server(self):", "            self.clients.remove(websocket)\n\n    def _start_server(self):")
content = content.replace("            self.thread.start()    def stop(self):", "            self.thread.start()\n\n    def stop(self):")

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
