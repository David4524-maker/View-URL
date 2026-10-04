#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
View URL — visor de código fuente de cualquier página web.
Idiomas: español (es) · English (en) · português (pt).
Ejecuta en IDLE (Python 3.14): F5
"""

import json
import os
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
TIMEOUT     = 20
USER_AGENT  = "Mozilla/5.0 (compatible; ViewURL/1.0)"
MAX_ASSETS  = 15
MAX_HL      = 500_000
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".view_url.json")
LANGS       = ("es", "en", "pt")
LANG_NAMES  = {"es": "Español", "en": "English", "pt": "Português"}

COLORS = {
    "bg":     "#0b0f14", "panel": "#0d1117", "border": "#1e2937",
    "text":   "#c9d1d9", "muted": "#8b949e", "accent": "#58a6ff",
    "ok":     "#3fb950", "err":   "#f85149", "warn":   "#d29922",
    "com":    "#6b7a8d", "tag":   "#7ee787", "attr":   "#79c0ff",
    "str":    "#a5d6ff", "kw":    "#ff7b72", "num":    "#f0883e",
    "punc":   "#7d8590", "line":  "#39465a", "gutter": "#0a0e13",
}


# ═══════════════════════════════════════════════════════════════════
#  Traducciones
# ═══════════════════════════════════════════════════════════════════
TRANSLATIONS = {
    "es": {
        "app.title":          "View URL · visor de código fuente",
        "app.tagline":        "Mira todo el código de cualquier página web",
        "btn.view":           "Ver código",
        "btn.loading":        "Cargando…",
        "btn.copy":           "Copiar",
        "btn.save":           "Guardar…",
        "btn.open":           "Abrir web ↗",
        "menu.language":      "Idioma",
        "status.ready":       "Escribe una URL y pulsa «Ver código».",
        "status.connecting":  "Conectando con {url} …",
        "status.fetched":     "✔ {n} caracteres descargados. Cargando CSS/JS externos…",
        "status.assets":      "Cargando recursos externos… {i}/{total}",
        "status.done":        "✔ Listo · {n} caracteres · {css} CSS · {js} JS",
        "status.parse_warn":  "⚠ HTML descargado pero falló el análisis: {msg}",
        "status.error":       "✖ {msg}",
        "status.copied":      "✔ Código copiado al portapapeles.",
        "status.saved":       "✔ Guardado: {path}",
        "status.no_code":     "La pestaña actual no contiene código que copiar.",
        "status.nothing_dl":  "No hay nada que descargar.",
        "tab.html":           "HTML",
        "tab.css":            "CSS",
        "tab.js":             "JavaScript",
        "tab.resources":      "Recursos",
        "tab.info":           "Info",
        "empty.page":         "Todavía no se ha cargado ninguna página.\n\nEscribe una URL arriba y pulsa «Ver código».",
        "err.http":           "HTTP {code}: {reason}",
        "err.network":        "Error de red: {reason}",
        "err.save":           "No se pudo guardar:\n{msg}",
        "err.cannot_download":"No se pudo descargar",
        "err.empty_response": "respuesta vacía",
        "err.not_downloaded": "(no descargado)",
        "section.css_ext":    "Hojas de estilo externas",
        "section.css_inline": "Estilos en línea",
        "section.js_ext":     "Scripts externos",
        "section.js_inline":  "Scripts en línea",
        "section.images":     "Imágenes",
        "section.links":      "Enlaces únicos",
        "section.none":       "  (ninguno)\n",
        "section.meta":       "Metadatos",
        "no.css":             "/* No se encontró CSS en esta página. */",
        "no.js":              "/* No se encontró JavaScript en esta página. */",
        "info.summary":       "Resumen de {host}",
        "info.url":           "URL",
        "info.title":         "Título",
        "info.no_title":      "(sin título)",
        "info.size":          "Tamaño HTML",
        "info.chars":         "{n} caracteres",
        "info.lines":         "Líneas de HTML",
        "info.css_ext":       "CSS externo",
        "info.css_inline":    "CSS en línea",
        "info.js_ext":        "JS externo",
        "info.js_inline":     "JS en línea",
        "info.images":        "Imágenes",
        "info.links":         "Enlaces únicos",
        "info.metas":         "Etiquetas meta",
        "dialog.save_title":  "Guardar código",
        "dialog.all_files":   "Todos los archivos",
    },
    "en": {
        "app.title":          "View URL · source code viewer",
        "app.tagline":        "See the code of any web page",
        "btn.view":           "View code",
        "btn.loading":        "Loading…",
        "btn.copy":           "Copy",
        "btn.save":           "Save…",
        "btn.open":           "Open site ↗",
        "menu.language":      "Language",
        "status.ready":       "Type a URL and press “View code”.",
        "status.connecting":  "Connecting to {url} …",
        "status.fetched":     "✔ {n} characters downloaded. Loading external CSS/JS…",
        "status.assets":      "Loading external assets… {i}/{total}",
        "status.done":        "✔ Ready · {n} characters · {css} CSS · {js} JS",
        "status.parse_warn":  "⚠ HTML downloaded but parsing failed: {msg}",
        "status.error":       "✖ {msg}",
        "status.copied":      "✔ Code copied to clipboard.",
        "status.saved":       "✔ Saved: {path}",
        "status.no_code":     "The current tab has no code to copy.",
        "status.nothing_dl":  "Nothing to download.",
        "tab.html":           "HTML",
        "tab.css":            "CSS",
        "tab.js":             "JavaScript",
        "tab.resources":      "Resources",
        "tab.info":           "Info",
        "empty.page":         "No page has been loaded yet.\n\nType a URL above and press “View code”.",
        "err.http":           "HTTP {code}: {reason}",
        "err.network":        "Network error: {reason}",
        "err.save":           "Could not save:\n{msg}",
        "err.cannot_download":"Could not download",
        "err.empty_response": "empty response",
        "err.not_downloaded": "(not downloaded)",
        "section.css_ext":    "External stylesheets",
        "section.css_inline": "Inline styles",
        "section.js_ext":     "External scripts",
        "section.js_inline":  "Inline scripts",
        "section.images":     "Images",
        "section.links":      "Unique links",
        "section.none":       "  (none)\n",
        "section.meta":       "Metadata",
        "no.css":             "/* No CSS found on this page. */",
        "no.js":              "/* No JavaScript found on this page. */",
        "info.summary":       "Summary of {host}",
        "info.url":           "URL",
        "info.title":         "Title",
        "info.no_title":      "(no title)",
        "info.size":          "HTML size",
        "info.chars":         "{n} characters",
        "info.lines":         "HTML lines",
        "info.css_ext":       "External CSS",
        "info.css_inline":    "Inline CSS",
        "info.js_ext":        "External JS",
        "info.js_inline":     "Inline JS",
        "info.images":        "Images",
        "info.links":         "Unique links",
        "info.metas":         "Meta tags",
        "dialog.save_title":  "Save code",
        "dialog.all_files":   "All files",
    },
    "pt": {
        "app.title":          "View URL · visualizador de código-fonte",
        "app.tagline":        "Veja o código de qualquer página web",
        "btn.view":           "Ver código",
        "btn.loading":        "Carregando…",
        "btn.copy":           "Copiar",
        "btn.save":           "Salvar…",
        "btn.open":           "Abrir site ↗",
        "menu.language":      "Idioma",
        "status.ready":       "Digite uma URL e pressione «Ver código».",
        "status.connecting":  "Conectando a {url} …",
        "status.fetched":     "✔ {n} caracteres baixados. Carregando CSS/JS externos…",
        "status.assets":      "Carregando recursos externos… {i}/{total}",
        "status.done":        "✔ Pronto · {n} caracteres · {css} CSS · {js} JS",
        "status.parse_warn":  "⚠ HTML baixado mas a análise falhou: {msg}",
        "status.error":       "✖ {msg}",
        "status.copied":      "✔ Código copiado para a área de transferência.",
        "status.saved":       "✔ Salvo: {path}",
        "status.no_code":     "A aba atual não contém código para copiar.",
        "status.nothing_dl":  "Nada para baixar.",
        "tab.html":           "HTML",
        "tab.css":            "CSS",
        "tab.js":             "JavaScript",
        "tab.resources":      "Recursos",
        "tab.info":           "Info",
        "empty.page":         "Nenhuma página foi carregada ainda.\n\nDigite uma URL acima e pressione «Ver código».",
        "err.http":           "HTTP {code}: {reason}",
        "err.network":        "Erro de rede: {reason}",
        "err.save":           "Não foi possível salvar:\n{msg}",
        "err.cannot_download":"Não foi possível baixar",
        "err.empty_response": "resposta vazia",
        "err.not_downloaded": "(não baixado)",
        "section.css_ext":    "Folhas de estilo externas",
        "section.css_inline": "Estilos em linha",
        "section.js_ext":     "Scripts externos",
        "section.js_inline":  "Scripts em linha",
        "section.images":     "Imagens",
        "section.links":      "Links únicos",
        "section.none":       "  (nenhum)\n",
        "section.meta":       "Metadados",
        "no.css":             "/* Nenhum CSS encontrado nesta página. */",
        "no.js":              "/* Nenhum JavaScript encontrado nesta página. */",
        "info.summary":       "Resumo de {host}",
        "info.url":           "URL",
        "info.title":         "Título",
        "info.no_title":      "(sem título)",
        "info.size":          "Tamanho do HTML",
        "info.chars":         "{n} caracteres",
        "info.lines":         "Linhas de HTML",
        "info.css_ext":       "CSS externo",
        "info.css_inline":    "CSS em linha",
        "info.js_ext":        "JS externo",
        "info.js_inline":     "JS em linha",
        "info.images":        "Imagens",
        "info.links":         "Links únicos",
        "info.metas":         "Meta tags",
        "dialog.save_title":  "Salvar código",
        "dialog.all_files":   "Todos os arquivos",
    },
}


def load_lang():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            lang = json.load(f).get("lang", "es")
            return lang if lang in LANGS else "es"
    except Exception:
        return "es"


def save_lang(lang):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"lang": lang}, f)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
#  Analizador HTML
# ═══════════════════════════════════════════════════════════════════
class PageParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title = ""
        self._in_title = False; self._title_buf = []
        self.css_links = []; self.inline_styles = []
        self._in_style = False; self._style_buf = []
        self.js_links = []; self.inline_scripts = []
        self._in_script = False; self._script_buf = []
        self.images = []; self.links = []
        self._seen_links = set()
        self._in_a = False; self._a_buf = []; self._a_href = None
        self.metas = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "base" and a.get("href"):
            self.base_url = urljoin(self.base_url, a["href"]); return
        if tag == "title":
            self._in_title = True; self._title_buf = []
        elif tag == "link":
            if "stylesheet" in a.get("rel", "").lower() and a.get("href"):
                self.css_links.append({
                    "href": urljoin(self.base_url, a["href"]),
                    "media": a.get("media", "")})
        elif tag == "style":
            self._in_style = True; self._style_buf = []
        elif tag == "script":
            src = a.get("src"); stype = (a.get("type") or "").lower()
            is_js = (not stype or "javascript" in stype
                     or "ecmascript" in stype or stype == "module")
            if src:
                self.js_links.append({
                    "src": urljoin(self.base_url, src), "type": stype})
            elif is_js:
                self._in_script = True; self._script_buf = []
        elif tag == "img" and a.get("src"):
            self.images.append({
                "src": urljoin(self.base_url, a["src"]),
                "alt": a.get("alt", "")})
        elif tag == "a" and a.get("href"):
            self._in_a = True; self._a_buf = []
            self._a_href = urljoin(self.base_url, a["href"])
        elif tag == "meta":
            name = a.get("name") or a.get("property") or ""
            content = (a.get("content") or "")[:400]
            if name and content:
                self.metas.append({"name": name, "content": content})

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title" and self._in_title:
            self._in_title = False
            self.title = "".join(self._title_buf).strip()
        elif tag == "style" and self._in_style:
            self._in_style = False
            css = "".join(self._style_buf).strip()
            if css: self.inline_styles.append(css)
        elif tag == "script" and self._in_script:
            self._in_script = False
            js = "".join(self._script_buf).strip()
            if js: self.inline_scripts.append(js)
        elif tag == "a" and self._in_a:
            self._in_a = False
            text = "".join(self._a_buf).strip()[:70]
            if self._a_href and self._a_href not in self._seen_links:
                self._seen_links.add(self._a_href)
                self.links.append({"href": self._a_href, "text": text})

    def handle_data(self, data):
        if self._in_title:  self._title_buf.append(data)
        if self._in_style:  self._style_buf.append(data)
        if self._in_script: self._script_buf.append(data)
        if self._in_a:      self._a_buf.append(data)


# ═══════════════════════════════════════════════════════════════════
#  Resaltado
# ═══════════════════════════════════════════════════════════════════
RE_HTML = re.compile(r'(<!--[\s\S]*?-->)|(<!DOCTYPE[^>]*>)|(<\/?[a-zA-Z][^>]*>)',
                     re.IGNORECASE)
RE_ATTR = re.compile(r'([a-zA-Z_:@][\w:.\-]*)(\s*=\s*)("[^"]*"|\'[^\']*\'|[^\s"\'>]+)')
RE_CSS = re.compile(
    r'(\/\*[\s\S]*?\*\/)|("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'
    r'|(@[\w-]+)|(#[0-9a-fA-F]{3,8}\b)|([\w-]+(?=\s*:))'
    r'|(\d*\.?\d+(?:px|em|rem|%|vh|vw|s|ms|deg|fr|pt)?)')
RE_JS = re.compile(
    r'(\/\/[^\n]*|\/\*[\s\S]*?\*\/)'
    r'|("(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|`(?:[^`\\]|\\.)*`)'
    r'|(\b(?:const|let|var|function|return|if|else|for|while|do|switch|case|'
    r'break|continue|new|class|extends|super|this|typeof|instanceof|delete|'
    r'in|of|try|catch|finally|throw|async|await|yield|import|export|from|'
    r'default|null|undefined|true|false|void|static)\b)'
    r'|(\b\d+(?:\.\d+)?\b)')


# ═══════════════════════════════════════════════════════════════════
#  Aplicación
# ═══════════════════════════════════════════════════════════════════
class ViewURLApp:

    def __init__(self, root):
        self.root = root
        self.lang = load_lang()
        self.state = {
            "url": "", "html": "", "parser": None,
            "assets": {}, "tab": "html", "busy": False,
        }
        self._last_status = ("status.ready", "", {})
        self._code_widgets = {}
        self._text_widgets = {}
        self._tab_buttons = {}

        system = platform.system()
        mono_family = {"Windows": "Consolas", "Darwin": "Menlo"}.get(
            system, "DejaVu Sans Mono")
        ui_family = {"Windows": "Segoe UI", "Darwin": "Helvetica Neue"}.get(
            system, "Helvetica")
        self.mono      = Font(family=mono_family, size=10)
        self.mono_bold = Font(family=mono_family, size=10, weight="bold")
        self.mono_ital = Font(family=mono_family, size=10, slant="italic")
        self.ui        = (ui_family, 9)
        self.ui_bold   = (ui_family, 10, "bold")

        self._build_ui()
        self._seed_placeholders()
        self._retranslate()

    # ------------------------------------------------------------------
    #  Traducción
    # ------------------------------------------------------------------
    def t(self, key, **kw):
        txt = TRANSLATIONS.get(self.lang, {}).get(key, key)
        if kw:
            try: return txt.format(**kw)
            except Exception: return txt
        return txt

    def set_status(self, key_or_text, kind="", **kw):
        colors = {"": "#374151", "ok": COLORS["ok"],
                  "err": COLORS["err"], "load": COLORS["warn"]}
        self.status_dot.configure(fg=colors.get(kind, "#374151"))
        if key_or_text in TRANSLATIONS.get(self.lang, {}):
            self._last_status = (key_or_text, kind, kw)
            self.status_lbl.configure(text=self.t(key_or_text, **kw))
        else:
            self._last_status = None
            self.status_lbl.configure(text=str(key_or_text))

    def change_lang(self, lang):
        if lang == self.lang or lang not in LANGS:
            return
        self.lang = lang
        save_lang(lang)
        self._retranslate()

    def _retranslate(self):
        self.root.title(self.t("app.title"))
        self.tagline_lbl.configure(text=self.t("app.tagline"))
        self.go_btn.configure(
            text=self.t("btn.loading") if self.state["busy"] else self.t("btn.view"))
        self.open_btn.configure(text=self.t("btn.open"))
        self.save_btn.configure(text=self.t("btn.save"))
        self.copy_btn.configure(text=self.t("btn.copy"))
        self.lang_btn.configure(text="🌐 " + self.t("menu.language"))

        for key, btn in self._tab_buttons.items():
            tk_key = {"recursos": "tab.resources"}.get(key, "tab." + key)
            btn.configure(text=self.t(tk_key))

        if self._last_status:
            key, kind, kw = self._last_status
            self.set_status(key, kind, **kw)
        else:
            self.set_status("status.ready")

        if self.state["html"]:
            self._render_derived_tabs()
        else:
            self._seed_placeholders()

    # ------------------------------------------------------------------
    #  UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.root.geometry("1180x760")
        self.root.minsize(820, 540)
        self.root.configure(bg=COLORS["bg"])

        # cabecera
        header = tk.Frame(self.root, bg=COLORS["bg"])
        header.pack(fill="x", padx=16, pady=(12, 0))

        tk.Label(header, text="</>", bg="#1f6feb", fg="white",
                 font=self.mono_bold, padx=12, pady=6).pack(side="left")

        titles = tk.Frame(header, bg=COLORS["bg"])
        titles.pack(side="left", padx=12)
        tk.Label(titles, text="View URL", bg=COLORS["bg"], fg=COLORS["text"],
                 font=(self.ui[0], 15, "bold")).pack(anchor="w")
        self.tagline_lbl = tk.Label(titles, text="", bg=COLORS["bg"],
                                    fg=COLORS["muted"], font=self.ui)
        self.tagline_lbl.pack(anchor="w")

        # selector de idioma
        self.lang_btn = tk.Menubutton(
            header, text="🌐", bg=COLORS["bg"], fg=COLORS["muted"],
            activebackground="#111823", activeforeground=COLORS["text"],
            relief="flat", bd=0, padx=12, pady=6, font=self.ui,
            cursor="hand2", highlightthickness=0)
        menu = tk.Menu(self.lang_btn, tearoff=0)
        for code in LANGS:
            menu.add_command(label=LANG_NAMES[code],
                             command=lambda c=code: self.change_lang(c))
        self.lang_btn.configure(menu=menu)
        self.lang_btn.pack(side="right")

        # barra URL
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

        self.go_btn = tk.Button(bar, text="", command=self.on_go,
                                bg="#1f6feb", fg="white",
                                activebackground="#3b82f6",
                                activeforeground="white",
                                disabledforeground="#9fb4cc",
                                relief="flat", bd=0, padx=20, pady=6,
                                font=self.ui_bold, cursor="hand2")
        self.go_btn.pack(side="left", padx=(8, 0))

        # estado
        sframe = tk.Frame(self.root, bg=COLORS["bg"])
        sframe.pack(fill="x", padx=18, pady=(0, 8))
        self.status_dot = tk.Label(sframe, text="●", bg=COLORS["bg"],
                                   fg="#374151", font=(self.ui[0], 10))
        self.status_dot.pack(side="left")
        self.status_lbl = tk.Label(sframe, text="", bg=COLORS["bg"],
                                   fg=COLORS["muted"], font=self.ui)
        self.status_lbl.pack(side="left", padx=6)

        # pestañas
        tabs_bar = tk.Frame(self.root, bg=COLORS["bg"])
        tabs_bar.pack(fill="x", padx=16)

        for key in ("html", "css", "js", "recursos", "info"):
            b = tk.Button(tabs_bar, text=key,
                          command=lambda k=key: self.switch_tab(k),
                          bg=COLORS["bg"], fg=COLORS["muted"],
                          activebackground="#111823",
                          activeforeground=COLORS["text"],
                          relief="flat", bd=0, padx=12, pady=6,
                          font=self.ui, cursor="hand2")
            b.pack(side="left")
            self._tab_buttons[key] = b

        self.open_btn = self._mini_btn(tabs_bar, "", self.open_in_browser)
        self.open_btn.pack(side="right", padx=2)
        self.save_btn = self._mini_btn(tabs_bar, "", self.save_current)
        self.save_btn.pack(side="right", padx=2)
        self.copy_btn = self._mini_btn(tabs_bar, "", self.copy_current)
        self.copy_btn.pack(side="right", padx=2)

        tk.Frame(self.root, bg=COLORS["border"], height=1).pack(
            fill="x", pady=(6, 0))

        # visor
        self.viewer = tk.Frame(self.root, bg=COLORS["panel"])
        self.viewer.pack(fill="both", expand=True)

        self.frames = {k: tk.Frame(self.viewer, bg=COLORS["panel"])
                       for k in ("html", "css", "js", "recursos", "info")}
        for key in ("html", "css", "js"):
            self._build_code_tab(self.frames[key], key)
        for key in ("recursos", "info"):
            self._build_text_tab(self.frames[key], key)

        self.switch_tab("html")

    def _mini_btn(self, parent, text, command):
        return tk.Button(parent, text=text, command=command,
                         bg=COLORS["bg"], fg=COLORS["muted"],
                         activebackground="#111823",
                         activeforeground=COLORS["text"],
                         relief="flat", bd=0, padx=10, pady=5,
                         font=self.ui, cursor="hand2")

    def _build_code_tab(self, parent, key):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)
        gutter = tk.Text(parent, width=5, bg=COLORS["gutter"], fg=COLORS["line"],
                         font=self.mono, bd=0, highlightthickness=0,
                         state="disabled", wrap="none", padx=8, pady=10,
                         cursor="arrow", takefocus=0)
        gutter.grid(row=0, column=0, sticky="ns")
        text = tk.Text(parent, bg=COLORS["panel"], fg=COLORS["text"],
                       font=self.mono, bd=0, highlightthickness=0,
                       wrap="none", padx=10, pady=10,
                       insertbackground=COLORS["text"],
                       selectbackground="#1f6feb", selectforeground="white",
                       state="disabled")
        text.grid(row=0, column=1, sticky="nsew")
        vsb = tk.Scrollbar(parent, orient="vertical", bg=COLORS["panel"],
                           troughcolor=COLORS["bg"], activebackground="#31465f",
                           bd=0, highlightthickness=0, width=12)
        vsb.grid(row=0, column=2, sticky="ns")
        hsb = tk.Scrollbar(parent, orient="horizontal", bg=COLORS["panel"],
                           troughcolor=COLORS["bg"], activebackground="#31465f",
                           bd=0, highlightthickness=0, width=12)
        hsb.grid(row=1, column=1, sticky="ew")
        def on_vsb(*a): text.yview(*a); gutter.yview(*a)
        vsb.config(command=on_vsb)
        def on_yscroll(f, l): vsb.set(f, l); gutter.yview_moveto(f)
        text.config(yscrollcommand=on_yscroll, xscrollcommand=hsb.set)
        hsb.config(command=text.xview)

        # ⚠️ tag_configure usa 'foreground=' (no 'fg=')
        for tag, fg, fnt in (("com", COLORS["com"], self.mono_ital),
                             ("tag", COLORS["tag"], self.mono),
                             ("attr", COLORS["attr"], self.mono),
                             ("str", COLORS["str"], self.mono),
                             ("punc", COLORS["punc"], self.mono),
                             ("kw", COLORS["kw"], self.mono),
                             ("num", COLORS["num"], self.mono),
                             ("prop", COLORS["attr"], self.mono),
                             ("at", COLORS["kw"], self.mono),
                             ("doc", COLORS["muted"], self.mono)):
            text.tag_configure(tag, foreground=fg, font=fnt)

        self._code_widgets[key] = (text, gutter)

    def _build_text_tab(self, parent, key):
        text = tk.Text(parent, bg=COLORS["panel"], fg=COLORS["text"],
                       font=self.mono, bd=0, highlightthickness=0,
                       wrap="word", padx=18, pady=14,
                       insertbackground=COLORS["text"],
                       selectbackground="#1f6feb", selectforeground="white",
                       state="disabled", cursor="arrow")
        text.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(parent, orient="vertical", bg=COLORS["panel"],
                          troughcolor=COLORS["bg"], activebackground="#31465f",
                          bd=0, highlightthickness=0, width=12)
        sb.pack(side="right", fill="y")
        text.config(yscrollcommand=sb.set); sb.config(command=text.yview)

        # ⚠️ FIX: tag_configure NO acepta el alias 'fg' → 'foreground'
        text.tag_configure("h",     foreground=COLORS["accent"], font=self.mono_bold)
        text.tag_configure("muted", foreground=COLORS["muted"])
        text.tag_configure("link",  foreground=COLORS["accent"], underline=True)
        text.tag_configure("key",   foreground=COLORS["muted"])
        text.tag_configure("val",   foreground=COLORS["text"])
        self._text_widgets[key] = text

    def _seed_placeholders(self):
        for key in ("html", "css", "js"):
            self._set_code(key, "", "html")
        for key in ("recursos", "info"):
            t = self._text_widgets[key]
            t.configure(state="normal"); t.delete("1.0", "end")
            t.insert("end", self.t("empty.page"), "muted")
            t.configure(state="disabled")

    def switch_tab(self, key):
        self.state["tab"] = key
        for k, frame in self.frames.items():
            if k == key: frame.pack(fill="both", expand=True)
            else: frame.pack_forget()
        for k, btn in self._tab_buttons.items():
            if k == key: btn.configure(fg=COLORS["text"], bg="#0f1520")
            else: btn.configure(fg=COLORS["muted"], bg=COLORS["bg"])
        st = "normal" if key in ("html", "css", "js") else "disabled"
        self.copy_btn.configure(state=st); self.save_btn.configure(state=st)

    # ------------------------------------------------------------------
    #  Flujo
    # ------------------------------------------------------------------
    def on_go(self):
        if self.state["busy"]: return
        url = self.url_var.get().strip()
        if not url: return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            self.url_var.set(url)
        self.load(url)

    def load(self, url):
        self.state.update(busy=True, url=url, html="", parser=None, assets={})
        self.go_btn.configure(state="disabled", text=self.t("btn.loading"))
        self.set_status("status.connecting", "load", url=url)
        for key in ("html", "css", "js"): self._set_code(key, "", "html")
        for key in ("recursos", "info"):
            t = self._text_widgets[key]
            t.configure(state="normal"); t.delete("1.0", "end")
            t.configure(state="disabled")
        threading.Thread(target=self._worker_fetch, args=(url,), daemon=True).start()

    @staticmethod
    def _download(url):
        req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        with urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            cs = resp.headers.get_content_charset() or "utf-8"
            try: return raw.decode(cs, errors="replace")
            except LookupError: return raw.decode("utf-8", errors="replace")

    def _worker_fetch(self, url):
        try:
            html = self._download(url)
            self.root.after(0, self._on_fetched, url, html)
        except HTTPError as e:
            self.root.after(0, self._on_error,
                            self.t("err.http", code=e.code, reason=e.reason))
        except URLError as e:
            self.root.after(0, self._on_error,
                            self.t("err.network", reason=e.reason))
        except Exception as e:
            self.root.after(0, self._on_error, f"{type(e).__name__}: {e}")

    def _on_fetched(self, url, html):
        self.state["html"] = html
        try:
            parser = PageParser(url); parser.feed(html); parser.close()
            self.state["parser"] = parser
        except Exception as e:
            self.set_status(self.t("status.parse_warn", msg=str(e)), "err")
        self._set_code("html", html, "html")
        self._render_derived_tabs()
        self.set_status("status.fetched", "ok", n=f"{len(html):,}")
        threading.Thread(target=self._worker_assets, daemon=True).start()

    def _worker_assets(self):
        parser = self.state["parser"]
        if parser is None:
            self.root.after(0, self._on_assets_done); return
        urls = ([l["href"] for l in parser.css_links[:MAX_ASSETS]] +
                [s["src"]  for s in parser.js_links[:MAX_ASSETS]])
        urls = list(dict.fromkeys(urls))
        total = len(urls)
        if total == 0:
            self.root.after(0, self._on_assets_done); return
        for i, u in enumerate(urls, 1):
            try: self.state["assets"][u] = {"text": self._download(u)}
            except Exception as e:
                self.state["assets"][u] = {"error": f"{type(e).__name__}: {e}"}
            self.root.after(0, self.set_status, "status.assets", "load",
                            {"i": i, "total": total})
        self.root.after(0, self._on_assets_done)

    def _on_assets_done(self):
        self.state["busy"] = False
        self.go_btn.configure(state="normal", text=self.t("btn.view"))
        self._render_derived_tabs()
        p = self.state["parser"]
        n_css = (len(p.css_links) + len(p.inline_styles)) if p else 0
        n_js  = (len(p.js_links)  + len(p.inline_scripts)) if p else 0
        self.set_status("status.done", "ok",
                        n=f"{len(self.state['html']):,}", css=n_css, js=n_js)

    def _on_error(self, msg):
        self.state["busy"] = False
        self.go_btn.configure(state="normal", text=self.t("btn.view"))
        self.set_status(self.t("status.error", msg=msg), "err")

    # ------------------------------------------------------------------
    #  Renderizado
    # ------------------------------------------------------------------
    def _render_derived_tabs(self):
        p = self.state["parser"]
        self._set_code("css", self._build_css(p), "css")
        self._set_code("js",  self._build_js(p),  "js")
        self._render_resources(p)
        self._render_info(p)

    def _build_css(self, p):
        if p is None: return ""
        parts = []
        for i, css in enumerate(p.inline_styles, 1):
            parts.append(f"/* ═════════ <style> #{i} ═════════ */\n{css}")
        for link in p.css_links:
            href = link["href"]; head = f"/* ═════════ {href} ═════════ */"
            a = self.state["assets"].get(href)
            if a is None: parts.append(f"{head}\n   {self.t('err.not_downloaded')}")
            elif "error" in a: parts.append(f"{head}\n   ERROR: {a['error']}")
            else: parts.append(f"{head}\n{a['text'].strip()}")
        return "\n\n\n".join(parts) or self.t("no.css")

    def _build_js(self, p):
        if p is None: return ""
        parts = []
        for i, js in enumerate(p.inline_scripts, 1):
            parts.append(f"/* ═════════ <script> #{i} ═════════ */\n{js}")
        for link in p.js_links:
            href = link["src"]; head = f"/* ═════════ {href} ═════════ */"
            a = self.state["assets"].get(href)
            if a is None: parts.append(f"{head}\n   {self.t('err.not_downloaded')}")
            elif "error" in a: parts.append(f"{head}\n   ERROR: {a['error']}")
            else: parts.append(f"{head}\n{a['text'].strip()}")
        return "\n\n\n".join(parts) or self.t("no.js")

    def _render_resources(self, p):
        t = self._text_widgets["recursos"]
        t.configure(state="normal"); t.delete("1.0", "end")
        if p is None:
            t.insert("end", self.t("empty.page"), "muted")
            t.configure(state="disabled"); return

        counter = [0]
        def add_link(url, extra=""):
            tag = f"lk_{counter[0]}"; counter[0] += 1
            t.insert("end", url, (tag, "link"))
            t.tag_bind(tag, "<Button-1>", lambda e, u=url: webbrowser.open(u))
            if extra: t.insert("end", "  " + extra, "muted")
            t.insert("end", "\n")

        def header(title, n):
            t.insert("end", f"\n{title}  ", "h")
            t.insert("end", f"({n})\n", "muted")

        def empty():
            t.insert("end", self.t("section.none"), "muted")

        header(self.t("section.css_ext"), len(p.css_links))
        if p.css_links:
            for l in p.css_links:
                t.insert("end", "  • ", "muted")
                add_link(l["href"], f"[media={l['media']}]" if l["media"] else "")
        else: empty()

        header(self.t("section.css_inline"), len(p.inline_styles))
        if p.inline_styles:
            for i, css in enumerate(p.inline_styles, 1):
                prev = css.strip().replace("\n", " ")[:120]
                t.insert("end", f"  • <style> #{i}  ", "muted")
                t.insert("end", f"{prev}…\n", "val")
        else: empty()

        header(self.t("section.js_ext"), len(p.js_links))
        if p.js_links:
            for l in p.js_links:
                t.insert("end", "  • ", "muted")
                add_link(l["src"], f"[{l['type']}]" if l["type"] else "")
        else: empty()

        header(self.t("section.js_inline"), len(p.inline_scripts))
        if p.inline_scripts:
            for i, js in enumerate(p.inline_scripts, 1):
                prev = js.strip().replace("\n", " ")[:120]
                t.insert("end", f"  • inline #{i}  ", "muted")
                t.insert("end", f"{prev}…\n", "val")
        else: empty()

        header(self.t("section.images"), len(p.images))
        if p.images:
            for im in p.images:
                t.insert("end", "  • ", "muted")
                add_link(im["src"], f"[alt: {im['alt']}]" if im["alt"] else "")
        else: empty()

        header(self.t("section.links"), len(p.links))
        if p.links:
            for l in p.links[:200]:
                t.insert("end", "  • ", "muted")
                add_link(l["href"], f"«{l['text']}»" if l["text"] else "")
        else: empty()

        t.configure(state="disabled")

    def _render_info(self, p):
        t = self._text_widgets["info"]
        t.configure(state="normal"); t.delete("1.0", "end")
        if p is None:
            t.insert("end", self.t("empty.page"), "muted")
            t.configure(state="disabled"); return
        try: host = urlparse(self.state["url"]).hostname or self.state["url"]
        except Exception: host = self.state["url"]
        html = self.state["html"]
        rows = [
            (self.t("info.url"),         self.state["url"]),
            (self.t("info.title"),       p.title or self.t("info.no_title")),
            (self.t("info.size"),        self.t("info.chars", n=f"{len(html):,}")),
            (self.t("info.lines"),       f"{html.count(chr(10)) + 1:,}"),
            (self.t("info.css_ext"),     str(len(p.css_links))),
            (self.t("info.css_inline"),  str(len(p.inline_styles))),
            (self.t("info.js_ext"),      str(len(p.js_links))),
            (self.t("info.js_inline"),   str(len(p.inline_scripts))),
            (self.t("info.images"),      str(len(p.images))),
            (self.t("info.links"),       str(len(p.links))),
            (self.t("info.metas"),       str(len(p.metas))),
        ]
        t.insert("end", self.t("info.summary", host=host) + "\n\n", "h")
        for k, v in rows:
            t.insert("end", f"  {k:<20}", "key")
            t.insert("end", f"{v}\n", "val")
        if p.metas:
            t.insert("end", f"\n{self.t('section.meta')}\n\n", "h")
            for m in p.metas:
                t.insert("end", f"  {m['name']:<20}", "key")
                t.insert("end", f"{m['content']}\n", "val")
        t.configure(state="disabled")

    def _set_code(self, key, code, lang):
        text, gutter = self._code_widgets[key]
        text.configure(state="normal"); text.delete("1.0", "end")
        if code: text.insert("1.0", code)
        if code and len(code) <= MAX_HL:
            if lang == "html": self._hl_html(text, code)
            elif lang == "css": self._hl_css(text, code)
            elif lang == "js":  self._hl_js(text, code)
        text.configure(state="disabled")
        n = code.count("\n") + 1 if code else 1
        gutter.configure(state="normal"); gutter.delete("1.0", "end")
        gutter.insert("1.0", "\n".join(str(i) for i in range(1, n + 1)))
        gutter.configure(state="disabled")
        text.yview_moveto(0); gutter.yview_moveto(0)

    @staticmethod
    def _tag(text, s, e, tag):
        text.tag_add(tag, f"1.0+{s}c", f"1.0+{e}c")

    def _hl_html(self, text, code):
        for m in RE_HTML.finditer(code):
            s, e = m.start(), m.end()
            if m.group(1) or m.group(2):
                self._tag(text, s, e, "com"); continue
            frag = m.group(3); self._tag(text, s, e, "punc")
            tm = re.match(r"<\/?([a-zA-Z][\w:.\-]*)", frag)
            if not tm: continue
            self._tag(text, s + tm.start(1), s + tm.end(1), "tag")
            attrs_off = s + tm.end()
            for am in RE_ATTR.finditer(frag[tm.end():]):
                self._tag(text, attrs_off + am.start(1), attrs_off + am.end(1), "attr")
                self._tag(text, attrs_off + am.start(3), attrs_off + am.end(3), "str")

    def _hl_css(self, text, code):
        for m in RE_CSS.finditer(code):
            s, e = m.start(), m.end()
            for i, tag in ((1, "com"), (2, "str"), (3, "at"),
                           (4, "num"), (5, "prop"), (6, "num")):
                if m.group(i):
                    self._tag(text, s, e, tag); break

    def _hl_js(self, text, code):
        for m in RE_JS.finditer(code):
            s, e = m.start(), m.end()
            for i, tag in ((1, "com"), (2, "str"), (3, "kw"), (4, "num")):
                if m.group(i):
                    self._tag(text, s, e, tag); break

    # ------------------------------------------------------------------
    #  Acciones
    # ------------------------------------------------------------------
    def _current_code(self):
        tab = self.state["tab"]
        if tab == "html": return self.state["html"], "html"
        if tab == "css":  return self._build_css(self.state["parser"]), "css"
        if tab == "js":   return self._build_js(self.state["parser"]),  "js"
        return None, None

    def copy_current(self):
        code, _ = self._current_code()
        if code is None: return
        self.root.clipboard_clear(); self.root.clipboard_append(code)
        self.set_status("status.copied", "ok")

    def save_current(self):
        code, ext = self._current_code()
        if code is None: return
        try: base = urlparse(self.state["url"]).hostname or "viewurl"
        except Exception: base = "viewurl"
        base = re.sub(r"[^\w.-]", "_", base)
        path = filedialog.asksaveasfilename(
            title=self.t("dialog.save_title"),
            defaultextension="." + ext,
            initialfile=f"{base}.{ext}",
            filetypes=[(ext.upper(), f"*.{ext}"),
                       (self.t("dialog.all_files"), "*.*")])
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f: f.write(code)
            self.set_status("status.saved", "ok", path=path)
        except Exception as e:
            messagebox.showerror("View URL", self.t("err.save", msg=str(e)))

    def open_in_browser(self):
        if self.state["url"]: webbrowser.open(self.state["url"])


def main():
    root = tk.Tk()
    ViewURLApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
