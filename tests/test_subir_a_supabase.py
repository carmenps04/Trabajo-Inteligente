import json

import pytest

from scripts import subir_a_supabase as subir
from tests.test_almacen import bd  # noqa: F401  (fixture: Supabase falso)


@pytest.mark.parametrize("ruta, esperada", [
    (r"C:\Users\C a r m e n\REPOSITORIOS_GIT\Trabajo-Inteligente\salidas\cv\job_4\v1_2026\CV_Strada.docx",
     "salidas/cv/job_4/v1_2026/CV_Strada.docx"),
    ("/app/salidas/cv/job_4/CV.docx", "salidas/cv/job_4/CV.docx"),
    ("salidas/cv/job_4/CV.docx", "salidas/cv/job_4/CV.docx"),
    ("v2.docx", "v2.docx"),
    (None, None),
])
def test_rutas_del_historial_a_relativas(ruta, esperada):
    assert subir.a_relativa(ruta) == esperada


def test_sube_datos_y_salidas_sin_pisar_lo_que_ya_esta(bd, tmp_path):  # noqa: F811
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "cv_base.yaml").write_text("contacto: {}", encoding="utf-8")
    (tmp_path / "data" / "flujos.sqlite").write_bytes(b"no se sube")
    (tmp_path / "data" / "historial_cv.json").write_text(json.dumps([{
        "ruta_cv": r"C:\x\salidas\cv\job_1\CV.docx", "ruta_brechas": r"C:\x\salidas\cv\job_1\B.docx",
        "revision": {"ruta": r"C:\x\salidas\cv\job_1\cambios.json"},
    }]), encoding="utf-8")
    (tmp_path / "salidas" / "cv" / "job_1").mkdir(parents=True)
    (tmp_path / "salidas" / "cv" / "job_1" / "CV.docx").write_bytes(b"PK")
    (tmp_path / "salidas" / "cv" / "job_1" / "x.tmp").write_bytes(b"no")

    assert subir.subir(tmp_path, simular=True)["simulados"] == [
        "data/cv_base.yaml", "data/historial_cv.json", "salidas/cv/job_1/CV.docx",
    ]
    assert bd.filas == {}  # simular no escribe

    primera = subir.subir(tmp_path)
    assert len(primera["subidos"]) == 3
    historial = json.loads(bd.filas["data/historial_cv.json"])
    assert historial[0]["ruta_cv"] == "salidas/cv/job_1/CV.docx"
    assert historial[0]["revision"]["ruta"] == "salidas/cv/job_1/cambios.json"

    bd.filas["data/cv_base.yaml"] = b"editado en la nube"
    segunda = subir.subir(tmp_path)
    assert len(segunda["ya_estaban"]) == 3
    assert bd.filas["data/cv_base.yaml"] == b"editado en la nube"  # no lo pisó

    subir.subir(tmp_path, sobrescribir=True)
    assert bd.filas["data/cv_base.yaml"] == b"contacto: {}"
