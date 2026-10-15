import sys
sys.path.insert(0, r'C:\Users\Administrator\Trabajo\GSsmartDesktopFree')
from src.core import config
print("PROVIDERS:", config.PROVIDERS)
print("List:", config.list_providers())
for name in config.list_providers():
    print(f"  {name}:", config.get_provider_config(name))