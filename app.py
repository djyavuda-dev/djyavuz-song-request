"""
Spotify Song Request Kiosk
---------------------------
Guests scan a QR code -> land on a search page -> request a song.
Only YOUR (the DJ's) Spotify token ever touches the Spotify API.
Guests never authenticate with Spotify and never see your other playlists.

One-time setup (you, the DJ):
  1. Create an app at https://developer.spotify.com/dashboard
     - Add redirect URI: http://localhost:8888/callback (or your real domain + /callback)
  2. Copy the Client ID / Client Secret into a .env file (see .env.example)
  3. Run this app, visit /login once, log in with YOUR Spotify account, approve access.
     -> This creates a .cache file with your refresh token. Guests never see this step.
  4. Set TARGET_PLAYLIST_ID in .env to the playlist you want guests adding to.
  5. Deploy somewhere with a stable URL (Render, Railway, a VPS, etc.) and point the
     QR code at that URL. Keep .cache and .env OFF any public repo.
"""

import os
import time
from collections import defaultdict, deque

from flask import Flask, request, jsonify, render_template, redirect
from spotipy import Spotify, SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["SPOTIFY_CLIENT_ID"]
CLIENT_SECRET = os.environ["SPOTIFY_CLIENT_SECRET"]
REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
TARGET_PLAYLIST_ID = os.environ["TARGET_PLAYLIST_ID"]  # the ONLY playlist this app can touch

# Scope is deliberately narrow: just enough to add tracks. No account-read,
# no delete, no follow, no library access.
SCOPE = "playlist-modify-public playlist-modify-private"

# On a free host (Render, Railway free tier, etc.) the filesystem is wiped
# every time the service restarts or spins down from inactivity — so we
# never rely on a cache FILE surviving. Instead, once you log in via /login,
# the refresh token is printed so you can save it as the SPOTIFY_REFRESH_TOKEN
# environment variable on your host. From then on the app rebuilds a fresh
# access token from that env var on every restart, no re-login needed.
oauth = SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE,
    cache_handler=None,
    open_browser=False,
)

app = Flask(__name__)

_token_cache = {}  # in-memory only, rebuilt from env var on cold start

# --- simple in-memory guardrails (fine for a single-event kiosk) ---
REQUEST_COOLDOWN_SECONDS = 45           # per IP, between requests
RECENT_TRACK_WINDOW_SECONDS = 60 * 20   # don't re-add the same track twice in 20 min
_last_request_by_ip = {}
_recently_added_tracks = deque()  # (track_id, timestamp)


def get_spotify_client():
    """Returns a Spotify client, refreshing the access token as needed.

    Refresh token source, in order:
      1. In-memory cache from this same running process (fast path).
      2. SPOTIFY_REFRESH_TOKEN env var — set this once on your host after
         your first /login, and it survives restarts/spin-downs.
    """
    token_info = _token_cache.get("token")

    if not token_info:
        refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN")
        if not refresh_token:
            raise RuntimeError("No DJ token available — visit /login once first.")
        token_info = oauth.refresh_access_token(refresh_token)
        _token_cache["token"] = token_info

    if oauth.is_token_expired(token_info):
        token_info = oauth.refresh_access_token(token_info["refresh_token"])
        _token_cache["token"] = token_info

    return Spotify(auth=token_info["access_token"])


def is_recently_added(track_id: str) -> bool:
    now = time.time()
    while _recently_added_tracks and now - _recently_added_tracks[0][1] > RECENT_TRACK_WINDOW_SECONDS:
        _recently_added_tracks.popleft()
    return any(tid == track_id for tid, _ in _recently_added_tracks)


# ---------- DJ-only one-time setup routes ----------

@app.route("/login")
def login():
    return redirect(oauth.get_authorize_url())


@app.route("/callback")
def callback():
    code = request.args.get("code")
    token_info = oauth.get_access_token(code, as_dict=True, check_cache=False)
    _token_cache["token"] = token_info
    refresh_token = token_info["refresh_token"]
    return (
        "<p>Spotify bağlantısı kuruldu.</p>"
        "<p>Şimdi hosting panelinden şu ortam değişkenini ekle, sonra bu sayfayı kapat:</p>"
        f"<p><b>SPOTIFY_REFRESH_TOKEN</b> = <code>{refresh_token}</code></p>"
        "<p>Bunu ekledikten sonra servis kaç kere yeniden başlarsa başlasın "
        "tekrar giriş yapmana gerek kalmaz.</p>"
    )


# ---------- Guest-facing routes ----------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search")
def search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    sp = get_spotify_client()
    results = sp.search(q=query, type="track", limit=8)
    tracks = [
        {
            "id": t["id"],
            "uri": t["uri"],
            "name": t["name"],
            "artist": ", ".join(a["name"] for a in t["artists"]),
            "album_art": (t["album"]["images"][-1]["url"] if t["album"]["images"] else None),
        }
        for t in results["tracks"]["items"]
    ]
    return jsonify(tracks)


@app.route("/api/request", methods=["POST"])
def request_song():
    ip = request.remote_addr
    now = time.time()

    last = _last_request_by_ip.get(ip, 0)
    if now - last < REQUEST_COOLDOWN_SECONDS:
        wait = int(REQUEST_COOLDOWN_SECONDS - (now - last))
        return jsonify({"ok": False, "error": f"Az önce istek gönderdin, {wait} saniye bekle."}), 429

    data = request.get_json(force=True)
    track_id = data.get("id")
    track_uri = data.get("uri")
    if not track_id or not track_uri:
        return jsonify({"ok": False, "error": "Geçersiz şarkı."}), 400

    if is_recently_added(track_id):
        return jsonify({"ok": False, "error": "Bu şarkı zaten listede — başka bir şey dene."}), 409

    sp = get_spotify_client()
    # This is the ONLY write operation this app ever performs, and it can
    # only ever touch TARGET_PLAYLIST_ID — nothing else on the DJ's account.
    sp.playlist_add_items(TARGET_PLAYLIST_ID, [track_uri])

    _last_request_by_ip[ip] = now
    _recently_added_tracks.append((track_id, now))

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888, debug=True)
