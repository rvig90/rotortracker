def get_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", 
             "https://www.googleapis.com/auth/drive"]
    
    try:
        # Get credentials from Streamlit secrets
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # Ensure the private key is properly formatted
        if "\\n" in creds_dict["private_key"]:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Rotor Log").sheet1
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {str(e)}")
        return None
