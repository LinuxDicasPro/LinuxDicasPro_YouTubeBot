#!/usr/bin/env python3
"""
youtube_telegram_bot.py
Versão robusta: evita reposts, trata premieres/não listados e tenta persistir estado
no repositório (opcional) quando executado no GitHub Actions com token.
"""

import os
import json
import requests
import feedparser
import subprocess
from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile

# --- Config ---
TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
THREAD_ID = os.environ.get("THREAD_ID")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

# Arquivo de estado — coloca no mesmo diretório do script (mais previsível)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "last_video.json")

YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/videos"
URL_FEED = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"

# Quantos dias manter pending antes de limpar (evita crescimento infinito)
PENDING_TTL_DAYS = 30


# --- Helpers de estado ---
def load_state():
    """Carrega estado: { 'sent': [...], 'pending': {video_id: {...}} }"""
    if not os.path.exists(STATE_FILE):
        return {"sent": [], "pending": {}}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
            # garantir chaves
            state.setdefault("sent", [])
            state.setdefault("pending", {})
            return state
    except (json.JSONDecodeError, IOError) as e:
        print(f"Erro lendo {STATE_FILE}: {e} — criando estado novo.")
        return {"sent": [], "pending": {}}


def atomic_save_state(state):
    """Salva estado de forma atômica e tenta commitar ao repo se token existir."""
    # escrever atômico
    tmp = NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=BASE_DIR)
    try:
        json.dump(state, tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()
        os.replace(tmp.name, STATE_FILE)
        print(f"Estado salvo em {STATE_FILE}")
    except Exception as e:
        print(f"Falha ao salvar estado localmente: {e}")
        try:
            if os.path.exists(tmp.name):
                os.remove(tmp.name)
        except:
            pass

    # Se existir token e repo, tenta commitar (opcional)
    commit_state_to_repo_if_possible(STATE_FILE)


def commit_state_to_repo_if_possible(state_file_path):
    """
    Se estiver rodando no GitHub Actions (ou tiver GITHUB_TOKEN / PERSONAL_TOKEN),
    tenta commitar o arquivo de estado no repositório para persistência entre runs.
    Requer:
      - env GITHUB_REPOSITORY (owner/repo)
      - env GITHUB_TOKEN (ou GITHUB_PUSH_TOKEN) com permissão de escrita em contents
    OBS: se não estiver disponível, apenas ignora.
    """
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PUSH_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        # nada a fazer
        return False

    # configure git user
    try:
        subprocess.run(["git", "config", "--local", "user.email", "action@github.com"], check=True)
        subprocess.run(["git", "config", "--local", "user.name", "github-actions[bot]"], check=True)
    except Exception as exc:
        print("Aviso: não foi possível configurar git localmente:", exc)
        # continuar tentando

    try:
        # Add file
        subprocess.run(["git", "add", state_file_path], check=True)

        # Commit só se houver mudanças
        # git diff --cached --quiet retorna 0 se sem diferenças
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if diff.returncode == 0:
            print("Sem mudanças para commitar no estado.")
            return True

        commit_message = "chore(bot): update last_video state"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)

        # Ajusta origin para usar token (URL com token)
        remote_url = f"https://x-access-token:{token}@github.com/{repo}.git"
        subprocess.run(["git", "remote", "set-url", "origin", remote_url], check=True)

        # descobrir branch atual
        branch_proc = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
        branch = branch_proc.stdout.strip() or "main"

        # Push
        subprocess.run(["git", "push", "origin", f"HEAD:{branch}"], check=True)
        print("Estado comitado e push realizado com sucesso.")
        return True
    except subprocess.CalledProcessError as e:
        print("Falha no commit/push do estado (git):", e)
        return False
    except Exception as e:
        print("Erro inesperado ao commitar estado:", e)
        return False


# --- YouTube / Telegram helpers ---
def check_video_status(video_id):
    params = {"part": "status", "id": video_id, "key": YOUTUBE_API_KEY}
    try:
        r = requests.get(YOUTUBE_API_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        # debug opcional
        # print(json.dumps(data, indent=2, ensure_ascii=False))
        if "items" in data and len(data["items"]) > 0:
            return data["items"][0]["status"].get("privacyStatus", "unknown")
        return "not_found"
    except Exception as e:
        print("Erro ao consultar YouTube API:", e)
        return "error"


def telegram_send_message(text):
    if not TOKEN or not CHAT_ID:
        print("TOKEN ou CHAT_ID não configurados. Ignorando envio.")
        return False
    payload = {
        "chat_id": CHAT_ID,
        "text": text
    }
    if THREAD_ID:
        try:
            payload["message_thread_id"] = int(THREAD_ID)
        except ValueError:
            payload["message_thread_id"] = THREAD_ID

    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json=payload, timeout=15)
        r.raise_for_status()
        print("Mensagem enviada ao Telegram.")
        return True
    except Exception as e:
        print("Erro ao enviar Telegram:", e)
        return False


# --- util ---
def iso_now():
    return datetime.utcnow().isoformat() + "Z"


def cleanup_pending(pending):
    """Remove pendings muito antigos"""
    cutoff = datetime.utcnow() - timedelta(days=PENDING_TTL_DAYS)
    keys_to_remove = []
    for vid, meta in pending.items():
        first_seen = meta.get("first_seen")
        if not first_seen:
            continue
        try:
            dt = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
            if dt < cutoff:
                keys_to_remove.append(vid)
        except Exception:
            # se parse falhar, remove
            keys_to_remove.append(vid)
    for k in keys_to_remove:
        pending.pop(k, None)


# --- main ---
def main():
    # validação rápida
    if not CHANNEL_ID:
        print("CHANNEL_ID não definido. Abortando.")
        return

    feed = feedparser.parse(URL_FEED)
    if not feed.entries:
        print("Nenhum vídeo encontrado no feed.")
        return

    latest = feed.entries[0]
    video_id = getattr(latest, "yt_videoid", None)
    title = getattr(latest, "title", "")
    link = getattr(latest, "link", "")

    if not video_id:
        print("Não foi possível obter video_id do feed.")
        return

    state = load_state()
    sent = set(state.get("sent", []))
    pending = state.get("pending", {})

    # Limpeza de pendings antigos
    cleanup_pending(pending)

    # Se já foi enviado antes, não faz nada
    if video_id in sent:
        print(f"Vídeo {video_id} já foi enviado anteriormente — nada a fazer.")
        # ainda mantemos o arquivo de estado atualizado (pois pode ter sido limpo)
        state["sent"] = list(sent)
        state["pending"] = pending
        atomic_save_state(state)
        return

    # Se está em pending, checamos de novo (pode ter ficado público)
    video_status = check_video_status(video_id)
    print(f"Status do vídeo {video_id}: {video_status}")

    now = iso_now()

    if video_status == "public":
        # enviar e marcar como sent
        message = f"Novo vídeo no canal! 🎥\n{title}\n{link}"
        success = telegram_send_message(message)
        if success:
            sent.add(video_id)
            if video_id in pending:
                pending.pop(video_id, None)
            state["sent"] = list(sent)
            state["pending"] = pending
            atomic_save_state(state)
        else:
            print("Erro ao enviar mensagem — não marcando como enviado para tentar novamente mais tarde.")
            # se falhou no envio, manter como pending para tentar depois
            pending[video_id] = {
                "first_seen": pending.get(video_id, {}).get("first_seen", now),
                "last_seen": now,
                "last_status": video_status,
            }
            state["pending"] = pending
            atomic_save_state(state)
    elif video_status in ("private", "unlisted", "not_found", "error"):
        # Marca como pending (ou atualiza) para não repostar todo dia,
        # e aguarda futuras execuções para checar se virou public.
        prev = pending.get(video_id)
        if not prev:
            pending[video_id] = {
                "first_seen": now,
                "last_seen": now,
                "last_status": video_status,
            }
            print(f"Vídeo {video_id} adicionado ao pending (status={video_status}).")
        else:
            prev["last_seen"] = now
            prev["last_status"] = video_status
            pending[video_id] = prev
            print(f"Vídeo {video_id} ainda pending (status={video_status}). Atualizado.")
        state["sent"] = list(sent)
        state["pending"] = pending
        atomic_save_state(state)
    else:
        print("Status inesperado:", video_status)
        # salvar estado só pra garantir
        state["sent"] = list(sent)
        state["pending"] = pending
        atomic_save_state(state)


if __name__ == "__main__":
    main()
