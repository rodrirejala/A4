from django import forms
from django.conf import settings
from django.forms import inlineformset_factory

from .models import ItemNotaPedido, NotaPedido, Obra, Proveedor

DATALIST_ATTR = {'autocomplete': 'off', 'class': 'form-control'}


class BootstrapFormMixin:
    def _add_bootstrap_classes(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(field.widget, (forms.Select,)):
                field.widget.attrs.setdefault('class', 'form-select')
            else:
                field.widget.attrs.setdefault('class', 'form-control')


class DateInput(forms.DateInput):
    input_type = 'date'


class NotaPedidoForm(BootstrapFormMixin, forms.ModelForm):
    obra_nombre = forms.CharField(
        label='Obra',
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={**DATALIST_ATTR, 'list': 'datalist-obras', 'placeholder': 'Escribí o elegí la obra…'}),
    )
    proveedor_nombre = forms.CharField(
        label='Proveedor',
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={**DATALIST_ATTR, 'list': 'datalist-proveedores', 'placeholder': 'Escribí o elegí el proveedor…'}),
    )
    prioridad = forms.CharField(
        label='Prioridad',
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={**DATALIST_ATTR, 'list': 'datalist-prioridades', 'placeholder': 'Media / Alta / Baja…'}),
    )

    class Meta:
        model = NotaPedido
        fields = [
            'encargado', 'etapa', 'fecha', 'solicitante', 'prioridad',
            'limite', 'vendedor',
            'para_envio', 'a_retirar', 'retira', 'observaciones',
            'creado_por',
        ]
        widgets = {
            'encargado': forms.TextInput(attrs={**DATALIST_ATTR, 'list': 'datalist-encargados', 'placeholder': 'Encargado de la obra…'}),
            'etapa': forms.TextInput(attrs={**DATALIST_ATTR, 'list': 'datalist-etapas', 'placeholder': 'Ej. Etapa 2 losa'}),
            'solicitante': forms.TextInput(attrs={**DATALIST_ATTR, 'list': 'datalist-solicitantes', 'placeholder': 'Quién solicita…'}),
            'fecha': DateInput(attrs={'class': 'form-control'}),
            'limite': DateInput(attrs={'class': 'form-control'}),
            'vendedor': forms.TextInput(attrs={**DATALIST_ATTR, 'list': 'datalist-vendedores', 'placeholder': 'Vendedor/a…'}),
            'retira': forms.TextInput(attrs={**DATALIST_ATTR, 'list': 'datalist-retiran', 'placeholder': 'Quién retira…'}),
            'observaciones': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Observaciones…'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._add_bootstrap_classes()
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            self.fields['obra_nombre'].initial = instance.obra.nombre if instance.obra else ''
            self.fields['proveedor_nombre'].initial = instance.proveedor.nombre if instance.proveedor else ''
            self.fields['prioridad'].initial = instance.prioridad

    def clean_obra_nombre(self):
        return (self.cleaned_data.get('obra_nombre') or '').strip()

    def clean_proveedor_nombre(self):
        return (self.cleaned_data.get('proveedor_nombre') or '').strip()


class ItemNotaPedidoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ItemNotaPedido
        fields = ['stock', 'cantidad', 'detalle', 'especificaciones', 'estado', 'precio']
        widgets = {
            'stock': forms.NumberInput(attrs={'min': '0', 'step': '1', 'placeholder': '0'}),
            'cantidad': forms.NumberInput(attrs={'step': 'any', 'placeholder': '0'}),
            'detalle': forms.TextInput(attrs={'list': 'datalist-detalles', 'placeholder': 'Detalle de las mercaderías…'}),
            'especificaciones': forms.TextInput(attrs={'list': 'datalist-especificaciones', 'placeholder': 'Especificaciones/Medidas…'}),
            'estado': forms.TextInput(attrs={'placeholder': 'Estado…'}),
            'precio': forms.NumberInput(attrs={'step': 'any'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._add_bootstrap_classes()
        self.fields['detalle'].required = False
        self.fields['cantidad'].required = False
        self.fields['stock'].required = False


ItemFormSet = inlineformset_factory(
    NotaPedido,
    ItemNotaPedido,
    form=ItemNotaPedidoForm,
    extra=1,
    max_num=settings.MAX_ITEMS,
    absolute_max=settings.MAX_ITEMS + 1,
    can_delete=True,
    validate_max=True,
)


class ObraForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Obra
        fields = ['nombre', 'direccion', 'activa']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._add_bootstrap_classes()


class ProveedorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'ruc', 'direccion', 'telefono']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._add_bootstrap_classes()