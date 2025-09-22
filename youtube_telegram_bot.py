import requests
import feedparser
import os
import json

TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
THREAD_ID = os.environ["THREAD_ID"]
CHANNEL_ID = os.environ["CHANNEL_ID"]

url_feed = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
STATE_FILE = "last_video.json"

def load_last_video():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f).get("video_id")
    return None

def save_last_video(video_id):
    with open(STATE_FILE, "w") as f:
        json.dump({"video_id": video_id}, f)

feed = feedparser.parse(url_feed)
video = feed.entries[0]
title = video.title
link = video.link
video_id = video.yt_videoid

last_video = load_last_video()

if last_video != video_id:
    msg = f"Novo vídeo no canal! 🎥\n{title}\n{link}"
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "message_thread_id": int(THREAD_ID),
            "text": msg
        }
    )
    save_last_video(video_id)
else:
    print("Nenhum vídeo novo.")
