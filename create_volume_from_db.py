import pandas as pd
import psycopg2
import traceback
import argparse
from datetime import datetime
import xml.etree.ElementTree as ET

# Database configuration
TS_DATABASE_NAME = 'aidss-prod'
TS_DATABASE_HOST = '10.80.3.22'
TS_DATABASE_PORT = 5432
TS_DATABASE_USERNAME = 'zhiyao'
TS_DATABASE_PASSWORD = 'zhiyao8275682'

# Intersection mapping (code to full name)
SIGNALIZED_INTERSECTIONS = {
    'S1': 'Madison Square Boulevard and Murfreesboro Road',
    'S2': 'Stones River Road and Murfreesboro Road',
    'S3': 'Floyd Mayfield Drive and Murfreesboro Pike'
}

def make_ts_db_connection() -> psycopg2.extensions.connection:
    """Create and return a database connection."""
    return psycopg2.connect(
        host=TS_DATABASE_HOST,
        port=TS_DATABASE_PORT,
        dbname=TS_DATABASE_NAME,
        user=TS_DATABASE_USERNAME,
        password=TS_DATABASE_PASSWORD
    )

def database_query(query_message: str, params: tuple = None):
    """Execute a database query and return results."""
    conn = make_ts_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(query_message, params)
        return [desc[0] for desc in cur.description], cur.fetchall()
    except Exception:
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()

def query_volume_data(intersection_ids: list, start_time: str, end_time: str):
    """Query volume data for given intersections and time range."""
    query = """
    SELECT DISTINCT ON (intersection_id, data_update_time, vehicle_class, entrance_direction, exit_direction) 
        intersection_id, 
        data_update_time, 
        data_interval_in_minutes, 
        vehicle_class, 
        entrance_direction, 
        exit_direction, 
        vehicle_count
    FROM external_feeds.miovision_volume
    WHERE intersection_id = ANY(%s)
        AND data_update_time BETWEEN %s AND %s
    ORDER BY intersection_id, data_update_time ASC, 
        vehicle_class, entrance_direction, exit_direction
    """
    return database_query(query, (intersection_ids, start_time, end_time))

def get_intersection_ids_by_names(names: list) -> list:
    """Get intersection IDs from their names using a CSV mapping."""
    df = pd.read_csv('/Users/zhiyao/PycharmProjects/Signal_timing_change/source/environments/all_intersections.csv')
    filtered_df = df[df['name'].isin(names)]
    return filtered_df['id'].tolist()

def aggregate_volume_data(headers, data, bin_size: str = '15min'):
    """Process and aggregate raw volume data."""
    df = pd.DataFrame(data, columns=headers)
    # Convert to timezone-aware datetime (UTC to US/Central)
    df['data_update_time'] = pd.to_datetime(df['data_update_time'], utc=True).dt.tz_convert('US/Central')
    df.set_index('data_update_time', inplace=True)
    
    grouped = df.groupby(['intersection_id', 'entrance_direction', 'exit_direction'])\
                .resample(bin_size)['vehicle_count'].sum().reset_index()
    
    return grouped

def generate_xml_from_data(df: pd.DataFrame, id_to_code: dict, output_filename: str):
    """Generate XML file from processed volume data."""
    xml_root = ET.Element('data')
    start_timestamp = df['data_update_time'].min()
    
    for timestamp, group in df.groupby('data_update_time'):
        begin_time = (timestamp - start_timestamp).total_seconds()
        end_time = begin_time + 900  # 15 minutes
        
        interval = ET.SubElement(xml_root, 'interval')
        interval.set('id', timestamp.strftime('%Y-%m-%d %H:%M:%S%z'))
        interval.set('begin', str(int(begin_time)))
        interval.set('end', str(int(end_time)))
        
        for _, row in group.iterrows():
            intersection_code = id_to_code[row['intersection_id']]
            from_edge = f"{intersection_code}-{row['entrance_direction']}-in"
            to_edge = f"{intersection_code}-{row['exit_direction']}-out"
            
            edge_relation = ET.SubElement(interval, 'edgeRelation')
            edge_relation.set('from', from_edge)
            edge_relation.set('to', to_edge)
            edge_relation.set('count', str(row['vehicle_count']))
    
    ET.ElementTree(xml_root).write(output_filename, encoding='utf-8', xml_declaration=True)

def main():
    parser = argparse.ArgumentParser(description='Process intersection volume data')
    parser.add_argument('--start', default="2024-10-21 00:00:00-05:00", required=True, help='Start timestamp (YYYY-MM-DD HH:MM:SS TZ)')
    parser.add_argument('--end', default="2024-10-25 23:59:59-05:00", required=True, help='End timestamp (YYYY-MM-DD HH:MM:SS TZ)')
    args = parser.parse_args()
    
    # Process all intersections defined in SIGNALIZED_INTERSECTIONS
    selected_names = list(SIGNALIZED_INTERSECTIONS.values())
    
    # Get intersection IDs and create ID->code mapping
    intersection_ids = get_intersection_ids_by_names(selected_names)
    id_to_code = {id: code for id, code in zip(intersection_ids, SIGNALIZED_INTERSECTIONS.keys())}

    # Convert timestamps to UTC for database query
    start_utc = pd.to_datetime(args.start).tz_convert('UTC').strftime('%Y-%m-%d %H:%M:%S')
    end_utc = pd.to_datetime(args.end).tz_convert('UTC').strftime('%Y-%m-%d %H:%M:%S')

    # Query and process data
    headers, data = query_volume_data(intersection_ids, start_utc, end_utc)
    aggregated_df = aggregate_volume_data(headers, data)

    # Generate filename with date-only format
    start_date = pd.to_datetime(args.start).strftime('%Y%m%d')
    end_date = pd.to_datetime(args.end).strftime('%Y%m%d')
    base_filename = f"volume_{start_date}_{end_date}"
    
    # Save CSV
    csv_filename = f"{base_filename}.csv"
    aggregated_df.to_csv(csv_filename, index=False)
    
    # Generate XML
    xml_filename = f"{base_filename}.xml"
    generate_xml_from_data(aggregated_df, id_to_code, xml_filename)
    print(f"Successfully generated {csv_filename} and {xml_filename}")

if __name__ == "__main__":
    main()