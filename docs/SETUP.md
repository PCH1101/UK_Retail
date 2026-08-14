# Hướng dẫn cài đặt

## Yêu cầu

- Docker Desktop có hỗ trợ Docker Compose.
- Git, nếu clone dự án từ repository.

## 1. Tạo file môi trường

Từ thư mục gốc dự án, tạo `.env` từ file mẫu:

```bash
cp .env.example .env
```

Trên Windows PowerShell có thể dùng:

```powershell
Copy-Item .env.example .env
```

Mở `.env` và thay các giá trị `change-me`, đặc biệt là mật khẩu và `SUPERSET_SECRET_KEY`.

## 2. Khởi động hệ thống

```bash
docker compose up -d --build
```

Kiểm tra trạng thái các service:

```bash
docker compose ps
```

Lần khởi động đầu tiên có thể mất vài phút vì hệ thống cần tạo database và tài khoản quản trị. Schema data warehouse sẽ được tạo khi ETL chạy.

## 3. Chạy pipeline ETL

Kích hoạt DAG từ Airflow CLI:

```bash
docker compose exec airflow-webserver airflow dags trigger online_retail_etl_pipeline
```

Theo dõi log của task nếu cần:

```bash
docker compose logs -f airflow-scheduler
```

Hoặc chạy ETL trực tiếp trong container Airflow:

```bash
docker compose exec airflow-webserver \
  python /opt/airflow/scripts/etl_pipeline.py /opt/airflow/data/retail.csv
```

## 4. Truy cập dịch vụ

Các cổng mặc định lấy từ `.env.example`:

| Dịch vụ | URL |
| --- | --- |
| Airflow | http://localhost:8081 |
| pgAdmin | http://localhost:5051 |
| Superset | http://localhost:8089 |
| PostgreSQL | `localhost:5433` |

Thông tin đăng nhập được khai báo trong `.env` qua các biến `AIRFLOW_ADMIN_*`, `PGADMIN_DEFAULT_*` và `SUPERSET_ADMIN_*`.

## 5. Dừng và xóa hệ thống

Dừng container nhưng giữ dữ liệu:

```bash
docker compose down
```

Dừng container và xóa cả Docker volumes:

```bash
docker compose down -v
```

Lệnh `down -v` sẽ xóa dữ liệu PostgreSQL và cấu hình Superset đã lưu.
