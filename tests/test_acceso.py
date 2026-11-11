"""Login con una sola contraseña (app/acceso.py)."""

import pytest
from fastapi.testclient import TestClient

from app import acceso
from app.main import app

CLAVE = "una-contrasena-larga-de-prueba"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def con_clave(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", CLAVE)


def test_sin_contrasena_no_hay_login(client):
    assert client.get("/api/sesion").json() == {"con_login": False, "activa": True}
    assert client.get("/login", follow_redirects=False).status_code == 303


def test_con_contrasena_la_api_pide_sesion(client, con_clave):
    r = client.get("/api/ofertas")
    assert r.status_code == 401
    assert "sesión" in r.json()["detail"]


def test_con_contrasena_las_paginas_llevan_al_login(client, con_clave):
    r = client.get("/analizar?copiada=1&url=x", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/login?siguiente=%2Fanalizar%3Fcopiada%3D1")


def test_el_marcador_por_post_tambien_exige_sesion(client, con_clave):
    r = client.post("/recibir", data={"texto": "x", "url": "y"}, follow_redirects=False)
    assert r.status_code == 401


def test_contrasena_incorrecta(client, con_clave, monkeypatch):
    monkeypatch.setattr(acceso, "ESPERA_TRAS_FALLO", 0)
    r = client.post("/login", data={"clave": "mala", "siguiente": "/"}, follow_redirects=False)
    assert r.status_code == 401
    assert acceso.COOKIE not in r.cookies


def test_login_correcto_da_sesion_y_vuelve_a_donde_ibas(client, con_clave):
    r = client.post("/login", data={"clave": CLAVE, "siguiente": "/bandeja"}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/bandeja"
    assert "httponly" in r.headers["set-cookie"].lower()
    assert client.get("/api/sesion").json() == {"con_login": True, "activa": True}


def test_logout_borra_la_sesion(client, con_clave):
    client.post("/login", data={"clave": CLAVE}, follow_redirects=False)
    client.post("/logout", follow_redirects=False)
    assert client.get("/api/sesion").json()["activa"] is False


@pytest.mark.parametrize("siguiente", ["//evil.com", "https://evil.com", "/\\evil.com", ""])
def test_no_redirige_fuera_de_la_app(siguiente):
    assert acceso.destino_seguro(siguiente) == "/"


def test_token_manipulado_o_caducado():
    token = acceso.crear_token(CLAVE, ahora=1000)
    assert acceso.token_valido(token, CLAVE, ahora=1001)
    assert not acceso.token_valido(token, "otra-clave", ahora=1001)
    vence, firma = token.split(".")
    assert not acceso.token_valido(f"{int(vence) + 1}.{firma}", CLAVE, ahora=1001)
    assert not acceso.token_valido(token, CLAVE, ahora=1000 + acceso.DURACION_SEGUNDOS + 1)
    assert not acceso.token_valido("basura", CLAVE)


def test_en_cloud_run_no_arranca_sin_contrasena(monkeypatch):
    monkeypatch.setenv("K_SERVICE", "job-intelligence")
    with pytest.raises(RuntimeError, match="APP_PASSWORD"):
        acceso.verificar_config()
    monkeypatch.setenv("APP_PASSWORD", "corta")
    with pytest.raises(RuntimeError, match="al menos"):
        acceso.verificar_config()
    monkeypatch.setenv("APP_PASSWORD", CLAVE)
    acceso.verificar_config()


def test_en_cloud_run_la_cookie_es_secure(client, con_clave, monkeypatch):
    monkeypatch.setenv("K_SERVICE", "job-intelligence")
    r = client.post("/login", data={"clave": CLAVE}, follow_redirects=False)
    assert "secure" in r.headers["set-cookie"].lower()
