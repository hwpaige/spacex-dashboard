import requests

LAUNCH_API_BASE_URL = "https://launch-narrative-api-dafccc521fb8.herokuapp.com"

def check_api(params=None):
    url = f"{LAUNCH_API_BASE_URL}/launches"
    print(f"Testing URL: {url} with params: {params}")
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        upcoming = data.get('upcoming', [])
        previous = data.get('previous', [])
        print(f"  Upcoming: {len(upcoming)}")
        print(f"  Previous: {len(previous)}")
    except Exception as e:
        print(f"  Error: {e}")

print("--- Testing if limit works for smaller values ---")
check_api(params={'limit': 5})
check_api(params={'limit': 10})
check_api(params={'limit': 15})
check_api(params={'limit': 20})
