#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mando PC — agente que corre en tu laptop y te deja controlarla desde el celular.

Sirve la app web (PWA) y habla con ella por WebSocket:
  - pantalla en vivo (JPEG con control de flujo)
  - mouse y teclado
  - volumen / multimedia / bloquear / suspender / apagar
  - explorador de archivos (bajar y subir)
Seguridad: token secreto + solo redes privadas (Wi-Fi local o Tailscale).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import io
import ipaddress
import json
import mimetypes
import os
import platform
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, urlsplit

VERSION = "1.0"
SISTEMA = platform.system()  # 'Windows' | 'Darwin' | 'Linux'

# En Windows hay que ser "DPI aware" ANTES de tocar pantalla/mouse, para que
# las coordenadas de la captura y del mouse coincidan con los píxeles reales.
if SISTEMA == "Windows":
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from aiohttp import web, WSMsgType
except ImportError:
    print("Falta instalar las dependencias:  pip install -r requirements.txt")
    sys.exit(1)

AQUI = Path(__file__).resolve().parent
WEB = AQUI / "web"
DIR_CFG = Path.home() / ".mando-pc"
ARCH_CFG = DIR_CFG / "config.json"
PX_POR_CLIC = 24.0  # píxeles de dedo que equivalen a un "clic" de rueda


# ───────────────────────────── Configuración ─────────────────────────────

def atajos_por_defecto() -> list[dict]:
    if SISTEMA == "Windows":
        return [
            {"nombre": "Mostrar escritorio", "icono": "🖥️", "teclas": ["win", "d"]},
            {"nombre": "Cambiar ventana", "icono": "🪟", "teclas": ["alt", "tab"]},
            {"nombre": "Administrador de tareas", "icono": "📊", "teclas": ["ctrl", "shift", "esc"]},
            {"nombre": "Explorador de archivos", "icono": "📁", "teclas": ["win", "e"]},
            {"nombre": "Captura de pantalla", "icono": "✂️", "teclas": ["win", "shift", "s"]},
            {"nombre": "Cerrar ventana", "icono": "❌", "teclas": ["alt", "f4"]},
        ]
    if SISTEMA == "Darwin":
        return [
            {"nombre": "Mission Control", "icono": "🖥️", "teclas": ["ctrl", "up"]},
            {"nombre": "Cambiar app", "icono": "🪟", "teclas": ["cmd", "tab"]},
            {"nombre": "Spotlight", "icono": "🔎", "teclas": ["cmd", "space"]},
            {"nombre": "Captura de pantalla", "icono": "✂️", "teclas": ["cmd", "shift", "4"]},
            {"nombre": "Cerrar ventana", "icono": "❌", "teclas": ["cmd", "w"]},
            {"nombre": "Forzar salir", "icono": "⚠️", "teclas": ["cmd", "alt", "esc"]},
        ]
    return [
        {"nombre": "Mostrar escritorio", "icono": "🖥️", "teclas": ["win", "d"]},
        {"nombre": "Cambiar ventana", "icono": "🪟", "teclas": ["alt", "tab"]},
        {"nombre": "Cerrar ventana", "icono": "❌", "teclas": ["alt", "f4"]},
    ]


def guardar_config(cfg: dict) -> None:
    DIR_CFG.mkdir(parents=True, exist_ok=True)
    tmp = ARCH_CFG.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), "utf-8")
    try:
        os.chmod(tmp, 0o600)
    except Exception:
        pass
    tmp.replace(ARCH_CFG)


def cargar_config() -> dict:
    DIR_CFG.mkdir(parents=True, exist_ok=True)
    cfg: dict = {}
    if ARCH_CFG.exists():
        try:
            cfg = json.loads(ARCH_CFG.read_text("utf-8"))
        except Exception:
            print(f"⚠ No pude leer {ARCH_CFG}; uso valores por defecto.")
    base = {
        "puerto": 8765,
        "token": "",
        "emparejado": False,
        "solo_redes_privadas": True,
        "monitor": 1,
        "carpetas": [str(Path.home())],
        "carpeta_subidas": str(Path.home() / "MandoPC"),
        "limite_subida_mb": 4096,
        "atajos": atajos_por_defecto(),
    }
    for k, v in base.items():
        cfg.setdefault(k, v)
    if not cfg["token"]:
        cfg["token"] = secrets.token_urlsafe(24)
    guardar_config(cfg)
    return cfg


# ───────────────────────────── Red y seguridad ─────────────────────────────

REDES_PRIVADAS = [
    ipaddress.ip_network(n)
    for n in (
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16",
        "100.64.0.0/10",  # Tailscale / CGNAT
        "127.0.0.0/8", "::1/128", "fc00::/7", "fe80::/10",
    )
]


def es_red_privada(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if a.version == 6 and a.ipv4_mapped:
        a = a.ipv4_mapped
    return any(a in n for n in REDES_PRIVADAS)


def direcciones_locales() -> list[tuple[str, str]]:
    """[(etiqueta, ip)] de las IPs por las que el celular puede llegar."""
    out: list[tuple[str, str]] = []
    try:
        import psutil

        for nombre, addrs in psutil.net_if_addrs().items():
            for a in addrs:
                if a.family != socket.AF_INET:
                    continue
                ip = a.address
                if ip.startswith(("127.", "169.254.")) or not es_red_privada(ip):
                    continue
                if ipaddress.ip_address(ip) in ipaddress.ip_network("100.64.0.0/10"):
                    out.append(("Tailscale (desde cualquier lugar)", ip))
                else:
                    out.append((f"Wi-Fi / red local ({nombre})", ip))
    except Exception:
        pass
    if not out:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))
            out.append(("Red local", s.getsockname()[0]))
            s.close()
        except Exception:
            pass
    out.sort(key=lambda t: (t[0].startswith("Tailscale"), t[1]))
    return out


class Guardia:
    """Verifica el token y bloquea IPs que fallan muchas veces."""

    MAX_FALLOS = 10
    BLOQUEO_S = 600

    def __init__(self, token: str):
        self.token = token
        self.fallos: dict[str, list[float]] = {}

    def verificar(self, ip: str, candidato: str) -> bool:
        ahora = time.time()
        reg = [t for t in self.fallos.get(ip, []) if ahora - t < self.BLOQUEO_S]
        self.fallos[ip] = reg
        if len(reg) >= self.MAX_FALLOS:
            return False
        ok = bool(candidato) and hmac.compare_digest(candidato.encode(), self.token.encode())
        if not ok:
            reg.append(ahora)
        return ok


# ───────────────────────────── Pantalla ─────────────────────────────

class Pantalla:
    """Captura con mss en UN hilo (mss usa recursos ligados al hilo)."""

    def __init__(self):
        self.pool = ThreadPoolExecutor(1, thread_name_prefix="captura")
        self.local = threading.local()
        self.geo: dict[int, tuple[int, int, int, int]] = {}

    def _sct(self):
        s = getattr(self.local, "sct", None)
        if s is None:
            import mss

            s = (getattr(mss, "MSS", None) or mss.mss)()
            self.local.sct = s
        return s

    def _mouse(self):
        m = getattr(self.local, "mouse", None)
        if m is None:
            try:
                from pynput import mouse

                m = mouse.Controller()
            except Exception:
                m = False
            self.local.mouse = m
        return m

    def _info(self) -> list[dict]:
        sct = self._sct()
        res = []
        for i, m in enumerate(sct.monitors[1:], start=1):
            self.geo[i] = (m["left"], m["top"], m["width"], m["height"])
            res.append({"i": i, "w": m["width"], "h": m["height"]})
        return res

    def _frame(self, ancho: int, calidad: int, idx: int, ult: bytes | None):
        from PIL import Image, ImageDraw

        sct = self._sct()
        mons = sct.monitors
        if not (1 <= idx < len(mons)):
            idx = 1
        mon = mons[idx]
        self.geo[idx] = (mon["left"], mon["top"], mon["width"], mon["height"])
        shot = sct.grab(mon)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        w, h = img.size
        if w > ancho:
            img = img.resize((ancho, max(1, round(h * ancho / w))), Image.BILINEAR, reducing_gap=2.0)
        # dibujar el puntero (mss no lo captura)
        pos = None
        m = self._mouse()
        if m:
            try:
                pos = m.position
            except Exception:
                pos = None
        if pos:
            nx = (pos[0] - mon["left"]) / mon["width"]
            ny = (pos[1] - mon["top"]) / mon["height"]
            if 0 <= nx <= 1 and 0 <= ny <= 1:
                s = max(12, img.width // 60) / 19.0
                base = [(0, 0), (0, 16), (4, 12), (7, 19), (10, 18), (7, 11), (12, 11)]
                x0, y0 = nx * img.width, ny * img.height
                pts = [(x0 + px * s, y0 + py * s) for px, py in base]
                d = ImageDraw.Draw(img)
                d.polygon(pts, fill=(255, 255, 255), outline=(0, 0, 0))
        hsh = hashlib.blake2b(img.tobytes(), digest_size=8).digest()
        if hsh == ult:
            return None, hsh, img.size
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=calidad)
        return buf.getvalue(), hsh, img.size

    async def info(self):
        return await asyncio.get_running_loop().run_in_executor(self.pool, self._info)

    async def frame(self, ancho, calidad, idx, ult):
        return await asyncio.get_running_loop().run_in_executor(self.pool, self._frame, ancho, calidad, idx, ult)


# ───────────────────────────── Mouse y teclado ─────────────────────────────

ALIAS_TECLAS = {
    "ctrl": "ctrl", "control": "ctrl", "shift": "shift", "alt": "alt", "opt": "alt", "option": "alt",
    "win": "cmd", "cmd": "cmd", "super": "cmd", "meta": "cmd",
    "enter": "enter", "return": "enter", "esc": "esc", "escape": "esc",
    "del": "delete", "supr": "delete", "bksp": "backspace", "pgup": "page_up", "pageup": "page_up",
    "pgdn": "page_down", "pagedown": "page_down", "printscreen": "print_screen", "prtsc": "print_screen",
}


class Entrada:
    """Mouse + teclado. Todo en UN hilo con cola FIFO para conservar el orden."""

    def __init__(self):
        self.pool = ThreadPoolExecutor(1, thread_name_prefix="entrada")
        self._m = None
        self._k = None
        self._Key = None
        self._Button = None
        self.ax = 0.0
        self.ay = 0.0

    def _init(self):
        if self._m is None:
            from pynput import keyboard, mouse

            self._m = mouse.Controller()
            self._k = keyboard.Controller()
            self._Key = keyboard.Key
            self._Button = mouse.Button

    def enviar(self, fn, *args):
        fut = asyncio.get_running_loop().run_in_executor(self.pool, self._seguro, fn, args)
        return fut

    def _seguro(self, fn, args):
        try:
            self._init()
            return fn(*args)
        except Exception as e:  # no tumbar el hilo
            print(f"⚠ entrada: {type(e).__name__}: {e}")
            raise

    # ---- mouse
    def mover_rel(self, dx, dy):
        self._m.move(int(dx), int(dy))

    def mover_abs(self, x, y):
        self._m.position = (int(x), int(y))

    def _btn(self, b):
        return {"l": self._Button.left, "r": self._Button.right, "m": self._Button.middle}.get(b, self._Button.left)

    def clic(self, b, n):
        self._m.click(self._btn(b), int(n))

    def abajo(self, b):
        self._m.press(self._btn(b))

    def arriba(self, b):
        self._m.release(self._btn(b))

    def rueda(self, dx, dy):
        self.ax += (-dx) / PX_POR_CLIC
        self.ay += dy / PX_POR_CLIC
        ix, iy = int(self.ax), int(self.ay)
        if ix or iy:
            self.ax -= ix
            self.ay -= iy
            self._m.scroll(ix, iy)

    # ---- teclado
    def _tecla(self, nombre):
        n = str(nombre)
        if len(n) == 1:
            return n
        n = ALIAS_TECLAS.get(n.lower(), n.lower())
        k = getattr(self._Key, n, None)
        if k is None:
            raise ValueError(f"tecla desconocida: {nombre}")
        return k

    def tecla(self, nombre, mods):
        k = self._tecla(nombre)
        ms = [self._tecla(m) for m in (mods or [])]
        for m in ms:
            self._k.press(m)
        try:
            self._k.press(k)
            self._k.release(k)
        finally:
            for m in reversed(ms):
                self._k.release(m)

    def combo(self, teclas):
        ks = [self._tecla(t) for t in teclas]
        hechas = []
        try:
            for k in ks:
                self._k.press(k)
                hechas.append(k)
        finally:
            for k in reversed(hechas):
                self._k.release(k)

    def escribir(self, texto):
        self._k.type(texto)

    def pegar(self, texto):
        import pyperclip

        try:
            pyperclip.copy(texto)
        except pyperclip.PyperclipException:
            raise RuntimeError("Falta el portapapeles (en Linux instala xclip)")
        time.sleep(0.05)
        self.combo(["cmd" if SISTEMA == "Darwin" else "ctrl", "v"])


# ───────────────────────────── Acciones del sistema ─────────────────────────────

def _lanzar(args, shell=False):
    kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=shell)
    if SISTEMA == "Windows":
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    subprocess.Popen(args, **kw)


def _osascript(script):
    _lanzar(["osascript", "-e", script])


def accion_sistema(nombre: str, entrada: Entrada) -> None:
    """Ejecuta una acción (corre en el hilo de entrada para las que usan teclas)."""
    teclas = {
        "vol_up": "media_volume_up", "vol_down": "media_volume_down", "mute": "media_volume_mute",
        "play": "media_play_pause", "next": "media_next", "prev": "media_previous",
    }
    if nombre in ("vol_up", "vol_down", "mute"):
        if SISTEMA == "Darwin":
            if nombre == "mute":
                return _osascript("set volume output muted not (output muted of (get volume settings))")
            signo = "+" if nombre == "vol_up" else "-"
            return _osascript(
                f"set volume output volume ((output volume of (get volume settings)) {signo} 6)"
            )
        if SISTEMA == "Linux" and shutil.which("pactl"):
            if nombre == "mute":
                return _lanzar(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])
            return _lanzar(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%" if nombre == "vol_up" else "-5%"])
    if nombre in teclas:
        return entrada.tecla(teclas[nombre], [])

    W, M, L = SISTEMA == "Windows", SISTEMA == "Darwin", SISTEMA == "Linux"
    if nombre == "lock":
        if W:
            return _lanzar(["rundll32.exe", "user32.dll,LockWorkStation"])
        if M:
            return _lanzar(["pmset", "displaysleepnow"])
        if shutil.which("loginctl"):
            return _lanzar(["loginctl", "lock-session"])
        return _lanzar(["xdg-screensaver", "lock"])
    if nombre == "monitor_off":
        if W:
            import ctypes

            return ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
        if M:
            return _lanzar(["pmset", "displaysleepnow"])
        return _lanzar(["xset", "dpms", "force", "off"])
    if nombre == "sleep":
        if W:
            return _lanzar(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        if M:
            return _lanzar(["pmset", "sleepnow"])
        return _lanzar(["systemctl", "suspend"])
    if nombre == "restart":
        if W:
            return _lanzar(["shutdown", "/r", "/t", "5"])
        if M:
            return _osascript('tell app "System Events" to restart')
        return _lanzar(["systemctl", "reboot"])
    if nombre == "shutdown":
        if W:
            return _lanzar(["shutdown", "/s", "/t", "5"])
        if M:
            return _osascript('tell app "System Events" to shut down')
        return _lanzar(["systemctl", "poweroff"])
    raise ValueError(f"acción desconocida: {nombre}")


def abrir_en_pc(ruta: str) -> None:
    if SISTEMA == "Windows":
        os.startfile(ruta)  # type: ignore[attr-defined]
    elif SISTEMA == "Darwin":
        _lanzar(["open", ruta])
    else:
        _lanzar(["xdg-open", ruta])


def estado() -> dict:
    d = {"host": socket.gethostname()}
    try:
        import psutil

        b = psutil.sensors_battery()
        if b is not None:
            d["bateria"] = round(b.percent)
            d["cargando"] = bool(b.power_plugged)
    except Exception:
        pass
    return d


# ───────────────────────────── Servidor ─────────────────────────────

class Cliente:
    def __init__(self, cfg):
        self.ancho = 960
        self.calidad = 58
        self.fps = 12
        self.monitor = int(cfg.get("monitor", 1))
        self.activo = False
        self.ack = asyncio.Event()
        self.ultimo_input = time.monotonic()
        self.despertar = asyncio.Event()


def crear_app(cfg: dict) -> web.Application:
    guardia = Guardia(cfg["token"])
    pantalla = Pantalla()
    entrada = Entrada()
    raices = [Path(p).expanduser().resolve() for p in cfg["carpetas"] if Path(p).expanduser().exists()]
    if not raices:
        raices = [Path.home().resolve()]
    tickets: dict[str, tuple[Path, float]] = {}
    atajos: list[dict] = cfg.get("atajos", [])

    def permitido(p: Path) -> bool:
        for r in raices:
            try:
                p.relative_to(r)
                return True
            except ValueError:
                pass
        return False

    def ruta_segura(txt: str | None) -> Path:
        p = Path(txt).expanduser() if txt else raices[0]
        p = p.resolve()
        if not permitido(p):
            raise web.HTTPForbidden(text="Carpeta fuera de las permitidas")
        return p

    # ---- middleware
    @web.middleware
    async def seguridad(request: web.Request, handler):
        ip = request.remote or ""
        if cfg["solo_redes_privadas"] and not es_red_privada(ip):
            return web.Response(status=403, text="Red no permitida")
        if request.path.startswith("/api/"):
            h = request.headers.get("Authorization", "")
            tok = h[7:].strip() if h.lower().startswith("bearer ") else ""
            if not guardia.verificar(ip, tok):
                return web.json_response({"error": "no autorizado"}, status=401)
        resp = await handler(request)
        if isinstance(resp, web.WebSocketResponse):
            return resp
        resp.headers.setdefault("Cache-Control", "no-store" if request.path.startswith(("/api/", "/dl/")) else "no-cache")
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    # ---- páginas
    async def indice(request):
        return web.FileResponse(WEB / "index.html")

    async def manifiesto(request):
        t = request.query.get("t", "")
        inicio = "/"
        if t and hmac.compare_digest(t.encode(), cfg["token"].encode()):
            inicio = "/#t=" + quote(t)
        data = {
            "id": "/", "name": "Mando PC", "short_name": "Mando PC", "lang": "es",
            "start_url": inicio, "scope": "/", "display": "standalone", "orientation": "any",
            "background_color": "#0b0f14", "theme_color": "#0b0f14",
            "icons": [
                {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                {"src": "/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            ],
        }
        return web.json_response(data, content_type="application/manifest+json")

    async def parear(request: web.Request):
        h = request.headers
        host = h.get("Host", "")
        nombre = host if host.endswith("]") else host.rsplit(":", 1)[0]
        proxied = any(x in h for x in ("X-Forwarded-For", "Forwarded", "CF-Connecting-IP", "X-Real-IP", "Tailscale-User-Login"))
        if request.remote not in ("127.0.0.1", "::1") or proxied or nombre not in ("localhost", "127.0.0.1", "[::1]"):
            return web.Response(status=403, text="Esta página solo se abre desde la propia laptop.")
        import qrcode
        import qrcode.image.svg

        puerto = cfg["puerto"]
        bloques = []
        for etiqueta, ip in direcciones_locales():
            url = f"http://{ip}:{puerto}/#t={quote(cfg['token'])}"
            qr = qrcode.QRCode(border=2, box_size=8)
            qr.add_data(url)
            qr.make(fit=True)
            svg = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage).to_string().decode()
            svg = svg[svg.index("<svg"):]
            bloques.append(
                f'<div class="c"><h3>{etiqueta}</h3><div class="qr">{svg}</div>'
                f'<code>{ip}:{puerto}</code></div>'
            )
        if not bloques:
            bloques.append("<p>No encontré ninguna red. Conecta la laptop al Wi-Fi.</p>")
        html = f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Emparejar celular — Mando PC</title>
<style>body{{font:16px system-ui;background:#0b0f14;color:#e6edf5;margin:0;padding:24px;max-width:900px;margin:auto}}
h1{{margin:0 0 4px}}p{{color:#8b9bb0}}.g{{display:flex;flex-wrap:wrap;gap:16px}}
.c{{background:#121821;border:1px solid #243040;border-radius:14px;padding:16px;width:290px}}
.c h3{{margin:0 0 10px;font-size:15px}}.qr{{background:#fff;border-radius:8px;padding:6px;line-height:0}}.qr svg{{width:100%;height:auto}}
code{{display:block;margin-top:10px;color:#3ddc97}}.t{{margin-top:24px;word-break:break-all}}
ol{{color:#c5d1e0;line-height:1.7}}</style>
<h1>Mando PC</h1><p>Empareja tu celular (solo se ve desde esta laptop).</p>
<ol><li>Abre la <b>cámara del iPhone</b> y apunta al código QR de tu red.</li>
<li>Toca el aviso para abrir el enlace en Safari.</li>
<li>Toca <b>Compartir → Agregar a inicio</b> para instalarla como app.</li></ol>
<div class=g>{''.join(bloques)}</div>
<div class=t><p>Si no puedes escanear, en la app pega este código:</p><code>{cfg['token']}</code></div>"""
        return web.Response(text=html, content_type="text/html")

    # ---- API de archivos
    async def api_ls(request: web.Request):
        p = ruta_segura(request.query.get("path"))
        if not p.is_dir():
            raise web.HTTPBadRequest(text="No es una carpeta")
        ocultos = request.query.get("ocultos") == "1"
        items = []
        try:
            with os.scandir(p) as it:
                for e in it:
                    if not ocultos and e.name.startswith("."):
                        continue
                    try:
                        st = e.stat()
                        es_dir = e.is_dir()
                        items.append({"n": e.name, "d": es_dir, "s": 0 if es_dir else st.st_size, "m": int(st.st_mtime)})
                    except OSError:
                        continue
        except PermissionError:
            raise web.HTTPForbidden(text="Sin permiso para leer esta carpeta")
        items.sort(key=lambda x: (not x["d"], x["n"].lower()))
        padre = str(p.parent) if p != raices[0] and permitido(p.parent) else None
        home = raices[0]
        rapidos = []
        for etiqueta, sub in (("Inicio", ""), ("Escritorio", "Desktop"), ("Documentos", "Documents"), ("Descargas", "Downloads")):
            q = home / sub if sub else home
            if q.is_dir():
                rapidos.append({"n": etiqueta, "p": str(q)})
        for r in raices[1:]:
            rapidos.append({"n": r.name or str(r), "p": str(r)})
        return web.json_response({"path": str(p), "parent": padre, "items": items, "rapidos": rapidos})

    async def api_ticket(request: web.Request):
        body = await request.json()
        p = ruta_segura(body.get("path"))
        if not p.is_file():
            raise web.HTTPBadRequest(text="No es un archivo")
        ahora = time.time()
        for k in [k for k, (_, exp) in tickets.items() if exp < ahora]:
            tickets.pop(k, None)
        tk = secrets.token_urlsafe(18)
        tickets[tk] = (p, ahora + 180)
        return web.json_response({"url": f"/dl/{tk}"})

    async def descargar(request: web.Request):
        reg = tickets.get(request.match_info["tk"])
        if not reg or reg[1] < time.time():
            raise web.HTTPNotFound(text="Enlace vencido")
        p = reg[0]
        if not p.is_file() or not permitido(p.resolve()):
            raise web.HTTPNotFound()
        resp = web.FileResponse(p)
        resp.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(p.name)}"
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        resp.content_type = ctype
        return resp

    async def api_abrir(request: web.Request):
        body = await request.json()
        p = ruta_segura(body.get("path"))
        abrir_en_pc(str(p))
        return web.json_response({"ok": True})

    async def api_subir(request: web.Request):
        q = request.query.get("dir")
        try:
            destino = ruta_segura(q) if q else Path(cfg["carpeta_subidas"]).expanduser()
        except web.HTTPForbidden:
            destino = Path(cfg["carpeta_subidas"]).expanduser()
        destino.mkdir(parents=True, exist_ok=True)
        limite = int(cfg["limite_subida_mb"]) * 1024 * 1024
        lector = await request.multipart()
        guardados = []
        while True:
            parte = await lector.next()
            if parte is None:
                break
            if not parte.filename:
                continue
            nombre = "".join(c for c in os.path.basename(parte.filename.replace("\\", "/")) if c not in '<>:"|?*\x00') or "archivo"
            dest = destino / nombre
            i = 1
            while dest.exists():
                dest = destino / f"{Path(nombre).stem} ({i}){Path(nombre).suffix}"
                i += 1
            total = 0
            with open(dest, "wb") as f:
                while True:
                    trozo = await parte.read_chunk(1 << 20)
                    if not trozo:
                        break
                    total += len(trozo)
                    if total > limite:
                        f.close()
                        dest.unlink(missing_ok=True)
                        raise web.HTTPRequestEntityTooLarge(max_size=limite, actual_size=total)
                    f.write(trozo)
            guardados.append(dest.name)
        return web.json_response({"ok": True, "archivos": guardados, "carpeta": str(destino)})

    # ---- WebSocket
    async def info_hello(cl: Cliente):
        mons = await pantalla.info()
        sel = next((m for m in mons if m["i"] == cl.monitor), mons[0] if mons else {"i": 1, "w": 1920, "h": 1080})
        cl.monitor = sel["i"]
        return {
            "t": "hello", "version": VERSION, "os": {"Windows": "win", "Darwin": "mac"}.get(SISTEMA, "linux"),
            "monitores": len(mons), "monitor": sel["i"], "pantalla": {"w": sel["w"], "h": sel["h"]},
            "atajos": [{"n": a.get("nombre", "?"), "i": a.get("icono", "⚡")} for a in atajos],
            **estado(),
        }

    async def bucle_pantalla(ws: web.WebSocketResponse, cl: Cliente):
        ult = None
        try:
            while not ws.closed:
                if not cl.activo:
                    cl.despertar.clear()
                    await cl.despertar.wait()
                    ult = None
                    continue
                t0 = time.monotonic()
                try:
                    datos, ult, _ = await pantalla.frame(cl.ancho, cl.calidad, cl.monitor, ult)
                except Exception as e:
                    await ws.send_json({"t": "err", "m": f"No pude capturar la pantalla: {e}"})
                    await asyncio.sleep(2)
                    continue
                if datos is not None:
                    cl.ack.clear()
                    await ws.send_bytes(b"\x01" + datos)
                    try:
                        await asyncio.wait_for(cl.ack.wait(), 3)
                    except asyncio.TimeoutError:
                        pass
                activo_reciente = time.monotonic() - cl.ultimo_input < 3
                intervalo = 1 / cl.fps if (datos is not None or activo_reciente) else 0.25
                await asyncio.sleep(max(0.0, intervalo - (time.monotonic() - t0)))
        except (asyncio.CancelledError, ConnectionResetError):
            pass

    async def bucle_estado(ws: web.WebSocketResponse):
        try:
            while not ws.closed:
                await asyncio.sleep(15)
                await ws.send_json({"t": "estado", **estado()})
        except (asyncio.CancelledError, ConnectionResetError):
            pass

    def geo_de(cl: Cliente):
        return pantalla.geo.get(cl.monitor)

    async def operar(ws, cl: Cliente, m: dict):
        op = m.get("op")
        if op == "ack":
            cl.ack.set()
            return
        if op == "ping":
            await ws.send_json({"t": "pong", "ts": m.get("ts")})
            return
        cl.ultimo_input = time.monotonic()
        cl.despertar.set()
        if op == "mv":
            entrada.enviar(entrada.mover_rel, float(m.get("dx", 0)), float(m.get("dy", 0)))
        elif op == "abs":
            g = geo_de(cl)
            if g:
                x = g[0] + min(max(float(m["x"]), 0), 1) * (g[2] - 1)
                y = g[1] + min(max(float(m["y"]), 0), 1) * (g[3] - 1)
                entrada.enviar(entrada.mover_abs, x, y)
        elif op == "clk":
            entrada.enviar(entrada.clic, m.get("b", "l"), int(m.get("n", 1)))
        elif op == "dn":
            entrada.enviar(entrada.abajo, m.get("b", "l"))
        elif op == "up":
            entrada.enviar(entrada.arriba, m.get("b", "l"))
        elif op == "scr":
            entrada.enviar(entrada.rueda, float(m.get("dx", 0)), float(m.get("dy", 0)))
        elif op == "key":
            entrada.enviar(entrada.tecla, m["k"], m.get("m", []))
        elif op == "combo":
            entrada.enviar(entrada.combo, list(m["keys"]))
        elif op == "txt":
            entrada.enviar(entrada.escribir, str(m["s"])[:20000])
        elif op == "paste":
            entrada.enviar(entrada.pegar, str(m["s"])[:200000])
        elif op == "getclip":
            import pyperclip

            try:
                txt = await asyncio.get_running_loop().run_in_executor(None, pyperclip.paste)
            except pyperclip.PyperclipException:
                raise RuntimeError("Falta el portapapeles (en Linux instala xclip)")
            await ws.send_json({"t": "clip", "s": txt[:200000]})
        elif op == "act":
            await entrada.enviar(accion_sistema, str(m["n"]), entrada)
        elif op == "url":
            u = str(m.get("u", "")).strip()
            if urlsplit(u).scheme not in ("http", "https"):
                u = "https://" + u
            if urlsplit(u).scheme in ("http", "https") and urlsplit(u).netloc:
                webbrowser.open(u)
        elif op == "sc":
            a = atajos[int(m["i"])]
            if a.get("teclas"):
                entrada.enviar(entrada.combo, a["teclas"])
            elif a.get("ejecutar"):
                _lanzar(a["ejecutar"], shell=True)
            elif a.get("url"):
                webbrowser.open(a["url"])
        elif op == "screen":
            cl.ancho = min(max(int(m.get("w", cl.ancho)), 320), 2400)
            cl.calidad = min(max(int(m.get("q", cl.calidad)), 20), 90)
            cl.fps = min(max(int(m.get("fps", cl.fps)), 1), 30)
            cl.activo = bool(m.get("on", True))
            cl.ack.set()
        elif op == "monitor":
            cl.monitor = int(m.get("i", 1))
            mons = await pantalla.info()
            sel = next((x for x in mons if x["i"] == cl.monitor), None)
            if sel:
                await ws.send_json({"t": "monitor", "i": sel["i"], "pantalla": {"w": sel["w"], "h": sel["h"]}})
            cl.ack.set()

    async def ws_handler(request: web.Request):
        origen = request.headers.get("Origin")
        if origen and urlsplit(origen).netloc != request.headers.get("Host"):
            return web.Response(status=403, text="Origen no permitido")
        ws = web.WebSocketResponse(heartbeat=20, max_msg_size=4 * 1024 * 1024)
        await ws.prepare(request)
        ip = request.remote or ""
        try:
            msg = await asyncio.wait_for(ws.receive(), 6)
            datos = json.loads(msg.data) if msg.type == WSMsgType.TEXT else {}
        except Exception:
            await ws.close()
            return ws
        if datos.get("op") != "auth" or not guardia.verificar(ip, str(datos.get("token", ""))):
            await ws.send_json({"t": "denegado"})
            await ws.close()
            return ws
        if not cfg.get("emparejado"):
            cfg["emparejado"] = True
            guardar_config(cfg)
        cl = Cliente(cfg)
        await ws.send_json(await info_hello(cl))
        t1 = asyncio.create_task(bucle_pantalla(ws, cl))
        t2 = asyncio.create_task(bucle_estado(ws))
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                try:
                    await operar(ws, cl, json.loads(msg.data))
                except Exception as e:
                    await ws.send_json({"t": "err", "m": f"{type(e).__name__}: {e}"})
        finally:
            t1.cancel()
            t2.cancel()
            cl.despertar.set()
        return ws

    app = web.Application(middlewares=[seguridad])
    app.router.add_get("/", indice)
    app.router.add_get("/manifest.webmanifest", manifiesto)
    app.router.add_get("/pair", parear)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/api/ls", api_ls)
    app.router.add_post("/api/ticket", api_ticket)
    app.router.add_post("/api/abrir", api_abrir)
    app.router.add_post("/api/subir", api_subir)
    app.router.add_get("/dl/{tk}", descargar)
    app.router.add_static("/", WEB, follow_symlinks=False)
    return app


# ───────────────────────────── Arranque ─────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Mando PC: controla tu laptop desde el celular")
    ap.add_argument("--puerto", type=int, help="puerto (por defecto 8765)")
    ap.add_argument("--nuevo-token", action="store_true", help="invalida los celulares emparejados y crea un token nuevo")
    ap.add_argument("--parear", action="store_true", help="abrir la página de emparejamiento")
    args = ap.parse_args()

    cfg = cargar_config()
    if args.nuevo_token:
        cfg["token"] = secrets.token_urlsafe(24)
        cfg["emparejado"] = False
        guardar_config(cfg)
        print("🔑 Token nuevo creado. Los celulares anteriores ya no pueden entrar; vuelve a emparejarlos.")
    if args.puerto:
        cfg["puerto"] = args.puerto
    puerto = int(cfg["puerto"])

    app = crear_app(cfg)
    print(f"\n  Mando PC {VERSION} — {platform.node()} ({SISTEMA})")
    print("  ───────────────────────────────────────────")
    for etiqueta, ip in direcciones_locales():
        print(f"  {etiqueta}:  http://{ip}:{puerto}")
    print(f"\n  Emparejar celular:  http://localhost:{puerto}/pair   (solo se abre en esta laptop)")
    print("  Para detener: Ctrl+C\n")

    async def al_iniciar(_app):
        if args.parear or not cfg.get("emparejado"):
            asyncio.get_running_loop().call_later(1.0, webbrowser.open, f"http://localhost:{puerto}/pair")

    app.on_startup.append(al_iniciar)
    try:
        web.run_app(app, host="0.0.0.0", port=puerto, print=None, access_log=None)
    except OSError as e:
        print(f"✗ No pude abrir el puerto {puerto}: {e}\n  ¿Ya está corriendo Mando PC? Prueba con --puerto 8766")
        sys.exit(1)


if __name__ == "__main__":
    main()
