from django.db import transaction
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import excel
from .forms import ItemFormSet, NotaPedidoForm, ObraForm, ProveedorForm
from .models import NotaPedido, ItemNotaPedido, Obra, Proveedor


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
            ItemNotaPedido.objects.exclude(detalle='').order_by('detalle').values_list('detalle', flat=True).distinct()
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


def panel(request):
    notas = NotaPedido.objects.select_related('obra', 'proveedor').all()
    estado = request.GET.get('estado', '')
    q = request.GET.get('q', '').strip()

    if estado and estado in ('pendiente', 'aprobada'):
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
        'estado': estado,
        'q': q,
        'cant_pendientes': NotaPedido.objects.filter(estado='pendiente').count(),
        'cant_aprobadas': NotaPedido.objects.filter(estado='aprobada').count(),
    }
    return render(request, 'pedidos/nota_list.html', context)


@transaction.atomic
def nueva(request):
    if request.method == 'POST':
        form = NotaPedidoForm(request.POST)
        formset = ItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            nota = _aplicar_resolucion(form, form.save(commit=False))
            nota.numero = _siguiente_numero()
            nota.save()
            formset.instance = nota
            formset.save()
            _limpiar_items_vacios(nota)
            messages.success(request, f'Nota de Pedido N° {nota.numero} creada correctamente.')
            return redirect('pedidos:panel')
    else:
        form = NotaPedidoForm()
        formset = ItemFormSet()

    return render(request, 'pedidos/nota_form.html', {
        'form': form,
        'formset': formset,
        'titulo': 'Nueva Nota de Pedido',
        'max_items': settings.MAX_ITEMS,
        'sugerencias': _datos_sugerencias(),
    })


def detalle(request, pk):
    nota = get_object_or_404(NotaPedido.objects.select_related('obra', 'proveedor'), pk=pk)
    return render(request, 'pedidos/nota_detalle.html', {'nota': nota})


@transaction.atomic
def editar(request, pk):
    nota = get_object_or_404(NotaPedido.objects.select_related('obra', 'proveedor'), pk=pk)
    if request.method == 'POST':
        form = NotaPedidoForm(request.POST, instance=nota)
        formset = ItemFormSet(request.POST, instance=nota)
        if form.is_valid() and formset.is_valid():
            nota = _aplicar_resolucion(form, form.save(commit=False))
            nota.save()
            formset.save()
            _limpiar_items_vacios(nota)
            messages.success(request, f'Nota N° {nota.numero} actualizada correctamente.')
            return redirect('pedidos:panel')
    else:
        form = NotaPedidoForm(instance=nota)
        formset = ItemFormSet(instance=nota)

    return render(request, 'pedidos/nota_form.html', {
        'form': form,
        'formset': formset,
        'nota': nota,
        'titulo': f'Editar Nota N° {nota.numero}',
        'max_items': settings.MAX_ITEMS,
        'sugerencias': _datos_sugerencias(),
    })


@transaction.atomic
def borrar(request, pk):
    nota = get_object_or_404(NotaPedido, pk=pk)
    if request.method == 'POST':
        numero = nota.numero
        nota.delete()
        messages.success(request, f'Nota N° {numero} eliminada.')
        return redirect('pedidos:panel')
    return render(request, 'pedidos/nota_confirm_delete.html', {'nota': nota})


def aprobar(request, pk):
    nota = get_object_or_404(NotaPedido, pk=pk)
    if request.method == 'POST':
        if nota.estado == 'aprobada':
            nota.estado = 'pendiente'
            nota.aprobado_por = ''
            nota.save()
            messages.info(request, f'Nota N° {nota.numero} vuelta a Pendiente.')
        else:
            aprobador = request.POST.get('aprobado_por', '').strip()
            nota.aprobado_por = aprobador or nota.solicitante
            nota.estado = 'aprobada'
            nota.save()
            messages.success(request, f'Nota N° {nota.numero} aprobada.')
    return redirect('pedidos:panel')


def descargar(request, pk):
    nota = get_object_or_404(NotaPedido, pk=pk)
    return excel.excel_response(nota)


def descargar_todas(request):
    notas = NotaPedido.objects.select_related('obra').all()
    estado = request.GET.get('estado', '')
    if estado in ('pendiente', 'aprobada'):
        notas = notas.filter(estado=estado)
    if not notas:
        messages.warning(request, 'No hay notas para descargar.')
        return redirect('pedidos:panel')
    return excel.zip_response(notas)


# ---- Obras ---------------------------------------------------------------

def obras(request):
    if request.method == 'POST':
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


def obra_borrar(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    if request.method == 'POST':
        obra.delete()
        messages.success(request, 'Obra eliminada.')
    return redirect('pedidos:obras')


# ---- Proveedores ---------------------------------------------------------

def proveedores(request):
    if request.method == 'POST':
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


def proveedor_borrar(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        proveedor.delete()
        messages.success(request, 'Proveedor eliminado.')
    return redirect('pedidos:proveedores')