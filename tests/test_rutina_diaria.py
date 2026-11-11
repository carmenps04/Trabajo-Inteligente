from scripts import rutina_diaria


def test_sabueso_desactivado_por_defecto():
    assert not rutina_diaria.debe_buscar(["rutina"], {})
    assert not rutina_diaria.debe_buscar(["rutina"], {"en_rutina_diaria": False})


def test_sabueso_activo_desde_la_config():
    assert rutina_diaria.debe_buscar(["rutina"], {"en_rutina_diaria": True})


def test_los_argumentos_mandan_sobre_la_config():
    assert rutina_diaria.debe_buscar(["rutina", "--con-sabueso"], {"en_rutina_diaria": False})
    assert not rutina_diaria.debe_buscar(["rutina", "--sin-sabueso"], {"en_rutina_diaria": True})


def test_la_config_del_repo_trae_sabueso_apagado():
    from app.agents import sabueso
    assert sabueso.cargar_config()["en_rutina_diaria"] is False


def test_la_rutina_no_llama_a_sabueso_si_esta_apagado(monkeypatch, tmp_path):
    from app.agents import centinela, sabueso
    monkeypatch.setattr(rutina_diaria, "RUTA_LOG", tmp_path / "rutina.log")
    monkeypatch.setattr(rutina_diaria.sys, "argv", ["rutina"])
    monkeypatch.setattr(sabueso, "cargar_config", lambda: {"en_rutina_diaria": False})

    def no_llamar(*a, **k):
        raise AssertionError("Sabueso no debía ejecutarse")

    monkeypatch.setattr(sabueso, "ejecutar", no_llamar)
    monkeypatch.setattr(centinela, "armar_resumen", lambda: {
        "fecha": "2026-11-11", "nuevas": [], "recordatorios": [], "dias_sin_respuesta": 7})
    monkeypatch.setattr(centinela, "guardar_resumen", lambda texto, fecha: tmp_path / "r.md")
    monkeypatch.setattr(centinela, "notificar", lambda *a: True)
    monkeypatch.setattr(rutina_diaria, "date", type("D", (), {"today": staticmethod(lambda: __import__("datetime").date(2026, 11, 11))}))
    assert rutina_diaria.main() == 0
