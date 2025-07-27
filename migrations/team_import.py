#!/usr/bin/env python3
"""
import_teams.py

Loads teams.csv (located in the same directory) and inserts the team names into the 'teams' table in the Postgres database.

Usage:
    python import_teams.py

Environment Variables (optional):
    DB_HOST (default 'localhost')
    DB_PORT (default '5432')
    DB_NAME (default 'cfb26')
    DB_USER (default 'ethan')
    DB_PASSWORD (default 'WarEagles544!')
"""

import os
import csv
import sys
import psycopg2
from psycopg2.extras import execute_values

def main():
    # Database connection parameters
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'cfb26')
    db_user = os.getenv('DB_USER', 'ethan')
    db_password = os.getenv('DB_PASSWORD', 'WarEagles544!')

    # Path to CSV file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file = os.path.join(script_dir, 'teams.csv')

    # Read team names from CSV
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            # Skip first metadata row
            next(reader)
            # Read header row and find 'School' column index
            header = next(reader)
            if 'School' not in header:
                print("Error: 'School' column not found in CSV header", file=sys.stderr)
                sys.exit(1)
            school_idx = header.index('School')

            teams = []
            for row in reader:
                name = row[school_idx].strip()
                if name:
                    teams.append((name,))
    except FileNotFoundError:
        print(f"Error: CSV file not found at {csv_file}", file=sys.stderr)
        sys.exit(1)

    if not teams:
        print("No team data found in CSV.", file=sys.stderr)
        sys.exit(1)

    # Connect to Postgres
    try:
        conn = psycopg2.connect(
            host=db_host, port=db_port, dbname=db_name,
            user=db_user, password=db_password
        )
        conn.autocommit = True
        cur = conn.cursor()
    except Exception as e:
        print(f"Error connecting to database: {e}", file=sys.stderr)
        sys.exit(1)


    # Bulk insert team names
    insert_query = "INSERT INTO teams (name) VALUES %s;"
    try:
        execute_values(cur, insert_query, teams)
        print(f"Inserted {len(teams)} teams into the database.")
    except Exception as e:
        print(f"Error inserting data: {e}", file=sys.stderr)
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
