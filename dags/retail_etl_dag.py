import sys
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# Thêm thư mục làm việc của Airflow vào PYTHONPATH để import module scripts
sys.path.append('/opt/airflow')

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 8, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def trigger_etl():
    # Gọi hàm run_etl từ scripts.etl_pipeline
    from scripts.etl_pipeline import run_etl
    
    csv_path = '/opt/airflow/data/retail.csv'
    run_etl(csv_path)

with DAG(
    'online_retail_etl_pipeline',
    default_args=default_args,
    description='Pipeline ETL chạy làm sạch và nạp dữ liệu bán lẻ thô vào Star Schema',
    schedule_interval=None,  # Chạy on-demand (vì dữ liệu lịch sử tĩnh)
    catchup=False,
    tags=['retail', 'dw', 'etl'],
) as dag:

    run_etl_task = PythonOperator(
        task_id='run_retail_etl_pipeline',
        python_callable=trigger_etl,
    )

    run_etl_task
