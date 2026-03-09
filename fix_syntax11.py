import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

content = content.replace("            self.btn_start.config(text=\"STOP MOTION\")        else:", "            self.btn_start.config(text=\"STOP MOTION\")\n        else:")

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
