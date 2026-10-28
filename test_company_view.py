import copy
import unittest
from engine import EDIT_FIELDS, evaluate
from company_view import matrix_records, prepare_batch, company_summary


class CompanyReviewTests(unittest.TestCase):
    def setUp(self):
        row = {"id_mp": "01", "inec_identificador_empresa": "001", "nombre": "Materia",
               "cpc": "0116019210099", "unid_med": 66,
               "cantidad_inv_ini": "10", "valor_inv_ini": "100",
               "cantidad_impor": "0", "valor_impor": "0", "cantidad_local": "0", "valor_local": "0",
               "cantidad_inv_fin": "2", "valor_inv_fin": "20", "cant_terceros": "0",
               "porcentaje_local": "0", "ciiu4_actividad_principal": "C141002"}
        self.rows = {"01": row, "02": {**row, "id_mp": "02"}}
        self.edits = {key: {**dict.fromkeys(EDIT_FIELDS, ""), "Estado_revision": "Pendiente"} for key in self.rows}
        self.units = {66: {"label": "LIBRAS", "target": "Kilos", "factor": 0.45359237}, 24: {"label": "KILOS"}}
        self.cpc = {row["cpc"]: "Descripción"}
        self.report = {key: evaluate(row, self.edits[key], self.units, self.cpc) for key, row in self.rows.items()}

    def matrix(self):
        return matrix_records(list(self.rows), self.rows, self.edits, self.report, self.cpc)

    def test_save_uses_ids_after_sort_and_cannot_change_money(self):
        records = list(reversed(self.matrix()))
        records[0]["cantidad_inv_ini_act"] = "0"
        records[0]["valor_inv_ini"] = "999999"
        result = prepare_batch(records, list(self.rows), self.rows, self.edits, self.units, self.cpc)
        self.assertEqual(result["02"]["cantidad_inv_ini_act"], "0")
        self.assertEqual(result["01"]["cantidad_inv_ini_act"], "")
        self.assertEqual(self.rows["02"]["valor_inv_ini"], "100")
        self.assertNotIn("valor_inv_ini", result["02"])

    def test_invalid_batch_does_not_mutate_state(self):
        before = copy.deepcopy(self.edits)
        records = self.matrix()
        records[0]["cantidad_inv_ini_act"] = "99"
        records[1]["cantidad_inv_ini_act"] = "texto"
        with self.assertRaises(ValueError):
            prepare_batch(records, list(self.rows), self.rows, self.edits, self.units, self.cpc)
        self.assertEqual(self.edits, before)

    def test_company_conversion_and_summary_share_state(self):
        records = self.matrix()
        records[0]["Convertir según UM"] = True
        result = prepare_batch(records, list(self.rows), self.rows, self.edits, self.units, self.cpc)
        self.assertEqual(result["01"]["cantidad_inv_ini_act"], "4.5359237")
        self.assertEqual(result["01"]["uni_med_act"], "24")
        self.edits.update(result)
        self.assertEqual(self.matrix()[0]["cantidad_inv_ini_act"], "4.5359237")
        self.assertEqual(company_summary(self.rows, self.edits, self.report)[0]["Materias primas"], 2)


if __name__ == "__main__":
    unittest.main()
