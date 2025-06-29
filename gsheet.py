
>>> import gspread
... from google.oauth2.service_account import Credentials
... import pandas as pd
... import streamlit as st
... 
... SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
... SHEET_NAME = "Rotor Log"
... 
... def get_gsheet():
...     creds_dict = st.secrets["gcp_service_account"]
...     creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
...     client = gspread.authorize(creds)
... 
...     try:
...         sheet = client.open(SHEET_NAME).sheet1
...     except gspread.SpreadsheetNotFound:
...         # Create sheet if it doesn't exist
...         sheet = client.create(SHEET_NAME).sheet1
...         # Share it again after creating
...         client.insert_permission(
...             creds_dict["client_email"],
...             perm_type='user',
...             role='writer'
...         )
...         # Set headers
...         sheet.insert_row(["Date", "Size (mm)", "Type", "Quantity", "Remarks"], 1)
...     return sheet
... 
... def append_to_sheet(new_row):
...     sheet = get_gsheet()
...     sheet.append_row(new_row)
... 
... def read_sheet_as_df():
...     sheet = get_gsheet()
...     data = sheet.get_all_records()
