# UK Retail Data Warehouse

**[Tiếng Việt](README.vi.md)**

This project builds a data warehouse for UK-based online retail data.
Raw CSV data is cleaned with Python/Pandas, then loaded into a **multi-fact star schema** on PostgreSQL.

## Key Components

- PostgreSQL 15: stores the data warehouse and Airflow metadata.
- Apache Airflow: orchestrates the ETL pipeline.
- pgAdmin: PostgreSQL administration.
- Apache Superset: data visualization and dashboarding.
- Python, Pandas and SQLAlchemy: data processing and loading.

## Directory Structure

```text
data/       Source data and schema initialization SQL
dags/       Airflow DAGs
scripts/    ETL source code
docs/       Design documentation
```

## Quick Start

See [SETUP.md](docs/SETUP.md) for full installation and run instructions.

```bash
cp .env.example .env
docker compose up -d --build
```

After the containers are up:

- Airflow: http://localhost:8081
- pgAdmin: http://localhost:5051
- Superset: http://localhost:8089

The Airflow pipeline is named `online_retail_etl_pipeline` and runs manually when triggered.

## ETL Pipeline Overview

1. **Connect & Initialize** – connect to PostgreSQL and create the star schema from `data/init_dw_schema.sql`.
2. **Extract** – read `data/retail.csv` (ISO-8859-1 encoding).
3. **Clean & Normalize** – fill missing values, trim/uppercase text, parse dates, compute `TotalAmount`.
4. **Populate Dimensions** – upsert the conformed dimensions: `dim_date`, `dim_time`, `dim_country`, `dim_customer`, `dim_product`.
5. **Map Surrogate Keys** – join raw transactions to dimension surrogate keys.
6. **Classify & Load Facts** – route transactions into three fact tables and truncate/reload them:
   - `fact_sales` – physical product sales and returns (`InvoiceNo` starting with `C`).
   - `fact_invoice_fees` – shipping, discounts and financial/banking charges.
   - `fact_inventory_adjustments` – zero-price adjustments and write-offs (damaged, lost, found, destroyed, etc.).

## Notes

- Do not commit the `.env` file or real credentials.
- The source data uses `ISO-8859-1` encoding.
- Databases and application configuration are stored in Docker volumes.