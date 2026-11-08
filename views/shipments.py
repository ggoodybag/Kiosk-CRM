import streamlit as st
import pandas as pd

def render(get_connection):
    st.subheader("Stock Shipment Logs & Additional Sub-Costs")
    conn = get_connection()
    sh_df = pd.read_sql_query("SELECT id, sku, item_name, quantity, base_cost_per_unit, total_additional_cost, total_landed_cost, effective_unit_cost, timestamp FROM stock_shipments ORDER BY timestamp DESC", conn)
    conn.close()
    st.dataframe(sh_df, use_container_width=True)