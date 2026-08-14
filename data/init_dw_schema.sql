-- ============================================================================
-- THIẾT KẾ CƠ SỞ DỮ LIỆU KHO DỮ LIỆU BÁN LẺ (RETAIL MULTI-FACT STAR SCHEMA)
-- Database: retail_dw
-- ============================================================================

-- Dọn dẹp schema cũ nếu có (để chạy lại sạch sẽ khi debug/re-init)
DROP TABLE IF EXISTS fact_sales CASCADE;
DROP TABLE IF EXISTS fact_invoice_fees CASCADE;
DROP TABLE IF EXISTS fact_inventory_adjustments CASCADE;
DROP TABLE IF EXISTS dim_customer CASCADE;
DROP TABLE IF EXISTS dim_product CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;
DROP TABLE IF EXISTS dim_time CASCADE;
DROP TABLE IF EXISTS dim_country CASCADE;

-- ----------------------------------------------------------------------------
-- 1. BẢNG CHIỀU (DIMENSION TABLES)
-- ----------------------------------------------------------------------------

-- Chiều Ngày (dim_date)
CREATE TABLE dim_date (
    date_key INT PRIMARY KEY,                       -- Định dạng YYYYMMDD (ví dụ: 20101201)
    date DATE NOT NULL,
    day INT NOT NULL,
    month INT NOT NULL,
    quarter INT NOT NULL,
    year INT NOT NULL,
    day_of_week INT NOT NULL,                       -- 1 (Thứ 2) đến 7 (Chủ nhật)
    is_weekend BOOLEAN NOT NULL
);

-- Chiều Giờ (dim_time)
CREATE TABLE dim_time (
    time_key INT PRIMARY KEY,                       -- Định dạng Hour 0-23 (ví dụ: 8)
    hour INT NOT NULL,
    minute INT NOT NULL,
    time_of_day VARCHAR(20) NOT NULL                -- Sáng, Trưa, Chiều, Tối
);

-- Chiều Quốc gia (dim_country)
CREATE TABLE dim_country (
    country_key SERIAL PRIMARY KEY,
    country_name VARCHAR(100) NOT NULL UNIQUE
);

-- Chiều Khách hàng (dim_customer)
CREATE TABLE dim_customer (
    customer_key SERIAL PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL UNIQUE,       -- Business Key từ CSV (CustomerID thô hoặc '-1')
    country_name VARCHAR(100)                      -- Quốc gia đăng ký ban đầu
);

-- Chiều Sản phẩm (dim_product)
CREATE TABLE dim_product (
    product_key SERIAL PRIMARY KEY,
    stock_code VARCHAR(50) NOT NULL UNIQUE,         -- Business Key từ CSV (ví dụ: '85123A')
    description VARCHAR(255) NOT NULL,              -- Mô tả chuẩn hóa
    is_physical BOOLEAN NOT NULL DEFAULT TRUE       -- TRUE: Sản phẩm vật lý; FALSE: Dịch vụ/Phí
);


-- ----------------------------------------------------------------------------
-- 2. BẢNG SỰ KIỆN (FACT TABLES)
-- ----------------------------------------------------------------------------

-- Fact 1: Bán hàng & Trả hàng sản phẩm vật lý (fact_sales)
CREATE TABLE fact_sales (
    sales_key SERIAL PRIMARY KEY,
    invoice_no VARCHAR(50) NOT NULL,
    customer_key INT NOT NULL REFERENCES dim_customer(customer_key) ON DELETE RESTRICT,
    product_key INT NOT NULL REFERENCES dim_product(product_key) ON DELETE RESTRICT,
    date_key INT NOT NULL REFERENCES dim_date(date_key) ON DELETE RESTRICT,
    time_key INT NOT NULL REFERENCES dim_time(time_key) ON DELETE RESTRICT,
    country_key INT NOT NULL REFERENCES dim_country(country_key) ON DELETE RESTRICT,
    quantity INT NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,           -- quantity * unit_price (âm cho đơn trả hàng)
    is_cancelled BOOLEAN NOT NULL DEFAULT FALSE     -- TRUE nếu đơn trả hàng (InvoiceNo bắt đầu bằng 'C')
);

-- Fact 2: Phí dịch vụ & Chiết khấu cấp Hóa đơn (fact_invoice_fees)
CREATE TABLE fact_invoice_fees (
    fee_key SERIAL PRIMARY KEY,
    invoice_no VARCHAR(50) NOT NULL,
    customer_key INT NOT NULL REFERENCES dim_customer(customer_key) ON DELETE RESTRICT,
    product_key INT NOT NULL REFERENCES dim_product(product_key) ON DELETE RESTRICT,
    date_key INT NOT NULL REFERENCES dim_date(date_key) ON DELETE RESTRICT,
    time_key INT NOT NULL REFERENCES dim_time(time_key) ON DELETE RESTRICT,
    country_key INT NOT NULL REFERENCES dim_country(country_key) ON DELETE RESTRICT,
    quantity INT NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,           -- Âm cho Discount 'D'
    fee_type VARCHAR(50) NOT NULL                   -- 'Shipping', 'Discount', 'Financial Fee'
);

-- Fact 3: Điều chỉnh kho & Hao hụt (fact_inventory_adjustments)
CREATE TABLE fact_inventory_adjustments (
    adj_key SERIAL PRIMARY KEY,
    invoice_no VARCHAR(50) NOT NULL,
    product_key INT NOT NULL REFERENCES dim_product(product_key) ON DELETE RESTRICT,
    date_key INT NOT NULL REFERENCES dim_date(date_key) ON DELETE RESTRICT,
    time_key INT NOT NULL REFERENCES dim_time(time_key) ON DELETE RESTRICT,
    quantity INT NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
    total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.0,
    adjustment_type VARCHAR(100) NOT NULL            -- 'Damaged', 'Lost', 'Found', 'Bad Debt Write-off'
);


-- ----------------------------------------------------------------------------
-- 3. TỐI ƯU HÓA HIỆU NĂNG - CHỈ MỤC (INDEXING STRATEGY)
-- ----------------------------------------------------------------------------

-- Indexes cho fact_sales
CREATE INDEX idx_sales_date ON fact_sales(date_key);
CREATE INDEX idx_sales_time ON fact_sales(time_key);
CREATE INDEX idx_sales_customer ON fact_sales(customer_key);
CREATE INDEX idx_sales_product ON fact_sales(product_key);
CREATE INDEX idx_sales_country ON fact_sales(country_key);
CREATE INDEX idx_sales_invoice ON fact_sales(invoice_no);

-- Indexes cho fact_invoice_fees
CREATE INDEX idx_fees_date ON fact_invoice_fees(date_key);
CREATE INDEX idx_fees_time ON fact_invoice_fees(time_key);
CREATE INDEX idx_fees_customer ON fact_invoice_fees(customer_key);
CREATE INDEX idx_fees_product ON fact_invoice_fees(product_key);
CREATE INDEX idx_fees_invoice ON fact_invoice_fees(invoice_no);

-- Indexes cho fact_inventory_adjustments
CREATE INDEX idx_adj_date ON fact_inventory_adjustments(date_key);
CREATE INDEX idx_adj_time ON fact_inventory_adjustments(time_key);
CREATE INDEX idx_adj_product ON fact_inventory_adjustments(product_key);
CREATE INDEX idx_adj_invoice ON fact_inventory_adjustments(invoice_no);
