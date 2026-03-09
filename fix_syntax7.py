import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

content = content.replace("self.canvas.itemconfig(self.canvas_window, width=event.width)    def _on_mousewheel(self, event):", "self.canvas.itemconfig(self.canvas_window, width=event.width)\n\n    def _on_mousewheel(self, event):")

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
