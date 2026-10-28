"""Casos de negocio que protegen la separación entre origen y revisión."""

import unittest

from engine import conversion_for, converted_edits, evaluate


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "cpc": "0116019210099", "unid_med": 66,
            "cantidad_inv_ini": "10", "valor_inv_ini": "100",
            "cantidad_impor": "0", "valor_impor": "0",
            "cantidad_local": "0", "valor_local": "0",
            "cantidad_inv_fin": "2", "valor_inv_fin": "20",
            "cant_terceros": "0", "porcentaje_local": "0",
            "ciiu4_actividad_principal": "C141002",
        }
        self.units = {
            66: {"label": "LIBRAS", "target": "Kilos", "factor": 0.45359237},
            24: {"label": "KILOS", "target": None, "factor": None},
            65: {"label": "GRAMOS", "target": "Kilos", "factor": None},
        }
        self.cpc = {self.row["cpc"]: "Descripción"}

    def test_conversion_and_original_values(self):
        edits = converted_edits(self.row, self.units)
        self.assertEqual(edits["uni_med_act"], "24")
        self.assertEqual(edits["cantidad_inv_ini_act"], "4.5359237")
        result = evaluate(self.row, edits, self.units, self.cpc)
        self.assertEqual(str(result["values"]["valor_inv_ini"]), "100")
        self.assertEqual(str(result["quantities"]["cantidad_inv_ini"]), "4.5359237")
        self.assertFalse(any("falta la cantidad" in alert for alert in result["alerts"]))

    def test_zero_is_an_override_not_a_blank(self):
        result = evaluate(self.row, {"cantidad_inv_ini_act": "0"}, self.units, self.cpc)
        self.assertEqual(result["quantities"]["cantidad_inv_ini"], 0)
        self.assertIn("Inventario inicial: cantidad y valor no corresponden.", result["alerts"])

    def test_missing_conversion_factor(self):
        self.row["unid_med"] = 65
        code, factor, message = conversion_for(self.row, self.units)
        self.assertIsNone(code)
        self.assertIsNone(factor)
        self.assertIn("falta un factor", message)

    def test_unit_change_requires_converted_quantities(self):
        result = evaluate(self.row, {"uni_med_act": "24"}, self.units, self.cpc)
        self.assertTrue(any("falta la cantidad en la nueva unidad" in x for x in result["alerts"]))

    def test_capitulo_three_activity(self):
        self.row["ciiu4_actividad_principal"] = "G471100"
        result = evaluate(self.row, {}, self.units, self.cpc)
        self.assertTrue(any("Capítulo 3" in x for x in result["alerts"]))


if __name__ == "__main__":
    unittest.main()
