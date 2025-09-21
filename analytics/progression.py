import pandas as pd
from sklearn.linear_model import LinearRegression
from datetime import datetime


class ProgressionAnalyzer:
    """
    Analiza la progresión de un ejercicio para un cliente
    """

    def __init__(self, cliente):
        self.cliente = cliente

    def analizar_progresion_ejercicio(self, nombre_ejercicio, periodo_dias=90):
        from .views import CalculadoraEjerciciosTabla
        from django.utils import timezone

        fecha_fin = timezone.now().date()
        fecha_inicio = fecha_fin - pd.Timedelta(days=periodo_dias)

        calculadora = CalculadoraEjerciciosTabla(self.cliente)
        ejercicios = calculadora.obtener_ejercicios_tabla(fecha_inicio, fecha_fin)

        datos = []
        for e in ejercicios:
            if e['nombre'].strip().lower() == nombre_ejercicio.strip().lower():
                try:
                    peso = float(e.get('peso', 0)) if e.get('peso') != 'PC' else 0
                    if peso > 0:
                        datos.append({'fecha': e['fecha'], 'peso': peso})
                except (ValueError, TypeError):
                    continue

        if len(datos) < 3:
            return None

        df = pd.DataFrame(datos)
        df['fecha_num'] = pd.to_datetime(df['fecha']).astype(int) / 10 ** 9  # timestamp

        X = df[['fecha_num']]
        y = df['peso']
        modelo = LinearRegression().fit(X, y)

        pendiente = modelo.coef_[0]
        r2 = modelo.score(X, y)

        return {
            'tendencia': {
                'pendiente': round(pendiente * 100000, 2),  # escalar
                'confianza': round(r2, 3)
            }
        }
