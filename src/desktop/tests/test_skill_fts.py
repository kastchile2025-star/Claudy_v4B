"""Tests del índice FTS5 de skills + carga search-first (features/skill_loop.py)."""
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from features.skill_loop import SkillLoopMixin, fts_query  # noqa: E402


class FakePet(SkillLoopMixin):
    def __init__(self, root, index):
        self._root = root
        self._index = index

    def _skills_root(self):
        return self._root

    def _skills_index_path(self):
        return self._index

    def _workspace_skills_roots(self):
        return []  # cada test de workspace lo overridea

    def _debug_log(self, *a):
        pass


def _mk_skill(root, slug, description, body, mtime=None):
    folder = os.path.join(root, slug)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "SKILL.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"---\nname: {slug}\ndescription: {description}\n---\n\n{body}")
    if mtime:
        os.utime(path, (mtime, mtime))
    return path


class SkillFTSBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="claudy_skills_")
        self.root = os.path.join(self.tmp, "skills")
        os.makedirs(self.root)
        self.index = os.path.join(self.tmp, "skills_index.db")
        _mk_skill(self.root, "facturas-resumen",
                  "Resumen semanal de facturas en un xlsx",
                  "# Facturas\n\n## Pasos\n1. Buscar facturas y boletas del mes\n"
                  "2. Calcular IVA y totales\n3. Generar xlsx con el resumen")
        _mk_skill(self.root, "limpiar-descargas",
                  "Limpieza de archivos viejos en Descargas",
                  "# Limpieza\n\n## Pasos\n1. Listar instaladores antiguos\n"
                  "2. Proponer borrado a papelera de reciclaje")
        _mk_skill(self.root, "informe-mercado",
                  "Informes de mercado con fuentes verificadas",
                  "# Informe\n\n## Pasos\n1. Investigar el mercado objetivo\n"
                  "2. Redactar informe con fuentes citadas")
        self.pet = FakePet(self.root, self.index)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestIndice(SkillFTSBase):
    def test_busqueda_relevante(self):
        hits = self.pet._skills_fts_search("hazme el resumen de facturas de esta semana")
        self.assertTrue(hits)
        self.assertEqual(hits[0], "facturas-resumen")

    def test_sin_matches_devuelve_lista_vacia(self):
        self.assertEqual(self.pet._skills_fts_search("quiero jugar ajedrez online"), [])

    def test_acentos_no_importan(self):
        hits = self.pet._skills_fts_search("necesito un informe del mercado inmobiliario")
        self.assertIn("informe-mercado", hits)

    def test_reindexa_cuando_cambia_un_skill(self):
        self.assertEqual(self.pet._skills_fts_search("ajedrez"), [])
        _mk_skill(self.root, "facturas-resumen",
                  "Resumen de facturas y partidas de ajedrez",
                  "# Facturas\nAhora también cubre torneos de ajedrez",
                  mtime=time.time() + 10)
        hits = self.pet._skills_fts_search("ajedrez")
        self.assertIn("facturas-resumen", hits)

    def test_skill_eliminada_sale_del_indice(self):
        self.assertTrue(self.pet._skills_fts_search("limpieza de descargas"))
        shutil.rmtree(os.path.join(self.root, "limpiar-descargas"))
        self.assertEqual(self.pet._skills_fts_search("limpieza de descargas viejas"), [])

    def test_archive_se_ignora(self):
        _mk_skill(os.path.join(self.root), "_archive", "no", "no debería indexarse")
        slugs = [s for s, _, _ in self.pet._skills_scan()]
        self.assertNotIn("_archive", slugs)

    def test_fts_query_segura(self):
        self.assertEqual(fts_query(""), "")
        self.assertIn('"facturas"', fts_query("facturas; DROP TABLE--"))


class TestWorkspaceSkills(SkillFTSBase):
    """B2: skills de proyecto pisan a las globales por slug."""

    def setUp(self):
        super().setUp()
        self.ws = os.path.join(self.tmp, "proyecto", ".claudy-skills")
        os.makedirs(self.ws)
        self.pet._workspace_skills_roots = lambda: [self.ws]

    def test_workspace_pisa_a_la_global(self):
        _mk_skill(self.ws, "facturas-resumen",
                  "Version SmartStudent del resumen de facturas",
                  "# Facturas SmartStudent\nUsar la plantilla corporativa AZUL",
                  mtime=time.time() + 5)
        entries = {s: p for s, p, _ in self.pet._skills_scan()}
        self.assertIn(self.ws, entries["facturas-resumen"])  # gana la del proyecto
        out = self.pet._load_installed_skills("resumen de facturas del mes")
        self.assertIn("plantilla corporativa AZUL", out)
        self.assertNotIn("Calcular IVA", out)  # el cuerpo global quedó pisado

    def test_workspace_suma_skills_nuevas(self):
        _mk_skill(self.ws, "deploy-smartstudent",
                  "Pasos de deploy de SmartStudent",
                  "# Deploy\n1. Compilar el APK\n2. Subir a Play Console",
                  mtime=time.time() + 5)
        slugs = [s for s, _, _ in self.pet._skills_scan()]
        self.assertIn("deploy-smartstudent", slugs)
        self.assertIn("facturas-resumen", slugs)  # las globales siguen
        hits = self.pet._skills_fts_search("cómo hago el deploy del apk")
        self.assertIn("deploy-smartstudent", hits)

    def test_sin_workspace_todo_sigue_igual(self):
        self.pet._workspace_skills_roots = lambda: []
        slugs = [s for s, _, _ in self.pet._skills_scan()]
        self.assertEqual(len(slugs), 3)


class TestCargaSearchFirst(SkillFTSBase):
    def test_incluye_catalogo_y_solo_la_relevante(self):
        out = self.pet._load_installed_skills("resumen de facturas del mes")
        # catálogo: TODAS las skills listadas
        for slug in ("facturas-resumen", "limpiar-descargas", "informe-mercado"):
            self.assertIn(slug, out)
        # cuerpo completo: solo la relevante
        self.assertIn("Calcular IVA", out)
        self.assertNotIn("papelera de reciclaje", out)
        self.assertIn("RELEVANTES", out)

    def test_sin_matches_solo_catalogo(self):
        out = self.pet._load_installed_skills("quiero jugar ajedrez online")
        self.assertIn("facturas-resumen", out)   # catálogo
        self.assertNotIn("Calcular IVA", out)    # sin cuerpos
        self.assertNotIn("RELEVANTES", out)

    def test_fallback_legacy_sin_fts(self):
        self.pet._skills_fts_search = lambda q, limit=3: None
        out = self.pet._load_installed_skills("resumen de facturas")
        self.assertIn("[SKILLS INSTALADAS LOCALMENTE]", out)
        self.assertIn("Calcular IVA", out)
        self.assertIn("papelera de reciclaje", out)  # legacy: carga todas

    def test_sin_prompt_usa_legacy(self):
        out = self.pet._load_installed_skills()
        self.assertIn("[SKILLS INSTALADAS LOCALMENTE]", out)

    def test_sin_skills_devuelve_vacio(self):
        pet = FakePet(os.path.join(self.tmp, "no-existe"),
                      os.path.join(self.tmp, "idx2.db"))
        self.assertEqual(pet._load_installed_skills("hola"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
