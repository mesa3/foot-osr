import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

ws_stop_replacement = """    def stop(self):
        if self.running and self.loop:
            self.running = False
            # Safely stop server without hanging
            try:
                self.loop.call_soon_threadsafe(self.server.close)
                self.loop.call_soon_threadsafe(self.loop.stop)
            except RuntimeError:
                pass # Event loop might be already closed
            logger.info(f"WebSocket server {self.port} stopped")"""

content = re.sub(r'(\s+)def stop\(self\):.*?logger\.info\("WebSocket server stopped"\)', ws_stop_replacement, content, flags=re.DOTALL)

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
