# rotor_tracker.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from PIL import Image
import io
import requests
from uuid import uuid4
import altair as alt
import re


import os
import os
import os
import toml
import streamlit as st
import streamlit as st
import pandas as pd
import requests

import os
import toml
import streamlit as st





# Stop here, don't show the rest of the app # Stop here, don't show the rest of the app
ROTOR_WEIGHTS = { 80: 0.5, 100: 1, 110: 1.01, 120: 1.02, 125: 1.058, 130: 1.1, 140: 1.15, 150: 1.3, 160: 1.4, 170: 1.422, 180: 1.5, 200: 1.7, 225: 1.9, 260: 2.15, 2403: 1.46, 1803: 1, 2003: 1.1 }
from uuid import uuid4

# Session state for logs

# Ensure session state dataframes exist before chatbot
if "clitting_data" not in st.session_state:
    st.session_state["clitting_data"] = pd.DataFrame(columns=[
        "Date", "Size (mm)", "Bags", "Weight per Bag (kg)", "Remarks", "ID"
    ])
if "lamination_v3" not in st.session_state:
    st.session_state["lamination_v3"] = pd.DataFrame(columns=[
        "Date", "Quantity", "Remarks", "ID"
    ])
if "lamination_v4" not in st.session_state:
    st.session_state["lamination_v4"] = pd.DataFrame(columns=[
        "Date", "Quantity", "Remarks", "ID"
    ])
if "stator_data" not in st.session_state:
    st.session_state["stator_data"] = pd.DataFrame(columns=[
        "Date", "Size (mm)", "Quantity", "Remarks",
        "Estimated Clitting (kg)", "Laminations Used",
        "Lamination Type", "ID"
    ])





    
# ====== INITIALIZE DATA ======
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        'Date', 'Size (mm)', 'Type', 'Quantity', 'Remarks', 'Status', 'Pending', 'ID'
    ])
    st.session_state.last_sync = "Never"
    st.session_state.editing = None
    st.session_state.filter_reset = False



# ====== APP LOGO ======
import streamlit as st
import requests
from PIL import Image
import io

@st.cache_data(ttl=86400, show_spinner=False)
def load_logo_bytes():
    logo_url = "https://ik.imagekit.io/zmv7kjha8x/D936A070-DB06-4439-B642-854E6510A701.PNG?updatedAt=1752629786861"
    response = requests.get(logo_url, timeout=5)
    response.raise_for_status()
    return response.content

def display_logo():
    try:
        st.image(load_logo_bytes(), width=200)
    except requests.exceptions.RequestException as e:
        st.warning(f"Couldn't load logo from URL: {e}")
        st.title("Rotor Tracker")
    except Exception as e:
        st.warning(f"An error occurred: {e}")
        st.title("Rotor Tracker")

display_logo()
