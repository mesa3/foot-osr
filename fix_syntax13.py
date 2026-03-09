import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

content = content.replace("        logger.info(\"All devices disconnected\")    def start_motion(self):", "        logger.info(\"All devices disconnected\")\n\n    def start_motion(self):")

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
