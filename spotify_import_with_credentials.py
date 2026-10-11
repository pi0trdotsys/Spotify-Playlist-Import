import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
import time
import sys
from dotenv import load_dotenv
import os

load_dotenv()

CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
CSV_FILE      = os.getenv("CSV_FILE", "Liked_Songs.csv")
SCOPE = "user-library-modify user-library-read"
BATCH_SIZE = 40  # limit PUT /me/library

# Od marca 2026 aplikacje w trybie Development zapisują utwory przez PUT /me/library.
# None = jeszcze nie sprawdzono, False = endpoint niedostępny, wracamy do PUT /me/tracks.
use_library_endpoint = None

def load_csv(path):
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        print(f"❌ Nie znaleziono pliku: {path}")
        sys.exit(1)
    uri_col = None
    for col in df.columns:
        if "uri" in col.lower() and "track" in col.lower():
            uri_col = col
            break
        if col.strip().lower() == "spotify uri":
            uri_col = col
            break
    if uri_col is None:
        print("❌ Nie znaleziono kolumny URI.")
        print(f"   Kolumny: {list(df.columns)}")
        sys.exit(1)
    df = df.dropna(subset=[uri_col])
    print(f"✅ Wczytano {len(df)} utworów.")
    return df, uri_col

def get_already_liked(sp):
    print("🔍 Sprawdzam już polubione...")
    liked = set()
    results = sp.current_user_saved_tracks(limit=50)
    while results:
        for item in results["items"]:
            liked.add(item["track"]["uri"])
        results = sp.next(results) if results["next"] else None
    print(f"   Już polubionych: {len(liked)}")
    return liked

def explain(error):
    if isinstance(error, SpotifyException) and error.http_status == 403:
        return ("Spotify odmówiło dostępu (403). W trybie Development dodaj nowe konto "
                "w zakładce User Management aplikacji i upewnij się, że właściciel aplikacji ma Premium.")
    return error

def save_batch(sp, batch):
    global use_library_endpoint
    if use_library_endpoint is not False:
        try:
            sp._put("me/library", uris=",".join(batch))
            use_library_endpoint = True
            return
        except SpotifyException as e:
            if use_library_endpoint or e.http_status not in (400, 403, 404, 405):
                raise
            use_library_endpoint = False
    sp.current_user_saved_tracks_add(tracks=batch)

def add_tracks(sp, uris):
    total = len(uris)
    added = 0
    for i in range(0, total, BATCH_SIZE):
        batch = uris[i:i+BATCH_SIZE]
        try:
            save_batch(sp, batch)
            added += len(batch)
            print(f"   ✓ {min(i+BATCH_SIZE, total)}/{total}...", end="\r")
            time.sleep(0.3)
        except Exception as e:
            print(f"\n⚠️  Błąd: {explain(e)}")
            time.sleep(2)
    print(f"\n✅ Dodano {added}/{total} utworów!")

def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ Brak SPOTIFY_CLIENT_ID lub SPOTIFY_CLIENT_SECRET w pliku .env")
        sys.exit(1)

    print("🎵 Spotify Liked Songs Importer\n")
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
    ))
    try:
        user = sp.current_user()
    except SpotifyException as e:
        if e.http_status != 403:
            raise
        print(f"❌ {explain(e)}")
        sys.exit(1)
    print(f"👤 Zalogowano: {user['display_name']}")
    confirm = input("Czy to poprawne konto docelowe? (tak/nie): ").strip().lower()
    if confirm not in ("tak", "t", "yes", "y"):
        sys.exit(0)
    df, uri_col = load_csv(CSV_FILE)
    all_uris = df[uri_col].tolist()
    already = get_already_liked(sp)
    new_uris = [u for u in all_uris if u not in already]
    print(f"\n📋 Do dodania: {len(new_uris)} utworów")
    if not new_uris:
        print("ℹ️  Nic do dodania.")
        return
    confirm2 = input(f"Dodać {len(new_uris)} utworów? (tak/nie): ").strip().lower()
    if confirm2 not in ("tak", "t", "yes", "y"):
        sys.exit(0)
    add_tracks(sp, new_uris)

if __name__ == "__main__":
    main()
