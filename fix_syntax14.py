import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

content = content.replace("            return False    def disconnect_all(self):", "            return False\n\n    def disconnect_all(self):")

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
