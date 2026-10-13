from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, User
from django.forms import inlineformset_factory

from .models import ItemNotaPedido, Material, NotaPedido, Obra, OrdenCompra, Proveedor
from .roles import GRUPO_ADMINISTRADOR, GRUPO_SOLICITANTE
from .textos import normalizar

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
    # Sección "Para Administración": solo el administrador la ve y la completa.
    # Ocultarla en el template no alcanza (un POST artesanal la llenaría), así
    # que los campos se eliminan del formulario para los demás roles.
    CAMPOS_ADMIN = ['proveedor_nombre', 'creado_por', 'vendedor', 'retira', 'para_envio', 'a_retirar', 'estado']

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

    estado = forms.ChoiceField(
        label='Estado',
        required=False,
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Cerrado = el material ya se compró y deja de aparecer en el consolidado de compras.',
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

    def __init__(self, *args, es_admin=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.es_admin = es_admin
        self._add_bootstrap_classes()
        if not es_admin:
            for campo in self.CAMPOS_ADMIN:
                self.fields.pop(campo, None)
        instance = getattr(self, 'instance', None)
        actual = instance.estado if (instance and instance.pk) else 'pendiente'
        if 'estado' in self.fields:
            # Solo se ofrecen las transiciones válidas desde el estado actual.
            permitidos = settings.TRANSICIONES_ESTADO.get(actual, [actual])
            etiquetas = dict(settings.ESTADOS_NOTA)
            self.fields['estado'].choices = [
                (c, etiquetas.get(c, c)) for c in permitidos
            ]
            self.fields['estado'].initial = actual
        if instance and instance.pk:
            if 'obra_nombre' in self.fields:
                self.fields['obra_nombre'].initial = instance.obra.nombre if instance.obra else ''
            if 'proveedor_nombre' in self.fields:
                self.fields['proveedor_nombre'].initial = instance.proveedor.nombre if instance.proveedor else ''
            self.fields['prioridad'].initial = instance.prioridad

    def clean_obra_nombre(self):
        return (self.cleaned_data.get('obra_nombre') or '').strip()

    def clean_proveedor_nombre(self):
        return (self.cleaned_data.get('proveedor_nombre') or '').strip()

    def save(self, commit=True):
        nota = super().save(commit=commit)
        # ``estado`` es un campo del formulario y no del Meta.fields, así que
        # hay que aplicarlo a mano. Vacío significa "dejar el estado actual".
        # El sellado de ``cerrado_por`` lo hace la vista, que conoce al actor.
        nuevo = self.cleaned_data.get('estado')
        if nuevo and nuevo != nota.estado:
            nota.estado = nuevo
            if nuevo != 'cerrado':
                nota.cerrado_por = ''
        if commit and 'estado' in self.fields:
            nota.save(update_fields=['estado', 'cerrado_por', 'updated_at'])
        return nota


class ItemNotaPedidoForm(BootstrapFormMixin, forms.ModelForm):
    # Igual que en NotaPedidoForm: el solicitante no completa stock, estado ni
    # precio (los llena administración al momento de comprar). Ocultarlos en el
    # template no alcanza: un POST artesanal los llenaría igual, así que los
    # campos se eliminan del formulario para los demás roles.
    CAMPOS_ADMIN = ['stock', 'estado', 'precio']

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

    def __init__(self, *args, es_admin=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.es_admin = es_admin
        self._add_bootstrap_classes()
        if not es_admin:
            for campo in self.CAMPOS_ADMIN:
                self.fields.pop(campo, None)
        self.fields['detalle'].required = False
        self.fields['cantidad'].required = False
        if 'stock' in self.fields:
            self.fields['stock'].required = False

    @property
    def muestra_admin(self):
        return 'stock' in self.fields


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


class MaterialForm(BootstrapFormMixin, forms.ModelForm):
    """Alta/edición del catálogo maestro de materiales."""

    class Meta:
        model = Material
        fields = ['nombre', 'unidad', 'especificacion', 'notas', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={**DATALIST_ATTR, 'list': 'datalist-materiales', 'placeholder': 'Cemento 50kg'}),
            'unidad': forms.TextInput(attrs={'placeholder': 'bolsa, kg, m3, metro…'}),
            'especificacion': forms.TextInput(attrs={'placeholder': '50 kg'}),
            'notas': forms.TextInput(attrs={'placeholder': 'Observaciones internas'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._add_bootstrap_classes()

    def clean_nombre(self):
        """La clave normalizada es única: el conflicto se reporta en el campo.

        ``clave`` es ``editable=False`` y no está en ``fields``, así que
        ``validate_unique`` no lo revisa y el choque llegaría como un 500 desde
        la restricción UNIQUE de la base.
        """
        nombre = self.cleaned_data['nombre']
        clave = normalizar(nombre)
        if not clave:
            raise forms.ValidationError('Escribí un nombre de material.')
        repetidos = Material.objects.filter(clave=clave)
        if self.instance.pk:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise forms.ValidationError(
                f'Ya existe el material "{repetidos.first().nombre}" con el mismo nombre '
                f'(sin tildes ni mayúsculas). Editá ese en lugar de crear otro.'
            )
        return nombre


class OrdenCompraForm(BootstrapFormMixin, forms.ModelForm):
    """Encabezado de la orden que se manda al proveedor.

    ``anulada`` queda fuera a propósito: nace la orden vigente y anularla es una
    acción aparte (``orden_anular``), no algo que se marque al crearla.
    """

    class Meta:
        model = OrdenCompra
        fields = ['proveedor', 'fecha', 'observaciones']
        widgets = {
            'proveedor': forms.Select(attrs={'class': 'form-select'}),
            'fecha': DateInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Condiciones de pago, plazo de entrega…'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._add_bootstrap_classes()


class UsuarioForm(BootstrapFormMixin, UserCreationForm):
    """Alta/edición de usuarios con los dos roles de la aplicación.

    No expone ``is_staff`` ni ``is_superuser``: la pantalla de usuarios solo
    asigna roles, nunca privilegio de Django admin.
    """

    first_name = forms.CharField(label='Nombre', max_length=150, required=False)
    last_name = forms.CharField(label='Apellido', max_length=150, required=False)
    email = forms.EmailField(label='Email', required=False)
    es_admin = forms.BooleanField(
        label='Administrador', required=False,
        help_text='Puede ver y editar todas las notas, aprobar, gestionar obras, proveedores y usuarios.',
    )
    es_solicitante = forms.BooleanField(
        label='Solicitante', required=False,
        help_text='Solo puede generar notas de pedido y ver las suyas.',
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def __init__(self, *args, actor=None, cambiar_password=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.es_edicion_propia = (
            actor is not None and bool(self.instance.pk) and self.instance.pk == actor.pk
        )
        # Necesario para restaurar el hash si el admin deja la clave en blanco.
        self._password_previo = self.instance.password
        self._add_bootstrap_classes()

        if self.instance.pk:
            if cambiar_password:
                # Campos opcionales: vacíos = conservar la contraseña actual.
                for campo in ('password1', 'password2'):
                    self.fields[campo].required = False
            else:
                for campo in ('password1', 'password2'):
                    self.fields.pop(campo)
            roles_actuales = {g.name for g in self.instance.groups.all()}
            self.fields['es_admin'].initial = GRUPO_ADMINISTRADOR in roles_actuales
            self.fields['es_solicitante'].initial = GRUPO_SOLICITANTE in roles_actuales

    def clean_username(self):
        """Al editar, el propio registro no cuenta como nombre duplicado.

        ``UserCreationForm.clean_username`` rechaza cualquier coincidencia
        existente; acá se deja pasar el nombre del usuario que se está
        editando (incluso con distinta capitalización).
        """
        username = self.cleaned_data['username']
        if self.instance.pk and User.objects.filter(
            pk=self.instance.pk, **{f'{User.USERNAME_FIELD}__iexact': username}
        ).exists():
            return username
        return super().clean_username()

    def clean(self):
        cleaned = super().clean()
        # El admin no puede quitarse a sí mismo el rol, ni desde el formulario
        # (checkbox desmarcado) ni con un POST artesanal. Se usa error global
        # (no de campo) porque ``add_error`` borraría el valor de cleaned_data.
        if self.es_edicion_propia and not cleaned.get('es_admin'):
            cleaned['es_admin'] = True
            cleaned['es_solicitante'] = True
            self.add_error(None, 'No podés quitarte a vos mismo el rol de administrador.')
        if not cleaned.get('es_admin') and not cleaned.get('es_solicitante'):
            raise forms.ValidationError('Tenés que asignar al menos un rol.')
        return cleaned

    def _aplicar_grupos(self, es_admin, es_solicitante, instance):
        objetivo = set()
        if es_admin:
            objetivo.add(self._grupo(GRUPO_ADMINISTRADOR))
        if es_solicitante:
            objetivo.add(self._grupo(GRUPO_SOLICITANTE))
        instance.groups.set(objetivo)
        instance.is_superuser = False
        instance.is_staff = False

    @staticmethod
    def _grupo(nombre):
        try:
            return Group.objects.get(name=nombre)
        except Group.DoesNotExist:
            raise forms.ValidationError(
                f'Falta el grupo "{nombre}". Ejecutá: python manage.py crear_roles'
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not self.cleaned_data.get('password1'):
            # super() seteó el hash de una clave vacía: se restaura el original.
            instance.password = self._password_previo
        instance.is_superuser = False
        instance.is_staff = False
        if commit:
            # El M2M de grupos exige la instancia ya persistida.
            instance.save()
            self._aplicar_grupos(
                self.cleaned_data['es_admin'], self.cleaned_data['es_solicitante'], instance
            )
        return instance