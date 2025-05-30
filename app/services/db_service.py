from sqlalchemy import create_engine, text
import urllib

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

def run_query(sql):
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = result.keys()
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
    return rows 