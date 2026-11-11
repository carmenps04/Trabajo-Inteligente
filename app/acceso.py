"""
acceso.py -- login con una sola contraseña.

La app es para una sola persona, así que no hay usuarios: una
contraseña (APP_PASSWORD) y una cookie de sesión firmada con HMAC.

- Sin APP_PASSWORD (uso en tu PC): no hay login, todo como antes.
- En Cloud Run (variable K_SERVICE, la pone Google): la app NO arranca
  sin una contraseña de al menos LONGITUD_MINIMA caracteres, para que
  nunca quede publicada sin protección por un descuido.

Las variables se leen en cada petición (no al importar) para que los
tests y un cambio del .env no dependan del orden de importación.
"""

import asyncio
import hashlib
import hmac
import html
import os
import time
from typing import Optional
from urllib.parse import parse_qs, quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

COOKIE = "ji_sesion"
DURACION_SEGUNDOS = 30 * 24 * 3600
LONGITUD_MINIMA = 12
ESPERA_TRAS_FALLO = 1.0  # frena los intentos de adivinar la contraseña

# Rutas que se pueden abrir sin sesión.
RUTAS_LIBRES = {"/login", "/logout", "/icono.svg", "/favicon.ico", "/api/sesion"}

router = APIRouter()


def contrasena() -> Optional[str]:
    return os.environ.get("APP_PASSWORD") or None


def en_la_nube() -> bool:
    return bool(os.environ.get("K_SERVICE"))


def verificar_config() -> None:
    """Se llama al arrancar el servidor. Falla si la app quedaría abierta en la nube."""
    if not en_la_nube():
        return
    clave = contrasena()
    if not clave:
        raise RuntimeError("Falta APP_PASSWORD: la app no arranca en Cloud Run sin contraseña.")
    if len(clave) < LONGITUD_MINIMA:
        raise RuntimeError(f"APP_PASSWORD debe tener al menos {LONGITUD_MINIMA} caracteres.")


def _clave_firma(clave: str) -> bytes:
    # Derivada de la contraseña: si la cambias, todas las sesiones caducan.
    return hashlib.sha256(("ji-sesion:" + clave).encode()).digest()


def crear_token(clave: str, ahora: Optional[float] = None) -> str:
    vence = int((ahora or time.time()) + DURACION_SEGUNDOS)
    firma = hmac.new(_clave_firma(clave), str(vence).encode(), hashlib.sha256).hexdigest()
    return f"{vence}.{firma}"


def token_valido(token: Optional[str], clave: str, ahora: Optional[float] = None) -> bool:
    if not token or "." not in token:
        return False
    vence, firma = token.split(".", 1)
    if not vence.isdigit():
        return False
    esperada = hmac.new(_clave_firma(clave), vence.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(firma, esperada) and int(vence) > (ahora or time.time())


def destino_seguro(siguiente: Optional[str]) -> str:
    """Solo rutas de esta misma app: evita redirigir a otra web tras el login."""
    if siguiente and siguiente.startswith("/") and not siguiente.startswith("//") and "\\" not in siguiente:
        return siguiente
    return "/"


def sesion_activa(request: Request) -> bool:
    clave = contrasena()
    return clave is None or token_valido(request.cookies.get(COOKIE), clave)


async def exigir_sesion(request: Request, call_next):
    """Middleware: sin sesión, la API responde 401 y las páginas llevan al login."""
    ruta = request.url.path
    if contrasena() is None or ruta in RUTAS_LIBRES or sesion_activa(request):
        return await call_next(request)
    if ruta.startswith("/api") or request.method != "GET":
        return JSONResponse({"detail": "Tu sesión ha caducado. Vuelve a entrar."}, status_code=401)
    actual = ruta + (f"?{request.url.query}" if request.url.query else "")
    return RedirectResponse(f"/login?siguiente={quote(actual, safe='')}", status_code=303)


def _pagina_login(siguiente: str, error: str = "") -> str:
    aviso = f'<p class="error">{html.escape(error)}</p>' if error else ""
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Entrar · Job-Intelligence</title>
<style>
  :root {{ color-scheme: light dark; --bg:#f6f7f9; --card:#fff; --ink:#1b1f24; --line:#d9dde3; --acc:#1f5fbf; --bad:#b42318; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg:#111418; --card:#1a1e24; --ink:#e8eaed; --line:#30363d; --acc:#5b9bf0; --bad:#f97066; }} }}
  body {{ margin:0; min-height:100vh; display:grid; place-items:center; background:var(--bg); color:var(--ink);
         font:16px/1.5 system-ui, sans-serif; padding:16px; box-sizing:border-box; }}
  form {{ width:100%; max-width:340px; background:var(--card); border:1px solid var(--line); border-radius:8px; padding:24px; }}
  h1 {{ font-size:20px; margin:0 0 16px; }}
  label {{ display:block; font-size:14px; margin-bottom:6px; }}
  input {{ width:100%; box-sizing:border-box; padding:10px; border:1px solid var(--line); border-radius:6px;
          background:transparent; color:inherit; font-size:16px; }}
  button {{ margin-top:16px; width:100%; padding:10px; border:0; border-radius:6px; background:var(--acc);
           color:#fff; font-size:16px; cursor:pointer; }}
  .error {{ color:var(--bad); font-size:14px; margin:0 0 12px; }}
</style></head>
<body><form method="post" action="/login">
  <h1>Job-Intelligence</h1>{aviso}
  <input type="hidden" name="siguiente" value="{html.escape(siguiente)}">
  <label for="clave">Contraseña</label>
  <input id="clave" name="clave" type="password" autocomplete="current-password" autofocus required>
  <button type="submit">Entrar</button>
</form></body></html>"""


@router.get("/login", include_in_schema=False)
def ver_login(siguiente: str = "/"):
    if contrasena() is None:
        return RedirectResponse("/", status_code=303)
    return HTMLResponse(_pagina_login(destino_seguro(siguiente)))


@router.post("/login", include_in_schema=False)
async def entrar(request: Request):
    clave = contrasena()
    if clave is None:
        return RedirectResponse("/", status_code=303)
    # Formulario normal; se lee a mano para no depender de python-multipart.
    campos = parse_qs((await request.body())[:4096].decode("utf-8", errors="replace"))
    enviada = (campos.get("clave") or [""])[0]
    siguiente = destino_seguro((campos.get("siguiente") or ["/"])[0])
    if not hmac.compare_digest(enviada.encode(), clave.encode()):
        await asyncio.sleep(ESPERA_TRAS_FALLO)
        return HTMLResponse(_pagina_login(siguiente, "Contraseña incorrecta."), status_code=401)
    respuesta = RedirectResponse(siguiente, status_code=303)
    respuesta.set_cookie(
        COOKIE, crear_token(clave), max_age=DURACION_SEGUNDOS, httponly=True, samesite="lax",
        secure=en_la_nube() or request.headers.get("x-forwarded-proto") == "https", path="/",
    )
    return respuesta


@router.post("/logout", include_in_schema=False)
def salir():
    respuesta = RedirectResponse("/login", status_code=303)
    respuesta.delete_cookie(COOKIE, path="/")
    return respuesta


@router.get("/api/sesion")
def estado_sesion(request: Request):
    """Para el frontend: ¿hay login y estoy dentro? (para mostrar "Cerrar sesión")."""
    return {"con_login": contrasena() is not None, "activa": sesion_activa(request)}
