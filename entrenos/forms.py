# Archivo: entrenos/forms.py - VERSIÓN COMPLETA CON COMPATIBILIDAD

from django import forms
from django.utils import timezone
from django.forms import formset_factory
from .models import EntrenoRealizado, EjercicioLiftinDetallado, DatosLiftinDetallados, DetalleEjercicioRealizado, \
    SerieRealizada
from clientes.models import Cliente
from rutinas.models import Rutina, EjercicioBase
import re
from decimal import Decimal


class EjercicioForm(forms.ModelForm):
    class Meta:
        model = EjercicioBase
        fields = ['nombre', 'grupo_muscular', 'equipo']


# ============================================================================
# FORMULARIOS ORIGINALES (Para compatibilidad con código existente)
# ============================================================================

class SeleccionClienteForm(forms.Form):
    """
    Formulario original para selección de cliente
    """
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Selecciona un cliente"
    )


class DetalleEjercicioForm(forms.ModelForm):
    """
    Formulario original para detalles de ejercicio
    """

    class Meta:
        model = DetalleEjercicioRealizado
        fields = ['ejercicio', 'series', 'repeticiones', 'peso_kg', 'completado']
        widgets = {
            'ejercicio': forms.Select(attrs={'class': 'form-control'}),
            'series': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'repeticiones': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'peso_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'completado': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }


class FiltroClienteForm(forms.Form):
    """
    Formulario original para filtrar por cliente
    """
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        required=False,
        empty_label="Todos los clientes",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )


# ============================================================================
# FORMULARIOS NUEVOS PARA LIFTIN
# ============================================================================

class ImportarLiftinCompletoForm(forms.ModelForm):
    """
    Formulario completo para importar TODOS los datos de Liftin
    basado en la pantalla que me enviaste
    """

    # Campos adicionales para facilitar la entrada de datos
    fecha_entrenamiento = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        initial=timezone.now().date(),
        help_text="Fecha en que realizaste el entrenamiento"
    )

    # Campos de tiempo detallados
    hora_inicio_str = forms.CharField(
        max_length=5,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '09:43',
            'pattern': '[0-9]{2}:[0-9]{2}'
        }),
        help_text="Hora de inicio (formato: HH:MM)"
    )

    hora_fin_str = forms.CharField(
        max_length=5,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '10:46',
            'pattern': '[0-9]{2}:[0-9]{2}'
        }),
        help_text="Hora de finalización (formato: HH:MM)"
    )

    # Volumen total como aparece en Liftin
    volumen_total_str = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '19K KG'
        }),
        help_text="Volumen como aparece en Liftin (ej: 19K KG)"
    )

    class Meta:
        model = EntrenoRealizado
        fields = [
            'cliente',
            'nombre_rutina_liftin',
            'numero_ejercicios',
            'tiempo_total_formateado',
            'calorias_quemadas',
            'frecuencia_cardiaca_promedio',
            'frecuencia_cardiaca_maxima',
            'notas_liftin'
        ]

        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-control'}),
            'nombre_rutina_liftin': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Día 6 - Full Body'
            }),
            'numero_ejercicios': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '8',
                'min': 1,
                'max': 50
            }),
            'tiempo_total_formateado': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '1:02:23'
            }),
            'calorias_quemadas': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 350',
                'min': 1,
                'max': 2000
            }),
            'frecuencia_cardiaca_promedio': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 135',
                'min': 60,
                'max': 220
            }),
            'frecuencia_cardiaca_maxima': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 165',
                'min': 80,
                'max': 220
            }),
            'notas_liftin': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Notas adicionales del entrenamiento...'
            })
        }

        help_texts = {
            'nombre_rutina_liftin': 'Nombre de la rutina como aparece en Liftin',
            'numero_ejercicios': 'Número total de ejercicios realizados',
            'tiempo_total_formateado': 'Tiempo total como aparece en Liftin (ej: 1:02:23)',
            'calorias_quemadas': 'Calorías quemadas según Liftin',
            'frecuencia_cardiaca_promedio': 'Frecuencia cardíaca promedio en BPM',
            'frecuencia_cardiaca_maxima': 'Frecuencia cardíaca máxima alcanzada en BPM',
            'notas_liftin': 'Cualquier nota adicional sobre el entrenamiento'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Personalizar el queryset de clientes
        self.fields['cliente'].queryset = Cliente.objects.all().order_by('nombre')

        # Hacer algunos campos obligatorios para Liftin
        self.fields['cliente'].required = True
        self.fields['nombre_rutina_liftin'].required = True

        # Agregar clases CSS adicionales
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'

    def clean_hora_inicio_str(self):
        hora_str = self.cleaned_data.get('hora_inicio_str')
        if hora_str:
            try:
                from datetime import datetime
                hora = datetime.strptime(hora_str, '%H:%M').time()
                return hora
            except ValueError:
                raise forms.ValidationError("Formato de hora inválido. Use HH:MM")
        return None

    def clean_hora_fin_str(self):
        hora_str = self.cleaned_data.get('hora_fin_str')
        if hora_str:
            try:
                from datetime import datetime
                hora = datetime.strptime(hora_str, '%H:%M').time()
                return hora
            except ValueError:
                raise forms.ValidationError("Formato de hora inválido. Use HH:MM")
        return None

    def clean_volumen_total_str(self):
        volumen_str = self.cleaned_data.get('volumen_total_str')
        if volumen_str:
            # Extraer número del formato "19K KG" o "1500 KG"
            import re
            match = re.search(r'(\d+(?:\.\d+)?)\s*([KM]?)\s*KG', volumen_str.upper())
            if match:
                numero = float(match.group(1))
                unidad = match.group(2)

                if unidad == 'K':
                    numero *= 1000
                elif unidad == 'M':
                    numero *= 1000000

                return Decimal(str(numero))
            else:
                raise forms.ValidationError("Formato de volumen inválido. Use formato como '19K KG' o '1500 KG'")
        return None

    def clean_tiempo_total_formateado(self):
        tiempo_str = self.cleaned_data.get('tiempo_total_formateado')
        if tiempo_str:
            # Validar formato H:MM:SS
            import re
            if not re.match(r'^\d{1,2}:\d{2}:\d{2}$', tiempo_str):
                raise forms.ValidationError("Formato de tiempo inválido. Use H:MM:SS (ej: 1:02:23)")
        return tiempo_str

    def clean(self):
        cleaned_data = super().clean()

        # Validaciones cruzadas
        hora_inicio = cleaned_data.get('hora_inicio_str')
        hora_fin = cleaned_data.get('hora_fin_str')
        fc_promedio = cleaned_data.get('frecuencia_cardiaca_promedio')
        fc_maxima = cleaned_data.get('frecuencia_cardiaca_maxima')

        # Validar horarios
        if hora_inicio and hora_fin:
            if hora_inicio >= hora_fin:
                raise forms.ValidationError(
                    "La hora de fin debe ser posterior a la hora de inicio."
                )

        # Validar frecuencias cardíacas
        if fc_promedio and fc_maxima:
            if fc_promedio >= fc_maxima:
                raise forms.ValidationError(
                    "La frecuencia cardíaca máxima debe ser mayor que la promedio."
                )

        return cleaned_data

    def save(self, commit=True):
        # Crear el entrenamiento sin guardar aún
        entreno = super().save(commit=False)

        # Configurar campos específicos de Liftin
        entreno.fuente_datos = 'liftin'
        entreno.fecha = self.cleaned_data['fecha_entrenamiento']
        entreno.fecha_importacion = timezone.now()

        # Configurar horarios
        entreno.hora_inicio = self.cleaned_data.get('hora_inicio_str')
        entreno.hora_fin = self.cleaned_data.get('hora_fin_str')

        # Configurar volumen
        volumen_kg = self.cleaned_data.get('volumen_total_str')
        if volumen_kg:
            entreno.volumen_total_kg = volumen_kg
            entreno.volumen_total_formateado = self.cleaned_data.get('volumen_total_str')

        # Calcular duración en minutos si tenemos horarios
        if entreno.hora_inicio and entreno.hora_fin:
            from datetime import datetime
            inicio = datetime.combine(entreno.fecha, entreno.hora_inicio)
            fin = datetime.combine(entreno.fecha, entreno.hora_fin)
            duracion = fin - inicio
            entreno.duracion_minutos = int(duracion.total_seconds() / 60)

        # Generar un ID único para Liftin
        import uuid
        entreno.liftin_workout_id = f"manual_{uuid.uuid4().hex[:8]}"

        # ❌ NO crear ni asignar rutina aquí. Se hará desde la vista.
        return entreno


class EjercicioLiftinForm(forms.ModelForm):
    """
    Formulario para agregar ejercicios individuales de Liftin
    """

    # Campo para peso con formato flexible
    peso_formateado_input = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: 268.5 kg, PC, 90-100 kg'
        }),
        help_text="Peso como aparece en Liftin"
    )

    # Campo para repeticiones con formato flexible
    repeticiones_input = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: 3x5-10, 3x10-12'
        }),
        help_text="Series y repeticiones como aparecen en Liftin"
    )

    class Meta:
        model = EjercicioLiftinDetallado
        fields = [
            'nombre_ejercicio',
            'orden_ejercicio',
            'estado_liftin',
            'notas_ejercicio'
        ]

        widgets = {
            'nombre_ejercicio': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Prensa, Curl Femoral Tumbado'
            }),
            'orden_ejercicio': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 50,
                'value': 1
            }),
            'estado_liftin': forms.Select(attrs={'class': 'form-control'}),
            'notas_ejercicio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Notas específicas de este ejercicio...'
            })
        }

    def clean_peso_formateado_input(self):
        peso_str = self.cleaned_data.get('peso_formateado_input')
        if peso_str:
            # Extraer peso numérico si es posible
            import re

            # Casos especiales
            if peso_str.upper() in ['PC', 'PESO CORPORAL', 'BODYWEIGHT']:
                return None  # Peso corporal

            # Buscar números en el string
            numeros = re.findall(r'\d+(?:\.\d+)?', peso_str)
            if numeros:
                # Si hay un rango (ej: 90-100), tomar el promedio
                if len(numeros) >= 2:
                    peso_promedio = (float(numeros[0]) + float(numeros[-1])) / 2
                    return Decimal(str(peso_promedio))
                else:
                    return Decimal(numeros[0])
        return None

    def clean_repeticiones_input(self):
        reps_str = self.cleaned_data.get('repeticiones_input')
        if reps_str:
            # Extraer series y repeticiones del formato "3x5-10"
            import re
            match = re.match(r'(\d+)x(\d+)(?:-(\d+))?', reps_str)
            if match:
                series = int(match.group(1))
                reps_min = int(match.group(2))
                reps_max = int(match.group(3)) if match.group(3) else reps_min

                return {
                    'series': series,
                    'reps_min': reps_min,
                    'reps_max': reps_max
                }
            else:
                raise forms.ValidationError("Formato de repeticiones inválido. Use formato como '3x5-10' o '3x12'")
        return None

    def save(self, commit=True):
        ejercicio = super().save(commit=False)

        # Configurar peso
        peso_kg = self.cleaned_data.get('peso_formateado_input')
        if peso_kg:
            ejercicio.peso_kg = peso_kg
        ejercicio.peso_formateado = self.cleaned_data.get('peso_formateado_input')

        # Configurar repeticiones
        reps_data = self.cleaned_data.get('repeticiones_input')
        if reps_data:
            ejercicio.series_realizadas = reps_data['series']
            ejercicio.repeticiones_min = reps_data['reps_min']
            ejercicio.repeticiones_max = reps_data['reps_max']
            ejercicio.repeticiones_formateado = self.cleaned_data.get('repeticiones_input')

        if commit:
            ejercicio.save()

        return ejercicio


# Formset para múltiples ejercicios
EjercicioLiftinFormSet = formset_factory(
    EjercicioLiftinForm,
    extra=8,  # Por defecto 8 ejercicios como en la imagen
    can_delete=True
)


class BuscarEntrenamientosLiftinForm(forms.Form):
    """
    Formulario mejorado para buscar entrenamientos con filtros específicos de Liftin
    """

    FUENTE_CHOICES = [
        ('', 'Todas las fuentes'),
        ('manual', 'Solo manuales'),
        ('liftin', 'Solo de Liftin'),
    ]

    VOLUMEN_CHOICES = [
        ('', 'Cualquier volumen'),
        ('bajo', 'Menos de 10K KG'),
        ('medio', '10K - 20K KG'),
        ('alto', 'Más de 20K KG'),
    ]

    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        required=False,
        empty_label="Todos los clientes",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    fuente_datos = forms.ChoiceField(
        choices=FUENTE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    volumen_rango = forms.ChoiceField(
        choices=VOLUMEN_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    numero_ejercicios_min = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mín. ejercicios',
            'min': 1
        })
    )

    numero_ejercicios_max = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Máx. ejercicios',
            'min': 1
        })
    )

    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        fecha_desde = cleaned_data.get('fecha_desde')
        fecha_hasta = cleaned_data.get('fecha_hasta')
        ejercicios_min = cleaned_data.get('numero_ejercicios_min')
        ejercicios_max = cleaned_data.get('numero_ejercicios_max')

        if fecha_desde and fecha_hasta:
            if fecha_desde > fecha_hasta:
                raise forms.ValidationError(
                    "La fecha 'desde' no puede ser posterior a la fecha 'hasta'."
                )

        if ejercicios_min and ejercicios_max:
            if ejercicios_min > ejercicios_max:
                raise forms.ValidationError(
                    "El número mínimo de ejercicios no puede ser mayor que el máximo."
                )

        return cleaned_data


# ============================================================================
# FORMULARIOS ADICIONALES PARA COMPATIBILIDAD
# ============================================================================

class ImportarLiftinBasicoForm(forms.ModelForm):
    """
    Formulario básico para importar datos de Liftin (versión simplificada)
    """

    class Meta:
        model = EntrenoRealizado
        fields = [
            'cliente',
            'rutina',
            'duracion_minutos',
            'calorias_quemadas',
            'frecuencia_cardiaca_promedio',
            'notas_liftin'
        ]

        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-control'}),
            'rutina': forms.Select(attrs={'class': 'form-control'}),
            'duracion_minutos': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Duración en minutos',
                'min': 1
            }),
            'calorias_quemadas': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Calorías quemadas',
                'min': 1
            }),
            'frecuencia_cardiaca_promedio': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'FC promedio (BPM)',
                'min': 60,
                'max': 220
            }),
            'notas_liftin': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Notas del entrenamiento...'
            })
        }

    def save(self, commit=True):
        entreno = super().save(commit=False)
        entreno.fuente_datos = 'liftin'
        entreno.fecha_importacion = timezone.now()

        # Generar ID único
        import uuid
        entreno.liftin_workout_id = f"basico_{uuid.uuid4().hex[:8]}"

        if commit:
            entreno.save()

        return entreno


class ExportarDatosForm(forms.Form):
    """
    Formulario para exportar datos de entrenamientos
    """

    FORMATO_CHOICES = [
        ('csv', 'CSV (Excel)'),
        ('json', 'JSON'),
        ('pdf', 'PDF'),
    ]

    formato = forms.ChoiceField(
        choices=FORMATO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    incluir_liftin = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    incluir_manual = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

# forms.py
