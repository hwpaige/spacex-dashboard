import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))
from ui_qml import qml_code
import re

def check_balance():
    balance = 0
    lines = qml_code.split('\n')
    
    # Simple regex to remove string literals to avoid counting braces inside them
    # and remove comments
    
    for i, line in enumerate(lines):
        line_num = i + 65
        clean_line = re.sub(r'".*?"', '', line)
        clean_line = re.sub(r"'.*?'", '', clean_line)
        clean_line = re.sub(r'//.*', '', clean_line)
        
        opens = clean_line.count('{')
        closes = clean_line.count('}')
        balance += opens - closes
        if line_num in [1000, 1500, 2000]:
            print(f"Line {line_num}: Balance {balance}")
        if balance < 0:
            print(f"ERROR: Negative balance at line {line_num}")
            break
    print(f"Final Balance: {balance}")

# Run it
check_balance()
