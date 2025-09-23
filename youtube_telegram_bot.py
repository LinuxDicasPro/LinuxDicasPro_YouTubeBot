import requests
import feedparser
import os
import json

TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
THREAD_ID = os.environ["THREAD_ID"]

CHANNEL_ID = os.environ["CHANNEL_ID"]
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]

url_feed = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
STATE_FILE = "last_video.json"
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/videos"

def load_last_video():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f).get("video_id")
    return None

def save_last_video(video_id):
    with open(STATE_FILE, "w") as f:
        json.dump({"video_id": video_id}, f)

def check_video_status(video_id, api_key):
    params = {
        "part": "status",
        "id": video_id,
        "key": api_key
    }
    try:
        response = requests.get(YOUTUBE_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        print("--- Resposta completa da API do YouTube ---")
        print(json.dumps(data, indent=2))
        print("------------------------------------------")

        if "items" in data and len(data["items"]) > 0:
            status = data["items"][0]["status"]
            return status["privacyStatus"]
        return "not_found"
    except requests.exceptions.RequestException as e:
        print(f"Erro ao chamar a API do YouTube: {e}")
        return "error"

feed = feedparser.parse(url_feed)

if not feed.entries:
    print("Nenhum vídeo encontrado na feed.")
else:
    video = feed.entries[0]
    title = video.title
    link = video.link
    video_id = video.yt_videoid

    last_video = load_last_video()

    if last_video != video_id:
        print(f"Novo vídeo detectado: {title} ({video_id})")

        video_status = check_video_status(video_id, YOUTUBE_API_KEY)
        print(f"Status do vídeo na API: {video_status}")

        if video_status == "public":
            msg = f"Novo vídeo no canal! 🎥\n{title}\n{link}"
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={
                    "chat_id": CHAT_ID,
                    "message_thread_id": int(THREAD_ID),
                    "text": msg
                }
            )
            print("Mensagem enviada para o Telegram.")
            save_last_video(video_id)
        else:
            print("O vídeo ainda não está público. Não enviando notificação.")
    else:
        print("Nenhum vídeo novo.")
