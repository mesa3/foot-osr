import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

# Replace _start_server
ws_replacement = """    def _start_server(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def _serve():
            self.server = await websockets.serve(self._handler, "0.0.0.0", self.port)
            logger.info(f"WebSocket server started on port {self.port}")

        self.loop.run_until_complete(_serve())
        self.loop.run_forever()"""

content = re.sub(r'(\s+)def _start_server\(self\):.*?self\.loop\.run_forever\(\)', ws_replacement, content, flags=re.DOTALL)

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
