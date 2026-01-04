
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    print("Checking functions.py...")
    import functions
    print("functions.py imported successfully")
except Exception as e:
    print(f"Error importing functions.py: {e}")

try:
    print("Checking app.py...")
    # Mocking PyQt6 objects because we can't initialize full QAApplication here easily and it might fail on import if no display
    # But we just want to check syntax.
    # Actually app.py imports PyQt6, so if the environment has it, it should work.
    # If not, we might catch ImportError.
    import app
    print("app.py imported successfully")
except ImportError as e:
    print(f"ImportError (expected if deps missing): {e}")
except SyntaxError as e:
    print(f"SyntaxError in app.py: {e}")
except Exception as e:
    print(f"Error importing app.py: {e}")
