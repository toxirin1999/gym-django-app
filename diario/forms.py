# diario/forms.py

from django import forms
from django.core.exceptions import ValidationError
from .models import PersonaImportante, Interaccion, ProsocheHabito, TriggerHabito, Gesto


class PersonaImportanteForm(forms.ModelForm):
    class Meta:
        model = PersonaImportante
        fields = ['nombre', 'tipo_relacion', 'salud_relacion', 'notas']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Marco Aurelio'}),
            'tipo_relacion': forms.Select(attrs={'class': 'form-select'}),
            'salud_relacion': forms.NumberInput(
                attrs={'class': 'form-control', 'type': 'range', 'min': '1', 'max': '5'}),
            'notas': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3, 'placeholder': '¿Qué representa esta persona para ti?'}),
        }
        labels = {
            'nombre': 'Nombre de la Persona',
            'tipo_relacion': 'Tipo de Relación',
            'salud_relacion': 'Salud de la Relación (1=Mala, 5=Excelente)',
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
            'personas': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '5'}),
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

        # Si se proporcionó un usuario, filtramos el queryset del campo 'personas'
        # para mostrar solo las personas importantes de ESE usuario.
        if usuario:
            self.fields['personas'].queryset = PersonaImportante.objects.filter(usuario=usuario)


class ProsocheHabitoForm(forms.ModelForm):
    """Formulario para crear/editar hábitos con soporte para hábitos positivos y negativos"""
    
    class Meta:
        model = ProsocheHabito
        fields = ['nombre', 'descripcion', 'tipo_habito', 'objetivo_dias', 'fecha_objetivo', 'color']
        
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Hacer ejercicio, Fumar, Leer...'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '¿Por qué es importante este hábito para ti?'
            }),
            'tipo_habito': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_tipo_habito'
            }),
            'objetivo_dias': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '365',
                'value': '30'
            }),
            'fecha_objetivo': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color'
            })
        }
        
        labels = {
            'nombre': 'Nombre del Hábito',
            'descripcion': 'Descripción',
            'tipo_habito': 'Tipo de Hábito',
            'objetivo_dias': 'Días Objetivo',
            'fecha_objetivo': 'Fecha Objetivo (Opcional)',
            'color': 'Color'
        }
        
        help_texts = {
            'tipo_habito': '¿Es un hábito que quieres formar o eliminar?',
            'objetivo_dias': 'Número de días para establecer/eliminar el hábito (recomendado: 21-90 días)',
            'fecha_objetivo': 'Fecha en la que quieres completar el desafío'
        }


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
