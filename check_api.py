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

print("--- Trying different params ---")
check_api(params={'limit': 100})
check_api(params={'limit_previous': 100, 'limit_upcoming': 100})
check_api(params={'previous_limit': 100, 'upcoming_limit': 100})
check_api(params={'count': 100})
check_api(params={'all': 'true'})
check_api(params={'mode': 'all'})
