"""Tests de Notify Me — vigilancias de páginas e indicadores (features/watcher.py)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from features.watcher import (  # noqa: E402
    WatcherMixin, parse_watch_request, parse_money, extract_prices,
    pick_main_price, extract_visible_text, fmt_clp, MAX_FAILS,
)


class FakePet(WatcherMixin):
    def __init__(self):
        self._cron_jobs = []
        self.saves = 0
        self.notifications = []
        self.page_text = ""
        self.fetch_error = None
        self.indicador_valor = 900.0

    def _save_cron_json(self):
        self.saves += 1

    def _watch_fetch_text(self, url):
        if self.fetch_error:
            raise self.fetch_error
        return self.page_text

    def _watch_fetch_indicador(self, nombre):
        if self.fetch_error:
            raise self.fetch_error
        return self.indicador_valor

    def _watch_notify(self, label, msg):
        self.notifications.append((label, msg))


class TestParseWatchRequest(unittest.TestCase):
    def test_precio_con_url(self):
        r = parse_watch_request("avísame cuando baje el precio de https://tienda.cl/notebook-x")
        self.assertEqual(r["kind"], "precio")
        self.assertEqual(r["url"], "https://tienda.cl/notebook-x")
        self.assertEqual(r["interval_min"], 60)
        self.assertIn("tienda.cl", r["label"])

    def test_cambio_con_intervalo(self):
        r = parse_watch_request("vigila https://ejemplo.com/novedades cada 2 horas")
        self.assertEqual(r["kind"], "cambio")
        self.assertEqual(r["interval_min"], 120)

    def test_texto_con_comillas(self):
        r = parse_watch_request('avísame si https://tienda.cl/p1 dice "agotado"')
        self.assertEqual(r["kind"], "texto")
        self.assertEqual(r["keyword"], "agotado")

    def test_indicador_dolar_baja(self):
        r = parse_watch_request("avísame si el dólar baja de 900")
        self.assertEqual(r["kind"], "indicador")
        self.assertEqual(r["indicador"], "dólar")
        self.assertEqual(r["direction"], "baja")
        self.assertEqual(r["umbral"], 900.0)

    def test_indicador_uf_sube(self):
        r = parse_watch_request("alértame si la uf supera 39.000")
        self.assertEqual(r["kind"], "indicador")
        self.assertEqual(r["indicador"], "UF")
        self.assertEqual(r["direction"], "sube")
        self.assertEqual(r["umbral"], 39000.0)

    def test_www_recibe_https(self):
        r = parse_watch_request("vigila www.ejemplo.cl/oferta")
        self.assertTrue(r["url"].startswith("https://www.ejemplo.cl"))

    def test_frases_que_no_son_vigilancia(self):
        for frase in ("hola como estás",
                      "busca el precio del iphone 15",
                      "avísame en 30 minutos comprar pan",
                      "recuérdame llamar a mamá"):
            self.assertIsNone(parse_watch_request(frase), frase)

    def test_intervalo_minimo(self):
        r = parse_watch_request("vigila https://x.cl cada 1 min")
        self.assertGreaterEqual(r["interval_min"], 5)


class TestDinero(unittest.TestCase):
    def test_parse_money(self):
        self.assertEqual(parse_money("19.990"), 19990.0)
        self.assertEqual(parse_money("25.99"), 25.99)
        self.assertEqual(parse_money("1.234,56"), 1234.56)
        self.assertEqual(parse_money("1,234.56"), 1234.56)
        self.assertEqual(parse_money("39.000"), 39000.0)
        self.assertEqual(parse_money("900"), 900.0)
        self.assertIsNone(parse_money("abc"))

    def test_extract_y_principal(self):
        text = "Antes $25.990 ahora $19.990 — llévalo por $19.990 con envío $0"
        prices = extract_prices(text)
        self.assertIn(19990.0, prices)
        self.assertIn(25990.0, prices)
        self.assertNotIn(0.0, prices)  # envío $0 no es plausible
        self.assertEqual(pick_main_price(prices), 19990.0)  # el más repetido

    def test_fmt_clp(self):
        self.assertEqual(fmt_clp(19990), "$19.990")
        self.assertEqual(fmt_clp(912.45), "$912,45")


class TestVisibleText(unittest.TestCase):
    def test_quita_scripts_y_tags(self):
        html = ("<html><head><style>p{color:red}</style>"
                "<script>var precio=1;</script></head>"
                "<body><p>Precio: <b>$19.990</b></p></body></html>")
        text = extract_visible_text(html)
        self.assertIn("$19.990", text)
        self.assertNotIn("var precio", text)
        self.assertNotIn("color:red", text)


class TestWatchAdd(unittest.TestCase):
    def test_add_precio_guarda_baseline(self):
        pet = FakePet()
        pet.page_text = "Notebook X — $549.990 oferta $549.990"
        out = pet._watch_add("avísame cuando baje el precio de https://tienda.cl/nb")
        self.assertIn("Vigilando", out)
        self.assertIn("$549.990", out)
        self.assertEqual(len(pet._cron_jobs), 1)
        job = pet._cron_jobs[0]
        self.assertEqual(job["action"], "watch")
        self.assertEqual(job["baseline"], {"price": 549990.0})
        self.assertTrue(job["last_fired"])  # no doble chequeo inmediato

    def test_add_precio_sin_precios_no_crea(self):
        pet = FakePet()
        pet.page_text = "Página sin valores"
        out = pet._watch_add("avísame cuando baje el precio de https://tienda.cl/nb")
        self.assertIn("No encontré precios", out)
        self.assertEqual(pet._cron_jobs, [])

    def test_add_error_de_red_no_crea(self):
        pet = FakePet()
        pet.fetch_error = RuntimeError("timeout")
        out = pet._watch_add("vigila https://caida.cl")
        self.assertIn("No pude leer", out)
        self.assertEqual(pet._cron_jobs, [])

    def test_add_indicador(self):
        pet = FakePet()
        pet.indicador_valor = 925.5
        out = pet._watch_add("avísame si el dólar baja de 900")
        self.assertIn("Vigilando", out)
        self.assertEqual(pet._cron_jobs[0]["baseline"], {"valor": 925.5})


class TestWatchCheckPrecio(unittest.TestCase):
    def _job(self, pet, price=19990.0):
        pet.page_text = "Producto $19.990 $19.990"
        pet._watch_add("avísame cuando baje el precio de https://t.cl/p")
        job = pet._cron_jobs[0]
        job["baseline"] = {"price": price}
        return job

    def test_baja_notifica_y_actualiza(self):
        pet = FakePet()
        job = self._job(pet, price=25990.0)
        pet.page_text = "Producto $19.990 $19.990"
        pet._watch_check_worker(dict(job))
        self.assertEqual(len(pet.notifications), 1)
        self.assertIn("Bajó", pet.notifications[0][1])
        self.assertEqual(pet._cron_jobs[0]["baseline"]["price"], 19990.0)

    def test_sube_no_notifica_ni_mueve_baseline(self):
        pet = FakePet()
        job = self._job(pet, price=15000.0)
        pet.page_text = "Producto $19.990 $19.990"
        pet._watch_check_worker(dict(job))
        self.assertEqual(pet.notifications, [])
        self.assertEqual(pet._cron_jobs[0]["baseline"]["price"], 15000.0)


class TestWatchCheckTexto(unittest.TestCase):
    def test_aparece_notifica(self):
        pet = FakePet()
        pet.page_text = "Stock disponible"
        pet._watch_add('avísame si https://t.cl/p dice "agotado"')
        job = pet._cron_jobs[0]
        self.assertEqual(job["baseline"], {"present": False})
        pet.page_text = "Producto AGOTADO por ahora"
        pet._watch_check_worker(dict(job))
        self.assertEqual(len(pet.notifications), 1)
        self.assertIn("apareció", pet.notifications[0][1])
        self.assertEqual(pet._cron_jobs[0]["baseline"], {"present": True})

    def test_sin_cambio_no_notifica(self):
        pet = FakePet()
        pet.page_text = "Stock disponible"
        pet._watch_add('avísame si https://t.cl/p dice "agotado"')
        pet._watch_check_worker(dict(pet._cron_jobs[0]))
        self.assertEqual(pet.notifications, [])


class TestWatchCheckCambio(unittest.TestCase):
    def test_cambio_de_pagina_notifica(self):
        pet = FakePet()
        pet.page_text = "Versión uno de la página"
        pet._watch_add("vigila https://t.cl/novedades")
        job = pet._cron_jobs[0]
        pet.page_text = "Versión dos: ¡novedad importante!"
        pet._watch_check_worker(dict(job))
        self.assertEqual(len(pet.notifications), 1)
        self.assertIn("cambió", pet.notifications[0][1])


class TestWatchCheckIndicador(unittest.TestCase):
    def test_umbral_baja_avisa_una_sola_vez(self):
        pet = FakePet()
        pet.indicador_valor = 920.0
        pet._watch_add("avísame si el dólar baja de 900")
        job_id = pet._cron_jobs[0]["id"]

        pet.indicador_valor = 895.0
        pet._watch_check_worker(dict(pet._cron_jobs[0]))
        self.assertEqual(len(pet.notifications), 1)
        self.assertIn("bajó de", pet.notifications[0][1])

        # Sigue bajo el umbral: NO debe repetir el aviso
        pet.indicador_valor = 890.0
        pet._watch_check_worker(dict(pet._cron_jobs[0]))
        self.assertEqual(len(pet.notifications), 1)

        # Vuelve sobre el umbral (re-arma) y baja otra vez → nuevo aviso
        pet.indicador_valor = 930.0
        pet._watch_check_worker(dict(pet._cron_jobs[0]))
        self.assertEqual(len(pet.notifications), 1)
        pet.indicador_valor = 880.0
        pet._watch_check_worker(dict(pet._cron_jobs[0]))
        self.assertEqual(len(pet.notifications), 2)
        self.assertTrue(all(j["id"] == job_id for j in pet._cron_jobs))

    def test_sin_umbral_avisa_cualquier_cambio(self):
        pet = FakePet()
        pet.indicador_valor = 920.0
        pet._watch_add("vigila el dólar")
        pet.indicador_valor = 921.5
        pet._watch_check_worker(dict(pet._cron_jobs[0]))
        self.assertEqual(len(pet.notifications), 1)
        self.assertIn("subió", pet.notifications[0][1])


class TestFallos(unittest.TestCase):
    def test_fallos_acumulados_pausan_la_vigilancia(self):
        pet = FakePet()
        pet.page_text = "algo $10.000 $10.000"
        pet._watch_add("avísame cuando baje el precio de https://t.cl/p")
        pet.fetch_error = RuntimeError("DNS caído")
        for _ in range(MAX_FAILS):
            pet._watch_check_worker(dict(pet._cron_jobs[0]))
        job = pet._cron_jobs[0]
        self.assertFalse(job["enabled"])
        self.assertEqual(job["fail_count"], MAX_FAILS)
        self.assertTrue(any("pausé" in msg for _, msg in pet.notifications))

    def test_exito_resetea_fallos(self):
        pet = FakePet()
        pet.page_text = "algo $10.000 $10.000"
        pet._watch_add("avísame cuando baje el precio de https://t.cl/p")
        pet._cron_jobs[0]["fail_count"] = 3
        pet._watch_check_worker(dict(pet._cron_jobs[0]))
        self.assertEqual(pet._cron_jobs[0]["fail_count"], 0)


class TestListaYBorrado(unittest.TestCase):
    def test_lista_y_quita(self):
        pet = FakePet()
        pet.page_text = "x $5.000 $5.000"
        pet._watch_add("avísame cuando baje el precio de https://t.cl/a")
        pet._watch_add("vigila https://t.cl/b")
        out = pet._watch_list()
        self.assertIn("[1]", out)
        self.assertIn("[2]", out)
        self.assertIn("$5.000", out)
        out = pet._watch_remove("1")
        self.assertIn("Ya no vigilo", out)
        self.assertEqual(len(pet._cron_jobs), 1)

    def test_quitar_numero_invalido(self):
        pet = FakePet()
        self.assertIn("inválido", pet._watch_remove("7"))

    def test_lista_vacia(self):
        pet = FakePet()
        self.assertIn("No estoy vigilando", pet._watch_list())


if __name__ == "__main__":
    unittest.main(verbosity=2)
