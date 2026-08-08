# diario/forms.py

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import PersonaImportante, Interaccion, ProsocheHabito, TriggerHabito, Gesto, SeguimientoVires


class CierreDiarioForm(forms.Form):
    reflexion_libre = forms.CharField(required=False, max_length=5000, strip=True)
    friccion_no = forms.TypedChoiceField(
        choices=[(i, str(i)) for i in range(1, 6)], coerce=int, required=True,
    )
    cuerpo_cierre = forms.ChoiceField(
        required=False, choices=[('', 'Sin seleccionar'), *SeguimientoVires.CUERPO_CIERRE_CHOICES]
    )
    estado_animo_noche = forms.TypedChoiceField(
        choices=[(1, 'Bajo'), (2, 'Flojo'), (4, 'Bien'), (5, 'Pleno')],
        coerce=int, required=True,
    )
    habitos_completados = forms.JSONField(required=False, initial=list)
    simbiosis_respuesta = forms.CharField(required=False, max_length=5000, strip=True)
    simbiosis_pregunta = forms.CharField(required=False, max_length=5000, strip=True)
    analisis_cierre_token = forms.CharField(required=False, max_length=24576, strip=True)
    idempotency_key = forms.UUIDField(required=True)
    expected_version = forms.IntegerField(required=True, min_value=0)

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

    def clean_habitos_completados(self):
        ids = self.cleaned_data.get('habitos_completados') or []
        if not isinstance(ids, list) or any(type(pk) is not int for pk in ids):
            raise ValidationError('Debe ser una lista de identificadores enteros.')
        validos = set(Gesto.objects.filter(
            usuario=self.usuario, estado='activo', pk__in=ids
        ).values_list('pk', flat=True))
        if validos != set(ids):
            raise ValidationError('Incluye gestos inexistentes, inactivos o ajenos.')
        return sorted(validos)


class AperturaDiariaForm(forms.Form):
    ESTADOS_ANIMO = [(1, 'Bajo'), (2, 'Flojo'), (4, 'Bien'), (5, 'Pleno')]

    estado_animo = forms.TypedChoiceField(
        choices=ESTADOS_ANIMO, coerce=int, empty_value=None, required=True
    )
    intencion = forms.CharField(required=False, max_length=1000, strip=True)
    gratitud_1 = forms.CharField(required=False, max_length=200, strip=True)
    soberania = forms.CharField(required=False, max_length=200, strip=True)
    molestia_zona = forms.ChoiceField(
        required=False, choices=[('', 'Sin seleccionar'), *SeguimientoVires.MOLESTIA_ZONAS]
    )
    molestia_nota = forms.CharField(required=False, max_length=500, strip=True)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('molestia_zona') in ('', 'ninguna'):
            cleaned['molestia_nota'] = ''
        return cleaned


class PersonaImportanteForm(forms.ModelForm):
    salud_relacion = forms.TypedChoiceField(
        required=False,
        coerce=int,
        empty_value=None,
        choices=[('', 'Sin valorar'), *[(valor, str(valor)) for valor in range(1, 6)]],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Salud de la Relación (1=Mala, 5=Excelente)',
        error_messages={
            'invalid_choice': 'Elige Sin valorar o un valor entre 1 y 5.',
        },
    )

    class Meta:
        model = PersonaImportante
        fields = ['nombre', 'tipo_relacion', 'salud_relacion', 'notas']
        error_messages = {
            'nombre': {'required': 'Este campo es obligatorio.'},
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Marco Aurelio'}),
            'tipo_relacion': forms.Select(attrs={'class': 'form-select'}),
            'notas': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3, 'placeholder': '¿Qué representa esta persona para ti?'}),
        }
        labels = {
            'nombre': 'Nombre de la Persona',
            'tipo_relacion': 'Tipo de Relación',
            'notas': 'Notas Adicionales',
        }


class InteraccionForm(forms.ModelForm):
    class Meta:
        model = Interaccion
        # Excluimos 'usuario' porque se asignará automáticamente en la vista
        fields = ['titulo', 'fecha', 'personas', 'tipo_interaccion', 'descripcion', 'mi_sentir', 'aprendizaje']

        # Usamos widgets para dar estilo y mejorar la usabilidad
        widgets = {
            'titulo': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Ej: Conversación sobre el futuro'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'personas': forms.CheckboxSelectMultiple(attrs={
                'class': 'personas-checklist',
                'aria-labelledby': 'personas-label',
                'aria-describedby': 'personas-help',
            }),
            'tipo_interaccion': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 4, 'placeholder': '¿Qué sucedió exactamente?'}),
            'mi_sentir': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3, 'placeholder': '¿Cómo me hizo sentir esto?'}),
            'aprendizaje': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3, 'placeholder': '¿Qué lección o idea extraigo de esto?'}),
        }

    def __init__(self, *args, **kwargs):
        # --- LÓGICA CLAVE PARA FILTRAR LAS PERSONAS ---
        # Extraemos el usuario que se pasa desde la vista
        usuario = kwargs.pop('usuario', None)
        super().__init__(*args, **kwargs)

        self.fields['fecha'].error_messages['invalid'] = 'Introduce una fecha válida.'
        self.fields['personas'].label = 'Personas involucradas'
        self.fields['personas'].help_text = (
            'Elige una o varias personas. Puedes registrar la interacción sin asociarla a nadie.'
        )

        # Si se proporcionó un usuario, filtramos el queryset del campo 'personas'
        # para mostrar solo las personas importantes de ESE usuario.
        if usuario:
            disponibles = PersonaImportante.objects.filter(usuario=usuario, archivada=False)
            if self.instance and self.instance.pk:
                disponibles = PersonaImportante.objects.filter(usuario=usuario).filter(
                    Q(archivada=False) | Q(interaccion=self.instance)
                )
            self.fields['personas'].queryset = disponibles.distinct()


class GestoForm(forms.ModelForm):
    """Formulario para crear/editar Gesto (Phase Hábitos 2.0D)."""

    # El template habito_form.html usa el campo radio 'tipo_habito' con valores
    # 'positivo'/'negativo'; lo mapeamos a Gesto.tipo ('cultivo'/'suelto').
    tipo_habito = forms.ChoiceField(
        choices=[('positivo', 'Gesto que cultivo'), ('negativo', 'Gesto que suelto')],
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_tipo_habito'}),
        label='Tipo de Gesto',
    )

    class Meta:
        model = Gesto
        fields = ['nombre', 'descripcion', 'periodo_observacion_dias', 'color']

        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Leer antes de dormir, Abrir el móvil al levantarme...'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '¿Por qué aparece este gesto en tu día a día?'
            }),
            'periodo_observacion_dias': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '365',
                'value': '30'
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color'
            }),
        }

        labels = {
            'nombre': 'Nombre del Gesto',
            'descripcion': 'Descripción',
            'periodo_observacion_dias': 'Período de observación (días)',
            'color': 'Color',
        }

    _TIPO_HABITO_A_TIPO = {'positivo': 'cultivo', 'negativo': 'suelto'}
    _TIPO_A_TIPO_HABITO = {'cultivo': 'positivo', 'suelto': 'negativo'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['tipo_habito'].initial = self._TIPO_A_TIPO_HABITO.get(self.instance.tipo, 'positivo')

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.tipo = self._TIPO_HABITO_A_TIPO.get(self.cleaned_data['tipo_habito'], 'cultivo')
        if commit:
            instance.save()
        return instance


class CadenciaGestoForm(forms.Form):
    """
    Configura la cadencia de un Gesto tipo='cultivo' (Fase 5B del
    CONTRATO_ANALIZADOR_GESTOS.md). No es un ModelForm porque las
    invariantes válidas dependen de qué campos aplican a cada
    tipo_cadencia — se reutiliza literalmente
    Gesto._validar_invariantes_cadencia() en clean() en vez de
    duplicar las reglas aquí, para que formulario y modelo nunca
    puedan divergir.
    """
    tipo_cadencia = forms.ChoiceField(
        choices=Gesto.TIPO_CADENCIA_CHOICES,
        widget=forms.RadioSelect(attrs={'id': 'id_tipo_cadencia'}),
        label='Cadencia',
    )
    frecuencia_semanal_objetivo = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '7'}),
        label='Veces por semana',
    )
    dias_semana_objetivo = forms.MultipleChoiceField(
        required=False,
        choices=[(dia, dia.capitalize()) for dia in Gesto.DIAS_SEMANA_VALIDOS],
        widget=forms.CheckboxSelectMultiple,
        label='Días concretos',
    )

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned

        temporal = Gesto(
            tipo_cadencia=cleaned.get('tipo_cadencia'),
            frecuencia_semanal_objetivo=cleaned.get('frecuencia_semanal_objetivo'),
            dias_semana_objetivo=cleaned.get('dias_semana_objetivo') or [],
        )
        try:
            temporal._validar_invariantes_cadencia()
        except ValidationError as error:
            for campo, mensajes in error.message_dict.items():
                for mensaje in mensajes:
                    self.add_error(campo if campo in self.fields else None, mensaje)
        return cleaned


class TriggerHabitoForm(forms.ModelForm):
    """Formulario para registrar triggers/recaídas de hábitos negativos"""
    
    class Meta:
        model = TriggerHabito
        fields = [
            'fecha', 'hora', 'emocion_previa', 'situacion', 
            'personas_presentes', 'intensidad_deseo', 'cediste',
            'estrategia_usada', 'aprendizaje'
        ]
        
        widgets = {
            'fecha': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'hora': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'emocion_previa': forms.Select(attrs={
                'class': 'form-select'
            }),
            'situacion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '¿Qué estaba pasando? ¿Dónde estabas?'
            }),
            'personas_presentes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': '¿Estabas solo o acompañado? ¿Con quién?'
            }),
            'intensidad_deseo': forms.Select(attrs={
                'class': 'form-select'
            }),
            'cediste': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'estrategia_usada': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '¿Qué hiciste para resistir? (si resististe)'
            }),
            'aprendizaje': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '¿Qué aprendiste de esta experiencia?'
            })
        }
        
        labels = {
            'fecha': 'Fecha del impulso',
            'hora': 'Hora del impulso',
            'emocion_previa': 'Emoción que sentías',
            'situacion': 'Situación',
            'personas_presentes': 'Personas presentes',
            'intensidad_deseo': 'Intensidad del deseo (1-10)',
            'cediste': '¿Cediste al impulso?',
            'estrategia_usada': 'Estrategia usada',
            'aprendizaje': 'Aprendizaje'
        }
