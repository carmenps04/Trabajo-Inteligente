"""app/almacen.py: archivos en el PC, tabla `almacen` en Supabase."""

import pytest

from app import almacen
from app.cv.cargador import RAIZ


class BDFalsa:
    """Imita lo justo de psycopg2 para las tres consultas de almacen."""

    def __init__(self):
        self.filas: dict[str, bytes] = {}

    def conexion(self):
        bd = self

        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *a): return False

            def execute(self, sql, params):
                self.resultado = None
                clave = params[0]
                if sql.startswith("SELECT contenido"):
                    self.resultado = (memoryview(bd.filas[clave]),) if clave in bd.filas else None
                elif sql.startswith("SELECT 1"):
                    self.resultado = (1,) if clave in bd.filas else None
                elif sql.startswith("INSERT"):
                    bd.filas[clave] = bytes(getattr(params[1], "adapted", params[1]))
                elif sql.startswith("DELETE"):
                    bd.filas.pop(clave, None)

            def fetchone(self): return self.resultado

        class Conexion:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def cursor(self): return Cursor()
            def close(self): pass

        return Conexion()


@pytest.fixture
def bd(monkeypatch):
    falsa = BDFalsa()
    import app.repository
    monkeypatch.setattr(app.repository, "get_connection", falsa.conexion)
    monkeypatch.setenv("ALMACEN", "supabase")
    return falsa


def test_por_defecto_archivos_y_en_cloud_run_supabase(monkeypatch):
    assert almacen.modo() == "archivos"
    monkeypatch.setenv("K_SERVICE", "job-intelligence")
    assert almacen.modo() == "supabase"
    monkeypatch.setenv("ALMACEN", "archivos")  # se puede forzar
    assert almacen.modo() == "archivos"


def test_valor_de_almacen_invalido(monkeypatch):
    monkeypatch.setenv("ALMACEN", "dropbox")
    with pytest.raises(ValueError):
        almacen.modo()


def test_modo_archivos(tmp_path):
    ruta = tmp_path / "sub" / "cv.yaml"
    assert not almacen.existe(ruta)
    with pytest.raises(FileNotFoundError):
        almacen.leer_texto(ruta)
    almacen.escribir_texto(ruta, "nombre: Ñandú")
    assert almacen.existe(ruta)
    assert almacen.leer_texto(ruta) == "nombre: Ñandú"
    assert not list(tmp_path.rglob("*.tmp"))  # no deja temporales
    almacen.borrar(ruta)
    assert not almacen.existe(ruta)
    almacen.borrar(ruta)  # borrar lo que no existe no falla


def test_modo_supabase(bd):
    ruta = RAIZ / "data" / "cv_base.yaml"
    assert not almacen.existe(ruta)
    with pytest.raises(FileNotFoundError):
        almacen.leer_bytes(ruta)
    almacen.escribir_texto(ruta, "nombre: Ñandú")
    assert bd.filas == {"data/cv_base.yaml": "nombre: Ñandú".encode()}
    assert almacen.leer_texto(ruta) == "nombre: Ñandú"
    almacen.escribir_bytes(ruta, b"\x00\x01")  # sobrescribe
    assert almacen.leer_bytes(ruta) == b"\x00\x01"
    almacen.borrar(ruta)
    assert not almacen.existe(ruta)


def test_clave_relativa_y_con_barras(bd):
    assert almacen.clave(RAIZ / "salidas" / "cv" / "job_4" / "CV.docx") == "salidas/cv/job_4/CV.docx"


def test_fuera_del_proyecto_no_se_guarda_en_supabase(bd, tmp_path):
    with pytest.raises(ValueError, match="fuera del proyecto"):
        almacen.escribir_texto(tmp_path / "x.txt", "x")


def test_los_datos_privados_van_a_supabase_y_no_al_disco(bd):
    """CV, respuestas, historial, plan, actividad y pendientes con ALMACEN=supabase."""
    from app import pendientes
    from app.agents import brujula, eventos
    from app.cv import cargador, historial, respuestas
    from app.cv.modelo import CVBase

    cv = CVBase.model_validate({"contacto": {"nombre": "N", "email": "n@x.es"}, "perfil": "P"})
    cargador.guardar_cv_base(cv)
    cargador.guardar_cv_base(cv)  # el segundo guardado deja respaldo
    assert cargador.cargar_cv_base().contacto.nombre == "N"

    respuestas.guardar_respuestas([respuestas.Respuesta(tecnologia="dbt", la_tengo=False)])
    assert "dbt" in respuestas.cargar_respuestas()

    historial.registrar(1, "Puesto", "Empresa", "salidas/cv/a.docx", "salidas/cv/b.docx", True)
    assert historial.versiones(1)[0]["puesto"] == "Puesto"

    eventos.registrar("lupa", "leyó", ruta=cargador.RAIZ / "data" / "actividad.jsonl")
    assert eventos.actividad_reciente(ruta=cargador.RAIZ / "data" / "actividad.jsonl")[0]["agente"] == "lupa"

    id_ = pendientes.guardar("https://x", "texto")
    assert pendientes.tomar(id_)["texto"] == "texto"
    assert pendientes.tomar(id_) is None  # se borra al tomarla

    assert brujula.cargar_plan() is None

    assert set(bd.filas) == {
        "data/cv_base.yaml", "data/cv_base.respaldo.yaml", "data/respuestas.yaml",
        "data/historial_cv.json", "data/actividad.jsonl",
    }


def test_sin_cv_en_supabase_el_mensaje_lo_explica(bd):
    from app.cv import cargador
    with pytest.raises(cargador.CVBaseNoEncontrado, match="subir_a_supabase"):
        cargador.cargar_cv_base()


def test_word_en_supabase_se_descarga_con_ruta_relativa(bd):
    from docx import Document
    from fastapi.testclient import TestClient
    from app.main import app

    doc = Document()
    doc.add_paragraph("Hola")
    ruta = almacen.guardar_docx(doc, RAIZ / "salidas" / "cv" / "job_1" / "v1" / "CV_Ñ.docx")
    relativa = almacen.para_mostrar(ruta)
    assert relativa == "salidas/cv/job_1/v1/CV_Ñ.docx"

    client = TestClient(app)
    r = client.get("/api/archivos", params={"ruta": relativa})
    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # un .docx es un zip
    assert "CV_%C3%91.docx" in r.headers["content-disposition"]

    # Nada fuera de salidas/, ni con trucos de ruta.
    almacen.escribir_texto(RAIZ / "data" / "cv_base.yaml", "secreto")
    for ruta_mala in ["data/cv_base.yaml", "salidas/../data/cv_base.yaml", "salidas/cv/no-existe.docx",
                      "C:\\Users\\x\\salidas\\cv\\CV.docx"]:
        assert client.get("/api/archivos", params={"ruta": ruta_mala}).status_code == 404


def test_flujos_pausados_en_postgres_solo_con_supabase(monkeypatch):
    from langgraph.checkpoint.memory import InMemorySaver
    from app.agents import batuta

    usados = []
    monkeypatch.setattr(batuta, "_checkpointer_postgres", lambda: usados.append("postgres") or InMemorySaver())
    monkeypatch.setattr(batuta, "_checkpointer_sqlite", lambda: usados.append("sqlite") or InMemorySaver())

    monkeypatch.setattr(batuta, "_grafo_cv", None)
    batuta._obtener_grafo_cv()
    monkeypatch.setattr(batuta, "_grafo_cv", None)
    monkeypatch.setenv("ALMACEN", "supabase")
    batuta._obtener_grafo_cv()
    assert usados == ["sqlite", "postgres"]
