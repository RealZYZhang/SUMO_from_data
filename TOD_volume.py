import pandas as pd
import matplotlib.pyplot as plt
import json
from datetime import datetime
import pytz

def main(dates_of_interest, date_types):
    plt.rcParams.update({'font.size': 16})

    # Load config
    with open('config.json') as f:
        config = json.load(f)

    # Load the traffic volume data
    df = pd.read_csv('data/sampled_intersections_volume_2022-2025.csv',
                     parse_dates=['data_update_time'])

    # Convert UTC to US Central time
    df['data_update_time'] = df['data_update_time'].dt.tz_convert('US/Central')

    # Filter for intersection S1
    intersection_id = config['signalized_intersections']['S1']['id']
    df_s1 = df[df['intersection_id'] == intersection_id]

    # Use .loc to avoid SettingWithCopyWarning
    df_s1.loc[:, 'date'] = df_s1['data_update_time'].dt.date

    # Filter for the specific dates
    df_filtered = df_s1[df_s1['date'].isin(pd.to_datetime(dates_of_interest).date)]

    # Extract time of day (in US Central time)
    df_filtered['time_of_day'] = df_filtered['data_update_time'].dt.time

    # Create a plot
    plt.figure(figsize=(10, 5))

    # Loop through each date and plot
    for date in dates_of_interest:
        daily_data = df_filtered[df_filtered['date'] == pd.to_datetime(date).date()]
        # Group by time of day and sum vehicle counts across all directions
        total_counts = daily_data.groupby(['time_of_day', 'data_update_time'])['vehicle_count'].sum().reset_index()
        # Then take the average for each time of day
        avg_counts = total_counts.groupby('time_of_day')['vehicle_count'].mean().reset_index()
        # Convert time objects to hours since midnight for plotting
        hours_since_midnight = [(t.hour + t.minute/60) for t in avg_counts['time_of_day']]
        plt.plot(hours_since_midnight, total_counts['vehicle_count'], label=f"{date} ({date_types[date]})")

    # Formatting the plot
    # plt.title("Overlapping Daily Traffic Volume Patterns at Intersection S1 (US Central Time)")
    plt.xlabel("Hour of Day (US Central)")
    plt.ylabel("15min Vehicle Count (All Directions)")
    plt.legend(title="Date")
    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
    dates_of_interest = ['2024-06-19', '2024-09-18', '2024-12-25']
    date_types = {
        '2024-06-19': 'Off-School Day',
        '2024-09-18': 'School Day',
        '2024-12-25': 'Public Holiday'
    }
    main(dates_of_interest, date_types)