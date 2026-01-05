import requests

LAUNCH_API_BASE_URL = "https://launch-narrative-api-dafccc521fb8.herokuapp.com"

def check_url(endpoint, params=None):
    url = f"{LAUNCH_API_BASE_URL}{endpoint}"
    print(f"Testing URL: {url} with params: {params}")
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 404:
            print("  404 Not Found")
            return
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            print(f"  List length: {len(data)}")
        elif isinstance(data, dict):
            print(f"  Dict keys: {list(data.keys())}")
            for k in ['upcoming', 'previous', 'results', 'launches']:
                if k in data and isinstance(data[k], list):
                    print(f"    {k} length: {len(data[k])}")
    except Exception as e:
        print(f"  Error: {e}")

print("--- Testing separate endpoints ---")
check_url("/previous")
check_url("/upcoming")
check_url("/previous_launches")
check_url("/upcoming_launches")
check_url("/launches/previous")
check_url("/launches/upcoming")

print("\n--- Testing /launches with different limit param names ---")
check_url("/launches", params={'limit': 100})
check_url("/launches", params={'max': 100})
check_url("/launches", params={'per_page': 100})
check_url("/launches", params={'results': 100})
