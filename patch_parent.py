import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

# Replace self.root with self.scrollable_frame in create_widgets
start_idx = content.find('def create_widgets(self):')
end_idx = content.find('def refresh_ports(self):')

widgets_code = content[start_idx:end_idx]
new_widgets_code = widgets_code.replace("ttk.LabelFrame(self.root,", "ttk.LabelFrame(self.scrollable_frame,")
new_widgets_code = new_widgets_code.replace("ttk.Button(self.root,", "ttk.Button(self.scrollable_frame,")

content = content[:start_idx] + new_widgets_code + content[end_idx:]

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
