#!/usr/bin/env python3
import os
import json
import requests
import feedparser
from bs4 import BeautifulSoup
import re

# Variáveis de ambiente
TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
THREAD_ID = os.environ.get("THREAD_ID")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

STATE_FILE = "last_video.json"
url_feed = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"


def load_last_video():
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
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"video_id": video_id}, f)
        print(f"[DEBUG] Último vídeo salvo: {video_id}")
    except Exception as e:
        print(f"[DEBUG] Erro ao salvar estado: {e}")


def send_telegram_message(text):
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


def is_premiere(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"[DEBUG] Erro ao acessar vídeo ({r.status_code})")
            return False

        html = r.text
        if "Premiered" in html or "UPCOMING" in html:
            print("[DEBUG] Detecção textual: vídeo é estreia ou não publicado.")
            return True

        match = re.search(r"ytInitialPlayerResponse\s*=\s*({.*?});", html)
        if match:
            data = json.loads(match.group(1))
            details = data.get("videoDetails", {})
            if details.get("isUpcoming"):
                print("[DEBUG] Vídeo é estreia (isUpcoming=true).")
                return True
    except Exception as e:
        print(f"[DEBUG] Erro ao verificar estreia: {e}")

    return False


def main():
    feed = feedparser.parse(url_feed)
    if not feed.entries:
        print("[DEBUG] Nenhum vídeo encontrado no feed.")
        return

    last_video = load_last_video()
    new_videos = []

    for entry in feed.entries:
        video_id = entry.yt_videoid
        title = entry.title
        link = entry.link

        if video_id == last_video:
            print(f"[DEBUG] Encontrado vídeo já registrado ({video_id}). Parando iteração.")
            break

        # Verifica se é estreia
        if is_premiere(video_id):
            print(f"[DEBUG] Ignorando estreia: {title}")
            continue

        # Adiciona vídeos publicados
        new_videos.append((video_id, title, link))

    if not new_videos:
        print("[DEBUG] Nenhum novo vídeo publicado encontrado.")
        return

    # Envia em ordem do mais antigo para o mais recente
    for video_id, title, link in reversed(new_videos):
        msg = f"🎥 Novo vídeo no canal!\n{title}\n{link}"
        if send_telegram_message(msg):
            print(f"[DEBUG] Notificado: {title}")

    # Salva o mais recente publicado
    save_last_video(new_videos[0][0])
    print(f"[DEBUG] Último vídeo público registrado: {new_videos[0][0]}")

if __name__ == "__main__":
    main()
