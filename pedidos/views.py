from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from decimal import Decimal

from django.db.models import Count, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render

from . import excel
from .forms import (
    ItemFormSet,
    MaterialForm,
    NotaPedidoForm,
    ObraForm,
    OrdenCompraForm,
    ProveedorForm,
    UsuarioForm,
)
from .models import (
    ItemNotaPedido,
    Material,
    NotaPedido,
    Obra,
    OrdenCompra,
    OrdenCompraLinea,
    Proveedor,
)
from .roles import es_admin, GRUPO_ADMINISTRADOR, GRUPO_SOLICITANTE
from .textos import normalizar

MAX_INTENTOS_NUMERO = 5


def _exige(user, *permisos):
    """Levanta 403 si el usuario no tiene ninguno de los permisos dados."""
    if not any(user.has_perm(p) for p in permisos):
        raise PermissionDenied


def _estados_validos():
    """Códigos de estado aceptados por los filtros, derivados de settings.

    Se evita la lista fija ('pendiente', 'aprobada') porque al agregar
    ``cerrado`` el filtro de URL lo descartaba en silencio.
    """
    return {codigo for codigo, _ in settings.ESTADOS_NOTA}


def _siguiente_numero():
    ultimo = NotaPedido.objects.order_by('-numero').values_list('numero', flat=True).first()
    return (ultimo or 0) + 1


def _datos_sugerencias():
    return {
        'obras': list(Obra.objects.order_by('nombre').values_list('nombre', flat=True)),
        'proveedores': list(Proveedor.objects.order_by('nombre').values_list('nombre', flat=True)),
        'prioridades': [p[0] for p in settings.PRIORIDADES],
        'encargados': list(
            NotaPedido.objects.exclude(encargado='').order_by('encargado').values_list('encargado', flat=True).distinct()
        ),
        'solicitantes': list(
            NotaPedido.objects.exclude(solicitante='').order_by('solicitante').values_list('solicitante', flat=True).distinct()
        ),
        'etapas': list(
            NotaPedido.objects.exclude(etapa='').order_by('etapa').values_list('etapa', flat=True).distinct()
        ),
        'vendedores': list(
            NotaPedido.objects.exclude(vendedor='').order_by('vendedor').values_list('vendedor', flat=True).distinct()
        ),
        'retiran': list(
            NotaPedido.objects.exclude(retira='').order_by('retira').values_list('retira', flat=True).distinct()
        ),
        'detalles': list(
            dict.fromkeys(
                list(Material.objects.filter(activo=True).order_by('nombre').values_list('nombre', flat=True))
                + list(ItemNotaPedido.objects.exclude(detalle='').order_by('detalle').values_list('detalle', flat=True).distinct())
            )
        ),
        'especificaciones': list(
            ItemNotaPedido.objects.exclude(especificaciones='').order_by('especificaciones')
            .values_list('especificaciones', flat=True).distinct()
        ),
    }


def _aplicar_resolucion(form, nota):
    obra_nombre = form.cleaned_data.get('obra_nombre')
    proveedor_nombre = form.cleaned_data.get('proveedor_nombre')
    nota.obra = (
        Obra.objects.get_or_create(nombre__iexact=obra_nombre, defaults={'nombre': obra_nombre})[0]
        if obra_nombre else None
    )
    nota.proveedor = (
        Proveedor.objects.get_or_create(nombre__iexact=proveedor_nombre, defaults={'nombre': proveedor_nombre})[0]
        if proveedor_nombre else None
    )
    return nota


def _limpiar_items_vacios(nota):
    for item in nota.items.all():
        vacio = (
            not item.detalle
            and not item.especificaciones
            and not item.estado
            and item.stock in (None, 0, '')
            and item.cantidad in (None, '')
            and item.precio in (None, '')
        )
        if vacio:
            item.delete()


def _resolver_materials(nota):
    """Enlaza cada ítem con su material del catálogo, si la clave coincide.

    La resolución es en el servidor a propósito: si el material fuera un
    ``<select>`` con pk, un POST artesanal podría referenciar cualquier
    material. Acá se busca por clave normalizada del texto escrito.
    """
    for item in nota.items.select_related('material'):
        if item.material_id or not item.detalle:
            continue
        clave = normalizar(item.detalle)
        if not clave:
            continue
        material = Material.objects.filter(clave=clave, activo=True).first()
        if material:
            item.material = material
            item.save(update_fields=['material'])


def _crear_nota(form, formset, user):
    """Crea la nota asignando el N.P. N° con reintentos ante colisiones.

    Con varios usuarios generando notas en paralelo, dos peticiones pueden
    leer el mismo ``numero``; como el campo es único, una recibe
    IntegrityError. El savepoint interno del ``atomic`` permite reintentar sin
    abortar la transacción que envuelve la vista completa.
    """
    nota = _aplicar_resolucion(form, form.save(commit=False)).registrar_autor(user)

    for intento in range(1, MAX_INTENTOS_NUMERO + 1):
        try:
            with transaction.atomic():
                nota.numero = _siguiente_numero()
                nota.save()
            break
        except IntegrityError:
            if intento == MAX_INTENTOS_NUMERO:
                raise

    formset.instance = nota
    formset.save()
    _limpiar_items_vacios(nota)
    _resolver_materials(nota)
    return nota


# ---- Materiales (catálogo maestro) ------------------------------------------

@login_required
@permission_required('pedidos.view_material', raise_exception=True)
def materiales(request):
    q = request.GET.get('q', '').strip()
    lista = Material.objects.annotate(usos=Count('items'))
    if q:
        lista = lista.filter(
            Q(nombre__icontains=q) | Q(clave__icontains=q)
            | Q(unidad__icontains=q) | Q(especificacion__icontains=q)
        )
    if request.method == 'POST':
        _exige(request.user, 'pedidos.add_material')
        form = MaterialForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Material "{form.instance.nombre}" agregado al catálogo.')
            return redirect('pedidos:materiales')
    else:
        form = MaterialForm()
    return render(request, 'pedidos/material_list.html', {
        'materiales': lista,
        'form': form,
        'q': q,
    })


@login_required
@permission_required('pedidos.change_material', raise_exception=True)
def material_editar(request, pk):
    material = get_object_or_404(Material, pk=pk)
    if request.method == 'POST':
        form = MaterialForm(request.POST, instance=material)
        if form.is_valid():
            clave_anterior = material.clave
            form.save()
            # Si cambió el nombre, los ítems que enlazaban la clave vieja
            # quedan apuntando a un material que ya no corresponde.
            if material.clave != clave_anterior:
                _reenlazar_items(material, clave_anterior)
                messages.warning(
                    request,
                    f'Cambió la clave de "{material.nombre}". Revisá los ítems que seguían '
                    'con el nombre anterior.',
                )
            else:
                messages.success(request, f'Material "{material.nombre}" actualizado.')
            return redirect('pedidos:materiales')
    else:
        form = MaterialForm(instance=material)
    return render(request, 'pedidos/material_form.html', {
        'form': form,
        'material': material,
        'usos': ItemNotaPedido.objects.filter(material=material).count(),
    })


def _reenlazar_items(material, clave_anterior):
    """Reasigna a ``material`` los ítems cuyo detalle ya coincide con la clave nueva."""
    for item in ItemNotaPedido.objects.filter(material__isnull=True).select_related('material'):
        if normalizar(item.detalle) == material.clave:
            item.material = material
            item.save(update_fields=['material'])


@login_required
@permission_required('pedidos.delete_material', raise_exception=True)
def material_borrar(request, pk):
    """Desvincula y borra el material. Si ya está en órdenes, solo se desactiva."""
    material = get_object_or_404(Material, pk=pk)
    if request.method != 'POST':
        return redirect('pedidos:materiales')

    en_ordenes = material.lineas_orden.count()
    if en_ordenes:
        material.activo = False
        material.save(update_fields=['activo'])
        messages.warning(
            request,
            f'"{material.nombre}" se usa en {en_ordenes} línea(s) de órdenes de compra: '
            'se desactivó en lugar de borrarse.',
        )
    else:
        nombre = material.nombre
        ItemNotaPedido.objects.filter(material=material).update(material=None)
        material.delete()
        messages.success(
            request,
            f'Material "{nombre}" eliminado. Los ítems que lo usaban quedaron sin catalogar.',
        )
    return redirect('pedidos:materiales')


def _material_por_id(valor):
    """Busca un material por id tolerante: un POST con ``''`` o basura no revienta."""
    try:
        return Material.objects.filter(pk=int(valor)).first()
    except (TypeError, ValueError):
        return None


@login_required
@permission_required('pedidos.change_material', raise_exception=True)
def material_fusionar(request):
    """Unifica materiales duplicados del catálogo en uno solo.

    La normalización no puede saber que "cemento" y "cemento 50kg" son lo mismo:
    eso lo decide el admin. Acá mueve todos los ítems y líneas de orden del
    material elegido al destino, y borra el origen.
    """
    if request.method != 'POST':
        return redirect('pedidos:materiales')

    destino = _material_por_id(request.POST.get('destino'))
    origenes = [
        m for m in (
            _material_por_id(pk) for pk in request.POST.getlist('origenes')
        )
        if m and destino and m.pk != destino.pk
    ]
    if not destino:
        messages.error(request, 'Elegí el material que va a quedar como oficial.')
        return redirect('pedidos:materiales')
    if not origenes:
        messages.error(request, 'Elegí al menos un material para fusionar.')
        return redirect('pedidos:materiales')

    total_items = total_lineas = 0
    with transaction.atomic():
        for origen in origenes:
            total_items += ItemNotaPedido.objects.filter(material=origen).update(material=destino)
            total_lineas += OrdenCompraLinea.objects.filter(material=origen).update(
                material=destino,
            )
            origen.delete()

    mensajes = [f'"{origen.nombre}" → "{destino.nombre}"' for origen in origenes]
    messages.success(
        request,
        f'Materiales unificados: {"; ".join(mensajes)}. '
        f'{total_items} ítem(s) y {total_lineas} línea(s) de orden reasignados.',
    )
    return redirect('pedidos:materiales')


# ---- Compras (consolidado y órdenes al proveedor) ---------------------------

def _notas_para_comprar(params):
    """Notas que todavía generan demanda de compra, ya filtradas.

    Solo los estados de ``ESTADOS_ABIERTOS_NOTA`` y, salvo que se pida lo
    contrario, se excluyen las que ya entraron en una orden vigente. Esa última
    exclusión es lo que evita volver a pedir lo mismo dos veces.
    """
    notas = NotaPedido.objects.filter(estado__in=settings.ESTADOS_ABIERTOS_NOTA)

    obra = params.get('obra')
    if obra and obra.isdigit():
        notas = notas.filter(obra_id=int(obra))
    proveedor = params.get('proveedor')
    if proveedor and proveedor.isdigit():
        notas = notas.filter(proveedor_id=int(proveedor))
    estados = [e for e in params.getlist('estado') if e in _estados_validos()]
    if estados:
        notas = notas.filter(estado__in=estados)
    desde = params.get('desde')
    if desde:
        notas = notas.filter(fecha__gte=desde)
    hasta = params.get('hasta')
    if hasta:
        notas = notas.filter(fecha__lte=hasta)
    if not params.get('incluir_pedidas'):
        notas = notas.exclude(ordenes_compra__anulada=False)
    return notas.distinct()


def _items_consolidados(notas, solo_materiales=None, incluir_sin_catalogar=False, texto=None):
    """Ítems de esas notas listos para agregar."""
    # ``cantidad`` en blanco no es "0": el admin todavía no la cargó, así que no
    # debe sumar al consolidado.
    items = ItemNotaPedido.objects.filter(nota__in=notas).exclude(cantidad__isnull=True)
    if solo_materiales is not None:
        items = items.filter(material__in=solo_materiales)
    if not incluir_sin_catalogar:
        items = items.filter(material__isnull=False)
    if texto:
        items = items.filter(
            Q(detalle__icontains=texto) | Q(material__nombre__icontains=texto)
        )
    return items


@login_required
@permission_required('pedidos.view_ordencompra', raise_exception=True)
def compras(request):
    """Resumen de qué hay que comprar, agrupado por material y desglosado por obra."""
    params = request.GET
    notas = _notas_para_comprar(params)
    incluir_sin_catalogar = bool(params.get('sin_catalogar'))
    items = _items_consolidados(
        notas,
        incluir_sin_catalogar=incluir_sin_catalogar,
        texto=params.get('q', '').strip(),
    )

    # Un item por material: total y cantidad de notas/obras que lo piden.
    totales = list(
        items.exclude(material__isnull=True)
        .values('material_id', 'material__nombre', 'material__unidad', 'material__especificacion')
        .annotate(
            total=Coalesce(Sum('cantidad'), Decimal('0')),
            notas=Count('nota', distinct=True),
            obras=Count('nota__obra', distinct=True),
        )
        .order_by('material__nombre')
    )

    # Segunda agregación para el desglose por obra (sin N+1: son 2 consultas).
    por_obra = list(
        items.exclude(material__isnull=True)
        .values('material_id', 'nota__obra_id', 'nota__obra__nombre')
        .annotate(cantidad=Sum('cantidad'))
        .order_by('material_id', 'nota__obra__nombre')
    )
    desglose = {}
    for fila in por_obra:
        desglose.setdefault(fila['material_id'], []).append({
            'nombre': fila['nota__obra__nombre'] or '(sin obra)',
            'cantidad': fila['cantidad'],
        })

    # Ítems que no están en el catálogo: no se pueden agrupar, se avisan aparte.
    sin_catalogar = list(
        items.filter(material__isnull=True)
        .exclude(detalle='')
        .values('detalle')
        .annotate(
            total=Coalesce(Sum('cantidad'), Decimal('0')),
            notas=Count('nota', distinct=True),
        )
        .order_by('detalle')
    )

    return render(request, 'pedidos/compras_list.html', {
        'totales': [(t, desglose.get(t['material_id'], [])) for t in totales],
        'sin_catalogar': sin_catalogar,
        'total_items': sum(t['total'] for t in totales),
        'obras': Obra.objects.filter(activa=True),
        'proveedores': Proveedor.objects.all(),
        'estados': settings.ESTADOS_NOTA,
        'ordenes': (
            OrdenCompra.objects.select_related('proveedor').prefetch_related('notas')[:10]
        ),
        'filtros': {
            'obra': params.get('obra', ''),
            'proveedor': params.get('proveedor', ''),
            'estado': params.getlist('estado'),
            'desde': params.get('desde', ''),
            'hasta': params.get('hasta', ''),
            'q': params.get('q', '').strip(),
            'material': params.get('material', ''),
            'incluir_pedidas': bool(params.get('incluir_pedidas')),
            'sin_catalogar': incluir_sin_catalogar,
        },
        'hay_datos': bool(totales or sin_catalogar),
    })


def _siguiente_numero_orden():
    ultimo = OrdenCompra.objects.order_by('-numero').values_list('numero', flat=True).first()
    return (ultimo or 0) + 1


def _precios_del_post(post):
    """Lee ``precio_<material_id>``; un precio inválido se ignora (queda en 0)."""
    precios = {}
    for material_id in post.getlist('materiales'):
        if not material_id.isdigit():
            continue
        crudo = post.get(f'precio_{material_id}', '').strip().replace(',', '.')
        if not crudo:
            continue
        try:
            valor = Decimal(crudo)
        except (ArithmeticError, ValueError, TypeError):
            continue
        if valor >= 0:
            precios[int(material_id)] = valor.quantize(Decimal('0.01'))
    return precios


@login_required
@permission_required('pedidos.add_ordencompra', raise_exception=True)
@transaction.atomic
def compras_crear_orden(request):
    """Arma la orden al proveedor con los materiales tildados del consolidado.

    Las cantidades y las notas de origen se recalculan en el servidor con los
    mismos filtros del consolidado: no se confía en lo que manda el formulario.
    """
    if request.method != 'POST':
        return redirect('pedidos:compras')

    pedidos = request.POST.getlist('materiales')
    if not pedidos:
        messages.error(request, 'Tildá al menos un material para crear la orden.')
        return redirect('pedidos:compras')

    notas = _notas_para_comprar(request.POST)
    materiales = Material.objects.filter(pk__in=[m for m in pedidos if m.isdigit()], activo=True)
    items = _items_consolidados(
        notas,
        solo_materiales=materiales,
        incluir_sin_catalogar=bool(request.POST.get('sin_catalogar')),
        texto=request.POST.get('q', '').strip(),
    )
    if not items.exists():
        messages.error(
            request,
            'Con los filtros actuales no queda nada por comprar para esos materiales.',
        )
        return redirect('pedidos:compras')

    # Los campos de la orden llegan con prefijo "orden_" para no chocar con los
    # filtros, que también tienen un "proveedor" (proveedor ya asignado).
    form = OrdenCompraForm({
        'proveedor': request.POST.get('orden_proveedor', ''),
        'fecha': request.POST.get('orden_fecha', ''),
        'observaciones': request.POST.get('orden_observaciones', ''),
    })
    if not form.is_valid():
        messages.error(request, 'Revisá el proveedor y la fecha de la orden.')
        return redirect('pedidos:compras')

    totales = {
        fila['material_id']: fila['total']
        for fila in items.values('material_id').annotate(total=Sum('cantidad'))
    }
    orden = form.save(commit=False)
    orden.creado_por = request.user
    for intento in range(1, MAX_INTENTOS_NUMERO + 1):
        try:
            with transaction.atomic():
                orden.numero = _siguiente_numero_orden()
                orden.save()
            break
        except IntegrityError:
            if intento == MAX_INTENTOS_NUMERO:
                raise

    precios = _precios_del_post(request.POST)
    for material in materiales:
        cantidad = totales.get(material.pk)
        if cantidad:
            orden.lineas.create(
                material=material,
                cantidad=cantidad,
                especificacion=material.especificacion,
                precio=precios.get(material.pk) or Decimal('0'),
            )
    orden.notas.set(items.values_list('nota', flat=True).distinct())

    if request.POST.get('marcar_cerrado'):
        for nota in orden.notas.all():
            nota.estado = 'cerrado'
            nota.cerrado_por = _nombre_actor(request.user)
            nota.save(update_fields=['estado', 'cerrado_por', 'updated_at'])

    messages.success(
        request,
        f'Orden de Compra N° {orden.numero:04d} creada para {orden.proveedor} '
        f'con {orden.lineas.count()} material(es).',
    )
    return redirect('pedidos:orden_detalle', pk=orden.pk)


@login_required
@permission_required('pedidos.view_ordencompra', raise_exception=True)
def orden_detalle(request, pk):
    orden = get_object_or_404(
        OrdenCompra.objects.select_related('proveedor', 'creado_por').prefetch_related(
            'notas__obra', 'lineas__material'
        ),
        pk=pk,
    )
    return render(request, 'pedidos/orden_detalle.html', {'orden': orden})


@login_required
@permission_required('pedidos.change_ordencompra', raise_exception=True)
def orden_anular(request, pk):
    """Deshace la orden: sus notas vuelven al consolidado.

    Solo se reabren las que esta orden cerró. Si el administrador ya había
    cerrado alguna antes de crearla, se respeta ese estado: anular un pedido mal
    hecho no significa deshacer el cierre de una nota que ya estaba cerrada.
    """
    orden = get_object_or_404(OrdenCompra, pk=pk)
    if request.method != 'POST':
        return redirect('pedidos:orden_detalle', pk=pk)
    if orden.anulada:
        messages.info(request, f'Orden N° {orden.numero:04d} ya estaba anulada.')
    else:
        reabiertas = list(orden.notas.filter(estado='cerrado'))
        with transaction.atomic():
            orden.anulada = True
            orden.save(update_fields=['anulada'])
            for nota in reabiertas:
                nota.estado = 'pendiente'
                nota.cerrado_por = ''
                nota.save(update_fields=['estado', 'cerrado_por', 'updated_at'])
        detalle = f' Sus {len(reabiertas)} nota(s) cerradas se reabrieron.' if reabiertas else ''
        messages.success(
            request,
            f'Orden N° {orden.numero:04d} anulada. Sus notas vuelven al consolidado.{detalle}',
        )
    return redirect('pedidos:compras')


@login_required
@permission_required('pedidos.view_ordencompra', raise_exception=True)
def orden_descargar(request, pk):
    orden = get_object_or_404(
        OrdenCompra.objects.select_related('proveedor').prefetch_related(
            'lineas__material', 'notas'
        ),
        pk=pk,
    )
    return excel.orden_compra_response(orden)


# ---- Notas de pedido -------------------------------------------------------

@login_required
@permission_required('pedidos.view_notapedido', raise_exception=True)
def panel(request):
    notas = NotaPedido.objects.visibles_para(request.user)
    estado = request.GET.get('estado', '')
    q = request.GET.get('q', '').strip()

    if estado and estado in _estados_validos():
        notas = notas.filter(estado=estado)
    if q:
        notas = notas.filter(
            Q(numero__icontains=q)
            | Q(obra__nombre__icontains=q)
            | Q(solicitante__icontains=q)
            | Q(proveedor__nombre__icontains=q)
        )

    context = {
        'notas': notas,
        'estados': settings.ESTADOS_NOTA,
        'estado': estado,
        'q': q,
        'es_admin': es_admin(request.user),
        'contadores': {codigo: notas.filter(estado=codigo).count() for codigo, _ in settings.ESTADOS_NOTA},
        'cant_pendientes': notas.filter(estado='pendiente').count(),
        'cant_aprobadas': notas.filter(estado='aprobada').count(),
        'cant_cerradas': notas.filter(estado='cerrado').count(),
    }
    return render(request, 'pedidos/nota_list.html', context)


@login_required
@permission_required('pedidos.add_notapedido', raise_exception=True)
@transaction.atomic
def nueva(request):
    admin = es_admin(request.user)
    if request.method == 'POST':
        form = NotaPedidoForm(request.POST, es_admin=admin)
        formset = ItemFormSet(request.POST, form_kwargs={'es_admin': admin})
        if form.is_valid() and formset.is_valid():
            nota = _crear_nota(form, formset, request.user)
            messages.success(request, f'Nota de Pedido N° {nota.numero} creada correctamente.')
            return redirect('pedidos:panel')
    else:
        form = NotaPedidoForm(es_admin=admin)
        formset = ItemFormSet(form_kwargs={'es_admin': admin})

    return render(request, 'pedidos/nota_form.html', {
        'form': form,
        'formset': formset,
        'titulo': 'Nueva Nota de Pedido',
        'max_items': settings.MAX_ITEMS,
        'sugerencias': _datos_sugerencias(),
    })


@login_required
@permission_required('pedidos.view_notapedido', raise_exception=True)
def detalle(request, pk):
    nota = get_object_or_404(NotaPedido.objects.visibles_para(request.user), pk=pk)
    return render(request, 'pedidos/nota_detalle.html', {'nota': nota})


@login_required
@permission_required('pedidos.change_notapedido', raise_exception=True)
@transaction.atomic
def editar(request, pk):
    nota = get_object_or_404(NotaPedido.objects, pk=pk)
    # Una nota cerrada es un registro ya firmado: no se toca sin reabrirla.
    # El formulario sigue siendo la vía para reabrir (cerrado -> pendiente).
    if request.method == 'POST':
        estado_previo = nota.estado
        form = NotaPedidoForm(request.POST, instance=nota)
        formset = ItemFormSet(request.POST, instance=nota, form_kwargs={'es_admin': es_admin(request.user)})
        if form.is_valid() and formset.is_valid():
            # Solo se permite tocar el contenido si la nota no está cerrada;
            # cambiar el estado (reabrir) sí vale.
            if nota.esta_cerrada and form.cleaned_data['estado'] == 'cerrado':
                messages.error(
                    request,
                    f'La nota N° {nota.numero} está cerrada. Reabrila para poder editarla.',
                )
                return redirect('pedidos:panel')
            nota = _aplicar_resolucion(form, form.save(commit=False))
            nota.save()
            # Si el administrador llevó la nota a "cerrado" desde el formulario,
            # se sella quién lo hizo (el form no conoce al actor).
            if nota.estado == 'cerrado' and estado_previo != 'cerrado':
                nota.cerrado_por = _nombre_actor(request.user)
                nota.save(update_fields=['cerrado_por'])
            formset.save()
            _limpiar_items_vacios(nota)
            _resolver_materials(nota)
            messages.success(request, f'Nota N° {nota.numero} actualizada correctamente.')
            return redirect('pedidos:panel')
    else:
        form = NotaPedidoForm(instance=nota)
        formset = ItemFormSet(instance=nota, form_kwargs={'es_admin': es_admin(request.user)})

    return render(request, 'pedidos/nota_form.html', {
        'form': form,
        'formset': formset,
        'nota': nota,
        'titulo': f'Editar Nota N° {nota.numero}',
        'max_items': settings.MAX_ITEMS,
        'sugerencias': _datos_sugerencias(),
    })


@login_required
@permission_required('pedidos.delete_notapedido', raise_exception=True)
@transaction.atomic
def borrar(request, pk):
    nota = get_object_or_404(NotaPedido, pk=pk)
    if request.method == 'POST':
        numero = nota.numero
        nota.delete()
        messages.success(request, f'Nota N° {numero} eliminada.')
        return redirect('pedidos:panel')
    return render(request, 'pedidos/nota_confirm_delete.html', {'nota': nota})


def _nombre_actor(user):
    return user.get_full_name() or user.get_username()


@login_required
@permission_required('pedidos.change_notapedido', raise_exception=True)
def aprobar(request, pk):
    nota = get_object_or_404(NotaPedido, pk=pk)
    if request.method != 'POST':
        return redirect('pedidos:panel')

    if nota.estado == 'cerrado':
        messages.warning(
            request,
            f'Nota N° {nota.numero} está cerrada. Reabrirla para poder modificarla.',
        )
        return redirect('pedidos:panel')

    if nota.estado == 'aprobada':
        nota.estado = 'pendiente'
        nota.aprobado_por = ''
        messages.info(request, f'Nota N° {nota.numero} vuelta a Pendiente.')
    else:
        nota.estado = 'aprobada'
        nota.aprobado_por = _nombre_actor(request.user)
        messages.success(request, f'Nota N° {nota.numero} aprobada.')
    nota.save(update_fields=['estado', 'aprobado_por', 'updated_at'])
    return redirect('pedidos:panel')


@login_required
@permission_required('pedidos.change_notapedido', raise_exception=True)
def cerrar(request, pk):
    """Marca la nota como comprada (``cerrado``) o la reabre a ``pendiente``."""
    nota = get_object_or_404(NotaPedido, pk=pk)
    if request.method != 'POST':
        return redirect('pedidos:panel')

    if nota.estado == 'cerrado':
        nota.estado = 'pendiente'
        nota.cerrado_por = ''
        messages.info(request, f'Nota N° {nota.numero} reabierta a Pendiente.')
    else:
        nota.estado = 'cerrado'
        nota.cerrado_por = _nombre_actor(request.user)
        # Se conserva ``aprobado_por`` para que el Excel siga mostrando la firma.
        messages.success(request, f'Nota N° {nota.numero} cerrada.')
    nota.save(update_fields=['estado', 'cerrado_por', 'updated_at'])
    return redirect('pedidos:panel')


@login_required
@permission_required('pedidos.view_notapedido', raise_exception=True)
def descargar(request, pk):
    nota = get_object_or_404(NotaPedido.objects.visibles_para(request.user).para_exportar(), pk=pk)
    return excel.excel_response(nota)


@login_required
@permission_required('pedidos.change_notapedido', raise_exception=True)
def descargar_todas(request):
    notas = NotaPedido.objects.para_exportar()
    estado = request.GET.get('estado', '')
    if estado in _estados_validos():
        notas = notas.filter(estado=estado)
    if not notas:
        messages.warning(request, 'No hay notas para descargar.')
        return redirect('pedidos:panel')
    return excel.zip_response(notas)


# ---- Obras -----------------------------------------------------------------

@login_required
def obras(request):
    _exige(request.user, 'pedidos.add_obra', 'pedidos.view_obra')
    if request.method == 'POST':
        _exige(request.user, 'pedidos.add_obra')
        form = ObraForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Obra agregada.')
            return redirect('pedidos:obras')
    else:
        form = ObraForm()
    return render(request, 'pedidos/obra_list.html', {
        'obras': Obra.objects.all(),
        'form': form,
    })


@login_required
@permission_required('pedidos.change_obra', raise_exception=True)
def obra_editar(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    if request.method == 'POST':
        form = ObraForm(request.POST, instance=obra)
        if form.is_valid():
            form.save()
            messages.success(request, 'Obra actualizada.')
            return redirect('pedidos:obras')
    else:
        form = ObraForm(instance=obra)
    return render(request, 'pedidos/obra_form.html', {'form': form, 'obra': obra})


@login_required
@permission_required('pedidos.delete_obra', raise_exception=True)
def obra_borrar(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    if request.method == 'POST':
        obra.delete()
        messages.success(request, 'Obra eliminada.')
    return redirect('pedidos:obras')


# ---- Proveedores -----------------------------------------------------------

@login_required
def proveedores(request):
    _exige(request.user, 'pedidos.add_proveedor', 'pedidos.view_proveedor')
    if request.method == 'POST':
        _exige(request.user, 'pedidos.add_proveedor')
        form = ProveedorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor agregado.')
            return redirect('pedidos:proveedores')
    else:
        form = ProveedorForm()
    return render(request, 'pedidos/proveedor_list.html', {
        'proveedores': Proveedor.objects.all(),
        'form': form,
    })


@login_required
@permission_required('pedidos.change_proveedor', raise_exception=True)
def proveedor_editar(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor actualizado.')
            return redirect('pedidos:proveedores')
    else:
        form = ProveedorForm(instance=proveedor)
    return render(request, 'pedidos/proveedor_form.html', {'form': form, 'proveedor': proveedor})


@login_required
@permission_required('pedidos.delete_proveedor', raise_exception=True)
def proveedor_borrar(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        proveedor.delete()
        messages.success(request, 'Proveedor eliminado.')
    return redirect('pedidos:proveedores')


# ---- Usuarios --------------------------------------------------------------

def _hay_otros_administradores(user):
    """True si queda algún administrador activo además de ``user``."""
    return (
        User.objects.filter(groups__name=GRUPO_ADMINISTRADOR, is_active=True)
        .exclude(pk=user.pk).exists()
        or User.objects.filter(is_superuser=True, is_active=True).exclude(pk=user.pk).exists()
    )


def _solicitantes_activos():
    """Usuarios que solo generan notas de pedido."""
    return User.objects.filter(
        groups__name=GRUPO_SOLICITANTE, is_active=True,
    ).exclude(groups__name=GRUPO_ADMINISTRADOR).distinct().order_by('username')


def _administradores_activos():
    return User.objects.filter(
        Q(groups__name=GRUPO_ADMINISTRADOR) | Q(is_superuser=True),
        is_active=True,
    ).distinct().order_by('username')


@login_required
@permission_required('auth.add_user', raise_exception=True)
def usuarios(request):
    return render(request, 'pedidos/usuario_list.html', {
        'administradores': _administradores_activos(),
        'solicitantes': _solicitantes_activos(),
        'sin_rol': User.objects.filter(is_active=True).exclude(
            Q(groups__name__in=[GRUPO_ADMINISTRADOR, GRUPO_SOLICITANTE]) | Q(is_superuser=True),
        ).distinct().order_by('username'),
    })


@login_required
@permission_required('auth.add_user', raise_exception=True)
def usuario_crear(request):
    form = UsuarioForm(request.POST or None, actor=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Usuario "{form.instance.username}" creado correctamente.')
        return redirect('pedidos:usuarios')
    return render(request, 'pedidos/usuario_form.html', {
        'form': form,
        'titulo': 'Nuevo usuario',
    })


@login_required
@permission_required('auth.change_user', raise_exception=True)
def usuario_editar(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    form = UsuarioForm(
        request.POST or None, instance=usuario, actor=request.user, cambiar_password=request.method == 'POST',
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Usuario "{usuario.username}" actualizado correctamente.')
        return redirect('pedidos:usuarios')
    return render(request, 'pedidos/usuario_form.html', {
        'form': form,
        'usuario': usuario,
        'titulo': f'Editar usuario: {usuario.username}',
    })


@login_required
@permission_required('auth.delete_user', raise_exception=True)
def usuario_borrar(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    if request.method != 'POST':
        return redirect('pedidos:usuarios')

    if usuario == request.user:
        messages.error(request, 'No podés desactivar tu propio usuario.')
        return redirect('pedidos:usuarios')

    if usuario.groups.filter(name=GRUPO_ADMINISTRADOR).exists() and not _hay_otros_administradores(request.user):
        messages.error(request, 'No podés desactivar al último administrador.')
        return redirect('pedidos:usuarios')

    notas = usuario.notas_creadas.count()
    usuario.is_active = False
    usuario.save(update_fields=['is_active'])
    messages.success(
        request, f'Usuario "{usuario.username}" desactivado. Conserva sus {notas} nota(s) creadas.'
    )
    return redirect('pedidos:usuarios')