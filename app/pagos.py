"""Ordenes de pago y pasarela.

Por defecto se usa una PASARELA SIMULADA (entorno de pruebas): no cobra dinero real ni guarda datos de tarjeta.
Para producir cobros reales hay que implementar una clase con el mismo metodo `cobrar` (Culqi, Niubiz, Izipay,
Mercado Pago, Stripe, etc.), idealmente con el checkout HOSTEADO del proveedor y confirmacion por webhook, y
seleccionarla con PAYMENT_PROVIDER en `get_pasarela`.

Limitacion: las ordenes viven en la memoria de la instancia (igual que la memoria del chat). En produccion
deben guardarse en una base de datos (Firestore / Cloud SQL)."""
import threading
import time
import uuid
from datetime import datetime

from .config import get_settings

VIGENCIA_SEG = 24 * 3600
_ordenes: dict = {}
_lock = threading.Lock()


def crear_orden(slug: str, id_alumno: str, monto: int, concepto: str) -> dict:
    with _lock:
        previa = next((o for o in _ordenes.values()
                       if o["slug"] == slug and o["id_alumno"] == id_alumno
                       and (o["estado"] == "pagada" or (o["estado"] == "pendiente" and o["vence"] > time.time()))), None)
        if previa:
            return dict(previa)
        oid = uuid.uuid4().hex[:12].upper()
        o = {"id": oid, "slug": slug, "id_alumno": id_alumno, "monto": monto, "moneda": "PEN",
             "concepto": concepto, "estado": "pendiente", "creada": time.time(), "vence": time.time() + VIGENCIA_SEG}
        _ordenes[oid] = o
        return dict(o)


def obtener(oid: str):
    with _lock:
        o = _ordenes.get(oid)
        if o and o["estado"] == "pendiente" and o["vence"] < time.time():
            o["estado"] = "vencida"
        return dict(o) if o else None


def orden_pagada(id_alumno: str, slug: str):
    with _lock:
        return next((dict(o) for o in _ordenes.values()
                     if o["id_alumno"] == id_alumno and o["slug"] == slug and o["estado"] == "pagada"), None)


def vista(o: dict) -> dict:
    return {"orden_id": o["id"], "tramite_slug": o["slug"], "id_alumno": o["id_alumno"], "monto": o["monto"],
            "moneda": o["moneda"], "concepto": o["concepto"], "estado": o["estado"],
            "vence": datetime.fromtimestamp(o["vence"]).isoformat(timespec="minutes"),
            "checkout_url": f"/pasarela/{o['id']}", "return_url": f"/preview/{o['slug']}/{o['id_alumno']}"}


def _luhn(num: str) -> bool:
    t = 0
    for i, ch in enumerate(reversed(num)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        t += d
    return t % 10 == 0


class PasarelaSimulada:
    """Aprueba tarjetas con numero valido (Luhn) salvo 4000 0000 0000 0002 (rechazada). No guarda la tarjeta."""
    nombre = "Pasarela de pruebas"

    def cobrar(self, orden: dict, numero: str, vence: str, cvv: str):
        numero = "".join(c for c in numero if c.isdigit())
        if not (13 <= len(numero) <= 19) or not _luhn(numero):
            return False, "El numero de tarjeta no es valido."
        try:
            mm, aa = vence.replace(" ", "").split("/")
            fin = datetime(2000 + int(aa), int(mm), 1)
            if not 1 <= int(mm) <= 12 or (fin.year, fin.month) < (datetime.now().year, datetime.now().month):
                raise ValueError
        except Exception:
            return False, "La fecha de vencimiento no es valida o la tarjeta esta vencida."
        if not (cvv.isdigit() and 3 <= len(cvv) <= 4):
            return False, "El codigo de seguridad (CVV) no es valido."
        if numero == "4000000000000002":
            return False, "El banco rechazo el pago. Prueba con otra tarjeta."
        return True, "Pago aprobado."


def pagar(oid: str, numero: str, vence: str, cvv: str):
    pasarela = get_pasarela()
    with _lock:
        o = _ordenes.get(oid)
        if not o:
            return None, "La orden no existe."
        if o["estado"] == "pagada":
            return dict(o), "La orden ya estaba pagada."
        if o["vence"] < time.time():
            o["estado"] = "vencida"
            return None, "La orden vencio. Vuelve a confirmar tu tramite para generar una nueva."
    ok, msg = pasarela.cobrar(o, numero, vence, cvv)
    if not ok:
        return None, msg
    with _lock:
        o["estado"] = "pagada"
        o["pagada"] = time.time()
        return dict(o), msg


def get_pasarela():
    if get_settings().payment_provider == "simulada":
        return PasarelaSimulada()
    raise RuntimeError("PAYMENT_PROVIDER no soportado: implementa la pasarela real en app/pagos.py.")
