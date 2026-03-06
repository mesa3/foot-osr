import re

with open('dual_osr_control.py', 'r') as f:
    content = f.read()

# Fix the mousewheel logic and syntax
mousewheel_code = """    def _on_mousewheel(self, event):
        # Windows/Mac/Linux cross platform
        if hasattr(event, 'num') and event.num == 5 or getattr(event, 'delta', 0) < 0:
            self.canvas.yview_scroll(1, "units")
        elif hasattr(event, 'num') and event.num == 4 or getattr(event, 'delta', 0) > 0:
            self.canvas.yview_scroll(-1, "units")"""

content = re.sub(r'(\s+)def _on_mousewheel\(self, event\):.*?self\.canvas\.yview_scroll\(-1, "units"\)', mousewheel_code, content, flags=re.DOTALL)

with open('dual_osr_control.py', 'w') as f:
    f.write(content)
