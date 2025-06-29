# Google Sheets setup
def get_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", 
             "https://www.googleapis.com/auth/drive"]
    
    # Streamlit secrets are already dictionaries - no need for json.loads()
    creds_dict = st.secrets["gcp_service_account"]
    
    # Ensure the credentials are properly formatted
    if isinstance(creds_dict, str):
        try:
            creds_dict = json.loads(creds_dict)
        except json.JSONDecodeError:
            st.error("Invalid service account format in secrets")
            return None
            
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Rotor Log").sheet1

def read_sheet_as_df():
    try:
        sheet = get_gsheet()
        if sheet is None:
            return pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks'])
        records = sheet.get_all_records()
        return pd.DataFrame(records) if records else pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks'])
    except Exception as e:
        st.error(f"Error reading Google Sheet: {e}")
        return pd.DataFrame(columns=['Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks'])
