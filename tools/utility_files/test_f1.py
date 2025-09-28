import json

# Mock the F1_TEAM_COLORS
F1_TEAM_COLORS = {
    'red_bull': '#3671C6',
    'mercedes': '#6CD3BF', 
    'ferrari': '#E8002D',
    'mclaren': '#FF8000',
    'alpine': '#0093CC',
    'aston_martin': '#2D826D',
    'williams': '#37BEDD',
    'rb': '#6692FF',
    'sauber': '#52E252',
    'haas': '#B6BABD'
}

# Load the data
try:
    with open('../cache/f1_cache.json', 'r') as f:
        cache_data = json.load(f)
    f1_data = cache_data['data']
    standings = f1_data['driver_standings']
    
    # Simulate the function
    top_drivers = standings[:10]
    stat_key = 'points'
    
    series_data = []
    team_drivers = {}
    
    for driver in top_drivers:
        team_id = driver.get('teamId', 'unknown')
        if team_id not in team_drivers:
            team_drivers[team_id] = []
        team_drivers[team_id].append(driver)
    
    for team_id, drivers in team_drivers.items():
        team_color = F1_TEAM_COLORS.get(team_id, '#808080')
        for driver in drivers:
            driver_name = f"{driver['Driver']['givenName']} {driver['Driver']['familyName']}"
            points = float(driver.get(stat_key, 0))
            series_data.append({
                'label': driver_name,
                'values': [points],
                'color': team_color,
                'team': driver.get('Constructor', {}).get('name', team_id)
            })
    
    print('Series data length:', len(series_data))
    for item in series_data[:3]:
        print('Item:', item)
        
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()
