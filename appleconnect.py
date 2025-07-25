from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd

app = FastAPI()

# Load your existing DataFrame or data logic
df = pd.read_csv("https://docs.google.com/spreadsheets/d/10Etsj7QwCSR1hXcAcC1w6bWwNxQKACSw5VLDS2JXbNk/edit?usp=sharing")  # Or your gsheet data

class ChatRequest(BaseModel):
    query: str

@app.post("/chatbot")
def chatbot_endpoint(req: ChatRequest):
    from your_chatbot_module import run_chatbot_logic  # reuse your existing logic
    result = run_chatbot_logic(req.query, df)
    return {"response": str(result)}
