import io
import zipfile

from django.conf import settings
from django.http import HttpResponse
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import IllegalCharacterError

TEMPLATE_PATH = settings.BASE_DIR / 'plantillas' / 'formato_nota_pedido.xlsx'


def _set_value(ws, cell, value):
    """Escribe `value` en `cell` limpiando caracteres no soportados por Excel."""
    if value is None or value == '':
        ws[cell] = None
        return
    if isinstance(value, str):
        value = value.replace('\x00', '')
    try:
        ws[cell] = value
    except IllegalCharacterError:
        ws[cell] = ''.join(c for c in str(value) if ord(c) >= 32)


def _fmt_fecha(fecha):
    if not fecha:
        return ''
    return fecha.isoformat()


def build_nota_workbook(nota):
    wb = load_workbook(TEMPLATE_PATH)
    ws = wb.active

    # ---- Cabecera / datos generales --------------------------------------
    _set_value(ws, 'D13', nota.obra.nombre if nota.obra else '')
    _set_value(ws, 'K13', nota.numero)
    _set_value(ws, 'D14', nota.encargado)
    _set_value(ws, 'H14', nota.etapa)
    _set_value(ws, 'K14', _fmt_fecha(nota.fecha))
    _set_value(ws, 'D15', nota.solicitante)
    _set_value(ws, 'H15', nota.prioridad)
    _set_value(ws, 'K15', _fmt_fecha(nota.limite))
    _set_value(ws, 'D18', nota.proveedor.nombre if nota.proveedor else '')
    _set_value(ws, 'H18', nota.vendedor)

    # ---- Tabla de mercaderías (filas 21 a 31) -----------------------------
    row = 21
    for item in nota.items.all():
        if row > 31:
            break
        _set_value(ws, f'C{row}', int(item.stock) if item.stock not in (None, '') else '')
        _set_value(ws, f'D{row}', float(item.cantidad) if item.cantidad not in (None, '') else '')
        _set_value(ws, f'E{row}', item.detalle)
        _set_value(ws, f'H{row}', item.especificaciones)
        _set_value(ws, f'J{row}', item.estado)
        _set_value(ws, f'K{row}', float(item.precio) if item.precio not in (None, '') else '')
        row += 1

    # ---- Firmas y pie -----------------------------------------------------
    _set_value(ws, 'C33', nota.solicitante)
    if nota.estado == 'aprobada' and nota.aprobado_por:
        _set_value(ws, 'H33', nota.aprobado_por)
    _set_value(ws, 'C34', 'OBSERVACIONES: ' + nota.observaciones)
    _set_value(ws, 'F34', 'Sí' if nota.para_envio else '')
    _set_value(ws, 'F35', 'Sí' if nota.a_retirar else '')
    _set_value(ws, 'H35', nota.retira)

    return wb


def nota_to_bytes(nota):
    wb = build_nota_workbook(nota)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def excel_response(nota):
    data = nota_to_bytes(nota)
    nombre = nota.obra.nombre if nota.obra else ''
    filename = f'NP_{nota.numero:03d}_{nombre}.xlsx'
    response = HttpResponse(
        data,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def zip_response(notas):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for nota in notas:
            nombre = nota.obra.nombre if nota.obra else ''
            filename = f'NP_{nota.numero:03d}_{nombre}.xlsx'
            zf.writestr(filename, nota_to_bytes(nota))
    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="notas_pedido.zip"'
    return response