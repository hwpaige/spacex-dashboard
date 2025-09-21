import json

with open('f1_cache.json', 'r') as f:
    data = json.load(f)

print('Circuit names from F1 API:')
for race in data.get('data', {}).get('schedule', []):
    circuit_name = race['circuit_short_name']
    print(f'  "{circuit_name}"')