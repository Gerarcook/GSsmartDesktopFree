import os
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env", override=False)

key = os.getenv("OMNIROUTE_API_KEY")
print(f"Key: {repr(key)}")
print(f"Length: {len(key) if key else 0}")
print(f"Starts with sk-? {key.startswith('sk-') if key else False}")
print(f"Contains spaces? {' ' in key if key else False}")
print(f"Contains newline? {'\\n' in key if key else False}")