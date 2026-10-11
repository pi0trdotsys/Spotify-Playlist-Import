"""Wczytywanie eksportu polubionych utworów z Exportify (CSV)."""

import csv
import zlib
from dataclasses import dataclass, field
from pathlib import Path


class CsvError(Exception):
    """Plik nie wygląda na eksport z Exportify."""


@dataclass
class Track:
    uri: str
    name: str
    artists: str
    album: str
    duration_ms: int
    added_at: str
    search_key: str = field(init=False, repr=False)
    cover_index: int = field(init=False, repr=False)

    def __post_init__(self):
        self.search_key = f"{self.name} {self.artists} {self.album}".casefold()
        # Ta sama płyta → ta sama zastępcza okładka.
        self.cover_index = zlib.crc32((self.album or self.name).encode("utf-8"))

    @property
    def importable(self):
        """Pliki lokalne (spotify:local:…) nie dają się polubić przez API."""
        return self.uri.startswith("spotify:track:")

    @property
    def duration(self):
        return format_duration(self.duration_ms)


@dataclass
class Library:
    path: Path
    tracks: list
    uri_column: str
    artist_count: int = 0
    duplicates: int = 0

    @property
    def importable(self):
        return [t for t in self.tracks if t.importable]

    @property
    def total_ms(self):
        return sum(t.duration_ms for t in self.tracks)


def _find_column(columns, *keywords, exact=None):
    for col in columns:
        name = col.strip().lower()
        if exact and name == exact:
            return col
        if all(k in name for k in keywords):
            return col
    return None


def load_library(path):
    """Czyta CSV jak skrypt CLI: kolumna z „track” i „uri” albo „Spotify URI”."""
    path = Path(path)
    if path.suffix.lower() != ".csv":
        raise CsvError("Wybierz plik w formacie CSV.")
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = reader.fieldnames or []
            uri_col = _find_column(columns, "uri", "track", exact="spotify uri")
            if uri_col is None:
                raise CsvError("Nie znaleziono kolumny z URI utworów. Czy to na pewno eksport z Exportify?")
            name_col = _find_column(columns, "track", "name")
            artist_col = _find_column(columns, "artist")
            album_col = _find_column(columns, "album", "name")
            duration_col = _find_column(columns, "duration")
            added_col = _find_column(columns, "added", "at")
            tracks, seen, artists, duplicates = [], set(), set(), 0
            for row in reader:
                uri = (row.get(uri_col) or "").strip()
                if not uri:
                    continue
                if uri in seen:
                    duplicates += 1
                    continue
                seen.add(uri)
                names = [a.strip() for a in (row.get(artist_col) or "").split(";") if a.strip()]
                artists.update(a.casefold() for a in names)
                try:
                    duration = int(float(row.get(duration_col) or 0)) if duration_col else 0
                except ValueError:
                    duration = 0
                tracks.append(Track(
                    uri=uri,
                    name=(row.get(name_col) or "").strip() or "Bez tytułu",
                    artists=", ".join(names) or "Nieznany wykonawca",
                    album=(row.get(album_col) or "").strip() if album_col else "",
                    duration_ms=duration,
                    added_at=(row.get(added_col) or "").strip() if added_col else "",
                ))
    except FileNotFoundError:
        raise CsvError(f"Nie znaleziono pliku: {path.name}") from None
    except (UnicodeDecodeError, csv.Error) as exc:
        raise CsvError(f"Nie udało się odczytać pliku CSV ({exc}).") from None
    if not tracks:
        raise CsvError("Plik nie zawiera żadnych utworów.")
    return Library(path=path, tracks=tracks, uri_column=uri_col, artist_count=len(artists), duplicates=duplicates)


def import_order(tracks):
    """Najstarsze najpierw — wtedy najnowsze lądują na górze „Polubionych”."""
    if all(t.added_at for t in tracks):
        return sorted(tracks, key=lambda t: t.added_at)
    return list(reversed(tracks))


def format_duration(ms):
    seconds = round(ms / 1000)
    return f"{seconds // 60}:{seconds % 60:02d}"


def format_hours(ms):
    return f"{ms / 3_600_000:.1f}".replace(".", ",") + " h"


def plural(n, one, few, many):
    """Polska odmiana: 1 utwór, 2 utwory, 5 utworów, 22 utwory, 112 utworów."""
    if n == 1:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many


def count(n, one, few, many):
    return f"{n} {plural(n, one, few, many)}"
