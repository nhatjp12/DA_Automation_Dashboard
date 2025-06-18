Link youtube Demo: https://www.youtube.com/watch?v=PHtZdTiPV94

# Quy trình xử lý Prompt người dùng cho Dashboard bán hàng

File này mô tả luồng xử lý khi người dùng nhập một yêu cầu phân tích dữ liệu bằng ngôn ngữ tự nhiên (prompt) trong ứng dụng Dashboard bán hàng.

Ví dụ Prompt: "cơ cấu sản phẩm theo doanh thu"

## 1. Người dùng nhập Prompt

Người dùng nhập câu hỏi của họ (ví dụ: "cơ cấu sản phẩm theo doanh thu") vào ô nhập liệu trên giao diện người dùng (có thể là ứng dụng Streamlit hoặc giao diện frontend riêng).

## 2. Gửi Prompt đến Backend/API Service

- Prompt từ giao diện người dùng được gửi đến tầng backend.
- Cụ thể, yêu cầu được xử lý bởi file `app/services/gemini_service.py`.
- File này chịu trách nhiệm gọi đến một API của mô hình ngôn ngữ lớn (ví dụ: API của Gemini) để xử lý prompt.

## 3. API xử lý Prompt và tạo SQL Query

- API của mô hình ngôn ngữ nhận prompt từ backend.
- API này đã được cung cấp thông tin về cấu trúc cơ sở dữ liệu hiện tại (lược đồ hình sao - Star Schema) thông qua prompt hệ thống hoặc cấu hình nội bộ. Cấu trúc này bao gồm các bảng:
    - `Fact_Order` (Thông tin đơn hàng, các cột như MaTaoDon, MaKhachHang, MaMatHang, DonViTinh, NgayTaoDon, SoLuong, DonGia, ThanhTien)
    - `Dim_Product` (Thông tin sản phẩm, các cột như MaMatHang, TenMatHang, MaNhomHang, TenNhomHang, DonViTinh)
    - `Dim_Customer` (Thông tin khách hàng, các cột như MaKhachHang, TenKhachHang, PhanKhucKhachHang)
    - `Dim_Date` (Thông tin thời gian, các cột như NgayTaoDon, Nam, Thang, Ngay, Quy)
    - API cũng hiểu các mối quan hệ (JOIN) giữa các bảng này (ví dụ: Fact_Order JOIN Dim_Product ON Fact_Order.MaMatHang = Dim_Product.MaMatHang AND Fact_Order.DonViTinh = Dim_Product.DonViTinh).
- Dựa trên prompt của người dùng và hiểu biết về cấu trúc DB, API sẽ tạo ra một câu lệnh SQL phù hợp để truy vấn dữ liệu cần thiết từ cơ sở dữ liệu SQL Server.
- Ví dụ, với prompt "cơ cấu sản phẩm theo doanh thu", API sẽ tạo ra câu truy vấn tương tự như:

```sql
SELECT 
    p.TenMatHang,
    SUM(f.ThanhTien) AS DoanhThu
FROM 
    Fact_Order f
    JOIN Dim_Product p ON f.MaMatHang = p.MaMatHang AND f.DonViTinh = p.DonViTinh
GROUP BY 
    p.TenMatHang
ORDER BY 
    DoanhThu DESC
```

- API trả về kết quả ở dạng JSON, thường bao gồm:
    - `sql`: Câu lệnh SQL đã tạo.
    - `chart_type`: Gợi ý loại biểu đồ phù hợp để hiển thị kết quả (ví dụ: "bar", "pie").
    - (Có thể có trường `error` nếu có lỗi).

## 4. Backend thực thi SQL Query

- File `app/services/gemini_service.py` nhận kết quả JSON từ API.
- Nó trích xuất câu lệnh SQL.
- Nó gọi hàm trong file `app/services/db_service.py` để thực thi câu lệnh SQL này trên cơ sở dữ liệu SQL Server.
- File `app/services/db_service.py` chứa logic kết nối cơ sở dữ liệu (sử dụng SQLAlchemy và PyODBC) với thông tin cấu hình như tên server (`DESKTOP-GHAKIAA`), database (`InvoiceDB`), UID, PWD, v.v.
- Kết quả truy vấn từ cơ sở dữ liệu (dữ liệu dạng bảng) được trả về cho `app/services/gemini_service.py`.

## 5. Xử lý và hiển thị dữ liệu trên giao diện

- Dữ liệu nhận được từ database và `chart_type` từ API được truyền lại cho giao diện người dùng.
- **Nếu sử dụng Streamlit (`app/streamlit_app.py`):**
    - Dữ liệu được chuyển đổi thành DataFrame của Pandas.
    - Streamlit sử dụng thư viện `plotly.express` để tạo đối tượng biểu đồ dựa trên dữ liệu và `chart_type`.
    - Biểu đồ được hiển thị trực tiếp trong ứng dụng Streamlit bằng `st.plotly_chart()`.
- **Nếu sử dụng giao diện Frontend riêng (React):**
    - Dữ liệu và `chart_type` được gửi đến component render biểu đồ (ví dụ: `frontend/src/components/ChartRenderer.jsx`).
    - Component này sử dụng thư viện `chart.js` (hoặc `react-chartjs-2`) để vẽ loại biểu đồ tương ứng với dữ liệu nhận được.

## Tóm tắt vai trò các File chính

- `app/streamlit_app.py`: Giao diện người dùng (Streamlit), nhận prompt, gọi backend, hiển thị kết quả dạng bảng và biểu đồ (dùng Plotly).
- `app/services/gemini_service.py`: Tầng trung gian backend, nhận prompt từ UI, gọi API mô hình ngôn ngữ, nhận SQL và chart_type, gọi `db_service` để chạy SQL.
- `app/services/db_service.py`: Chứa logic kết nối và thực thi truy vấn trên cơ sở dữ liệu SQL Server.
- `etl/initial_etl.py` / `etl/daily_etl.py`: Các script ETL ban đầu và hàng ngày, chịu trách nhiệm đọc dữ liệu nguồn (Excel) và load vào cơ sở dữ liệu SQL Server theo lược đồ hình sao. **Các file này không tham gia trực tiếp vào quy trình xử lý prompt sau khi dữ liệu đã được load.**
- `frontend/src/components/ChartRenderer.jsx`: Component frontend (React) chịu trách nhiệm vẽ biểu đồ trên giao diện web sử dụng Chart.js (nếu có giao diện frontend riêng).

Quy trình này đảm bảo rằng yêu cầu phân tích dữ liệu bằng ngôn ngữ tự nhiên của người dùng được chuyển đổi thành truy vấn SQL chính xác dựa trên cấu trúc cơ sở dữ liệu hiện tại và kết quả được hiển thị trực quan dưới dạng biểu đồ. 
