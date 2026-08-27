from django import forms

from clientes.models import Cliente


class BloqueGymColaborativoForm(forms.Form):
    DURACIONES = ((4, "4 semanas"), (6, "6 semanas"), (8, "8 semanas"), (12, "12 semanas"))
    SECUNDARIOS = (
        ("gemelos", "Gemelos"),
        ("hombros", "Hombros"),
        ("brazos", "Brazos"),
        ("espalda", "Espalda"),
        ("pecho", "Pecho"),
        ("gluteos", "Glúteos"),
        ("cuadriceps", "Cuádriceps"),
    )
    POST_ALLOWLIST = frozenset({
        "csrfmiddlewaretoken", "semana_inicio", "semanas_previstas",
        "objetivo_principal", "objetivos_secundarios", "motivo", "version",
    })

    semana_inicio = forms.DateField(
        label="Comienza el lunes", widget=forms.DateInput(attrs={"type": "date"}),
    )
    semanas_previstas = forms.TypedChoiceField(
        label="Duración", choices=DURACIONES, coerce=int,
    )
    objetivo_principal = forms.ChoiceField(
        label="Objetivo general", choices=Cliente.OBJETIVO_CHOICES,
    )
    objetivos_secundarios = forms.MultipleChoiceField(
        label="Énfasis secundarios", choices=SECUNDARIOS, required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    motivo = forms.CharField(
        label="Por qué quieres este bloque", required=False, max_length=300,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def clean(self):
        cleaned = super().clean()
        inesperados = sorted(set(self.data.keys()) - self.POST_ALLOWLIST)
        if inesperados:
            raise forms.ValidationError(
                "La solicitud incluye campos que no se pueden modificar desde el Centro."
            )
        inicio = cleaned.get("semana_inicio")
        if inicio and inicio.weekday() != 0:
            self.add_error("semana_inicio", "La semana debe comenzar en lunes.")
        secundarios = cleaned.get("objetivos_secundarios") or []
        if len(secundarios) > 2:
            self.add_error(
                "objetivos_secundarios", "Elige como máximo dos énfasis secundarios."
            )
        return cleaned
