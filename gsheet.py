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
