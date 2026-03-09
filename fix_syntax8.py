import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

content = content.replace("            self.thread.start()    def stop(self):", "            self.thread.start()\n\n    def stop(self):")

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
