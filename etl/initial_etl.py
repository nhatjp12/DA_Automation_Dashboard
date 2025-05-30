import pandas as pd
from sqlalchemy import create_engine, text
import urllib
import os

# === 1. Thiết lập kết nối tới SQL Server ===
def get_engine():
    """Trả về SQLAlchemy engine kết nối qua ODBC Driver 18"""
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

# === 2. Tạo các bảng theo lược đồ hình sao ===
def create_star_schema():
    try:
        engine = get_engine()
        
        # Xóa các bảng cũ nếu tồn tại
        with engine.connect() as conn:
            conn.execute(text("IF OBJECT_ID('Fact_Order', 'U') IS NOT NULL DROP TABLE Fact_Order"))
            conn.execute(text("IF OBJECT_ID('Dim_Customer', 'U') IS NOT NULL DROP TABLE Dim_Customer"))
            conn.execute(text("IF OBJECT_ID('Dim_Product', 'U') IS NOT NULL DROP TABLE Dim_Product"))
            conn.execute(text("IF OBJECT_ID('Dim_Date', 'U') IS NOT NULL DROP TABLE Dim_Date"))
            conn.commit()
            print("Đã xóa các bảng cũ")
        
        # Tạo bảng Dim_Customer
        create_dim_customer = """
        CREATE TABLE Dim_Customer (
            MaKhachHang NVARCHAR(10) PRIMARY KEY,
            TenKhachHang NVARCHAR(100),
            PhanKhucKhachHang NVARCHAR(50)
        )
        """
        
        # Tạo bảng Dim_Product với composite key
        create_dim_product = """
        CREATE TABLE Dim_Product (
            MaMatHang NVARCHAR(10),
            TenMatHang NVARCHAR(100),
            MaNhomHang NVARCHAR(10),
            TenNhomHang NVARCHAR(100),
            DonViTinh NVARCHAR(20),
            PRIMARY KEY (MaMatHang, DonViTinh)
        )
        """
        
        # Tạo bảng Dim_Date
        create_dim_date = """
        CREATE TABLE Dim_Date (
            NgayTaoDon DATE PRIMARY KEY,
            Nam INT,
            Thang INT,
            Ngay INT,
            Quy INT
        )
        """
        
        # Tạo bảng Fact_Order
        create_fact_order = """
        CREATE TABLE Fact_Order (
            MaChiTietDonHang INT IDENTITY(1,1) PRIMARY KEY,
            MaTaoDon NVARCHAR(20),
            MaKhachHang NVARCHAR(10) FOREIGN KEY REFERENCES Dim_Customer(MaKhachHang),
            MaMatHang NVARCHAR(10),
            DonViTinh NVARCHAR(20),
            NgayTaoDon DATE FOREIGN KEY REFERENCES Dim_Date(NgayTaoDon),
            SoLuong INT,
            DonGia DECIMAL(18,2),
            ThanhTien DECIMAL(18,2),
            FOREIGN KEY (MaMatHang, DonViTinh) REFERENCES Dim_Product(MaMatHang, DonViTinh)
        )
        """
        
        # Thực thi các câu lệnh tạo bảng
        with engine.connect() as conn:
            conn.execute(text(create_dim_customer))
            conn.execute(text(create_dim_product))
            conn.execute(text(create_dim_date))
            conn.execute(text(create_fact_order))
            conn.commit()
            print("Đã tạo xong các bảng theo lược đồ hình sao")
    except Exception as e:
        print(f"Lỗi khi tạo lược đồ hình sao: {str(e)}")
        raise

# === 3. ETL dữ liệu ===
def etl_data():
    try:
        # Đọc file Excel
        file_path = os.path.join(os.path.dirname(__file__), 'Kimthanh_data.xlsx')
        print(f"Đang đọc file: {file_path}")
        
        # Kiểm tra file tồn tại
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Không tìm thấy file {file_path}. Vui lòng đặt file Kimthanh_data.xlsx vào thư mục etl")
            
        df = pd.read_excel(file_path, parse_dates=['Ngày tạo đơn'])
        
        # In ra tên các cột để debug
        print("\nCác cột trong file Excel:")
        for col in df.columns:
            print(f"- {col}")
        
        # Chuẩn hóa dữ liệu
        df['Ngày tạo đơn'] = pd.to_datetime(df['Ngày tạo đơn'], dayfirst=True)
        
        engine = get_engine()
        
        # 1. ETL Dim_Customer
        print("\nĐang ETL bảng Dim_Customer...")
        customers = df[['Mã khách hàng', 'Tên khách hàng', 'Phân khúc khách hàng']].drop_duplicates().copy()
        customers.columns = ['MaKhachHang', 'TenKhachHang', 'PhanKhucKhachHang']
        customers.to_sql('Dim_Customer', engine, if_exists='append', index=False)
        print(f"Đã ETL {len(customers)} bản ghi vào bảng Dim_Customer")
        
        # 2. ETL Dim_Product
        print("\nĐang ETL bảng Dim_Product...")
        products = df[['Mã mặt hàng', 'Tên mặt hàng', 'Mã nhóm hàng', 'Tên nhóm hàng', 'Đơn vị tính']].drop_duplicates().copy()
        products.columns = ['MaMatHang', 'TenMatHang', 'MaNhomHang', 'TenNhomHang', 'DonViTinh']
        products.to_sql('Dim_Product', engine, if_exists='append', index=False)
        print(f"Đã ETL {len(products)} bản ghi vào bảng Dim_Product")
        
        # 3. ETL Dim_Date
        print("\nĐang ETL bảng Dim_Date...")
        # Tạo DataFrame cho Dim_Date từ các ngày duy nhất
        unique_dates = df['Ngày tạo đơn'].dt.date.unique()
        dates_data = []
        for date in unique_dates:
            dates_data.append({
                'NgayTaoDon': date,
                'Nam': date.year,
                'Thang': date.month,
                'Ngay': date.day,
                'Quy': (date.month - 1) // 3 + 1
            })
        dates = pd.DataFrame(dates_data)
        dates.to_sql('Dim_Date', engine, if_exists='append', index=False)
        print(f"Đã ETL {len(dates)} bản ghi vào bảng Dim_Date")
        
        # 4. ETL Fact_Order
        print("\nĐang ETL bảng Fact_Order...")
        fact_orders = df[[
            'Mã tạo đơn', 'Mã khách hàng', 'Mã mặt hàng', 'Đơn vị tính', 'Ngày tạo đơn',
            'Số lượng', 'Đơn giá', 'Thành tiền'
        ]].copy()
        
        fact_orders.columns = [
            'MaTaoDon', 'MaKhachHang', 'MaMatHang', 'DonViTinh', 'NgayTaoDon',
            'SoLuong', 'DonGia', 'ThanhTien'
        ]
        
        # Chuyển đổi kiểu dữ liệu sử dụng .loc
        fact_orders.loc[:, 'NgayTaoDon'] = fact_orders['Ngày tạo đơn'].dt.date
        fact_orders.loc[:, 'SoLuong'] = fact_orders['SoLuong'].astype(int)
        fact_orders.loc[:, 'DonGia'] = fact_orders['DonGia'].astype(float)
        fact_orders.loc[:, 'ThanhTien'] = fact_orders['ThanhTien'].astype(float)
        
        fact_orders.to_sql('Fact_Order', engine, if_exists='append', index=False)
        print(f"Đã ETL {len(fact_orders)} bản ghi vào bảng Fact_Order")
        print("\nĐã hoàn thành ETL dữ liệu!")
    except Exception as e:
        print(f"\nLỗi khi ETL dữ liệu: {str(e)}")
        raise

def main():
    try:
        print("Bắt đầu ETL dữ liệu...")
        create_star_schema()
        etl_data()
        print("Hoàn thành ETL dữ liệu!")
    except Exception as e:
        print(f"Lỗi: {str(e)}")
        raise

if __name__ == "__main__":
    main()