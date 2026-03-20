"""
AI Food Talking Bangla - YouTube Auto Uploader
Runs on GitHub Actions every 2 hours, uploads 1 video
Drive → Gemini AI → YouTube → Log to Google Sheets
"""

import os
import json
import random
import requests
import gspread
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as OAuthCredentials

DRIVE_FOLDER_ID        = os.environ["DRIVE_FOLDER_ID"]
SHEET_ID               = os.environ["SHEET_ID"]
GEMINI_API_KEY         = os.environ["GEMINI_API_KEY"]
SERVICE_ACCOUNT_JSON   = os.environ["GOOGLE_SERVICE_ACCOUNT"]
YOUTUBE_CLIENT_ID      = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET  = os.environ["YOUTUBE_CLIENT_SECRET"]
YOUTUBE_REFRESH_TOKEN  = os.environ["YOUTUBE_REFRESH_TOKEN"]

def get_creds():
    info = json.loads(SERVICE_ACCOUNT_JSON)
    return Credentials.from_service_account_info(info, scopes=[
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/spreadsheets"
    ])

def get_youtube():
    creds = OAuthCredentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token"
    )
    return build("youtube", "v3", credentials=creds)

def get_sheet():
    gc = gspread.authorize(get_creds())
    sh = gc.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet("Tracker")
    except:
        ws = sh.add_worksheet("Tracker", rows=5000, cols=8)
        ws.append_row(["File ID","File Name","Status","Title","YouTube URL","Uploaded At","Error"])
    return ws

def get_pending_video(drive_service, sheet):
    records = sheet.get_all_records()
    done_ids = {r["File ID"] for r in records if r["Status"] in ("uploaded","failed")}
    results = drive_service.files().list(
        q=f"'{DRIVE_FOLDER_ID}' in parents and mimeType contains 'video/' and trashed=false",
        pageSize=500, fields="files(id,name)"
    ).execute()
    files = results.get("files", [])
    random.shuffle(files)
    for f in files:
        if f["id"] not in done_ids:
            return f
    return None

def mark(sheet, fid, fname, status, title="", url="", error=""):
    try:
        cell = sheet.find(fid)
        sheet.update(f"A{cell.row}:G{cell.row}",
            [[fid, fname, status, title, url,
              datetime.utcnow().strftime("%Y-%m-%d %H:%M"), error]])
    except:
        sheet.append_row([fid, fname, status, title, url,
            datetime.utcnow().strftime("%Y-%m-%d %H:%M"), error])

def generate_metadata(file_name):
    prompt = f"""তুমি একজন বাংলা YouTube ভাইরাল কন্টেন্ট এক্সপার্ট। AI food talking ভিডিও বাংলায়।
ফাইল নাম: {file_name}

শুধু JSON দাও, অন্য কিছু না:
{{
  "youtube_title": "আকর্ষণীয় বা
