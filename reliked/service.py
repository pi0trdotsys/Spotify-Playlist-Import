"""Połączenie ze Spotify (spotipy), konfiguracja .env i tryb demo bez sieci.

Metody serwisów blokują — aplikacja wywołuje je w wątkach roboczych.
"""

import html
import os
import secrets
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    import spotipy
    from spotipy.cache_handler import CacheFileHandler
    from spotipy.exceptions import SpotifyException
    from spotipy.oauth2 import SpotifyOAuth, SpotifyOauthError
except ImportError:
    spotipy = None

try:
    from dotenv import dotenv_values, set_key
except ImportError:
    dotenv_values = set_key = None

try:
    from requests.exceptions import ConnectionError as NetworkError, Timeout as NetworkTimeout
except ImportError:
    NetworkError = NetworkTimeout = OSError

SCOPE = "user-library-modify user-library-read"
DEFAULT_REDIRECT = "http://127.0.0.1:8888/callback"
BATCH_SIZE = 40          # limit PUT /me/library
AUTH_TIMEOUT = 300       # sekundy na dokończenie logowania w przeglądarce

MISSING = [name for name, module in (("spotipy", spotipy), ("python-dotenv", dotenv_values)) if module is None]

ENV_KEYS = {
    "client_id": "SPOTIFY_CLIENT_ID",
    "client_secret": "SPOTIFY_CLIENT_SECRET",
    "redirect_uri": "SPOTIFY_REDIRECT_URI",
    "csv_file": "CSV_FILE",
}


class ServiceError(Exception):
    """Błąd z gotowym komunikatem dla użytkownika."""


class Cancelled(Exception):
    """Użytkownik przerwał operację."""


class NoSession(Exception):
    """Brak zapamiętanej sesji — potrzebne logowanie w przeglądarce."""


@dataclass
class Config:
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = DEFAULT_REDIRECT
    csv_file: str = "Liked_Songs.csv"

    @property
    def complete(self):
        return bool(self.client_id and self.client_secret)


def load_config(env_path):
    """Wartości z .env mają pierwszeństwo — to je edytuje okno ustawień."""
    file_values = dotenv_values(env_path) if dotenv_values and Path(env_path).exists() else {}
    defaults = Config()

    def get(attr):
        key = ENV_KEYS[attr]
        return (file_values.get(key) or os.environ.get(key) or getattr(defaults, attr)).strip()

    return Config(**{attr: get(attr) for attr in ENV_KEYS})


def save_config(env_path, config):
    if set_key is None:
        raise ServiceError("Zapis ustawień wymaga pakietu python-dotenv (pip install -r requirements.txt).")
    env_path = Path(env_path)
    env_path.touch(exist_ok=True)
    for attr, key in ENV_KEYS.items():
        set_key(str(env_path), key, getattr(config, attr), quote_mode="never")


# --- Odbiór kodu autoryzacji z przeglądarki --------------------------------

PAGE = """<!doctype html><html lang="pl"><meta charset="utf-8"><title>re:liked</title>
<body style="margin:0;min-height:100vh;display:grid;place-items:center;background:#08100C;color:#E9F3ED;font-family:'Segoe UI',system-ui,sans-serif">
<div style="text-align:center;padding:24px"><div style="width:64px;height:64px;border-radius:50%;margin:0 auto 22px;background:{color};box-shadow:0 0 70px {color}88"></div>
<h1 style="font-size:24px;font-weight:600;margin:0 0 8px">{title}</h1><p style="margin:0;color:#7F978A">{text}</p></div></body></html>"""


class _CallbackServer(HTTPServer):
    # Na Windows SO_REUSEADDR pozwoliłby dwóm procesom słuchać na tym samym porcie.
    allow_reuse_address = False

    def __init__(self, address, callback_path):
        super().__init__(address, _CallbackHandler)
        self.callback_path = callback_path.rstrip("/") or "/"
        self.result = None
        self.timeout = 0.25


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if (url.path.rstrip("/") or "/") != self.server.callback_path:
            self.send_error(404)
            return
        params = {key: values[0] for key, values in parse_qs(url.query).items()}
        self.server.result = params
        ok = "code" in params
        page = PAGE.format(
            color="#1ED760" if ok else "#FF6B6B",
            title="Połączono z re:liked" if ok else "Autoryzacja przerwana",
            text="Możesz zamknąć tę kartę i wrócić do aplikacji." if ok
            else html.escape(f"Spotify zwróciło: {params.get('error', 'nieznany błąd')}. Wróć do aplikacji."),
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, *args):
        pass


# --- Prawdziwe Spotify ------------------------------------------------------

class SpotifyService:
    demo = False
    pause = 1.0   # przerwa między paczkami: każda dostaje inny znacznik czasu → zachowana kolejność

    def __init__(self, config, cache_path):
        self.config = config
        self.cache_path = Path(cache_path)
        self.sp = None
        self._library_endpoint = None   # None = nie wiadomo jeszcze, czy działa PUT /me/library

    def _auth_manager(self):
        return SpotifyOAuth(
            client_id=self.config.client_id,
            client_secret=self.config.client_secret,
            redirect_uri=self.config.redirect_uri,
            scope=SCOPE,
            cache_handler=CacheFileHandler(cache_path=str(self.cache_path)),
            show_dialog=True,      # pozwala wybrać właściwe (nowe) konto
            open_browser=False,
        )

    def connect(self, cancel, on_url, interactive=True):
        if spotipy is None:
            raise ServiceError("Brakuje pakietu spotipy (pip install -r requirements.txt).")
        auth = self._auth_manager()
        token = None
        cached = auth.cache_handler.get_cached_token()
        if cached:
            try:
                token = auth.validate_token(cached)
            except SpotifyOauthError:
                self.forget()   # np. invalid_client po zmianie danych aplikacji — zaloguj od nowa
        if not token:
            if not interactive:
                raise NoSession()
            code = self._authorize(auth, cancel, on_url)
            auth.get_access_token(code, as_dict=False, check_cache=False)
        self.sp = spotipy.Spotify(auth_manager=auth, requests_timeout=20)
        me = self.sp.current_user()
        return {"name": me.get("display_name") or me.get("id", "?"), "id": me.get("id", "")}

    def _authorize(self, auth, cancel, on_url):
        redirect = urlparse(self.config.redirect_uri)
        if redirect.scheme != "http" or redirect.hostname not in ("127.0.0.1", "localhost") or not redirect.port:
            raise ServiceError("Redirect URI musi mieć postać http://127.0.0.1:<port>/callback "
                               "— dokładnie taką jak w Spotify Developer Dashboard.")
        try:
            server = _CallbackServer((redirect.hostname, redirect.port), redirect.path or "/")
        except OSError:
            raise ServiceError(f"Port {redirect.port} jest zajęty. Zamknij inne okno importu "
                               "(np. skrypt w terminalu) i spróbuj ponownie.") from None
        state = secrets.token_urlsafe(16)
        url = auth.get_authorize_url(state=state)
        try:
            on_url(url)
            webbrowser.open(url)
            deadline = time.monotonic() + AUTH_TIMEOUT
            while server.result is None:
                if cancel.is_set():
                    raise Cancelled()
                if time.monotonic() > deadline:
                    raise ServiceError("Logowanie nie zostało dokończone w ciągu 5 minut. Spróbuj ponownie.")
                server.handle_request()
        finally:
            server.server_close()
        params = server.result
        if "error" in params:
            if params["error"] == "access_denied":
                raise ServiceError("Nie udzielono zgody w Spotify. Kliknij „Połącz”, aby spróbować ponownie.")
            raise ServiceError(f"Spotify odrzuciło logowanie ({params['error']}).")
        if params.get("state") != state:
            raise ServiceError("Odpowiedź Spotify ma niezgodny parametr state — przerwano ze względów bezpieczeństwa.")
        return params["code"]

    def forget(self):
        """Zapomina sesję (usuwa .cache), żeby można było zalogować się innym kontem."""
        self.sp = None
        try:
            self.cache_path.unlink()
        except FileNotFoundError:
            pass

    def fetch_liked(self, cancel, on_progress, candidates):
        liked = set()
        page = self.sp.current_user_saved_tracks(limit=50)
        while page:
            for item in page.get("items", []):
                uri = (item.get("track") or {}).get("uri")
                if uri:
                    liked.add(uri)
            on_progress(len(liked))
            if cancel.is_set():
                raise Cancelled()
            page = self.sp.next(page) if page.get("next") else None
        return liked

    def add_tracks(self, tracks):
        uris = [t.uri for t in tracks]
        # Od 2026 aplikacje w trybie Development zapisują przez PUT /me/library;
        # gdyby ten endpoint był niedostępny, wracamy do PUT /me/tracks.
        if self._library_endpoint is not False:
            try:
                self.sp._put("me/library", uris=",".join(uris))
                self._library_endpoint = True
                return
            except SpotifyException as exc:
                if self._library_endpoint or exc.http_status not in (400, 403, 404, 405):
                    raise
                self._library_endpoint = False
        self.sp.current_user_saved_tracks_add(tracks=uris)


# --- Tryb demo --------------------------------------------------------------

class DemoService:
    """Udaje Spotify: nic nie wysyła, pozwala obejrzeć cały przepływ."""

    demo = True
    pause = 0.05

    def connect(self, cancel, on_url, interactive=True):
        if not interactive:
            raise NoSession()
        on_url(None)
        for _ in range(16):
            if cancel.is_set():
                raise Cancelled()
            time.sleep(0.1)
        return {"name": "Konto demo", "id": "demo"}

    def forget(self):
        pass

    def fetch_liked(self, cancel, on_progress, candidates):
        liked = {t.uri for i, t in enumerate(candidates) if i % 37 == 5}
        for n in range(0, len(liked) + 1, 8):
            if cancel.is_set():
                raise Cancelled()
            on_progress(n)
            time.sleep(0.05)
        return liked

    def add_tracks(self, tracks):
        time.sleep(0.12)


# --- Komunikaty błędów ------------------------------------------------------

def is_fatal(exc):
    """Błędy, przy których nie ma sensu ponawiać kolejnych paczek."""
    if isinstance(exc, (ServiceError, Cancelled)):
        return True
    if spotipy is not None:
        if isinstance(exc, SpotifyOauthError):
            return True
        if isinstance(exc, SpotifyException) and exc.http_status in (401, 403):
            return True
    return False


def describe_error(exc):
    if isinstance(exc, ServiceError):
        return str(exc)
    if spotipy is not None:
        if isinstance(exc, SpotifyOauthError):
            if "invalid_client" in str(exc):
                return "Spotify odrzuciło Client ID lub Client Secret. Sprawdź je w Ustawieniach."
            return f"Błąd autoryzacji Spotify: {getattr(exc, 'error_description', None) or exc}"
        if isinstance(exc, SpotifyException):
            if exc.http_status == 401:
                return "Sesja Spotify wygasła. Odłącz konto i połącz je ponownie."
            if exc.http_status == 403:
                return ("Spotify odmówiło dostępu (403). W trybie Development dodaj nowe konto w zakładce "
                        "User Management aplikacji i upewnij się, że właściciel aplikacji ma Premium.")
            if exc.http_status == 429:
                return "Spotify chwilowo ogranicza liczbę zapytań (429). Odczekaj minutę i spróbuj ponownie."
            return f"Spotify zwróciło błąd {exc.http_status}: {exc.msg}"
    if isinstance(exc, (NetworkError, NetworkTimeout)):
        return "Brak połączenia ze Spotify. Sprawdź internet i spróbuj ponownie."
    return f"Nieoczekiwany błąd: {exc}"
