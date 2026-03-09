import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

content = content.replace("            logger.info(\"Disconnected all devices\")    def go_to_neutral(self):", "            logger.info(\"Disconnected all devices\")\n\n    def go_to_neutral(self):")
content = content.replace("            logger.info(\"All devices disconnected\")    def start_motion(self):", "            logger.info(\"All devices disconnected\")\n\n    def start_motion(self):")

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
