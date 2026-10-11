"""Własne widżety: karty, przyciski, stepper, pasek postępu, lista utworów, nagłówek."""

import tkinter as tk
import webbrowser

from . import images as img
from . import theme as t
from .theme import ICON, font, px


def recolor(widget, old, new):
    """Zmienia tło widżetu i jego potomków, które miały kolor `old`."""
    try:
        if widget.cget("bg") == old:
            widget.configure(bg=new)
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        recolor(child, old, new)


def clamp(value, low, high):
    return max(low, min(high, value))


class Panel(tk.Frame):
    """Karta z wygładzonymi rogami; zawartość umieszcza się w `self.body`.

    Tło to Canvas schowany pod treścią (place), więc wysokość karty wynika
    z zawartości, a przy pack(expand=True) karta wypełnia dostępne miejsce.
    Wcięcie `pad` musi być większe niż ~0,3 promienia, żeby treść nie zasłaniała rogów.
    """

    def __init__(self, master, *, fill=t.PANEL, outline=t.LINE, radius=14, pad=16, dashed=False, bg=None):
        outer = bg or master.cget("bg")
        super().__init__(master, bg=outer)
        self.fill, self.outline, self.dashed = fill, outline, dashed
        self.radius = px(radius)
        padx, pady = pad if isinstance(pad, tuple) else (pad, pad)
        self._canvas = tk.Canvas(self, bg=outer, highlightthickness=0, bd=0)
        self._canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg_item = self._canvas.create_image(0, 0, anchor="nw")
        self._image = None
        self.body = tk.Frame(self, bg=fill)
        self.body.pack(fill="both", expand=True, padx=px(padx), pady=px(pady))
        self.bind("<Configure>", lambda e: self._paint(e.width, e.height))

    def _paint(self, w=None, h=None):
        w, h = w or self.winfo_width(), h or self.winfo_height()
        if w < 4 or h < 4:
            return
        width = px(1.2) if self.dashed else t.hairline()
        self._image = img.rounded_rect(w, h, self.radius, self.fill, self.outline, width, self.dashed)
        self._canvas.itemconfigure(self._bg_item, image=self._image)

    def set_style(self, *, fill=None, outline=..., dashed=None):
        if fill and fill != self.fill:
            recolor(self.body, self.fill, fill)
            self.fill = fill
        if outline is not ...:
            self.outline = outline
        if dashed is not None:
            self.dashed = dashed
        self._paint()

    def clear(self):
        for child in self.body.winfo_children():
            child.destroy()


class PillButton(tk.Canvas):
    """Przycisk w kształcie pigułki. Warianty: primary, outline, soft, danger."""

    def __init__(self, master, text, command=None, *, variant="primary", icon=None, icon_side="right",
                 height=40, width=None, radius=None, font_name="btn", bg=None):
        super().__init__(master, bg=bg or master.cget("bg"), highlightthickness=0, bd=0,
                         height=px(height), takefocus=1)
        self.text, self.icon, self.icon_side = text, icon, icon_side
        self.command, self.variant = command, variant
        self.radius = px(radius) if radius is not None else None
        self.font, self.icon_font = font(font_name), font("icon_s")
        self.fixed_width = px(width) if width else None
        self.disabled = self.busy = False
        self._hover = self._pressed = self._focus = False
        self._image = None
        self._resize()
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, pressed=False))
        self.bind("<ButtonPress-1>", lambda e: self._set(pressed=True))
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<FocusIn>", lambda e: self._set(focus=True))
        self.bind("<FocusOut>", lambda e: self._set(focus=False))
        self.bind("<Return>", lambda e: self.invoke())
        self.bind("<space>", lambda e: self.invoke())

    def _resize(self):
        if self.fixed_width:
            width = self.fixed_width
        else:
            width = self.font.measure(self.text) + 2 * px(18)
            if self.icon:
                width += self.icon_font.measure(self.icon) + px(8)
        self.configure(width=width)

    def _set(self, **state):
        for key, value in state.items():
            setattr(self, "_" + key, value)
        self._draw()

    def _on_release(self, event):
        pressed = self._pressed
        self._set(pressed=False)
        if pressed and 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height():
            self.invoke()

    def invoke(self):
        if self.command and not (self.disabled or self.busy):
            self.command()

    def set_state(self, text=None, *, variant=None, icon=..., disabled=None, busy=None, command=None):
        if text is not None:
            self.text = text
        if variant:
            self.variant = variant
        if icon is not ...:
            self.icon = icon
        if disabled is not None:
            self.disabled = disabled
        if busy is not None:
            self.busy = busy
        if command:
            self.command = command
        self.configure(cursor="arrow" if self.disabled else "watch" if self.busy else "hand2",
                       takefocus=0 if self.disabled else 1)
        self._resize()
        self._draw()

    def _colors(self):
        base = self.cget("bg")
        if self.disabled:
            if self.variant == "primary":
                return t.PANEL_DISABLED, None, t.DIM
            return base, t.LINE, t.DIM
        hover = self._hover and not self.busy
        if self.variant == "primary":
            fill = t.GREEN_PRESS if self._pressed else t.GREEN_HI if hover else t.GREEN
            return fill, None, t.GREEN_INK
        if self.variant == "soft":
            return (t.GREEN_SOFT_HI if hover else t.GREEN_SOFT), None, t.GREEN_HI
        if self.variant == "danger":
            return (t.RED_SOFT if hover else base), t.RED_LINE, t.RED
        return (t.mix(base, t.TEXT, 0.06) if hover else base), (t.GREEN_LINE if hover else t.LINE_STRONG), t.TEXT

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        fill, outline, fg = self._colors()
        if self._focus and not self.disabled:
            outline = t.TEXT
        radius = self.radius if self.radius is not None else h // 2
        self._image = img.rounded_rect(w, h, radius, fill, outline, t.hairline())
        self.create_image(0, 0, image=self._image, anchor="nw")
        text_w = self.font.measure(self.text)
        icon_w = self.icon_font.measure(self.icon) if self.icon else 0
        gap = px(8) if self.icon else 0
        x, cy = (w - text_w - icon_w - gap) / 2, h / 2
        if self.icon and self.icon_side == "left":
            self.create_text(x, cy + px(1), text=self.icon, font=self.icon_font, fill=fg, anchor="w")
            x += icon_w + gap
        self.create_text(x, cy, text=self.text, font=self.font, fill=fg, anchor="w")
        if self.icon and self.icon_side == "right":
            self.create_text(x + text_w + gap, cy + px(1), text=self.icon, font=self.icon_font, fill=fg, anchor="w")


class Link(tk.Label):
    """Tekst-odnośnik z podświetleniem po najechaniu."""

    def __init__(self, master, text, command=None, *, url=None, fg=t.TEXT, hover=t.GREEN_HI,
                 font_name="small", bg=None):
        super().__init__(master, text=text, fg=fg, bg=bg or master.cget("bg"), font=font(font_name),
                         cursor="hand2", bd=0, padx=0, pady=0)
        self._fg, self._hover = fg, hover
        self.command = command or (lambda: webbrowser.open(url))
        self.bind("<Enter>", lambda e: self.configure(fg=self._hover))
        self.bind("<Leave>", lambda e: self.configure(fg=self._fg))
        self.bind("<Button-1>", lambda e: self.command())


def icon_label(master, name, fg=t.MUTED, size="icon_s", bg=None):
    return tk.Label(master, text=ICON[name], font=font(size), fg=fg, bg=bg or master.cget("bg"), bd=0, padx=0, pady=0)


def icon_tile(master, icon, *, size=40, fill=t.GREEN_SOFT, fg=t.GREEN_HI, radius=None, icon_size="icon", bg=None):
    """Ikona na zaokrąglonym (lub okrągłym, gdy radius=None) tle."""
    canvas = tk.Canvas(master, bg=bg or master.cget("bg"), highlightthickness=0, bd=0, width=px(size), height=px(size))
    d = px(size)
    canvas.image = img.circle(d, fill) if radius is None else img.rounded_rect(d, d, px(radius), fill)
    canvas.create_image(d / 2, d / 2, image=canvas.image)
    canvas.create_text(d / 2, d / 2 + px(1), text=ICON[icon], font=font(icon_size), fill=fg)
    return canvas


def label(master, text="", fg=t.TEXT, size="body", bg=None, **kw):
    return tk.Label(master, text=text, font=font(size), fg=fg, bg=bg or master.cget("bg"), bd=0, padx=0, pady=0, **kw)


class Badge(tk.Canvas):
    """Mała etykieta w kształcie pigułki."""

    def __init__(self, master, text, *, fg=t.GREEN_HI, outline=t.GREEN_LINE, fill=None, bg=None):
        super().__init__(master, bg=bg or master.cget("bg"), highlightthickness=0, bd=0)
        self._image = None
        self.set(text, fg=fg, outline=outline, fill=fill)

    def set(self, text, *, fg=None, outline=..., fill=...):
        self.text = text
        self.fg = fg or self.fg
        if outline is not ...:
            self.outline = outline
        if fill is not ...:
            self.fill = fill
        f = font("tiny")
        w, h = f.measure(text) + 2 * px(10), px(22)
        self.configure(width=w, height=h)
        self.delete("all")
        self._image = img.rounded_rect(w, h, h // 2, self.fill, self.outline, t.hairline())
        self.create_image(0, 0, image=self._image, anchor="nw")
        self.create_text(w / 2, h / 2, text=text, font=f, fill=self.fg)


class Stepper(tk.Canvas):
    """Trzy etapy importu połączone liniami."""

    def __init__(self, master, labels):
        super().__init__(master, bg=master.cget("bg"), highlightthickness=0, bd=0, height=px(30))
        self.labels = labels
        self.active, self.complete = 0, frozenset()
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, active, complete):
        complete = frozenset(complete)
        if (active, complete) != (self.active, self.complete):
            self.active, self.complete = active, complete
            self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            return
        cy, d, gap, margin = h / 2, px(26), px(10), px(20)
        fonts = [font("body_b") if i == self.active else font("body") for i in range(len(self.labels))]
        widths = [d + gap + f.measure(text) for f, text in zip(fonts, self.labels)]
        line_len = (w - sum(widths)) / max(1, len(self.labels) - 1)
        x = 0
        for i, text in enumerate(self.labels):
            done, active = i in self.complete, i == self.active
            if done:
                disc, mark, mark_font, mark_fg = img.circle(d, t.GREEN_SOFT), ICON["check"], font("icon_xs"), t.GREEN_HI
            elif active:
                disc, mark, mark_font, mark_fg = img.circle(d, t.GREEN), str(i + 1), font("btn_s"), t.GREEN_INK
            else:
                disc, mark, mark_font, mark_fg = img.circle(d, t.BG, t.LINE_STRONG, t.hairline()), str(i + 1), font("small"), t.MUTED
            self.create_image(x + d / 2, cy, image=disc)
            self.create_text(x + d / 2, cy, text=mark, font=mark_font, fill=mark_fg)
            self.create_text(x + d + gap, cy, text=text, font=fonts[i], anchor="w",
                             fill=t.TEXT if (done or active) else t.MUTED)
            x += widths[i]
            if i < len(self.labels) - 1:
                thickness = max(1, px(1.5))
                self.create_rectangle(x + margin, cy - thickness / 2, x + line_len - margin, cy + thickness / 2,
                                      fill=t.GREEN if done else t.LINE, width=0)
                x += line_len


class ProgressBar(tk.Canvas):
    """Pasek postępu z płynną animacją i trybem nieokreślonym."""

    def __init__(self, master):
        super().__init__(master, bg=master.cget("bg"), highlightthickness=0, bd=0, height=px(8))
        self.value = self.shown = 0.0
        self.indeterminate = False
        self._phase, self._job, self._images = 0.0, None, []
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, value, instant=False):
        self.indeterminate = False
        self.value = clamp(value, 0.0, 1.0)
        if instant:
            self.shown = self.value
        self._kick()

    def pulse(self):
        self.indeterminate = True
        self._kick()

    def stop(self):
        if self._job:
            self.after_cancel(self._job)
            self._job = None

    def _kick(self):
        if not self._job:
            self._job = self.after(16, self._tick)

    def _tick(self):
        self._job = None
        if self.indeterminate:
            self._phase = (self._phase + 0.011) % 1.3
            again = True
        else:
            diff = self.value - self.shown
            self.shown = self.value if abs(diff) < 0.002 else self.shown + diff * 0.15
            again = self.shown != self.value
        self._draw()
        if again:
            self._job = self.after(16, self._tick)

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            return
        r = h // 2
        self._images = [img.rounded_rect(w, h, r, t.LINE_SOFT)]
        self.create_image(0, 0, image=self._images[0], anchor="nw")
        if self.indeterminate:
            x0 = clamp((self._phase - 0.3) * w, 0, w)
            x1 = clamp(self._phase * w, 0, w)
            if x1 - x0 >= h:
                self._images.append(img.rounded_rect(int(x1 - x0), h, r, t.GREEN))
                self.create_image(x0, 0, image=self._images[-1], anchor="nw")
        elif self.shown > 0:
            fill_w = max(h, int(w * self.shown))
            self._images.append(img.rounded_rect(fill_w, h, r, t.GREEN))
            self.create_image(0, 0, image=self._images[-1], anchor="nw")


class SearchBox(Panel):
    """Pole wyszukiwania z ikoną, podpowiedzią i przyciskiem czyszczenia."""

    def __init__(self, master, on_change, placeholder):
        super().__init__(master, fill=t.FIELD, outline=t.LINE, radius=10, pad=(12, 8))
        self.on_change, self._job = on_change, None
        self.var = tk.StringVar()
        body = self.body
        body.columnconfigure(1, weight=1)
        icon_label(body, "search", fg=t.MUTED).grid(row=0, column=0, padx=(0, px(10)))
        self.entry = tk.Entry(body, textvariable=self.var, bg=t.FIELD, fg=t.TEXT, insertbackground=t.GREEN,
                              relief="flat", bd=0, highlightthickness=0, font=font("body"),
                              selectbackground=t.GREEN_SOFT_HI, selectforeground=t.TEXT)
        self.entry.grid(row=0, column=1, sticky="ew")
        self.placeholder = label(body, placeholder, fg=t.DIM, anchor="w")
        self.placeholder.grid(row=0, column=1, sticky="ew")
        self.placeholder.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.clear_btn = Link(body, ICON["close"], self.clear, fg=t.MUTED, hover=t.TEXT, font_name="icon_xs")
        self.var.trace_add("write", self._changed)
        self.entry.bind("<FocusIn>", lambda e: self.set_style(outline=t.GREEN_LINE))
        self.entry.bind("<FocusOut>", lambda e: self.set_style(outline=t.LINE))
        self.entry.bind("<Escape>", lambda e: self.clear())

    def clear(self):
        self.var.set("")

    def _changed(self, *_):
        text = self.var.get()
        if text:
            self.placeholder.grid_remove()
            self.clear_btn.grid(row=0, column=2, padx=(px(8), 0))
        else:
            self.placeholder.grid()
            self.clear_btn.grid_remove()
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(140, lambda: self.on_change(self.var.get()))


class TrackList(tk.Canvas):
    """Wirtualizowana lista utworów: rysuje tylko widoczne wiersze, płynnie przewija."""

    STATUS = {
        "pending": ("clock", t.DIM),
        "added": ("done_fill", t.GREEN),
        "skipped": ("heart_fill", t.MUTED),
        "failed": ("error", t.RED),
        "local": ("warning", t.AMBER),
    }

    def __init__(self, master, *, bg):
        super().__init__(master, bg=bg, highlightthickness=0, bd=0, takefocus=0)
        self.row_h, self.header_h = px(54), px(34)
        self.tracks, self.view, self.index, self.position = [], [], {}, {}
        self.statuses = {}
        self.query = ""
        self.offset = self.target = 0.0
        self.follow = True
        self.hover = None
        self._anim = None
        self._drag = None
        self._thumb = None
        self._fit_cache = {}
        self._images = []
        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag", None) or self._redraw())
        self.bind("<Double-Button-1>", self._on_double)

    # --- dane ---
    def set_tracks(self, tracks):
        self.tracks = tracks
        self.index = {track.uri: i for i, track in enumerate(tracks)}
        self._apply_filter()

    def set_query(self, query):
        self.query = query.strip().casefold()
        self._apply_filter()

    def _apply_filter(self):
        if self.query:
            self.view = [i for i, track in enumerate(self.tracks) if self.query in track.search_key]
        else:
            self.view = list(range(len(self.tracks)))
        self.position = {i: p for p, i in enumerate(self.view)}
        self.offset = self.target = 0.0
        self.hover = None
        self._redraw()

    def refresh(self):
        self._redraw()

    def reveal(self, uri):
        """W trybie śledzenia przewija listę do utworu, który właśnie przetworzono."""
        pos = self.position.get(self.index.get(uri))
        if not self.follow or pos is None:
            return
        top, h = pos * self.row_h, self.view_h
        if top < self.target or top + self.row_h > self.target + h:
            self._scroll_to(top - h / 2 + self.row_h / 2)

    # --- przewijanie ---
    @property
    def view_h(self):
        """Wysokość obszaru wierszy (pod przypiętym nagłówkiem kolumn)."""
        return max(1, self.winfo_height() - self.header_h)

    @property
    def max_offset(self):
        return max(0, len(self.view) * self.row_h - self.view_h)

    def _scroll_to(self, y, animate=True):
        self.target = clamp(y, 0, self.max_offset)
        if not animate:
            self.offset = self.target
            self._redraw()
        elif not self._anim:
            self._animate()

    def _animate(self):
        self._anim = None
        diff = self.target - self.offset
        if abs(diff) < 0.5:
            self.offset = self.target
        else:
            self.offset += diff * 0.25
            self._anim = self.after(16, self._animate)
        self._redraw()

    def _on_wheel(self, event):
        self.follow = False
        self._scroll_to(self.target - event.delta / 120 * self.row_h * 2.5)

    def _on_motion(self, event):
        if event.x > self.winfo_width() - px(16) or event.y < self.header_h:
            self._set_hover(None)
            return
        pos = int((event.y - self.header_h + self.offset) // self.row_h)
        self._set_hover(pos if 0 <= pos < len(self.view) else None)

    def _set_hover(self, pos):
        if pos != self.hover:
            self.hover = pos
            self.configure(cursor="hand2" if pos is not None else "")
            self._redraw()

    def _on_press(self, event):
        if self._thumb and event.x > self.winfo_width() - px(16):
            top, size, content = self._thumb
            y, h = event.y - self.header_h, self.view_h
            if not top <= y <= top + size:
                ratio = clamp((y - size / 2) / max(1, h - size), 0, 1)
                self._scroll_to(ratio * (content - h), animate=False)
                top = (self.offset / (content - h)) * (h - size)
            self._drag = y - top
            self.follow = False

    def _on_drag(self, event):
        if self._drag is None or not self._thumb:
            return
        _, size, content = self._thumb
        h = self.view_h
        ratio = clamp((event.y - self.header_h - self._drag) / max(1, h - size), 0, 1)
        self._scroll_to(ratio * (content - h), animate=False)

    def _on_double(self, event):
        if self.hover is not None:
            track = self.tracks[self.view[self.hover]]
            if track.importable:
                webbrowser.open("https://open.spotify.com/track/" + track.uri.rsplit(":", 1)[-1])

    # --- rysowanie ---
    def _fit(self, text, font_name, width):
        key = (text, font_name, width)
        fitted = self._fit_cache.get(key)
        if fitted is None:
            f = font(font_name)
            if f.measure(text) <= width:
                fitted = text
            else:
                lo, hi = 0, len(text)
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if f.measure(text[:mid].rstrip() + "…") <= width:
                        lo = mid
                    else:
                        hi = mid - 1
                fitted = text[:lo].rstrip() + "…"
            if len(self._fit_cache) > 6000:
                self._fit_cache.clear()
            self._fit_cache[key] = fitted
        return fitted

    def _redraw(self):
        self.delete("all")
        self._images = []
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20 or h < 20:
            return
        if not self.view:
            self._draw_empty(w, h)
            return
        rh, head = self.row_h, self.header_h
        self.offset = clamp(self.offset, 0, self.max_offset)
        first = int(self.offset // rh)
        last = min(len(self.view), int((self.offset + h - head) // rh) + 1)
        pad, cover = px(14), px(38)
        x_index = pad + px(30)
        x_cover = x_index + px(10)
        x_text = x_cover + cover + px(14)
        x_status = w - pad - px(12)
        x_time = x_status - px(22)
        text_w = max(20, x_time - px(52) - x_text)
        hover_img = img.rounded_rect(w - px(12), rh - px(6), px(10), t.PANEL_HOVER)
        for pos in range(first, last):
            i = self.view[pos]
            track = self.tracks[i]
            top = head + pos * rh - self.offset
            cy = top + rh / 2
            if pos == self.hover:
                self._images.append(hover_img)
                self.create_image(px(6), top + px(3), image=hover_img, anchor="nw")
            elif pos + 1 != self.hover and pos != last - 1:
                self.create_line(x_text, top + rh, w - pad, top + rh, fill=t.LINE_SOFT)
            self.create_text(x_index, cy, text=str(i + 1), font=font("mono_s"), fill=t.DIM, anchor="e")
            cover_img = img.cover(cover, track.cover_index)
            self._images.append(cover_img)
            self.create_image(x_cover, cy, image=cover_img, anchor="w")
            self.create_text(x_text, cy - px(9), text=self._fit(track.name, "body", text_w),
                             font=font("body"), fill=t.TEXT, anchor="w")
            self.create_text(x_text, cy + px(10), text=self._fit(track.artists, "small", text_w),
                             font=font("small"), fill=t.MUTED, anchor="w")
            self.create_text(x_time, cy, text=track.duration, font=font("mono_s"), fill=t.MUTED, anchor="e")
            status = self.statuses.get(track.uri) or (None if track.importable else "local")
            if status:
                name, color = self.STATUS[status]
                self.create_text(x_status, cy, text=ICON[name], font=font("icon_s"), fill=color)
        # Przypięty nagłówek kolumn zasłania wiersze wjeżdżające pod niego.
        self.create_rectangle(0, 0, w, head, fill=self.cget("bg"), width=0)
        hy = head / 2 - px(2)
        self.create_text(x_index, hy, text="#", font=font("tiny"), fill=t.DIM, anchor="e")
        self.create_text(x_text, hy, text=t.spaced("TYTUŁ / WYKONAWCA"), font=font("tiny"), fill=t.DIM, anchor="w")
        self.create_text(x_time, hy, text=ICON["clock"], font=font("icon_xs"), fill=t.DIM, anchor="e")
        self.create_line(pad, head - 1, w - pad, head - 1, fill=t.LINE)
        self._draw_scrollbar(w)

    def _draw_scrollbar(self, w):
        content, h = len(self.view) * self.row_h, self.view_h
        if content <= h:
            self._thumb = None
            return
        size = max(px(36), h * h / content)
        top = (self.offset / (content - h)) * (h - size)
        x, y = w - px(6), self.header_h + top
        color = t.MUTED if self._drag is not None else t.LINE_STRONG
        self.create_line(x, y + px(4), x, y + size - px(4), width=px(4), fill=color, capstyle="round")
        self._thumb = (top, size, content)

    def _draw_empty(self, w, h):
        cy = h * 0.42
        disc = img.circle(px(60), t.FIELD, t.LINE, t.hairline())
        self._images.append(disc)
        self.create_image(w / 2, cy, image=disc)
        if self.query:
            icon, title, sub = "search", "Brak wyników", f"Nic nie pasuje do „{self.query}”."
        else:
            icon, title, sub = "headphones", "Tu pojawi się Twoja kolekcja", "Wgraj plik CSV z Exportify, żeby zobaczyć podgląd utworów."
        self.create_text(w / 2, cy, text=ICON[icon], font=font("icon_l"), fill=t.MUTED)
        self.create_text(w / 2, cy + px(52), text=title, font=font("body_b"), fill=t.TEXT)
        self.create_text(w / 2, cy + px(76), text=sub, font=font("small"), fill=t.MUTED,
                         width=w - px(80), justify="center", anchor="n")


class Hero(tk.Canvas):
    """Nagłówek okna: logo, odnośniki, hasło i obracający się winyl na tle z poświatą."""

    HEADER, HEIGHT, VINYL = 62, 194, 128

    def __init__(self, master, *, badge, demo, on_settings, on_help):
        super().__init__(master, bg=t.BG, highlightthickness=0, bd=0, height=px(self.HEIGHT))
        self.badge, self.demo = badge, demo
        self.on_settings, self.on_help = on_settings, on_help
        self.spinning = False
        self._frame, self._job = 0, None
        self._refs = {}
        self._vinyl_item = None
        self.bind("<Configure>", lambda e: self._draw())

    def set_spinning(self, on):
        if on == self.spinning:
            return
        self.spinning = on
        self._draw()
        if on and not self._job:
            self._tick()

    def _tick(self):
        self._job = None
        if not self.spinning:
            return
        frames = self._refs.get("frames")
        if frames and self._vinyl_item:
            self._frame = (self._frame + 1) % len(frames)
            self.itemconfigure(self._vinyl_item, image=frames[self._frame])
        self._job = self.after(36, self._tick)

    def _link(self, right, cy, text, icon, command, tag):
        f, fi = font("small"), font("icon_s")
        text_w = f.measure(text)
        self.create_text(right, cy, text=text, font=f, fill=t.MUTED, anchor="e", tags=tag)
        self.create_text(right - text_w - px(8), cy + px(1), text=ICON[icon], font=fi, fill=t.MUTED, anchor="e", tags=tag)
        self.tag_bind(tag, "<Enter>", lambda e: (self.itemconfigure(tag, fill=t.TEXT), self.configure(cursor="hand2")))
        self.tag_bind(tag, "<Leave>", lambda e: (self.itemconfigure(tag, fill=t.MUTED), self.configure(cursor="")))
        self.tag_bind(tag, "<Button-1>", lambda e: command())
        return right - text_w - px(8) - fi.measure(ICON[icon])

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50:
            return
        header, d, margin = px(self.HEADER), px(self.VINYL), px(40)
        arm_left = w - margin - int(d * 1.25)
        vx, vy = arm_left + d / 2, header + (h - header) / 2 + px(4)
        refs = self._refs
        refs["glow"] = img.glow_background(w, h, t.BG, [
            (vx, vy, px(400), px(220), t.GREEN, 0.22),
            (w * 0.5, -px(30), px(560), px(150), t.GREEN, 0.06),
        ])
        self.create_image(0, 0, image=refs["glow"], anchor="nw")
        self.create_line(0, header, w, header, fill=t.LINE)

        # Logo i znaczek wersji.
        cy = header / 2
        refs["brand"] = img.circle(px(30), t.GREEN)
        self.create_image(margin + px(15), cy, image=refs["brand"])
        self.create_text(margin + px(15), cy + px(1), text=ICON["music"], font=font("icon_s"), fill=t.GREEN_INK)
        self.create_text(margin + px(40), cy, text="re:liked", font=font("brand"), fill=t.TEXT, anchor="w")
        bx = margin + px(40) + font("brand").measure("re:liked") + px(12)
        bw, bh = font("tiny").measure(self.badge) + px(16), px(20)
        refs["badge"] = img.rounded_rect(bw, bh, px(6), None, t.AMBER_LINE if self.demo else t.LINE_STRONG, t.hairline())
        self.create_image(bx, cy, image=refs["badge"], anchor="w")
        self.create_text(bx + bw / 2, cy, text=self.badge, font=font("tiny"), fill=t.AMBER if self.demo else t.MUTED)

        right = self._link(w - margin, cy, "Instrukcja", "book", self.on_help, "help")
        self._link(right - px(28), cy, "Ustawienia", "settings", self.on_settings, "settings")

        # Hasło.
        self.create_text(margin, header + px(34), text=t.spaced("SPOTIFY · LIKED SONGS"),
                         font=font("eyebrow"), fill=t.GREEN_HI, anchor="w")
        self.create_text(margin, header + px(72), text="Nowe konto. Ta sama muzyka.",
                         font=font("h1"), fill=t.TEXT, anchor="w")
        self.create_text(margin, header + px(110), text="Przenieś polubione utwory ze starego konta na nowe — bez ręcznego klikania.",
                         font=font("body"), fill=t.MUTED, anchor="w")

        # Winyl z ramieniem gramofonu.
        refs["frames"] = img.vinyl_frames(d)
        self._frame %= len(refs["frames"])
        self._vinyl_item = self.create_image(vx, vy, image=refs["frames"][self._frame])
        self.create_text(vx, vy + px(1), text=ICON["heart_fill"], font=font("icon"), fill=t.GREEN_INK)
        refs["arm"] = img.tonearm(d, self.spinning)
        self.create_image(arm_left, vy - d / 2, image=refs["arm"], anchor="nw")
