import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

init_replacement = """    def __init__(self, port=8766):
        self.port = port
        self.clients = set()
        self.loop = None
        self.running = False
        self.thread = None
        self.server = None"""

content = re.sub(r'(\s+)def __init__\(self, port=8766\):.*?self\.thread = None', init_replacement, content, flags=re.DOTALL)

serve_replacement = """    def _start_server(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def _serve():
            try:
                self.server = await websockets.serve(self._handler, "0.0.0.0", self.port)
                logger.info(f"WebSocket server started on port {self.port}")
            except OSError as e:
                logger.error(f"Failed to start WebSocket server on port {self.port}: {e}")
                self.running = False
                return

        self.loop.run_until_complete(_serve())
        if self.running:
            self.loop.run_forever()"""

content = re.sub(r'(\s+)def _start_server\(self\):.*?self\.loop\.run_forever\(\)', serve_replacement, content, flags=re.DOTALL)


stop_replacement = """    def stop(self):
        if self.running and self.loop:
            self.running = False
            # Safely stop server without hanging
            try:
                if self.server:
                    self.loop.call_soon_threadsafe(self.server.close)
                self.loop.call_soon_threadsafe(self.loop.stop)
            except RuntimeError:
                pass # Event loop might be already closed
            logger.info(f"WebSocket server {self.port} stopped")"""

content = re.sub(r'(\s+)def stop\(self\):.*?logger\.info\(f"WebSocket server \{self\.port\} stopped"\)', stop_replacement, content, flags=re.DOTALL)

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
