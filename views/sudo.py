import streamlit as st
import pandas as pd

def render(get_connection):
    st.subheader("⚙️ Sudo Administration: Roles, Permissions & User Accounts")
    
    col_role_create, col_user_create = st.columns(2)
    
    with col_role_create:
        st.markdown("### 1. Create New Custom Role")
        with st.form("new_role_form"):
            new_role_name = st.text_input("New Role Name (e.g., Supervisor)")
            selected_features = st.multiselect("Assign Features / Tabs", [
                "POS Checkout", "Inventory Control", "Operating Expenses", "Net P&L Overview", "Shipment Audit"
            ])
            if st.form_submit_button("Create Role"):
                if new_role_name:
                    conn = get_connection()
                    cur = conn.cursor()
                    try:
                        cur.execute("INSERT INTO roles (role_name) RETURNING id;", (new_role_name,))
                        rid = cur.fetchone()[0]
                        for f in selected_features:
                            cur.execute("INSERT INTO role_permissions (role_id, feature_name) VALUES (%s, %s);", (rid, f))
                        conn.commit()
                        st.success(f"Role '{new_role_name}' created successfully!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Error creating role: {ex}")
                    finally:
                        cur.close()
                        conn.close()

    with col_user_create:
        st.markdown("### 2. Create Staff User & Assign Role")
        conn = get_connection()
        roles_df = pd.read_sql_query("SELECT id, role_name FROM roles", conn)
        conn.close()
        
        with st.form("new_user_form"):
            u_name = st.text_input("Staff Username (e.g. Mummy, Cashier2)")
            u_pin = st.text_input("Assigned 4-Digit PIN", type="password")
            chosen_role = st.selectbox("Select Role", roles_df["role_name"].tolist())
            
            if st.form_submit_button("Create User Account"):
                if u_name and u_pin:
                    role_id = roles_df.loc[roles_df["role_name"] == chosen_role, "id"].values[0]
                    conn = get_connection()
                    cur = conn.cursor()
                    try:
                        cur.execute("INSERT INTO app_users (username, pin, role_id) VALUES (%s, %s, %s);", (u_name.strip(), u_pin.strip(), role_id))
                        conn.commit()
                        st.success(f"User '{u_name}' created with role '{chosen_role}'!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Error creating user (PIN or Username might already exist): {ex}")
                    finally:
                        cur.close()
                        conn.close()

    st.markdown("---")
    col_pin_update, col_delete_user = st.columns(2)

    with col_pin_update:
        st.markdown("### 3. Update Existing User PIN")
        with st.form("update_pin_form"):
            conn = get_connection()
            users_list_df = pd.read_sql_query("SELECT username FROM app_users", conn)
            conn.close()
            
            target_user = st.selectbox("Select Staff Member", users_list_df["username"].tolist())
            new_pin = st.text_input("Enter New 4-Digit PIN", type="password", max_chars=4)
            
            if st.form_submit_button("Update PIN"):
                if new_pin and len(new_pin) == 4:
                    conn = get_connection()
                    cur = conn.cursor()
                    try:
                        cur.execute("UPDATE app_users SET pin = %s WHERE username = %s;", (new_pin.strip(), target_user))
                        conn.commit()
                        st.success(f"PIN successfully updated for {target_user}!")
                    except Exception as e:
                        st.error(f"Error updating PIN: {e}")
                    finally:
                        cur.close()
                        conn.close()
                else:
                    st.error("Please enter a valid 4-digit PIN.")

    with col_delete_user:
        st.markdown("### 4. Delete Staff User Account")
        with st.form("delete_user_form"):
            conn = get_connection()
            users_list_df = pd.read_sql_query("SELECT username FROM app_users", conn)
            conn.close()
            
            user_to_delete = st.selectbox("Select Staff to Remove", users_list_df["username"].tolist(), key="del_user")
            
            if st.form_submit_button("🗑️ Delete User Account", type="secondary"):
                if user_to_delete.lower() in ["lead developer", "mummy"]:
                    st.warning("⚠️ Protected system accounts cannot be deleted.")
                else:
                    conn = get_connection()
                    cur = conn.cursor()
                    try:
                        cur.execute("DELETE FROM app_users WHERE username = %s;", (user_to_delete,))
                        conn.commit()
                        st.success(f"User '{user_to_delete}' has been deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting user: {e}")
                    finally:
                        cur.close()
                        conn.close()

    st.markdown("---")
    st.markdown("### 📋 Current Active Users & Roles in System")
    conn = get_connection()
    users_df = pd.read_sql_query("""
        SELECT u.username AS "Staff Name", r.role_name AS "Role" 
        FROM app_users u JOIN roles r ON u.role_id = r.id
    """, conn)
    conn.close()
    st.dataframe(users_df, use_container_width=True)