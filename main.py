#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
View URL — visor de código fuente de cualquier página web
=========================================================
Ejecuta en IDLE (Python 3.14):  File > Open… > view_url.py  →  F5

Sólo usa la biblioteca estándar:
  tkinter, urllib, html.parser, threading, re, webbrowser, platform
"""

import platform
import re
import threading
import webbrowser
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.font import Font


# ═══════════════════════════════════════════════════════════════════
#  Configuración
# ═══════════════════════════════════════════════════════════════════
TIMEOUT      = 20          # segundos por petición
USER_AGENT   = "Mozilla/5.0 (compatible; ViewURL/1.0)"
MAX_ASSETS   = 15          # máx. CSS/JS externos que se descargan
MAX_HL       = 500_000     # a partir de aquí no se colorea (rendimiento)

COLORS = {
    "bg":     "#0b0f14",
    "panel":  "#0d1117",
    "border": "#1e2937",
    "text":   "#c9d1d9",
    "muted":  "#8b949e",
    "accent": "#58a6ff",
    "ok":     "#3fb950",
    "err":    "#f85149",
    "warn":   "#d29922",
    "com":    "#6b7a8d",
    "tag":    "#7ee787",
    "attr":   "#79c0ff",
    "str":    "#a5d6ff",
    "kw":     "#ff7b72",
    "num":    "#f0883e",
    "punc":   "#7d8590",
    "line":   "#39465a",
    "gutter": "#0a0e13",
}


# ═══════════════════════════════════════════════════════════════════
#  1. Analizador HTML (basado en html.parser)
# ═══════════════════════════════════════════════════════════════════
class PageParser(HTMLParser):
    """Extrae título, CSS, JS, imágenes, enlaces y metadatos del HTML."""

    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url

        self.title = ""
        self._in_title = False
        self._title_buf = []

        self.css_links   = []      # [{'href', 'media'}]
        self.inline_styles = []    # [str]
        self._in_style = False
        self._style_buf = []

        self.js_links      = []    # [{'src', 'type'}]
        self.inline_scripts = []   # [str]
        self._in_script = False
        self._script_buf = []

        self.images = []           # [{'src', 'alt'}]
        self.links  = []           # [{'href', 'text'}]
        self._seen_links = set()
        self._in_a = False
        self._a_buf = []
        self._a_href = None

        self.metas = []            # [{'name', 'content'}]

    # ---------- etiquetas de apertura ----------
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        a = {k.lower(): (v or "") for k, v in attrs}

        if tag == "base" and a.get("href"):
            self.base_url = urljoin(self.base_url, a["href"])
            return

        if tag == "title":
            self._in_title = True
            self._title_buf = []

        elif tag == "link":
            rel = a.get("rel", "").lower()
            if "stylesheet" in rel and a.get("href"):
                self.css_links.append({
                    "href": urljoin(self.base_url, a["href"]),
                    "media": a.get("media", ""),
                })

        elif tag == "style":
            self._in_style = True
            self._style_buf = []

        elif tag == "script":
            src = a.get("src")
            stype = (a.get("type") or "").lower()
            is_js = (not stype or "javascript" in stype
                     or "ecmascript" in stype or stype == "module")
            if src:
                self.js_links.append({
                    "src": urljoin(self.base_url, src),
                    "type": stype,
                })
            elif is_js:
                self._in_script = True
                self._script_buf = []

        elif tag == "img" and a.get("src"):
            self.images.append({
                "src": urljoin(self.base_url, a["src"]),
                "alt": a.get("alt", ""),
            })

        elif tag == "a" and a.get("href"):
            self._in_a = True
            self._a_buf = []
            self._a_href = urljoin(self.base_url, a["href"])

        elif tag == "meta":
            name = a.get("name") or a.get("property") or ""
            content = (a.get("content") or "")[:400]
            if name and content:
                self.metas.append({"name": name, "content": content})

    # ---------- etiquetas de cierre ----------
    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title" and self._in_title:
            self._in_title = False
            self.title = "".join(self._title_buf).strip()

        elif tag == "style" and self._in_style:
            self._in_style = False
            css = "".join(self._style_buf).strip()
            if css:
                self.inline_styles.append(css)

        elif tag == "script" and self._in_script:
            self._in_script = False
            js = "".join(self._script_buf).strip()
            if js:
                self.inline_scripts.append(js)

        elif tag == "a" and self._in_a:
            self._in_a = False
            text = "".join(self._a_buf).strip()[:70]
            if self._a_href and self._a_href not in self._seen_links:
                self._seen_links.add(self._a_href)
                self.links.append({"href": self._a_href, "text": text})

    # ---------- texto ----------
    def handle_data(self, data):
        if self._in_title:   self._title_buf.append(data)
        if self._in_style:   self._style_buf.append(data)
        if self._in_script:  self._script_buf.append(data)
        if self._in_a:       self._a_buf.append(data)


# ═══════════════════════════════════════════════════════════════════
#  2. Expresiones regulares para resaltado
# ═══════════════════════════════════════════════════════════════════
RE_HTML = re.compile(
    r'(<!--[\s\S]*?-->)|(<!DOCTYPE[^>]*>)|(<\/?[a-zA-Z][^>]*>)',
    re.IGNORECASE,
)
RE_ATTR = re.compile(
    r'([a-zA-Z_:@][\w:.\-]*)(\s*=\s*)("[^"]*"|\'[^\']*\'|[^\s"\'>]+)'
)
RE_CSS = re.compile(
    r'(\/\*[\s\S]*?\*\/)'                                  # 1 comentario
    r'|("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'           # 2 cadena
    r'|(@[\w-]+)'                                          # 3 arroba
    r'|(#[0-9a-fA-F]{3,8}\b)'                              # 4 color hex
    r'|([\w-]+(?=\s*:))'                                   # 5 propiedad
    r'|(\d*\.?\d+(?:px|em|rem|%|vh|vw|vmin|vmax|s|ms|deg|fr|pt|ch|ex|turn)?)'  # 6 número
)
RE_JS = re.compile(
    r'(\/\/[^\n]*|\/\*[\s\S]*?\*\/)'                       # 1 comentario
    r'|("(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|`(?:[^`\\]|\\.)*`)'  # 2 cadena
    r'|(\b(?:const|let|var|function|return|if|else|for|while|do|switch|case|'
    r'break|continue|new|class|extends|super|this|typeof|instanceof|delete|'
    r'in|of|try|catch|finally|throw|async|await|yield|import|export|from|'
    r'default|null|undefined|true|false|void|static)\b)'   # 3 palabra clave
    r'|(\b\d+(?:\.\d+)?\b)'                                # 4 número
)


# ═══════════════════════════════════════════════════════════════════
#  3. Aplicación
# ═══════════════════════════════════════════════════════════════════
class ViewURLApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("View URL · visor de código fuente")
        root.geometry("1180x760")
        root.minsize(800, 520)
        root.configure(bg=COLORS["bg"])

        # ----- fuentes -----
        system = platform.system()
        mono_family = {"Windows": "Consolas",
                       "Darwin":  "Menlo"}.get(system, "DejaVu Sans Mono")
        ui_family   = {"Windows": "Segoe UI",
                       "Darwin":  "Helvetica Neue"}.get(system, "Helvetica")

        self.mono      = Font(family=mono_family, size=10)
        self.mono_bold = Font(family=mono_family, size=10, weight="bold")
        self.mono_ital = Font(family=mono_family, size=10, slant="italic")
        self.ui        = (ui_family, 9)
        self.ui_bold   = (ui_family, 10, "bold")

        # ----- estado -----
        self.state = {
            "url":     "",
            "html":    "",
            "parser":  None,
            "assets":  {},      # url → {'text': str} | {'error': str}
            "tab":     "html",
            "busy":    False,
        }

        self.code_widgets = {}   # key -> (text, gutter)
        self.text_widgets = {}   # key -> text  (recursos, info)

        self._build_ui()
        self._seed_placeholders()

    # ------------------------------------------------------------------
    #  Construcción de la interfaz
    # ------------------------------------------------------------------
    def _build_ui(self):
        # ── cabecera ──
        header = tk.Frame(self.root, bg=COLORS["bg"])
        header.pack(fill="x", padx=16, pady=(12, 0))

        tk.Label(header, text="</>", bg="#1f6feb", fg="white",
                 font=self.mono_bold, padx=12, pady=6).pack(side="left")

        titles = tk.Frame(header, bg=COLORS["bg"])
        titles.pack(side="left", padx=12)
        tk.Label(titles, text="View URL", bg=COLORS["bg"], fg=COLORS["text"],
                 font=(self.ui[0], 15, "bold")).pack(anchor="w")
        tk.Label(titles, text="Mira todo el código de cualquier página web",
                 bg=COLORS["bg"], fg=COLORS["muted"],
                 font=self.ui).pack(anchor="w")

        # ── barra de URL ──
        bar = tk.Frame(self.root, bg=COLORS["bg"])
        bar.pack(fill="x", padx=16, pady=(12, 4))

        self.url_var = tk.StringVar()
        entry = tk.Entry(bar, textvariable=self.url_var,
                         bg=COLORS["gutter"], fg=COLORS["text"],
                         insertbackground=COLORS["text"],
                         font=self.mono, relief="flat", bd=8,
                         highlightthickness=1,
                         highlightbackground=COLORS["border"],
                         highlightcolor=COLORS["accent"])
        entry.pack(side="left", fill="x", expand=True, ipady=4)
        entry.bind("<Return>", lambda e: self.on_go())
        entry.focus_set()

        self.go_btn = tk.Button(bar, text="Ver código", command=self.on_go,
                                bg="#1f6feb", fg="white",
                                activebackground="#3b82f6",
                                activeforeground="white",
                                disabledforeground="#9fb4cc",
                                relief="flat", bd=0, padx=20, pady=6,
                                font=self.ui_bold, cursor="hand2")
        self.go_btn.pack(side="left", padx=(8, 0))

        # ── barra de estado ──
        sframe = tk.Frame(self.root, bg=COLORS["bg"])
        sframe.pack(fill="x", padx=18, pady=(0, 8))
        self.status_dot = tk.Label(sframe, text="●", bg=COLORS["bg"],
                                   fg="#374151", font=(self.ui[0], 10))
        self.status_dot.pack(side="left")
        self.status_lbl = tk.Label(sframe,
                                   text="Escribe una URL y pulsa «Ver código».",
                                   bg=COLORS["bg"], fg=COLORS["muted"],
                                   font=self.ui)
        self.status_lbl.pack(side="left", padx=6)

        # ── pestañas ──
        self.tabs_bar = tk.Frame(self.root, bg=COLORS["bg"])
        self.tabs_bar.pack(fill="x", padx=16)

        self.tab_buttons = {}
        for key, label in (("html", "HTML"), ("css", "CSS"),
                           ("js", "JavaScript"), ("recursos", "Recursos"),
                           ("info", "Info")):
            b = tk.Button(self.tabs_bar, text=label,
                          command=lambda k=key: self.switch_tab(k),
                          bg=COLORS["bg"], fg=COLORS["muted"],
                          activebackground="#111823",
                          activeforeground=COLORS["text"],
                          relief="flat", bd=0, padx=12, pady=6,
                          font=self.ui, cursor="hand2")
            b.pack(side="left")
            self.tab_buttons[key] = b

        # botones de acción a la derecha
        self._mini_btn(self.tabs_bar, "Abrir web ↗",
                       self.open_in_browser).pack(side="right", padx=2)
        self.save_btn = self._mini_btn(self.tabs_bar, "Guardar…",
                                       self.save_current)
        self.save_btn.pack(side="right", padx=2)
        self.copy_btn = self._mini_btn(self.tabs_bar, "Copiar",
                                       self.copy_current)
        self.copy_btn.pack(side="right", padx=2)

        # separador
        tk.Frame(self.root, bg=COLORS["border"], height=1).pack(
            fill="x", padx=0, pady=(6, 0))

        # ── contenedor de vistas ──
        self.viewer = tk.Frame(self.root, bg=COLORS["panel"])
        self.viewer.pack(fill="both", expand=True)

        self.frames = {}
        for key in ("html", "css", "js", "recursos", "info"):
            f = tk.Frame(self.viewer, bg=COLORS["panel"])
            self.frames[key] = f

        for key in ("html", "css", "js"):
            self._build_code_tab(self.frames[key], key)
        for key in ("recursos", "info"):
            self._build_text_tab(self.frames[key], key)

        self.switch_tab("html")

    # ------------------------------------------------------------------
    def _mini_btn(self, parent, text, command):
        return tk.Button(parent, text=text, command=command,
                         bg=COLORS["bg"], fg=COLORS["muted"],
                         activebackground="#111823",
                         activeforeground=COLORS["text"],
                         relief="flat", bd=0, padx=10, pady=5,
                         font=self.ui, cursor="hand2")

    # ------------------------------------------------------------------
    def _build_code_tab(self, parent, key):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)

        gutter = tk.Text(parent, width=5, bg=COLORS["gutter"],
                         fg=COLORS["line"], font=self.mono,
                         bd=0, highlightthickness=0, state="disabled",
                         wrap="none", padx=8, pady=10, cursor="arrow",
                         takefocus=0)
        gutter.grid(row=0, column=0, sticky="ns")

        text = tk.Text(parent, bg=COLORS["panel"], fg=COLORS["text"],
                       font=self.mono, bd=0, highlightthickness=0,
                       wrap="none", padx=10, pady=10,
                       insertbackground=COLORS["text"],
                       selectbackground="#1f6feb",
                       selectforeground="white",
                       state="disabled")
        text.grid(row=0, column=1, sticky="nsew")

        vsb = tk.Scrollbar(parent, orient="vertical",
                           bg=COLORS["panel"], troughcolor=COLORS["bg"],
                           activebackground="#31465f", bd=0,
                           highlightthickness=0, width=12)
        vsb.grid(row=0, column=2, sticky="ns")

        hsb = tk.Scrollbar(parent, orient="horizontal",
                           bg=COLORS["panel"], troughcolor=COLORS["bg"],
                           activebackground="#31465f", bd=0,
                           highlightthickness=0, width=12)
        hsb.grid(row=1, column=1, sticky="ew")

        def on_vsb(*args):
            text.yview(*args)
            gutter.yview(*args)

        vsb.config(command=on_vsb)

        def on_yscroll(first, last):
            vsb.set(first, last)
            gutter.yview_moveto(first)

        text.config(yscrollcommand=on_yscroll, xscrollcommand=hsb.set)
        hsb.config(command=text.xview)

        # rueda del ratón con desplazamiento
        def on_wheel(e):
            delta = -1 if e.delta > 0 else 1
            text.yview_scroll(delta * 3, "units")
            gutter.yview_scroll(delta * 3, "units")
            return "break"

        for w in (text, gutter):
            w.bind("<MouseWheel>", on_wheel)
            w.bind("<Button-4>", lambda e: (text.yview_scroll(-3, "units"),
                                            gutter.yview_scroll(-3, "units")))
            w.bind("<Button-5>", lambda e: (text.yview_scroll(3, "units"),
                                            gutter.yview_scroll(3, "units")))

        # etiquetas de color
        text.tag_configure("com",  foreground=COLORS["com"], font=self.mono_ital)
        text.tag_configure("tag",  foreground=COLORS["tag"])
        text.tag_configure("attr", foreground=COLORS["attr"])
        text.tag_configure("str",  foreground=COLORS["str"])
        text.tag_configure("punc", foreground=COLORS["punc"])
        text.tag_configure("kw",   foreground=COLORS["kw"])
        text.tag_configure("num",  foreground=COLORS["num"])
        text.tag_configure("prop", foreground=COLORS["attr"])
        text.tag_configure("at",   foreground=COLORS["kw"])
        text.tag_configure("doc",  foreground=COLORS["muted"])

        self.code_widgets[key] = (text, gutter)

    # ------------------------------------------------------------------
    def _build_text_tab(self, parent, key):
        text = tk.Text(parent, bg=COLORS["panel"], fg=COLORS["text"],
                       font=self.mono, bd=0, highlightthickness=0,
                       wrap="word", padx=18, pady=14,
                       insertbackground=COLORS["text"],
                       selectbackground="#1f6feb",
                       selectforeground="white",
                       state="disabled", cursor="arrow")
        text.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(parent, orient="vertical",
                          bg=COLORS["panel"], troughcolor=COLORS["bg"],
                          activebackground="#31465f", bd=0,
                          highlightthickness=0, width=12)
        sb.pack(side="right", fill="y")
        text.config(yscrollcommand=sb.set)
        sb.config(command=text.yview)

        text.tag_configure("h",     foreground=COLORS["accent"],
                           font=self.mono_bold)
        text.tag_configure("muted", foreground=COLORS["muted"])
        text.tag_configure("link",  foreground=COLORS["accent"],
                           underline=True)
        text.tag_configure("key",   foreground=COLORS["muted"])
        text.tag_configure("val",   foreground=COLORS["text"])
        text.tag_configure("ok",    foreground=COLORS["ok"])
        text.tag_configure("err",   foreground=COLORS["err"])

        self.text_widgets[key] = text

    # ------------------------------------------------------------------
    def _seed_placeholders(self):
        for key in ("html", "css", "js"):
            self._set_code(key, "", "html")
        for key in ("recursos", "info"):
            t = self.text_widgets[key]
            t.configure(state="normal")
            t.delete("1.0", "end")
            t.insert("end",
                     "Todavía no se ha cargado ninguna página.\n\n"
                     "Escribe una URL arriba y pulsa «Ver código».",
                     "muted")
            t.configure(state="disabled")

    # ------------------------------------------------------------------
    #  Cambio de pestaña
    # ------------------------------------------------------------------
    def switch_tab(self, key):
        self.state["tab"] = key
        for k, frame in self.frames.items():
            if k == key:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

        for k, btn in self.tab_buttons.items():
            if k == key:
                btn.configure(fg=COLORS["text"], bg="#0f1520")
            else:
                btn.configure(fg=COLORS["muted"], bg=COLORS["bg"])

        is_code = key in ("html", "css", "js")
        state = "normal" if is_code else "disabled"
        self.copy_btn.configure(state=state)
        self.save_btn.configure(state=state)

    # ------------------------------------------------------------------
    #  Estado
    # ------------------------------------------------------------------
    def set_status(self, text, kind=""):
        colors = {"": "#374151", "ok": COLORS["ok"],
                  "err": COLORS["err"], "load": COLORS["warn"]}
        self.status_dot.configure(fg=colors.get(kind, "#374151"))
        self.status_lbl.configure(text=text)

    # ══════════════════════════════════════════════════════════════════
    #  Flujo principal: descargar + analizar
    # ══════════════════════════════════════════════════════════════════
    def on_go(self):
        if self.state["busy"]:
            return
        url = self.url_var.get().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            self.url_var.set(url)
        self.load(url)

    # ------------------------------------------------------------------
    def load(self, url):
        self.state.update(busy=True, url=url, html="",
                          parser=None, assets={})
        self.go_btn.configure(state="disabled", text="Cargando…")
        self.set_status("Conectando con " + url + " …", "load")

        # limpiar pestañas
        for key in ("html", "css", "js"):
            self._set_code(key, "", key if key != "html" else "html")
        for key in ("recursos", "info"):
            t = self.text_widgets[key]
            t.configure(state="normal")
            t.delete("1.0", "end")
            t.configure(state="disabled")

        threading.Thread(target=self._worker_fetch,
                         args=(url,), daemon=True).start()

    # ------------------------------------------------------------------
    @staticmethod
    def _download(url):
        req = Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
        })
        with urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            try:
                return raw.decode(charset, errors="replace")
            except LookupError:
                return raw.decode("utf-8", errors="replace")

    # ------------------------------------------------------------------
    def _worker_fetch(self, url):
        try:
            html = self._download(url)
            self.root.after(0, self._on_fetched, url, html)
        except HTTPError as e:
            self.root.after(0, self._on_error,
                            f"HTTP {e.code}: {e.reason}")
        except URLError as e:
            self.root.after(0, self._on_error,
                            f"Error de red: {e.reason}")
        except Exception as e:
            self.root.after(0, self._on_error,
                            f"{type(e).__name__}: {e}")

    # ------------------------------------------------------------------
    def _on_fetched(self, url, html):
        self.state["html"] = html
        try:
            parser = PageParser(url)
            parser.feed(html)
            parser.close()
            self.state["parser"] = parser
        except Exception as e:
            self.set_status(f"⚠ HTML descargado pero falló el análisis: {e}",
                            "err")

        self._set_code("html", html, "html")
        self._render_derived_tabs()
        self.set_status(
            f"✔ {len(html):,} caracteres descargados. "
            f"Cargando CSS/JS externos…", "ok")

        threading.Thread(target=self._worker_assets, daemon=True).start()

    # ------------------------------------------------------------------
    def _worker_assets(self):
        parser = self.state["parser"]
        if parser is None:
            self.root.after(0, self._on_assets_done)
            return

        urls = []
        for link in parser.css_links[:MAX_ASSETS]:
            urls.append(link["href"])
        for script in parser.js_links[:MAX_ASSETS]:
            urls.append(script["src"])
        urls = list(dict.fromkeys(urls))     # únicos, en orden

        total = len(urls)
        if total == 0:
            self.root.after(0, self._on_assets_done)
            return

        for i, u in enumerate(urls, 1):
            try:
                self.state["assets"][u] = {"text": self._download(u)}
            except Exception as e:
                self.state["assets"][u] = {
                    "error": f"{type(e).__name__}: {e}"
                }
            self.root.after(
                0, self.set_status,
                f"Cargando recursos externos… {i}/{total}", "load")

        self.root.after(0, self._on_assets_done)

    # ------------------------------------------------------------------
    def _on_assets_done(self):
        self.state["busy"] = False
        self.go_btn.configure(state="normal", text="Ver código")
        self._render_derived_tabs()

        parser = self.state["parser"]
        n_css = (len(parser.css_links) + len(parser.inline_styles)) if parser else 0
        n_js  = (len(parser.js_links)  + len(parser.inline_scripts)) if parser else 0
        self.set_status(
            f"✔ Listo · {len(self.state['html']):,} caracteres · "
            f"{n_css} CSS · {n_js} JS", "ok")

    # ------------------------------------------------------------------
    def _on_error(self, msg):
        self.state["busy"] = False
        self.go_btn.configure(state="normal", text="Ver código")
        self.set_status(f"✖ {msg}", "err")

    # ══════════════════════════════════════════════════════════════════
    #  Renderizado
    # ══════════════════════════════════════════════════════════════════
    def _render_derived_tabs(self):
        p = self.state["parser"]
        self._set_code("css", self._build_css(p), "css")
        self._set_code("js",  self._build_js(p),  "js")
        self._render_resources(p)
        self._render_info(p)

    # ------------------------------------------------------------------
    def _build_css(self, parser):
        if parser is None:
            return ""
        parts = []
        for i, css in enumerate(parser.inline_styles, 1):
            parts.append(f"/* ═════════ <style> en línea #{i} ═════════ */\n{css}")
        for link in parser.css_links:
            href = link["href"]
            head = f"/* ═════════ {href} ═════════ */"
            a = self.state["assets"].get(href)
            if a is None:
                parts.append(f"{head}\n   (no descargado)")
            elif "error" in a:
                parts.append(f"{head}\n   ERROR: {a['error']}")
            else:
                parts.append(f"{head}\n{a['text'].strip()}")
        return "\n\n\n".join(parts) or "/* No se encontró CSS en esta página. */"

    # ------------------------------------------------------------------
    def _build_js(self, parser):
        if parser is None:
            return ""
        parts = []
        for i, js in enumerate(parser.inline_scripts, 1):
            parts.append(f"/* ═════════ <script> en línea #{i} ═════════ */\n{js}")
        for link in parser.js_links:
            href = link["src"]
            head = f"/* ═════════ {href} ═════════ */"
            a = self.state["assets"].get(href)
            if a is None:
                parts.append(f"{head}\n   (no descargado)")
            elif "error" in a:
                parts.append(f"{head}\n   ERROR: {a['error']}")
            else:
                parts.append(f"{head}\n{a['text'].strip()}")
        return "\n\n\n".join(parts) or "/* No se encontró JavaScript en esta página. */"

    # ------------------------------------------------------------------
    def _render_resources(self, parser):
        t = self.text_widgets["recursos"]
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.tag_bind("link", "<Enter>",
                   lambda e: t.configure(cursor="hand2"))
        t.tag_bind("link", "<Leave>",
                   lambda e: t.configure(cursor="arrow"))

        if parser is None:
            t.insert("end", "Todavía no se ha cargado ninguna página.\n",
                     "muted")
            t.configure(state="disabled")
            return

        counter = [0]

        def add_link(url, extra=""):
            tag = f"lk_{counter[0]}"
            counter[0] += 1
            t.insert("end", url, (tag, "link"))
            t.tag_bind(tag, "<Button-1>",
                       lambda e, u=url: webbrowser.open(u))
            if extra:
                t.insert("end", "  " + extra, "muted")
            t.insert("end", "\n")

        def header(title, n):
            t.insert("end", f"\n{title}  ", "h")
            t.insert("end", f"({n})\n", "muted")

        def empty_line():
            t.insert("end", "  (ninguno)\n", "muted")

        # CSS externos
        header("Hojas de estilo externas", len(parser.css_links))
        if parser.css_links:
            for l in parser.css_links:
                t.insert("end", "  • ", "muted")
                add_link(l["href"],
                         f"[media={l['media']}]" if l["media"] else "")
        else:
            empty_line()

        # CSS en línea
        header("Estilos en línea", len(parser.inline_styles))
        if parser.inline_styles:
            for i, css in enumerate(parser.inline_styles, 1):
                preview = css.strip().replace("\n", " ")[:120]
                t.insert("end", f"  • <style> #{i}  ", "muted")
                t.insert("end", f"{preview}…\n", "val")
        else:
            empty_line()

        # JS externos
        header("Scripts externos", len(parser.js_links))
        if parser.js_links:
            for l in parser.js_links:
                t.insert("end", "  • ", "muted")
                add_link(l["src"],
                         f"[{l['type']}]" if l["type"] else "")
        else:
            empty_line()

        # JS en línea
        header("Scripts en línea", len(parser.inline_scripts))
        if parser.inline_scripts:
            for i, js in enumerate(parser.inline_scripts, 1):
                preview = js.strip().replace("\n", " ")[:120]
                t.insert("end", f"  • inline #{i}  ", "muted")
                t.insert("end", f"{preview}…\n", "val")
        else:
            empty_line()

        # Imágenes
        header("Imágenes", len(parser.images))
        if parser.images:
            for im in parser.images:
                t.insert("end", "  • ", "muted")
                add_link(im["src"],
                         f"[alt: {im['alt']}]" if im["alt"] else "")
        else:
            empty_line()

        # Enlaces
        header("Enlaces únicos", len(parser.links))
        if parser.links:
            for l in parser.links[:200]:
                t.insert("end", "  • ", "muted")
                add_link(l["href"],
                         f"«{l['text']}»" if l["text"] else "")
        else:
            empty_line()

        t.configure(state="disabled")

    # ------------------------------------------------------------------
    def _render_info(self, parser):
        t = self.text_widgets["info"]
        t.configure(state="normal")
        t.delete("1.0", "end")

        if parser is None:
            t.insert("end", "Todavía no se ha cargado ninguna página.\n",
                     "muted")
            t.configure(state="disabled")
            return

        url = self.state["url"]
        try:
            host = urlparse(url).hostname or url
        except Exception:
            host = url

        html = self.state["html"]
        rows = [
            ("URL",             url),
            ("Título",          parser.title or "(sin título)"),
            ("Tamaño HTML",     f"{len(html):,} caracteres"),
            ("Líneas de HTML",  f"{html.count(chr(10)) + 1:,}"),
            ("CSS externo",     str(len(parser.css_links))),
            ("CSS en línea",    str(len(parser.inline_styles))),
            ("JS externo",      str(len(parser.js_links))),
            ("JS en línea",     str(len(parser.inline_scripts))),
            ("Imágenes",        str(len(parser.images))),
            ("Enlaces únicos",  str(len(parser.links))),
            ("Etiquetas meta",  str(len(parser.metas))),
        ]

        t.insert("end", f"Resumen de {host}\n", "h")
        t.insert("end", "\n")
        for k, v in rows:
            t.insert("end", f"  {k:<20}", "key")
            t.insert("end", f"{v}\n", "val")

        if parser.metas:
            t.insert("end", "\nMetadatos\n", "h")
            t.insert("end", "\n")
            for m in parser.metas:
                t.insert("end", f"  {m['name']:<20}", "key")
                t.insert("end", f"{m['content']}\n", "val")

        t.configure(state="disabled")

    # ══════════════════════════════════════════════════════════════════
    #  Escritura de código con resaltado
    # ══════════════════════════════════════════════════════════════════
    def _set_code(self, key, code, lang):
        text, gutter = self.code_widgets[key]

        text.configure(state="normal")
        text.delete("1.0", "end")
        if code:
            text.insert("1.0", code)

        if code and len(code) <= MAX_HL:
            if   lang == "html": self._hl_html(text, code)
            elif lang == "css":  self._hl_css(text, code)
            elif lang == "js":   self._hl_js(text, code)

        text.configure(state="disabled")

        # números de línea
        n = code.count("\n") + 1 if code else 1
        gutter.configure(state="normal")
        gutter.delete("1.0", "end")
        gutter.insert("1.0", "\n".join(str(i) for i in range(1, n + 1)))
        gutter.configure(state="disabled")

        # sincroniza scroll inicial
        text.yview_moveto(0)
        gutter.yview_moveto(0)

    # ------------------------------------------------------------------
    @staticmethod
    def _tag(text, start, end, tag):
        text.tag_add(tag, f"1.0+{start}c", f"1.0+{end}c")

    # ------------------------------------------------------------------
    def _hl_html(self, text, code):
        for m in RE_HTML.finditer(code):
            s, e = m.start(), m.end()
            if m.group(1) or m.group(2):
                self._tag(text, s, e, "com")
                continue

            frag = m.group(3)
            self._tag(text, s, e, "punc")

            tm = re.match(r"<\/?([a-zA-Z][\w:.\-]*)", frag)
            if not tm:
                continue
            self._tag(text, s + tm.start(1), s + tm.end(1), "tag")

            attrs_off = s + tm.end()
            attrs_part = frag[tm.end():]
            for am in RE_ATTR.finditer(attrs_part):
                self._tag(text,
                          attrs_off + am.start(1),
                          attrs_off + am.end(1), "attr")
                self._tag(text,
                          attrs_off + am.start(3),
                          attrs_off + am.end(3), "str")

    # ------------------------------------------------------------------
    def _hl_css(self, text, code):
        for m in RE_CSS.finditer(code):
            s, e = m.start(), m.end()
            if   m.group(1): self._tag(text, s, e, "com")
            elif m.group(2): self._tag(text, s, e, "str")
            elif m.group(3): self._tag(text, s, e, "at")
            elif m.group(4): self._tag(text, s, e, "num")
            elif m.group(5): self._tag(text, s, e, "prop")
            elif m.group(6): self._tag(text, s, e, "num")

    # ------------------------------------------------------------------
    def _hl_js(self, text, code):
        for m in RE_JS.finditer(code):
            s, e = m.start(), m.end()
            if   m.group(1): self._tag(text, s, e, "com")
            elif m.group(2): self._tag(text, s, e, "str")
            elif m.group(3): self._tag(text, s, e, "kw")
            elif m.group(4): self._tag(text, s, e, "num")

    # ══════════════════════════════════════════════════════════════════
    #  Acciones (copiar, guardar, abrir)
    # ══════════════════════════════════════════════════════════════════
    def _current_code(self):
        tab = self.state["tab"]
        if tab == "html": return self.state["html"], "html"
        if tab == "css":  return self._build_css(self.state["parser"]), "css"
        if tab == "js":   return self._build_js(self.state["parser"]),  "js"
        return None, None

    # ------------------------------------------------------------------
    def copy_current(self):
        code, _ = self._current_code()
        if code is None:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        self.set_status("✔ Código copiado al portapapeles.", "ok")

    # ------------------------------------------------------------------
    def save_current(self):
        code, ext = self._current_code()
        if code is None:
            return
        try:
            base = urlparse(self.state["url"]).hostname or "viewurl"
        except Exception:
            base = "viewurl"
        base = re.sub(r"[^\w.-]", "_", base)

        path = filedialog.asksaveasfilename(
            defaultextension="." + ext,
            initialfile=f"{base}.{ext}",
            filetypes=[(ext.upper(), f"*.{ext}"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(code)
            self.set_status("✔ Guardado: " + path, "ok")
        except Exception as e:
            messagebox.showerror("View URL", f"No se pudo guardar:\n{e}")

    # ------------------------------------------------------------------
    def open_in_browser(self):
        url = self.state["url"]
        if url:
            webbrowser.open(url)


# ═══════════════════════════════════════════════════════════════════
#  Punto de entrada
# ═══════════════════════════════════════════════════════════════════
def main():
    root = tk.Tk()
    ViewURLApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
