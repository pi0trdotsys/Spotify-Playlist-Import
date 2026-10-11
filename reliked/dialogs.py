"""Ciemne okna dialogowe: ustawienia Spotify, instrukcja i potwierdzenie."""

import tkinter as tk
from urllib.parse import urlparse

from . import images as img
from . import theme as t
from .service import Config, ServiceError
from .theme import ICON, font, px
from .widgets import Link, Panel, PillButton, icon_label, icon_tile, label

DASHBOARD_URL = "https://developer.spotify.com/dashboard"
EXPORTIFY_URL = "https://exportify.net/"


class Dialog(tk.Toplevel):
    """Modalne okno w kolorach aplikacji, wyśrodkowane nad rodzicem."""

    def __init__(self, master, title, width=520):
        super().__init__(master, bg=t.BG)
        self.withdraw()
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.width = px(width)
        self.inner = self.width - 2 * px(28)
        self.content = tk.Frame(self, bg=t.BG)
        self.content.pack(fill="both", expand=True, padx=px(28), pady=px(24))
        self.bind("<Escape>", lambda e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)

    def heading(self, icon, title, subtitle=None, *, fill=t.GREEN_SOFT, fg=t.GREEN_HI):
        row = tk.Frame(self.content, bg=t.BG)
        row.pack(fill="x", pady=(0, px(18)))
        icon_tile(row, icon, size=42, fill=fill, fg=fg).pack(side="left", padx=(0, px(14)))
        texts = tk.Frame(row, bg=t.BG)
        texts.pack(side="left", fill="x", expand=True)
        label(texts, title, size="h2", anchor="w").pack(fill="x")
        if subtitle:
            label(texts, subtitle, fg=t.MUTED, size="small", anchor="w").pack(fill="x", pady=(px(2), 0))

    def buttons(self, *specs):
        row = tk.Frame(self.content, bg=t.BG)
        row.pack(fill="x", pady=(px(22), 0))
        for text, command, variant in reversed(specs):
            PillButton(row, text, command, variant=variant, height=40, font_name="btn_s").pack(side="right", padx=(px(10), 0))
        return row

    def show(self):
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        w, h = max(self.width, self.winfo_reqwidth()), self.winfo_reqheight()
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - h) // 3)
        self.geometry(f"{w}x{h}+{x}+{y}")
        t.style_titlebar(self)
        self.deiconify()
        self.grab_set()
        self.focus_set()

    def close(self):
        self.grab_release()
        self.destroy()


class SettingsDialog(Dialog):
    FIELDS = (
        ("client_id", "Client ID", False),
        ("client_secret", "Client Secret", True),
        ("redirect_uri", "Redirect URI", False),
    )

    def __init__(self, master, config, on_save):
        super().__init__(master, "Ustawienia Spotify", width=560)
        self.config, self.on_save = config, on_save
        c = self.content
        self.heading("settings", "Aplikacja Spotify", "Dane z Spotify Developer Dashboard")
        label(c, "Utwórz aplikację (zaznacz Web API) i dodaj w niej Redirect URI dokładnie taki jak niżej. "
                 "Potem wklej tutaj Client ID i Client Secret.",
              fg=t.MUTED, size="small", wraplength=self.inner, justify="left", anchor="w").pack(fill="x")
        Link(c, "Otwórz Developer Dashboard ↗", url=DASHBOARD_URL).pack(anchor="w", pady=(px(6), px(18)))
        self.vars = {}
        for key, title, secret in self.FIELDS:
            label(c, title, fg=t.MUTED, size="small", anchor="w").pack(fill="x", pady=(0, px(6)))
            self.vars[key] = self._field(getattr(config, key), secret)
        note = tk.Frame(c, bg=t.BG)
        note.pack(fill="x")
        icon_label(note, "lock", fg=t.DIM, size="icon_xs").pack(side="left", padx=(0, px(8)))
        label(note, "Zapisywane lokalnie w pliku .env (ignorowanym przez Git).", fg=t.DIM, size="tiny").pack(side="left")
        self.error = label(c, "", fg=t.RED, size="small", wraplength=self.inner, justify="left", anchor="w")
        self.buttons(("Anuluj", self.close, "outline"), ("Zapisz", self._save, "primary"))
        self.bind("<Return>", lambda e: self._save())
        self.show()
        empty = next((entry for var, entry in self.vars.values() if not var.get()), None)
        (empty or next(iter(self.vars.values()))[1]).focus_set()

    def _field(self, value, secret):
        panel = Panel(self.content, fill=t.FIELD, outline=t.LINE, radius=10, pad=(12, 9))
        panel.pack(fill="x", pady=(0, px(14)))
        var = tk.StringVar(value=value)
        entry = tk.Entry(panel.body, textvariable=var, show="•" if secret else "", bg=t.FIELD, fg=t.TEXT,
                         insertbackground=t.GREEN, relief="flat", bd=0, highlightthickness=0, font=font("mono"),
                         selectbackground=t.GREEN_SOFT_HI, selectforeground=t.TEXT)
        entry.pack(side="left", fill="x", expand=True)
        if secret:
            def toggle():
                entry.configure(show="" if entry.cget("show") else "•")
            Link(panel.body, ICON["eye"], toggle, fg=t.MUTED, hover=t.TEXT, font_name="icon_s").pack(side="right", padx=(px(8), 0))
        entry.bind("<FocusIn>", lambda e: panel.set_style(outline=t.GREEN_LINE))
        entry.bind("<FocusOut>", lambda e: panel.set_style(outline=t.LINE))
        return var, entry

    def _save(self):
        values = {key: var.get().strip() for key, (var, _entry) in self.vars.items()}
        redirect = urlparse(values["redirect_uri"])
        problem = None
        if not values["client_id"] or not values["client_secret"]:
            problem = "Wpisz Client ID i Client Secret."
        elif redirect.scheme != "http" or redirect.hostname not in ("127.0.0.1", "localhost") or not redirect.port:
            problem = "Redirect URI musi mieć postać http://127.0.0.1:<port>/callback."
        if not problem:
            try:
                self.on_save(Config(csv_file=self.config.csv_file, **values))
            except (ServiceError, OSError) as exc:
                problem = str(exc)
        if problem:
            self.error.configure(text=problem)
            self.error.pack(fill="x", pady=(px(12), 0), before=self.content.winfo_children()[-1])
            self.update_idletasks()
            self.geometry(f"{self.winfo_width()}x{self.winfo_reqheight()}")
            return
        self.close()


class HelpDialog(Dialog):
    def __init__(self, master, on_settings):
        super().__init__(master, "Instrukcja", width=600)
        self.heading("book", "Jak przenieść polubione utwory", "Cztery kroki, jednorazowo")
        steps = (
            ("Wyeksportuj polubione",
             "Na exportify.net zaloguj się STARYM kontem i pobierz „Liked Songs” jako CSV.",
             ("Otwórz Exportify ↗", EXPORTIFY_URL)),
            ("Utwórz aplikację Spotify",
             "W Developer Dashboard utwórz aplikację z Web API i Redirect URI http://127.0.0.1:8888/callback. "
             "W trybie Development dodaj NOWE konto w zakładce User Management — właściciel aplikacji musi mieć Premium.",
             ("Otwórz Developer Dashboard ↗", DASHBOARD_URL)),
            ("Wpisz dane aplikacji",
             "Wklej Client ID i Client Secret w Ustawieniach — zapiszą się w pliku .env.",
             ("Otwórz ustawienia", lambda: (self.close(), on_settings()))),
            ("Połącz i importuj",
             "Wybierz plik CSV, połącz NOWE konto (jeśli przeglądarka pamięta stare, kliknij „To nie Ty?”) "
             "i kliknij Importuj. Utwory polubione wcześniej zostaną pominięte.",
             None),
        )
        for number, (title, text, action) in enumerate(steps, 1):
            self._step(number, title, text, action)
        self.buttons(("Zamknij", self.close, "outline"))
        self.show()

    def _step(self, number, title, text, action):
        row = tk.Frame(self.content, bg=t.BG)
        row.pack(fill="x", pady=(0, px(16)))
        d = px(28)
        disc = tk.Canvas(row, bg=t.BG, highlightthickness=0, bd=0, width=d, height=d)
        disc.image = img.circle(d, t.GREEN_SOFT)
        disc.create_image(d / 2, d / 2, image=disc.image)
        disc.create_text(d / 2, d / 2, text=str(number), font=font("btn_s"), fill=t.GREEN_HI)
        disc.pack(side="left", anchor="n", padx=(0, px(14)))
        texts = tk.Frame(row, bg=t.BG)
        texts.pack(side="left", fill="x", expand=True)
        label(texts, title, size="body_b", anchor="w").pack(fill="x")
        label(texts, text, fg=t.MUTED, size="small", wraplength=self.inner - d - px(14),
              justify="left", anchor="w").pack(fill="x", pady=(px(3), 0))
        if action:
            caption, target = action
            if callable(target):
                Link(texts, caption + " →", target, fg=t.GREEN_HI, hover=t.TEXT).pack(anchor="w", pady=(px(5), 0))
            else:
                Link(texts, caption, url=target, fg=t.GREEN_HI, hover=t.TEXT).pack(anchor="w", pady=(px(5), 0))


class ConfirmDialog(Dialog):
    def __init__(self, master, title, message, confirm_text, on_confirm):
        super().__init__(master, title, width=460)
        self.heading("warning", title, fill=t.AMBER_SOFT, fg=t.AMBER)
        label(self.content, message, fg=t.MUTED, size="small", wraplength=self.inner,
              justify="left", anchor="w").pack(fill="x")
        self.buttons(("Wróć", self.close, "outline"), (confirm_text, lambda: (self.close(), on_confirm()), "danger"))
        self.show()
