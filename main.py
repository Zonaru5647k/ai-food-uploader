import os, json, random, requests, gspread, textwrap, io
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload, MediaIoBaseUpload
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as OAuthCredentials

DRIVE_FOLDER_ID       = os.environ["DRIVE_FOLDER_ID"]
SHEET_ID              = os.environ["SHEET_ID"]
OPENROUTER_API_KEY    = os.environ["OPENROUTER_API_KEY"]
SERVICE_ACCOUNT_JSON  = os.environ["GOOGLE_SERVICE_ACCOUNT"]
YOUTUBE_CLIENT_ID     = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
YOUTUBE_REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]

SHORTS_TAGS = ["Shorts","YouTubeShorts","ViralShorts","ShortVideo",
               "বাংলাShorts","AIShorts","FoodShorts","ViralVideo",
               "TrendingShorts","NewShorts"]

BRIGHT_COLORS = [
    ("#FF6B6B","#FFE66D"),("#4ECDC4","#FFE66D"),("#FF6B9D","#C44DFF"),
    ("#F7971E","#FFD200"),("#56CCF2","#2F80ED"),("#6FCF97","#27AE60"),
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

def get_pending_video(drive, sheet):
    records = sheet.get_all_records()
    done_ids = {r["File ID"] for r in records if r["Status"] in ("uploaded","failed")}
    results = drive.files().list(
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

def generate_metadata(fname):
    prompt = f"""তুমি একজন বাংলা YouTube ভাইরাল কন্টেন্ট এক্সপার্ট। AI food talking ভিডিও বাংলায়।
ফাইল নাম: {fname}

শুধু JSON দাও, কোনো markdown বা অন্য কিছু না:
{{
  "youtube_title": "আকর্ষণীয় বাংলা টাইটেল ৬০ অক্ষরের মধ্যে ইমোজি সহ",
  "youtube_description": "বাংলায় ৩০০ শব্দের বর্ণনা ইমোজি সহ শেষে subscribe বলো",
  "youtube_hashtags": "#AIFood #বাংলাফুড #Shorts দিয়ে শুরু ২০টি ভাইরাল হ্যাশট্যাগ",
  "facebook_caption": "Facebook এর জন্য বাংলা ক্যাপশন ১৫০ শব্দ ইমোজি সহ",
  "thumbnail_text": "থাম্বনেইলের জন্য ছোট বাংলা টেক্সট সর্বোচ্চ ৫ শব্দ ইমোজি সহ"
}}"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com",
        "X-Title": "AI Food Uploader"
    }
    body = {
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1500
    }
    r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                      headers=headers, json=body)
    rj = r.json()
    print("OpenRouter status:", r.status_code)
    if "choices" not in rj:
        raise Exception(f"OpenRouter error: {rj}")
    text = rj["choices"][0]["message"]["content"].strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())

def create_thumbnail(thumb_text):
    W, H = 1280, 720
    c1, c2 = random.choice(BRIGHT_COLORS)
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    r1,g1,b1 = int(c1[1:3],16),int(c1[3:5],16),int(c1[5:7],16)
    r2,g2,b2 = int(c2[1:3],16),int(c2[3:5],16),int(c2[5:7],16)
    for i in range(H):
        ratio = i/H
        r=int(r1+(r2-r1)*ratio); g=int(g1+(g2-g1)*ratio); b=int(b1+(b2-b1)*ratio)
        draw.line([(0,i),(W,i)], fill=(r,g,b))
    draw.rounded_rectangle([50,50,W-50,H-50], radius=40,
                           fill=(255,255,255), outline=c2, width=8)
    try:
        f_big  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 110)
        f_mid  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 65)
        f_small= ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 45)
    except:
        f_big = f_mid = f_small = ImageFont.load_default()
    draw.text((W//2, 200), "🍛", font=f_big, fill=c1, anchor="mm")
    draw.text((W//2, 370), "AI FOOD", font=f_mid,
              fill=c1, anchor="mm", stroke_width=3, stroke_fill="white")
    wrapped = textwrap.fill(thumb_text, width=22)
    draw.text((W//2, 530), wrapped, font=f_small,
              fill="#222222", anchor="mm", align="center")
    draw.rounded_rectangle([50,610,260,680], radius=20, fill=c1)
    draw.text((155,645), "Bangla AI Food", font=f_small, fill="white", anchor="mm")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf

def upload_youtube(youtube, path, meta):
    tags = [t.strip("#") for t in meta["youtube_hashtags"].split() if t.startswith("#")]
    all_tags = list(set(tags + SHORTS_TAGS))[:30]
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
    vid = response["id"]
    return f"https://youtu.be/{vid}", meta["youtube_title"], vid

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
        meta  = generate_metadata(fname)
        local = f"/tmp/{fname}"
        req   = drive.files().get_media(fileId=fid)
        with open(local, "wb") as f:
            dl = MediaIoBaseDownload(f, req)
            done = False
            while not done:
                _, done = dl.next_chunk()
        url, title, vid = upload_youtube(youtube, local, meta)
        thumb_text = meta.get("thumbnail_text", title[:30])
        buf = create_thumbnail(thumb_text)
        media = MediaIoBaseUpload(buf, mimetype="image/jpeg", resumable=True)
        youtube.thumbnails().set(videoId=vid, media_body=media).execute()
        print("✅ Thumbnail uploaded!")
        mark(sheet, fid, fname, "uploaded", title, url)
        print(f"✅ Done! {title} → {url}")
    except Exception as e:
        print(f"❌ Error: {e}")
        mark(sheet, fid, fname, "failed", error=str(e))
        raise

if __name__ == "__main__":
    main()
