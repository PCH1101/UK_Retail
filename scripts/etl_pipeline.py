import os
import re
import sys
from urllib.parse import quote_plus
import pandas as pd
import numpy as np
from sqlalchemy import create_engine

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    project_env = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(project_env)

def run_etl(csv_path='data/retail.csv'):
    print("=== STARTING ETL PIPELINE ===")
    
    # 1. Database Connection Configuration
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT')
    db_user = os.getenv('DB_USER') or os.getenv('POSTGRES_USER')
    db_password = os.getenv('DB_PASSWORD') or os.getenv('POSTGRES_PASSWORD')
    db_name = os.getenv('DB_NAME') or os.getenv('RETAIL_DB')
    missing_config = [
        name for name, value in {
            'DB_HOST': db_host,
            'DB_PORT': db_port,
            'DB_USER': db_user,
            'DB_PASSWORD': db_password,
            'DB_NAME': db_name,
        }.items() if not value
    ]
    if missing_config:
        raise RuntimeError(f"Missing database configuration: {', '.join(missing_config)}")
    
    conn_str = (
        f"postgresql+psycopg2://{quote_plus(db_user)}:{quote_plus(db_password)}"
        f"@{db_host}:{db_port}/{quote_plus(db_name)}"
    )
    print(f"Connecting to database at {db_host}:{db_port}/{db_name}...")
    try:
        engine = create_engine(conn_str)
        # Test connection & Initialize Schema
        with engine.begin() as conn:
            print("Database connection test successful!")
            schema_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'init_dw_schema.sql')
            if os.path.exists(schema_path):
                print(f"Initializing database schema from {schema_path}...")
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema_sql = f.read()
                from sqlalchemy import text
                # Execute DDL statements
                conn.execute(text(schema_sql))
                print("Database schema initialized successfully!")
            else:
                print("Warning: init_dw_schema.sql not found, skipping schema initialization.")
    except Exception as e:
        print(f"ERROR: Cannot connect or initialize database: {e}")
        sys.exit(1)
        
    # 2. Extract Phase
    print(f"Reading source data from {csv_path} with ISO-8859-1 encoding...")
    if not os.path.exists(csv_path):
        print(f"ERROR: CSV file not found at {csv_path}")
        sys.exit(1)
        
    df = pd.read_csv(csv_path, encoding='ISO-8859-1')
    print(f"Successfully loaded {len(df)} rows.")

    # 3. Clean & Normalize Phase
    print("Cleaning and normalizing data...")
    # Missing CustomerID -> -1, cast to integer then to string
    df['CustomerID'] = df['CustomerID'].fillna(-1).astype(int).astype(str)
    # Missing Description -> UNKNOWN, trim and uppercase
    df['Description'] = df['Description'].fillna('UNKNOWN').astype(str).str.strip().str.upper()
    # Clean StockCode
    df['StockCode'] = df['StockCode'].astype(str).str.strip()
    # Clean Country
    df['Country'] = df['Country'].astype(str).str.strip()
    # Parse InvoiceDate
    df['InvoiceDate'] = pd.to_datetime(df['InvoiceDate'], format='mixed')
    # Compute TotalAmount
    df['TotalAmount'] = df['Quantity'] * df['UnitPrice']
    
    # 4. Dimension Population Phase
    print("Populating conformed dimensions...")
    
    # Helper to load/upsert dimensions
    def load_dimension(df_dim, table_name, unique_cols):
        try:
            existing_df = pd.read_sql(f"SELECT * FROM {table_name}", engine)
        except Exception as e:
            print(f"Warning: Could not read {table_name}, assuming empty: {e}")
            existing_df = pd.DataFrame(columns=df_dim.columns)
            
        if not existing_df.empty:
            # Match new rows against existing rows
            merged = df_dim.merge(existing_df, on=unique_cols, how='left', suffixes=('', '_existing'))
            # Filter rows that do not exist in the database (where surrogate key is null)
            surrogate_key_col = existing_df.columns[0]
            new_rows = merged[merged[surrogate_key_col].isnull()][df_dim.columns]
        else:
            new_rows = df_dim
            
        if not new_rows.empty:
            new_rows.to_sql(table_name, engine, if_exists='append', index=False)
            print(f"Inserted {len(new_rows)} new rows into {table_name}")
        else:
            print(f"No new rows to insert into {table_name}")

    # A. Dim Date
    min_date = df['InvoiceDate'].min()
    max_date = df['InvoiceDate'].max()
    print(f"Generating date dimension range: {min_date.date()} to {max_date.date()}...")
    date_range = pd.date_range(start=min_date.floor('D'), end=max_date.floor('D'))
    df_date = pd.DataFrame({'date': date_range})
    df_date['date_key'] = df_date['date'].dt.strftime('%Y%m%d').astype(int)
    df_date['day'] = df_date['date'].dt.day
    df_date['month'] = df_date['date'].dt.month
    df_date['quarter'] = df_date['date'].dt.quarter
    df_date['year'] = df_date['date'].dt.year
    df_date['day_of_week'] = df_date['date'].dt.dayofweek + 1 # Monday=1, Sunday=7
    df_date['is_weekend'] = df_date['day_of_week'].isin([6, 7])
    df_date['date'] = df_date['date'].dt.date
    load_dimension(df_date, 'dim_date', ['date_key'])

    # B. Dim Time
    print("Generating time dimension...")
    time_keys = list(range(24))
    df_time = pd.DataFrame({
        'time_key': time_keys,
        'hour': time_keys,
        'minute': [0] * 24
    })
    def get_time_of_day(h):
        if 5 <= h < 12: return 'Sáng'
        elif 12 <= h < 18: return 'Trưa/Chiều'
        else: return 'Tối/Đêm'
    df_time['time_of_day'] = df_time['hour'].apply(get_time_of_day)
    load_dimension(df_time, 'dim_time', ['time_key'])

    # C. Dim Country
    print("Generating country dimension...")
    unique_countries = pd.DataFrame({'country_name': df['Country'].unique()})
    load_dimension(unique_countries, 'dim_country', ['country_name'])

    # D. Dim Customer
    print("Generating customer dimension...")
    # Map each customer to their primary country (first country they ordered from)
    df_customer_prep = df.groupby('CustomerID').agg({
        'Country': lambda x: x.iloc[0] if len(x) > 0 else 'UNKNOWN'
    }).reset_index().rename(columns={'CustomerID': 'customer_id', 'Country': 'country_name'})
    load_dimension(df_customer_prep, 'dim_customer', ['customer_id'])

    # E. Dim Product
    print("Generating product dimension with standardization...")
    # Find the most frequent valid description for each StockCode
    def resolve_description(group):
        valid = group[group != 'UNKNOWN']
        if not valid.empty:
            return valid.value_counts().index[0]
        return 'UNKNOWN'

    df_product_prep = df.groupby('StockCode')['Description'].apply(resolve_description).reset_index()
    df_product_prep.rename(columns={'StockCode': 'stock_code', 'Description': 'description'}, inplace=True)
    
    # Classify physical vs non-physical products
    non_physical_codes = {'POST', 'DOT', 'C2', 'D', 'M', 'm', 'BANK CHARGES', 'AMAZONFEE', 'CRUK', 'S'}
    df_product_prep['is_physical'] = ~df_product_prep['stock_code'].isin(non_physical_codes)
    load_dimension(df_product_prep, 'dim_product', ['stock_code'])

    # 5. Key Mapping Phase
    print("Mapping surrogate keys to raw transaction data...")
    # Load dimensions to obtain surrogate keys
    dim_country_db = pd.read_sql("SELECT country_key, country_name FROM dim_country", engine)
    dim_customer_db = pd.read_sql("SELECT customer_key, customer_id FROM dim_customer", engine)
    dim_product_db = pd.read_sql("SELECT product_key, stock_code, is_physical FROM dim_product", engine)

    # Join
    df_mapped = df.merge(dim_country_db, left_on='Country', right_on='country_name', how='left')
    df_mapped = df_mapped.merge(dim_customer_db, left_on='CustomerID', right_on='customer_id', how='left')
    df_mapped = df_mapped.merge(dim_product_db, left_on='StockCode', right_on='stock_code', how='left')

    df_mapped['date_key'] = df_mapped['InvoiceDate'].dt.strftime('%Y%m%d').astype(int)
    df_mapped['time_key'] = df_mapped['InvoiceDate'].dt.hour

    # 6. Route Classification & Load Phase
    print("Classifying and routing transactions to their respective Fact tables...")

    # A. Sales Fact: Real customer product transactions (Standard/physical products, UnitPrice > 0)
    sales_mask = (df_mapped['UnitPrice'] > 0) & (df_mapped['is_physical'] == True)
    df_sales = df_mapped[sales_mask].copy()
    df_sales['is_cancelled'] = df_sales['InvoiceNo'].astype(str).str.startswith('C')
    
    fact_sales = df_sales[[
        'InvoiceNo', 'customer_key', 'product_key', 'date_key', 'time_key', 
        'country_key', 'Quantity', 'UnitPrice', 'TotalAmount', 'is_cancelled'
    ]].rename(columns={
        'InvoiceNo': 'invoice_no',
        'Quantity': 'quantity',
        'UnitPrice': 'unit_price',
        'TotalAmount': 'total_amount'
    })

    # B. Invoice Fees Fact: Shipping fees, discounts, and banking/platform charges
    fee_codes = {'POST', 'DOT', 'C2', 'D', 'M', 'm', 'BANK CHARGES', 'AMAZONFEE', 'CRUK', 'S'}
    df_fees = df_mapped[df_mapped['StockCode'].isin(fee_codes)].copy()
    
    def get_fee_type(code):
        if code in ['POST', 'DOT', 'C2']: return 'Shipping'
        elif code in ['D']: return 'Discount'
        elif code in ['S']: return 'Sample'
        else: return 'Financial Fee'
        
    df_fees['fee_type'] = df_fees['StockCode'].apply(get_fee_type)
    
    # Ensure discounts are negative
    discount_mask = df_fees['StockCode'] == 'D'
    df_fees.loc[discount_mask & (df_fees['Quantity'] > 0), 'Quantity'] = -df_fees.loc[discount_mask & (df_fees['Quantity'] > 0), 'Quantity']
    df_fees['TotalAmount'] = df_fees['Quantity'] * df_fees['UnitPrice']

    fact_invoice_fees = df_fees[[
        'InvoiceNo', 'customer_key', 'product_key', 'date_key', 'time_key', 
        'country_key', 'Quantity', 'UnitPrice', 'TotalAmount', 'fee_type'
    ]].rename(columns={
        'InvoiceNo': 'invoice_no',
        'Quantity': 'quantity',
        'UnitPrice': 'unit_price',
        'TotalAmount': 'total_amount'
    })

    # C. Inventory Adjustments Fact: Adjustments with UnitPrice == 0 or accounting write-offs (B)
    adj_mask = (df_mapped['UnitPrice'] == 0) | (df_mapped['StockCode'] == 'B')
    df_adj = df_mapped[adj_mask].copy()
    
    def get_adj_type(row):
        desc = str(row['Description']).upper()
        code = str(row['StockCode'])
        if code == 'B': return 'Bad Debt Write-off'
        elif 'DAMAGE' in desc or 'DAMAGED' in desc: return 'Damaged'
        elif 'LOST' in desc: return 'Lost'
        elif 'FOUND' in desc: return 'Found'
        elif 'DESTROYED' in desc: return 'Destroyed'
        elif 'CHECK' in desc: return 'Stock Check'
        else: return 'Warehouse Adjustment'
        
    df_adj['adjustment_type'] = df_adj.apply(get_adj_type, axis=1)

    fact_inventory_adjustments = df_adj[[
        'InvoiceNo', 'product_key', 'date_key', 'time_key', 
        'Quantity', 'UnitPrice', 'TotalAmount', 'adjustment_type'
    ]].rename(columns={
        'InvoiceNo': 'invoice_no',
        'Quantity': 'quantity',
        'UnitPrice': 'unit_price',
        'TotalAmount': 'total_amount'
    })

    # Load Facts (clean tables before loading to avoid duplicate data on rerun)
    print("Clearing old facts and bulk loading new datasets...")
    with engine.begin() as conn:
        from sqlalchemy import text
        conn.execute(text("TRUNCATE TABLE fact_sales, fact_invoice_fees, fact_inventory_adjustments CASCADE;"))
        print("Truncated old facts successfully.")

    # Ingest facts in chunk sizes for efficiency
    print(f"Loading {len(fact_sales)} rows into fact_sales...")
    fact_sales.to_sql('fact_sales', engine, if_exists='append', index=False, chunksize=20000)

    print(f"Loading {len(fact_invoice_fees)} rows into fact_invoice_fees...")
    fact_invoice_fees.to_sql('fact_invoice_fees', engine, if_exists='append', index=False, chunksize=20000)

    print(f"Loading {len(fact_inventory_adjustments)} rows into fact_inventory_adjustments...")
    fact_inventory_adjustments.to_sql('fact_inventory_adjustments', engine, if_exists='append', index=False, chunksize=20000)

    print("=== ETL PIPELINE COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    csv_arg = sys.argv[1] if len(sys.argv) > 1 else 'data/retail.csv'
    run_etl(csv_arg)
