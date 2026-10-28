"""Reglas de revisión del Tomo II, Materias Primas.

Los valores monetarios siempre provienen de la matriz original.
"""

from decimal import Decimal, InvalidOperation
import re
import unicodedata


QUANTITIES = (
    ("cantidad_inv_ini", "cantidad_inv_ini_act", "Inventario inicial"),
    ("cantidad_impor", "cantidad_impor_act", "Importaciones"),
    ("cantidad_local", "cantidad_local_act", "Compras locales"),
    ("cantidad_inv_fin", "cantidad_inv_fin_act", "Inventario final"),
    ("cant_terceros", "cant_terceros_act", "Terceros"),
)
VALUES = (
    ("cantidad_inv_ini", "cantidad_inv_ini_act", "valor_inv_ini", "Inventario inicial"),
    ("cantidad_impor", "cantidad_impor_act", "valor_impor", "Importaciones"),
    ("cantidad_local", "cantidad_local_act", "valor_local", "Compras locales"),
    ("cantidad_inv_fin", "cantidad_inv_fin_act", "valor_inv_fin", "Inventario final"),
)
EDIT_FIELDS = (
    "cod_cpc_act", "uni_med_act", "cantidad_inv_ini_act", "cantidad_impor_act",
    "cantidad_local_act", "porcentaje_local_act", "cantidad_inv_fin_act",
    "cant_terceros_act", "Justificación a las novedades", "Responsable",
    "Estado_revision",
)
NUMERIC_EDITS = tuple(x[1] for x in QUANTITIES) + ("porcentaje_local_act",)
REVIEW_STATES = ("Pendiente", "En revisión", "Con novedades", "Validado")
SPECIAL_CPC = {f"999999999999{i}" for i in range(1, 5)}


def blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def decimal(value):
    if blank(value):
        return None
    if isinstance(value, str):
        value = value.strip().replace(" ", "")
        if "," in value and "." not in value:
            value = value.replace(",", ".")
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def display_number(value):
    return "" if value is None else format(value.normalize(), "f")


def effective(row, edits, original, change):
    return row.get(original) if blank(edits.get(change)) else edits[change]


def normalize_label(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.upper()).strip()


def conversion_for(row, units):
    """Devuelve (código destino, factor, aviso), sin modificar el registro."""
    source = decimal(row.get("unid_med"))
    source_code = int(source) if source is not None and source == int(source) else None
    source_unit = units.get(source_code, {})
    target = normalize_label(source_unit.get("target"))
    factor = decimal(source_unit.get("factor"))
    labels = {
        "LITROS": 27, "LITRO (1.000 CM3 UN LITRO)": 27,
        "KILOS": 24, "METROS": 29, "METRO LINEAL": 29,
        "METRO 2": 30, "METRO 3": 31,
    }
    if not target:
        return None, None, "Esta unidad no tiene conversión en el catálogo."
    code = labels.get(target)
    if code not in units:
        return None, None, f"Destino sin código reconocido: {target}."
    if factor is None or factor <= 0:
        return None, None, "El catálogo indica un destino, pero falta un factor positivo."
    return code, factor, ""


def converted_edits(row, units):
    code, factor, message = conversion_for(row, units)
    if message:
        raise ValueError(message)
    changes = {"uni_med_act": str(code)}
    for original, edit, _ in QUANTITIES:
        original_value = row.get(original)
        if blank(original_value):
            changes[edit] = ""
        else:
            amount = decimal(original_value)
            if amount is None:
                raise ValueError(f"No se puede convertir {original}: el dato original no es numérico.")
            changes[edit] = display_number(amount * factor)
    return changes


def _price(value, quantity):
    return value / quantity if value is not None and quantity is not None and quantity > 0 else None


def _variation(first, second):
    if first is None or second is None or first <= 0 or second <= 0:
        return None
    return max(abs(first / second - 1), abs(second / first - 1))


def evaluate(row, edits, units, cpc):
    """Retorna valores efectivos, precios y alertas para una materia prima."""
    alerts = []
    qty = {}
    val = {}
    for original, change, name in QUANTITIES:
        current = effective(row, edits, original, change)
        qty[original] = decimal(current)
        if not blank(current) and qty[original] is None:
            alerts.append(f"{name}: cantidad no numérica.")
        elif qty[original] is not None and qty[original] < 0:
            alerts.append(f"{name}: cantidad negativa.")

    for original, change, value_field, name in VALUES:
        amount = row.get(value_field)
        val[value_field] = decimal(amount)
        if not blank(amount) and val[value_field] is None:
            alerts.append(f"{name}: valor original no numérico.")
        quantity, value = qty[original], val[value_field]
        if quantity is not None and value is not None:
            if (quantity > 0 and value == 0) or (quantity == 0 and value > 0):
                alerts.append(f"{name}: cantidad y valor no corresponden.")
        elif quantity is not None and quantity > 0 and blank(amount):
            alerts.append(f"{name}: falta el valor informado.")
        elif value is not None and value > 0 and blank(effective(row, edits, original, change)):
            alerts.append(f"{name}: falta la cantidad.")

    percentage = decimal(effective(row, edits, "porcentaje_local", "porcentaje_local_act"))
    if percentage is None and not blank(effective(row, edits, "porcentaje_local", "porcentaje_local_act")):
        alerts.append("Porcentaje local: dato no numérico.")
    elif percentage is not None:
        if not 0 <= percentage <= 100:
            alerts.append("Porcentaje local: debe estar entre 0 y 100.")
        elif percentage > 0 and (val["valor_local"] is None or val["valor_local"] == 0):
            alerts.append("Porcentaje local: existe porcentaje sin valor local.")

    code = str(effective(row, edits, "cpc", "cod_cpc_act") or "").strip()
    if code not in cpc:
        alerts.append("CPC: el código efectivo no consta en el catálogo.")
    original_unit = decimal(row.get("unid_med"))
    current_unit = decimal(effective(row, edits, "unid_med", "uni_med_act"))
    unit_code = int(current_unit) if current_unit is not None and current_unit == int(current_unit) else None
    source_code = int(original_unit) if original_unit is not None and original_unit == int(original_unit) else None
    if code not in SPECIAL_CPC and unit_code not in units:
        alerts.append("Unidad de medida: falta un código válido.")
    if source_code != unit_code and source_code is not None:
        target, factor, problem = conversion_for(row, units)
        if problem or target != unit_code:
            alerts.append("Unidad de medida: el cambio no tiene un factor documentado para ese destino.")
        else:
            for original, change, name in QUANTITIES:
                source_quantity = decimal(row.get(original))
                if source_quantity is not None and blank(edits.get(change)):
                    alerts.append(f"{name}: falta la cantidad en la nueva unidad.")
    sectors = [str(row.get(name) or "")[:1].upper() for name in (
        "ciiu4_actividad_principal", "ciiu4_actividad_secundaria", "ciiu4_tercera_actividad"
    )]
    if not any(sector in {"B", "C", "F"} for sector in sectors):
        alerts.append("Capítulo 3: revisar si la empresa debe llenarlo según sus actividades.")

    prices = {
        "Inventario inicial": _price(val["valor_inv_ini"], qty["cantidad_inv_ini"]),
        "Importaciones": _price(val["valor_impor"], qty["cantidad_impor"]),
        "Compras locales": _price(val["valor_local"], qty["cantidad_local"]),
        "Inventario final": _price(val["valor_inv_fin"], qty["cantidad_inv_fin"]),
    }
    imported, local = prices["Importaciones"], prices["Compras locales"]
    comparison = [x for x in (imported, local) if x is not None]
    average = sum(comparison) / len(comparison) if comparison else None
    for first, second, label in (
        (local, imported, "Precio local frente a importado"),
        (prices["Inventario final"], average, "Precio de inventario final frente a compras"),
        (prices["Inventario inicial"], average, "Precio de inventario inicial frente a compras"),
        (prices["Inventario inicial"], prices["Inventario final"], "Precio entre inventarios"),
    ):
        variation = _variation(first, second)
        if variation is not None and variation > 1:
            alerts.append(f"{label}: variación superior al 100 %.")

    used_quantity = None
    if all(qty[k] is not None for k in ("cantidad_inv_ini", "cantidad_impor", "cantidad_local", "cantidad_inv_fin")):
        used_quantity = qty["cantidad_inv_ini"] + qty["cantidad_impor"] + qty["cantidad_local"] - qty["cantidad_inv_fin"]
        if used_quantity < 0:
            alerts.append("Cantidad utilizada: inventario final supera las entradas disponibles.")
    used_value = None
    if all(val[k] is not None for k in ("valor_inv_ini", "valor_impor", "valor_local", "valor_inv_fin")):
        used_value = val["valor_inv_ini"] + val["valor_impor"] + val["valor_local"] - val["valor_inv_fin"]
        if used_value < 0:
            alerts.append("Valor utilizado: inventario final supera las entradas disponibles.")

    changes = [edit for edit in EDIT_FIELDS[:8] if not blank(edits.get(edit))]
    return {
        "alerts": alerts, "quantities": qty, "values": val, "prices": prices,
        "used_quantity": used_quantity, "used_value": used_value,
        "cpc": code, "unit": unit_code, "changes": changes,
    }
