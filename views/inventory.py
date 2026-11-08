import streamlit as st
import pandas as pd
import json

def render(get_connection):
    st.subheader("Product Catalog & Dynamic Stock Batch Intake")
    
    if "dynamic_costs" not in st.session_state:
        st.session_state.dynamic_costs = []

    with st.expander("➕ Intake New Stock Batch (With Custom Additional Cost Sub-Columns)", expanded=True):
        with st.form("stock_form_dynamic"):
            col_b1, col_b2 = st.columns(2)
            
            with col_b1:
                st.markdown("#### 1. Basic Item Details")
                n_sku = st.text_input("SKU / Barcode*")
                n_name = st.text_input("Item Name / Description*")
                n_qty = st.number_input("Quantity in Batch*", min_value=1, value=10, step=1)
                n_base = st.number_input("Basic Cost (Initial Unit Cost Price ₦)*", min_value=0.0, step=50.0)
                n_price = st.number_input("Target Retail Selling Price (₦)*", min_value=0.0, step=50.0)

            with col_b2:
                st.markdown("#### 2. Sub-Column Additional Costs Builder")
                cost_sub_name = st.text_input("Additional Cost Name (e.g. Transport, Mop)", placeholder="e.g. Transport Fee")
                cost_sub_amt = st.number_input("Cost Amount (₦)", min_value=0.0, step=50.0, value=0.0)
                
                add_cost_btn = st.form_submit_button("➕ Add Cost Sub-Item to Batch")

        if add_cost_btn:
            if cost_sub_name and cost_sub_amt > 0:
                st.session_state.dynamic_costs.append({"name": cost_sub_name.strip(), "amount": float(cost_sub_amt)})
                st.success(f"Added sub-item '{cost_sub_name}' (₦{cost_sub_amt:,.2f}) to batch calculations.")
                st.rerun()
            else:
                st.warning("Please provide a valid cost name and amount greater than zero.")

        if st.session_state.dynamic_costs:
            st.markdown("##### Current Additional Costs Sub-List for this Intake:")
            dyn_df = pd.DataFrame(st.session_state.dynamic_costs)
            dyn_df.columns = ["Cost Sub-Name", "Amount (₦)"]
            st.dataframe(dyn_df, use_container_width=True)
            
            if st.button("🗑️ Clear All Additional Costs"):
                st.session_state.dynamic_costs = []
                st.rerun()

        total_add_cost = sum(item["amount"] for item in st.session_state.dynamic_costs)
        unit_add_overhead = (total_add_cost / n_qty) if n_qty > 0 else 0
        final_landed_unit_cost = n_base + unit_add_overhead
        projected_profit = n_price - final_landed_unit_cost

        st.info(f"""
        🧮 **Automated Landed Calculation Summary:**
        * **Initial Basic Unit Cost:** ₦{n_base:,.2f}
        * **Total Additional Sub-Costs:** ₦{total_add_cost:,.2f} (*₦{unit_add_overhead:,.2f} added per unit*)
        * **Final True Landed Cost per Unit:** **₦{final_landed_unit_cost:,.2f}**
        * **Projected Unit Profit Margin:** **₦{projected_profit:,.2f}** ({((projected_profit/n_price)*100 if n_price > 0 else 0):.1f}%)
        """)

        if st.button("💾 Save Stock Batch & Commit to Database", type="primary"):
            if n_sku and n_name:
                conn = get_connection()
                cur = conn.cursor()
                try:
                    costs_json_str = json.dumps(st.session_state.dynamic_costs)
                    total_shipment_landed = (n_base * n_qty) + total_add_cost

                    cur.execute("""
                        INSERT INTO stock_shipments 
                        (sku, item_name, quantity, base_cost_per_unit, additional_costs_json, total_additional_cost, total_landed_cost, effective_unit_cost)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        n_sku.strip(), n_name, int(n_qty), n_base, 
                        costs_json_str, total_add_cost, total_shipment_landed, final_landed_unit_cost
                    ))

                    cur.execute("""
                        INSERT INTO products (sku, name, base_cost, overhead_cost, cost_price, selling_price, stock)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (sku) DO UPDATE SET
                            name = EXCLUDED.name,
                            base_cost = EXCLUDED.base_cost,
                            overhead_cost = EXCLUDED.overhead_cost,
                            cost_price = EXCLUDED.cost_price,
                            selling_price = EXCLUDED.selling_price,
                            stock = products.stock + EXCLUDED.stock;
                    """, (n_sku.strip(), n_name, n_base, unit_add_overhead, final_landed_unit_cost, n_price, int(n_qty)))

                    conn.commit()
                    st.session_state.dynamic_costs = []
                    st.success(f"Successfully saved stock batch for '{n_name}'!")
                    st.rerun()
                except Exception as err:
                    st.error(f"Error saving batch: {err}")
                finally:
                    cur.close()
                    conn.close()
            else:
                st.error("Please fill in SKU and Item Name.")


# Cache product catalog for 60 seconds to reduce database roundtrips
@st.cache_data(ttl=60)
def load_cached_catalog(db_url_secret):
    import psycopg2
    conn = psycopg2.connect(db_url_secret)
    df = pd.read_sql_query("""
        SELECT sku, name, 
               base_cost as "Basic Cost (₦)", 
               overhead_cost as "Add. Sub-Cost/Unit (₦)", 
               cost_price as "True Landed Cost/Unit (₦)", 
               selling_price as "Selling Price (₦)", 
               stock as "Stock Qty" 
        FROM products
    """, conn)
    conn.close()
    return df

def render(get_connection):
    # ... (keep your intake form code above as it is) ...

    st.markdown("---")
    st.markdown("### 📋 Active Product Catalog")
    
    # Use the cached catalog loader
    inv_df = load_cached_catalog(st.secrets["postgres"]["url"])
    st.dataframe(inv_df, use_container_width=True)
