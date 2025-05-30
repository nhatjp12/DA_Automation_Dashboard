import pandas as pd
import io
import re

# Define valid customer segments
VALID_CUSTOMER_SEGMENTS = {'Cửa hàng', 'Siêu thị', 'Khác'}

# --- Customer Mapping (derived from mota.txt) ---
customer_mapping = {
    'Xanh Xanh Hội An': {'Mã khách hàng': 'CU001', 'Phân khúc khách hàng': 'Cửa hàng'},
    'Joly mart': {'Mã khách hàng': 'CU002', 'Phân khúc khách hàng': 'Cửa hàng'},
    'Beba mart': {'Mã khách hàng': 'CU003', 'Phân khúc khách hàng': 'Cửa hàng'},
    'Thu Bồn': {'Mã khách hàng': 'CU004', 'Phân khúc khách hàng': 'Cửa hàng'},
    'Toàn cầu': {'Mã khách hàng': 'CU005', 'Phân khúc khách hàng': 'Cửa hàng'},
    'Greentech food': {'Mã khách hàng': 'CU006', 'Phân khúc khách hàng': 'Cửa hàng'},
    'Danavi mart': {'Mã khách hàng': 'CU007', 'Phân khúc khách hàng': 'Cửa hàng'},
    'Eco mart': {'Mã khách hàng': 'CU008', 'Phân khúc khách hàng': 'Cửa hàng'},
    'Co-op mart': {'Mã khách hàng': 'CU009', 'Phân khúc khách hàng': 'Siêu thị'},
    'Liên minh hợp tác xã': {'Mã khách hàng': 'CU010', 'Phân khúc khách hàng': 'Khác'},
    'Trung tâm hội nghị thể thao quốc gia': {'Mã khách hàng': 'CU011', 'Phân khúc khách hàng': 'Khác'},
    'Vita mart': {'Mã khách hàng': 'CU012', 'Phân khúc khách hàng': 'Cửa hàng'},
    'An Phú Farm': {'Mã khách hàng': 'CU013', 'Phân khúc khách hàng': 'Cửa hàng'},
    # Add other customers if necessary based on mota.txt or data
}

# --- Product Mapping (derived from mota.txt) ---
# Key: (Tên mặt hàng, Đơn vị tính) -> Value: {'Mã nhóm hàng', 'Tên nhóm hàng', 'Mã mặt hàng'}
product_mapping = {
    ('Nấm Mộc nhĩ khô', 'gói'): {'Mã nhóm hàng': 'MN', 'Tên nhóm hàng': 'Nấm mộc nhĩ', 'Mã mặt hàng': 'MN01'},
    ('Nấm Mộc nhĩ khô thái sợi', 'gói'): {'Mã nhóm hàng': 'MN', 'Tên nhóm hàng': 'Nấm mộc nhĩ', 'Mã mặt hàng': 'MN02'},
    ('Nấm Bào ngư tươi', 'gói'): {'Mã nhóm hàng': 'BN', 'Tên nhóm hàng': 'Nấm bào ngư', 'Mã mặt hàng': 'BN01'},
    ('Nấm Bào ngư tươi', 'kg'): {'Mã nhóm hàng': 'BN', 'Tên nhóm hàng': 'Nấm bào ngư', 'Mã mặt hàng': 'BN01'},
    ('Nấm Bào ngư khô', 'gói'): {'Mã nhóm hàng': 'BN', 'Tên nhóm hàng': 'Nấm bào ngư', 'Mã mặt hàng': 'BN02'},
    ('Nấm Rơm tươi', 'kg'): {'Mã nhóm hàng': 'R', 'Tên nhóm hàng': 'Nấm rơm', 'Mã mặt hàng': 'R01'},
    ('Nấm Rơm khô', 'gói'): {'Mã nhóm hàng': 'R', 'Tên nhóm hàng': 'Nấm rơm', 'Mã mặt hàng': 'R02'},
    ('Nấm Đông cô', 'gói'): {'Mã nhóm hàng': 'DC', 'Tên nhóm hàng': 'Nấm đông cô', 'Mã mặt hàng': 'DC'},
    ('Nấm Hương', 'gói'): {'Mã nhóm hàng': 'H', 'Tên nhóm hàng': 'Nấm hương', 'Mã mặt hàng': 'H'},
    ('Tiêu hột', 'hộp'): {'Mã nhóm hàng': 'T', 'Tên nhóm hàng': 'Tiêu hột', 'Mã mặt hàng': 'T'},
    ('Ớt', 'hộp'): {'Mã nhóm hàng': 'OT', 'Tên nhóm hàng': 'Ớt', 'Mã mặt hàng': 'OT'},
    ('Nấm Đùi gà', 'gói'): {'Mã nhóm hàng': 'G', 'Tên nhóm hàng': 'Nấm đùi gà', 'Mã mặt hàng': 'G'},
    # Add other products if necessary based on mota.txt or data
}

# Counter for new product IDs
rau_counter = 1

def get_product_category(product_name, unit):
    """Determine product category based on name and unit using fuzzy matching."""
    # Check if it's a mushroom product
    if product_name.lower().startswith('nấm'):
        # First try exact match
        for (name, u), info in product_mapping.items():
            if name.lower() == product_name.lower() and u == unit:
                return info['Mã nhóm hàng'], info['Tên nhóm hàng'], info['Mã mặt hàng']
        
        # If no exact match, try fuzzy matching
        best_match = None
        best_score = 0
        
        # Extract key words from product name
        product_words = set(product_name.lower().split())
        
        # Special case for Nấm hương
        if 'hương' in product_name.lower():
            for (name, u), info in product_mapping.items():
                if 'hương' in name.lower() and u == unit:
                    return info['Mã nhóm hàng'], info['Tên nhóm hàng'], info['Mã mặt hàng']
        
        # Define mushroom type keywords and their priorities
        mushroom_types = {
            'mộc nhĩ': ['mộc nhĩ'],
            'bào ngư': ['bào ngư'],
            'rơm': ['rơm'],
            'đông cô': ['đông cô'],
            'hương': ['hương, hương khô'],
            'đùi gà': ['đùi gà']
        }
        
        # Find the mushroom type in the product name
        product_type = None
        for type_name, keywords in mushroom_types.items():
            if any(keyword in product_name.lower() for keyword in keywords):
                product_type = type_name
                break
        
        if product_type:
            for (name, u), info in product_mapping.items():
                if u != unit:
                    continue
                    
                # Check if it's the same type of mushroom
                if any(keyword in name.lower() for keyword in mushroom_types[product_type]):
                    # Calculate similarity score
                    name_words = set(name.lower().split())
                    common_words = product_words.intersection(name_words)
                    score = len(common_words) / max(len(product_words), len(name_words))
                    
                    # Boost score if it's the same type
                    if product_type in name.lower():
                        score += 0.3
                        
                    if score > best_score:
                        best_score = score
                        best_match = (name, u, info)
        
        # If we found a good match (score > 0.3), use it
        if best_match and best_score > 0.3:
            name, u, info = best_match
            print(f"Matched '{product_name}' to '{name}' with score {best_score:.2f}")
            return info['Mã nhóm hàng'], info['Tên nhóm hàng'], info['Mã mặt hàng']
            
        return None, None, None
    elif product_name.lower().startswith('rau'):
        global rau_counter
        ma_mat_hang = f'RAU{rau_counter:02d}'
        rau_counter += 1
        return 'RAU', 'Rau', ma_mat_hang
    else:
        return None, None, None

def validate_customer_segment(segment):
    """Validate customer segment and return 'Khác' if not in valid segments."""
    if segment not in VALID_CUSTOMER_SEGMENTS:
        return 'Khác'
    return segment

def process_sales_data(sales_excel_path, output_excel_path):
    """Reads sales data, adds missing columns using mappings, and saves to new excel."""
    global rau_counter
    # Reset rau_counter each time the function is called to ensure sequential IDs for new 'Rau' products in each run
    rau_counter = 1

    try:
        df_sales = pd.read_excel(sales_excel_path)
        print(f"Đã đọc file: {sales_excel_path}")
        print(f"Các cột trong file {sales_excel_path}: {list(df_sales.columns)}")

    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file {sales_excel_path}")
        return
    except Exception as e:
        print(f"Lỗi khi đọc file {sales_excel_path}: {e}")
        return

    # --- Dynamically update customer mapping ---
    existing_customer_ids = [v['Mã khách hàng'] for v in customer_mapping.values() if v.get('Mã khách hàng')]
    max_customer_id_num = 0
    for cid in existing_customer_ids:
        match = re.match(r'CU(\d+)', cid)
        if match:
            max_customer_id_num = max(max_customer_id_num, int(match.group(1)))

    updated_customer_mapping = customer_mapping.copy()
    next_customer_id_num = max_customer_id_num + 1

    for customer_name in df_sales['Tên khách hàng'].unique():
        if customer_name not in updated_customer_mapping:
            new_customer_id = f'CU{next_customer_id_num:03d}'
            updated_customer_mapping[customer_name] = {'Mã khách hàng': new_customer_id, 'Phân khúc khách hàng': 'Khác'}
            print(f"Added new customer '{customer_name}' with ID {new_customer_id} to mapping.")
            next_customer_id_num += 1

    # --- Dynamically update product mapping ---
    updated_product_mapping = product_mapping.copy()

    for index, row in df_sales.iterrows():
        product_name = row['Tên mặt hàng']
        unit = row['Đơn vị tính']
        product_key = (product_name, unit)

        # If product is not in the initial mapping, try to categorize and add it
        if product_key not in updated_product_mapping:
            ma_nhom, ten_nhom, ma_mat_hang = get_product_category(product_name, unit)
            if ma_nhom and ten_nhom and ma_mat_hang:
                updated_product_mapping[product_key] = {
                    'Mã nhóm hàng': ma_nhom,
                    'Tên nhóm hàng': ten_nhom,
                    'Mã mặt hàng': ma_mat_hang
                }
                print(f"Added new product '{product_name}' ('{unit}') to {ten_nhom} category with ID {ma_mat_hang}")
            else:
                print(f"Warning: Could not categorize product '{product_name}' ('{unit}')")

    # Use the updated mappings for processing
    df_sales['Mã khách hàng'] = df_sales['Tên khách hàng'].apply(
        lambda x: updated_customer_mapping.get(x, {}).get('Mã khách hàng', None)
    )
    
    df_sales['Phân khúc khách hàng'] = df_sales['Tên khách hàng'].apply(
        lambda x: validate_customer_segment(updated_customer_mapping.get(x, {}).get('Phân khúc khách hàng', 'Khác'))
    )

    def get_updated_product_info(row):
        key = (row['Tên mặt hàng'], row['Đơn vị tính'])
        return updated_product_mapping.get(key, {})

    df_sales['Mã nhóm hàng'] = df_sales.apply(lambda row: get_updated_product_info(row).get('Mã nhóm hàng', None), axis=1)
    df_sales['Tên nhóm hàng'] = df_sales.apply(lambda row: get_updated_product_info(row).get('Tên nhóm hàng', None), axis=1)
    df_sales['Mã mặt hàng'] = df_sales.apply(lambda row: get_updated_product_info(row).get('Mã mặt hàng', None), axis=1)

    # --- Reorder columns ---
    final_column_order = [
        'Ngày tạo đơn', 'Mã tạo đơn', 'Mã khách hàng', 'Tên khách hàng', 'Phân khúc khách hàng',
        'Mã nhóm hàng', 'Tên nhóm hàng', 'Mã mặt hàng', 'Tên mặt hàng', 'Đơn vị tính',
        'Số lượng', 'Đơn giá', 'Thành tiền'
    ]

    existing_cols_in_order = [col for col in final_column_order if col in df_sales.columns]
    final_df = df_sales[existing_cols_in_order]

    # --- Save to Excel ---
    try:
        final_df.to_excel(output_excel_path, index=False)
        print(f"Đã lưu dữ liệu xử lý vào file: {output_excel_path}")
    except Exception as e:
        print(f"Lỗi khi lưu file {output_excel_path}: {e}")


if __name__ == "__main__":
    # Adjust file paths as needed
    sales_file = "output.xlsx"
    output_file = "processed_output.xlsx"

    process_sales_data(sales_file, output_file) 