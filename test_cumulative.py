import json
import pandas as pd
from datetime import datetime
import pytz

# Load the cache data
with open('previous_launches_cache.json', 'r') as f:
    cache_data = json.load(f)

launches = cache_data['data']
print(f'Total launches: {len(launches)}')

# Process the data like the app does
df = pd.DataFrame(launches)
df['date'] = pd.to_datetime(df['date'])
current_year = datetime.now(pytz.UTC).year
df = df[df['date'].dt.year == current_year]
print(f'Launches in {current_year}: {len(df)}')

rocket_types = ['Starship', 'Falcon 9', 'Falcon Heavy']
df = df[df['rocket'].isin(rocket_types)]
print(f'Filtered launches: {len(df)}')

if len(df) > 0:
    df['month'] = df['date'].dt.to_period('M').astype(str)
    df_grouped = df.groupby(['month', 'rocket']).size().reset_index(name='Launches')
    df_pivot = df_grouped.pivot(index='month', columns='rocket', values='Launches').fillna(0)
    print('Monthly data:')
    print(df_pivot)

    # Test cumulative
    df_cumulative = df_pivot.cumsum()
    print('\nCumulative data:')
    print(df_cumulative)

    # Check data for each rocket
    for rocket in rocket_types:
        if rocket in df_pivot.columns:
            monthly_values = df_pivot[rocket].tolist()
            cumulative_values = df_cumulative[rocket].tolist()
            print(f'{rocket} monthly: {monthly_values}')
            print(f'{rocket} cumulative: {cumulative_values}')
        else:
            print(f'{rocket}: not found in data')
else:
    print('No launches found for current year')
