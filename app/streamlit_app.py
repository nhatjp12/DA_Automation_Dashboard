import streamlit as st
import pandas as pd
from services.gemini_service import analyze_prompt
from services.db_service import run_query # Assuming db_service.py is in services folder
import plotly.express as px
import json
import io
from contextlib import redirect_stdout
import traceback
import re
import plotly.graph_objects as go

# Định nghĩa hàm auto_plot ở đây
def pick_best_xy(df):
    cols = list(df.columns)
    x = None
    y = None

    # Ưu tiên cột thời gian cho X
    time_keywords = ['thang', 'ngay', 'date', 'month', 'year', 'nam', 'quy', 'time', 'period']
    for t_kw in time_keywords:
        for c in cols:
            if t_kw in c.lower():
                x = c
                break
        if x:
            break
    
    if not x: # Nếu không có cột thời gian, tìm cột categorical
        cat_cols = [c for c in cols if not pd.api.types.is_numeric_dtype(df[c]) or df[c].nunique() < 30]
        if cat_cols:
            # Ưu tiên cột có ít giá trị duy nhất hơn (nhưng không quá ít)
            cat_cols_sorted = sorted(cat_cols, key=lambda col: df[col].nunique())
            for c in cat_cols_sorted:
                if df[c].nunique() > 1 : # Avoid columns with only one unique value for X
                    x = c
                    break
            if not x and cat_cols_sorted: # Fallback if all have 1 unique value (less ideal)
                x = cat_cols_sorted[0]


    # Ưu tiên cột số có tên đặc biệt cho Y
    y_keywords = ['tongdoanhthu', 'doanhthu', 'soluong', 'giatri', 'value', 'amount', 'count', 'total', 'metric']
    num_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c]) and c != x]

    for y_kw in y_keywords:
        for c in num_cols:
            if y_kw in c.lower():
                y = c
                break
        if y:
            break
    
    if not y and num_cols: # Nếu không có tên đặc biệt, lấy cột số đầu tiên không phải là X
        y = num_cols[0]

    # Fallbacks if x or y are still not found
    if not x and cols:
        x = cols[0]
    if not y and cols:
        if len(cols) > 1 and cols[1] != x:
            y = cols[1]
        elif len(cols) > 1 and cols[0] != x: # If cols[1] was chosen as x
             y = cols[0]
        elif cols[0] != x : # Only one column, and it's not x (should not happen if x picked first)
             y = cols[0]
        elif len(cols) == 1: # Only one column, use it for y if x is also that col (e.g. for histogram)
            y = cols[0]


    return x, y

def auto_plot(df, chart_type=None, x_col=None, y_col=None, color_col=None):
    if df is None or df.empty:
        st.warning("Không có dữ liệu để vẽ biểu đồ.")
        return None

    barmode = None
    actual_chart_type = chart_type
    if chart_type and isinstance(chart_type, str):
        if 'stack' in chart_type.lower() and 'bar' in chart_type.lower():
            actual_chart_type = 'bar'
            barmode = 'stack'
        elif chart_type.strip().lower() == 'stacked_bar': # explicit type
            actual_chart_type = 'bar'
            barmode = 'stack'


    # Column selection logic:
    # 1. Use suggested columns if valid
    # 2. Fallback to hardcoded preferences (Thang, TongDoanhThu, Nam)
    # 3. Fallback to pick_best_xy
    # 4. Fallback to auto-detection of color column

    cols = list(df.columns)
    x = x_col if x_col and x_col in cols else None
    y = y_col if y_col and y_col in cols else None
    color = color_col if color_col and color_col in cols else None

    # Fallback to specific common column names if suggestions not used or invalid
    if not x and 'Thang' in cols: x = 'Thang'
    if not y and 'TongDoanhThu' in cols: y = 'TongDoanhThu'
    if not y and 'DoanhThu' in cols : y = 'DoanhThu' #  Added this common variant
    if not color and 'Nam' in cols: color = 'Nam'


    # If x or y are still not determined, use pick_best_xy
    if not x or not y:
        picked_x, picked_y = pick_best_xy(df)
        if not x: x = picked_x
        if not y: y = picked_y
    
    # Validate x and y exist
    if not x or x not in df.columns:
        st.error(f"Không tìm thấy cột X ({x}) hợp lệ trong dữ liệu.")
        return None
    if not y or y not in df.columns:
        st.error(f"Không tìm thấy cột Y ({y}) hợp lệ trong dữ liệu.")
        return None

    # Auto-detect color column if not provided or suggested
    if not color:
        num_cols_set = {c for c in cols if pd.api.types.is_numeric_dtype(df[c])}
        potential_color_cols = [c for c in cols if c not in [x, y] and c not in num_cols_set and df[c].nunique() < 20 and df[c].nunique() > 1]
        if potential_color_cols:
            # Prefer columns with fewer unique values for color, but more than 1
            potential_color_cols.sort(key=lambda c: df[c].nunique())
            color = potential_color_cols[0]
        elif 'TenNhomHang' in cols and 'TenNhomHang' not in [x,y]: color = 'TenNhomHang' # Specific fallback

    # Data type conversions
    if y in df.columns:
        df[y] = pd.to_numeric(df[y], errors='coerce').fillna(0) # Fill NaN with 0 for numeric y
    if x in df.columns and any(t in x.lower() for t in ['ngay', 'thang', 'date', 'year', 'month', 'quy']):
        # Attempt to convert to numeric if it looks like a time component that should be ordered
        # If it's already datetime, plotly handles it. If it's string like "Tháng 1", conversion might be tricky.
        # For simplicity, let's assume if it's numeric (e.g. Thang as 1,2,3) it's fine.
        # If it's categorical like "Jan", "Feb", plotly also handles sorting if df is sorted.
        pass # Plotly often handles time-like axes well. Explicit conversion can be complex.


    # Automatic chart type selection if not provided
    if not actual_chart_type or actual_chart_type.strip() == "":
        num_distinct_x = df[x].nunique()
        
        if pd.api.types.is_numeric_dtype(df[y]):
            if pd.api.types.is_numeric_dtype(df[x]): # Both numeric -> scatter or line
                actual_chart_type = "line" if num_distinct_x > 5 else "scatter"
            else: # X is categorical/datetime, Y is numeric
                if num_distinct_x <= 10 and not color : # Few categories, no color -> pie or bar
                     actual_chart_type = "pie" if num_distinct_x <=7 else "bar"
                else: # More categories or has color -> bar or line
                     actual_chart_type = "bar"
        else: # Y is not numeric (less common for typical charts)
            actual_chart_type = "bar" # Default to bar
        
        if color and actual_chart_type != "pie": # If color is present, group/stack often makes sense
            if actual_chart_type == "bar":
                barmode = "group" # Default to grouped bar if color exists
        st.info(f"Loại biểu đồ không được chỉ định, tự động chọn: {actual_chart_type}" + (f" với barmode={barmode}" if barmode else ""))


    # Data transformation for wide format (e.g., DoanhThu2022, DoanhThu2023)
    wide_pattern = re.compile(r'^(DoanhThu|SoLuong|GiaTri)(\d{4})$') # More generic pattern
    id_vars_for_melt = [c for c in [x, color] if c and c in df.columns and not wide_pattern.match(c)]
    if not id_vars_for_melt and x and x in df.columns: # Ensure at least one id_var, typically x
        id_vars_for_melt = [x]
    
    value_vars_for_melt = [c for c in df.columns if wide_pattern.match(c)]

    if value_vars_for_melt and id_vars_for_melt and actual_chart_type in ['line', 'bar', 'area', 'combo', 'stacked bar']:
        try:
            # Determine value_name from the prefix of the first value_var
            match_val_name = wide_pattern.match(value_vars_for_melt[0])
            base_value_name = match_val_name.group(1) if match_val_name else 'Value' # e.g., DoanhThu
            var_name_melt = 'Nam' # Default, can be dynamic if needed

            df_melted = pd.melt(df, id_vars=id_vars_for_melt, value_vars=value_vars_for_melt,
                                var_name=var_name_melt, value_name=base_value_name)
            
            # Extract year from the var_name
            df_melted[var_name_melt] = df_melted[var_name_melt].str.extract(r'(\d{4})').astype(str)
            
            # Update x, y, color for the melted dataframe
            # x remains from id_vars. y becomes base_value_name. color becomes var_name_melt.
            if id_vars_for_melt[0] == x: # Check if x was an id_var
                 y = base_value_name
                 color = var_name_melt # The new color dimension is the melted variable name (e.g., Nam)
                 df = df_melted # Use the melted dataframe
                 st.info(f"Dữ liệu được chuyển từ dạng wide sang long. X='{x}', Y='{y}', Color='{color}'")
        except Exception as e_melt:
            st.warning(f"Lỗi khi cố gắng melt dữ liệu wide: {e_melt}. Sử dụng dữ liệu gốc.")


    layout_opts = dict(
        template="plotly_dark",
        legend_title_text=str(color) if color else '',
        margin=dict(l=70, r=50, t=70, b=70), # Increased margins slightly
        xaxis=dict(title_text=str(x), automargin=True, tickangle=-45, tickfont=dict(size=11)), # tickangle often helps
        yaxis=dict(title_text=str(y), automargin=True, tickfont=dict(size=11)),
        bargap=0.15 if not color else 0.1, # Adjust gap based on color presence
        bargroupgap=0.05,
        title_text=f"{y} theo {x}" + (f" theo {color}" if color else ""), # Dynamic title
        height=500, # Default height
    )
    color_discrete_sequence = px.colors.qualitative.Plotly # Using a different default palette

    fig = None
    try:
        if actual_chart_type == "bar":
            fig = px.bar(df, x=x, y=y, color=color, barmode=barmode or ('group' if color else 'relative'), 
                         color_discrete_sequence=color_discrete_sequence, text_auto=True)
        elif actual_chart_type == "barh":
            fig = px.bar(df, x=y, y=x, color=color, orientation='h', 
                         barmode='group' if color else 'relative', 
                         color_discrete_sequence=color_discrete_sequence, text_auto=True)
        elif actual_chart_type == "line":
            fig = px.line(df, x=x, y=y, color=color, markers=True, 
                          color_discrete_sequence=color_discrete_sequence)
        elif actual_chart_type == "area":
            fig = px.area(df, x=x, y=y, color=color, line_group=color if color else None, # line_group needs a column
                          color_discrete_sequence=color_discrete_sequence)
        elif actual_chart_type == "pie":
            # For pie, x is names, y is values. Color is an additional dimension if present.
            if x and y:
                 names_pie = x
                 values_pie = y
                 # Ensure names_pie is not numeric for better pie charts, unless it's like years
                 if pd.api.types.is_numeric_dtype(df[names_pie]) and df[names_pie].nunique() > 10:
                     st.warning(f"Cột '{names_pie}' cho biểu đồ tròn là số và có nhiều giá trị. Cân nhắc cột khác.")

                 fig = px.pie(df, names=names_pie, values=values_pie, color=color if color and color != names_pie else None, 
                              color_discrete_sequence=color_discrete_sequence, hole=0.3) # Added a hole for donut style
                 fig.update_traces(textposition='inside', textinfo='percent+label')
            else:
                st.error("Cần cột 'names' (X) và 'values' (Y) cho biểu đồ tròn.")
        elif actual_chart_type == "scatter":
            fig = px.scatter(df,x=x,y=y,color=color, color_discrete_sequence=color_discrete_sequence,
                             size=y if pd.api.types.is_numeric_dtype(df[y]) else None) # Optional size based on Y
        elif actual_chart_type == "combo":
            fig = go.Figure()
            unique_colors = df[color].unique() if color and color in df.columns else [None]
            
            for i, c_val in enumerate(unique_colors):
                df_group = df[df[color] == c_val] if c_val is not None else df
                
                bar_name = f"{y} (Bar)" + (f" - {c_val}" if c_val else "")
                line_name = f"{y} (Line)" + (f" - {c_val}" if c_val else "")

                fig.add_trace(go.Bar(x=df_group[x], y=df_group[y], name=bar_name,
                                     marker_color=color_discrete_sequence[i % len(color_discrete_sequence)]))
                fig.add_trace(go.Scatter(x=df_group[x], y=df_group[y], name=line_name, mode='lines+markers',
                                         line=dict(color=color_discrete_sequence[(i+1) % len(color_discrete_sequence)]))) # Slightly different color for line
            fig.update_layout(barmode='group') # Group bars if multiple colors

        if fig is not None:
            fig.update_layout(**layout_opts)
            # For bar charts, if y values are large, format them
            if actual_chart_type in ["bar", "barh", "combo"] and pd.api.types.is_numeric_dtype(df[y]) and df[y].max() > 1000:
                fig.update_layout(yaxis_tickformat=',.0f') # Format y-axis for large numbers
            if actual_chart_type != "pie" and color and df[color].nunique() > 10: # If too many colors, hide legend or make smaller
                fig.update_layout(showlegend=False)


    except Exception as e_plot:
        st.error(f"Lỗi khi tạo biểu đồ '{actual_chart_type}': {e_plot}")
        st.code(traceback.format_exc())
        return None
        
    return fig


st.set_page_config(layout="wide")
st.title("💬 Chat with Data Dashboard")

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame()
if 'last_sql' not in st.session_state:
    st.session_state.last_sql = ""
if 'current_fig' not in st.session_state:
    st.session_state.current_fig = None


# User input
prompt = st.text_input("Nhập yêu cầu phân tích dữ liệu hoặc vẽ/chỉnh sửa biểu đồ:", key="user_prompt",
                       placeholder="Ví dụ: 'doanh thu theo tháng năm 2023' hoặc 'đổi thành biểu đồ đường'")

if st.button("🚀 Xử lý yêu cầu", type="primary"):
    if not prompt:
        st.warning("Vui lòng nhập yêu cầu.")
        st.stop()

    current_df_cols = None
    if not st.session_state.df.empty:
        current_df_cols = list(st.session_state.df.columns)

    with st.spinner("🧠 Đang xử lý yêu cầu..."):
        try:
            api_result = analyze_prompt(prompt, current_df_columns=current_df_cols)

            action = api_result.get("action")
            sql_query = api_result.get("sql", "")
            chart_type_api = api_result.get("chart_type", None)
            x_col_api = api_result.get("x_col", None)
            y_col_api = api_result.get("y_col", None)
            color_col_api = api_result.get("color_col", None)

            if action == "error":
                st.error(f"Lỗi phân tích yêu cầu: {api_result.get('error', 'Không rõ lỗi')}")
                st.stop()
            elif action == "explain":
                st.info(f"Giải thích từ AI: {api_result.get('error', 'Yêu cầu không phù hợp để phân tích dữ liệu hoặc vẽ biểu đồ.')}") # Using 'error' field for explanation text for now
                st.stop()

            # Handle data fetching if SQL is provided
            if sql_query and action in ["query_only", "query_and_chart"]:
                st.subheader("⚙️ SQL Query được tạo:")
                st.code(sql_query, language="sql")
                st.session_state.last_sql = sql_query
                try:
                    st.info("⏳ Đang truy vấn dữ liệu...")
                    data = run_query(sql_query) # This should return list of dicts or similar
                    if data is not None:
                        df = pd.DataFrame(data)
                        st.session_state.df = df
                        if df.empty:
                            st.warning("Truy vấn không trả về dữ liệu hoặc dữ liệu rỗng.")
                        else:
                            st.success(f"Đã tải {len(df)} dòng dữ liệu.")
                    else: # run_query might return None on error or no data
                        st.warning("Truy vấn không trả về dữ liệu (kết quả là None).")
                        st.session_state.df = pd.DataFrame() # Reset df

                except Exception as e:
                    st.error(f"Lỗi khi thực thi SQL query: {e}")
                    st.code(traceback.format_exc())
                    st.session_state.df = pd.DataFrame() # Reset df
                    st.session_state.last_sql = ""
                    st.stop()
            
            # Display data if available and action is not just chart modification
            if not st.session_state.df.empty and action != "modify_chart":
                st.subheader("📊 Dữ liệu trả về:")
                st.dataframe(st.session_state.df, height=300) # Use st.dataframe for better display

            # Plotting logic
            if action in ["query_and_chart", "modify_chart"]:
                if not st.session_state.df.empty:
                    st.subheader("📈 Biểu đồ:")
                    with st.spinner("🎨 Đang vẽ biểu đồ..."):
                        fig = auto_plot(st.session_state.df.copy(), # Pass a copy to avoid modification issues
                                        chart_type=chart_type_api,
                                        x_col=x_col_api,
                                        y_col=y_col_api,
                                        color_col=color_col_api)
                        if fig:
                            st.plotly_chart(fig, use_container_width=True)
                            st.session_state.current_fig = fig # Store the figure
                        else:
                            st.warning("Không thể tạo biểu đồ từ dữ liệu hoặc yêu cầu hiện tại.")
                else:
                    st.warning("Không có dữ liệu để vẽ biểu đồ. Vui lòng thực hiện truy vấn trước.")
            
            # If action was 'query_only', explicitly state no chart is generated for this request type
            elif action == "query_only" and not st.session_state.df.empty:
                 st.info("Yêu cầu này chỉ để xem dữ liệu, không tạo biểu đồ.")


        except Exception as e:
            st.error(f"Đã xảy ra lỗi không mong muốn trong quá trình xử lý: {e}")
            st.code(traceback.format_exc())

# Display current data and last SQL query outside the button press logic, if they exist
if not st.session_state.df.empty and not st.button: # Only show if not actively processing a new request
    with st.expander("Xem lại dữ liệu hiện tại", expanded=False):
        st.dataframe(st.session_state.df)

if st.session_state.last_sql and not st.button:
    st.caption(f"Last SQL Query: `{st.session_state.last_sql}`")