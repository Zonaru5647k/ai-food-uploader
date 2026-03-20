"""
AI Food Talking Bangla - YouTube Auto Uploader
Drive → Groq AI → YouTube (with thumbnail + Shorts tags)
"""

import os
import json
import random
import requests
import gspread
import textwrap
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload, MediaIoBaseUpload
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as OAuthCredentials
import io

DRIVE_FOLDER_ID        = os.environ["DRIVE_FOLDER_ID"]
SHEET_ID               = os.environ["SHEET_ID"]
DEEPSEEK_API_KEY       = os.environ["DEEPSEEK_API_KEY"]
SERVICE_ACCOUNT_JSON   = os.environ["GOOGLE_SERVICE_ACCOUNT"]
YOUTUBE_CLIENT_ID      = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET  = os.environ["YOUTUBE_CLIENT_SECRET"]
YOUTUBE_REFRESH_TOKEN  = os.environ["YOUTUBE_REFRESH_TOKEN"]

BRIGHT_COLORS = [
    ("#FF6B6B", "#FFE66D"),  # red to yellow
    ("#4ECDC4", "#FFE66D"),  # teal to yellow
    ("#FF6B9D", "#C44DFF"),  # pink to purple
    ("#F7971E", "#FFD200"),  # orange to gold
    ("#56CCF2", "#2F80ED"),  # light blue to blue
    ("#6FCF97", "#27AE60"),  # light green to green
    ("#EB5757", "#F2994A"),  # red to orange
]

SHORTS_TAGS = [
    "Shorts", "YouTubeShorts", "ViralShorts", "ShortVideo",
    "বাংলাShorts", "AIShorts", "FoodShorts", "ViralVideo",
    "TrendingShorts", "NewShorts"
]

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
        sheet.update(
            values=[[fid, fname, status, title, url,
                     datetime.utcnow().strftime("%Y-%m-%d %H:%M"), error]],
            range_name=f"A{cell.row}:G{cell.row}"
        )
    except:
        sheet.append_row([fid, fname, status, title, url,
            datetime.utcnow().strftime("%Y-%m-%d %H:%M"), error])

def generate_metadata(file_name):
    prompt = f"""তুমি একজন বাংলা YouTube ভাইরাল কন্টেন্ট এক্সপার্ট। AI food talking ভিডিও বাংলায়।
ফাইল নাম: {file_name}

শুধু JSON দাও, অন্য কিছু না, কোনো markdown নেই:
{{
  "youtube_title": "আকর্ষণীয় বাংলা টাইটেল ৬০ অক্ষরের মধ্যে ইমোজি সহ",
  "youtube_description": "বাংলায় ৩০০ শব্দের বর্ণনা ইমোজি সহ শেষে subscribe বলো",
  "youtube_hashtags": "#AIFood #বাংলাফুড #Shorts দিয়ে শুরু ২০টি ভাইরাল হ্যাশট্যাগ",
  "facebook_caption": "Facebook এর জন্য বাংলা ক্যাপশন ১৫০ শব্দ ইমোজি সহ",
  "thumbnail_text": "থাম্বনেইলের জন্য ছোট আকর্ষণীয় বাংলা টেক্সট সর্বোচ্চ ৬ শব্দ ইমোজি সহ"
}}"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1500
    }
    response = requests.post("https://api.deepseek.com/chat/completions",
                             headers=headers, json=body)
    rjson = response.json()
    print("Groq response status:", response.status_code)
    if "choices" not in rjson:
        raise Exception(f"Groq error: {rjson}")
    text = rjson["choices"][0]["message"]["content"].strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    return json.loads(text)

def create_thumbnail(title_text):
    """Create a bright colorful thumbnail 1280x720"""
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), "#FF6B6B")
    draw = ImageDraw.Draw(img)

    # Pick random bright gradient colors
    color_pair = random.choice(BRIGHT_COLORS)
    bg_color = color_pair[0]
    accent = color_pair[1]

    # Draw gradient background (simulate with bands)
    for i in range(H):
        ratio = i / H
        r1, g1, b1 = int(bg_color[1:3],16), int(bg_color[3:5],16), int(bg_color[5:7],16)
        r2, g2, b2 = int(accent[1:3],16), int(accent[3:5],16), int(accent[5:7],16)
        r = int(r1 + (r2-r1)*ratio)
        g = int(g1 + (g2-g1)*ratio)
        b = int(b1 + (b2-b1)*ratio)
        draw.line([(0,i),(W,i)], fill=(r,g,b))

    # Draw decorative circles
    draw.ellipse([(-100,-100),(300,300)], fill=(255,255,255,30))
    draw.ellipse([(1000,400),(1400,800)], fill=(255,255,255,30))

    # Draw white rounded rectangle in center
    margin = 60
    draw.rounded_rectangle([margin, margin, W-margin, H-margin],
                           radius=40, fill=(255,255,255), outline=accent, width=8)

    # Add food emojis as large text on sides
    emojis = ["🍛", "🍜", "🍚", "🥘", "🍲"]
    emoji = random.choice(emojis)

    try:
        # Try to load a font
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 120)
        font_text  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    except:
        font_large = ImageFont.load_default()
        font_text  = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Draw big emoji
    draw.text((W//2, 180), emoji, font=font_large, fill=bg_color, anchor="mm")

    # Draw AI FOOD text
    draw.text((W//2, 360), "🤖 AI FOOD", font=font_text,
              fill=bg_color, anchor="mm", stroke_width=3, stroke_fill="white")

    # Draw thumbnail title text (wrap if long)
    wrapped = textwrap.fill(title_text, width=20)
    draw.text((W//2, 530), wrapped, font=font_small,
              fill="#333333", anchor="mm", align="center")

    # Add "বাংলা" badge
    draw.rounded_rectangle([40, 580, 280, 660], radius=20, fill=bg_color)
    draw.text((160, 620), "🇧🇩 বাংলা", font=font_small,
              fill="white", anchor="mm")

    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG", quality=95)
    img_bytes.seek(0)
    return img_bytes

def upload_thumbnail(youtube, video_id, img_bytes):
    media = MediaIoBaseUpload(img_bytes, mimetype="image/jpeg", resumable=True)
    youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
    print(f"✅ Thumbnail uploaded for {video_id}")

def upload_youtube(youtube, path, meta):
    # Combine regular tags + shorts tags
    regular_tags = [t.strip("#") for t in meta["youtube_hashtags"].split() if t.startswith("#")]
    all_tags = list(set(regular_tags + SHORTS_TAGS))[:30]

    body = {
        "snippet": {
            "title": meta["youtube_title"],
            "description": meta["youtube_description"] + "\n\n" + meta["youtube_hashtags"],
            "tags": all_tags,
            "categoryId": "24",
            "defaultLanguage": "bn"
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }
    media = MediaFileUpload(path, chunksize=-1, resumable=True, mimetype="video/*")
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = req.next_chunk()
    video_id = response["id"]
    return f"https://youtu.be/{video_id}", meta["youtube_title"], video_id

def main():
    print(f"🚀 Run started: {datetime.utcnow()} UTC")
    creds   = get_creds()
    drive   = build("drive", "v3", credentials=creds)
    youtube = get_youtube()
    sheet   = get_sheet()

    video = get_pending_video(drive, sheet)
    if not video:
        print("🎉 All videos uploaded!")
        return

    fid, fname = video["id"], video["name"]
    print(f"📹 Processing: {fname}")
    mark(sheet, fid, fname, "processing")

    try:
        # 1. Generate metadata
        meta  = generate_metadata(fname)

        # 2. Download video
        local = f"/tmp/{fname}"
        req   = drive.files().get_media(fileId=fid)
        with open(local, "wb") as f:
            dl = MediaIoBaseDownload(f, req)
            done = False
            while not done:
                _, done = dl.next_chunk()

        # 3. Upload to YouTube
        url, title, video_id = upload_youtube(youtube, local, meta)

        # 4. Create and upload thumbnail
        thumb_text = meta.get("thumbnail_text", title[:30])
        img_bytes  = create_thumbnail(thumb_text)
        upload_thumbnail(youtube, video_id, img_bytes)

        # 5. Log success
        mark(sheet, fid, fname, "uploaded", title, url)
        print(f"✅ Done! {title} → {url}")

    except Exception as e:
        print(f"❌ Error: {e}")
        mark(sheet, fid, fname, "failed", error=str(e))
        raise

if __name__ == "__main__":
    main()
