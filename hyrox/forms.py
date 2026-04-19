from django import forms
from .models import HyroxObjective, HyroxSession

class HyroxObjectiveForm(forms.ModelForm):
    class Meta:
        model = HyroxObjective
        fields = ['categoria', 'fecha_evento', 'rm_peso_muerto', 'rm_sentadilla', 'tiempo_5k_base', 'material_disponible', 'nivel_experiencia', 'lesiones_previas', 'dias_preferidos']
        widgets = {
            'fecha_evento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control bg-slate-800 border-slate-700 text-slate-200'}),
            'categoria': forms.Select(attrs={'class': 'form-select bg-slate-800 border-slate-700 text-slate-200'}),
            'rm_peso_muerto': forms.NumberInput(attrs={'class': 'form-control bg-slate-800 border-slate-700 text-slate-200', 'placeholder': 'Ej. 120 (Si no sabes, déjalo en blanco)'}),
            'rm_sentadilla': forms.NumberInput(attrs={'class': 'form-control bg-slate-800 border-slate-700 text-slate-200', 'placeholder': 'Ej. 100 (Si no sabes, déjalo en blanco)'}),
            'tiempo_5k_base': forms.TextInput(attrs={'class': 'form-control bg-slate-800 border-slate-700 text-slate-200', 'placeholder': 'Ej. 25:00'}),
            'nivel_experiencia': forms.Select(attrs={'class': 'form-select bg-slate-800 border-slate-700 text-slate-200'}),
            'lesiones_previas': forms.Textarea(attrs={'class': 'form-control bg-slate-800 border-slate-700 text-slate-200', 'rows': 2, 'placeholder': 'Ej: Molestias en hombro derecho...'}),
            'material_disponible': forms.Textarea(attrs={'class': 'form-control bg-slate-800 border-slate-700 text-slate-200', 'rows': 3, 'placeholder': '¿Tienes acceso a Sled, SkiErg, Row? Escríbelo aquí...'}),
            'dias_preferidos': forms.TextInput(attrs={'class': 'form-control bg-slate-800 border-slate-700 text-slate-200 font-mono text-sm', 'placeholder': 'Ej: 0,2,4,5 (Lunes, Mierc, Viern, Sab)'}),
        }

class HyroxSessionNotesForm(forms.ModelForm):
    sustituir_material = forms.BooleanField(
        required=False,
        label="No tengo material oficial, busca equivalencia",
        widget=forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-purple-600 bg-slate-800 border-slate-700 rounded focus:ring-purple-500'})
    )
    
    class Meta:
        model = HyroxSession
        fields = ['nivel_energia_pre', 'titulo', 'tiempo_total_minutos', 'hr_media', 'hr_maxima', 'rpe_global', 'notas_raw']
        widgets = {
            'nivel_energia_pre': forms.NumberInput(attrs={'type': 'range', 'class': 'w-full accent-yellow-500 mt-2', 'min': 1, 'max': 10, 'value': 7, 'oninput': 'document.getElementById("energia-val").innerText = this.value'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control bg-slate-800 border-slate-700 text-slate-200', 'placeholder': 'Ej. Simulación Hyrox Mitad'}),
            'tiempo_total_minutos': forms.NumberInput(attrs={'class': 'form-control bg-slate-800 border-slate-700 text-slate-200', 'placeholder': 'Ej. 45'}),
            'hr_media': forms.NumberInput(attrs={'class': 'form-control bg-slate-800 border-slate-700 text-slate-200', 'placeholder': 'Ej. 155'}),
            'hr_maxima': forms.NumberInput(attrs={'class': 'form-control bg-slate-800 border-slate-700 text-slate-200', 'placeholder': 'Ej. 185'}),
            'rpe_global': forms.NumberInput(attrs={'type': 'range', 'class': 'w-full accent-pink-500 mt-2', 'min': 1, 'max': 10, 'value': 5, 'oninput': 'document.getElementById("rpe-val").innerText = this.value'}),
            'notas_raw': forms.Textarea(attrs={'class': 'form-control bg-slate-800 border-slate-700 text-slate-200', 'rows': 8, 'placeholder': 'Pega el texto de tu entrenamiento...\nEj: Carrera 5km ritmo 4:30.\nWallballs 4 series de 20.'}),
            'hubo_molestias': forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-red-600 bg-slate-800 border-slate-700 rounded focus:ring-red-500 ml-2'}),
        }

from .models import UserInjury, DailyRecoveryEntry

class UserInjuryForm(forms.ModelForm):
    ZONAS_CHOICES = [
        ('', '--- Selecciona la zona ---'),
        ('Tren Inferior', (
            ('rodilla', 'Rodilla'),
            ('gemelo', 'Gemelo / Sóleo'),
            ('tobillo', 'Tobillo'),
            ('isquiotibial', 'Isquiotibial'),
            ('cuadriceps', 'Cuádriceps'),
            ('cadera', 'Cadera / Glúteo'),
            ('pie', 'Pie / Fascia'),
        )),
        ('Tren Superior', (
            ('hombro', 'Hombro / Manguito'),
            ('codo', 'Codo'),
            ('muneca', 'Muñeca / Mano'),
            ('pectoral', 'Pectoral'),
            ('dorsal', 'Dorsal / Escápula'),
        )),
        ('Core y Columna', (
            ('lumbar', 'Espalda Baja (Lumbar)'),
            ('cervical', 'Cabello / Cervical'),
            ('abdomen', 'Abdomen / Psoas'),
        ))
    ]

    TAGS_CHOICES = [
        # Tren Inferior
        ('impacto_vertical', 'Evitar Impacto (Piernas)'),
        ('flexion_rodilla_profunda', 'Evitar Flexión Rodilla Profunda'),
        ('empuje_pierna', 'Evitar Empuje Pesado (Sled Push)'),
        ('flexion_plantar', 'Evitar Flexión Plantar (Saltos/Correr)'),
        ('carga_distal_pierna', 'Evitar Carga Distal (Prensa/Hack Squat)'),
        ('estabilidad_gemelo', 'Evitar Estabilidad de Gemelo'),
        # Tren Superior
        ('empuje_hombro', 'Evitar Empuje Hombro (Press, Burpees)'),
        ('traccion_superior', 'Evitar Tracción (Dominadas, Remo)'),
        ('empuje_horizontal', 'Evitar Empuje Horizontal (Flexiones)'),
        # Core
        ('lumbar_carga', 'Evitar Carga Lumbar Pesada (Peso Muerto)'),
        ('rotacion_tronco', 'Evitar Rotación de Tronco'),
    ]
    
    zona_afectada = forms.ChoiceField(
        choices=ZONAS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select bg-slate-800 border-slate-700 text-slate-200', 'id': 'id_zona_afectada'})
    )
    
    tags_seleccionados = forms.MultipleChoiceField(
        choices=TAGS_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'text-red-500 bg-slate-800 border-slate-700 tag-checkbox'}),
        label="Movimientos a Evitar (El sistema los sustituirá por ti)",
        required=False
    )
    
    class Meta:
        model = UserInjury
        fields = ['zona_afectada', 'fase', 'fecha_inicio', 'gravedad']
        widgets = {
            'fase': forms.Select(attrs={'class': 'form-select bg-slate-800 border-slate-700 text-slate-200'}),
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control bg-slate-800 border-slate-700 text-slate-200'}),
            'gravedad': forms.NumberInput(attrs={'type': 'range', 'class': 'w-full accent-red-500 mt-2', 'min': 1, 'max': 10, 'value': 5, 'oninput': 'document.getElementById("gravedad-val").innerText = this.value'}),
        }

class DailyRecoveryEntryForm(forms.ModelForm):
    class Meta:
        model = DailyRecoveryEntry
        fields = ['dolor_reposo', 'dolor_movimiento', 'inflamacion_percibida', 'rango_movimiento']
        widgets = {
            'dolor_reposo': forms.NumberInput(attrs={'type': 'range', 'class': 'w-full accent-yellow-500 mt-2', 'min': 0, 'max': 10, 'value': 0, 'oninput': 'document.getElementById("dolor-reposo-val").innerText = this.value'}),
            'dolor_movimiento': forms.NumberInput(attrs={'type': 'range', 'class': 'w-full accent-red-500 mt-2', 'min': 0, 'max': 10, 'value': 2, 'oninput': 'document.getElementById("dolor-movimiento-val").innerText = this.value'}),
            'inflamacion_percibida': forms.NumberInput(attrs={'type': 'range', 'class': 'w-full accent-orange-500 mt-2', 'min': 1, 'max': 10, 'value': 2, 'oninput': 'document.getElementById("inflamacion-val").innerText = this.value'}),
            'rango_movimiento': forms.NumberInput(attrs={'type': 'range', 'class': 'w-full accent-green-500 mt-2', 'min': 1, 'max': 10, 'value': 8, 'oninput': 'document.getElementById("rango-val").innerText = this.value'}),
        }

from .models import RecoveryTestLog

# Phase 12: Recovery Test Form
class RecoveryTestForm(forms.ModelForm):
    class Meta:
        model = RecoveryTestLog
        fields = ['dolor_movimiento', 'inflamacion_percibida', 'confianza_atleta']
        widgets = {
            'dolor_movimiento': forms.NumberInput(attrs={'type': 'range', 'class': 'w-full accent-red-500 mt-2', 'min': 0, 'max': 10, 'value': 5, 'oninput': 'document.getElementById("dolor-val").innerText = this.value'}),
            'inflamacion_percibida': forms.NumberInput(attrs={'type': 'range', 'class': 'w-full accent-orange-500 mt-2', 'min': 0, 'max': 10, 'value': 5, 'oninput': 'document.getElementById("inflamacion-val").innerText = this.value'}),
            'confianza_atleta': forms.NumberInput(attrs={'type': 'range', 'class': 'w-full accent-green-500 mt-2', 'min': 0, 'max': 10, 'value': 5, 'oninput': 'document.getElementById("confianza-val").innerText = this.value'}),
        }
