#!/usr/bin/env python3
import os
import json
import requests
import feedparser

# Variáveis de ambiente
TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
THREAD_ID = os.environ.get("THREAD_ID")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

# URLs e arquivos
STATE_FILE = "last_video.json"
url_feed = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"


def load_last_video():
    """Carrega o último vídeo notificado"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                video_id = data.get("video_id")
                print(f"[DEBUG] Último vídeo carregado: {video_id}")
                return video_id
        except (json.JSONDecodeError, IOError) as e:
            print(f"[DEBUG] Erro lendo {STATE_FILE}: {e}")
    print("[DEBUG] Nenhum vídeo registrado ainda.")
    return None


def save_last_video(video_id):
    """Salva o último vídeo notificado"""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"video_id": video_id}, f)
        print(f"[DEBUG] Último vídeo salvo: {video_id}")
    except Exception as e:
        print(f"[DEBUG] Erro ao salvar estado: {e}")


def send_telegram_message(text):
    """Envia mensagem ao Telegram"""
    payload = {"chat_id": CHAT_ID, "text": text}
    if THREAD_ID:
        try:
            payload["message_thread_id"] = int(THREAD_ID)
        except ValueError:
            payload["message_thread_id"] = THREAD_ID

    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json=payload, timeout=15)
        r.raise_for_status()
        print("[DEBUG] Mensagem enviada para o Telegram.")
        return True
    except requests.RequestException as e:
        print(f"[DEBUG] Erro ao enviar mensagem: {e}")
        return False


def main():
    feed = feedparser.parse(url_feed)
    if not feed.entries:
        print("[DEBUG] Nenhum vídeo encontrado no feed.")
        return

    # Pega vídeo mais recente do feed
    latest = feed.entries[0]
    video_id = latest.yt_videoid
    title = latest.title
    link = latest.link

    print(f"[DEBUG] Último vídeo do feed: {title} ({video_id})")

    last_video = load_last_video()

    if last_video == video_id:
        print("[DEBUG] Nenhum vídeo novo, já notificado anteriormente.")
        return

    # Se for novo, manda pro Telegram
    msg = f"Novo vídeo no canal! 🎥\n{title}\n{link}"
    if send_telegram_message(msg):
        save_last_video(video_id)


if __name__ == "__main__":
    main()
