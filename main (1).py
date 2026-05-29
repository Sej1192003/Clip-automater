import feedparser
import yt_dlp
import json
import os
import smtplib
import schedule
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─────────────────────────────────────────────
# CONFIG — fill these in
# ─────────────────────────────────────────────

EMAIL_SENDER = os.environ.get("EMAIL_SENDER")       # your gmail
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")   # gmail app password
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")   # where digest gets sent

# ─────────────────────────────────────────────
# YOUR 5 FINANCE CREATORS (YouTube Channel IDs)
# ─────────────────────────────────────────────

CREATORS = [
    {"name": "Codie Sanchez",   "channel_id": "UC8gBySB1s3oBTLmgC8MTRSA"},
    {"name": "Graham Stephan",  "channel_id": "UCV6KDgJskWaEckne5aPA0aQ"},
    {"name": "George Kamel",    "channel_id": "UCdBjKAVIoGhpFNDTnqXJzgQ"},
    {"name": "Andrei Jikh",     "channel_id": "UCGy7SkBjcIAgTiwkXEtPnYg"},
    {"name": "Mark Tilbury",    "channel_id": "UCIBgYfDjtWlbJhg--Z4sOgQ"},
]

DOWNLOAD_DIR = "downloads"
QUEUE_FILE = "clip_queue.json"
MAX_VIDEOS_PER_CREATOR = 5       # how many recent videos to check per creator
MIN_VIRALITY_SCORE = 2           # out of 10, skip anything below this

# ─────────────────────────────────────────────
# STEP 1 — FETCH LATEST VIDEOS VIA RSS
# ─────────────────────────────────────────────

def fetch_latest_videos(channel_id, max_results=MAX_VIDEOS_PER_CREATOR):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    feed = feedparser.parse(url)
    videos = []
    for entry in feed.entries[:max_results]:
        published = datetime(*entry.published_parsed[:6])
        # only grab videos from last 7 days
        if datetime.now() - published > timedelta(days=7):
            continue
        videos.append({
            "title": entry.title,
            "url": entry.link,
            "published": published.strftime("%Y-%m-%d"),
            "video_id": entry.yt_videoid,
        })
    return videos

# ─────────────────────────────────────────────
# STEP 2 — SCORE VIRALITY (simple heuristic)
# ─────────────────────────────────────────────

VIRAL_KEYWORDS = [
    # money & wealth
    "money", "rich", "broke", "wealth", "millionaire", "billionaire",
    "income", "salary", "earnings", "profit", "loss", "cash",
    # investing
    "invest", "stock", "market", "bond", "crypto", "bitcoin", "etf",
    "portfolio", "dividend", "returns", "interest", "rate",
    # real estate & business
    "real estate", "property", "business", "entrepreneur", "startup",
    "side hustle", "passive income", "asset", "liability",
    # debt & spending
    "debt", "loan", "mortgage", "credit", "budget", "savings",
    "afford", "expensive", "cheap", "cost", "price",
    # emotion/urgency triggers
    "secret", "truth", "warning", "mistake", "never", "always", "stop",
    "start", "why", "how", "breaking", "crisis", "problem", "future",
    "massive", "world", "every", "biggest", "worst", "best",
    # career & life
    "fired", "quit", "retire", "freedom", "financial freedom", "job",
    "career", "work", "boss",
    # clickbait patterns
    "nobody tells you", "how i", "i made", "you need",
    "don't", "do this", "avoid", "here's why"
]

def score_virality(title):
    title_lower = title.lower()
    score = 0
    matched = []
    for keyword in VIRAL_KEYWORDS:
        if keyword in title_lower:
            score += 1
            matched.append(keyword)
    # bonus for questions or numbers in title
    if "?" in title:
        score += 1
    if any(char.isdigit() for char in title):
        score += 1
    # cap at 10
    score = min(score, 10)
    return score, matched

# ─────────────────────────────────────────────
# STEP 3 — DOWNLOAD TOP SCORING VIDEOS
# ─────────────────────────────────────────────

def download_video(url, output_dir=DOWNLOAD_DIR):
    os.makedirs(output_dir, exist_ok=True)
    ydl_opts = {
        "format": "bestvideo[height<=1080]+bestaudio/best",
        "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).replace(".webm", ".mp4").replace(".mkv", ".mp4")
            return filename
    except Exception as e:
        print(f"Download failed for {url}: {e}")
        return None

# ─────────────────────────────────────────────
# STEP 4 — SAVE TO QUEUE
# ─────────────────────────────────────────────

def load_queue():
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, "r") as f:
            return json.load(f)
    return []

def save_queue(queue):
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2)

def already_in_queue(video_id, queue):
    return any(item["video_id"] == video_id for item in queue)

# ─────────────────────────────────────────────
# STEP 5 — SEND DAILY EMAIL DIGEST
# ─────────────────────────────────────────────

def send_digest(new_clips):
    if not EMAIL_SENDER or not EMAIL_RECEIVER:
        print("Email not configured — skipping digest")
        return

    subject = f"🎬 Clip Automator — {len(new_clips)} new clips queued ({datetime.now().strftime('%b %d')})"

    body = "Here are today's clips queued for review:\n\n"
    for i, clip in enumerate(new_clips, 1):
        body += f"{i}. [{clip['creator']}] {clip['title']}\n"
        body += f"   Score: {clip['score']}/10 | Keywords: {', '.join(clip['keywords'])}\n"
        body += f"   URL: {clip['url']}\n"
        body += f"   Status: Queued for Opus Clip → TikTok + IG\n\n"

    body += "\nReply to this email or check clip_queue.json to remove any before they post.\n"
    body += "Everything else goes live automatically within 24hrs.\n"

    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print(f"✅ Digest sent — {len(new_clips)} clips")
    except Exception as e:
        print(f"Email failed: {e}")

# ─────────────────────────────────────────────
# MAIN PIPELINE — runs daily
# ─────────────────────────────────────────────

def run_pipeline():
    print(f"\n🚀 Pipeline started — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    queue = load_queue()
    new_clips = []

    for creator in CREATORS:
        print(f"\n📡 Checking {creator['name']}...")
        videos = fetch_latest_videos(creator["channel_id"])

        for video in videos:
            if already_in_queue(video["video_id"], queue):
                print(f"   ⏭️  Already queued: {video['title'][:50]}")
                continue

            score, keywords = score_virality(video["title"])
            print(f"   Score {score}/10 — {video['title'][:50]}")

            if score < MIN_VIRALITY_SCORE:
                print(f"   ❌ Score too low, skipping")
                continue

            print(f"   ⬇️  Downloading...")
            filepath = download_video(video["url"])

            clip_entry = {
                "creator": creator["name"],
                "title": video["title"],
                "url": video["url"],
                "video_id": video["video_id"],
                "published": video["published"],
                "score": score,
                "keywords": keywords,
                "filepath": filepath,
                "status": "queued",
                "added": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }

            queue.append(clip_entry)
            new_clips.append(clip_entry)
            print(f"   ✅ Added to queue")

    save_queue(queue)
    print(f"\n📋 Queue updated — {len(new_clips)} new clips added")

    if new_clips:
        send_digest(new_clips)
    else:
        print("No new clips found today")

# ─────────────────────────────────────────────
# SCHEDULER — runs pipeline once per day
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 Clip Automator started")
    run_pipeline()  # run immediately on start

    schedule.every().day.at("09:00").do(run_pipeline)  # then daily at 9am

    while True:
        schedule.run_pending()
        time.sleep(60)
