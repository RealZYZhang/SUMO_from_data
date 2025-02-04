import pandas as pd
import matplotlib.pyplot as plt
import json
from datetime import datetime
import argparse

def plot_daily_counts(start_date: str, end_date: str):
    # Set global font size
    plt.rcParams.update({'font.size': 16})

    # Load config
    with open('config.json') as f:
        config = json.load(f)

    # Load and preprocess data
    df = pd.read_csv('data/sampled_intersections_volume_2022-2025.csv', 
                     parse_dates=['data_update_time'])

    # Merge with config to get intersection names
    intersection_df = pd.DataFrame.from_dict(config['signalized_intersections'], 
                                           orient='index').reset_index()
    df = pd.merge(df, intersection_df, left_on='intersection_id', right_on='id')

    # Extract date (without time component) and remove timezone information
    df['date'] = df['data_update_time'].dt.tz_localize(None).dt.normalize()

    # Aggregate daily counts
    daily_counts = df.groupby(['name', 'date'])['vehicle_count'].sum().reset_index()

    # Filter for date range - convert input dates to datetime
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    daily_counts = daily_counts[
        (daily_counts['date'] >= start_dt) & 
        (daily_counts['date'] <= end_dt)
    ]

    # Create figure and subplots
    unique_names = daily_counts['name'].unique()
    fig, axes = plt.subplots(len(unique_names), 1, figsize=(12, 2.5*len(unique_names)))
    plt.style.use('seaborn-v0_8-whitegrid')

    # Plot each intersection
    for idx, name in enumerate(unique_names):
        intersection_data = daily_counts[daily_counts['name'] == name]
        axes[idx].plot(intersection_data['date'], intersection_data['vehicle_count'])
        axes[idx].set_title(name)

        # Only set y-label for middle subplot
        if idx == 1:
            axes[idx].set_ylabel("Daily Vehicle Count")
        
        # Only set x-label for the last subplot
        if idx == len(unique_names) - 1:
            axes[idx].set_xticks(pd.date_range(start=daily_counts['date'].min(),
                                        end=daily_counts['date'].max(),
                                        freq='QS'))
        else:
            axes[idx].tick_params(axis='x', which='both', bottom=False, top=False, labelbottom=False)
    plt.tight_layout()
    plt.show()

def main():
    parser = argparse.ArgumentParser(description='Plot daily vehicle counts for intersections')
    parser.add_argument('--start_date', required=True, help='Start date in YYYY-MM-DD format')
    parser.add_argument('--end_date', required=True, help='End date in YYYY-MM-DD format')
    
    args = parser.parse_args()
    plot_daily_counts(args.start_date, args.end_date)

if __name__ == '__main__':
    main()