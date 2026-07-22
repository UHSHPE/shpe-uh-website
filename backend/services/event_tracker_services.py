import os
import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()
CREDENTIALS = os.getenv("CREDENTIALS")
SHEET_ID = os.getenv("SHEET_ID")

scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(CREDENTIALS, scopes=scopes)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID)

header = sheet.sheet1.row_values(1)
print(header)