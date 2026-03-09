import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

content = content.replace("            logger.info(\"Motion started\")    def stop_motion(self):", "            logger.info(\"Motion started\")\n\n    def stop_motion(self):")

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
