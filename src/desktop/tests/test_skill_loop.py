"""Tests del bucle de aprendizaje cerrado + Curator (features/skill_loop.py)."""
import datetime
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from features.skill_loop import SkillLoopMixin  # noqa: E402


VALID_SKILL = (
    "---\n"
    "name: resumen-facturas\n"
    "description: Resumir facturas del mes en un xlsx\n"
    "---\n\n"
    "# Resumen de facturas\n\n"
    "## Cuándo usarla\nCuando pidan resumen de facturas.\n\n"
    "## Pasos\n1. Buscar facturas.\n2. Armar xlsx.\n\n"
    "## Reglas\n- Usar formato chileno.\n\n"
    "## Ejemplo\nResumen de mayo."
)


class FakePet(SkillLoopMixin):
    """Implementa los helpers de pet.py que el mixin necesita, sobre un tmpdir."""

    def __init__(self, root):
        self.root = root
        self.llm_responses = []   # cola FIFO de respuestas simuladas
        self.llm_calls = []       # prompts recibidos
        self.notifications = []
        self._last_auto_skill_eval = 0.0
        self._curator_running = False

    # — helpers de skills (mismas firmas que pet.py) —
    def _skill_slug(self, name):
        return re.sub(r"[^a-z0-9_-]+", "-", (name or "").lower().strip()).strip("-")

    def _skill_dir(self, slug):
        return os.path.join(self.root, slug)

    def _skill_meta_path(self, slug):
        return os.path.join(self._skill_dir(slug), "_meta.json")

    def _load_skill_meta(self, slug):
        meta = {
            "slug": slug, "version": 1, "uses": 0, "uses_since_refine": 0,
            "created": datetime.datetime.now().isoformat(timespec="seconds"),
            "last_used": None, "last_refined": None, "observations": [],
        }
        try:
            if os.path.isfile(self._skill_meta_path(slug)):
                with open(self._skill_meta_path(slug), encoding="utf-8") as f:
                    meta.update(json.load(f) or {})
        except Exception:
            pass
        return meta

    def _save_skill_meta(self, slug, meta):
        os.makedirs(self._skill_dir(slug), exist_ok=True)
        with open(self._skill_meta_path(slug), "w", encoding="utf-8") as f:
            json.dump(meta, f)

    def _installed_skill_slugs(self):
        out = []
        for folder in sorted(os.listdir(self.root)):
            if os.path.isfile(os.path.join(self.root, folder, "SKILL.md")):
                out.append(folder)
        return out

    def _create_skill_stub(self, name):
        return f"stub:{name}"

    # — infraestructura simulada —
    def send_quick_message(self, prompt, **kwargs):
        self.llm_calls.append(prompt)
        return self.llm_responses.pop(0) if self.llm_responses else "NO"

    def _debug_log(self, *a):
        pass

    def _show_notification(self, title, msg):
        self.notifications.append((title, msg))

    def after(self, _ms, fn=None):
        if fn:
            fn()

    # override del archive para usar el tmpdir (pet.py usa ~/.claudy)
    def _archive_skill(self, slug, reason=""):
        archive_root = os.path.join(self.root, "_archive")
        os.makedirs(archive_root, exist_ok=True)
        shutil.move(self._skill_dir(slug), os.path.join(archive_root, slug))


def _make_skill(pet, slug, description, origin="manual", uses=0, created=None):
    folder = pet._skill_dir(slug)
    os.makedirs(folder, exist_ok=True)
    content = VALID_SKILL.replace("resumen-facturas", slug).replace(
        "Resumir facturas del mes en un xlsx", description)
    with open(os.path.join(folder, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(content)
    meta = pet._load_skill_meta(slug)
    meta.update({"origin": origin, "uses": uses})
    if created:
        meta["created"] = created
    pet._save_skill_meta(slug, meta)


class TestWriteSkillMd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pet = FakePet(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_guarda_skill_valida_y_marca_origen(self):
        path = self.pet._write_skill_md("mi-skill", VALID_SKILL, origin="auto")
        self.assertTrue(path and os.path.isfile(path))
        self.assertEqual(self.pet._load_skill_meta("mi-skill")["origin"], "auto")

    def test_rechaza_contenido_sin_frontmatter(self):
        self.assertIsNone(self.pet._write_skill_md("mala", "esto no es una skill", "auto"))

    def test_limpia_fences_de_markdown(self):
        path = self.pet._write_skill_md("fenced", f"```markdown\n{VALID_SKILL}\n```", "auto")
        self.assertTrue(path)
        with open(path, encoding="utf-8") as f:
            self.assertTrue(f.read().startswith("---"))


class TestDescribeASkill(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pet = FakePet(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_nombre_corto_cae_al_stub(self):
        self.assertEqual(self.pet._create_skill_from_description("facturas"), "stub:facturas")

    def test_genera_desde_descripcion(self):
        self.pet.llm_responses = [VALID_SKILL]
        out = self.pet._create_skill_from_description(
            "que resuma las facturas del mes en un xlsx")
        self.assertIn("resumen-facturas", out)
        self.assertIn("resumen-facturas", self.pet._installed_skill_slugs())

    def test_slug_duplicado_se_versiona(self):
        _make_skill(self.pet, "resumen-facturas", "ya existe")
        self.pet.llm_responses = [VALID_SKILL]
        out = self.pet._create_skill_from_description(
            "que resuma las facturas del mes en un xlsx")
        self.assertIn("resumen-facturas-2", out)

    def test_horario_en_descripcion_sugiere_cron(self):
        self.pet.llm_responses = [VALID_SKILL]
        out = self.pet._create_skill_from_description(
            "que cada viernes a las 9 resuma las facturas en un xlsx")
        self.assertIn("⏰", out)


class TestAutoSkillCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pet = FakePet(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _msgs(self, n):
        return [{"role": "user" if i % 2 == 0 else "bot", "text": f"mensaje {i}"}
                for i in range(n)]

    def test_sesion_corta_no_evalua(self):
        self.pet._auto_skill_check(self._msgs(4))
        self.assertEqual(self.pet.llm_calls, [])

    def test_veredicto_no_crea_nada(self):
        self.pet.llm_responses = ["NO"]
        self.pet._auto_skill_check(self._msgs(10))
        self.assertEqual(len(self.pet.llm_calls), 1)
        self.assertEqual(self.pet._installed_skill_slugs(), [])

    def test_veredicto_si_crea_skill_y_notifica(self):
        self.pet.llm_responses = [
            '{"name": "resumen-facturas", "reason": "flujo repetible"}',
            VALID_SKILL,
        ]
        self.pet._auto_skill_check(self._msgs(10))
        self.assertIn("resumen-facturas", self.pet._installed_skill_slugs())
        self.assertEqual(self.pet._load_skill_meta("resumen-facturas")["origin"], "auto")
        self.assertTrue(self.pet.notifications)

    def test_cooldown_evita_evaluaciones_seguidas(self):
        self.pet.llm_responses = ["NO", "NO"]
        self.pet._auto_skill_check(self._msgs(10))
        self.pet._auto_skill_check(self._msgs(10))
        self.assertEqual(len(self.pet.llm_calls), 1)


class TestCurator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pet = FakePet(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_archiva_auto_skill_vieja_sin_uso(self):
        vieja = (datetime.datetime.now() - datetime.timedelta(days=45)).isoformat(timespec="seconds")
        _make_skill(self.pet, "vieja-auto", "algo que nadie usa", origin="auto",
                    uses=0, created=vieja)
        out = self.pet._curator_run(manual=True)
        self.assertNotIn("vieja-auto", self.pet._installed_skill_slugs())
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "_archive", "vieja-auto")))
        self.assertIn("archivé", out)

    def test_no_toca_skills_manuales_viejas(self):
        vieja = (datetime.datetime.now() - datetime.timedelta(days=90)).isoformat(timespec="seconds")
        _make_skill(self.pet, "manual-vieja", "creada por el usuario", origin="manual",
                    uses=0, created=vieja)
        self.pet._curator_run(manual=True)
        self.assertIn("manual-vieja", self.pet._installed_skill_slugs())

    def test_fusiona_duplicados_evidentes(self):
        _make_skill(self.pet, "resumen-facturas-mes", "resumir facturas mensuales en xlsx", uses=5)
        _make_skill(self.pet, "resumen-facturas-mensual", "resumir facturas mensuales en xlsx", uses=1)
        self.pet.llm_responses = [VALID_SKILL.replace("resumen-facturas", "resumen-facturas-mes")]
        out = self.pet._curator_run(manual=True)
        self.assertIn("fusioné", out)
        self.assertIn("resumen-facturas-mes", self.pet._installed_skill_slugs())
        self.assertNotIn("resumen-facturas-mensual", self.pet._installed_skill_slugs())

    def test_biblioteca_sana_no_hace_nada(self):
        _make_skill(self.pet, "skill-a", "buscar precios de productos en internet")
        _make_skill(self.pet, "skill-b", "redactar correos formales de cobranza")
        out = self.pet._curator_run(manual=True)
        self.assertIn("todo en orden", out)


if __name__ == "__main__":
    unittest.main()
