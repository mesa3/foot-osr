import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

# Replace stop_motion join with a short timeout or just let it naturally end since it's a daemon thread
replacement = """    def stop_motion(self):
        self.running = False
        # Do not block the GUI thread waiting for serial writes or sleep to finish
        # if self.thread and self.thread.is_alive():
        #     self.thread.join(timeout=0.1)
        logger.info("Motion stopped signal sent (waiting for thread to finish in background)")"""

content = re.sub(r'(\s+)def stop_motion\(self\):.*?logger\.info\("Motion stopped"\)', replacement, content, flags=re.DOTALL)

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
