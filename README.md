# spotify-playlist-import

Useful when changing your Spotify account — automatically transfers your liked songs.

> 🇵🇱 [Polska wersja poniżej](#polska-wersja)

---

## How it works

1. Export liked songs from your old account to CSV
2. Run the script on your new account
3. The script adds all tracks to your liked songs

---

## Desktop app (re:liked)

A dark Tkinter app that does the same job as the script, without the terminal:
CSV preview with search, Spotify login in the browser, the target account name shown before import,
skipping songs that are already liked, a live progress bar and a retry for failed batches.

```bash
pip install -r requirements.txt
python spotify_import_gui.py            # real import
python spotify_import_gui.py --demo     # walkthrough without login or account changes
```

Client ID and Client Secret can be entered in **Settings** (saved to `.env`).
Dragging a CSV into the window works when `tkinterdnd2` is installed.

> Since March 2026 Spotify apps in Development Mode save tracks through `PUT /me/library`;
> both the scripts and the desktop app use it and fall back to `PUT /me/tracks`. In Development Mode the app owner
> needs Premium and the new account must be added under **User Management** in the dashboard.

---

## Step 1 — Export with Exportify

Go to https://exportify.net/, log in with your old account and download **Liked Songs** as CSV.  
Save the file as `Liked_Songs.csv` in the project directory.

---

## Step 2 — Create a Spotify Developer App

1. Go to https://developer.spotify.com/dashboard/create
2. Fill in the form (name and description can be anything)
3. In the **Redirect URIs** field enter exactly: `http://127.0.0.1:8888/callback`
4. Under **APIs used** check only: **Web API** ✅  
   (Web Playback SDK, Android, iOS, Ads API — **not needed**)
5. Save and go to app settings — copy your **Client ID** and **Client Secret**

---

## Step 3 — Configure `.env`

Copy the example file and fill in your credentials:

```bash
cp env.example .env
```

Edit `.env`:

```env
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
CSV_FILE=Liked_Songs.csv
```

---

## Step 4 — Install dependencies

```bash
pip install spotipy pandas python-dotenv
```

---

## Step 5 — Run

```bash
python3 spotify_import_with_credentials.py
```

On first run a browser window will open asking you to authorize.  
After logging in you'll be redirected to `http://127.0.0.1:8888/callback` — that's expected.

---

## Troubleshooting

### `SpotifyOauthError: invalid_client`

Spotipy caches the token in a `.cache` file. If the token expired or the app credentials changed, the refresh fails.

**Fix:** delete the cache and re-run:

```bash
rm -f .cache && python3 spotify_import_with_credentials.py
```

You'll be prompted to log in again via the browser.

### Browser doesn't open

Copy the URL printed in the terminal and paste it manually into your browser.

---

## .gitignore

Make sure `.env` and `.cache` are in `.gitignore` — don't push credentials to GitHub:

```
.env
.cache
```

---

---

# Polska wersja

Przydatne przy zmianie konta Spotify — automatycznie przenosi polubione utwory.

## Jak to działa

1. Eksportujesz polubione utwory ze starego konta do CSV
2. Uruchamiasz skrypt na nowym koncie
3. Skrypt dodaje wszystkie utwory do polubionych

---

## Aplikacja okienkowa (re:liked)

Ciemna aplikacja w Tkinter robi to samo co skrypt, ale bez terminala:
podgląd CSV z wyszukiwarką, logowanie do Spotify w przeglądarce, nazwa konta docelowego przed importem,
pomijanie już polubionych utworów, pasek postępu na żywo i ponawianie nieudanych paczek.

```bash
pip install -r requirements.txt
python spotify_import_gui.py            # prawdziwy import
python spotify_import_gui.py --demo     # pokaz bez logowania i bez zmian na koncie
```

Client ID i Client Secret można wpisać w **Ustawieniach** (zapisują się w `.env`).
Przeciąganie pliku CSV do okna działa, gdy zainstalowany jest `tkinterdnd2`.

> Od marca 2026 aplikacje Spotify w trybie Development zapisują utwory przez `PUT /me/library`;
> korzystają z niego zarówno skrypty, jak i aplikacja okienkowa, a w razie potrzeby wracają do `PUT /me/tracks`. W trybie Development
> właściciel aplikacji potrzebuje Premium, a nowe konto trzeba dodać w zakładce **User Management**.

---

## Krok 1 — Eksport z Exportify

Wejdź na https://exportify.net/, zaloguj się starym kontem i pobierz **Liked Songs** jako CSV.  
Zapisz plik jako `Liked_Songs.csv` w katalogu projektu.

---

## Krok 2 — Utwórz aplikację w Spotify Developer Dashboard

1. Wejdź na https://developer.spotify.com/dashboard/create
2. Wypełnij formularz (nazwa i opis dowolne)
3. W polu **Redirect URIs** wpisz dokładnie: `http://127.0.0.1:8888/callback`
4. W sekcji **APIs used** zaznacz tylko: **Web API** ✅  
   (Web Playback SDK, Android, iOS, Ads API — **nie są potrzebne**)
5. Zapisz i wejdź w ustawienia aplikacji — skopiuj **Client ID** i **Client Secret**

---

## Krok 3 — Konfiguracja `.env`

Skopiuj plik przykładowy i uzupełnij swoje dane:

```bash
cp env.example .env
```

Edytuj `.env`:

```env
SPOTIFY_CLIENT_ID=tutaj_wklej_client_id
SPOTIFY_CLIENT_SECRET=tutaj_wklej_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
CSV_FILE=Liked_Songs.csv
```

---

## Krok 4 — Instalacja zależności

```bash
pip install spotipy pandas python-dotenv
```

---

## Krok 5 — Uruchomienie

```bash
python3 spotify_import_with_credentials.py
```

Przy pierwszym uruchomieniu otworzy się przeglądarka z prośbą o autoryzację.  
Po zalogowaniu zostaniesz przekierowany na `http://127.0.0.1:8888/callback` — to normalne.

---

## Rozwiązywanie problemów

### `SpotifyOauthError: invalid_client`

Spotipy cache'uje token w pliku `.cache`. Jeśli token wygasł lub dane aplikacji się zmieniły, odświeżenie nie działa.

**Rozwiązanie:** usuń cache i uruchom ponownie:

```bash
rm -f .cache && python3 spotify_import_with_credentials.py
```

Zostaniesz poproszony o ponowne zalogowanie przez przeglądarkę.

### Przeglądarka się nie otwiera

Skopiuj URL wypisany w terminalu i wklej go ręcznie do przeglądarki.

---

## .gitignore

Upewnij się, że `.env` i `.cache` są w `.gitignore` — nie wrzucaj credentiali na GitHub:

```
.env
.cache
```
