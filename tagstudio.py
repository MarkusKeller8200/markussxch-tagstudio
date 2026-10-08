#!/usr/bin/env python3
"""
MarKusSXCH TagStudio – MP3-Tagger, Vergleich (im Stil von Beyond Compare), Tag-Fixer und mehr.

Links und rechts je einen Ordner oder eine Datei laden. Alle ID3-Felder werden
zeilenweise gegenübergestellt, Unterschiede rot und zeichengenau markiert. Felder lassen
sich einzeln, als Auswahl oder komplett nach links/rechts kopieren, direkt bearbeiten
und speichern. Läuft auf Windows und macOS mit Python 3.9+ (ohne Zusatzpakete).
"""
from __future__ import annotations

import hashlib
import re
import os
import queue
import subprocess
import threading
import time
import sys
import tempfile
import tkinter as tk
from tkinter import ttk, font as tkfont
from tkinter import filedialog as _filedialog, messagebox as _messagebox
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from id3tags import (MP3File, Item, Cover, key_label, sort_key, TEXT_LABELS,  # noqa: E402
                     PIC_TYPES, STANDARD_KEYS, MV, MV_SHOW, V23_JOIN)
import backup  # noqa: E402
import thumbs  # noqa: E402
from undo import UndoStack  # noqa: E402,F401
import core  # noqa: E402
import xmltools  # noqa: E402
from core import URL_RE, FILTER_OPS  # noqa: E402,F401
from compare import (diff, copy_tags, all_keys, PAIR_MODES, Rules, DEFAULT_TRIVIAL,  # noqa: E402
                     Cancelled, MULTI_FIELDS, INPUT_SEPARATORS, plan_multi_fix)  # noqa: E402

APP = "MarKusSXCH TagStudio"
VERSION = "2.9"
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")
MOD = "Command" if IS_MAC else "Control"
MOD_TXT = "Cmd" if IS_MAC else "Strg"
CONFIG = core.CONFIG          # Einstellungen (gemeinsam mit der Web-Oberfläche)
CONFIG_OLD = core.CONFIG_OLD

THEMES = {
    "dark": dict(
        bg="#1e1f22", bar="#2b2d30", panel="#232427", head="#2f3134", fg="#dcdee3",
        dim="#8b8f96", border="#3b3e43", hover="#3a3d42", press="#45494f", accent="#3d7ef5",
        sel="#24467a", entry="#1a1b1e", grid="#34363b",
        diff_bg="#4b1417", chg="#ff6b6b", triv_bg="#3b2c12", triv_chg="#f0b04a",
        only_bg="#3d2650", miss_bg="#2a2b2f", mod="#4fc3ff", ok="#62c26a",
        g_cmp="#5aa2ff", g_copy="#f0a83c", g_save="#62c26a", g_warn="#ff6b6b", g_misc="#c5c8ce",
    ),
    "light": dict(
        bg="#eef0f3", bar="#f7f8fa", panel="#ffffff", head="#e9ebee", fg="#1d1f23",
        dim="#6a6f78", border="#cfd3d9", hover="#e2e6ec", press="#d3d9e2", accent="#2f6fde",
        sel="#cfe0fc", entry="#ffffff", grid="#e3e5e9",
        diff_bg="#fde4e4", chg="#d00000", triv_bg="#fff3dc", triv_chg="#b35c00",
        only_bg="#f1e4fb", miss_bg="#f0f1f3", mod="#0062cc", ok="#2e8b3a",
        g_cmp="#2f6fde", g_copy="#d07a00", g_save="#2e8b3a", g_warn="#d00000", g_misc="#4b5058",
    ),
}
NAME_W = 250  # Breite der Namensspalte in Pixel



_APP = None  # Hauptfenster, wird beim Start gesetzt


def _active_window():
    """Aktuell aktives Programmfenster (Dialog oder Hauptfenster) – Bezug für Meldungen/Dateidialoge."""
    if _APP is None:
        return None
    try:
        w = _APP.focus_get()
        if w is not None:
            top = w.winfo_toplevel()
            if top.winfo_viewable() and not getattr(top, "_is_tip", False):
                return top
    except (KeyError, tk.TclError):
        pass
    return _APP


class _Parented:
    """Leitet messagebox/filedialog weiter und setzt parent automatisch → Dialog erscheint über dem Programm
    (auf dem Bildschirm, auf dem das Programm gerade liegt)."""

    def __init__(self, mod):
        self._mod = mod

    def __getattr__(self, name):
        fn = getattr(self._mod, name)
        if not callable(fn):
            return fn

        def call(*a, **k):
            if k.get("parent") is None:
                p = _active_window()
                if p is not None:
                    k["parent"] = p
            return fn(*a, **k)
        return call


messagebox = _Parented(_messagebox)
filedialog = _Parented(_filedialog)



def _dpi_aware():
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass


# =========================================================================== Toolbar-Button
class ToolButton(tk.Frame):
    def __init__(self, master, app, glyph, text, command, color="g_misc", toggle=False, tip=""):
        super().__init__(master, bd=0, highlightthickness=0, cursor="hand2")
        self.app, self.command, self.color, self.toggle = app, command, color, toggle
        self.active = False
        self.enabled = True
        self.g = tk.Label(self, text=glyph, font=app.f_glyph, bd=0, padx=6)
        self.t = tk.Label(self, text=text, font=app.f_small, bd=0, padx=4)
        self.g.pack(pady=(4, 0))
        self.t.pack(pady=(0, 4))
        for w in (self, self.g, self.t):
            w.bind("<Enter>", lambda e: self._paint(hover=True))
            w.bind("<Leave>", lambda e: self._paint())
            w.bind("<ButtonRelease-1>", self._click)
        if tip:
            Tooltip(self, tip, app)
        self._paint()

    def _click(self, _e):
        if self.enabled and self.command:
            self.command()

    def set_active(self, v):
        self.active = v
        self._paint()

    def set_enabled(self, v):
        self.enabled = v
        self._paint()

    def _paint(self, hover=False):
        th = self.app.th
        bg = th["sel"] if self.active else (th["hover"] if hover and self.enabled else th["bar"])
        gfg = th[self.color] if self.enabled else th["border"]
        tfg = th["fg"] if self.enabled else th["dim"]
        for w in (self, self.g, self.t):
            w.configure(bg=bg)
        self.g.configure(fg=gfg)
        self.t.configure(fg=tfg)


class Tooltip:
    def __init__(self, widget, text, app):
        self.w, self.text, self.app, self.tip, self.job = widget, text, app, None, None
        for w in [widget] + list(widget.winfo_children()):
            w.bind("<Enter>", self._sched, add="+")
            w.bind("<Leave>", self._hide, add="+")

    def _sched(self, _e):
        self.job = self.w.after(600, self._show)

    def _show(self):
        if self.tip:
            return
        x, y = self.w.winfo_rootx() + 10, self.w.winfo_rooty() + self.w.winfo_height() + 4
        self.tip = tk.Toplevel(self.w)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        th = self.app.th
        tk.Label(self.tip, text=self.text, bg=th["head"], fg=th["fg"], font=self.app.f_small,
                 padx=8, pady=4, relief="solid", bd=1).pack()

    def _hide(self, _e):
        if self.job:
            self.w.after_cancel(self.job)
            self.job = None
        if self.tip:
            self.tip.destroy()
            self.tip = None



# =========================================================================== Fortschritt
class ProgressDialog:
    """Modaler Fortschrittsdialog mit Abbrechen. Erscheint erst nach kurzer Zeit (kein Flackern)."""

    def __init__(self, app, cancel_event, delay_ms=300, title="Dateien einlesen", first="Zähle Dateien …",
                 total_fmt="Lese Tags von {n} Dateien …", count_fmt="{n} MP3-Dateien gefunden", hint=""):
        self.app, self.cancel = app, cancel_event
        self.total_fmt, self.count_fmt = total_fmt, count_fmt
        self.t0 = time.monotonic()
        self.total = 0
        self.closed = False
        th = app.th
        w = self.win = tk.Toplevel(app)
        w.withdraw()
        w.title(title)
        w.configure(bg=th["bg"])
        w.transient(app)
        w.resizable(False, False)
        w.protocol("WM_DELETE_WINDOW", self.do_cancel)
        w.bind("<Escape>", lambda e: self.do_cancel())
        f = ttk.Frame(w, padding=18)
        f.pack(fill="both", expand=True)
        self.phase = ttk.Label(f, text=first, font=app.f_title)
        self.phase.pack(anchor="w")
        self.bar = ttk.Progressbar(f, orient="horizontal", length=460, mode="indeterminate")
        self.bar.pack(fill="x", pady=(10, 6))
        self.bar.start(12)
        self.count = ttk.Label(f, text=count_fmt.format(n=0))
        self.count.pack(anchor="w")
        if hint:
            ttk.Label(f, text=hint, style="Dim.TLabel").pack(anchor="w", pady=(4, 0))
        self.file = ttk.Label(f, text="", style="Dim.TLabel", width=70)
        self.file.pack(anchor="w", pady=(2, 0))
        bf = ttk.Frame(f)
        bf.pack(fill="x", pady=(14, 0))
        self.btn = ttk.Button(bf, text="Abbrechen", command=self.do_cancel)
        self.btn.pack(side="right")
        app.config(cursor="watch")
        app._status("⏳", "Lese Dateien …", "dim")
        w.after(delay_ms, self._show)

    def _show(self):
        if self.closed:
            return
        w = self.win
        w.update_idletasks()
        a = self.app
        x = a.winfo_rootx() + (a.winfo_width() - w.winfo_reqwidth()) // 2
        y = a.winfo_rooty() + (a.winfo_height() - w.winfo_reqheight()) // 3
        w.geometry(f"+{max(0, x)}+{max(0, y)}")
        w.deiconify()
        try:
            w.grab_set()
        except tk.TclError:
            pass
        self.btn.focus_set()

    def update_state(self, m):
        if m[0] == "count":
            self.count.configure(text=self.count_fmt.format(n=fmt_n(m[1])))
        elif m[0] == "total":
            self.total = m[1]
            self.t0 = time.monotonic()
            self.bar.stop()
            self.bar.configure(mode="determinate", maximum=max(1, m[1]), value=0)
            self.phase.configure(text=self.total_fmt.format(n=fmt_n(m[1])))
        elif m[0] == "progress":
            i, total, path = m[1], m[2], m[3]
            self.bar.configure(value=i)
            pct = i * 100 // max(1, total)
            el = time.monotonic() - self.t0
            eta = ""
            if i >= 5 and el > 1:
                rest = el / i * (total - i)
                mm, ss = divmod(int(rest), 60)
                eta = f"   ·   noch ca. {mm}:{ss:02d}"
            self.count.configure(text=f"{fmt_n(i)} / {fmt_n(total)}   ·   {pct} %{eta}")
            name = os.path.basename(path)
            self.file.configure(text=name if len(name) <= 80 else name[:77] + "…")
        elif m[0] == "pairing":
            self.phase.configure(text="Ordne Dateien zu …")

    def do_cancel(self):
        if not self.cancel.is_set():
            self.cancel.set()
            self.phase.configure(text="Breche ab …")
            self.btn.state(["disabled"])

    def close(self):
        self.closed = True
        try:
            self.bar.stop()
            self.win.grab_release()
        except tk.TclError:
            pass
        self.win.destroy()
        self.app.config(cursor="")


def fmt_n(n):
    return f"{n:,}".replace(",", "'")


# =========================================================================== Hauptfenster
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        global _APP
        _APP = self
        self.cfg = self._load_cfg()
        self.th = THEMES[self.cfg.get("theme", "dark")]
        self.title(f"{APP} {VERSION}")
        self.geometry(self.cfg.get("geometry", "1500x920"))
        self.minsize(1050, 650)
        # neue Standard-Muster für "unwichtig" auch in bestehende Einstellungen übernehmen
        triv = list(self.cfg.get("trivial", DEFAULT_TRIVIAL))
        known = set(self.cfg.get("trivial_known", triv))
        triv += [p for p in DEFAULT_TRIVIAL if p not in known and p not in triv]
        self.cfg["trivial_known"] = sorted(known | set(DEFAULT_TRIVIAL))
        self.rules = Rules(triv)

        self.dpi = max(1.0, self.winfo_fpixels("1i") / 96)
        self.name_w = int(NAME_W * self.dpi)
        self.name_auto = True
        self._fonts()
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self.pairs: list = []
        self.cur: int | None = None
        self.rows: list[str] = []
        self.sel: set[str] = set()
        self.anchor: str | None = None
        self.left_root = self.right_root = ""
        self.editor = None
        self.undo = UndoStack()
        self._tip = None
        self._tip_job = None
        self._tip_for = None
        self.loading = False
        self.themed: list = []  # (widget, {option: token})

        self.left_path = tk.StringVar(value=(self.cfg.get("hist_left") or [""])[0])
        self.right_path = tk.StringVar(value=(self.cfg.get("hist_right") or [""])[0])
        self.mode = tk.StringVar(value=PAIR_MODES.get(self.cfg.get("mode", "filename"), PAIR_MODES["filename"]))
        self.recursive = tk.BooleanVar(value=self.cfg.get("recursive", False))
        self.filter = self.cfg.get("filter", "all")
        self.show_trivial = self.cfg.get("show_trivial", True)
        self.empty_set = self.cfg.get("empty_set", "off")
        self.show_covers = self.cfg.get("show_covers", True)
        self.q_text = tk.StringVar()      # Schnellsuche Paarliste
        self.f_field = tk.StringVar(value="— kein Filter —")
        self.f_op = tk.StringVar(value="enthält")
        self.f_val = tk.StringVar()
        self.f_side = tk.StringVar(value="links oder rechts")
        self.q_fields = tk.StringVar()    # Feldsuche in der Vergleichstabelle
        self._field_choices = {}
        self._thumb_cache = {}
        self._thumb_jobs = queue.Queue()
        self._thumb_done = queue.Queue()
        self._thumb_pending = set()
        threading.Thread(target=self._thumb_worker, daemon=True).start()

        self._build()
        self.apply_theme()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._bind_keys()
        self._undo_buttons()
        if not self.show_covers:
            for strip in self.cover_strips.values():
                strip.pack_forget()
        self._fill_tree()
        self.render()

    # ------------------------------------------------------------------ Config / Fonts
    def _load_cfg(self):
        return core.load_config()

    def _save_cfg(self):
        def hist(var, name):
            h = [var.get()] + [x for x in self.cfg.get(name, []) if x != var.get()]
            return [x for x in h if x][:12]
        self.cfg.update(
            theme="dark" if self.th is THEMES["dark"] else "light",
            geometry=self.geometry(), hist_left=hist(self.left_path, "hist_left"),
            hist_right=hist(self.right_path, "hist_right"), mode=self._mode_key(),
            recursive=self.recursive.get(), filter=self.filter, show_trivial=self.show_trivial,
            empty_set=self.empty_set, show_covers=self.show_covers,
            trivial=self.rules.trivial)
        core.save_config(self.cfg)

    def _fonts(self):
        base = tkfont.nametofont("TkDefaultFont")
        fam = base.actual("family")
        if IS_WIN:
            fam, size, gfam = "Segoe UI", 10, "Segoe UI Symbol"
        elif IS_MAC:
            size, gfam = 13, fam
        else:
            size, gfam = 10, fam
        base.configure(family=fam, size=size)
        for n in ("TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(n).configure(family=fam, size=size)
            except tk.TclError:
                pass
        self.f_ui = tkfont.Font(family=fam, size=size)
        self.f_bold = tkfont.Font(family=fam, size=size, weight="bold")
        self.f_small = tkfont.Font(family=fam, size=size - 2 if not IS_MAC else size - 2)
        self.f_glyph = tkfont.Font(family=gfam, size=size + 5)
        self.f_title = tkfont.Font(family=fam, size=size + 1, weight="bold")
        self.f_italic = tkfont.Font(family=fam, size=size, slant="italic")
        mono = "Consolas" if IS_WIN else ("Menlo" if IS_MAC else "DejaVu Sans Mono")
        self.f_mono = tkfont.Font(family=mono, size=size, weight="bold")

    # ------------------------------------------------------------------ Theme
    def T(self, widget, **opts):
        """Widget für Theme-Wechsel registrieren: opts = {option: token}."""
        self.themed.append((widget, opts))
        return widget

    def apply_theme(self):
        th = self.th
        s = self.style
        s.configure(".", background=th["bg"], foreground=th["fg"], fieldbackground=th["entry"],
                    bordercolor=th["border"], lightcolor=th["bg"], darkcolor=th["bg"],
                    troughcolor=th["bg"], focuscolor=th["accent"], font=self.f_ui,
                    selectbackground=th["sel"], selectforeground=th["fg"], insertcolor=th["fg"])
        s.configure("TFrame", background=th["bg"])
        s.configure("Bar.TFrame", background=th["bar"])
        s.configure("Panel.TFrame", background=th["panel"])
        s.configure("Head.TFrame", background=th["head"])
        s.configure("TLabel", background=th["bg"], foreground=th["fg"])
        s.configure("Bar.TLabel", background=th["bar"], foreground=th["fg"])
        s.configure("Dim.TLabel", background=th["bg"], foreground=th["dim"], font=self.f_small)
        s.configure("Head.TLabel", background=th["head"], foreground=th["dim"], font=self.f_small)
        s.configure("HeadB.TLabel", background=th["head"], foreground=th["fg"], font=self.f_bold)
        s.configure("TButton", background=th["head"], foreground=th["fg"], bordercolor=th["border"],
                    lightcolor=th["head"], darkcolor=th["head"], padding=(10, 4), relief="flat")
        s.map("TButton", background=[("pressed", th["press"]), ("active", th["hover"]), ("disabled", th["bg"])],
              foreground=[("disabled", th["dim"])])
        s.configure("TCheckbutton", background=th["bg"], foreground=th["fg"], indicatorbackground=th["entry"],
                    indicatorforeground=th["fg"], indicatorcolor=th["entry"])
        s.map("TCheckbutton", background=[("active", th["bg"])], indicatorcolor=[("selected", th["accent"])])
        s.configure("Bar.TCheckbutton", background=th["bar"])
        s.map("Bar.TCheckbutton", background=[("active", th["bar"])])
        s.configure("TCombobox", fieldbackground=th["entry"], background=th["head"], foreground=th["fg"],
                    arrowcolor=th["fg"], bordercolor=th["border"], lightcolor=th["entry"], darkcolor=th["entry"],
                    padding=4)
        s.map("TCombobox", fieldbackground=[("readonly", th["entry"])], foreground=[("readonly", th["fg"])],
              selectbackground=[("readonly", th["entry"])], selectforeground=[("readonly", th["fg"])])
        s.configure("TEntry", fieldbackground=th["entry"], foreground=th["fg"], bordercolor=th["border"],
                    lightcolor=th["entry"], darkcolor=th["entry"], padding=4)
        s.configure("Treeview", background=th["panel"], fieldbackground=th["panel"], foreground=th["fg"],
                    bordercolor=th["border"], lightcolor=th["panel"], darkcolor=th["panel"],
                    rowheight=self.f_ui.metrics("linespace") + 8)
        s.map("Treeview", background=[("selected", th["sel"])], foreground=[("selected", th["fg"])])
        s.configure("Treeview.Heading", background=th["head"], foreground=th["dim"], relief="flat",
                    bordercolor=th["border"], lightcolor=th["head"], darkcolor=th["head"], font=self.f_small,
                    padding=(6, 4))
        s.map("Treeview.Heading", background=[("active", th["hover"])])
        for o in ("Vertical", "Horizontal"):
            s.configure(f"{o}.TScrollbar", background=th["head"], troughcolor=th["panel"], bordercolor=th["panel"],
                        arrowcolor=th["dim"], lightcolor=th["head"], darkcolor=th["head"], gripcount=0)
            s.map(f"{o}.TScrollbar", background=[("active", th["hover"])])
        s.configure("Horizontal.TProgressbar", background=th["accent"], troughcolor=th["panel"],
                    bordercolor=th["border"], lightcolor=th["accent"], darkcolor=th["accent"], thickness=14)
        s.configure("TPanedwindow", background=th["bg"])
        s.configure("Sash", sashthickness=6, background=th["bg"], gripcount=0)
        s.configure("TLabelframe", background=th["bg"], bordercolor=th["border"])
        s.configure("TLabelframe.Label", background=th["bg"], foreground=th["dim"])
        s.configure("TRadiobutton", background=th["bg"], foreground=th["fg"], indicatorcolor=th["entry"])
        s.map("TRadiobutton", indicatorcolor=[("selected", th["accent"])], background=[("active", th["bg"])])
        self.option_add("*TCombobox*Listbox.background", th["entry"])
        self.option_add("*TCombobox*Listbox.foreground", th["fg"])
        self.option_add("*TCombobox*Listbox.selectBackground", th["sel"])
        self.option_add("*TCombobox*Listbox.selectForeground", th["fg"])
        self.option_add("*Menu.background", th["head"])
        self.option_add("*Menu.foreground", th["fg"])
        self.option_add("*Menu.activeBackground", th["sel"])
        self.option_add("*Menu.activeForeground", th["fg"])
        self.configure(bg=th["bg"])
        for w, opts in self.themed:
            try:
                w.configure(**{o: th[t] for o, t in opts.items()})
            except tk.TclError:
                pass
        for b in self.toolbuttons:
            b._paint()
        for pool in getattr(self, "_line_pool", {}).values():
            for fr in pool:
                fr.configure(bg=th["grid"])
        for fr in getattr(self, "_col_lines", {}).values():
            fr.configure(bg=th["grid"])
        for t in self._texts():
            t.configure(bg=th["panel"], fg=th["fg"], selectbackground=th["panel"], inactiveselectbackground=th["panel"])
            t.tag_configure("mid", justify="center")
            t.tag_configure("toL", foreground=th["g_copy"], font=self.f_bold)
            t.tag_configure("toR", foreground=th["g_copy"], font=self.f_bold)
            t.tag_configure("hot", foreground=th["fg"], background=th["hover"])
            t.tag_configure("same", background=th["panel"])
            t.tag_configure("diff", background=th["diff_bg"])
            t.tag_configure("triv", background=th["triv_bg"])
            t.tag_configure("only", background=th["only_bg"])
            t.tag_configure("miss", background=th["miss_bg"])
            t.tag_configure("name", foreground=th["dim"])
            t.tag_configure("chg", foreground=th["chg"])
            t.tag_configure("tchg", foreground=th["triv_chg"])
            t.tag_configure("mod", foreground=th["mod"])
            t.tag_configure("hint", foreground=th["dim"], justify="center")
            t.tag_configure("link", foreground=th["g_cmp"], underline=True)
            t.tag_configure("empty", background=th["panel"])
            t.tag_configure("ename", foreground=th["dim"], font=self.f_italic)
            t.tag_configure("rowsel", background=th["sel"])
            t.tag_raise("rowsel")
        self.tree.tag_configure("diff", foreground=th["chg"])
        self.tree.tag_configure("triv", foreground=th["triv_chg"])
        self.tree.tag_configure("same", foreground=th["ok"])
        self.tree.tag_configure("single", foreground=th["dim"])
        self.ctx.configure(bg=th["head"], fg=th["fg"], activebackground=th["sel"], activeforeground=th["fg"])
        self._refresh_info()

    def toggle_theme(self):
        self.th = THEMES["light"] if self.th is THEMES["dark"] else THEMES["dark"]
        self.apply_theme()
        self.render()

    # ------------------------------------------------------------------ Aufbau
    def _build(self):
        self.toolbuttons = []
        # ---------- Toolbar
        bar = self.T(tk.Frame(self, bd=0), bg="bar")
        bar.pack(fill="x")

        def tb(glyph, text, cmd, color="g_misc", tip="", toggle=False):
            b = ToolButton(bar, self, glyph, text, cmd, color, toggle, tip)
            b.pack(side="left", padx=0, pady=2)
            self.toolbuttons.append(b)
            return b

        def sep():
            f = self.T(tk.Frame(bar, width=1), bg="border")
            f.pack(side="left", fill="y", padx=4, pady=8)

        tb("⇄", "Vergleichen", self.compare, "g_cmp", "Ordner/Dateien laden und vergleichen (F5)")
        sep()
        self.fb = {
            "all": tb("✱", "Alle", lambda: self.set_filter("all"), "g_misc", "Alle Felder anzeigen"),
            "diff": tb("≠", "Unterschiede", lambda: self.set_filter("diff"), "g_warn", "Nur unterschiedliche Felder"),
            "same": tb("=", "Gleiche", lambda: self.set_filter("same"), "g_save", "Nur gleiche Felder"),
        }
        self.b_triv = tb("≈", "Unwichtige", self.toggle_trivial, "g_copy",
                         "Unwichtige Unterschiede (Länge, Encoder, Fingerprints …) anzeigen")
        self.b_cover = tb("▣", "Cover", self.toggle_covers, "g_misc", "Cover-Vorschau ein-/ausblenden")
        self.b_empty = tb("☐", "Leere Felder", self.empty_menu, "g_misc",
                          "Alle in ID3v1 / v2.3 / v2.4 vorgesehenen Felder einblenden – auch unbeschriebene")
        sep()
        self.b_r = tb("→", "Auswahl →", lambda: self.copy_sel("lr"), "g_copy",
                      f"Markierte Felder nach rechts kopieren ({MOD_TXT}+→)")
        self.b_l = tb("←", "← Auswahl", lambda: self.copy_sel("rl"), "g_copy",
                      f"Markierte Felder nach links kopieren ({MOD_TXT}+←)")
        self.b_ar = tb("⇉", "Alles →", lambda: self.copy_all("lr"), "g_copy", "Alle unterschiedlichen Felder nach rechts")
        self.b_al = tb("⇇", "← Alles", lambda: self.copy_all("rl"), "g_copy", "Alle unterschiedlichen Felder nach links")
        self.b_mr = tb("⇥", "Fehlende →", lambda: self.copy_missing("lr"), "g_copy",
                       "Nur Felder übernehmen, die rechts fehlen")
        self.b_ml = tb("⇤", "← Fehlende", lambda: self.copy_missing("rl"), "g_copy",
                       "Nur Felder übernehmen, die links fehlen")
        sep()
        tb("+", "Feld", self.add_field_dialog, "g_misc", "Neues Feld hinzufügen")
        tb("¦", "Mehrfachwerte", self.multi_fix_dialog, "g_cmp",
           "Tag-Fixer: Mehrfachwerte (z. B. mehrere Künstler) einheitlich trennen")
        tb("⇆", "Tauschen", self.swap_sides, "g_misc", "Seiten tauschen")
        tb("⟳", "Neu laden", self.reload, "g_misc", "Dateien neu einlesen")
        tb("⊘", "Verwerfen", self.revert_pair, "g_misc", "Alle Änderungen dieses Paars verwerfen")
        sep()
        self.b_undo = tb("↶", "Rückgängig", self.do_undo, "g_cmp", f"Letzte Änderung rückgängig ({MOD_TXT}+Z)")
        self.b_redo = tb("↷", "Wiederholen", self.do_redo, "g_cmp",
                         f"Rückgängig gemachte Änderung wiederholen ({MOD_TXT}+Y / {MOD_TXT}+Shift+Z)")
        sep()
        self.b_save = tb("✔", "Speichern", self.save_all, "g_save",
                         f"Alle Änderungen speichern ({MOD_TXT}+S) – die bisherigen Tags werden vorher gesichert")
        tb("⟲", "Sicherungen", self.backup_dialog, "g_misc", "Gesicherte Tags ansehen und wiederherstellen")
        ToolButton(bar, self, "◐", "Design", self.toggle_theme, "g_misc", tip="Hell / Dunkel").pack(side="right", padx=4)
        self.toolbuttons.append(bar.winfo_children()[-1])
        self.T(tk.Frame(self, height=1), bg="border").pack(fill="x")

        # ---------- Pfade
        paths = ttk.Frame(self, padding=(8, 8, 8, 2))
        paths.pack(fill="x")
        self.info_l = ttk.Label(paths, style="Dim.TLabel")
        self.info_r = ttk.Label(paths, style="Dim.TLabel")
        for col, (var, side, info, hist) in enumerate(((self.left_path, "L", self.info_l, "hist_left"),
                                                        (self.right_path, "R", self.info_r, "hist_right"))):
            fr = ttk.Frame(paths)
            fr.grid(row=0, column=col, sticky="ew", padx=(0, 10) if col == 0 else (10, 0))
            cb = ttk.Combobox(fr, textvariable=var, values=self.cfg.get(hist, []), font=self.f_ui)
            cb.pack(side="left", fill="x", expand=True)
            cb.bind("<Return>", lambda e: self.compare())
            ttk.Button(fr, text="Ordner…", command=lambda s=side: self.pick(s, True)).pack(side="left", padx=(6, 0))
            ttk.Button(fr, text="Datei…", command=lambda s=side: self.pick(s, False)).pack(side="left", padx=(4, 0))
            info.grid(row=1, column=col, sticky="w", padx=(4 if col == 0 else 14, 0), pady=(4, 0))
        paths.columnconfigure(0, weight=1, uniform="p")
        paths.columnconfigure(1, weight=1, uniform="p")

        opts = ttk.Frame(self, padding=(8, 2, 8, 6))
        opts.pack(fill="x")
        ttk.Label(opts, text="Zuordnung", style="Dim.TLabel").pack(side="left")
        ttk.Combobox(opts, textvariable=self.mode, values=list(PAIR_MODES.values()), state="readonly",
                     width=24, font=self.f_ui).pack(side="left", padx=(6, 14))
        ttk.Checkbutton(opts, text="Unterordner einbeziehen", variable=self.recursive).pack(side="left")
        fs = ttk.Entry(opts, textvariable=self.q_fields, width=26, font=self.f_ui)
        fs.pack(side="right")
        ttk.Label(opts, text="Felder suchen", style="Dim.TLabel").pack(side="right", padx=(0, 6))
        fs.bind("<Escape>", lambda e: self.q_fields.set(""))
        self.q_fields.trace_add("write", lambda *a: self._debounce("fields", self.render, 200))

        # ---------- Paned: Paarliste / Vergleich
        self.paned = ttk.PanedWindow(self, orient="vertical")
        self.paned.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        self.pairframe = ttk.Frame(self.paned)
        ph = ttk.Frame(self.pairframe, style="Head.TFrame", padding=(8, 4))
        ph.pack(fill="x")
        ttk.Label(ph, text="Dateipaare", style="HeadB.TLabel").pack(side="left")
        self.pair_count = ttk.Label(ph, style="Head.TLabel")
        self.pair_count.pack(side="left", padx=10)
        ttk.Button(ph, text="Markierte  ← …", command=lambda: self.bulk_dialog("rl")).pack(side="right", padx=2)
        ttk.Button(ph, text="Markierte  … →", command=lambda: self.bulk_dialog("lr")).pack(side="right", padx=2)
        ttk.Button(ph, text="Alle markieren", command=lambda: self.tree.selection_set(self.tree.get_children())).pack(side="right", padx=8)
        pf = ttk.Frame(self.pairframe, padding=(8, 5, 8, 3))
        pf.pack(fill="x")
        ttk.Label(pf, text="Suchen", style="Dim.TLabel").pack(side="left")
        qe = ttk.Entry(pf, textvariable=self.q_text, width=24, font=self.f_ui)
        qe.pack(side="left", padx=(6, 16))
        Tooltip(qe, "Sucht in Dateinamen und allen Tag-Werten (links und rechts)", self)
        ttk.Label(pf, text="Filter", style="Dim.TLabel").pack(side="left")
        self.f_field_cb = ttk.Combobox(pf, textvariable=self.f_field, state="readonly", width=30, font=self.f_ui,
                                       values=["— kein Filter —"])
        self.f_field_cb.pack(side="left", padx=(6, 4))
        ttk.Combobox(pf, textvariable=self.f_op, state="readonly", width=13, font=self.f_ui,
                     values=FILTER_OPS).pack(side="left", padx=4)
        self.f_val_e = ttk.Entry(pf, textvariable=self.f_val, width=18, font=self.f_ui)
        self.f_val_e.pack(side="left", padx=4)
        ttk.Combobox(pf, textvariable=self.f_side, state="readonly", width=16, font=self.f_ui,
                     values=["links oder rechts", "links", "rechts", "beide Seiten"]).pack(side="left", padx=4)
        ttk.Button(pf, text="✕ Zurücksetzen", command=self.reset_filter).pack(side="left", padx=8)
        for v in (self.q_text, self.f_field, self.f_op, self.f_val, self.f_side):
            v.trace_add("write", lambda *a: self._debounce("pairs", self._fill_tree, 250))
        tf = ttk.Frame(self.pairframe)
        tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, columns=("st", "left", "right", "info"), show="headings", selectmode="extended")
        for c, t, w, stretch in (("st", "", 44, False), ("left", "Links", 420, True),
                                 ("right", "Rechts", 420, True), ("info", "Unterschiede", 260, False)):
            self.tree.heading(c, text=t, anchor="w")
            self.tree.column(c, width=w, stretch=stretch, anchor="center" if c == "st" else "w")
        ys = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ys.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_pair_select)
        self.paned.add(self.pairframe, weight=1)

        # ---------- Vergleichsansicht: [links | Befehle | rechts] mit Splittern
        cmpf = ttk.Frame(self.paned)
        body = ttk.Frame(cmpf)
        body.pack(fill="both", expand=True)
        self.hpane = self.T(tk.PanedWindow(body, orient="horizontal", sashwidth=5, sashrelief="flat", bd=0,
                                           opaqueresize=True, showhandle=False, sashcursor="sb_h_double_arrow"),
                            bg="border")
        self.hpane.grid(row=0, column=0, sticky="nsew")
        self.vsb = ttk.Scrollbar(body, orient="vertical", command=self._yview)
        self.vsb.grid(row=0, column=1, sticky="ns")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        hdr_h = self.f_bold.metrics("linespace") + self.f_small.metrics("linespace") + 14
        self.thumb_px = int(92 * self.dpi)
        self.cover_h = self.thumb_px + self.f_small.metrics("linespace") + 14
        self.cover_strips, self.cover_before = {}, {}
        self.col_handles = []
        self.wert_labels = []

        def side_pane(side):
            pane = ttk.Frame(self.hpane)
            h = ttk.Frame(pane, style="Head.TFrame", height=hdr_h)
            h.pack(fill="x")
            h.pack_propagate(False)
            title = ttk.Label(h, style="HeadB.TLabel")
            title.place(x=8, y=4)
            y2 = 6 + self.f_bold.metrics("linespace")
            ttk.Label(h, text="Name", style="Head.TLabel").place(x=8, y=y2)
            wl = ttk.Label(h, text="Wert", style="Head.TLabel")
            wl.place(x=self.name_w - 4, y=y2)
            self.wert_labels.append(wl)
            # Spaltensplitter Name | Wert in der Kopfzeile
            hd = self.T(tk.Frame(h, width=5, cursor="sb_h_double_arrow"), bg="border")
            hd.place(x=self.name_w - 12, y=y2, height=self.f_small.metrics("linespace"))
            hd.bind("<B1-Motion>", lambda e, w=hd: self._col_drag(e.x_root - w.master.winfo_rootx()))
            hd.bind("<ButtonRelease-1>", lambda e: self._col_drag_end())
            hd.bind("<Double-Button-1>", lambda e: self._col_auto())
            Tooltip(hd, "Spaltenbreite ziehen · Doppelklick = optimal", self)
            self.col_handles.append(hd)
            strip = self.T(tk.Frame(pane, height=self.cover_h, bd=0, highlightthickness=0), bg="panel")
            strip.pack(fill="x")
            strip.pack_propagate(False)
            self.cover_strips[side] = strip
            tf = ttk.Frame(pane)
            tf.pack(fill="both", expand=True)
            self.cover_before[side] = tf
            t = self._make_text(tf)
            hsb = ttk.Scrollbar(tf, orient="horizontal", command=t.xview)
            t.configure(xscrollcommand=hsb.set, yscrollcommand=self._yset)
            t.grid(row=0, column=0, sticky="nsew")
            hsb.grid(row=1, column=0, sticky="ew")
            tf.rowconfigure(0, weight=1)
            tf.columnconfigure(0, weight=1)
            return pane, title, t

        lp, self.title_l, self.text_l = side_pane("L")

        # Befehlsspalte
        self.mid_w = 104
        mp = ttk.Frame(self.hpane)
        mh = ttk.Frame(mp, style="Head.TFrame", height=hdr_h)
        mh.pack(fill="x")
        mh.grid_propagate(False)
        self.mid_btns = []
        for (r, c, glyph, cmd, tip) in (
                (0, 0, "⇇ Alle", lambda: self.copy_all("rl"), "Alles nach links übernehmen"),
                (0, 1, "Alle ⇉", lambda: self.copy_all("lr"), "Alles nach rechts übernehmen"),
                (1, 0, "◁ Fehl.", lambda: self.copy_missing("rl"), "Alle fehlenden Felder nach links übernehmen"),
                (1, 1, "Fehl. ▷", lambda: self.copy_missing("lr"), "Alle fehlenden Felder nach rechts übernehmen")):
            b = self.T(tk.Label(mh, text=glyph, font=self.f_small, cursor="hand2", padx=2, pady=1),
                       bg="head", fg="g_copy")
            b.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
            b.bind("<ButtonRelease-1>", lambda e, f=cmd: f())
            b.bind("<Enter>", lambda e, w=b: w.configure(bg=self.th["hover"]))
            b.bind("<Leave>", lambda e, w=b: w.configure(bg=self.th["head"]))
            Tooltip(b, tip, self)
            self.mid_btns.append(b)
        mh.columnconfigure(0, weight=1)
        mh.columnconfigure(1, weight=1)
        mh.rowconfigure(0, weight=1)
        mh.rowconfigure(1, weight=1)
        mstrip = self.T(tk.Frame(mp, height=self.cover_h, bd=0, highlightthickness=0), bg="panel")
        mstrip.pack(fill="x")
        mstrip.pack_propagate(False)
        self.cover_mid = self.T(tk.Label(mstrip, text="", font=self.f_bold), bg="panel", fg="dim")
        self.cover_mid.place(relx=0.5, rely=0.5, anchor="center")
        self.cover_strips["M"] = mstrip
        mtf = ttk.Frame(mp)
        mtf.pack(fill="both", expand=True)
        self.cover_before["M"] = mtf
        self.text_m = tk.Text(mtf, wrap="none", bd=0, highlightthickness=0, padx=0, pady=4, cursor="arrow",
                              font=self.f_ui, spacing1=3, spacing3=3, insertwidth=0, width=1,
                              exportselection=False, takefocus=0)
        self.text_m.configure(yscrollcommand=self._yset)
        self.text_m.grid(row=0, column=0, sticky="nsew")
        # Platzhalter in Höhe der horizontalen Scrollbar, damit unten alles bündig ist
        ttk.Frame(mtf, height=self.hsb_height()).grid(row=1, column=0, sticky="ew")
        mtf.rowconfigure(0, weight=1)
        mtf.columnconfigure(0, weight=1)
        self.text_m.bind("<Button-1>", self.on_mid_click)
        self.text_m.bind("<Motion>", self.on_mid_motion)
        self.text_m.bind("<B1-Motion>", lambda e: "break")
        if sys.platform.startswith("linux"):
            self.text_m.bind("<Button-4>", lambda e: self._wheel(-3))
            self.text_m.bind("<Button-5>", lambda e: self._wheel(3))
        else:
            self.text_m.bind("<MouseWheel>", lambda e: self._wheel(-e.delta if IS_MAC else -e.delta // 120 * 3))
        self.text_m.bind("<Configure>", lambda e: self._lines_later(), add="+")

        rp, self.title_r, self.text_r = side_pane("R")
        self.hpane.add(lp, stretch="always", minsize=220)
        self.hpane.add(mp, stretch="never", minsize=self.mid_w, width=self.mid_w)
        self.hpane.add(rp, stretch="always", minsize=220)
        self.layout_auto = True
        self.hpane.bind("<ButtonPress-1>", self._sash_press, add="+")
        self.hpane.bind("<ButtonRelease-1>", self._sash_release, add="+")
        self.hpane.bind("<Double-Button-1>", lambda e: self._auto_layout(force=True))
        self.hpane.bind("<Configure>", lambda e: self.after_idle(self._auto_layout), add="+")
        self.paned.add(cmpf, weight=4)
        self.pair_visible = True

        # ---------- Statusleiste
        self.T(tk.Frame(self, height=1), bg="border").pack(fill="x")
        sb = self.T(tk.Frame(self), bg="bar")
        sb.pack(fill="x")
        self.st_glyph = self.T(tk.Label(sb, font=self.f_ui, padx=8), bg="bar")
        self.st_glyph.pack(side="left")
        self.st_text = self.T(tk.Label(sb, font=self.f_small, anchor="w"), bg="bar", fg="fg")
        self.st_text.pack(side="left", pady=4)
        self.st_mod = self.T(tk.Label(sb, font=self.f_small, padx=10), bg="bar", fg="mod")
        self.st_mod.pack(side="right")
        self.legend = []
        for txt, tok in (("unwichtig", "triv_bg"), ("nur eine Seite", "only_bg"), ("unterschiedlich", "diff_bg")):
            lb = self.T(tk.Label(sb, text=f"  {txt}  ", font=self.f_small), bg=tok, fg="fg")
            lb.pack(side="right", padx=3, pady=4)

        # ---------- Kontextmenü
        self.ctx = tk.Menu(self, tearoff=0)

    def _make_text(self, master):
        t = tk.Text(master, wrap="none", bd=0, highlightthickness=0, padx=0, pady=4, cursor="arrow",
                    font=self.f_ui, spacing1=3, spacing3=3, tabs=(self.name_w,), insertwidth=0,
                    exportselection=False, takefocus=1, undo=False)
        t.bind("<Button-1>", lambda e, w=t: self.on_click(e, w))
        t.bind("<Double-Button-1>", lambda e, w=t: self.on_double(e, w))
        for seq in (("<Button-2>", "<Control-Button-1>") if IS_MAC else ("<Button-3>",)):
            t.bind(seq, lambda e, w=t: self.on_context(e, w))
        if sys.platform.startswith("linux"):
            t.bind("<Button-4>", lambda e: self._wheel(-3))
            t.bind("<Button-5>", lambda e: self._wheel(3))
        else:
            t.bind("<MouseWheel>", lambda e: self._wheel(-e.delta if IS_MAC else -e.delta // 120 * 3))
        t.bind("<B1-Motion>", lambda e, w=t: self._text_drag(e, w))
        t.bind("<ButtonRelease-1>", lambda e: self._col_drag_end(), add="+")
        t.bind("<Key>", self._text_key)
        t.bind("<Motion>", lambda e, w=t: self._name_hover(e, w), add="+")
        t.bind("<Configure>", lambda e: self._lines_later(), add="+")
        t.bind("<Leave>", lambda e: self._name_tip_hide(), add="+")
        return t

    # ------------------------------------------------------------------ Tooltip Frame-ID
    def _name_hover(self, e, w):
        """Beim Überfahren der Namensspalte die originale ID3-Frame-ID anzeigen."""
        near = abs(e.x - (self.name_w - 10)) <= 4
        link = None if near else self._link_at(w, e)
        w.configure(cursor="sb_h_double_arrow" if near else ("hand2" if link else "arrow"))
        if link and getattr(self, "_link_shown", None) != link:
            self._link_shown = link
            self._status("↗", f"Klick öffnet: {link}", "g_cmp")
        elif not link and getattr(self, "_link_shown", None):
            self._link_shown = None
            self._update_status()
        k = self._row_at(w, e) if e.x < self.name_w - 14 else None
        side = "L" if w is self.text_l else "R"
        cur = (side, k) if k else None
        if cur == getattr(self, "_tip_for", None):
            if self._tip and self._tip.winfo_exists():
                self._tip.wm_geometry(f"+{e.x_root + 14}+{e.y_root + 18}")
            return
        self._name_tip_hide()
        self._tip_for = cur
        if cur:
            pos = (e.x_root, e.y_root)
            self._tip_job = self.after(350, lambda: self._name_tip_show(side, k, pos))

    def _name_tip_text(self, side, key):
        f = self._file(side)
        it = f.get(key) if f else None
        if it is None:
            fid = key.split(":")[0].split("#")[0]
            return [("Frame", fid), ("", "auf dieser Seite nicht vorhanden")]
        lines = [("Frame", " + ".join(it.frame_ids(f.version)))]
        lines += it.details()
        if it.kind in ("text", "txxx") and MV in it.text:
            n = len([v for v in it.values if v.strip()])
            how = "null-getrennt (Standard)" if f.version == 4 else f"wird als '{V23_JOIN.strip()}' gespeichert (v2.3)"
            lines.append(("Mehrfachwert", f"{n} Werte, {how}"))
        lines.append(("Version", f"ID3v2.{f.version}" if f.had_v2 else f"{f.tag_desc} → wird als ID3v2.{f.version} gespeichert"))
        if f.field_modified(key):
            lines.append(("", "geändert, noch nicht gespeichert"))
        return lines

    def _name_tip_show(self, side, key, pos):
        self._tip_job = None
        if getattr(self, "_tip_for", None) != (side, key):
            return
        th = self.th
        tip = self._tip = tk.Toplevel(self)
        tip.wm_overrideredirect(True)
        try:
            tip.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        fr = tk.Frame(tip, bg=th["head"], highlightthickness=1, highlightbackground=th["border"], padx=10, pady=6)
        fr.pack()
        tk.Label(fr, text=key_label(key), bg=th["head"], fg=th["fg"], font=self.f_bold, anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        for r, (k, v) in enumerate(self._name_tip_text(side, key), start=1):
            if k:
                tk.Label(fr, text=k, bg=th["head"], fg=th["dim"], font=self.f_small, anchor="w").grid(
                    row=r, column=0, sticky="w", padx=(0, 10))
            font = self.f_mono if k == "Frame" else self.f_small
            fg = th["g_copy"] if k == "Frame" else (th["mod"] if not k else th["fg"])
            tk.Label(fr, text=v, bg=th["head"], fg=fg, font=font, anchor="w").grid(
                row=r, column=1 if k else 0, columnspan=1 if k else 2, sticky="w")
        tip.wm_geometry(f"+{pos[0] + 14}+{pos[1] + 18}")

    def _name_tip_hide(self):
        if getattr(self, "_tip_job", None):
            self.after_cancel(self._tip_job)
            self._tip_job = None
        if getattr(self, "_tip", None) is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None
        self._tip_for = None

    # ------------------------------------------------------------------ Scroll-Sync
    def _texts(self):
        return (self.text_l, self.text_m, self.text_r)

    def _yview(self, *a):
        for t in self._texts():
            t.yview(*a)

    def _yset(self, first, last):
        self.vsb.set(first, last)
        self._lines_later()
        for t in self._texts():
            if abs(t.yview()[0] - float(first)) > 1e-6:
                t.yview_moveto(first)

    def _wheel(self, units):
        self._name_tip_hide()
        for t in self._texts():
            t.yview_scroll(units, "units")
        return "break"

    def _bind_keys(self):
        for seq in (f"<{MOD}-z>", f"<{MOD}-Z>"):
            self.bind_all(seq, lambda e: self._undo_key(e, redo=bool(e.state & 0x1)))
        self.bind_all(f"<{MOD}-y>", lambda e: self._undo_key(e, redo=True))
        self.bind_all(f"<{MOD}-s>", lambda e: self.save_all())
        self.bind_all(f"<{MOD}-Right>", lambda e: self.copy_sel("lr"))
        self.bind_all(f"<{MOD}-Left>", lambda e: self.copy_sel("rl"))
        self.bind_all("<F5>", lambda e: self.compare())
        self.bind_all(f"<{MOD}-a>", self._select_all_rows)

    def _text_key(self, e):
        if e.keysym in ("Up", "Down") and self.rows:
            i = self.rows.index(self.anchor) if self.anchor in self.rows else -1
            i = max(0, min(len(self.rows) - 1, i + (1 if e.keysym == "Down" else -1)))
            self.sel, self.anchor = {self.rows[i]}, self.rows[i]
            self._paint_sel()
            self.text_l.see(f"{self._ln(i)}.0")
            self.text_r.see(f"{self._ln(i)}.0")
        elif e.keysym == "Return" and self.anchor:
            self.edit_field("L" if e.widget is self.text_l else "R", self.anchor)
        if e.state & 0x4 or (IS_MAC and e.state & 0x8):
            return None
        return "break"

    def _select_all_rows(self, e):
        if e.widget in (self.text_l, self.text_r):
            self.sel = set(self.rows)
            self._paint_sel()
            return "break"
        return None

    # ================================================================== Laden
    def pick(self, side, folder):
        var = self.left_path if side == "L" else self.right_path
        cur = var.get()
        start = cur if os.path.isdir(cur) else (os.path.dirname(cur) if cur else os.path.expanduser("~"))
        if folder:
            p = filedialog.askdirectory(initialdir=start, title="Ordner wählen")
        else:
            p = filedialog.askopenfilename(initialdir=start, title="MP3-Datei wählen",
                                           filetypes=[("MP3-Dateien", "*.mp3 *.MP3"), ("Alle Dateien", "*")])
        if p:
            var.set(os.path.normpath(p))
            other = self.right_path if side == "L" else self.left_path
            if other.get().strip():
                self.compare()

    def _mode_key(self):
        return next((k for k, v in PAIR_MODES.items() if v == self.mode.get()), "filename")

    def compare(self, ask=True, keep=None):
        if self.loading:
            return
        if ask and not self._confirm_discard():
            return
        lp, rp = self.left_path.get().strip(), self.right_path.get().strip()
        err = core.check_paths(lp, rp)
        if err:
            (messagebox.showinfo if not lp and not rp else messagebox.showwarning)(APP, err)
            return
        self._start_loading(lp, rp, keep)

    # ------------------------------------------------------------------ Einlesen im Hintergrund
    def _start_loading(self, lp, rp, keep):
        """Phase 1: Dateien zählen, Phase 2: Tags lesen – in einem Hintergrund-Thread mit Fortschrittsdialog."""
        self.loading = True
        cancel = threading.Event()
        q: queue.Queue = queue.Queue()
        recursive, mode = self.recursive.get(), self._mode_key()

        def worker():
            try:
                pairs, errors = core.load_pairs(lp, rp, recursive, mode, cancel, q.put)
                q.put(("done", pairs, errors))
            except Cancelled:
                q.put(("cancelled",))
            except Exception as ex:  # noqa: BLE001
                q.put(("error", str(ex)))

        dlg = ProgressDialog(self, cancel)
        threading.Thread(target=worker, daemon=True).start()

        def poll():
            msg = None
            try:
                while True:
                    m = q.get_nowait()
                    if m[0] in ("done", "cancelled", "error"):
                        msg = m
                        break
                    dlg.update_state(m)
            except queue.Empty:
                pass
            if msg is None:
                self.after(60, poll)
                return
            dlg.close()
            self.loading = False
            if msg[0] == "done":
                self._finish_loading(lp, rp, msg[1], msg[2], keep)
            elif msg[0] == "cancelled":
                self._status("✕", "Einlesen abgebrochen – bisherige Ansicht bleibt erhalten.", "g_warn")
            else:
                self._status("⚠", "Fehler beim Einlesen.", "g_warn")
                messagebox.showerror(APP, f"Fehler beim Einlesen:\n\n{msg[1]}")
        self.after(60, poll)

    def _finish_loading(self, lp, rp, pairs, errors, keep):
        self.undo.clear()
        self._update_field_choices(pairs)
        self._undo_buttons()
        self.left_root, self.right_root = lp, rp
        self.pairs = pairs
        self._save_cfg()
        self.cur = None
        self._fill_tree()
        kids = self.tree.get_children()
        if kids:
            target = str(keep) if keep is not None and self.tree.exists(str(keep)) else kids[0]
            self.tree.selection_set(target)
            self.tree.see(target)
            self.on_pair_select()
        else:
            self.render()
        self._update_status()
        if not pairs:
            self._status("ℹ", "Keine MP3-Dateien gefunden.", "dim")
        if errors:
            messagebox.showwarning(APP, f"{len(errors)} Datei(en) nicht lesbar:\n\n" + "\n".join(errors[:30])
                                   + ("\n…" if len(errors) > 30 else ""))

    def reload(self):
        keep = self.cur
        self.compare(keep=keep)

    def swap_sides(self):
        if not self._confirm_discard():
            return
        l, r = self.left_path.get(), self.right_path.get()
        self.left_path.set(r)
        self.right_path.set(l)
        if self.pairs:
            self.compare(ask=False, keep=self.cur)

    # ================================================================== Paarliste
    def _rel(self, f, root):
        return core.rel_name(f, root)

    def _pair_row(self, i):
        l, r = self.pairs[i]
        st = core.pair_status(l, r, self.rules)
        mod = "●" if st["modified"] else ""
        return (mod + st["symbol"], self._rel(l, self.left_root) or "—", self._rel(r, self.right_root) or "—",
                st["info"]), st["tag"]

    def _fill_tree(self):
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        flt = self._make_pair_filter()
        shown = 0
        for i in range(len(self.pairs)):
            if flt and not flt(self.pairs[i]):
                continue
            shown += 1
            vals, tag = self._pair_row(i)
            self.tree.insert("", "end", iid=str(i), values=vals, tags=(tag,))
        keep = [s for s in sel if self.tree.exists(s)]
        if keep:
            self.tree.selection_set(keep)
        n = len(self.pairs)
        if flt:
            self.pair_count.configure(text=f"{fmt_n(shown)} von {fmt_n(n)} Paaren (gefiltert)")
        else:
            self.pair_count.configure(text=f"{fmt_n(n)} Paar{'e' if n != 1 else ''}")
        show = n > 1
        if show != self.pair_visible:
            if show:
                self.paned.insert(0, self.pairframe, weight=1)
                self.after_idle(lambda: self.paned.sashpos(0, min(230, 60 + 26 * n)))
            else:
                self.paned.forget(self.pairframe)
            self.pair_visible = show

    def _refresh_pair(self, i):
        if i is not None and self.tree.exists(str(i)):
            vals, tag = self._pair_row(i)
            self.tree.item(str(i), values=vals, tags=(tag,))

    def on_pair_select(self, _e=None):
        sel = self.tree.selection()
        i = int(sel[0]) if sel else None
        if i != self.cur:
            self._close_editor(commit=True)
            self.cur = i
            self.sel, self.anchor = set(), None
            self.render()

    # ================================================================== Vergleichsansicht
    def _files(self):
        return self.pairs[self.cur] if self.cur is not None and self.cur < len(self.pairs) else (None, None)

    def _row_state(self, k, l, r):
        return core.row_state(k, l, r, self.rules)

    def render(self):
        self._name_tip_hide()
        l, r = self._files()
        th = self.th
        rows, states = core.visible_keys(l, r, self.rules, self.filter, self.show_trivial, self.empty_set,
                                         self.q_fields.get())
        self.rows = rows
        self.states = states
        self.sel &= set(rows)
        if self.name_auto and rows:
            self._set_name_w(self._optimal_name_w(), rerender=False)

        ypos = self.text_l.yview()[0]
        for t in (self.text_l, self.text_r):
            old = [tg for tg in t.tag_names() if tg.startswith("u_")]
            if old:
                t.tag_delete(*old)
        self._links = {}
        for side, t, f, other in (("L", self.text_l, l, r), ("R", self.text_r, r, l)):
            t.configure(state="normal")
            t.delete("1.0", "end")
            if f is None and other is None:
                t.insert("end", "\n\n\nLinks und rechts einen Ordner oder eine Datei wählen\nund auf »Vergleichen« klicken.", ("hint",))
            elif f is None:
                t.insert("end", "\n\n\n(keine Datei)", ("hint",))
            else:
                for i, k in enumerate(rows):
                    n = i + 1
                    it = f.get(k)
                    st = states[k]
                    if it is None:
                        if st == "empty":
                            name = self._fit(key_label(k), self.name_w - 30)
                            t.insert("end", "   ", ("empty",), name + "\t", ("ename", "empty"), "\n", ("empty",))
                        else:
                            t.insert("end", "\n", ("miss" if other is not None else "same",))
                        continue
                    tag = "only" if st == "only" else st
                    marker = "● " if f.field_modified(k) else "   "
                    name = self._fit(key_label(k), self.name_w - 30)
                    val = self._disp(it)
                    t.insert("end", marker, ("mod", tag), name + "\t", ("name", tag), val, (tag,), "\n", (tag,))
                    off = len(marker) + len(name) + 1
                    for a, b, url in core.link_spans(val):
                        tg = f"u_{len(self._links)}"
                        self._links[tg] = url
                        t.tag_add("link", f"{n}.{off + a}", f"{n}.{off + b}")
                        t.tag_add(tg, f"{n}.{off + a}", f"{n}.{off + b}")
                    if st in ("diff", "triv") and other is not None and other.get(k) is not None:
                        self._mark_chars(t, n, len(marker) + len(name) + 1, val, self._disp(other.get(k)),
                                         "chg" if st == "diff" else "tchg")
            t.configure(state="disabled")
        self._render_mid(l, r, rows, states)
        self._render_covers(l, r)
        for t in self._texts():
            t.yview_moveto(ypos)
        self._paint_sel()
        self._lines_later()
        pair_id = (id(l), id(r))
        if pair_id != getattr(self, "_layout_for", None):
            self._layout_for = pair_id
            if self.layout_auto:
                self.after_idle(self._auto_layout)
        self._refresh_info()
        for k, b in self.fb.items():
            b.set_active(self.filter == k)
        self.b_triv.set_active(self.show_trivial)
        self.b_empty.set_active(self.empty_set != "off")
        self.b_cover.set_active(self.show_covers)
        self.b_empty.t.configure(text={"off": "Leere Felder", "v1": "Leere: v1", "v23": "Leere: v2.3",
                                       "v24": "Leere: v2.4", "all": "Leere: alle"}[self.empty_set])
        both = l is not None and r is not None
        for b in (self.b_r, self.b_l, self.b_ar, self.b_al, self.b_mr, self.b_ml):
            b.set_enabled(both)
        self._update_status()

    @staticmethod
    def _disp(it):
        return core.disp(it)

    def _fit(self, s, width):
        f = self.f_ui
        if f.measure(s) <= width:
            return s
        while s and f.measure(s + "…") > width:
            s = s[:-1]
        return s + "…"

    def _mark_chars(self, t, line, off, a, b, tag):
        for i1, i2 in core.diff_spans(a, b):
            t.tag_add(tag, f"{line}.{off + i1}", f"{line}.{off + i2}")

    def _paint_sel(self):
        for t in self._texts():
            t.tag_remove("rowsel", "1.0", "end")
            for k in self.sel:
                if k in self.rows:
                    n = self._ln(self.rows.index(k))
                    t.tag_add("rowsel", f"{n}.0", f"{n}.end+1c")
            t.tag_raise("rowsel")
            for tg in ("chg", "tchg", "mod", "name", "ename", "toL", "toR", "link"):
                t.tag_raise(tg)

    def _refresh_info(self):
        l, r = self._files()
        self.info_l.configure(text=l.info() if l else "")
        self.info_r.configure(text=r.info() if r else "")
        self.title_l.configure(text=os.path.basename(l.path) if l else "—")
        self.title_r.configure(text=os.path.basename(r.path) if r else "—")

    # ------------------------------------------------------------------ Maus
    def _row_at(self, w, e):
        idx = w.index(f"@{e.x},{e.y}")
        line = int(idx.split(".")[0])
        n = line - 1
        bbox = w.dlineinfo(f"{line}.0")
        if 0 <= n < len(self.rows) and bbox and e.y <= bbox[1] + bbox[3] + 2:
            return self.rows[n]
        return None

    # ------------------------------------------------------------------ Splitter & optimale Breiten
    def hsb_height(self):
        try:
            return int(float(str(self.style.lookup("Horizontal.TScrollbar", "arrowsize") or 14))) + 2
        except (tk.TclError, ValueError):
            return 16

    def _set_name_w(self, w, rerender=True):
        pane_w = max(300, self.text_l.winfo_width())
        w = int(max(110 * self.dpi, min(w, pane_w - 120)))
        if w == self.name_w:
            return
        self.name_w = w
        for t in (self.text_l, self.text_r):
            t.configure(tabs=(w,))
        for lab in self.wert_labels:
            lab.place_configure(x=w - 4)
        for hd in self.col_handles:
            hd.place_configure(x=w - 12)
        self._lines_later()
        if rerender:
            self.render()

    def _optimal_name_w(self):
        if not self.rows:
            return self.name_w
        widest = max(self.f_ui.measure(key_label(k)) for k in self.rows)
        return widest + int(40 * self.dpi)

    def _text_drag(self, e, w):
        if getattr(self, "_coldrag", None) is w:
            self._col_drag(e.x + 10)
        return "break"

    def _col_drag(self, x):
        self.name_auto = False
        self._set_name_w(x, rerender=False)

    def _col_drag_end(self):
        if getattr(self, "_coldrag", None) is not None or not self.name_auto:
            self._coldrag = None
            self.render()

    def _col_auto(self):
        self.name_auto = True
        self._auto_layout(force=True)

    def _sash_press(self, e):
        self._sash_drag = "sash" in str(self.hpane.identify(e.x, e.y))

    def _sash_release(self, _e):
        if getattr(self, "_sash_drag", False):
            self.layout_auto = False
            self._sash_drag = False
            self._lines_later()

    def _content_width(self, f, rows):
        if f is None:
            return 0
        vals = [self._disp(f.get(k))[:140] for k in rows if f.get(k) is not None]
        if not vals:
            return 0
        vals.sort(key=len)
        sample = vals[-25:]  # die längsten Werte messen reicht
        return max(self.f_ui.measure(v) for v in sample)

    def _auto_layout(self, force=False):
        """Optimale Breiten je nach Inhalt: Namensspalte und Aufteilung links/rechts."""
        if force:
            self.layout_auto = True
        total = self.hpane.winfo_width()
        if total < 300:
            return
        if self.name_auto:
            self._set_name_w(self._optimal_name_w(), rerender=False)
        if self.layout_auto:
            sash = int(self.hpane.cget("sashwidth"))
            avail = total - self.mid_w - 2 * sash
            l, r = self._files()
            wl, wr = self._content_width(l, self.rows), self._content_width(r, self.rows)
            if l is None and r is not None:
                share = 0.3
            elif r is None and l is not None:
                share = 0.7
            elif wl + wr > 0:
                share = min(0.65, max(0.35, (self.name_w + wl) / (2 * self.name_w + wl + wr)))
            else:
                share = 0.5
            x0 = int(avail * share)
            try:
                self.hpane.sash_place(0, x0, 1)
                self.hpane.sash_place(1, x0 + sash + self.mid_w, 1)
            except tk.TclError:
                pass
        if force:
            self.render()
        self._lines_later()

    # ------------------------------------------------------------------ Fenster platzieren
    def _center(self, win, parent=None):
        """Zeigt ein Fenster zentriert über dem aktiven Programmfenster an – also auf dem Bildschirm,
        auf dem das Programm gerade liegt (auch bei mehreren Monitoren)."""
        parent = parent or self
        try:
            act = _active_window()
            if act is not None and act is not win and act.winfo_viewable():
                parent = act
        except tk.TclError:
            pass
        win.update_idletasks()
        w, h = getattr(win, "_size", (win.winfo_reqwidth(), win.winfo_reqheight()))
        w = int(w * (self.dpi if hasattr(win, "_size") else 1))
        h = int(h * (self.dpi if hasattr(win, "_size") else 1))
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        x = px + (pw - w) // 2
        y = py + max(0, (ph - h) // 3)
        # nicht über den oberen/linken Rand des Programmfensters hinaus schieben
        x, y = max(x, px - w // 4), max(y, py)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.deiconify()
        win.lift()
        try:
            win.focus_force()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ Suche & Filter
    def _debounce(self, name, fn, ms):
        jobs = self.__dict__.setdefault("_debounce_jobs", {})
        if jobs.get(name):
            self.after_cancel(jobs[name])
        jobs[name] = self.after(ms, lambda: (jobs.pop(name, None), fn()))

    def reset_filter(self):
        self.q_text.set("")
        self.f_field.set("— kein Filter —")
        self.f_val.set("")
        self.f_op.set("enthält")
        self.f_side.set("links oder rechts")

    def _update_field_choices(self, pairs):
        ch = core.field_choices(pairs)
        self._field_choices = ch
        self.f_field_cb.configure(values=list(ch))
        if self.f_field.get() not in ch:
            self.f_field.set("— kein Filter —")

    def _make_pair_filter(self):
        """Prüffunktion für ein Paar (oder None, wenn kein Filter aktiv ist)."""
        return core.make_pair_filter(self.q_text.get(), self._field_choices.get(self.f_field.get()),
                                     self.f_op.get(), self.f_val.get(), self.f_side.get())

    def _field_match(self, k, q, l, r):
        return core.field_match(k, q, l, r)

    # ------------------------------------------------------------------ Cover-Vorschau
    def toggle_covers(self):
        self.show_covers = not self.show_covers
        for side, strip in self.cover_strips.items():
            if self.show_covers:
                strip.pack(fill="x", before=self.cover_before[side])
            else:
                strip.pack_forget()
        self.render()

    def _thumb_worker(self):
        while True:
            key, data, size = self._thumb_jobs.get()
            try:
                png = thumbs.make_png(data, size)
            except Exception:  # noqa: BLE001
                png = None
            self._thumb_done.put((key, png))

    def _thumb(self, data, size):
        """PhotoImage aus dem Cache oder None (dann wird es im Hintergrund erzeugt)."""
        import base64 as _b64
        key = (hashlib.md5(data).hexdigest(), size)
        if key in self._thumb_cache:
            return self._thumb_cache[key]
        if key not in self._thumb_pending:
            self._thumb_pending.add(key)
            self._thumb_jobs.put((key, data, size))
            self.after(80, self._thumb_poll)
        return None

    def _thumb_poll(self):
        import base64 as _b64
        got = False
        try:
            while True:
                key, png = self._thumb_done.get_nowait()
                self._thumb_pending.discard(key)
                img = False
                if png:
                    try:
                        img = tk.PhotoImage(data=_b64.b64encode(png).decode("ascii"))
                    except tk.TclError:
                        img = False
                self._thumb_cache[key] = img
                got = True
        except queue.Empty:
            pass
        if got:
            self._render_covers(*self._files())
            for cb in list(self.__dict__.get("_thumb_listeners", [])):
                cb()
        if self._thumb_pending:
            self.after(120, self._thumb_poll)

    def _render_covers(self, l, r):
        if not self.show_covers:
            return
        th = self.th
        same = None
        for side, f, other in (("L", l, r), ("R", r, l)):
            strip = self.cover_strips[side]
            for w in strip.winfo_children():
                w.destroy()
            if f is None:
                continue
            keys = sorted((k for k, it in f.items.items() if it.kind == "picture"), key=sort_key)
            if not keys:
                tk.Label(strip, text="kein Cover", bg=th["panel"], fg=th["dim"], font=self.f_small).pack(
                    side="left", padx=12)
                if other is not None and any(it.kind == "picture" for it in other.items.values()):
                    same = False
                continue
            for k in keys[:5]:
                it = f.get(k)
                differ = other is not None and other.get(k) != it
                if other is not None:
                    same = (same is not False) and not differ
                box = tk.Frame(strip, bg=th["panel"], highlightthickness=2,
                               highlightbackground=th["chg"] if differ else th["panel"])
                box.pack(side="left", padx=(8, 2), pady=4)
                img = self._thumb(it.cover.data, self.thumb_px)
                if img:
                    lab = tk.Label(box, image=img, bg=th["panel"], cursor="hand2", bd=0)
                    lab.image = img
                else:
                    lab = tk.Label(box, text="…" if img is None else it.cover.mime.split("/")[-1].upper(),
                                   width=10, height=4, bg=th["entry"], fg=th["dim"], cursor="hand2")
                lab.pack()
                d = it.cover.dimensions()
                cap = (f"{d[0]}×{d[1]} · " if d else "") + f"{len(it.cover.data) // 1024} KB"
                tk.Label(box, text=cap, bg=th["panel"], fg=th["chg"] if differ else th["dim"],
                         font=self.f_small).pack()
                lab.bind("<Button-1>", lambda e, s=side, kk=k: self.cover_window(s, kk))
                Tooltip(lab, f"{key_label(k)} · {it.cover.describe()}\nKlick: große Ansicht", self)
        if l is not None and r is not None and same is not None:
            self.cover_mid.configure(text="=" if same else "≠", fg=th["g_save"] if same else th["chg"])
        else:
            self.cover_mid.configure(text="")

    def cover_window(self, side, key):
        f = self._file(side)
        it = f.get(key) if f else None
        if not it or not it.cover:
            return
        th = self.th
        w = tk.Toplevel(self)
        w.withdraw()  # erst zentriert anzeigen
        w.title(f"{key_label(key)} – {os.path.basename(f.path)}")
        w.configure(bg=th["bg"])
        w.transient(self)
        size = int(480 * self.dpi)
        lab = tk.Label(w, text="lade …", bg=th["bg"], fg=th["dim"], width=40, height=16)
        lab.pack(padx=12, pady=12)
        ttk.Label(w, text=it.cover.describe(), style="Dim.TLabel").pack()
        bf = ttk.Frame(w, padding=10)
        bf.pack(fill="x")
        ttk.Button(bf, text="Schließen", command=w.destroy).pack(side="right")
        ttk.Button(bf, text="Speichern unter …", command=lambda: self.export_cover(side, key)).pack(side="right", padx=6)
        ttk.Button(bf, text="Im Bildbetrachter öffnen", command=lambda: self.show_cover(side, key)).pack(side="right")
        w.bind("<Escape>", lambda e: w.destroy())
        self._center(w)

        def fill():
            if not w.winfo_exists():
                return
            img = self._thumb(it.cover.data, size)
            if img:
                lab.configure(image=img, text="", width=0, height=0)
                lab.image = img
                return True
            if img is False:
                lab.configure(text="Vorschau nicht möglich – „Im Bildbetrachter öffnen“ verwenden.")
                return True
            return False
        if not fill():
            lst = self.__dict__.setdefault("_thumb_listeners", [])

            def cb():
                if fill() and cb in lst:
                    lst.remove(cb)
            lst.append(cb)

    # ------------------------------------------------------------------ Befehlsspalte
    def _render_mid(self, l, r, rows, states):
        t = self.text_m
        t.configure(state="normal")
        t.delete("1.0", "end")
        both = l is not None and r is not None
        self._mid_caps = {}
        for k in rows:
            st = states[k]
            tag = st if st in ("diff", "triv", "only", "empty") else "same"
            li, ri = (l.get(k) if l else None), (r.get(k) if r else None)
            can_l = both and ri is not None and st in ("diff", "triv", "only")
            can_r = both and li is not None and st in ("diff", "triv", "only")
            self._mid_caps[k] = (can_l, can_r)
            t.insert("end", "◀" if can_l else " ", ("toL", tag, "mid") if can_l else (tag, "mid"),
                     "      ", (tag, "mid"),
                     "▶" if can_r else " ", ("toR", tag, "mid") if can_r else (tag, "mid"),
                     "\n", (tag, "mid"))
        t.configure(state="disabled")

    def _mid_hit(self, e):
        """Zeile + Richtung: linke Hälfte der Befehlsspalte = ◀ (nach links), rechte Hälfte = ▶."""
        t = self.text_m
        line = int(t.index(f"@{e.x},{e.y}").split(".")[0])
        info = t.dlineinfo(f"{line}.0")
        if not (1 <= line <= len(self.rows)) or not info or e.y > info[1] + info[3]:
            return None, None
        k = self.rows[line - 1]
        can_l, can_r = self._mid_caps.get(k, (False, False))
        if e.x < t.winfo_width() / 2:
            return k, "rl" if can_l else None
        return k, "lr" if can_r else None

    def on_mid_motion(self, e):
        k, d = self._mid_hit(e)
        t = self.text_m
        t.tag_remove("hot", "1.0", "end")
        if d:
            n = self.rows.index(k) + 1
            rng = t.tag_nextrange("toL" if d == "rl" else "toR", f"{n}.0", f"{n}.end")
            if rng:
                t.tag_add("hot", *rng)
                t.tag_raise("hot")
            t.configure(cursor="hand2")
        else:
            t.configure(cursor="arrow")

    def on_mid_click(self, e):
        self._name_tip_hide()
        self._close_editor(commit=True)
        k, d = self._mid_hit(e)
        if k is None:
            line = int(self.text_m.index(f"@{e.x},{e.y}").split(".")[0])
            if 1 <= line <= len(self.rows):
                k = self.rows[line - 1]
                self.sel, self.anchor = {k}, k
                self._paint_sel()
            return "break"
        src, dst = self._src_dst(d)
        if src and dst:
            self.undo.checkpoint(f"„{key_label(k)}“ {'nach rechts' if d == 'lr' else 'nach links'}", [dst])
            dst.set(k, src.get(k))
            self.sel, self.anchor = {k}, k
            self._changed(f"„{key_label(k)}“ {'nach rechts' if d == 'lr' else 'nach links'} übernommen – noch nicht gespeichert.")
        return "break"

    # ------------------------------------------------------------------ feine Trennlinien
    def _lines_later(self):
        if not getattr(self, "_lines_job", None):
            self._lines_job = self.after_idle(self._draw_lines)

    def _draw_lines(self):
        """1-px-Linien unter jeder sichtbaren Zeile (Overlay, folgt dem Scrollen)."""
        self._lines_job = None
        if not hasattr(self, "_line_pool"):
            self._line_pool = {self.text_l: [], self.text_m: [], self.text_r: []}
            self._col_lines = {t: tk.Frame(t, width=1, bd=0, highlightthickness=0, bg=self.th["grid"])
                               for t in (self.text_l, self.text_r)}
        for t, fr in self._col_lines.items():
            if self.rows and any(self._files()):
                fr.place(x=self.name_w - 10, y=0, width=1, relheight=1.0)
            else:
                fr.place_forget()
        n_rows = len(self.rows)
        for t, pool in self._line_pool.items():
            used = 0
            files = self._files()
            if n_rows and any(files):
                first = int(t.index("@0,0").split(".")[0])
                last = int(t.index(f"@0,{t.winfo_height()}").split(".")[0])
                for line in range(first, min(last, n_rows) + 1):
                    info = t.dlineinfo(f"{line}.0")
                    if not info:
                        continue
                    if used == len(pool):
                        pool.append(tk.Frame(t, height=1, bd=0, highlightthickness=0, bg=self.th["grid"]))
                    pool[used].place(x=0, y=info[1] + info[3] - 1, relwidth=1.0, height=1)
                    used += 1
            for fr in pool[used:]:
                fr.place_forget()
        if self.editor:
            self.editor[0].lift()

    @staticmethod
    def _ln(i):
        """Textzeile der Datenzeile i."""
        return i + 1

    def _link_at(self, w, e):
        """URL unter dem Mauszeiger (nur wenn wirklich über dem Linktext)."""
        if w not in (self.text_l, self.text_r):
            return None
        idx = w.index(f"@{e.x},{e.y}")
        bb = w.bbox(idx)
        if not bb or not (bb[0] <= e.x <= bb[0] + bb[2] + 1 and bb[1] <= e.y <= bb[1] + bb[3] + 1):
            return None
        for tg in w.tag_names(idx):
            if tg.startswith("u_"):
                return self._links.get(tg)
        return None

    def open_url(self, url):
        if not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.I):
            url = "https://" + url
        try:
            webbrowser.open(url, new=2)
            self._status("↗", f"Geöffnet: {url}", "g_cmp")
        except Exception as ex:  # noqa: BLE001
            messagebox.showerror(APP, f"Link konnte nicht geöffnet werden:\n{url}\n\n{ex}")

    def on_click(self, e, w):
        self._name_tip_hide()
        url = self._link_at(w, e)
        if url:
            k = self._row_at(w, e)
            if k:
                self.sel, self.anchor = {k}, k
                self._paint_sel()
            self.open_url(url)
            return "break"
        if abs(e.x - (self.name_w - 10)) <= 4 and w in (self.text_l, self.text_r):
            self._coldrag = w
            return "break"
        w.focus_set()
        self._close_editor(commit=True)
        k = self._row_at(w, e)
        if k is None:
            self.sel, self.anchor = set(), None
        elif e.state & 0x1 and self.anchor in self.rows:
            a, b = sorted((self.rows.index(self.anchor), self.rows.index(k)))
            self.sel = set(self.rows[a:b + 1])
        elif e.state & 0x4 or (IS_MAC and e.state & 0x8):
            self.sel ^= {k}
            self.anchor = k
        else:
            self.sel, self.anchor = {k}, k
        self._paint_sel()
        return "break"

    def on_double(self, e, w):
        k = self._row_at(w, e)
        if k:
            self.edit_field("L" if w is self.text_l else "R", k)
        return "break"

    def on_context(self, e, w):
        self._name_tip_hide()
        k = self._row_at(w, e)
        if k is None:
            return "break"
        if k not in self.sel:
            self.sel, self.anchor = {k}, k
            self._paint_sel()
        side = "L" if w is self.text_l else "R"
        f = self._file(side)
        l, r = self._files()
        it = f.get(k) if f else None
        m = self.ctx
        m.delete(0, "end")
        n = len(self.sel)
        lbl = f"„{key_label(k)}“" if n == 1 else f"{n} Felder"
        if f is not None:
            if it is None or it.editable:
                m.add_command(label=f"Bearbeiten …   (Doppelklick)", command=lambda: self.edit_field(side, k))
            if k.startswith("APIC"):
                if it is not None:
                    m.add_command(label="Bild anzeigen", command=lambda: self.show_cover(side, k))
                    m.add_command(label="Bild speichern unter …", command=lambda: self.export_cover(side, k))
                m.add_command(label="Bild ersetzen …", command=lambda: self.load_cover(side, k))
            m.add_separator()
        if l is not None and r is not None:
            m.add_command(label=f"{lbl}  →  nach rechts kopieren", command=lambda: self.copy_sel("lr"))
            m.add_command(label=f"{lbl}  ←  nach links kopieren", command=lambda: self.copy_sel("rl"))
            m.add_separator()
        if f is not None:
            m.add_command(label=f"{lbl} {'links' if side == 'L' else 'rechts'} entfernen",
                          command=lambda: self.remove_sel(side))
            m.add_command(label="Änderung zurücknehmen", command=lambda: self.undo_sel())
            m.add_separator()
            m.add_command(label="Neues Feld hinzufügen …", command=lambda: self.add_field_dialog(side))
            m.add_command(label="Datei im Ordner zeigen", command=lambda: self.reveal(f.path))
            urls = [mt.group(0).rstrip(".,;)") for mt in URL_RE.finditer(it.display())] if it is not None else []
            if urls:
                m.add_separator()
                for u in urls[:5]:
                    m.add_command(label=f"Link öffnen: {u[:70]}", command=lambda uu=u: self.open_url(uu))
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()
        return "break"

    # ------------------------------------------------------------------ Bearbeiten
    def _file(self, side):
        l, r = self._files()
        return l if side == "L" else r

    def edit_field(self, side, key):
        f = self._file(side)
        if f is None:
            return
        it = f.get(key)
        if key.startswith("APIC"):
            self.load_cover(side, key)
            return
        xml = xmltools.xml_of_item(it)
        if xml is not None:
            self._xml_dialog(f, key, xml[0], xml[1])
            return
        if it is None and key.split(":")[0] not in TEXT_LABELS and not key.startswith(("TXXX", "COMM", "WXXX", "USLT")) \
                and not key.startswith(("T", "W")):
            messagebox.showinfo(APP, f"„{key_label(key)}“ kann nur kopiert werden.")
            return
        if it is not None and not it.editable:
            if key.startswith("APIC"):
                self.load_cover(side, key)
            else:
                messagebox.showinfo(APP, f"„{key_label(key)}“ ist ein Binärfeld und kann nur kopiert oder entfernt werden.")
            return
        if key not in self.rows:
            return
        text = it.text.replace(MV, MV_SHOW) if it else ""
        if "\n" in text or key.startswith("USLT"):
            self._edit_dialog(f, key, text)
            return
        t = self.text_l if side == "L" else self.text_r
        n = self._ln(self.rows.index(key))
        t.see(f"{n}.0")
        self.update_idletasks()
        info = t.dlineinfo(f"{n}.0")
        if not info:
            return
        self._close_editor(commit=True)
        th = self.th
        x0 = self.name_w - 4
        e = tk.Entry(t, font=self.f_ui, bg=th["entry"], fg=th["fg"], insertbackground=th["fg"],
                     relief="flat", highlightthickness=1, highlightcolor=th["accent"],
                     highlightbackground=th["accent"], selectbackground=th["sel"], selectforeground=th["fg"])
        e.insert(0, text)
        e.select_range(0, "end")
        e.place(x=x0, y=info[1], width=max(120, t.winfo_width() - x0 - 6), height=info[3])
        e.lift()
        e.focus_set()
        self.editor = (e, f, key)
        e.bind("<Return>", lambda ev: self._close_editor(commit=True))
        e.bind("<KP_Enter>", lambda ev: self._close_editor(commit=True))
        e.bind("<Escape>", lambda ev: self._close_editor(commit=False))
        e.bind("<Tab>", lambda ev: self._editor_tab(side))
        e.bind("<FocusOut>", lambda ev: self._close_editor(commit=True))

    def _editor_tab(self, side):
        if not self.editor:
            return "break"
        key = self.editor[2]
        self._close_editor(commit=True)
        i = self.rows.index(key) + 1 if key in self.rows else 0
        f = self._file(side)
        while i < len(self.rows):
            it = f.get(self.rows[i]) if f else None
            if it is None or it.editable:
                self.sel, self.anchor = {self.rows[i]}, self.rows[i]
                self._paint_sel()
                self.edit_field(side, self.rows[i])
                break
            i += 1
        return "break"

    def _close_editor(self, commit=True):
        if not self.editor:
            return
        e, f, key = self.editor
        self.editor = None
        val = e.get()
        e.destroy()
        if commit:
            self._set_value(f, key, val)

    def _set_value(self, f, key, val):
        it = f.get(key)
        if core.normalize_value(val) == (it.text if it else ""):
            return
        self.undo.checkpoint(f"„{key_label(key)}“ bearbeitet", [f])
        core.apply_value(f, key, val)
        self._changed()

    # ------------------------------------------------------------------ XML-Editor
    _XML_RE = re.compile(r"(<!--[\s\S]*?(?:-->|$))|(<!\[CDATA\[[\s\S]*?(?:\]\]>|$))|(<\?[\s\S]*?(?:\?>|$))"
                         r"|(</?[A-Za-z_][\w:.\-]*)((?:\s+[^\s=>/]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+))?)*)\s*(/?>)?"
                         r"|(&[#\w]+;)")
    _ATTR_RE = re.compile(r"([^\s=]+)(\s*=\s*)?(\"[^\"]*\"|'[^']*'|[^\s\"']+)?")

    def _xml_dialog(self, f, key, text, editable=True):
        """Einfacher XML-Editor: Quelltext mit Hervorhebung, Prüfen, Formatieren, Kompakt."""
        th = self.th
        d = tk.Toplevel(self)
        d.withdraw()
        d.title(f"XML-Editor – {key_label(key)}" + ("" if editable else " (nur ansehen)"))
        d.configure(bg=th["bg"])
        d.transient(self)
        d.geometry("960x680")
        d.minsize(560, 360)
        mono = tkfont.Font(family=self.f_mono.actual("family"), size=self.f_ui.actual("size"))
        state = {"orig": text, "valid": True, "err": None, "job": None}

        bar = ttk.Frame(d, padding=(10, 10, 10, 6))
        bar.pack(fill="x")
        ttk.Label(bar, text=f"{os.path.basename(f.path)}  ·  {key_label(key)}", style="Dim.TLabel").pack(side="left")
        status = tk.Label(bar, text="", bg=th["bg"], font=self.f_bold, anchor="e", cursor="hand2")
        status.pack(side="right")
        tools = ttk.Frame(d, padding=(10, 0, 10, 8))
        tools.pack(fill="x")

        body = tk.Frame(d, bg=th["border"], bd=0)
        body.pack(fill="both", expand=True, padx=10)
        lines = tk.Text(body, width=5, padx=6, pady=8, bd=0, font=mono, bg=th["panel"], fg=th["dim"],
                        state="disabled", takefocus=0, cursor="arrow", highlightthickness=0)
        lines.pack(side="left", fill="y")
        ys = ttk.Scrollbar(body, orient="vertical")
        xs = ttk.Scrollbar(d, orient="horizontal")
        tx = tk.Text(body, wrap="none", undo=True, font=mono, bg=th["entry"], fg=th["fg"], insertbackground=th["fg"],
                     selectbackground=th["sel"], selectforeground=th["fg"], relief="flat", bd=0, padx=10, pady=8,
                     highlightthickness=0, tabs=(mono.measure("  "),))
        tx.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        xs.pack(fill="x", padx=10)

        def yscroll(*a):
            tx.yview(*a)
            lines.yview(*a)

        def on_y(first, last):
            ys.set(first, last)
            lines.yview_moveto(first)
        ys.configure(command=yscroll)
        tx.configure(yscrollcommand=on_y, xscrollcommand=xs.set)
        xs.configure(command=tx.xview)
        for tag, tok in (("h_tag", "g_cmp"), ("h_attr", "mod"), ("h_str", "g_copy"), ("h_ent", "ok"),
                         ("h_com", "dim"), ("h_pi", "dim"), ("h_cdata", "ok")):
            tx.tag_configure(tag, foreground=th[tok])
        tx.tag_configure("h_err", background=th["diff_bg"])
        lines.tag_configure("err", foreground=th["chg"])
        lines.tag_configure("right", justify="right")
        tx.insert("1.0", text)
        tx.edit_reset()

        def content():
            return tx.get("1.0", "end-1c")

        def highlight():
            s = content()
            for t in ("h_tag", "h_attr", "h_str", "h_ent", "h_com", "h_pi", "h_cdata"):
                tx.tag_remove(t, "1.0", "end")
            if len(s) > 300_000:
                return

            def mark(tag, a, b):
                if b > a:
                    tx.tag_add(tag, f"1.0+{a}c", f"1.0+{b}c")
            for m in self._XML_RE.finditer(s):
                if m.group(1):
                    mark("h_com", *m.span(1))
                elif m.group(2):
                    mark("h_cdata", *m.span(2))
                elif m.group(3):
                    mark("h_pi", *m.span(3))
                elif m.group(4):
                    mark("h_tag", *m.span(4))
                    if m.group(5):
                        base = m.start(5)
                        for am in self._ATTR_RE.finditer(m.group(5)):
                            mark("h_attr", base + am.start(1), base + am.end(1))
                            if am.group(3):
                                mark("h_str", base + am.start(3), base + am.end(3))
                    if m.group(6):
                        mark("h_tag", *m.span(6))
                elif m.group(7):
                    mark("h_ent", *m.span(7))

        def numbers():
            n = int(tx.index("end-1c").split(".")[0])
            err = state["err"]["line"] if state["err"] else -1
            lines.configure(state="normal")
            lines.delete("1.0", "end")
            lines.insert("1.0", "\n".join(str(i) for i in range(1, n + 1)), ("right",))
            if 1 <= err <= n:
                lines.tag_add("err", f"{err}.0", f"{err}.end")
            lines.configure(state="disabled")
            lines.yview_moveto(tx.yview()[0])

        def validate():
            r = xmltools.check(content())
            state["valid"], state["err"] = r["ok"], (None if r["ok"] else r)
            tx.tag_remove("h_err", "1.0", "end")
            if r["ok"]:
                status.configure(text="✓ Gültiges XML", fg=th["ok"])
            else:
                status.configure(text=f"✗ Zeile {r['line']}, Spalte {r['col']}: {r['error']}", fg=th["chg"])
                tx.tag_add("h_err", f"{r['line']}.0", f"{r['line']}.end")
            numbers()

        def refresh(_e=None):
            if state["job"]:
                d.after_cancel(state["job"])

            def run():
                state["job"] = None
                highlight()
                validate()
            state["job"] = d.after(250, run)

        def jump(_e=None):
            e = state["err"]
            if e:
                tx.mark_set("insert", f"{e['line']}.{max(0, e['col'] - 1)}")
                tx.see("insert")
                tx.focus_set()
        status.bind("<Button-1>", jump)

        def tool(action):
            r = xmltools.format_xml(content(), compact=(action == "compact"))
            if not r["ok"]:
                state["err"] = r
                validate()
                jump()
                return
            tx.edit_separator()
            tx.delete("1.0", "end")
            tx.insert("1.0", r["text"])
            tx.edit_separator()
            highlight()
            validate()
        b1 = ttk.Button(tools, text="Formatieren", command=lambda: tool("format"))
        b2 = ttk.Button(tools, text="Kompakt", command=lambda: tool("compact"))
        b1.pack(side="left")
        b2.pack(side="left", padx=6)
        ttk.Label(tools, text="Strg/Cmd+Enter übernimmt · Esc schließt", style="Dim.TLabel").pack(side="right")

        def close(commit):
            new = content()
            if commit and editable and new != state["orig"]:
                if not state["valid"] and not messagebox.askyesno(
                        APP, f"Das XML ist nicht gültig:\n{status.cget('text')}\n\nTrotzdem übernehmen?", parent=d):
                    return
                self._set_value(f, key, new)
            elif not commit and editable and new != state["orig"]:
                if not messagebox.askyesno(APP, "Änderungen im XML-Editor verwerfen?", parent=d):
                    return
            d.destroy()

        bf = ttk.Frame(d, padding=10)
        bf.pack(fill="x")
        ttk.Button(bf, text="Übernehmen" if editable else "Schließen", command=lambda: close(True)).pack(side="right")
        if editable:
            ttk.Button(bf, text="Abbrechen", command=lambda: close(False)).pack(side="right", padx=6)
        else:
            b1.state(["disabled"])
            b2.state(["disabled"])
        tx.bind("<<Modified>>", lambda e: (tx.edit_modified(False), refresh()))
        tx.bind("<Tab>", lambda e: (tx.insert("insert", "  "), "break")[1])
        d.bind("<Escape>", lambda e: close(False))
        d.bind(f"<{MOD}-Return>", lambda e: close(True))
        d.protocol("WM_DELETE_WINDOW", lambda: close(False))
        highlight()
        validate()
        if not editable:
            tx.configure(state="disabled")
        self._center(d)
        tx.focus_set()
        d.xml_text, d.xml_tool, d.xml_close, d.xml_status = tx, tool, close, status  # für Tests
        return d

    def _edit_dialog(self, f, key, text):
        th = self.th
        d = tk.Toplevel(self)
        d.withdraw()  # erst zentriert anzeigen
        d.title(key_label(key))
        d.configure(bg=th["bg"])
        d.transient(self)
        tx = tk.Text(d, width=70, height=18, wrap="word", font=self.f_ui, bg=th["entry"], fg=th["fg"],
                     insertbackground=th["fg"], relief="flat", padx=8, pady=8, undo=True)
        tx.pack(fill="both", expand=True, padx=10, pady=10)
        tx.insert("1.0", text)
        bf = ttk.Frame(d, padding=(10, 0, 10, 10))
        bf.pack(fill="x")

        def ok():
            self._set_value(f, key, tx.get("1.0", "end-1c"))
            d.destroy()
        ttk.Button(bf, text="Übernehmen", command=ok).pack(side="right")
        ttk.Button(bf, text="Abbrechen", command=d.destroy).pack(side="right", padx=6)
        tx.focus_set()
        self._center(d)

    # ------------------------------------------------------------------ Kopieren
    def _src_dst(self, direction):
        l, r = self._files()
        return (l, r) if direction == "lr" else (r, l)

    def copy_sel(self, direction):
        if self.editor:
            return
        src, dst = self._src_dst(direction)
        if not (src and dst):
            return
        keys = [k for k in self.rows if k in self.sel]
        if not keys:
            self._status("ℹ", "Bitte zuerst Felder markieren (Klick, Shift/Strg-Klick).", "g_cmp")
            return
        n = 0
        self.undo.checkpoint(f"{len(keys)} Feld(er) {'nach rechts' if direction == 'lr' else 'nach links'}", [dst])
        for k in keys:
            if dst.get(k) != src.get(k):
                dst.set(k, src.get(k))
                n += 1
        self._changed(f"{n} Feld(er) {'nach rechts' if direction == 'lr' else 'nach links'} kopiert – noch nicht gespeichert.")

    def copy_all(self, direction):
        src, dst = self._src_dst(direction)
        if not (src and dst):
            return
        imp, triv = diff(src, dst, self.rules)
        keys = imp + (triv if self.show_trivial else [])
        if not keys:
            self._status("✔", "Keine Unterschiede zum Kopieren.", "g_save")
            return
        missing = [k for k in keys if src.get(k) is None]
        delete = False
        if missing:
            ans = messagebox.askyesnocancel(
                APP, f"{len(missing)} Feld(er) gibt es nur im Ziel:\n\n"
                     + "\n".join("• " + key_label(k) for k in missing[:12])
                     + ("\n…" if len(missing) > 12 else "")
                     + "\n\nSollen diese im Ziel entfernt werden, damit beide Seiten gleich sind?")
            if ans is None:
                return
            delete = ans
        self.undo.checkpoint(f"Alles {'nach rechts' if direction == 'lr' else 'nach links'}", [dst])
        n = copy_tags(src, dst, keys, delete_missing=delete)
        self._changed(f"{n} Feld(er) {'nach rechts' if direction == 'lr' else 'nach links'} übernommen – noch nicht gespeichert.")

    def copy_missing(self, direction):
        """Nur Felder übernehmen, die im Ziel fehlen."""
        src, dst = self._src_dst(direction)
        if not (src and dst):
            return
        keys = [k for k in all_keys(src, dst) if src.get(k) is not None and dst.get(k) is None]
        if not self.show_trivial:
            keys = [k for k in keys if not self.rules.is_trivial(k)]
        if not keys:
            self._status("✔", f"Keine fehlenden Felder {'rechts' if direction == 'lr' else 'links'}.", "g_save")
            return
        self.undo.checkpoint(f"Fehlende {'nach rechts' if direction == 'lr' else 'nach links'}", [dst])
        for k in keys:
            dst.set(k, src.get(k))
        self._changed(f"{len(keys)} fehlende(s) Feld(er) {'nach rechts' if direction == 'lr' else 'nach links'} "
                      f"übernommen – noch nicht gespeichert.")

    def remove_sel(self, side):
        f = self._file(side)
        keys = [k for k in self.sel if f and f.get(k) is not None]
        if not keys:
            return
        self.undo.checkpoint(f"{len(keys)} Feld(er) entfernt", [f])
        for k in keys:
            f.set(k, None)
        self._changed(f"{len(keys)} Feld(er) entfernt – noch nicht gespeichert.")

    def undo_sel(self):
        self.undo.checkpoint("Änderung zurückgenommen", list(self._files()))
        for f in self._files():
            if f is None:
                continue
            for k in self.sel:
                orig = f._orig.get(k)
                f.set(k, orig) if orig is not None else f.set(k, None)
        self._changed()

    def revert_pair(self):
        self.undo.checkpoint("Paar verworfen", list(self._files()))
        for f in self._files():
            if f:
                f.revert()
        self._changed("Änderungen verworfen.")

    def _changed(self, msg=None):
        self._commit_undo()
        self.render()
        self._refresh_pair(self.cur)
        self._update_status()
        if msg:
            self._status("✎", msg, "mod")

    # ------------------------------------------------------------------ Feld hinzufügen
    def add_field_dialog(self, side=None):
        l, r = self._files()
        if not (l or r):
            return
        th = self.th
        d = tk.Toplevel(self)
        d.withdraw()  # erst zentriert anzeigen
        d.title("Feld hinzufügen")
        d.configure(bg=th["bg"])
        d.transient(self)
        d.resizable(False, False)
        frm = ttk.Frame(d, padding=14)
        frm.pack(fill="both")
        choices = {**{f"{v}": k for k, v in sorted(TEXT_LABELS.items(), key=lambda x: x[1]) if k not in ("TYER", "TIME", "TRDA", "TSIZ")},
                   "Benutzertext (TXXX) …": "TXXX", "Kommentar (COMM) …": "COMM", "Benutzer-URL (WXXX) …": "WXXX",
                   "Liedtext (USLT)": "USLT"}
        sv, fv, dv, vv = (tk.StringVar(value=side or ("L" if l else "R")), tk.StringVar(value="Benutzertext (TXXX) …"),
                          tk.StringVar(), tk.StringVar())
        ttk.Label(frm, text="Seite").grid(row=0, column=0, sticky="w", pady=4)
        rb = ttk.Frame(frm)
        rb.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(rb, text="Links", value="L", variable=sv, state="normal" if l else "disabled").pack(side="left")
        ttk.Radiobutton(rb, text="Rechts", value="R", variable=sv, state="normal" if r else "disabled").pack(side="left", padx=10)
        ttk.Label(frm, text="Feld").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(frm, textvariable=fv, values=list(choices), state="readonly", width=38, font=self.f_ui).grid(row=1, column=1, sticky="ew")
        ttk.Label(frm, text="Beschreibung").grid(row=2, column=0, sticky="w", pady=4)
        de = ttk.Entry(frm, textvariable=dv, font=self.f_ui)
        de.grid(row=2, column=1, sticky="ew")
        ttk.Label(frm, text="Wert").grid(row=3, column=0, sticky="w", pady=4)
        ve = ttk.Entry(frm, textvariable=vv, font=self.f_ui, width=50)
        ve.grid(row=3, column=1, sticky="ew")
        ttk.Label(frm, text="Beschreibung nur bei TXXX/COMM/WXXX/USLT (z. B. „Acoustid Id“).",
                  style="Dim.TLabel").grid(row=4, column=1, sticky="w")

        def ok():
            f = l if sv.get() == "L" else r
            fid = choices[fv.get()]
            key = f"{fid}:{dv.get().strip()}" if fid in ("TXXX", "COMM", "WXXX", "USLT") else fid
            if not vv.get().strip():
                return
            if f.get(key) is not None and not messagebox.askyesno(APP, f"„{key_label(key)}“ existiert schon. Ersetzen?"):
                return
            self.undo.checkpoint(f"„{key_label(key)}“ hinzugefügt", [f])
            f.set_text(key, re.sub(r"\s*¦\s*", MV, vv.get()).strip(MV))
            d.destroy()
            self.sel, self.anchor = {key}, key
            self._changed(f"„{key_label(key)}“ hinzugefügt – noch nicht gespeichert.")
        bf = ttk.Frame(frm)
        bf.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(bf, text="Abbrechen", command=d.destroy).pack(side="right")
        ttk.Button(bf, text="Hinzufügen", command=ok).pack(side="right", padx=6)
        ve.focus_set()
        d.bind("<Return>", lambda e: ok())
        d.bind("<Escape>", lambda e: d.destroy())
        self._center(d)

    # ------------------------------------------------------------------ Sammelkopie
    def bulk_dialog(self, direction):
        idx = [int(s) for s in self.tree.selection() if all(self.pairs[int(s)])]
        if not idx:
            messagebox.showinfo(APP, "Bitte in der Liste Dateipaare markieren (beide Seiten vorhanden).")
            return
        keys = set()
        for i in idx:
            src = self.pairs[i][0 if direction == "lr" else 1]
            keys |= set(src.items)
        keys = sorted(keys, key=sort_key)
        th = self.th
        d = tk.Toplevel(self)
        d.withdraw()  # erst zentriert anzeigen
        d.title("Sammelkopie")
        d.configure(bg=th["bg"])
        d.transient(self)
        d._size = (520, 620)
        frm = ttk.Frame(d, padding=12)
        frm.pack(fill="both", expand=True)
        arrow = "Links  →  Rechts" if direction == "lr" else "Rechts  →  Links"
        ttk.Label(frm, text=f"{arrow}   ·   {len(idx)} Paar(e)", font=self.f_title).pack(anchor="w")
        ttk.Label(frm, text="Welche Felder sollen übernommen werden?", style="Dim.TLabel").pack(anchor="w", pady=(2, 8))
        box = ttk.Frame(frm)
        box.pack(fill="both", expand=True)
        cv = tk.Canvas(box, bg=th["panel"], highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(box, orient="vertical", command=cv.yview)
        inner = tk.Frame(cv, bg=th["panel"])
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=inner, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        std = {k for k in keys if k in STANDARD_KEYS}
        vars_ = {}
        for k in keys:
            v = tk.BooleanVar(value=not self.rules.is_trivial(k))
            vars_[k] = v
            tk.Checkbutton(inner, text=key_label(k), variable=v, bg=th["panel"], fg=th["fg"], anchor="w",
                           selectcolor=th["entry"], activebackground=th["panel"], activeforeground=th["fg"],
                           font=self.f_ui, bd=0, highlightthickness=0).pack(fill="x", padx=8, pady=1)
        qb = ttk.Frame(frm)
        qb.pack(fill="x", pady=8)
        ttk.Button(qb, text="Alle", command=lambda: [v.set(True) for v in vars_.values()]).pack(side="left")
        ttk.Button(qb, text="Keine", command=lambda: [v.set(False) for v in vars_.values()]).pack(side="left", padx=4)
        ttk.Button(qb, text="Standardfelder", command=lambda: [v.set(k in std) for k, v in vars_.items()]).pack(side="left")
        ttk.Button(qb, text="Wichtige", command=lambda: [v.set(not self.rules.is_trivial(k)) for k, v in vars_.items()]).pack(side="left", padx=4)
        dele = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="Felder, die in der Quelle fehlen, im Ziel entfernen", variable=dele).pack(anchor="w")

        def ok():
            chosen = [k for k, v in vars_.items() if v.get()]
            n = 0
            self.undo.checkpoint(f"Sammelkopie {len(idx)} Paar(e)",
                                 [self.pairs[i][1 if direction == "lr" else 0] for i in idx])
            for i in idx:
                l, r = self.pairs[i]
                src, dst = (l, r) if direction == "lr" else (r, l)
                n += copy_tags(src, dst, chosen, delete_missing=dele.get())
                self._refresh_pair(i)
            d.destroy()
            self._commit_undo()
            self.render()
            self._status("✎", f"{n} Feld(er) in {len(idx)} Paar(en) übernommen – noch nicht gespeichert.", "mod")
        bf = ttk.Frame(frm)
        bf.pack(fill="x", pady=(10, 0))
        ttk.Button(bf, text="Abbrechen", command=d.destroy).pack(side="right")
        ttk.Button(bf, text="Übernehmen", command=ok).pack(side="right", padx=6)
        self._center(d)

    # ------------------------------------------------------------------ Bilder
    def show_cover(self, side, key):
        f = self._file(side)
        it = f.get(key) if f else None
        if not it or not it.cover:
            return
        fd, tmp = tempfile.mkstemp(prefix="cover_", suffix=it.cover.ext)
        with os.fdopen(fd, "wb") as out:
            out.write(it.cover.data)
        self._open(tmp)

    def export_cover(self, side, key):
        f = self._file(side)
        it = f.get(key) if f else None
        if not it or not it.cover:
            return
        base = os.path.splitext(os.path.basename(f.path))[0]
        p = filedialog.asksaveasfilename(initialfile=base + it.cover.ext, defaultextension=it.cover.ext)
        if p:
            with open(p, "wb") as fh:
                fh.write(it.cover.data)

    def load_cover(self, side, key):
        f = self._file(side)
        if not f:
            return
        p = filedialog.askopenfilename(title="Bild wählen", filetypes=[("Bilder", "*.jpg *.jpeg *.png *.JPG *.JPEG *.PNG"),
                                                                        ("Alle Dateien", "*")])
        if not p:
            return
        with open(p, "rb") as fh:
            data = fh.read()
        try:
            ptype = int(key.split(":")[1].split("#")[0])
        except (IndexError, ValueError):
            ptype = 3
        self.undo.checkpoint("Bild ersetzt", [f])
        f.set(key, Item.new_cover(Cover(data, ptype=ptype)))
        self._changed("Bild ersetzt – noch nicht gespeichert.")

    def _open(self, path):
        try:
            if IS_WIN:
                os.startfile(path)  # type: ignore[attr-defined]
            elif IS_MAC:
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as ex:  # noqa: BLE001
            messagebox.showerror(APP, f"Konnte nicht geöffnet werden:\n{ex}")

    def reveal(self, path):
        try:
            if IS_WIN:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            elif IS_MAC:
                subprocess.Popen(["open", "-R", path])
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(path)])
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ Filter
    def set_filter(self, f):
        self.filter = f
        self.render()

    def empty_menu(self):
        """Menü: vorgesehene Felder eines Standards einblenden, auch wenn sie leer sind."""
        m = tk.Menu(self, tearoff=0)
        th = self.th
        m.configure(bg=th["head"], fg=th["fg"], activebackground=th["sel"], activeforeground=th["fg"],
                    selectcolor=th["accent"])
        var = tk.StringVar(value=self.empty_set)
        for val, txt in (("off", "Nur beschriebene Felder"),
                         ("v1", "ID3v1-Felder einblenden"),
                         ("v23", "ID3v2.3-Felder einblenden"),
                         ("v24", "ID3v2.4-Felder einblenden"),
                         ("all", "Alle (v1 + v2.3 + v2.4)")):
            m.add_radiobutton(label=txt, value=val, variable=var, command=lambda v=val: self.set_empty(v))
        b = self.b_empty
        try:
            m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
        finally:
            m.grab_release()

    def set_empty(self, v):
        self.empty_set = v
        self.render()

    # ------------------------------------------------------------------ Mehrfachwerte-Fixer
    def multi_fix_dialog(self):
        l, r = self._files()
        if not self.pairs:
            messagebox.showinfo(APP, "Bitte zuerst Dateien laden.")
            return
        th = self.th
        fc = self.cfg.get("fixer", {})
        d = tk.Toplevel(self)
        d.withdraw()  # erst zentriert anzeigen
        d.title("Tag-Fixer – Mehrfachwerte")
        d.configure(bg=th["bg"])
        d.transient(self)
        d._size = (1200, 780)
        d.minsize(980, 560)
        main = ttk.Frame(d, padding=12)
        main.pack(fill="both", expand=True)
        left = ttk.Frame(main)
        left.pack(side="left", fill="y", padx=(0, 12))
        right = ttk.Frame(main)
        right.pack(side="left", fill="both", expand=True)

        def section(title):
            ttk.Label(left, text=title, font=self.f_bold).pack(anchor="w", pady=(10, 2))

        def cb(parent, text, var):
            ttk.Checkbutton(parent, text=text, variable=var).pack(anchor="w")

        # Dateien
        section("Dateien")
        sel_pairs = [int(x) for x in self.tree.selection()]
        scope = tk.StringVar(value="sel" if len(sel_pairs) > 1 else "pair")
        for val, txt in (("pair", "Aktuelles Paar (beide Seiten)"), ("L", "Aktuelles Paar – nur links"),
                         ("R", "Aktuelles Paar – nur rechts"), ("sel", f"Markierte Paare ({len(sel_pairs)})"),
                         ("all", f"Alle geladenen Dateien ({sum(1 for p in self.pairs for f in p if f)})")):
            ttk.Radiobutton(left, text=txt, value=val, variable=scope).pack(anchor="w")

        # Felder
        section("Felder")
        ff = ttk.Frame(left)
        ff.pack(anchor="w")
        chosen = set(fc.get("fields", MULTI_FIELDS))
        fvars = {}
        for i, k in enumerate(MULTI_FIELDS):
            v = tk.BooleanVar(value=k in chosen)
            fvars[k] = v
            ttk.Checkbutton(ff, text=key_label(k), variable=v).grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 10))
        all_text = tk.BooleanVar(value=fc.get("all_text", False))
        cb(left, "Alle Textfelder (inkl. Benutzertexte)", all_text)

        # Eingangs-Trenner
        section("Als Trenner erkennen")
        on = set(fc.get("seps", [s for _, s, a in INPUT_SEPARATORS if a]))
        svars = []
        sf = ttk.Frame(left)
        sf.pack(anchor="w")
        for i, (label, sep, _) in enumerate(INPUT_SEPARATORS):
            v = tk.BooleanVar(value=sep in on)
            svars.append((sep, v))
            ttk.Checkbutton(sf, text=label, variable=v).grid(row=i, column=0, sticky="w")

        # Ausgabe
        section("Ausgabe")
        mode = tk.StringVar(value=fc.get("mode", "sep"))
        sepv = tk.StringVar(value=fc.get("sep", ", "))
        row = ttk.Frame(left)
        row.pack(anchor="w")
        ttk.Radiobutton(row, text="Trennzeichen", value="sep", variable=mode).pack(side="left")
        ttk.Entry(row, textvariable=sepv, width=8, font=self.f_ui).pack(side="left", padx=6)
        ttk.Label(row, text="(Standard: Komma)", style="Dim.TLabel").pack(side="left")
        ttk.Radiobutton(left, text="ID3v2.4-Standard: echte Mehrfachwerte (null-getrennt)",
                        value="v24", variable=mode).pack(anchor="w", pady=(4, 0))
        upgrade = tk.BooleanVar(value=fc.get("upgrade", True))
        up_cb = ttk.Checkbutton(left, text="     ID3v2.3-Dateien dafür auf v2.4 umstellen", variable=upgrade)
        up_cb.pack(anchor="w")
        dedupe = tk.BooleanVar(value=fc.get("dedupe", True))
        cb(left, "Doppelte Werte entfernen", dedupe)

        # Vorschau
        hdr = ttk.Frame(right)
        hdr.pack(fill="x")
        ttk.Label(hdr, text="Vorschau", font=self.f_bold).pack(side="left")
        cnt = ttk.Label(hdr, style="Dim.TLabel")
        cnt.pack(side="left", padx=10)
        tf = ttk.Frame(right)
        tf.pack(fill="both", expand=True, pady=(6, 0))
        tv = ttk.Treeview(tf, columns=("file", "field", "old", "new"), show="headings")
        for c, t, w in (("file", "Datei", 230), ("field", "Feld", 150), ("old", "Vorher", 260), ("new", "Nachher", 260)):
            tv.heading(c, text=t, anchor="w")
            tv.column(c, width=w, anchor="w", stretch=c in ("old", "new"))
        tv.tag_configure("new", foreground=th["g_save"])
        ys = ttk.Scrollbar(tf, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=ys.set)
        tv.pack(side="left", fill="both", expand=True)
        ys.pack(side="left", fill="y")
        bf = ttk.Frame(right)
        bf.pack(fill="x", pady=(10, 0))
        ok_btn = ttk.Button(bf, text="Anwenden")
        ok_btn.pack(side="right")
        ttk.Button(bf, text="Abbrechen", command=d.destroy).pack(side="right", padx=6)
        ttk.Label(bf, text="Änderungen werden erst mit »Speichern« geschrieben.  Mehrfachwerte werden als  ¦  angezeigt.\n"
                           "Hinweis: Nicht alle Programme zeigen v2.4-Mehrfachwerte vollständig an (manche nur den ersten Wert). "
                           "v2.3-Dateien ohne Umstellung erhalten '; '.",
                  style="Dim.TLabel", justify="left", wraplength=700).pack(side="left")

        state = {"plan": [], "job": None}

        def files_in_scope():
            out = []
            sc = scope.get()
            if sc in ("pair", "L", "R"):
                if sc in ("pair", "L") and l:
                    out.append((l, "L"))
                if sc in ("pair", "R") and r:
                    out.append((r, "R"))
            else:
                idx = sel_pairs if sc == "sel" else range(len(self.pairs))
                for i in idx:
                    pl, pr = self.pairs[i]
                    out += [(f, s) for f, s in ((pl, "L"), (pr, "R")) if f]
            return out

        def refresh():
            state["job"] = None
            up_cb.state(["!disabled"] if mode.get() == "v24" else ["disabled"])
            fl = files_in_scope()
            side = {id(f): s for f, s in fl}
            seps = [sp for sp, v in svars if v.get()]
            out = MV if mode.get() == "v24" else (sepv.get() or ", ")
            plan = plan_multi_fix([f for f, _ in fl], [k for k, v in fvars.items() if v.get()], seps, out,
                                  dedupe.get(), all_text.get(), upgrade.get())
            state["plan"] = plan
            tv.delete(*tv.get_children())
            for f, k, old, new in plan[:3000]:
                tv.insert("", "end", values=(f"{'◧' if side[id(f)] == 'L' else '◨'} {os.path.basename(f.path)}",
                                             key_label(k), old.replace(MV, MV_SHOW), new.replace(MV, MV_SHOW)),
                          tags=("new",))
            nfiles = len({id(f) for f, *_ in plan})
            cnt.configure(text=f"{len(plan)} Änderung(en) in {nfiles} Datei(en)")
            ok_btn.configure(text=f"Anwenden ({len(plan)})")
            ok_btn.state(["!disabled"] if plan else ["disabled"])

        def schedule(*_a):
            if state["job"]:
                d.after_cancel(state["job"])
            state["job"] = d.after(150, refresh)

        for v in [scope, all_text, mode, sepv, upgrade, dedupe] + list(fvars.values()) + [v for _, v in svars]:
            v.trace_add("write", schedule)

        def apply():
            plan = state["plan"]
            to_v24 = mode.get() == "v24" and upgrade.get()
            self.undo.checkpoint(f"Tag-Fixer ({len(plan)} Felder)", [f for f, *_ in plan])
            for f, k, _old, new in plan:
                if to_v24 and f.version != 4:
                    f.set_version(4)
                f.set_text(k, new)
            self.cfg["fixer"] = dict(fields=[k for k, v in fvars.items() if v.get()], all_text=all_text.get(),
                                     seps=[sp for sp, v in svars if v.get()], mode=mode.get(), sep=sepv.get(),
                                     upgrade=upgrade.get(), dedupe=dedupe.get())
            self._save_cfg()
            d.destroy()
            self._fill_tree()
            self._changed(f"Tag-Fixer: {len(plan)} Feld(er) angepasst – noch nicht gespeichert.")
        ok_btn.configure(command=apply)
        d.bind("<Escape>", lambda e: d.destroy())
        refresh()
        self._center(d)

    def toggle_trivial(self):
        self.show_trivial = not self.show_trivial
        self.render()

    # ================================================================== Sicherungen
    def backup_dialog(self):
        th = self.th
        d = tk.Toplevel(self)
        d.withdraw()  # erst zentriert anzeigen
        d.title("Sicherungen – Tags wiederherstellen")
        d.configure(bg=th["bg"])
        d.transient(self)
        d._size = (1180, 640)
        d.minsize(900, 480)
        frm = ttk.Frame(d, padding=12)
        frm.pack(fill="both", expand=True)

        top = ttk.Frame(frm)
        top.pack(fill="x")
        enabled = tk.BooleanVar(value=self.cfg.get("backup_enabled", True))

        def folder():
            return self.cfg.get("backup_dir") or backup.default_dir()
        flabel = ttk.Label(frm, text="", style="Dim.TLabel")
        ttk.Checkbutton(top, text="Vor dem Speichern automatisch sichern (empfohlen)", variable=enabled,
                        command=lambda: (self.cfg.__setitem__("backup_enabled", enabled.get()), self._save_cfg())
                        ).pack(side="left")
        ttk.Button(top, text="Ordner öffnen", command=lambda: (os.makedirs(folder(), exist_ok=True),
                                                               self._open(folder()))).pack(side="right")

        def change_folder():
            p = filedialog.askdirectory(initialdir=folder(), title="Sicherungsordner wählen")
            if p:
                self.cfg["backup_dir"] = os.path.normpath(p)
                self._save_cfg()
                load_list()
        ttk.Button(top, text="Ordner ändern …", command=change_folder).pack(side="right", padx=6)
        flabel.pack(fill="x", pady=(6, 8))

        panes = ttk.PanedWindow(frm, orient="horizontal")
        panes.pack(fill="both", expand=True)
        lf = ttk.Frame(panes)
        rf = ttk.Frame(panes)
        panes.add(lf, weight=2)
        panes.add(rf, weight=3)
        bl = ttk.Treeview(lf, columns=("date", "label", "n", "size"), show="headings", selectmode="browse")
        for c, t, w in (("date", "Datum", 150), ("label", "Anlass", 220), ("n", "Dateien", 70), ("size", "Größe", 80)):
            bl.heading(c, text=t, anchor="w")
            bl.column(c, width=w, anchor="w", stretch=c == "label")
        bl.pack(fill="both", expand=True)
        fl = ttk.Treeview(rf, columns=("file", "state", "dir"), show="headings", selectmode="extended")
        for c, t, w in (("file", "Datei", 300), ("state", "Status", 230), ("dir", "Ordner", 220)):
            fl.heading(c, text=t, anchor="w")
            fl.column(c, width=w, anchor="w", stretch=c != "state")
        ys = ttk.Scrollbar(rf, orient="vertical", command=fl.yview)
        fl.configure(yscrollcommand=ys.set)
        fl.pack(side="left", fill="both", expand=True)
        ys.pack(side="left", fill="y")
        fl.tag_configure("ok", foreground=th["g_save"])
        fl.tag_configure("same", foreground=th["dim"])
        fl.tag_configure("missing", foreground=th["g_warn"])
        fl.tag_configure("audio", foreground=th["g_copy"])

        bf = ttk.Frame(frm)
        bf.pack(fill="x", pady=(10, 0))
        info = ttk.Label(bf, text="", style="Dim.TLabel")
        info.pack(side="left")
        ttk.Button(bf, text="Schließen", command=d.destroy).pack(side="right")
        b_all = ttk.Button(bf, text="Alle wiederherstellen")
        b_all.pack(side="right", padx=6)
        b_sel = ttk.Button(bf, text="Markierte wiederherstellen")
        b_sel.pack(side="right")
        b_del = ttk.Button(bf, text="Sicherung löschen …")
        b_del.pack(side="right", padx=(0, 18))

        st = {"backups": [], "cur": None, "status": {}, "job": 0}

        def load_list():
            bl.delete(*bl.get_children())
            fl.delete(*fl.get_children())
            st["backups"] = backup.list_backups(folder())
            for i, b in enumerate(st["backups"]):
                bl.insert("", "end", iid=str(i), values=(
                    time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(b["created"])), b["label"], b["count"],
                    f"{b['bytes'] / 1024:.0f} KB" if b["bytes"] < 1024 * 1024 else f"{b['bytes'] / 1048576:.1f} MB"))
            total = sum(b["bytes"] for b in st["backups"])
            flabel.configure(text=f"Ordner: {folder()}   ·   {len(st['backups'])} Sicherung(en), "
                                  f"{total / 1048576:.1f} MB   ·   Es wird nie automatisch etwas gelöscht.")
            if st["backups"]:
                bl.selection_set("0")

        def on_backup(_e=None):
            sel = bl.selection()
            fl.delete(*fl.get_children())
            if not sel:
                st["cur"] = None
                return
            b = st["backups"][int(sel[0])]
            st["cur"] = b
            st["job"] += 1
            job = st["job"]
            for e in b["files"]:
                fl.insert("", "end", iid=str(e["id"]), values=(e["name"], "prüfe …", os.path.dirname(e["path"])))
            info.configure(text=f"{b['count']} Datei(en) in {b['name']}")
            q2: queue.Queue = queue.Queue()

            def check():
                for e in b["files"]:
                    if job != st["job"]:
                        return
                    q2.put((e["id"], *backup.check_entry(e)))
                q2.put(None)
            threading.Thread(target=check, daemon=True).start()

            def poll():
                if job != st["job"] or not d.winfo_exists():
                    return
                try:
                    while True:
                        m = q2.get_nowait()
                        if m is None:
                            return
                        i, code, txt = m
                        if fl.exists(str(i)):
                            fl.set(str(i), "state", txt)
                            fl.item(str(i), tags=(code,))
                except queue.Empty:
                    pass
                d.after(80, poll)
            d.after(80, poll)

        bl.bind("<<TreeviewSelect>>", on_backup)

        def do_restore(ids):
            b = st["cur"]
            if not b:
                return
            entries = [e for e in b["files"] if ids is None or e["id"] in ids]
            if not entries:
                return
            paths = {os.path.normcase(os.path.abspath(e["path"])) for e in entries}
            loaded = [f for p in self.pairs for f in p if f and os.path.normcase(os.path.abspath(f.path)) in paths]
            dirty = [f for f in loaded if f.is_modified()]
            msg = (f"{len(entries)} Datei(en) auf den Stand vom "
                   f"{time.strftime('%d.%m.%Y %H:%M:%S', time.localtime(b['created']))} zurücksetzen?\n\n"
                   "Der aktuelle Zustand wird vorher selbst gesichert – das lässt sich also wieder rückgängig machen.")
            if dirty:
                msg += f"\n\nAchtung: {len(dirty)} dieser Datei(en) haben ungespeicherte Änderungen im Programm, die dabei verworfen werden."
            if not messagebox.askyesno(APP, msg, parent=d):
                return
            force = False
            audio = [e for e in entries if st["status"].get(e["id"]) == "audio" or fl.item(str(e["id"]), "tags") == ("audio",)]
            if audio:
                force = messagebox.askyesno(APP, f"Bei {len(audio)} Datei(en) haben sich die Audiodaten verändert "
                                                 "(evtl. eine andere Datei mit gleichem Namen).\n\n"
                                                 "Trotzdem die alten Tags dort einsetzen?", parent=d, default="no")
            cancel = threading.Event()
            qq: queue.Queue = queue.Queue()
            done = tk.BooleanVar(value=False)
            res = {}

            def worker():
                try:
                    r = backup.restore(b["path"], [e["id"] for e in entries], folder(), force,
                                       on_progress=lambda i, n, p: qq.put(("progress", i, n, p)), cancel=cancel)
                    res["r"] = r
                except Exception as ex:  # noqa: BLE001
                    res["err"] = str(ex)
                qq.put(("end",))
            self.loading = True
            dlg = ProgressDialog(self, cancel, delay_ms=250, title="Wiederherstellen", first="Sichere aktuellen Stand …",
                                 total_fmt="Stelle {n} Datei(en) wieder her …", count_fmt="{n} Datei(en)")
            qq.put(("total", len(entries)))
            threading.Thread(target=worker, daemon=True).start()

            def poll():
                try:
                    while True:
                        m = qq.get_nowait()
                        if m[0] == "end":
                            done.set(True)
                            return
                        dlg.update_state(m)
                except queue.Empty:
                    pass
                self.after(50, poll)
            self.after(50, poll)
            self.wait_variable(done)
            dlg.close()
            self.loading = False
            if "err" in res:
                messagebox.showerror(APP, f"Wiederherstellen fehlgeschlagen:\n{res['err']}", parent=d)
                return
            r = res["r"]
            ok = [p for p, code, _ in r if code == "restored"]
            okset = {os.path.normcase(os.path.abspath(p)) for p in ok}
            for f in loaded:
                if os.path.normcase(os.path.abspath(f.path)) in okset:
                    f.load()
            if ok:
                self.undo.clear()
                self._undo_buttons()
            self._fill_tree()
            self.render()
            skipped = [(p, t) for p, code, t in r if code != "restored"]
            text = f"{len(ok)} Datei(en) wiederhergestellt."
            if skipped:
                text += f"\n\n{len(skipped)} übersprungen:\n" + "\n".join(
                    f"• {os.path.basename(p)} – {t}" for p, t in skipped[:15])
            self._status("⟲", f"{len(ok)} Datei(en) aus Sicherung wiederhergestellt.", "g_save")
            messagebox.showinfo(APP, text, parent=d)
            load_list()

        def delete_backup():
            b = st["cur"]
            if not b:
                return
            if messagebox.askyesno(APP, f"Sicherung „{b['name']}“ ({b['count']} Datei(en)) endgültig löschen?\n\n"
                                        "Die MP3-Dateien selbst bleiben unverändert.", parent=d, default="no"):
                try:
                    os.remove(b["path"])
                except OSError as ex:
                    messagebox.showerror(APP, str(ex), parent=d)
                load_list()

        b_sel.configure(command=lambda: do_restore([int(i) for i in fl.selection()]))
        b_all.configure(command=lambda: do_restore(None))
        b_del.configure(command=delete_backup)
        d.bind("<Escape>", lambda e: d.destroy())
        load_list()
        self._center(d)

    # ================================================================== Rückgängig / Wiederholen
    def _commit_undo(self):
        self.undo.commit()
        self._undo_buttons()

    def _undo_buttons(self):
        if not hasattr(self, "b_undo"):
            return
        self.b_undo.set_enabled(bool(self.undo.undo))
        self.b_redo.set_enabled(bool(self.undo.redo))

    def _undo_key(self, e, redo=False):
        if self.editor or self.loading:
            return None  # im Eingabefeld gilt das normale Verhalten
        try:
            if e.widget.winfo_toplevel() is not self:
                return None
        except (AttributeError, tk.TclError):
            pass
        (self.do_redo if redo else self.do_undo)()
        return "break"

    def do_undo(self):
        self._close_editor(commit=True)
        e = self.undo.do_undo()
        if e:
            self._after_undo(f"Rückgängig: {e['label']}", "↶")

    def do_redo(self):
        self._close_editor(commit=True)
        e = self.undo.do_redo()
        if e:
            self._after_undo(f"Wiederholt: {e['label']}", "↷")

    def _after_undo(self, msg, glyph):
        self._fill_tree()
        self.render()
        self._undo_buttons()
        n_u, n_r = len(self.undo.undo), len(self.undo.redo)
        self._status(glyph, f"{msg}   ({n_u} rückgängig · {n_r} wiederholbar)", "g_cmp")

    # ================================================================== Speichern
    def _modified_files(self):
        return core.modified_files(self.pairs)

    def save_all(self):
        self._close_editor(commit=True)
        files = self._modified_files()
        if not files:
            self._status("✔", "Keine ungespeicherten Änderungen.", "g_save")
            return True
        names = "\n".join("• " + os.path.basename(f.path) for f in files[:10]) + ("\n…" if len(files) > 10 else "")
        if not messagebox.askyesno(APP, f"{len(files)} Datei(en) speichern?\n\n{names}"):
            return False
        return self._save(files)

    def _save(self, files):
        """Speichert im Hintergrund mit Fortschritt. Vorher werden die bisherigen Tags gesichert."""
        self._close_editor(commit=True)
        backup_on = self.cfg.get("backup_enabled", True)
        folder = self.cfg.get("backup_dir") or backup.default_dir()
        cancel = threading.Event()
        q: queue.Queue = queue.Queue()
        done = tk.BooleanVar(value=False)
        result = {}

        def worker():
            try:
                res = core.save_files(files, backup_on, folder, cancel, q.put)
                q.put(("done", res["saved"], res["errors"], res["backup"], res["cancelled"]))
            except core.BackupUnavailable as ex:
                q.put(("fatal", str(ex)))
            except Exception as ex:  # noqa: BLE001
                q.put(("fatal", f"Unerwarteter Fehler beim Speichern:\n{ex}"))

        self.loading = True
        dlg = ProgressDialog(self, cancel, delay_ms=250, title="Speichern", first="Sichere und speichere …",
                             total_fmt="Speichere {n} Datei(en) …", count_fmt="{n} Datei(en)",
                             hint=("Die bisherigen Tags werden vorher gesichert. " if backup_on else "")
                             + "Abbrechen stoppt nach der aktuellen Datei.")
        threading.Thread(target=worker, daemon=True).start()

        def poll():
            try:
                while True:
                    m = q.get_nowait()
                    if m[0] in ("done", "fatal"):
                        result["msg"] = m
                        done.set(True)
                        return
                    dlg.update_state(m)
            except queue.Empty:
                pass
            self.after(50, poll)
        self.after(50, poll)
        self.wait_variable(done)
        dlg.close()
        self.loading = False
        m = result["msg"]
        if m[0] == "fatal":
            messagebox.showerror(APP, m[1])
            return False
        _, saved, errors, bpath, cancelled = m
        self._fill_tree()
        self.render()
        bname = f"  ·  Sicherung: {os.path.basename(bpath)}" if bpath else ""
        if errors:
            self._status("⚠", f"{saved} gespeichert, {len(errors)} Fehler.{bname}", "g_warn")
            messagebox.showerror(APP, "Fehler beim Speichern:\n\n" + "\n".join(errors[:30]))
        elif cancelled:
            self._status("✕", f"Abgebrochen – {saved} von {len(files)} Datei(en) gespeichert.{bname}", "g_warn")
        else:
            self._status("✔", f"{saved} Datei(en) gespeichert.{bname}", "g_save")
        return not errors and not cancelled

    def _confirm_discard(self):
        files = self._modified_files()
        if not files:
            return True
        ans = messagebox.askyesnocancel(APP, f"{len(files)} Datei(en) haben ungespeicherte Änderungen.\n\n"
                                             "Jetzt speichern?  (Nein = verwerfen)")
        if ans is None:
            return False
        return self._save(files) if ans else True

    # ================================================================== Status
    def _status(self, glyph, text, tok="fg"):
        self.st_glyph.configure(text=glyph, fg=self.th.get(tok, self.th["fg"]))
        self.st_text.configure(text=text)

    def _update_status(self):
        n = len(self._modified_files())
        self.st_mod.configure(text=f"● {n} Datei(en) ungespeichert" if n else "")
        self.b_save.t.configure(text=f"Speichern ({n})" if n else "Speichern")
        l, r = self._files()
        if l is None and r is None:
            self._status("", "Bereit.", "dim")
            return
        if l is None or r is None:
            self._status("◧", "Nur eine Seite vorhanden – Tags können bearbeitet werden.", "dim")
            return
        st = list(getattr(self, "states", {}).values())
        imp, triv, only = st.count("diff"), st.count("triv"), st.count("only")
        if imp or only:
            self._status("⚠", f"Wichtige Unterschiede: {imp}   ·   nur eine Seite: {only}   ·   unwichtig: {triv}", "g_warn")
        elif triv:
            self._status("≈", f"Nur unwichtige Unterschiede ({triv})", "g_copy")
        else:
            self._status("✔", "Identisch", "g_save")

    def on_close(self):
        if self.loading:
            return
        self._close_editor(commit=True)
        if self._confirm_discard():
            self._save_cfg()
            self.destroy()


def main():
    _dpi_aware()
    app = App()
    if len(sys.argv) >= 2:
        app.left_path.set(sys.argv[1])
        app.right_path.set(sys.argv[2] if len(sys.argv) >= 3 else "")
        app.after(100, lambda: app.compare(ask=False))
    app.mainloop()


if __name__ == "__main__":
    main()
