import requests
import json
import re
import os
import ast

# Add your Gemini API URL and potentially API Key here
GEMINI_API_KEY = "AIzaSyD6qTOjr_6f8ZEpzQWAKUS385qY4ul-e0E"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")


def analyze_prompt(prompt, current_df_columns=None):
    """
    Phân tích prompt người dùng, tạo SQL query và/hoặc gợi ý loại biểu đồ bằng cách gọi API.
    Args:
        prompt (str): Yêu cầu của người dùng.
        current_df_columns (list/None): Danh sách tên cột của DataFrame hiện có (nếu đang ở giai đoạn chỉnh sửa biểu đồ).
    Returns:
        dict: Kết quả dạng JSON chứa 'action', 'sql', 'chart_type', 'x_col', 'y_col', 'color_col' hoặc 'error'.
    """
    db_schema_description = (
        "Cơ sở dữ liệu có lược đồ hình sao gồm các bảng sau (tên cột và kiểu dữ liệu):\n"
        "- Fact_Order: MaTaoDon (NVARCHAR), MaKhachHang (NVARCHAR, FK to Dim_Customer), MaMatHang (NVARCHAR, FK to Dim_Product), DonViTinh (NVARCHAR, FK to Dim_Product), NgayTaoDon (DATE, FK to Dim_Date), SoLuong (INT), DonGia (DECIMAL), ThanhTien (DECIMAL).\n"
        "- Dim_Product: MaMatHang (NVARCHAR), TenMatHang (NVARCHAR), MaNhomHang (NVARCHAR), TenNhomHang (NVARCHAR), DonViTinh (NVARCHAR). Primary Key: (MaMatHang, DonViTinh).\n"
        "- Dim_Customer: MaKhachHang (NVARCHAR), TenKhachHang (NVARCHAR), PhanKhucKhachHang (NVARCHAR). Primary Key: MaKhachHang.\n"
        "- Dim_Date: NgayTaoDon (DATE), Nam (INT), Thang (INT), Ngay (INT), Quy (INT). Primary Key: NgayTaoDon.\n"
        "Mối quan hệ: Fact_Order JOIN Dim_Product ON Fact_Order.MaMatHang = Dim_Product.MaMatHang AND Fact_Order.DonViTinh = Dim_Product.DonViTinh; Fact_Order JOIN Dim_Customer ON Fact_Order.MaKhachHang = Dim_Customer.MaKhachHang; Fact_Order JOIN Dim_Date ON Fact_Order.NgayTaoDon = Dim_Date.NgayTaoDon.\n"
        "Sử dụng tên cột tiếng Việt/không dấu như mô tả."
    )

    instruction_description = (
        "Bạn là trợ lý phân tích dữ liệu và vẽ biểu đồ cho Dashboard bán hàng. "
        "Dựa trên yêu cầu của người dùng, bạn cần xác định hành động phù hợp và tạo ra kết quả JSON theo định dạng sau: "
        "{ 'action': '<loại hành động>', 'sql': '<câu lệnh sql>', 'chart_type': '<loại biểu đồ>', 'x_col': '<tên cột cho trục X>', 'y_col': '<tên cột cho trục Y>', 'color_col': '<tên cột để phân nhóm màu>' }.\n"
        "Các loại hành động ('action') và cách sử dụng:\n"
        "- 'query_and_chart': Người dùng yêu cầu phân tích dữ liệu mới VÀ muốn xem cả bảng dữ liệu lẫn biểu đồ. Tạo SQL query. Trả về 'chart_type' (ví dụ: 'bar', 'line', 'pie', 'scatter', 'stacked bar', 'area', 'combo') và nếu có thể, gợi ý 'x_col', 'y_col', 'color_col'.\n"
        "- 'query_only': Người dùng chỉ yêu cầu phân tích dữ liệu mới VÀ CHỈ muốn xem bảng dữ liệu. Tạo SQL query. 'chart_type' và các trường *_col là rỗng hoặc không có.\n"
        "- 'modify_chart': Người dùng đã có dữ liệu hiện tại trong DataFrame `df`. Khi người dùng chỉ yêu cầu vẽ biểu đồ HOẶC chỉnh sửa biểu đồ hiện có từ dữ liệu này mà KHÔNG cần truy vấn dữ liệu mới, hãy chọn action này. 'sql' là rỗng. Chỉ trả về 'chart_type' phù hợp và nếu có thể, gợi ý 'x_col', 'y_col', 'color_col' để hàm auto_plot vẽ lại.\n"
        "- 'explain': Yêu cầu không rõ ràng hoặc mang tính trò chuyện, không liên quan đến phân tích dữ liệu hoặc biểu đồ. 'sql', 'chart_type' và các trường *_col là rỗng hoặc không có.\n"
        "Lưu ý quan trọng:\n"
        "- KHÔNG BAO GIỜ sinh code Python. Chỉ trả về JSON chứa các trường đã định nghĩa.\n"
        "- Luôn trả về JSON hợp lệ và chỉ JSON. Không có text nào khác ngoài JSON.\n"
        "- Bạn phải sinh truy vấn SQL Server, không dùng hàm của SQLite/MySQL/PostgreSQL. Để lấy tháng từ ngày, dùng hàm MONTH() hoặc cột Thang trong Dim_Date. Để lấy năm, dùng YEAR() hoặc cột Nam.\n"
        "- Với 'chart_type', hãy chọn từ danh sách: 'bar', 'line', 'pie', 'scatter', 'stacked bar', 'area', 'combo'.\n"
        "- 'x_col' thường là cột danh mục hoặc thời gian. 'y_col' thường là cột số liệu. 'color_col' là cột danh mục để phân nhóm.\n"
        "- Nếu không chắc chắn về 'x_col', 'y_col', 'color_col', có thể bỏ qua chúng hoặc trả về giá trị null/rỗng cho các trường đó.\n"
    )

    current_data_description = ""
    if current_df_columns is not None and isinstance(current_df_columns, list) and current_df_columns:
        current_data_description = (
            f"Hiện tại, người dùng đang xem dữ liệu đã được truy vấn, có sẵn trong Pandas DataFrame tên `df` với các cột sau: {current_df_columns}. "
            "Nếu yêu cầu của người dùng liên quan đến việc hiển thị hoặc chỉnh sửa biểu đồ dựa trên dữ liệu này mà KHÔNG cần truy vấn mới, hãy chọn action 'modify_chart', 'sql' là rỗng, và chỉ trả về 'chart_type' (và tùy chọn 'x_col', 'y_col', 'color_col') phù hợp.\n"
        )
    elif current_df_columns is not None:
         print(f"Warning: unexpected type/value for current_df_columns: {type(current_df_columns)}. Value: {current_df_columns}")

    system_prompt = f"""
{db_schema_description}
{current_data_description}
{instruction_description}

Yêu cầu của người dùng: "{prompt}"

Output JSON:
"""
    print(f"DEBUG: Sending prompt to API:\n{system_prompt}")

    try:
        api_payload = {
            "contents": [{"parts": [{"text": system_prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1024,
            }
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # It's good practice to set a timeout for network requests
        response = requests.post(
            GEMINI_API_URL, 
            params={"key": GEMINI_API_KEY},
            headers=headers,
            json=api_payload, 
            timeout=60
        )
        response.raise_for_status() # Will raise an HTTPError for bad responses (4XX or 5XX)
        
        resp_json = response.json()
        
        result_text = ""
        try:
            # Accessing the text part correctly based on Gemini API structure
            if resp_json.get("candidates") and resp_json["candidates"][0].get("content") and resp_json["candidates"][0]["content"].get("parts"):
                 result_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
            else:
                # Fallback or error if structure is not as expected
                generated_text_parts = []
                if resp_json.get("candidates"):
                    for candidate in resp_json["candidates"]:
                        if candidate.get("content") and candidate["content"].get("parts"):
                            for part in candidate["content"]["parts"]:
                                if "text" in part:
                                    generated_text_parts.append(part["text"])
                if generated_text_parts:
                    result_text = "".join(generated_text_parts)
                else:
                    return {"action": "error", "error": f"Không tìm thấy nội dung text trong response Gemini. Response: {json.dumps(resp_json)}"}

        except Exception as e:
            return {"action": "error", "error": f"Lỗi khi trích xuất text từ response Gemini: {str(e)}. Response: {json.dumps(resp_json)}"}

        # Clean markdown code block fences if present
        if result_text.strip().startswith("```json"):
            result_text = result_text.strip()[7:]
            if result_text.strip().endswith("```"):
                result_text = result_text.strip()[:-3]
        elif result_text.strip().startswith("```"): # More generic ``` removal
             result_text = result_text.strip()[3:]
             if result_text.strip().endswith("```"):
                result_text = result_text.strip()[:-3]
        
        result_text = result_text.strip()
        print(f"DEBUG: Raw text from API after cleaning:\n{result_text}")

        try:
            result = json.loads(result_text)
        except json.JSONDecodeError as e_json:
            # If json.loads fails, try ast.literal_eval as a fallback for Python-like dict strings
            try:
                result = ast.literal_eval(result_text)
            except Exception as e_ast:
                print(f"ERROR: Both json.loads and ast.literal_eval failed. JSON Error: {e_json}. AST Error: {e_ast}")
                return {"action": "error", "error": f"Lỗi parse JSON/dict từ API. JSON Error: {e_json}, AST Error: {e_ast}. Nội dung trả về: {result_text}"}
        
        if not isinstance(result, dict):
             return {"action": "error", "error": f"API không trả về một dictionary hợp lệ. Nội dung: {result_text}"}

        if "action" not in result:
            print(f"ERROR: API response missing 'action' field. Raw text: {result_text}")
            return {"action": "error", "error": f"API trả về JSON thiếu trường 'action'. Nội dung: {result_text}"}

        # Ensure expected fields are present or default to None/empty string
        result['sql'] = result.get('sql', '')
        result['chart_type'] = result.get('chart_type', None)
        result['x_col'] = result.get('x_col', None)
        result['y_col'] = result.get('y_col', None)
        result['color_col'] = result.get('color_col', None)
        # Remove python_code if it accidentally comes
        if 'python_code' in result:
            del result['python_code']


        print(f"DEBUG: Parsed API result:\n{result}")
        return result

    except requests.exceptions.RequestException as e_req: # Catch network errors
        print(f"ERROR: Lỗi kết nối tới Gemini API: {e_req}")
        return {"action": "error", "error": f"Lỗi kết nối tới Gemini API: {str(e_req)}"}
    except Exception as e:
        print(f"ERROR: Lỗi không xác định trong quá trình xử lý API: {e}")
        import traceback
        traceback.print_exc()
        return {"action": "error", "error": f"Lỗi không xác định trong quá trình xử lý Gemini API: {str(e)}"}

# Example of how to use analyze_prompt locally for testing
if __name__ == '__main__':
     # Ensure GEMINI_API_KEY is set as an environment variable before running
     if not GEMINI_API_KEY:
         print("Please set the GEMINI_API_KEY environment variable to run tests.")
     else:
        print("--- Testing query_and_chart ---")
        result1 = analyze_prompt("cơ cấu sản phẩm theo doanh thu dạng biểu đồ tròn")
        print(f"Result 1: {result1}")
        print("Expected: action='query_and_chart', sql with TenMatHang, DoanhThu, chart_type='pie', x_col='TenMatHang', y_col='DoanhThu'")
        print("\n")

        print("--- Testing modify_chart ---")
        result2 = analyze_prompt("đổi sang biểu đồ cột", current_df_columns=['TenMatHang', 'DoanhThu', 'Nam'])
        print(f"Result 2: {result2}")
        print("Expected: action='modify_chart', sql='', chart_type='bar', possibly x_col, y_col suggestions")
        print("\n")

        print("--- Testing query_only ---")
        result3 = analyze_prompt("cho xem bảng doanh thu theo khách hàng chi tiết")
        print(f"Result 3: {result3}")
        print("Expected: action='query_only', sql with customer details and revenue, chart_type=None")
        print("\n")

        print("--- Testing explain ---")
        result4 = analyze_prompt("cảm ơn bạn nhiều nhé")
        print(f"Result 4: {result4}")
        print("Expected: action='explain'")
        print("\n")

        print("--- Testing stacked bar chart request ---")
        result5 = analyze_prompt("vẽ biểu đồ cột chồng doanh thu theo tháng và theo năm")
        print(f"Result 5: {result5}")
        print("Expected: action='query_and_chart', sql for monthly revenue by year, chart_type='stacked bar', x_col='Thang', y_col='DoanhThu', color_col='Nam'")
