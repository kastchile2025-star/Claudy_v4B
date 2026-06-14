"""B3 — Catálogo de recetas QCORE (features/recipes.py).

Verifica el catálogo, el filtrado y la instalación como skill local, usando un
host mínimo que implementa los helpers de skill que el mixin necesita.

Ejecutar: python tests/test_recipes.py   (desde src/desktop)
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.recipes import RECIPES, RecipesMixin, _frontmatter_name  # noqa: E402


def make_host():
    tmp = tempfile.mkdtemp(prefix="claudy_recipes_")

    class Host(RecipesMixin):
        def __init__(self):
            self._root = os.path.join(tmp, "skills")

        def _skill_dir(self, slug):
            return os.path.join(self._root, slug)

        def _installed_skill_slugs(self):
            if not os.path.isdir(self._root):
                return []
            return sorted(d for d in os.listdir(self._root)
                          if os.path.isfile(os.path.join(self._root, d, "SKILL.md")))

        def _load_skill_meta(self, slug):
            return {"slug": slug}

        def _save_skill_meta(self, slug, meta):
            self._saved_meta = meta

    return Host()


class TestCatalogoValido(unittest.TestCase):
    def test_frontmatter_coincide_con_slug(self):
        for r in RECIPES:
            self.assertEqual(_frontmatter_name(r["body"]), r["slug"],
                             f"frontmatter de {r['slug']} no coincide")

    def test_cada_receta_tiene_campos(self):
        for r in RECIPES:
            for k in ("slug", "category", "title", "description", "body"):
                self.assertTrue(r.get(k), f"{r.get('slug')} sin '{k}'")

    def test_slugs_unicos(self):
        slugs = [r["slug"] for r in RECIPES]
        self.assertEqual(len(slugs), len(set(slugs)), "hay slugs duplicados")


class TestCatalogoListado(unittest.TestCase):
    def test_lista_completa_agrupa_por_categoria(self):
        out = make_host()._recipes_catalog()
        self.assertIn("Facturación", out)
        self.assertIn("factura-mensual-combas", out)

    def test_filtro_por_texto(self):
        out = make_host()._recipes_catalog("factura")
        self.assertIn("factura-mensual-combas", out)
        self.assertNotIn("vigilar-precio-web", out)

    def test_filtro_sin_resultados(self):
        out = make_host()._recipes_catalog("zzznoexiste")
        self.assertIn("No hay recetas", out)


class TestInstalacion(unittest.TestCase):
    def test_instala_una_receta(self):
        h = make_host()
        msg = h._install_recipe("factura-mensual-combas")
        self.assertIn("instalada", msg.lower())
        self.assertIn("factura-mensual-combas", h._installed_skill_slugs())
        # El SKILL.md escrito conserva el frontmatter.
        path = os.path.join(h._skill_dir("factura-mensual-combas"), "SKILL.md")
        with open(path, encoding="utf-8") as f:
            self.assertIn("name: factura-mensual-combas", f.read())

    def test_instalar_dos_veces_no_duplica(self):
        h = make_host()
        h._install_recipe("vigilar-precio-web")
        msg2 = h._install_recipe("vigilar-precio-web")
        self.assertIn("ya estaba", msg2.lower())

    def test_slug_inexistente(self):
        msg = make_host()._install_recipe("no-existe")
        self.assertIn("no encuentro", msg.lower())

    def test_instalar_todas(self):
        h = make_host()
        msg = h._install_recipe("todas")
        self.assertIn("Instaladas", msg)
        self.assertEqual(len(h._installed_skill_slugs()), len(RECIPES))

    def test_catalogo_marca_instaladas(self):
        h = make_host()
        h._install_recipe("backup-vault-qcore")
        out = h._recipes_catalog()
        # La línea de la receta instalada lleva la marca ✓.
        for line in out.splitlines():
            if "backup-vault-qcore" in line and line.strip().startswith("•"):
                self.assertIn("✓", line)


if __name__ == "__main__":
    unittest.main(verbosity=2)
