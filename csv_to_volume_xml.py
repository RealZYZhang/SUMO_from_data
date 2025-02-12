import pandas as pd
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime
import subprocess
import json
import os

# Load configuration
def load_config(config_path='config.json'):
    """Load configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config['signalized_intersections']
    except Exception as e:
        print(f"Error loading config file: {e}")
        raise

# Load configuration from JSON
intersections = load_config()

def load_and_filter_data(csv_path: str, start_time: str, end_time: str):
    """Load CSV data and filter by time range"""
    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    print("Converting timestamps and filtering by time range...")
    # Convert to datetime and set timezone
    df['data_update_time'] = pd.to_datetime(df['data_update_time'], utc=True)
    df['data_update_time'] = df['data_update_time'].dt.tz_convert('US/Central')
    
    # Filter by time range
    mask = (df['data_update_time'] >= start_time) & (df['data_update_time'] <= end_time)
    filtered = df[mask].copy()
    print(f"Filtered data contains {len(filtered)} records")
    return filtered

def aggregate_data(filtered_df: pd.DataFrame):
    """Aggregate data into 15-minute bins"""
    print("Aggregating data into 15-minute intervals...")
    filtered_df.set_index('data_update_time', inplace=True)
    grouped = filtered_df.groupby(['intersection_id', 'entrance_direction', 'exit_direction'])\
                        .resample('15min')['vehicle_count'].sum().reset_index()
    print(f"Created {len(grouped)} aggregated records")
    return grouped

def generate_xml(aggregated_df: pd.DataFrame, output_filename: str):
    """Generate XML file from filtered data"""
    print("Generating XML file...")
    xml_root = ET.Element('data')
    start_timestamp = aggregated_df['data_update_time'].min()
    
    # Create ID to code mapping
    print("Creating intersection ID to code mapping...")
    id_to_code = {get_intersection_id(code): code for code in intersections}
    
    print("Processing intervals and creating XML structure...")
    interval_count = 0
    for timestamp, group in aggregated_df.groupby('data_update_time'):
        begin_time = (timestamp - start_timestamp).total_seconds()
        end_time = begin_time + 900  # 15 minutes
        
        interval = ET.SubElement(xml_root, 'interval')
        interval.set('id', timestamp.strftime('%Y-%m-%d %H:%M:%S%z'))
        interval.set('begin', str(int(begin_time)))
        interval.set('end', str(int(end_time)))
        
        for _, row in group.iterrows():
            code = id_to_code[row['intersection_id']]
            from_edge = f"{code}-{row['entrance_direction']}-in"
            to_edge = f"{code}-{row['exit_direction']}-out"
            
            edge_relation = ET.SubElement(interval, 'edgeRelation')
            edge_relation.set('from', from_edge)
            edge_relation.set('to', to_edge)
            edge_relation.set('count', str(row['vehicle_count']))
        interval_count += 1
    
    print(f"Writing XML file with {interval_count} intervals...")
    ET.ElementTree(xml_root).write(output_filename, encoding='utf-8', xml_declaration=True)
    print(f"Successfully generated XML file: {output_filename}")

def get_intersection_id(code: str) -> str:
    """Get intersection ID from code using config"""
    return intersections[code]['id']

def get_intersection_name(code: str) -> str:
    """Get intersection name from code using config"""
    return intersections[code]['name']

def update_sumo_config(trips_file: str, config_file: str = 'SUMO_files/SR1-3.sumocfg'):
    """Update SUMO config file with new trips file"""
    print(f"\nUpdating SUMO configuration file {config_file}...")
    tree = ET.parse(config_file)
    root = tree.getroot()
    
    # Update route-files value
    route_files = root.find('.//route-files')
    if route_files is not None:
        route_files.set('value', trips_file)
        tree.write(config_file, encoding='utf-8', xml_declaration=True)
        print(f"Successfully updated SUMO config with trips file: {trips_file}")
    else:
        print("Warning: Could not find route-files element in SUMO config")

def main():
    parser = argparse.ArgumentParser(description='Generate XML from downloaded volume data')
    parser.add_argument('--csv_input', required=True, help='Path to downloaded CSV file')
    parser.add_argument('--route_file', required=True, help='Path to SUMO route file')
    parser.add_argument('--output', required=True, help='Output XML filename')
    parser.add_argument('--start', required=True, help='Start time (YYYY-MM-DD HH:MM:SS±TZ)')
    parser.add_argument('--end', required=True, help='End time (YYYY-MM-DD HH:MM:SS±TZ)')
    args = parser.parse_args()

    print("\n=== Starting Volume Data Processing ===")
    
    # Process data
    filtered_data = load_and_filter_data(args.csv_input, args.start, args.end)
    aggregated_data = aggregate_data(filtered_data)
    
    # Generate XML
    generate_xml(aggregated_data, args.output)
    
    # Add route sampling step
    print("\n=== Starting Route Sampling ===")
    trips_output = args.output.replace('.xml', '_trips.xml')
    try:
        print("Running routeSampler.py...")
        subprocess.run([
            'python', 'SUMO_files/routeSampler.py',
            '-r', args.route_file,
            '--turn-files', args.output,
            '-o', trips_output
        ], check=True)
        print(f"Successfully generated vehicle trips file: {trips_output}")
        
        # Update SUMO config with new trips file
        update_sumo_config(os.path.basename(trips_output), config_file='SUMO_files/SR1-3.sumocfg')
        update_sumo_config(os.path.basename(trips_output), config_file='SUMO_files/SR1-3-NEMA.sumocfg')

    except subprocess.CalledProcessError as e:
        print(f"\nError running routeSampler: {e}")
    except FileNotFoundError:
        print("\nrouteSampler.py not found - ensure it's in the SUMO_files directory")
    
    print("\n=== Processing Complete ===")

if __name__ == "__main__":
    main()