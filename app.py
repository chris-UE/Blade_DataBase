import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Blade Tracker", layout="centered")

# --- SESSION STATE INITIALIZATION ---
# This keeps track of which blade we are looking at across tab switches
if "active_blade" not in st.session_state:
    st.session_state.active_blade = None

conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    sheet_url = "https://docs.google.com/spreadsheets/d/1gMFMLz_qM4LOaiseSSPgyiNe9lQN9iTFfjvhaX9wsYw/edit"
    # QOL: fillna('') replaces 'NaN' with a clean empty string globally
    return conn.read(spreadsheet=sheet_url, ttl=0).fillna('')

df = get_data()
# Clean Blade_ID column and sort numerically so the newest is at the bottom of the list
df['Blade_ID'] = df['Blade_ID'].astype(str).str.replace(r'\.0$', '', regex=True)
blade_list = sorted(df['Blade_ID'].tolist(), key=lambda x: int(x) if x.isdigit() else x)

st.title("🚁 Blade Manager")

# Determine which tab to open by default (0 = Search, 1 = Add)
default_tab = 0 if st.session_state.active_blade is None else 0
tab_view, tab_add, tab_bulk = st.tabs(["🔍 Search & Edit", "➕ Add New", "📦 Assign Set"])

# --- TAB 1: SEARCH & EDIT ---
with tab_view:
    # QOL: Dropdown search. 'index' is set based on session_state if we just added a blade.
    current_index = 0
    if st.session_state.active_blade in blade_list:
        current_index = blade_list.index(st.session_state.active_blade)

    search_id = st.selectbox(
        "Select or Search Blade ID", 
        options=[""] + blade_list, 
        index=blade_list.index(st.session_state.active_blade) + 1 if st.session_state.active_blade else 0
    )

    if search_id:
        result = df[df['Blade_ID'] == search_id]
        
        if not result.empty:
            row_idx = result.index[0]
            curr = result.iloc[0]
            
            with st.form("edit_form"):
                st.subheader(f"Editing Blade: {search_id}")
                
                c1, c2 = st.columns(2)
                weight = c1.number_input("Weight", value=float(curr['Weight']) if curr['Weight'] != '' else 0.0)
                cg = c2.number_input("Center of Gravity", value=float(curr['Center_of_Gravity']) if curr['Center_of_Gravity'] != '' else 0.0)
                
                c3, c4 = st.columns(2)
                w_added_status = c3.selectbox("Weight Added?", ["No", "Yes"], index=1 if curr['Weight_Added'] == "Yes" else 0)
                # QOL: Logic check - if status is No, default the value to 0
                val_added = float(curr['Added_Weight']) if (curr['Added_Weight'] != '' and w_added_status == "Yes") else 0.0
                added_weight_val = c4.number_input("Added Weight Amount", value=val_added)
                
                c5, c6 = st.columns(2)
                t_added_status = c5.selectbox("Tip Weight Added?", ["No", "Yes"], index=1 if curr['Tip_Weight_Added'] == "Yes" else 0)
                val_tip = float(curr['Tip_Weight']) if (curr['Tip_Weight'] != '' and t_added_status == "Yes") else 0.0
                tip_weight_val = c6.number_input("Tip Weight Amount", value=val_tip)
                
                turbine = st.text_input("Assigned to Turbine", value=str(curr['Assigned_to_Turbine']))
                qa_test = st.number_input("QA Deflection Test", value=float(curr['QA_Deflection_Test']) if curr['QA_Deflection_Test'] != '' else 0.0)
                notes = st.text_area("Notes", value=str(curr['Notes']))
                
                col_save, col_del = st.columns(2)
                
                if col_save.form_submit_button("💾 Save Changes"):
                    # QOL: Clear values if "No" is selected
                    final_added = added_weight_val if w_added_status == "Yes" else 0
                    final_tip = tip_weight_val if t_added_status == "Yes" else 0
                    
                    df.at[row_idx, 'Weight'] = weight
                    df.at[row_idx, 'Center_of_Gravity'] = cg
                    df.at[row_idx, 'Weight_Added'] = w_added_status
                    df.at[row_idx, 'Added_Weight'] = final_added
                    df.at[row_idx, 'Tip_Weight_Added'] = t_added_status
                    df.at[row_idx, 'Tip_Weight'] = final_tip
                    df.at[row_idx, 'Assigned_to_Turbine'] = turbine
                    df.at[row_idx, 'QA_Deflection_Test'] = qa_test
                    df.at[row_idx, 'Notes'] = notes
                    
                    conn.update(data=df)
                    st.success("Updated!")
                    st.rerun()
                
                if col_del.form_submit_button("🗑️ Delete"):
                    df = df.drop(row_idx)
                    conn.update(data=df)
                    st.session_state.active_blade = None
                    st.rerun()

# --- TAB 2: ADD NEW ---
with tab_add:
    with st.form("new_blade_form", clear_on_submit=True):
        st.subheader("Register New Blade")
        # Show the last ID as a help hint
        last_id = blade_list[-1] if blade_list else "None"
        new_id = st.text_input("New Blade ID", help=f"Last registered ID: {last_id}")
        new_date = st.date_input("Manufacture Date", value=datetime.now())
        
        if st.form_submit_button("Register & Edit Details"):
            if new_id and new_id not in df['Blade_ID'].values:
                new_row = {
                    "Blade_ID": new_id, "Manufacture_Date": new_date.strftime("%m/%d/%Y"),
                    "Weight": 0, "Center_of_Gravity": 0, "Weight_Added": "No",
                    "Added_Weight": 0, "Tip_Weight_Added": "No", "Tip_Weight": 0,
                    "Assigned_to_Turbine": "", "QA_Deflection_Test": 0, "Notes": ""
                }
                updated_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                conn.update(data=updated_df)
                
                # QOL: Redirect logic
                st.session_state.active_blade = new_id
                st.success(f"Blade {new_id} created! Redirecting to Edit...")
                st.rerun()
            else:
                st.error("Invalid or Duplicate ID")

# --- TAB 3: BULK ASSIGN ---
with tab_bulk:
    st.subheader("Assign 5-Blade Set")
    target_turbine = st.text_input("Turbine Serial Number")
    available_blades = df[df['Assigned_to_Turbine'].astype(str).isin(['', '0', '0.0'])]['Blade_ID'].tolist()
    selected_ids = st.multiselect("Select 5 Blades", options=available_blades)
    
    if st.button("📦 Confirm Shipment"):
        if len(selected_ids) == 5 and target_turbine:
            df.loc[df['Blade_ID'].isin(selected_ids), 'Assigned_to_Turbine'] = target_turbine
            conn.update(data=df)
            st.success("Set assigned!")
            st.rerun()