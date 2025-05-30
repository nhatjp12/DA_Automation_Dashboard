import json
import re
import pandas as pd
import hashlib
from datetime import datetime

def format_date(date_str):
    # Tìm ngày, tháng, năm trong chuỗi
    match = re.search(r'(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})', date_str)
    if match:
        day, month, year = match.groups()
        return f"{int(day):02d}/{int(month):02d}/{year}"
    # Nếu không khớp, trả về chuỗi gốc
    return date_str.strip()

def clean_customer_name(name):
    # Lấy phần trước dấu ( nếu có
    name = name.split('(')[0].strip()
    
    # Chuẩn hóa tên khách hàng theo mapping
    customer_corrections = {
        'Thu Bàn': 'Thu Bồn',
        'Thu Bôn': 'Thu Bồn',
        'Xanh Xanh': 'Xanh Xanh Hội An',
        'Joly': 'Joly mart',
        'Beba': 'Beba mart',
        'Toàn Cầu': 'Toàn cầu',
        'Greentech': 'Greentech food',
        'Green Tech Food': 'Greentech food',
        'GreenTech Food': 'Greentech food',
        'Danavi': 'Danavi mart',
        'Eco': 'Eco mart',
        'Coop mart': 'Co-op mart',
        'Coopmart': 'Co-op mart',
        'Liên minh': 'Liên minh hợp tác xã',
        'Hội nghị thể thao': 'Trung tâm hội nghị thể thao quốc gia',
        'An Phu': 'An Phú Farm',
        'An Phú': 'An Phú Farm',
        'Vị Ta Mart': 'Vita mart',
        'Vita Mart': 'Vita mart',
        'VitaMart': 'Vita mart',
    }
    
    # Kiểm tra và trả về tên đã chuẩn hóa nếu có trong mapping
    return customer_corrections.get(name, name)

def correct_product_name(name):
    # Xóa phần trong ngoặc đơn () nếu có
    name = re.sub(r'\s*\(.*?\)', '', name).strip()
    
    # Sửa lỗi chính tả phổ biến, có thể mở rộng thêm
    corrections = {
        "Nấm bào ngư": ["Nấm Bào Ngư", "Nấm bào ngư", "Nấm bào ngư xám"],
        "Nấm rơm": ["Nấm rơm", "Nấm Rơm"],
        "Nấm đông cô": ["Nấm đông cô", "Nấm Đông Cô"],
        "Nấm mộc nhĩ": ["Nấm mộc nhĩ", "Nấm Mộc Nhĩ"],
        "Tiêu hột": ["Tiếu hột", "Tiếu Hột", "Tiến bột", "Tiêu hột"],
        # Thêm các tên khác nếu cần
    }
    
    # Kiểm tra từng variant trong corrections
    for correct, variants in corrections.items():
        if name.strip() in variants:  # Sử dụng strip() để so sánh an toàn hơn
            return correct
    return name.strip()

def format_number(val):
    # Loại bỏ dấu chấm, phẩy, lấy 2 số đầu và chuyển về số nguyên
    if isinstance(val, (int, float)):
        val = str(int(val)) # Chuyển số nguyên/thực sang chuỗi, loại bỏ phần thập phân nếu có
    else:
        val = str(val)

    # Loại bỏ dấu chấm, phẩy và khoảng trắng
    cleaned_val = val.replace('.', '').replace(',', '').strip()

    # Kiểm tra nếu không phải là chữ số hoặc rỗng
    if not cleaned_val or not cleaned_val.isdigit():
        # Nếu không thể chuyển đổi sang số, trả về 0 hoặc chuỗi rỗng tùy mục đích sử dụng
        # Hiện tại giữ nguyên logic cũ trả về chuỗi đã làm sạch nếu không phải số
        # hoặc bạn có thể cân nhắc trả về 0 nếu muốn tất cả là số
        return cleaned_val # Hoặc return 0

    # Lấy 2 chữ số đầu tiên
    first_two_digits_str = cleaned_val[:2]

    try:
        # Chuyển 2 chữ số đầu tiên sang số nguyên
        return int(first_two_digits_str)
    except ValueError:
        # Trường hợp này ít xảy ra nếu cleaned_val.isdigit() đúng,
        # nhưng để an toàn, trả về chuỗi đã làm sạch
        return cleaned_val # Hoặc return 0

def format_price(val):
    # Loại bỏ dấu chấm, phẩy, chuyển về số nguyên
    num = format_number(val)
    try:
        # Nếu format_number trả về số nguyên, thì xử lý giá
        if isinstance(num, int):
            # Kiểm tra heuristic giá (ví dụ: nếu nhỏ hơn 10k, nhân 1000)
            if num < 10000:
                num = num * 1000
            return num
        else:
            # Nếu format_number trả về chuỗi (không phải số), trả về nguyên trạng
            return num
    except Exception as e:
        print(f"Lỗi xử lý giá {val}: {e}")
        return val

def generate_order_code(date, customer):
    # Tạo mã đơn hàng từ ngày và tên khách hàng
    combined = f"{date}-{customer}".lower()
    # Tạo hash ngắn để làm mã đơn hàng
    hash_str = hashlib.md5(combined.encode()).hexdigest()[:8]
    return f"DH-{hash_str.upper()}"

def extract_json_blocks(input_path):
    with open(input_path, "r", encoding="utf-8") as fin:
        content = fin.read()
        # Tìm tất cả các block JSON (dạng list)
        blocks = re.findall(r'(\[.*?\])', content, re.DOTALL)
        all_rows = []
        # Dictionary để lưu mã đơn hàng đã tạo
        order_codes = {}
        
        for block in blocks:
            try:
                data = json.loads(block)
                # Lấy thông tin ngày tạo đơn, tên khách hàng từ phần tử đầu tiên
                # Đảm bảo phần tử đầu tiên tồn tại và có các key cần thiết
                if not data or not isinstance(data[0], dict):
                    continue # Bỏ qua block lỗi
                    
                ngay_tao = format_date(data[0].get("Ngày tạo đơn", ""))
                ten_kh = clean_customer_name(data[0].get("Tên khách hàng", ""))
                
                # Tạo hoặc lấy mã đơn hàng dựa trên ngày và tên khách hàng
                order_key = f"{ngay_tao}-{ten_kh}"
                if order_key not in order_codes:
                    order_codes[order_key] = generate_order_code(ngay_tao, ten_kh)
                ma_don = order_codes[order_key]
                
                # Các phần tử tiếp theo là mặt hàng
                # Bắt đầu từ data[1:] để bỏ qua phần tử đầu tiên chứa thông tin đơn hàng
                for item in data[1:]:
                    # Đảm bảo item là dictionary
                    if not isinstance(item, dict):
                        continue # Bỏ qua item lỗi
                        
                    ten_hang = correct_product_name(item.get("Tên mặt hàng", ""))
                    don_vi = item.get("Đơn vị tính", "")
                    
                    # Áp dụng format_number cho Số lượng
                    so_luong = format_number(item.get("Số lượng", ""))
                    
                    # Áp dụng format_price cho Đơn giá
                    don_gia = format_price(item.get("Đơn giá", ""))
                    
                    # Tính lại Thành tiền
                    thanh_tien = ""
                    # Chỉ tính Thành tiền nếu Số lượng và Đơn giá là số nguyên
                    if isinstance(so_luong, int) and isinstance(don_gia, int):
                         thanh_tien = so_luong * don_gia

                    row = {
                        "Mã tạo đơn": ma_don,
                        "Ngày tạo đơn": ngay_tao,
                        "Tên khách hàng": ten_kh,
                        "Tên mặt hàng": ten_hang,
                        "Đơn vị tính": don_vi,
                        "Số lượng": so_luong, # Đã được format
                        "Đơn giá": don_gia,   # Đã được format
                        "Thành tiền": thanh_tien # Đã được tính lại
                    }
                    all_rows.append(row)
            except Exception as e:
                print(f"Lỗi parse block: {e}\nBlock: {block[:200]}...") # In một phần block để debug
        return all_rows

def save_to_excel(rows, output_path):
    if not rows:
        print("Không có dữ liệu để xuất ra Excel")
        return
        
    # Không cần thêm cột STT ở đây nếu đã có trong extract_json_blocks
    # Thêm cột STT trong quá trình tạo dictionary row nếu muốn
    
    df = pd.DataFrame(rows)
    
    # Đảm bảo các cột có đúng thứ tự
    col_order = [
        "Mã tạo đơn", "Ngày tạo đơn", "Tên khách hàng", "Tên mặt hàng", 
        "Đơn vị tính", "Số lượng", "Đơn giá", "Thành tiền"
    ]
    # Chỉ lấy các cột có trong DataFrame và sắp xếp lại
    df = df[[col for col in col_order if col in df.columns]] # Bỏ cột STT

    df.to_excel(output_path, index=False)

if __name__ == "__main__":
    # Thêm cột STT trong quá trình extract
    rows = extract_json_blocks("text_cleaned.txt")
    # Thêm STT sau khi extract nếu muốn
    # for i, row in enumerate(rows):
    #     row["STT"] = i + 1

    save_to_excel(rows, "output.xlsx")
    print("Đã xuất dữ liệu ra file output.xlsx") 