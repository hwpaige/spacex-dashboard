import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))
from ui_qml import qml_code
import re

# Remove /* ... */ comments
code_no_comments = re.sub(r'/\*.*?\*/', '', qml_code, flags=re.DOTALL)
# Remove // ... comments
code_no_comments = re.sub(r'//.*', '', code_no_comments)

open_braces = code_no_comments.count('{')
close_braces = code_no_comments.count('}')
print(f"No comments - Open: {open_braces}")
print(f"No comments - Close: {close_braces}")
print(f"No comments - Difference: {open_braces - close_braces}")
