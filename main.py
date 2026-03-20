"""
AI Food Talking Bangla - YouTube Auto Uploader
Runs on GitHub Actions every 2 hours, uploads 1 video
Drive → Gemini AI → YouTube → Log to Google Sheets
"""

import os
import json
import pickle
import random
import gspread
import requests
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google.oauth2.service_account import Credentials

DRIVE_FOLDER_ID      = os.environ["DRIVE_FOLDER_ID"]
SHEET_ID             = os.environ["SHEET_ID"]
GEMINI_API_KEY       = os.environ["GEMINI_API_KEY"]
SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT"]
YOUTUBE_TOKEN_PICKLE = os.environ["YOUTUBE_TOKEN_PICKLE"]

def get_creds():
    info = json.loads(SERVICE_ACCOUNT_JSON)
    return Credentials.from_service_account_info(info, scopes=[
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/spreadsheets"
    ])

def get_youtube():
    token_bytes = bytes.fromhex(YOUTUBE_TOKEN_PICKLE)
    creds = pickle.loads(token_bytes)
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
  "youtube_title": "আকর্ষণীয় বাংলা টাইটেল ৬০ অক্ষরের মধ্যে ইমোজি সহ",
  "youtube_description": "বাংলায় ৩০০ শব্দের বর্ণনা ইমোজি সহ শেষে subscribe বলো",
  "youtube_hashtags": "#AIFood #বাংলাফুড দিয়ে শুরু ২০টি ভাইরাল হ্যাশট্যাগ",
  "facebook_caption": "Facebook এর জন্য বাংলা ক্যাপশন ১৫০ শব্দ ইমোজি সহ"
}}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(url, json=body)
    text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    text = text.strip().strip("```json").strip("```").strip()
    return json.loads(text)

def upload_youtube(youtube, path, meta):
    tags = [t.strip("#") for t in meta["youtube_hashtags"].split() if t.startswith("#")]
    body = {
        "snippet": {
            "title": meta["youtube_title"],
            "description": meta["youtube_description"] + "\n\n" + meta["youtube_hashtags"],
            "tags": tags[:30],
            "categoryId": "24",
            "defaultLanguage": "bn"
        },
        "status": {"privacyStatus": "public", "s
