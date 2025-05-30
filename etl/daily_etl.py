import pandas as pd
from sqlalchemy import create_engine, text
import urllib
import re

# === 1. Thiết lập kết nối tới SQL Server ===
# (Có thể dùng lại hàm get_engine, hoặc copy vào file này)
def get_engine():
    conn_str = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=DESKTOP-GHAKIAA;"
        "DATABASE=InvoiceDB;"
        "UID=sa;"
        "PWD=123456;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=30;"
        "Encrypt=yes;"
        "Trusted_Connection=yes;"
    )
    params = urllib.parse.quote_plus(conn_str)
    return create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

def process_dimension_tables(engine, df):
    # 1. Process Customer Dimension
    df_customer = df[['Mã khách hàng', 'Tên khách hàng', 'Phân khúc khách hàng']].drop_duplicates()
    df_customer.columns = ['MaKhachHang', 'TenKhachHang', 'PhanKhucKhachHang']
    
    # Get existing customers
    existing_customers = pd.read_sql('SELECT MaKhachHang FROM Dim_Customer', engine)
    # Only insert new customers
    new_customers = df_customer[~df_customer['MaKhachHang'].isin(existing_customers['MaKhachHang'])]
    if not new_customers.empty:
        new_customers.to_sql('Dim_Customer', engine, if_exists='append', index=False)
        print(f"Đã thêm {len(new_customers)} khách hàng mới vào Dim_Customer")

    # 2. Process Product Dimension
    df_product = df[['Mã nhóm hàng', 'Tên nhóm hàng', 'Mã mặt hàng', 'Tên mặt hàng', 'Đơn vị tính']].drop_duplicates()
    df_product.columns = ['MaNhomHang', 'TenNhomHang', 'MaMatHang', 'TenMatHang', 'DonViTinh']
    
    # Filter out products with NULL MaMatHang
    df_product = df_product.dropna(subset=['MaMatHang'])
    
    # Get existing products
    existing_products = pd.read_sql('SELECT MaMatHang, DonViTinh FROM Dim_Product', engine)
    # Only insert new products
    new_products = df_product[~df_product[['MaMatHang', 'DonViTinh']].apply(tuple, axis=1).isin(
        existing_products[['MaMatHang', 'DonViTinh']].apply(tuple, axis=1)
    )]
    if not new_products.empty:
        new_products.to_sql('Dim_Product', engine, if_exists='append', index=False)
        print(f"Đã thêm {len(new_products)} sản phẩm mới vào Dim_Product")

    # 3. Process Date Dimension
    df_date = df[['Ngày tạo đơn']].drop_duplicates()
    df_date['Ngay'] = df_date['Ngày tạo đơn'].dt.day
    df_date['Thang'] = df_date['Ngày tạo đơn'].dt.month
    df_date['Nam'] = df_date['Ngày tạo đơn'].dt.year
    df_date['Quy'] = df_date['Ngày tạo đơn'].dt.quarter
    df_date = df_date.rename(columns={'Ngày tạo đơn': 'NgayTaoDon'})
    
    # Get existing dates and convert to datetime
    existing_dates = pd.read_sql('SELECT NgayTaoDon FROM Dim_Date', engine)
    existing_dates['NgayTaoDon'] = pd.to_datetime(existing_dates['NgayTaoDon'])
    
    # Only insert new dates
    new_dates = df_date[~df_date['NgayTaoDon'].isin(existing_dates['NgayTaoDon'])]
    if not new_dates.empty:
        new_dates.to_sql('Dim_Date', engine, if_exists='append', index=False)
        print(f"Đã thêm {len(new_dates)} ngày mới vào Dim_Date")

    return df_customer, df_product, df_date

def process_fact_table(engine, df, df_customer, df_product, df_date):
    # Create fact table with foreign keys
    df_fact = df.merge(df_customer[['MaKhachHang']], left_on='Mã khách hàng', right_on='MaKhachHang', how='left')
    df_fact = df_fact.merge(df_product[['MaMatHang', 'DonViTinh']], left_on='Mã mặt hàng', right_on='MaMatHang', how='left')
    df_fact = df_fact.merge(df_date[['NgayTaoDon']], left_on='Ngày tạo đơn', right_on='NgayTaoDon', how='left')

    # Select and rename columns for fact table
    df_fact = df_fact[[
        'Mã tạo đơn',
        'MaKhachHang',
        'MaMatHang',
        'DonViTinh',
        'NgayTaoDon',
        'Số lượng',
        'Đơn giá',
        'Thành tiền'
    ]]

    # Rename columns to match database schema
    df_fact.columns = [
        'MaTaoDon',
        'MaKhachHang',
        'MaMatHang',
        'DonViTinh',
        'NgayTaoDon',
        'SoLuong',
        'DonGia',
        'ThanhTien'
    ]

    # Insert into fact table
    df_fact.to_sql('Fact_Order', engine, if_exists='append', index=False)
    print(f"Đã thêm {len(df_fact)} dòng vào Fact_Order")

def main_daily():
    engine = get_engine()

    try:
        # 1. Đọc file processed_output.xlsx
        df = pd.read_excel('processed_output.xlsx')
        
        # Xử lý cột ngày tháng
        df['Ngày tạo đơn'] = pd.to_datetime(df['Ngày tạo đơn'], format='%d/%m/%Y', errors='coerce')
        
        # Loại bỏ các dòng có ngày tháng không hợp lệ
        df = df.dropna(subset=['Ngày tạo đơn'])
        
        if len(df) == 0:
            raise ValueError("Không có dữ liệu hợp lệ sau khi xử lý ngày tháng")

        # 2. Dedupe trong file mới (theo Ngày tạo đơn + Tên khách hàng)
        df = df.drop_duplicates(
            subset=['Ngày tạo đơn', 'Tên khách hàng'],
            keep='first'
        )

        print(f"Đã đọc file processed_output.xlsx với {len(df)} dòng")

        # 3. Process dimension tables
        df_customer, df_product, df_date = process_dimension_tables(engine, df)

        # 4. Process fact table
        process_fact_table(engine, df, df_customer, df_product, df_date)

        print(f"Đã ETL {len(df)} dòng từ processed_output.xlsx")
        print("ETL hoàn tất thành công!")

    except Exception as e:
        print(f"Lỗi trong quá trình ETL: {str(e)}")

if __name__ == "__main__":
    main_daily()