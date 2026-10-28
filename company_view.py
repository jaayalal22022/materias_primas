"""Preparación y guardado de la revisión por empresa, usando id_mp."""
import math
from engine import EDIT_FIELDS, NUMERIC_EDITS, REVIEW_STATES, blank, decimal, evaluate, converted_edits


def company_summary(rows, edits, report):
    grouped = {}
    for key, row in rows.items():
        company = str(row.get("inec_identificador_empresa") or "")
        item = grouped.setdefault(company, {
            "Empresa": company, "Razón social": str(row.get("razon_social") or row.get("nombre_comercial") or ""),
            "CIIU principal": str(row.get("ciiu4_actividad_principal") or ""),
            "CIIU secundaria": str(row.get("ciiu4_actividad_secundaria") or ""),
            "CIIU tercera": str(row.get("ciiu4_tercera_actividad") or ""),
            "Materias primas": 0, "Con alertas": 0, "Validadas": 0,
        })
        item["Materias primas"] += 1
        item["Con alertas"] += bool(report[key]["alerts"])
        item["Validadas"] += edits[key]["Estado_revision"] == "Validado"
    return list(grouped.values())


def matrix_records(keys, rows, edits, report, cpc):
    result = []
    for key in keys:
        row = rows[key]
        # Conservar orden de los campos originales, sin mostrar fórmulas Excel.
        record = {name: "" if blank(value) else str(value)
                  for name, value in row.items()
                  if name != "_excel_row" and not (isinstance(value, str) and value.startswith("="))}
        record.update(edits[key])
        record.update({
            "id_mp": key, "CPC efectivo": report[key]["cpc"],
            "Descripción CPC efectiva": cpc.get(report[key]["cpc"], ""),
            "Unidad efectiva": str(report[key]["unit"] or ""),
            "Alertas app": "; ".join(report[key]["alerts"]),
            "Convertir según UM": False,
        })
        result.append(record)
    return result


def prepare_batch(records, keys, rows, edits, units, cpc):
    """Validar todo el lote antes de devolver cambios. Nunca escribir al origen."""
    expected = set(keys)
    if len(records) != len(expected) or {str(r.get("id_mp")) for r in records} != expected:
        raise ValueError("La lista de id_mp cambió. Recarga la empresa antes de guardar.")
    pending = {}
    for record in records:
        key = str(record["id_mp"])
        candidate = dict(edits[key])
        for field in EDIT_FIELDS:
            if field in record:
                value = record[field]
                candidate[field] = "" if blank(value) or (isinstance(value, float) and math.isnan(value)) else str(value).strip()
        if record.get("Convertir según UM"):
            try:
                candidate.update(converted_edits(rows[key], units))
            except ValueError as exc:
                raise ValueError(f"{key}: {exc}") from exc
        for field in NUMERIC_EDITS:
            if not blank(candidate[field]) and decimal(candidate[field]) is None:
                raise ValueError(f"{key}: {field} debe ser numérico o vacío.")
        code = candidate["cod_cpc_act"]
        if code and (len(code) != 13 or not code.isdigit()):
            raise ValueError(f"{key}: el CPC corregido debe tener 13 dígitos.")
        unit = candidate["uni_med_act"]
        if unit and (decimal(unit) is None or decimal(unit) != int(decimal(unit)) or int(decimal(unit)) not in units):
            raise ValueError(f"{key}: la unidad corregida no consta en UM.")
        if candidate["Estado_revision"] not in REVIEW_STATES:
            raise ValueError(f"{key}: estado de revisión desconocido.")
        result = evaluate(rows[key], candidate, units, cpc)
        if candidate["Estado_revision"] == "Validado" and result["alerts"] and not candidate["Justificación a las novedades"]:
            raise ValueError(f"{key}: para validar con alertas se necesita una justificación.")
        pending[key] = candidate
    return pending
