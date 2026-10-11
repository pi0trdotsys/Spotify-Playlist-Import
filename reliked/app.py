"""Główne okno re:liked: wybór CSV → połączenie konta → import polubionych."""

import argparse
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from . import images as img
from . import service as svc
from . import theme as t
from .dialogs import EXPORTIFY_URL, ConfirmDialog, HelpDialog, SettingsDialog
from .library import CsvError, count, format_hours, import_order, load_library, plural
from .theme import ICON, px
from .widgets import (Badge, Hero, Link, Panel, PillButton, ProgressBar, SearchBox, Stepper, TrackList,
                      icon_label, icon_tile, label)

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    TkinterDnD = None

APP_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = APP_DIR / ".env"
CACHE_PATH = APP_DIR / ".cache"

BANNER_STYLES = {
    "ok": (t.GREEN_SOFT, t.GREEN_LINE, t.GREEN_HI, "done_fill"),
    "nothing": (t.GREEN_SOFT, t.GREEN_LINE, t.GREEN_HI, "heart_fill"),
    "partial": (t.AMBER_SOFT, t.AMBER_LINE, t.AMBER, "warning"),
    "cancelled": (t.PANEL, t.LINE_STRONG, t.MUTED, "info"),
    "error": (t.RED_SOFT, t.RED_LINE, t.RED, "error"),
}


class App:
    def __init__(self, root, *, demo=False, csv_path=None):
        self.root = root
        self.demo = demo
        self.config = svc.load_config(ENV_PATH)
        self.service = svc.DemoService() if demo else svc.SpotifyService(self.config, CACHE_PATH)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.library = None
        self.file_error = None
        self.user = None
        self.auth_error = None
        self.auth_url = None
        self.auth_silent = False
        self.phase = "idle"          # idle | auth | check | import | done
        self.result = None
        self.statuses = {}
        self.counts = {}
        self.last_error = None
        self.dragging = False
        self.dnd = False
        self._drop_key = self._account_key = None
        self._reset_results()

        root.withdraw()
        root.title("re:liked — import polubionych utworów Spotify")
        root.configure(bg=t.BG)
        self._icons = [img.app_icon(32), img.app_icon(64)]
        root.iconphoto(True, *self._icons)
        self._build()
        self._place_window()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._setup_dnd()

        path = Path(csv_path) if csv_path else APP_DIR / self.config.csv_file
        if csv_path or path.exists():
            self.load_csv(path, quiet=not csv_path)
        self._render()
        t.style_titlebar(root)
        root.deiconify()
        self._poll()
        if not demo and self.config.complete and not svc.MISSING and CACHE_PATH.exists():
            self._connect(interactive=False)

    # --- budowa okna -------------------------------------------------------
    def _place_window(self):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = min(px(1200), int(sw * 0.92)), min(px(860), int(sh * 0.86))
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - px(24))}")
        # Wysokość z zapasem na pasek postępu i baner wyniku w lewej kolumnie.
        self.root.minsize(min(px(1000), w), min(px(780), h))

    def _build(self):
        root = self.root
        self.hero = Hero(root, badge="DEMO" if self.demo else "v2", demo=self.demo,
                         on_settings=self.open_settings, on_help=self.open_help)
        self.hero.pack(fill="x")
        self.stepper = Stepper(root, ["Wgraj plik CSV", "Połącz konto", "Importuj utwory"])
        self.stepper.pack(fill="x", padx=px(40), pady=(px(2), px(22)))
        self._build_footer()
        main = tk.Frame(root, bg=t.BG)
        main.pack(fill="both", expand=True, padx=px(40), pady=(0, px(18)))
        main.columnconfigure(0, weight=11, uniform="col")
        main.columnconfigure(1, weight=10, uniform="col")
        main.rowconfigure(0, weight=1)
        left = tk.Frame(main, bg=t.BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, px(16)))
        right = tk.Frame(main, bg=t.BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(px(16), 0))
        self._build_left(left)
        self._build_right(right)

    def _section(self, parent, number, title):
        row = tk.Frame(parent, bg=t.BG)
        label(row, number, fg=t.GREEN_HI, size="mono_s").pack(side="left", padx=(0, px(10)))
        label(row, title, size="h3").pack(side="left")
        return row

    def _build_footer(self):
        bar = tk.Frame(self.root, bg=t.BG)
        bar.pack(side="bottom", fill="x", padx=px(40))
        tk.Frame(bar, bg=t.LINE, height=1).pack(fill="x")
        row = tk.Frame(bar, bg=t.BG)
        row.pack(fill="x", pady=px(11))
        label(row, "re:liked", size="tiny").pack(side="left")
        label(row, "  /  Muzyka idzie z Tobą.", fg=t.MUTED, size="tiny").pack(side="left")
        self.footer_status = label(row, "", fg=t.MUTED, size="tiny")
        self.footer_status.pack(side="right")
        self.footer_dot = label(row, "●", size="tiny")
        self.footer_dot.pack(side="right", padx=(0, px(7)))

    def _build_left(self, parent):
        self._section(parent, "01", "Twoja kolekcja").pack(fill="x", pady=(0, px(10)))
        self.drop = Panel(parent, fill=t.PANEL, outline=t.LINE_STRONG, radius=16, pad=18, dashed=True)
        self.drop.pack(fill="x")
        row = tk.Frame(parent, bg=t.BG)
        row.pack(fill="x", pady=(px(10), 0))
        self.drop_msg = label(row, "", fg=t.MUTED, size="small", anchor="w", justify="left")
        self.drop_msg.pack(side="left", fill="x", expand=True)
        Link(row, "Otwórz Exportify ↗", url=EXPORTIFY_URL).pack(side="right", anchor="n")

        self._section(parent, "02", "Konto docelowe").pack(fill="x", pady=(px(24), px(10)))
        self.account = Panel(parent, fill=t.PANEL, outline=t.LINE, radius=16, pad=(16, 14))
        self.account.pack(fill="x")
        self.account_msg = label(parent, "", fg=t.RED, size="small", anchor="w", justify="left")

        self.import_btn = PillButton(parent, "Importuj polubione utwory", self._on_import_click,
                                     icon=ICON["arrow"], height=52)
        self.import_btn.pack(fill="x", pady=(px(24), 0))
        self.progress_box = tk.Frame(parent, bg=t.BG)
        self.progress = ProgressBar(self.progress_box)
        self.progress.pack(fill="x", pady=(px(16), px(9)))
        status = tk.Frame(self.progress_box, bg=t.BG)
        status.pack(fill="x")
        self.status_lbl = label(status, "", fg=t.MUTED, size="small", anchor="w")
        self.status_lbl.pack(side="left")
        self.cancel_link = Link(status, "Anuluj", self._cancel, fg=t.MUTED, hover=t.RED)
        self.cancel_link.pack(side="right")
        self.banner = Panel(parent, fill=t.GREEN_SOFT, outline=t.GREEN_LINE, radius=14, pad=(16, 14))

        safety = tk.Frame(parent, bg=t.BG)
        safety.pack(side="bottom", fill="x")
        inner = tk.Frame(safety, bg=t.BG)
        inner.pack(anchor="w")
        icon_label(inner, "lock", fg=t.DIM, size="icon_xs").pack(side="left", padx=(0, px(7)))
        label(inner, "Tylko dodajemy — nic nie znika z żadnego konta. Dane logowania zostają na tym komputerze.",
              fg=t.DIM, size="tiny").pack(side="left")

        def wrap(event):
            for widget in (self.drop_msg, self.account_msg):
                widget.configure(wraplength=max(px(200), event.width - px(130)))
        parent.bind("<Configure>", wrap, add="+")

    def _build_right(self, parent):
        card = Panel(parent, fill=t.PANEL, outline=t.LINE, radius=18, pad=6)
        card.pack(fill="both", expand=True)
        body = card.body
        head = tk.Frame(body, bg=t.PANEL)
        head.pack(fill="x", padx=px(14), pady=(px(12), 0))
        label(head, "Polubione utwory", size="h2").pack(side="left")
        self.lib_badge = Badge(head, "brak pliku", fg=t.MUTED, outline=t.LINE_STRONG)
        self.lib_badge.pack(side="right")
        meta = tk.Frame(body, bg=t.PANEL)
        meta.pack(fill="x", padx=px(14), pady=(px(4), 0))
        icon_label(meta, "heart_fill", fg=t.GREEN, size="icon_xs").pack(side="left", padx=(0, px(7)))
        self.lib_meta = label(meta, "", fg=t.MUTED, size="small")
        self.lib_meta.pack(side="left")

        tiles = tk.Frame(body, bg=t.PANEL)
        tiles.pack(fill="x", padx=px(14), pady=(px(14), 0))
        self.tiles = []
        for i in range(3):
            tiles.columnconfigure(i, weight=1, uniform="tile")
            tile = Panel(tiles, fill=t.FIELD, outline=None, radius=12, pad=(14, 10))
            tile.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else px(5), 0 if i == 2 else px(5)))
            value = label(tile.body, "—", size="stat", anchor="w")
            value.pack(fill="x")
            caption = label(tile.body, "", fg=t.MUTED, size="tiny", anchor="w")
            caption.pack(fill="x")
            self.tiles.append((value, caption))

        self.search = SearchBox(body, self._on_search, "Szukaj utworu, wykonawcy lub albumu")
        self.search.pack(fill="x", padx=px(14), pady=(px(14), px(4)))

        foot = tk.Frame(body, bg=t.PANEL)
        foot.pack(side="bottom", fill="x")
        tk.Frame(foot, bg=t.LINE, height=1).pack(fill="x", padx=px(8))
        row = tk.Frame(foot, bg=t.PANEL)
        row.pack(fill="x", padx=px(14), pady=(px(11), px(6)))
        icon_label(row, "shield", fg=t.MUTED, size="icon_xs").pack(side="left", padx=(0, px(8)))
        label(row, "Twoja muzyka zostaje na starym koncie.", fg=t.MUTED, size="tiny").pack(side="left")
        label(row, "dwuklik → otwórz w Spotify", fg=t.DIM, size="tiny").pack(side="right")

        self.tracklist = TrackList(body, bg=t.PANEL)
        self.tracklist.pack(fill="both", expand=True)
        self.tracklist.statuses = self.statuses

    def _setup_dnd(self):
        if TkinterDnD is None or not hasattr(self.root, "drop_target_register"):
            return
        try:
            self.root.drop_target_register(DND_FILES)
        except tk.TclError:
            return
        self.dnd = True
        self.root.dnd_bind("<<DropEnter>>", lambda e: self._set_dragging(True) or e.action)
        self.root.dnd_bind("<<DropLeave>>", lambda e: self._set_dragging(False) or e.action)
        self.root.dnd_bind("<<Drop>>", self._on_drop)

    # --- stan i rysowanie --------------------------------------------------
    @property
    def busy(self):
        return self.phase in ("auth", "check", "import")

    @property
    def running(self):
        return self.phase in ("check", "import")

    def _render(self):
        has_file, connected = self.library is not None, self.user is not None
        if self.phase == "done" and self.result["kind"] in ("ok", "nothing"):
            self.stepper.set(None, {0, 1, 2})
        else:
            active = 0 if not has_file else 1 if not connected else 2
            self.stepper.set(active, set(range(active)))
        self.hero.set_spinning(self.busy and not self.auth_silent)
        self._render_drop()
        self._render_account()
        self._render_import()
        self._render_library()
        self._render_footer()

    def _render_drop(self):
        lib = self.library
        key = (lib.path if lib else None, self.dragging, self.running, self.dnd)
        if key != self._drop_key:
            self._drop_key = key
            self._fill_drop()
        if self.file_error:
            self.drop_msg.configure(text=self.file_error, fg=t.RED)
        elif lib and lib.duplicates:
            self.drop_msg.configure(text=f"Pominięto {count(lib.duplicates, 'powtórzony wiersz', 'powtórzone wiersze', 'powtórzonych wierszy')}.", fg=t.MUTED)
        else:
            self.drop_msg.configure(text="Potrzebujesz świeżego eksportu?" if lib else "Nie masz jeszcze pliku?", fg=t.MUTED)

    def _fill_drop(self):
        p, lib = self.drop, self.library
        if self.dragging:
            p.set_style(fill=t.GREEN_SOFT, outline=t.GREEN, dashed=True)
        elif lib:
            p.set_style(fill=t.PANEL, outline=t.GREEN_LINE, dashed=False)
        else:
            p.set_style(fill=t.PANEL, outline=t.LINE_STRONG, dashed=True)
        p.clear()
        # Świeża ramka przy każdym wypełnieniu — razem z nią znikają stare powiązania zdarzeń.
        body = tk.Frame(p.body, bg=p.fill)
        body.pack(fill="x")
        if lib and not self.dragging:
            body.columnconfigure(1, weight=1)
            icon_tile(body, "playlist", size=46, radius=12).grid(row=0, column=0, rowspan=2, padx=(0, px(14)))
            label(body, lib.path.name, size="body_b", anchor="w").grid(row=0, column=1, sticky="ew")
            importable = len(lib.importable)
            details = f"{count(importable, 'utwór', 'utwory', 'utworów')} do importu · {format_hours(lib.total_ms)}"
            if importable < len(lib.tracks):
                details += f" · {len(lib.tracks) - importable} lokalnych pominiętych"
            label(body, details, fg=t.MUTED, size="small", anchor="w").grid(row=1, column=1, sticky="ew", pady=(px(2), 0))
            button = PillButton(body, "Zmień", self.choose_file, variant="outline", icon=ICON["upload"],
                                icon_side="left", height=34, font_name="btn_s")
            button.grid(row=0, column=2, rowspan=2, padx=(px(12), 0))
            button.set_state(disabled=self.running)
            return
        icon_tile(body, "upload", size=50, fill=t.GREEN if self.dragging else t.GREEN_SOFT,
                  fg=t.GREEN_INK if self.dragging else t.GREEN_HI).pack(pady=(px(6), px(12)))
        if self.dragging:
            title, sub = "Upuść plik, aby go wczytać", "Plik CSV z Exportify"
        else:
            title = "Przeciągnij tutaj plik CSV" if self.dnd else "Wybierz plik CSV z Exportify"
            sub = "Eksport polubionych utworów z exportify.net"
        label(body, title, size="body_b").pack()
        label(body, sub, fg=t.MUTED, size="small").pack(pady=(px(3), 0))
        if not self.dragging:
            PillButton(body, "Wybierz plik", self.choose_file, variant="soft", icon=ICON["upload"], icon_side="left",
                       height=36, font_name="btn_s").pack(pady=(px(14), px(4)))
            for widget in [body, *body.winfo_children()[:-1]]:
                widget.bind("<Button-1>", lambda e: self.choose_file())
                widget.configure(cursor="hand2")

    def _render_account(self):
        user_id = self.user["id"] if self.user else None
        key = (user_id, self.phase, self.auth_silent, self.auth_url, self.config.complete)
        if key != self._account_key:
            self._account_key = key
            self._fill_account()
        if self.auth_error:
            self.account_msg.configure(text=self.auth_error)
            if not self.account_msg.winfo_manager():
                self.account_msg.pack(fill="x", pady=(px(8), 0), after=self.account)
        else:
            self.account_msg.pack_forget()

    def _fill_account(self):
        p = self.account
        p.clear()
        body = p.body
        body.columnconfigure(1, weight=1)
        texts = tk.Frame(body, bg=p.fill)
        texts.grid(row=0, column=1, sticky="ew")
        action = None
        if svc.MISSING and not self.demo:
            icon_tile(body, "warning", size=42, fill=t.AMBER_SOFT, fg=t.AMBER).grid(row=0, column=0, padx=(0, px(14)))
            title, sub = "Brakuje bibliotek Pythona", f"Zainstaluj: pip install -r requirements.txt ({', '.join(svc.MISSING)})"
        elif not self.config.complete and not self.demo:
            icon_tile(body, "settings", size=42).grid(row=0, column=0, padx=(0, px(14)))
            title, sub = "Skonfiguruj aplikację Spotify", "Wpisz Client ID i Client Secret z Developer Dashboard."
            action = ("Ustawienia", self.open_settings, "soft", ICON["settings"])
        else:
            logo = tk.Canvas(body, bg=p.fill, highlightthickness=0, bd=0, width=px(42), height=px(42))
            logo.image = img.spotify_logo(px(42))
            logo.create_image(px(21), px(21), image=logo.image)
            logo.grid(row=0, column=0, padx=(0, px(14)))
            if self.phase == "auth" and self.auth_silent:
                title, sub = "Przywracam zapisaną sesję…", "Sprawdzam token w pliku .cache."
            elif self.phase == "auth":
                title = "Czekam na logowanie…"
                sub = "Symulacja logowania w trybie demo." if self.demo else "Dokończ logowanie w przeglądarce i wybierz NOWE konto."
                action = ("Anuluj", self._cancel, "outline", None)
            elif self.user:
                title = self.user["name"]
                sub = "Tryb demo · nic nie trafi na prawdziwe konto" if self.demo else f"Połączono · @{self.user['id']}"
                action = ("Odłącz", self._disconnect, "outline", None)
            else:
                title, sub = "Twoje nowe konto Spotify", "Tutaj trafią polubione utwory."
                action = ("Połącz", lambda: self._connect(interactive=True), "soft", ICON["link"])
        label(texts, title, size="body_b", anchor="w").pack(fill="x")
        sub_row = tk.Frame(texts, bg=p.fill)
        sub_row.pack(fill="x", pady=(px(2), 0))
        label(sub_row, sub, fg=t.MUTED, size="small", anchor="w").pack(side="left")
        if self.phase == "auth" and self.auth_url:
            Link(sub_row, "Otwórz ponownie ↗", url=self.auth_url, fg=t.GREEN_HI, hover=t.TEXT).pack(side="left", padx=(px(8), 0))
        if action:
            text, command, variant, icon = action
            button = PillButton(body, text, command, variant=variant, icon=icon, icon_side="left",
                                height=36, font_name="btn_s")
            button.grid(row=0, column=2, padx=(px(12), 0))
            button.set_state(disabled=self.running or (self.phase == "auth" and text != "Anuluj"))

    def _render_import(self):
        lib, btn = self.library, self.import_btn
        todo = len(lib.importable) if lib else 0
        if self.phase == "check":
            btn.set_state("Sprawdzam polubione na nowym koncie…", variant="primary", icon=None, disabled=False, busy=True)
        elif self.phase == "import":
            btn.set_state(f"Importowanie… {self._percent()}%", variant="primary", icon=None, disabled=False, busy=True)
        elif self.phase == "done":
            btn.set_state("Rozpocznij od nowa", variant="outline", icon=ICON["refresh"], disabled=False, busy=False)
        else:
            ready = lib is not None and self.user is not None and todo > 0 and self.phase == "idle"
            text = f"Importuj {count(todo, 'utwór', 'utwory', 'utworów')}" if lib else "Importuj polubione utwory"
            btn.set_state(text, variant="primary", icon=ICON["arrow"], disabled=not ready, busy=False)

        if self.running:
            if not self.progress_box.winfo_manager():
                self.progress_box.pack(fill="x", after=self.import_btn)
                self.cancel_link.configure(text="Anuluj")
        else:
            self.progress.stop()
            self.progress_box.pack_forget()

        if self.phase == "done":
            self._fill_banner()
            if not self.banner.winfo_manager():
                self.banner.pack(fill="x", pady=(px(16), 0), after=self.import_btn)
        else:
            self.banner.pack_forget()

    def _percent(self):
        c = self.counts
        return round(100 * (c["added"] + c["failed"]) / max(1, c["todo"]))

    def _update_progress(self):
        c = self.counts
        if self.phase == "check":
            self.progress.pulse()
            found = f" · znaleziono {c['checked']}" if c["checked"] else ""
            self.status_lbl.configure(text=f"Sprawdzam, co już jest polubione na nowym koncie{found}")
        elif self.phase == "import":
            self.progress.set((c["added"] + c["failed"]) / max(1, c["todo"]))
            parts = [f"{c['added']} / {c['todo']} dodanych"]
            if c["skipped"]:
                parts.append(f"{c['skipped']} już polubionych")
            if c["failed"]:
                parts.append(f"{c['failed']} {plural(c['failed'], 'błąd', 'błędy', 'błędów')}")
            self.status_lbl.configure(text=" · ".join(parts))
            self.import_btn.set_state(f"Importowanie… {self._percent()}%")
        self._render_tiles()

    def _fill_banner(self):
        kind, c = self.result["kind"], self.counts
        fill, outline, accent, icon = BANNER_STYLES[kind]
        name = self.user["name"] if self.user else "nowym koncie"
        action = None
        if kind == "ok":
            title = f"Gotowe! Dodano {count(c['added'], 'utwór', 'utwory', 'utworów')}."
            sub = f"Trafiły do polubionych na koncie {name}."
            if c["skipped"]:
                sub += f" {c['skipped']} było tam już wcześniej."
        elif kind == "nothing":
            title = "Wszystkie utwory są już polubione."
            sub = f"Na koncie {name} nie trzeba nic dodawać."
        elif kind == "partial":
            title = f"Dodano {c['added']} z {c['todo']} utworów."
            sub = f"{c['failed']} nie udało się dodać. {self.result['message'] or ''}".strip()
            action = ("Ponów brakujące", "soft")
        elif kind == "cancelled":
            title = "Import przerwany."
            sub = f"Dodano {c['added']} z {c['todo']}. Wznowienie pominie utwory, które już są na koncie."
            action = ("Wznów", "soft")
        else:
            title = "Import zatrzymany."
            sub = self.result["message"] or "Nieznany błąd."
            action = ("Spróbuj ponownie", "outline")
        p = self.banner
        p.set_style(fill=fill, outline=outline)
        p.clear()
        body = tk.Frame(p.body, bg=fill)
        body.pack(fill="x")
        body.columnconfigure(1, weight=1)
        label(body, ICON[icon], fg=accent, size="icon_l").grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, px(12)), pady=(px(2), 0))
        label(body, title, size="body_b", anchor="w").grid(row=0, column=1, sticky="ew")
        sub_lbl = label(body, sub, fg=t.MUTED, size="small", anchor="w", justify="left")
        sub_lbl.grid(row=1, column=1, sticky="ew", pady=(px(2), 0))
        if action:
            text, variant = action
            PillButton(body, text, self._start_import_all, variant=variant, icon=ICON["refresh"], icon_side="left",
                       height=34, font_name="btn_s").grid(row=0, column=2, rowspan=2, padx=(px(12), 0))
        reserved = px(220) if action else px(60)
        body.bind("<Configure>", lambda e: sub_lbl.configure(wraplength=max(px(160), e.width - reserved)))

    def _render_tiles(self):
        lib, c = self.library, self.counts
        if self.phase in ("import", "done") and c["todo"] + c["skipped"]:
            values = [
                (str(c["added"]), plural(c["added"], "dodany", "dodane", "dodanych"), t.GREEN_HI),
                (str(c["skipped"]), plural(c["skipped"], "już polubiony", "już polubione", "już polubionych"), t.TEXT),
                (str(c["failed"]), plural(c["failed"], "błąd", "błędy", "błędów"), t.RED if c["failed"] else t.TEXT),
            ]
        elif lib:
            n = len(lib.tracks)
            values = [
                (str(n), plural(n, "utwór", "utwory", "utworów"), t.TEXT),
                (format_hours(lib.total_ms), "muzyki", t.TEXT),
                (str(lib.artist_count), plural(lib.artist_count, "wykonawca", "wykonawców", "wykonawców"), t.TEXT),
            ]
        else:
            values = [("—", "utworów", t.DIM), ("—", "muzyki", t.DIM), ("—", "wykonawców", t.DIM)]
        for (value_lbl, caption_lbl), (value, caption, color) in zip(self.tiles, values):
            value_lbl.configure(text=value, fg=color)
            caption_lbl.configure(text=caption)

    def _render_library(self):
        lib = self.library
        if lib:
            self.lib_badge.set("z pliku", fg=t.GREEN_HI, outline=t.GREEN_LINE)
            self.lib_meta.configure(text=f"{count(len(lib.tracks), 'utwór', 'utwory', 'utworów')} · {format_hours(lib.total_ms)}")
        else:
            self.lib_badge.set("brak pliku", fg=t.MUTED, outline=t.LINE_STRONG)
            self.lib_meta.configure(text="Wgraj CSV, aby zobaczyć podgląd")
        self._render_tiles()

    def _render_footer(self):
        if self.demo:
            dot, text = t.AMBER, "Tryb demo · bez logowania i bez zmian na koncie Spotify"
        elif self.user:
            dot, text = t.GREEN, "Spotify Web API · połączono"
        else:
            dot, text = t.DIM, "Spotify Web API · niepołączono"
        self.footer_dot.configure(fg=dot)
        self.footer_status.configure(text=text)

    # --- akcje użytkownika -------------------------------------------------
    def choose_file(self):
        if self.running:
            return
        path = filedialog.askopenfilename(parent=self.root, title="Wybierz eksport z Exportify",
                                          initialdir=str(self.library.path.parent if self.library else APP_DIR),
                                          filetypes=[("Pliki CSV", "*.csv"), ("Wszystkie pliki", "*.*")])
        if path:
            self.load_csv(path)

    def load_csv(self, path, quiet=False):
        if self.running:
            return
        try:
            library = load_library(path)
        except CsvError as exc:
            if not quiet:
                self.file_error = str(exc)
                self._render()
            return
        self.library, self.file_error = library, None
        if self.phase == "done":
            self.phase = "idle"
        self._reset_results()
        self.search.clear()
        self.tracklist.set_tracks(library.tracks)
        self._render()

    def _set_dragging(self, on):
        if self.running:
            return
        self.dragging = on
        self._render_drop()

    def _on_drop(self, event):
        self.dragging = False
        files = self.root.tk.splitlist(event.data)
        if files:
            self.load_csv(files[0])
        self._render()
        return event.action

    def _on_search(self, text):
        self.tracklist.set_query(text)

    def open_settings(self):
        SettingsDialog(self.root, self.config, self._save_settings)

    def open_help(self):
        HelpDialog(self.root, self.open_settings)

    def _save_settings(self, config):
        if self.busy:
            raise svc.ServiceError("Poczekaj na zakończenie trwającej operacji.")
        svc.save_config(ENV_PATH, config)
        changed = (config.client_id, config.client_secret, config.redirect_uri) != \
                  (self.config.client_id, self.config.client_secret, self.config.redirect_uri)
        self.config = config
        if not self.demo:
            if changed:
                self.service.forget()   # token należał do poprzedniej aplikacji
                self.user = None
            self.service = svc.SpotifyService(config, CACHE_PATH)
        self.auth_error = None
        self._account_key = None
        self._render()

    def _connect(self, interactive=True):
        if self.busy:
            return
        self.phase, self.auth_silent = "auth", not interactive
        self.auth_error = self.auth_url = None
        self._start_worker(self._connect_worker, self.service, interactive)
        self._render()

    def _disconnect(self):
        if self.running:
            return
        self.service.forget()
        self.user = None
        if self.phase == "done":
            self.phase = "idle"
        self._reset_results()
        self._render()

    def _cancel(self):
        self.cancel.set()
        if self.running:
            self.cancel_link.configure(text="Przerywam…")

    def _on_import_click(self):
        if self.phase == "done":
            self.phase = "idle"
            self._reset_results()
            self._render()
        elif self.phase == "idle" and self.library and self.user:
            self._start_import_all()

    def _start_import_all(self):
        tracks = self.library.importable
        self._reset_results()
        self.phase = "check"
        for track in tracks:
            self.statuses[track.uri] = "pending"
        self.counts["todo"] = len(tracks)
        self.tracklist.follow = True
        self.progress.set(0, instant=True)
        self._start_worker(self._import_worker, self.service, import_order(tracks))
        self._render()
        self._update_progress()
        self.tracklist.refresh()

    def _reset_results(self):
        self.statuses.clear()
        self.counts = dict(added=0, skipped=0, failed=0, todo=0, checked=0)
        self.result = None
        self.last_error = None
        if hasattr(self, "tracklist"):
            self.tracklist.refresh()

    def _on_close(self):
        if self.running:
            ConfirmDialog(self.root, "Przerwać import?",
                          "Utwory dodane do tej pory zostaną na koncie. Resztę możesz dodać później — "
                          "już polubione zostaną wtedy pominięte.",
                          "Przerwij i zamknij", self._quit)
        else:
            self._quit()

    def _quit(self):
        self.cancel.set()
        self.root.destroy()

    # --- wątki robocze -----------------------------------------------------
    def _start_worker(self, target, *args):
        self.cancel = threading.Event()
        threading.Thread(target=target, args=(self.cancel, *args), daemon=True).start()

    def _connect_worker(self, cancel, service, interactive):
        put = self.events.put
        try:
            user = service.connect(cancel, lambda url: put(("auth_url", url)), interactive)
            put(("auth_ok", user))
        except (svc.Cancelled, svc.NoSession):
            put(("auth_end", None))
        except Exception as exc:  # noqa: BLE001 — każdy błąd trafia do UI jako komunikat
            put(("auth_end", svc.describe_error(exc) if interactive else None))

    def _import_worker(self, cancel, service, tracks):
        put = self.events.put
        try:
            liked = service.fetch_liked(cancel, lambda n: put(("checked", n)), tracks)
            todo = [track for track in tracks if track.uri not in liked]
            put(("plan", [track.uri for track in tracks if track.uri in liked], len(todo)))
            for start in range(0, len(todo), svc.BATCH_SIZE):
                if cancel.is_set():
                    raise svc.Cancelled()
                batch = todo[start:start + svc.BATCH_SIZE]
                error = self._send_batch(service, batch)
                uris = [track.uri for track in batch]
                put(("failed", uris, error) if error else ("added", uris))
                if start + svc.BATCH_SIZE < len(todo):
                    time.sleep(service.pause)
            put(("finished", "done", None))
        except svc.Cancelled:
            put(("finished", "cancelled", None))
        except Exception as exc:  # noqa: BLE001
            put(("finished", "error", svc.describe_error(exc)))

    @staticmethod
    def _send_batch(service, batch):
        """Wysyła paczkę; przy chwilowym błędzie ponawia raz. Zwraca opis błędu albo None."""
        for attempt in range(2):
            try:
                service.add_tracks(batch)
                return None
            except Exception as exc:  # noqa: BLE001
                if svc.is_fatal(exc):
                    raise
                if attempt:
                    return svc.describe_error(exc)
                time.sleep(2)

    def _poll(self):
        try:
            for _ in range(200):
                self._on_event(*self.events.get_nowait())
        except queue.Empty:
            pass
        self.root.after(40, self._poll)

    def _on_event(self, kind, *args):
        c = self.counts
        if kind == "auth_url":
            self.auth_url = args[0]
            self._render_account()
        elif kind == "auth_ok":
            self.user, self.phase, self.auth_silent = args[0], "idle", False
            self._render()
        elif kind == "auth_end":
            self.phase, self.auth_silent, self.auth_error = "idle", False, args[0]
            self._render()
        elif kind == "checked":
            c["checked"] = args[0]
            self._update_progress()
        elif kind == "plan":
            skipped, todo = args
            for uri in skipped:
                self.statuses[uri] = "skipped"
            c["skipped"], c["todo"] = len(skipped), todo
            self.phase = "import"
            self._render()
            self._update_progress()
            self.tracklist.refresh()
        elif kind in ("added", "failed"):
            uris = args[0]
            for uri in uris:
                self.statuses[uri] = kind
            c[kind] += len(uris)
            if kind == "failed":
                self.last_error = args[1]
            self.tracklist.reveal(uris[-1])
            self.tracklist.refresh()
            self._update_progress()
        elif kind == "finished":
            outcome, message = args
            if outcome in ("error", "cancelled"):
                result = outcome
                for uri, status in list(self.statuses.items()):
                    if status == "pending":
                        del self.statuses[uri]
            elif c["todo"] == 0:
                result = "nothing"
            else:
                result = "partial" if c["failed"] else "ok"
            self.result = {"kind": result, "message": message or self.last_error}
            self.phase = "done"
            self._render()
            self.tracklist.refresh()


def create_app(argv=None):
    parser = argparse.ArgumentParser(description="re:liked — import polubionych utworów Spotify")
    parser.add_argument("csv", nargs="?", help="plik CSV z Exportify (domyślnie CSV_FILE z .env)")
    parser.add_argument("--demo", action="store_true", help="tryb demo: bez logowania i bez zmian na koncie")
    args = parser.parse_args(argv)
    t.enable_dpi_awareness()
    root = None
    if TkinterDnD is not None:
        try:
            root = TkinterDnD.Tk()
        except (RuntimeError, tk.TclError):
            root = None
    root = root or tk.Tk()
    t.init(root)
    return root, App(root, demo=args.demo, csv_path=args.csv)


def main(argv=None):
    root, _app = create_app(argv)
    root.mainloop()
