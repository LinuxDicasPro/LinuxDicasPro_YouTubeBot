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
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f).get("video_id")
        except (json.JSONDecodeError, IOError):
            return None
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

        if "items" in data and len(data["items"]) > 0:
            return data["items"][0]["status"]["privacyStatus"]
        return "not_found"
    except requests.exceptions.RequestException as e:
        print(f"Erro ao chamar a API do YouTube: {e}")
        return "error"


def main():
    feed = feedparser.parse(url_feed)

    if not feed.entries:
        print("Nenhum vídeo encontrado no feed.")
        return

    video = feed.entries[0]
    title = video.title
    link = video.link
    video_id = video.yt_videoid

    last_video = load_last_video()

    if last_video != video_id:
        print(f"Novo vídeo detectado: {title} ({video_id})")

        video_status = check_video_status(video_id, YOUTUBE_API_KEY)
        print(f"Status do vídeo na API: {video_status}")

        save_last_video(video_id)

        if video_status == "public":
            msg = f"Novo vídeo no canal! 🎥\n{title}\n{link}"
            try:
                requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                    json={
                        "chat_id": CHAT_ID,
                        "message_thread_id": int(THREAD_ID),
                        "text": msg
                    }
                )
                print("Mensagem enviada para o Telegram.")
            except requests.exceptions.RequestException as e:
                print(f"Erro ao enviar mensagem para o Telegram: {e}")
        else:
            print("O vídeo ainda não está público. Notificação ignorada.")
    else:
        print("Nenhum vídeo novo.")


if __name__ == "__main__":
    main()
