# UK Retail Data Warehouse

**[English](README.md)**

**Tài liệu mô tả dự án:** [Google Docs](https://docs.google.com/document/d/1cN4MkCMybb-7pwGvxhJFFwfBIg9ZNLHjYgmyWmQbI0w/edit?tab=t.0)

Dự án xây dựng data warehouse cho dữ liệu bán lẻ trực tuyến tại Vương quốc Anh.
Dữ liệu CSV được làm sạch bằng Python/Pandas, sau đó nạp vào mô hình **multi-fact star schema** trên PostgreSQL.

## Thành phần chính

- PostgreSQL 15: lưu data warehouse và metadata của Airflow.
- Apache Airflow: điều phối pipeline ETL.
- pgAdmin: quản trị PostgreSQL.
- Apache Superset: trực quan hóa dữ liệu và tạo dashboard.
- Python, Pandas và SQLAlchemy: xử lý và nạp dữ liệu.

## Cấu trúc thư mục

```text
data/       Dữ liệu nguồn và SQL khởi tạo schema
dags/       DAG của Airflow
scripts/    Mã nguồn ETL
docs/       Tài liệu thiết kế
```

## Bắt đầu nhanh

Xem hướng dẫn cài đặt và chạy đầy đủ tại [SETUP.md](docs/SETUP.md).

```bash
cp .env.example .env
docker compose up -d --build
```

Sau khi các container khởi động:

- Airflow: http://localhost:8081
- pgAdmin: http://localhost:5051
- Superset: http://localhost:8089

Pipeline Airflow có tên `online_retail_etl_pipeline` và chạy thủ công khi được trigger.

## Tổng quan pipeline ETL

1. **Kết nối & khởi tạo** – kết nối PostgreSQL và tạo star schema từ `data/init_dw_schema.sql`.
2. **Extract** – đọc `data/retail.csv` (encoding ISO-8859-1).
3. **Làm sạch & chuẩn hóa** – điền giá trị thiếu, trim/hoa chuỗi, parse ngày, tính `TotalAmount`.
4. **Nạp chiều** – upsert các bảng chiều: `dim_date`, `dim_time`, `dim_country`, `dim_customer`, `dim_product`.
5. **Ánh xạ surrogate key** – nối dữ liệu giao dịch thô với surrogate key của bảng chiều.
6. **Phân loại & nạp sự kiện** – điều hướng giao dịch vào ba bảng fact và truncate/reload:
   - `fact_sales` – bán hàng và trả hàng sản phẩm vật lý (`InvoiceNo` bắt đầu bằng `C`).
   - `fact_invoice_fees` – phí vận chuyển, chiết khấu và phí ngân hàng/nền tảng.
   - `fact_inventory_adjustments` – điều chỉnh giá bằng 0 và ghi giảm (hư hỏng, thất lạc, tìm thấy, tiêu hủy, v.v.).

## Lưu ý

- Không commit file `.env` hoặc các thông tin đăng nhập thật.
- Dữ liệu nguồn sử dụng encoding `ISO-8859-1`.
- Các database và cấu hình ứng dụng được lưu trong Docker volumes.