from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
import datetime

app = FastAPI()

FILE = "rotor_data.csv"

class RotorEntry(BaseModel):
    size: str
    status: str
    remarks: str = ""

@app.post("/add-rotor")
def add_rotor(entry: RotorEntry):
    try:
        df = pd.read_csv(FILE)
    except:
        df = pd.DataFrame(columns=["Date", "Size", "Status", "Remarks"])

    new_entry = {
        "Date": str(datetime.date.today()),
        "Size": entry.size,
        "Status": entry.status,
        "Remarks": entry.remarks
    }

    df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
    df.to_csv(FILE, index=False)

    return {"message": "Rotor added successfully"}
