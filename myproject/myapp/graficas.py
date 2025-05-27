from django.db.models import Count, OuterRef
from django.db.models.functions import ExtractYear, Coalesce
from django.db.models import (
    Case, Value, When, DurationField, BooleanField, ExpressionWrapper, CharField,
    IntegerField, DecimalField, Sum, Avg, Max, Min, Q, Count, F, FloatField, Subquery
)
from django.db.models.functions import Now, TruncMonth, ExtractYear, ExtractMonth
from django.http import JsonResponse
from datetime import datetime, timezone
import plotly.express as px
from dateutil.relativedelta import relativedelta
from plotly.offline import plot
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import time
# <--- Esto está bien, le diste un alias
from django.utils import timezone as django_timezone
import logging
import collections
from django.core.cache import cache
# Importaciones locales
from myapp.models import (
    ContratoIndividual, AfiliadoIndividual, Reclamacion, Pago,
    ContratoColectivo, Intermediario, Tarifa, Factura
)
from myapp.forms import *


logger = logging.getLogger(__name__)

# Paleta de colores consistente
COLOR_PALETTE = {
    'primary': '#2C3E50',  # Azul oscuro
    'secondary': '#E74C3C',  # Rojo
    'success': '#27AE60',  # Verde
    'warning': '#F39C12',  # Naranja
    'info': '#3498DB',  # Azul claro
    'light': '#ECF0F1',  # Gris claro
    'dark': '#34495E',  # Gris oscuro
}

# Configuración de diseño base para todas las gráficas
BASE_LAYOUT = {
    'paper_bgcolor': 'rgba(255, 255, 255, 0.85)',  # Fondo del papel
    'plot_bgcolor': 'rgba(255, 255, 255, 0.85)',  # Fondo del gráfico
    'font': {'family': 'Arial, sans-serif'},  # Fuente
    'margin': {'t': 50, 'l': 50, 'r': 50, 'b': 50},  # Márgenes
}

# Configuración adicional para las gráficas
GRAPH_CONFIG = {
    'displayModeBar': True,  # Mostrar la barra de herramientas
    'responsive': True,  # Asegurar que el gráfico sea responsivo
    'displaylogo': False,  # Ocultar el logotipo de Plotly
    'autosizable': True,  # Permitir redimensionado externo
    # Quitar botones innecesarios
    'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
}

# =====================#
# SISTEMA DE CACHÉ     #
# =====================#
# Configuración de caché para diferentes tipos de gráficas
GRAPH_CACHE_CONFIG = {
    # Gráficas que cambian con frecuencia
    'dynamic': {
        'timeout': 1800,  # 30 minutos
        'graphs': [4, 5, 7, 9, 11, 29, 31, 39, 40]


    },
    # Gráficas que cambian con moderada frecuencia
    'moderate': {
        'timeout': 3600,  # 1 hora
        'graphs': [1, 2, 3, 6, 8, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 30, 32, 33, 34, 35, 36, 37, 38, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52]
    },
    # Valor predeterminado
    'default': {
        'timeout': 3600  # 1 hora
    }
}


def obtener_configuracion_graficas(request):
    """
    Devuelve la configuración base para las gráficas.

    Args:
        request: Objeto HttpRequest.

    Returns:
        JsonResponse: Configuración base para las gráficas en formato JSON.
    """
    config = {
        "glassConfig": BASE_LAYOUT.copy(),
        "colors": COLOR_PALETTE.copy(),
    }
    return JsonResponse(config)


def generar_figura_sin_datos(mensaje="No hay datos disponibles"):
    fig = go.Figure()
    fig.add_annotation(
        text=mensaje,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font={"size": 20, "color": COLOR_PALETTE['secondary']}
    )
    fig.update_layout(**BASE_LAYOUT)
    return fig


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def validate_graph_html(html_content):
    """Valida la estructura básica del HTML de la gráfica"""
    required_elements = [
        'plotly-graph-div',  # Contenedor principal
        'js-plotly-plot'     # Elemento de Plotly
    ]
    return all(element in html_content for element in required_elements)


def wrap_error_content(error_msg):
    """Envuelve los errores en un contenedor de gráfica válido"""
    return (
        f'<div class="plotly-graph-div" style="height:500px; width:100%;">'
        f'<div class="graph-error alert alert-danger">{error_msg}</div>'
        '</div>'
    )


def get_cached_graph(graph_id, force_refresh=False):
    """
    Versión mejorada con:
    - Validación estructural del HTML
    - Contenedores consistentes en errores
    - Protección contra caché corrupto
    """
    cache_key = f"graph_{graph_id}"

    # Determinar configuración de caché
    config = next(
        (cfg for cfg in GRAPH_CACHE_CONFIG.values()
         if graph_id in cfg.get('graphs', [])),
        GRAPH_CACHE_CONFIG['default']
    )

    # Intento de obtener de caché (con validación)
    if not force_refresh:
        cached_data = cache.get(cache_key)
        if cached_data:
            if validate_graph_html(cached_data.get('html', '')):
                logger.debug(f"Gráfica {graph_id} válida desde caché")
                return {**cached_data, 'from_cache': True}
            logger.warning(
                f"Gráfica {graph_id} en caché no válida, regenerando")

    try:
        start_time = time.time()

        # Obtener y ejecutar función de gráfica
        graph_func = globals().get(f'grafico_{graph_id:02d}')
        if not graph_func:
            raise ValueError(f"Función grafico_{graph_id:02d} no encontrada")

        # Generar contenido y validar estructura
        raw_html = graph_func()
        html_content = (
            raw_html
            if validate_graph_html(raw_html)
            else wrap_error_content("Estructura HTML inválida")
        )

        # Construir resultado
        result = {
            'html': html_content,
            'generated_at': timezone.now(),
            'generation_time': round(time.time() - start_time, 2),
            'from_cache': False,
            'error': None
        }

        # Cachear solo si es válido
        if validate_graph_html(html_content):
            cache.set(cache_key, result, config['timeout'])
            logger.info(f"Gráfica {graph_id} almacenada en caché")
        else:
            logger.error(
                f"Gráfica {graph_id} no cachéable por estructura inválida")

        return result

    except Exception as e:
        error_msg = f"Error en gráfica {graph_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return {
            'html': wrap_error_content(error_msg),
            'generated_at': timezone.now(),
            'generation_time': 0,
            'from_cache': False,
            'error': error_msg
        }


def clear_graph_cache(graph_id=None):
    """
    Limpia el caché de gráficas.

    Args:
        graph_id: ID de la gráfica a limpiar. Si es None, limpia todas.
    """
    if graph_id:
        cache_key = f"graph_{graph_id}"
        cache.delete(cache_key)
        logger.info(f"Caché de gráfica {graph_id} eliminado")
    else:
        # Eliminar todas las gráficas (del 1 al 50)
        for i in range(1, 51):
            cache_key = f"graph_{i}"
            cache.delete(cache_key)
        logger.info("Caché de todas las gráficas eliminado")


# ------------------------------
# Gráfico 01: Distribución de Contratos por Ramo (Pie Chart)
# ------------------------------
def grafico_01():
    """Distribución de Contratos por Ramo (Total Individual + Colectivo)."""
    try:
        data_ind_qs = (ContratoIndividual.objects.values(
            'ramo').annotate(total=Count('id')))
        data_col_qs = (ContratoColectivo.objects.values(
            'ramo').annotate(total=Count('id')))
        df_ind = pd.DataFrame(list(data_ind_qs))
        df_col = pd.DataFrame(list(data_col_qs))

        if not df_ind.empty and not df_col.empty:
            df_total = pd.concat([df_ind, df_col]).groupby(
                'ramo', as_index=False)['total'].sum()
        elif not df_ind.empty:
            df_total = df_ind
        elif not df_col.empty:
            df_total = df_col
        else:
            df_total = pd.DataFrame(columns=['ramo', 'total'])

        if df_total.empty or df_total['total'].sum() == 0:
            return plot(generar_figura_sin_datos("No hay contratos"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        ramo_choices = dict(CommonChoices.RAMO)
        df_total['label'] = df_total['ramo'].apply(
            lambda x: ramo_choices.get(x, x or "N/A"))

        fig = go.Figure(
            data=[go.Pie(
                labels=df_total['label'],
                values=df_total['total'],
                hole=0.35,
                marker_colors=px.colors.qualitative.Pastel,
                textinfo='percent+label',  # Muestra porcentaje y etiqueta en el sector
                hoverinfo='label+value+percent',
                insidetextorientation='radial',
                pull=[0.05 if i == df_total['total'].idxmax()
                      else 0 for i in df_total.index]
            )]
        )

        # --- Configuración del Layout (SIN leyenda) ---
        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Distribución Total de Contratos por Ramo', x=0.5)
        # <-- LÍNEA CLAVE PARA OCULTAR LEYENDA
        layout_grafico['showlegend'] = False
        layout_grafico['margin'] = dict(
            t=50, b=40, l=20, r=20)  # Márgenes ajustados
        fig.update_layout(**layout_grafico)
        # --- FIN Configuración Layout ---

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_01: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos("Error al generar Gráfico 01"), output_type='div', config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 02: Contratos Individuales Vigentes por Mes (Línea) - MODIFICADO
# ------------------------------


def grafico_02():
    """Muestra la cantidad mensual de creación de contratos individuales vigentes (Barras)."""
    try:
        # Obtener datos de contratos vigentes agrupados por mes de creación
        datos = (ContratoIndividual.objects
                 .filter(estatus='VIGENTE')
                 # Agrupar por mes
                 .annotate(mes_creacion=TruncMonth('fecha_creacion'))
                 .values('mes_creacion')
                 .annotate(total=Count('id'))
                 # Asegurar que no haya meses nulos
                 .filter(mes_creacion__isnull=False)
                 .order_by('mes_creacion'))  # Ordenar cronológicamente

        if not datos:  # Verificar si la consulta devolvió algo
            return plot(generar_figura_sin_datos("No hay contratos individuales vigentes"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(list(datos))
        # Asegurar que mes_creacion sea datetime y usarlo para ordenar antes de formatear
        df['mes_creacion'] = pd.to_datetime(df['mes_creacion'])
        df = df.sort_values('mes_creacion')  # Re-ordenar por si acaso
        df['periodo'] = df['mes_creacion'].dt.strftime(
            '%Y-%m')  # Formato YYYY-MM

        if df.empty:  # Doble chequeo por si algo falló en el procesamiento
            return plot(generar_figura_sin_datos("No hay datos válidos para mostrar"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Crear gráfico de barras simple
        fig = px.bar(
            df,
            x='periodo',  # Usar el string formateado para el eje X
            y='total',
            labels={'periodo': 'Mes de Creación',
                    'total': 'N° Contratos Creados (Vigentes)'},
            text='total'  # Mostrar el valor encima de la barra
        )

        fig.update_traces(marker_color=COLOR_PALETTE.get(
            'info'), textposition='outside')  # Color y posición del texto

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Creación Mensual de Contratos Individuales (Vigentes)', x=0.5)
        # Asegurar que el eje X se trate como categoría para mantener el orden del DataFrame
        layout_grafico['xaxis'] = dict(
            title='Mes de Creación', type='category', tickangle=45)
        layout_grafico['yaxis'] = dict(title='Cantidad de Contratos')
        fig.update_layout(**layout_grafico)

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_02: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos("Error al generar Gráfico 02"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 03: Muestra KPIs financieros clave del negocio.
# ------------------------------


def grafico_03():
    """Muestra KPIs financieros clave del negocio."""
    try:
        logger.debug("G03 - Iniciando KPIs Financieros Clave")
        # 1. Prima Emitida Total (Suma de monto_total de contratos activos)
        # Se considera "prima emitida" el valor total de los contratos que están actualmente activos.
        prima_ind_activos = ContratoIndividual.objects.filter(activo=True).aggregate(
            total=Coalesce(Sum('monto_total'), Decimal('0.0')))['total']
        prima_col_activos = ContratoColectivo.objects.filter(activo=True).aggregate(
            total=Coalesce(Sum('monto_total'), Decimal('0.0')))['total']
        prima_emitida_total_activos = prima_ind_activos + prima_col_activos

        # 2. Siniestros Pagados (Suma de pagos asociados a reclamaciones ACTIVAS)
        # Considerar si el Pago.activo=True es suficiente o si Reclamacion.activo=True también es relevante.
        # Aquí se asume que un Pago activo implica que la reclamación asociada también era relevante.
        siniestros_pagados = Pago.objects.filter(
            reclamacion__isnull=False,
            activo=True  # Pago activo
            # Opcional: si también quieres que la reclamación esté activa:
            # reclamacion__activo=True
        ).aggregate(
            total=Coalesce(Sum('monto_pago'), Decimal('0.0')))['total']

        # 3. Ratio de Siniestralidad General (Pagados / Emitida de Contratos Activos)
        # Este ratio compara los siniestros pagados (históricos o recientes) contra la cartera de primas de contratos actualmente activos.
        # Puede ser >100% si los pagos de siniestros (que pueden ser de contratos antiguos) superan las primas de la cartera activa actual.
        ratio_siniestralidad_actual = Decimal('0.0')
        if prima_emitida_total_activos > Decimal('0.005'):
            ratio_siniestralidad_actual = (
                siniestros_pagados / prima_emitida_total_activos * 100)

        logger.debug(
            f"G03 - Prima Emitida (Activos): {prima_emitida_total_activos}, Siniestros Pagados: {siniestros_pagados}, Ratio Actual: {ratio_siniestralidad_actual}")

        # 4. Comisión Total Estimada (basada en contratos activos y % comisión del intermediario)
        # Esta es una estimación de la comisión potencial de la cartera activa.
        comision_ind_est = ContratoIndividual.objects.filter(
            activo=True,
            intermediario__isnull=False,
            # Asegurar que el intermediario tenga %
            intermediario__porcentaje_comision__isnull=False
        ).aggregate(
            total=Coalesce(Sum(
                F('monto_total') * F('intermediario__porcentaje_comision') / Decimal('100.0')), Decimal('0.0'))
        )['total']

        comision_col_est = ContratoColectivo.objects.filter(
            activo=True,
            intermediario__isnull=False,
            intermediario__porcentaje_comision__isnull=False
        ).aggregate(
            total=Coalesce(Sum(
                F('monto_total') * F('intermediario__porcentaje_comision') / Decimal('100.0')), Decimal('0.0'))
        )['total']
        comision_total_estimada_cartera_activa = comision_ind_est + comision_col_est

        # 5. Número de Contratos Activos
        contratos_activos_count = ContratoIndividual.objects.filter(activo=True).count() + \
            ContratoColectivo.objects.filter(activo=True).count()

        fig = make_subplots(
            rows=1, cols=4,
            specs=[[{'type': 'indicator'}, {'type': 'indicator'},
                    {'type': 'indicator'}, {'type': 'indicator'}]]
        )

        fig.add_trace(go.Indicator(
            mode='number',  # Cambiado a solo número, el "delta" no tiene referencia clara aquí
            value=float(prima_emitida_total_activos),
            title={'text': "Prima Cartera Activa",
                   'font': {'size': 14}},  # Título más claro
            number={'prefix': "$", 'valueformat': ',.0f'},
            domain={'row': 0, 'column': 0}
        ), row=1, col=1)

        fig.add_trace(go.Indicator(
            mode='number',
            value=float(siniestros_pagados),
            # Clarificar que son pagos globales
            title={'text': "Siniestros Pagados (Global)", 'font': {
                'size': 14}},
            number={'prefix': "$", 'valueformat': ',.0f'},
            domain={'row': 0, 'column': 1}
        ), row=1, col=2)

        fig.add_trace(go.Indicator(
            mode='number+delta',
            value=float(ratio_siniestralidad_actual),
            # Título más claro
            title={
                'text': "Ratio Sinies. (Pag/Prima Activa)", 'font': {'size': 14}},
            number={'suffix': "%", 'valueformat': '.1f'},
            delta={'reference': 70,  # Objetivo general
                   # Malo si aumenta sobre 70
                   'increasing': {'color': COLOR_PALETTE['secondary']},
                   # Bueno si disminuye bajo 70
                   'decreasing': {'color': COLOR_PALETTE['success']}},
            domain={'row': 0, 'column': 2}
        ), row=1, col=3)

        fig.add_trace(go.Indicator(
            mode='number',
            value=contratos_activos_count,
            title={'text': "N° Contratos Activos", 'font': {'size': 14}},
            number={'valueformat': ',.0f'},
            domain={'row': 0, 'column': 3}
        ), row=1, col=4)

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Indicadores Financieros Clave del Negocio', x=0.5)
        layout_grafico['height'] = 250
        layout_grafico['margin'] = dict(t=80, l=20, r=20, b=20)
        fig.update_layout(**layout_grafico)

        logger.info("G03 - KPIs Financieros Clave generados.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error G03 (KPIs Financieros): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error al generar KPIs Financieros ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 04: Distribución de Edades (Histograma Mejorado)
# ------------------------------


def grafico_04():
    try:
        # Consulta optimizada con selección de campos
        edades_queryset = (AfiliadoIndividual.objects
                           .annotate(
                               edad=ExtractYear(Now()) -
                               ExtractYear('fecha_nacimiento')
                           )
                           .order_by('edad'))

        if not edades_queryset.exists():
            return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Obtener la lista de edades
        edades = edades_queryset.values_list('edad', flat=True)

        # Procesamiento numérico eficiente
        np_edades = np.array(edades)
        mean_age = np.mean(np_edades)
        hist, bins = np.histogram(np_edades, bins=15, range=(0, 100))

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=bins[:-1],
            y=hist,
            marker_color=COLOR_PALETTE['info'],
            opacity=0.8,
            width=np.diff(bins),
            hoverinfo='y+text',
            hovertext=[
                f'Rango: {bins[i]}-{bins[i+1]} años' for i in range(len(bins)-1)]
        ))

        fig.add_vline(x=mean_age, line_dash="dot",
                      line_color=COLOR_PALETTE['secondary'],
                      annotation_text=f'Media: {mean_age:.1f} años')

        fig.update_layout(
            **BASE_LAYOUT,
            title=dict(text='Distribución de Edades', x=0.5),
            xaxis=dict(
                title='Edad',
                dtick=10,
                range=[0, 100],
                fixedrange=True
            ),
            yaxis=dict(title='Cantidad de Afiliados'),
            bargap=0.05,
            hovermode='x'
        )
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_04: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 05: Tiempo de Autorización Médica (Gauge Avanzado)
# ------------------------------


def grafico_05():
    try:
        stats = (Reclamacion.objects
                 .filter(tipo_reclamacion='MEDICA', fecha_cierre_reclamo__isnull=False, fecha_reclamo__isnull=False)
                 .annotate(
                     duracion_field=Case(
                         When(fecha_cierre_reclamo__gte=F('fecha_reclamo'),
                              then=ExpressionWrapper(
                                  F('fecha_cierre_reclamo') -
                             F('fecha_reclamo'),
                                  output_field=DurationField()
                         )),
                         default=Value(None),
                         output_field=DurationField()
                     )
                 )
                 .filter(duracion_field__isnull=False)
                 .aggregate(
                     promedio=Coalesce(Avg('duracion_field'),
                                       timedelta(days=0)),
                     maximo=Coalesce(Max('duracion_field'), timedelta(days=0)),
                     minimo=Coalesce(Min('duracion_field'), timedelta(days=0)),
                     total=Count('id')
                 ))

        if not stats['total'] or stats['total'] == 0:
            return plot(generar_figura_sin_datos("No hay datos de cierre de reclamaciones médicas"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        avg_days = stats['promedio'].days
        max_days = stats['maximo'].days
        min_days = stats['minimo'].days
        max_days = max(max_days, avg_days, 1)
        avg_days = max(avg_days, min_days)

        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=avg_days,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Tiempo Promedio Autorización Médica (días)", 'font': {
                'size': 20}},
            delta={'reference': max_days, 'increasing': {
                'color': COLOR_PALETTE['secondary']}},
            gauge={
                'axis': {'range': [0, max(max_days + 5, 30)], 'tickwidth': 1},
                'bar': {'color': COLOR_PALETTE['primary'], 'thickness': 0.25},
                'steps': [
                    {'range': [0, max(0, min_days)],
                     'color': COLOR_PALETTE['success']},
                    {'range': [max(0, min_days), avg_days],
                     'color': COLOR_PALETTE['warning']},
                    {'range': [avg_days, max_days],
                        'color': COLOR_PALETTE['secondary']}
                ],
                'threshold': {
                    'line': {'color': COLOR_PALETTE['dark'], 'width': 4},
                    'thickness': 0.8, 'value': avg_days
                }
            }
        ))

        # CORRECCIÓN: Usar método de copia para evitar conflicto con BASE_LAYOUT['margin']
        layout_actualizado = BASE_LAYOUT.copy()
        layout_actualizado['height'] = 400
        layout_actualizado['margin'] = {
            't': 80, 'b': 40, 'l': 30, 'r': 30}  # Margin específico
        fig.update_layout(**layout_actualizado)

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_05: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos("Error al generar Gráfico 05"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


# ------------------------------
# Gráfico 06: Morosidad de Contratos (Pie Chart Dinámico)
# ------------------------------


def grafico_06():
    try:
        hoy = django_timezone.now().date()
        data = (ContratoIndividual.objects
                .annotate(
                    es_moroso=Case(
                        When(fecha_fin_vigencia__lt=hoy, then=Value(True)),
                        default=Value(False),
                        output_field=BooleanField()
                    )
                )
                .values('es_moroso')
                .annotate(total=Count('id')))

        if not data.exists():
            return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        labels = ['Al Día', 'Morosos']
        morosos_count = 0
        al_dia_count = 0
        for item in data:
            if item['es_moroso']:
                morosos_count = item['total']
            else:
                al_dia_count = item['total']
        values = [al_dia_count, morosos_count]

        fig = go.Figure(data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.5,
                marker=dict(
                    colors=[COLOR_PALETTE['success'],
                        COLOR_PALETTE['secondary']],
                    line=dict(color=COLOR_PALETTE['light'], width=2)
                ),
                textposition='inside',
                textinfo='percent+label',
                insidetextorientation='radial'
            )
        ])

        fig.update_layout(
            **BASE_LAYOUT,
            title=dict(text='Estado de Morosidad', x=0.5),
            showlegend=False,
            annotations=[
                dict(
                    text=f'Total: {sum(values)}',
                    x=0.5, y=0.5,
                    font_size=20,
                    showarrow=False
                )
            ]
        )
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_06: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


# ------------------------------
# Gráfico 07: Tendencia de Pagos (Serie Temporal Completa)
# ------------------------------
logger_grafica_07 = logging.getLogger("myapp.graficas.grafico_07")


def grafico_07():
    logger_grafica_07.info(
        "==================== grafico_07: INICIO ====================")
    try:
        hoy = django_timezone.now()  # Correcto
        rango_meses_dt = [
            hoy - relativedelta(months=x) for x in range(11, -1, -1)]
        meses_str_base = [m.strftime('%Y-%m') for m in rango_meses_dt]
        logger_grafica_07.debug(
            f"Meses base para el gráfico (meses_str_base): {meses_str_base}")

        data_qs = (Pago.objects
                   # fecha_pago es DateField, TruncMonth devuelve date
                   .annotate(mes_dt_db=TruncMonth('fecha_pago'))
                   .values('mes_dt_db')
                   .annotate(total=Sum('monto_pago'))
                   .filter(total__isnull=False)  # Solo meses con pagos
                   .order_by('mes_dt_db'))

        logger_grafica_07.debug(
            f"QuerySet de Pagos (data_qs) count: {data_qs.count()}")
        # for item in list(data_qs[:3]): logger_grafica_07.debug(f"  Item de data_qs: {item}")

        # df_base para asegurar que todos los meses del rango estén presentes
        df_base = pd.DataFrame({'mes_str': meses_str_base})
        df_base['total'] = Decimal('0.00')  # Inicializar con Decimal

        if data_qs.exists():
            df_real = pd.DataFrame(list(data_qs))
            logger_grafica_07.debug(
                f"df_real (datos de BD) head:\n{df_real.head().to_string()}")
            logger_grafica_07.debug(f"df_real dtypes:\n{df_real.dtypes}")

            # mes_dt_db es un objeto 'date'
            df_real['mes_dt_obj'] = pd.to_datetime(
                df_real['mes_dt_db'], errors='coerce')
            df_real.dropna(subset=['mes_dt_obj'], inplace=True)

            if not df_real.empty:
                df_real['mes_str'] = df_real['mes_dt_obj'].dt.strftime('%Y-%m')
                df_real['total'] = df_real['total'].apply(
                    lambda x: Decimal(x) if x is not None else Decimal('0.00'))

                logger_grafica_07.debug(
                    f"df_real ANTES del merge (con mes_str) head:\n{df_real[['mes_str', 'total']].head().to_string()}")

                # Merge usando la columna 'mes_str'
                df_merged = pd.merge(df_base[['mes_str']], df_real[[
                                     'mes_str', 'total']], on='mes_str', how='left')
                df_merged['total'] = df_merged['total'].fillna(Decimal('0.00'))
                logger_grafica_07.debug(
                    f"df_merged DESPUÉS del merge head:\n{df_merged.head().to_string()}")
                df = df_merged
            else:
                logger_grafica_07.info(
                    "df_real quedó vacío después de procesar fechas, usando df_base.")
                df = df_base
        else:
            logger_grafica_07.info(
                "No hay datos de pagos en la BD para el periodo, usando df_base.")
            df = df_base

        if df.empty:
            logger_grafica_07.warning(
                "DataFrame final 'df' está vacío antes de graficar.")
            return plot(generar_figura_sin_datos("No hay datos para la tendencia de pagos."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Convertir 'total' a float para Plotly justo antes de graficar
        df['total_float'] = df['total'].astype(float)
        logger_grafica_07.debug(
            f"DataFrame final para Plotly (df) head:\n{df[['mes_str', 'total_float']].head().to_string()}")
        logger_grafica_07.debug(
            f"DataFrame final para Plotly (df) dtypes:\n{df.dtypes}")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['mes_str'],
            y=df['total_float'],
            mode='lines+markers',
            line=dict(color=COLOR_PALETTE.get(
                'primary', '#2C3E50'), width=3, shape='spline'),
            marker=dict(size=8, color=COLOR_PALETTE.get(
                'secondary', '#E74C3C')),
            fill='tozeroy',
            fillcolor=f"rgba{(*hex_to_rgb(COLOR_PALETTE.get('primary', '#2C3E50')), 0.1)}",
            name='Monto Pagado'
        ))

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(text='Flujo de Pagos Mensuales', x=0.5)
        layout_grafico['xaxis'] = dict(
            title='Mes', type='category', tickangle=45, gridcolor='#f0f0f0')
        layout_grafico['yaxis'] = dict(
            title='Monto Total Pagado', tickprefix='$', gridcolor='#f5f5f5')
        layout_grafico['hoverlabel'] = dict(bgcolor=COLOR_PALETTE.get(
            'dark', '#34495E'), font_size=14, font_color='white')
        layout_grafico['margin'] = dict(t=50, l=60, r=30, b=80)
        fig.update_layout(**layout_grafico)

        logger_grafica_07.info(
            "==================== grafico_07: FIN - Gráfico generado ====================")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger_grafica_07.error(
            f"Error EXCEPCIONAL en grafico_07: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error al generar Gráfico 07 ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


# ------------------------------
# Gráfico 08: Estado de Reclamaciones (Bar Chart Interactivo)
# ------------------------------


def grafico_08():
    try:
        data = (Reclamacion.objects
                .values('estado')
                .annotate(total=Count('id')))

        if not data.exists():
            return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        estado_map = dict(CommonChoices.ESTADO_RECLAMACION)
        df = pd.DataFrame(data)
        df['estado'] = df['estado'].map(estado_map).fillna('Desconocido')
        df = df.sort_values('total', ascending=False)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df['estado'],
            y=df['total'],
            marker_color=COLOR_PALETTE['primary'],
            opacity=0.85,
            text=df['total'],
            textposition='auto',
            texttemplate='%{text:,}',
            hoverinfo='y+name',
            textfont=dict(color='white')
        ))

        fig.update_layout(
            **BASE_LAYOUT,
            title=dict(text='Estado de Reclamaciones', x=0.5),
            xaxis=dict(title='Estado'),
            yaxis=dict(title='Cantidad'),
            hovermode='x unified',
            clickmode='event+select'
        )
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_08: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 09: Edad vs Reclamaciones (Scatter Plot)
# ------------------------------


def grafico_09():
    """Muestra la distribución de la cantidad de reclamaciones por edad del afiliado."""
    try:
        # Obtener edad de afiliados con reclamaciones
        data_qs = (Reclamacion.objects
                   # Asegurar fecha nacimiento
                   .filter(contrato_individual__afiliado__fecha_nacimiento__isnull=False)
                   .annotate(
                       edad=ExtractYear(
                           Now()) - ExtractYear('contrato_individual__afiliado__fecha_nacimiento')
                   )
                   .values('edad'))  # Solo necesitamos las edades

        if not data_qs.exists():
            return plot(generar_figura_sin_datos("No hay reclamaciones con edad de afiliado"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        edades = [d['edad']
                  for d in data_qs if d['edad'] is not None]  # Lista de edades

        if not edades:
            return plot(generar_figura_sin_datos("No hay edades válidas para mostrar"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Crear Histograma en lugar de Scatter
        fig = go.Figure(data=[go.Histogram(
            x=edades,
            marker_color=COLOR_PALETTE.get('secondary'),
            xbins=dict(  # Definir los 'bins' o rangos
                start=min(edades) if edades else 0,
                # Un poco más del máximo
                end=max(edades) + 5 if edades else 100,
                size=5  # Agrupar cada 5 años (puedes ajustar)
            )
        )])

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Distribución de Reclamaciones por Edad del Afiliado', x=0.5)
        layout_grafico['xaxis'] = dict(
            title='Edad del Afiliado (al momento de la reclamación)')
        layout_grafico['yaxis'] = dict(title='Cantidad de Reclamaciones')
        layout_grafico['bargap'] = 0.1  # Espacio entre barras
        fig.update_layout(**layout_grafico)

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_09: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos("Error al generar Gráfico 09"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 10: Frecuencia de Tipos de Reclamación (Heatmap Optimizado)
# ------------------------------


def grafico_10():
    try:
        data = (Reclamacion.objects
                .values('tipo_reclamacion')
                .annotate(total=Count('id')))

        if not data.exists():
            return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        tipo_map = dict(CommonChoices.TIPO_RECLAMACION)
        df = pd.DataFrame(list(data))
        df['tipo'] = df['tipo_reclamacion'].map(tipo_map)
        df = df.sort_values('total', ascending=False)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df['tipo'],
            y=df['total'],
            marker_color=COLOR_PALETTE['primary'],
            opacity=0.85,
            text=df['total'],
            textposition='auto',
            texttemplate='%{text:,}',
            textfont=dict(color='white')
        ))

        fig.update_layout(
            **BASE_LAYOUT,
            title=dict(text='Frecuencia de Tipos de Reclamación', x=0.5),
            xaxis=dict(title='Tipo de Reclamación', tickangle=45),
            yaxis=dict(title='Cantidad'),
            hovermode='x unified'
        )
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_10: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 11: Tiempo Resolución Reclamaciones (Boxplot)
# ------------------------------


def grafico_11():
    """Muestra la distribución del tiempo de resolución de reclamaciones en días."""
    try:
        # Obtener duraciones válidas
        tiempos_qs = (Reclamacion.objects
                      .filter(fecha_cierre_reclamo__isnull=False, fecha_reclamo__isnull=False)
                      .annotate(
                          duracion=Case(
                              When(fecha_cierre_reclamo__gte=F('fecha_reclamo'),
                                   then=ExpressionWrapper(F('fecha_cierre_reclamo') - F('fecha_reclamo'), output_field=DurationField())),
                              default=Value(None)
                          )
                      )
                      .filter(duracion__isnull=False)
                      .values_list('duracion', flat=True))

        if not tiempos_qs:  # Usar la variable correcta
            return plot(generar_figura_sin_datos("No hay datos de resolución para mostrar"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Convertir timedelta a días (integer)
        # Filtrar negativos si ocurren
        dias = [t.days for t in tiempos_qs if t is not None and t.days >= 0]

        if not dias:
            return plot(generar_figura_sin_datos("No hay duraciones válidas para mostrar"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Crear Histograma en lugar de Boxplot
        fig = go.Figure(data=[go.Histogram(
            x=dias,
            marker_color=COLOR_PALETTE.get('primary'),
            xbins=dict(
                start=0,
                end=max(dias) + 10 if dias else 50,  # Ajustar rango final
                size=10  # Agrupar cada 10 días (ajustable)
            )
        )])

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Distribución del Tiempo de Resolución de Reclamaciones', x=0.5)
        layout_grafico['xaxis'] = dict(title='Días para Resolución')
        layout_grafico['yaxis'] = dict(title='Cantidad de Reclamaciones')
        layout_grafico['bargap'] = 0.1
        fig.update_layout(**layout_grafico)

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_11: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos("Error al generar Gráfico 11"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 12: Ahorro por Pago Anual (Bar Chart)
# ------------------------------


# ------------------------------
# Gráfico 12: Ahorro por Pago Anual (CORREGIDO)
# ------------------------------
def grafico_12():
    try:
        data = (Tarifa.objects
                .values('ramo')
                .annotate(
                    # CORREGIDO: Usar Decimal y output_field
                    descuento=Sum(
                        F('monto_anual') * Decimal('0.10'),
                        output_field=DecimalField()
                    )
                ))

        if not data.exists():
            return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = go.Figure()
        # Asegurarse que el descuento no sea None antes de convertir
        fig.add_trace(go.Bar(
            x=[d['ramo'] for d in data],
            y=[float(d['descuento'] or 0) for d in data],  # Usar 'or 0'
            marker_color=COLOR_PALETTE['success'],
            opacity=0.8
        ))

        fig.update_layout(
            **BASE_LAYOUT,
            title=dict(text='Ahorro Estimado por Pago Anual',
                       x=0.5),  # Título más claro
            xaxis=dict(title='Ramo'),
            yaxis=dict(title='Ahorro Estimado (USD)', tickprefix='$')
        )
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_12: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos("Error al generar Gráfico 12"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 13: Heatmap Edad vs Cobertura
# ------------------------------


def grafico_13():
    try:
        data = (ContratoIndividual.objects
                .select_related('afiliado')
                .annotate(
                    edad=ExtractYear(Now()) -
                    ExtractYear('afiliado__fecha_nacimiento'),
                    rango_edad=Case(
                        *[When(edad__gte=min, edad__lt=max, then=Value(f"{min}-{max}"))
                          for min, max in [(18, 25), (25, 35), (35, 45), (45, 55), (55, 65)]],
                        output_field=CharField()
                    )
                )
                .values('rango_edad', 'ramo')
                .annotate(total=Count('id')))

        if not data.exists():
            return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(data)
        pivot = df.pivot_table(
            index='rango_edad', columns='ramo', values='total', fill_value=0)

        fig = go.Figure(go.Heatmap(
            x=pivot.columns,
            y=pivot.index,
            z=pivot.values,
            colorscale='Viridis',
            text=pivot.values,
            texttemplate="%{text}",
            hoverinfo="x+y+z"
        ))

        fig.update_layout(
            **BASE_LAYOUT,
            title=dict(text='Distribución por Edad y Ramo', x=0.5),
            xaxis=dict(title='Ramo'),
            yaxis=dict(title='Rango de Edad')
        )
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_13: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 14 (Nuevo): Estado de Continuidad de Contratos del Último Mes Completo (Pie Chart)
# ------------------------------


def grafico_14():
    """
    Muestra la proporción de contratos (Ind + Col) que continuaron vs. no continuaron
    del total de contratos cuya vigencia finalizaba el mes anterior completo.
    """
    try:
        logger.debug(
            "G14_nuevo - Iniciando Estado de Continuidad de Contratos (Último Mes)")

        hoy = date.today()
        primer_dia_mes_actual = hoy.replace(day=1)
        ultimo_dia_mes_anterior = primer_dia_mes_actual - timedelta(days=1)
        primer_dia_mes_anterior = ultimo_dia_mes_anterior.replace(day=1)

        mes_anterior_label = primer_dia_mes_anterior.strftime("%B %Y")
        logger.info(
            f"G14_nuevo - Analizando contratos que vencían en: {mes_anterior_label}")

        # --- Contratos Individuales ---
        # Base: Contratos Ind cuya fecha_fin_vigencia fue el mes pasado
        base_contratos_ind_qs = ContratoIndividual.objects.filter(
            fecha_fin_vigencia__gte=primer_dia_mes_anterior,
            fecha_fin_vigencia__lte=ultimo_dia_mes_anterior
        )
        total_podian_continuar_ind = base_contratos_ind_qs.count()

        # No Continuaron: De la base, los que están VENCIDOS (o ANULADOS en ese periodo, más complejo)
        # Simplificación: si su estatus actual es VENCIDO
        no_continuaron_ind = base_contratos_ind_qs.filter(
            estatus='VENCIDO').count()

        continuaron_ind = total_podian_continuar_ind - no_continuaron_ind

        # --- Contratos Colectivos ---
        base_contratos_col_qs = ContratoColectivo.objects.filter(
            fecha_fin_vigencia__gte=primer_dia_mes_anterior,
            fecha_fin_vigencia__lte=ultimo_dia_mes_anterior
        )
        total_podian_continuar_col = base_contratos_col_qs.count()

        no_continuaron_col = base_contratos_col_qs.filter(
            estatus='VENCIDO').count()
        continuaron_col = total_podian_continuar_col - no_continuaron_col

        # --- Totales ---
        total_general_podian_continuar = total_podian_continuar_ind + \
            total_podian_continuar_col
        total_general_no_continuaron = no_continuaron_ind + no_continuaron_col
        total_general_continuaron = continuaron_ind + continuaron_col

        logger.debug(
            f"G14_nuevo - Podían continuar: {total_general_podian_continuar}, No Continuaron: {total_general_no_continuaron}, Continuaron: {total_general_continuaron}")

        if total_general_podian_continuar == 0:
            return plot(generar_figura_sin_datos(f"No hubo contratos finalizando vigencia en {mes_anterior_label}"),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        labels = ['Contratos que Continuaron',
                  'Contratos que No Continuaron (Lapsos)']
        values = [total_general_continuaron, total_general_no_continuaron]

        # Filtrar si alguna categoría tiene 0 para no mostrarla en el pie chart si se desea
        # data_for_pie = [{'label': l, 'value': v} for l, v in zip(labels, values) if v > 0]
        # if not data_for_pie:
        #     return plot(generar_figura_sin_datos("No hay datos para mostrar"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        # labels_pie = [d['label'] for d in data_for_pie]
        # values_pie = [d['value'] for d in data_for_pie]

        # Si quieres mostrar incluso si una categoría es 0:
        labels_pie = labels
        values_pie = values

        fig = go.Figure(data=[go.Pie(
            labels=labels_pie,
            values=values_pie,
            hole=0.3,
            marker_colors=[COLOR_PALETTE.get(
                'success'), COLOR_PALETTE.get('secondary')],
            textinfo='percent+label+value',
            hoverinfo='label+value+percent',
            insidetextorientation='radial'
        )])

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text=f'Estado de Continuidad de Contratos (Vencimiento en {mes_anterior_label})', x=0.5)
        # Mostrar leyenda para este tipo de pie
        layout_grafico['showlegend'] = True
        layout_grafico['margin'] = dict(t=60, b=40, l=20, r=20)
        fig.update_layout(**layout_grafico)

        logger.info(
            f"G14_nuevo - Gráfico de Continuidad de Contratos generado para {mes_anterior_label}")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(
            f"Error G14_nuevo (Continuidad Contratos): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error al generar Gráfico 14 ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 15: Monto Asegurado Promedio y Máximo por Rango de Edad (Barras Agrupadas)
# ------------------------------


def grafico_15():  # Reemplaza el anterior G15 de Box Plot
    """
    Muestra el Monto Total Asegurado PROMEDIO y MÁXIMO de Contratos Individuales,
    agrupados por Rango de Edad del afiliado.
    """
    try:
        logger.debug(
            "G15 - Iniciando Monto Asegurado Promedio/Máximo por Rango Edad (Barras)")

        # Definir rangos de edad en español para las etiquetas
        rangos_edad_definidos = [
            (0, 17, '0-17 años'), (18, 25, '18-25 años'), (26, 35, '26-35 años'),
            (36, 45, '36-45 años'), (46, 55, '46-55 años'), (56, 65, '56-65 años'),
            # Límite superior realista
            (66, 75, '66-75 años'), (76, 120, '76+ años')
        ]
        when_edad_clauses = [When(edad__gte=min_e, edad__lte=max_e, then=Value(lbl))
                             for min_e, max_e, lbl in rangos_edad_definidos]

        data_qs = (ContratoIndividual.objects
                   .filter(activo=True, afiliado__fecha_nacimiento__isnull=False, monto_total__isnull=False, monto_total__gt=0)
                   .annotate(
                       edad=ExtractYear(Now()) -
                       ExtractYear('afiliado__fecha_nacimiento'),
                       rango_edad_label=Case(
                           *when_edad_clauses, default=Value('Otros'), output_field=CharField())
                   )
                   # Excluir los que no caen en rangos definidos
                   .exclude(rango_edad_label='Otros')
                   # Agrupar por el label del rango
                   .values('rango_edad_label')
                   .annotate(
                       monto_asegurado_promedio=Coalesce(
                           Avg('monto_total'), Value(Decimal('0.0'))),
                       monto_asegurado_maximo=Coalesce(
                           Max('monto_total'), Value(Decimal('0.0')))
                   )
                   # Ordenar por el orden definido en 'rangos_edad_definidos' para el gráfico
                   .order_by(
                       Case(*[When(rango_edad_label=label, then=Value(i))
                              for i, (_, _, label) in enumerate(rangos_edad_definidos)])
                   )
                   )

        if not data_qs.exists():
            return plot(generar_figura_sin_datos("No hay contratos individuales con montos y edad para analizar"),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(list(data_qs))

        # Convertir a float para Plotly
        df['monto_asegurado_promedio'] = pd.to_numeric(
            df['monto_asegurado_promedio'], errors='coerce').fillna(0.0)
        df['monto_asegurado_maximo'] = pd.to_numeric(
            df['monto_asegurado_maximo'], errors='coerce').fillna(0.0)

        if df.empty or (df['monto_asegurado_promedio'].sum() == 0 and df['monto_asegurado_maximo'].sum() == 0):
            return plot(generar_figura_sin_datos("No hay datos de montos asegurados válidos tras procesar"),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Crear Gráfico de Barras Agrupadas
        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=df['rango_edad_label'],
            y=df['monto_asegurado_promedio'],
            name='Monto Asegurado Promedio',  # Leyenda en español
            marker_color=COLOR_PALETTE.get('info'),
            text=df['monto_asegurado_promedio'],
            texttemplate='$%{text:,.0f}',
            textposition='auto',
            hovertemplate="<b>Rango Edad:</b> %{x}<br>Promedio: $%{y:,.0f}<extra></extra>"
        ))

        fig.add_trace(go.Bar(
            x=df['rango_edad_label'],
            y=df['monto_asegurado_maximo'],
            name='Monto Asegurado Máximo',  # Leyenda en español
            marker_color=COLOR_PALETTE.get('primary'),
            text=df['monto_asegurado_maximo'],
            texttemplate='$%{text:,.0f}',
            textposition='auto',
            hovertemplate="<b>Rango Edad:</b> %{x}<br>Máximo: $%{y:,.0f}<extra></extra>"
        ))

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Monto Asegurado Promedio y Máximo por Rango de Edad (Cont. Individuales)', x=0.5)
        # type='category' para respetar el orden
        layout_grafico['xaxis'] = dict(
            title='Rango de Edad del Afiliado', type='category')
        layout_grafico['yaxis'] = dict(
            title='Monto Total Asegurado (USD)', tickprefix='$', tickformat=',.0f')
        layout_grafico['barmode'] = 'group'  # Barras agrupadas, no apiladas
        layout_grafico['legend'] = dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)  # Leyenda arriba
        layout_grafico['margin'] = dict(t=80, b=80, l=70, r=30)
        fig.update_layout(**layout_grafico)

        logger.info(
            "G15 - Monto Asegurado Prom/Max por Rango Edad (Barras) generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error G15 (Barras Prom/Max): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error al generar Gráfico 15 ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 16: Desempeño Top N Intermediarios (Primas y Rentabilidad Relativa)
# ------------------------------


def grafico_16():  # Reemplaza el G16 de barras agrupadas
    """
    Muestra las Primas Emitidas Totales para los Top N Intermediarios.
    El color de la barra indica una "rentabilidad relativa" (Primas vs Siniestros+Comisiones).
    El tooltip muestra el detalle de Primas, Siniestros Incurridos y Comisión Estimada.
    """
    try:
        N = 10  # Top N intermediarios
        logger.debug(f"G16 - Iniciando Desempeño Top {N} Intermediarios")

        # Las subconsultas y la consulta principal son las mismas que tenías,
        # ya que los datos base son correctos.
        siniestros_ind_sub = Subquery(
            Reclamacion.objects.filter(
                contrato_individual__intermediario_id=OuterRef('pk'), activo=True,
                contrato_individual__activo=True  # Siniestros de contratos que estaban activos
            )
            .values('contrato_individual__intermediario_id')
            .annotate(total_siniestro=Sum('monto_reclamado'))
            .values('total_siniestro')[:1],
            output_field=DecimalField()
        )
        siniestros_col_sub = Subquery(
            Reclamacion.objects.filter(
                contrato_colectivo__intermediario_id=OuterRef('pk'), activo=True,
                contrato_colectivo__activo=True
            )
            .values('contrato_colectivo__intermediario_id')
            .annotate(total_siniestro=Sum('monto_reclamado'))
            .values('total_siniestro')[:1],
            output_field=DecimalField()
        )

        intermediarios_data_qs = (
            Intermediario.objects.filter(activo=True)
            .annotate(
                prima_ind=Coalesce(Sum('contratoindividual__monto_total', filter=Q(
                    contratoindividual__activo=True)), Decimal('0.0')),
                prima_col=Coalesce(Sum('contratos_colectivos__monto_total', filter=Q(
                    contratos_colectivos__activo=True)), Decimal('0.0')),
                siniestros_ind_calc=Coalesce(
                    # Renombrar para claridad
                    siniestros_ind_sub, Decimal('0.0')),
                siniestros_col_calc=Coalesce(
                    siniestros_col_sub, Decimal('0.0')),
            )
            .annotate(
                prima_total_calc=F('prima_ind') + F('prima_col'),
                siniestros_total_calc=F(
                    'siniestros_ind_calc') + F('siniestros_col_calc'),
                comision_estimada_calc=(
                    (F('prima_ind') + F('prima_col')) * F('porcentaje_comision') / Decimal('100.0'))
            )
            # Solo intermediarios con primas significativas
            .filter(prima_total_calc__gt=Decimal('0.005'))
            .order_by('-prima_total_calc')[:N]
            # No es necesario .values() aquí si vamos a acceder a los campos del objeto después
        )

        if not intermediarios_data_qs:  # Chequea si el QuerySet tiene resultados
            return plot(generar_figura_sin_datos("No hay datos de intermediarios con primas para G16"),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df_data = []
        for inter in intermediarios_data_qs:
            prima_total = inter.prima_total_calc
            siniestros_total = inter.siniestros_total_calc
            comision_estimada = inter.comision_estimada_calc

            # Calcular un "Margen Bruto Estimado" o "Resultado Técnico Bruto"
            # Resultado = Prima - Siniestros - Comisiones
            resultado_tecnico = prima_total - siniestros_total - comision_estimada

            # Ratio de Resultado Técnico sobre Prima (para colorear)
            # (Prima - Siniestros - Comisiones) / Prima
            ratio_resultado_tecnico = Decimal('0.0')
            if prima_total > Decimal('0.005'):
                ratio_resultado_tecnico = (
                    resultado_tecnico / prima_total) * 100

            df_data.append({
                'nombre_completo': inter.nombre_completo,
                'prima_total': float(prima_total),
                'siniestros_total': float(siniestros_total),
                'comision_estimada': float(comision_estimada),
                'resultado_tecnico': float(resultado_tecnico),
                'ratio_resultado_tecnico': float(ratio_resultado_tecnico)
            })

        df = pd.DataFrame(df_data)
        # Si después del bucle no hay datos (improbable si queryset no estaba vacío)
        if df.empty:
            return plot(generar_figura_sin_datos("No hay datos válidos de intermediarios para G16"),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Ordenar por Prima Total para el gráfico (ya debería estarlo por la query)
        # df = df.sort_values('prima_total', ascending=True) # Para barras horizontales ascendentes

        # Crear gráfico de barras horizontales
        fig = px.bar(
            df,
            y='nombre_completo',  # Intermediarios en el eje Y para barras horizontales
            x='prima_total',     # Longitud de la barra es la Prima Total
            orientation='h',
            color='ratio_resultado_tecnico',  # Colorear según el ratio de rentabilidad
            color_continuous_scale=px.colors.diverging.RdYlGn,  # Rojo-Amarillo-Verde
            color_continuous_midpoint=0,  # Punto medio en 0% para la escala de color
            labels={
                'nombre_completo': 'Intermediario',
                'prima_total': 'Prima Emitida Total (USD)',
                'ratio_resultado_tecnico': 'Margen Técnico Bruto (%)'
            },
            text='prima_total'  # Mostrar valor de la prima en la barra
        )

        fig.update_traces(
            texttemplate='$%{text:,.0f}',
            textposition='auto',  # 'outside' puede funcionar mejor con barras horizontales
            customdata=df[['siniestros_total', 'comision_estimada',
                           'resultado_tecnico', 'ratio_resultado_tecnico']],
            hovertemplate=(
                "<b>Intermediario: %{y}</b><br><br>"
                "Prima Emitida Total: $%{x:,.0f}<br>"
                "Siniestros Incurridos: $%{customdata[0]:,.0f}<br>"
                "Comisión Estimada: $%{customdata[1]:,.0f}<br>"
                "<b>Resultado Técnico Bruto: $%{customdata[2]:,.0f}</b><br>"
                "(Margen Técnico: %{customdata[3]:.1f}%)"
                "<extra></extra>"
            )
        )

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text=f'Desempeño Top {N} Intermediarios por Prima Emitida', x=0.5)
        layout_grafico['xaxis_title'] = 'Prima Emitida Total (USD)'
        layout_grafico['yaxis_title'] = 'Intermediario'
        layout_grafico['yaxis'] = dict(
            autorange="reversed")  # El de mayor prima arriba
        layout_grafico['height'] = max(
            400, N * 40 + 100)  # Altura dinámica según N
        # Título para la barra de color
        layout_grafico['coloraxis_colorbar_title_text'] = 'Margen (%)'
        # Margen izquierdo amplio para nombres
        layout_grafico['margin'] = dict(t=60, b=50, l=250, r=50)
        fig.update_layout(**layout_grafico)

        logger.info(
            "G16 - Desempeño Top Intermediarios (Barras Horizontales) generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(
            f"Error G16 (Desempeño Intermediarios): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error al generar Gráfico 16 ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 17: Evolución Montos Contratos
# ------------------------------


def grafico_17():
    try:
        individual = (ContratoIndividual.objects
                      .annotate(mes=TruncMonth('fecha_emision'))
                      .values('mes')
                      .annotate(total=Sum('monto_total'))
                      .order_by('mes'))

        colectivo = (ContratoColectivo.objects
                     .annotate(mes=TruncMonth('fecha_emision'))
                     .values('mes')
                     .annotate(total=Sum('monto_total'))
                     .order_by('mes'))

        df_ind = pd.DataFrame(individual) if individual.exists(
        ) else pd.DataFrame(columns=['mes', 'total'])
        df_col = pd.DataFrame(colectivo) if colectivo.exists(
        ) else pd.DataFrame(columns=['mes', 'total'])

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_ind['mes'], y=df_ind['total'],
            name='Individual', line=dict(color=COLOR_PALETTE['primary'])
        ))
        fig.add_trace(go.Scatter(
            x=df_col['mes'], y=df_col['total'],
            name='Colectivo', line=dict(color=COLOR_PALETTE['secondary'])
        ))

        fig.update_layout(
            **BASE_LAYOUT,
            title=dict(text='Evolución de Montos Contratados', x=0.5),
            xaxis=dict(title='Mes'),
            yaxis=dict(title='Monto Total (USD)', tickprefix='$')
        )
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_17: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 18: Ratio Siniestralidad Estimado por Rango de Edad (VISUALMENTE CAPEADO AL 100%)
# ------------------------------


def grafico_18():
    """
    Muestra el Ratio de Siniestralidad (Reclamado/Contratado) por Rango de Edad del Afiliado.
    La altura de la barra y el texto en la barra se capean visualmente al 100%.
    El tooltip muestra el ratio real calculado y los montos absolutos.
    """
    try:
        logger.debug(
            "G18 - Iniciando Ratio Siniestralidad por Rango Edad (Visual Capeado 100%)")
        rangos_edad_definidos = [
            (0, 17, '0-17'), (18, 25, '18-25'), (26, 35, '26-35'),
            (36, 45, '36-45'), (46, 55, '46-55'), (56, 65, '56-65'),
            (66, 75, '66-75'), (76, 120, '76+')
        ]
        when_edad_clauses = [When(edad__gte=min_e, edad__lte=max_e, then=Value(lbl))
                             for min_e, max_e, lbl in rangos_edad_definidos]

        # 1. Monto Total Contratado
        contratado_por_edad_qs = (ContratoIndividual.objects
                                  .filter(activo=True, afiliado__fecha_nacimiento__isnull=False)
                                  .annotate(
                                      edad=ExtractYear(Now()) -
                                      ExtractYear(
                                          'afiliado__fecha_nacimiento'),
                                      rango_edad_calc=Case(
                                          *when_edad_clauses, default=Value('Otro'), output_field=CharField())
                                  )
                                  .exclude(rango_edad_calc='Otro')
                                  .values('rango_edad_calc')
                                  .annotate(total_contratado_rango=Coalesce(Sum('monto_total'), Value(Decimal('0.0'))))
                                  # No es necesario order_by aquí si usamos un dict y luego iteramos por labels_ordenados_grafico
                                  )
        dict_contratado = {item['rango_edad_calc']: item['total_contratado_rango']
                           for item in contratado_por_edad_qs}

        # 2. Monto Total Reclamado
        reclamado_por_edad_qs = (Reclamacion.objects
                                 .filter(
                                     contrato_individual__isnull=False,
                                     # Importante para alinear con primas de contratos activos
                                     contrato_individual__activo=True,
                                     contrato_individual__afiliado__fecha_nacimiento__isnull=False
                                 )
                                 .annotate(
                                     edad=ExtractYear(
                                         Now()) - ExtractYear('contrato_individual__afiliado__fecha_nacimiento'),
                                     rango_edad_calc=Case(
                                         *when_edad_clauses, default=Value('Otro'), output_field=CharField())
                                 )
                                 .exclude(rango_edad_calc='Otro')
                                 .values('rango_edad_calc')
                                 .annotate(total_reclamado_rango=Coalesce(Sum('monto_reclamado'), Value(Decimal('0.0'))))
                                 )
        dict_reclamado = {item['rango_edad_calc']: item['total_reclamado_rango']
                          for item in reclamado_por_edad_qs}

        # 3. Combinar datos y calcular ratio
        resultados = []
        labels_ordenados_grafico = [lbl for _, _, lbl in rangos_edad_definidos]
        RATIO_CAP_VISUAL = Decimal('100.0')

        for rango_label in labels_ordenados_grafico:
            contratado = dict_contratado.get(rango_label, Decimal('0.0'))
            reclamado_real = dict_reclamado.get(rango_label, Decimal('0.0'))

            ratio_bruto = Decimal('0.0')
            if contratado > Decimal('0.005'):
                ratio_bruto = (reclamado_real / contratado * 100)

            ratio_para_display = min(ratio_bruto, RATIO_CAP_VISUAL)

            texto_en_barra_final = f"{ratio_para_display:.0f}%"
            if ratio_bruto > RATIO_CAP_VISUAL:
                texto_en_barra_final = f"{RATIO_CAP_VISUAL:.0f}%+"

            logger.debug(
                f"G18 - Rango: {rango_label}, Contratado: {contratado:.2f}, Reclamado: {reclamado_real:.2f}, Ratio Bruto: {ratio_bruto:.1f}%, Ratio Display: {ratio_para_display:.1f}%")

            resultados.append({
                'rango': rango_label,
                'monto_contratado': contratado,
                'monto_reclamado_real': reclamado_real,
                'ratio_graficar': float(ratio_para_display.quantize(Decimal('0.1'))),
                'ratio_real_calculado': float(ratio_bruto.quantize(Decimal('0.1'))),
                'texto_barra_display': texto_en_barra_final
            })

        if not resultados:
            return plot(generar_figura_sin_datos("No hay datos suficientes para ratio por edad"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(resultados)
        # El orden ya está garantizado por iterar sobre labels_ordenados_grafico

        # 4. Crear gráfico
        colors = []
        threshold_saludable = 70.0
        for ratio_real_val in df['ratio_real_calculado']:
            if ratio_real_val >= 100.0:
                colors.append(COLOR_PALETTE.get('dark', '#34495E'))
            elif ratio_real_val >= threshold_saludable:
                colors.append(COLOR_PALETTE.get('secondary', '#E74C3C'))
            elif ratio_real_val >= threshold_saludable * 0.6:
                colors.append(COLOR_PALETTE.get('warning', '#F39C12'))
            else:
                colors.append(COLOR_PALETTE.get('success', '#27AE60'))

        fig = go.Figure(data=[go.Bar(
            x=df['rango'],
            y=df['ratio_graficar'],
            marker_color=colors,
            text=df['texto_barra_display'],
            textposition='auto',
            customdata=np.stack(
                (df['monto_contratado'], df['monto_reclamado_real'], df['ratio_real_calculado']), axis=-1),
            hovertemplate=(
                "<b>Rango Edad: %{x}</b><br>"
                "Ratio Siniestralidad (Calculado Real): %{customdata[2]:.1f}%<br>"
                "Prima Total: $%{customdata[0]:,.0f}<br>"
                "Siniestros Totales: $%{customdata[1]:,.0f}"
                "<extra></extra>"
            )
        )])

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Ratio Siniestralidad por Rango de Edad (Visualizado hasta 100%)', x=0.5)
        layout_grafico['xaxis'] = dict(
            title='Rango de Edad', type='category')  # Mantener orden
        layout_grafico['yaxis'] = dict(
            title='Ratio Siniestralidad (%)',
            ticksuffix='%',
            range=[0, float(RATIO_CAP_VISUAL * Decimal('1.1'))]
        )
        layout_grafico['margin'] = dict(t=50, l=70, r=30, b=80)
        fig.update_layout(**layout_grafico)

        logger.info(
            "G18 - Gráfico de Ratio Siniestralidad por Edad (Visual Capeado 100%) generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error G18 (Visual Capeado 100%): {e}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error al generar Gráfico 18 ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


# ------------------------------
# Gráfico 19: Estados de Contratos
# ------------------------------


def grafico_19():
    try:
        data = (ContratoIndividual.objects
                .values('estatus')
                .annotate(total=Count('id'))
                .order_by('-total'))

        if not data.exists():
            return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        labels = [d['estatus'] for d in data]
        values = [d['total'] for d in data]

        fig = go.Figure(go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker=dict(colors=list(COLOR_PALETTE.values()))
        ))

        fig.update_layout(
            **BASE_LAYOUT,
            title=dict(text='Estados de Contratos', x=0.5)
        )
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_19: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 20: Top 10 Contratos
# ------------------------------


def grafico_20():
    """Top 10 Contratos Individuales por Monto."""
    try:
        data = (ContratoIndividual.objects
                .order_by('-monto_total')[:10]
                .values('numero_contrato', 'monto_total'))

        if not data.exists():
            return plot(generar_figura_sin_datos("No hay Contratos Individuales para mostrar"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        montos = [float(d['monto_total'] or 0) for d in data]
        numeros = [d['numero_contrato']
                   or f"Contrato ID {i}" for i, d in enumerate(data)]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=numeros, x=montos, orientation='h',
            marker_color=COLOR_PALETTE.get('primary', '#2C3E50'),
            text=[f"${m:,.2f}" for m in montos], textposition='auto',
            hoverinfo='x+y'
        ))

        # CORRECCIÓN: Usar método de copia para evitar conflicto con BASE_LAYOUT['margin']
        layout_actualizado = BASE_LAYOUT.copy()
        layout_actualizado['title'] = dict(
            text='Top 10 Contratos Individuales por Monto', x=0.5)
        layout_actualizado['xaxis'] = dict(
            title='Monto Total (USD)', tickprefix='$')
        layout_actualizado['yaxis'] = dict(
            title='Número de Contrato', autorange="reversed")
        layout_actualizado['margin'] = dict(
            l=180, r=20, t=50, b=40)  # Margin específico
        fig.update_layout(**layout_actualizado)

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_20: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos("Error al generar Gráfico 20"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 21: tendencia mensual del ratio de siniestralidad (Pagados / Prima Emitida).
# ------------------------------


def grafico_21():
    """Muestra la tendencia mensual del ratio de siniestralidad (Siniestros Pagados en el mes / Prima Emitida en el mes)."""
    try:
        logger.debug("G21 - Iniciando Tendencia Mensual Ratio Siniestralidad")

        # --- 1. PRIMA EMITIDA MENSUAL ---
        # Contratos Individuales
        prima_mensual_ind_qs = (ContratoIndividual.objects
                                .filter(activo=True, fecha_emision__isnull=False, monto_total__gt=Decimal('0.00'))
                                # Usar un nombre de columna temporal
                                .annotate(mes_source=TruncMonth('fecha_emision'))
                                .values('mes_source')
                                .annotate(prima_calculada=Sum('monto_total'))
                                .order_by('mes_source'))
        df_prima_ind = pd.DataFrame(list(prima_mensual_ind_qs))
        if not df_prima_ind.empty:
            df_prima_ind['mes'] = pd.to_datetime(df_prima_ind['mes_source']).dt.normalize(
            ).dt.tz_localize(None)  # Asegurar Naive Datetime
            df_prima_ind.drop(columns=['mes_source'], inplace=True)
        else:
            df_prima_ind = pd.DataFrame(columns=['mes', 'prima_calculada'])

        # Contratos Colectivos
        prima_mensual_col_qs = (ContratoColectivo.objects
                                .filter(activo=True, fecha_emision__isnull=False, monto_total__gt=Decimal('0.00'))
                                .annotate(mes_source=TruncMonth('fecha_emision'))
                                .values('mes_source')
                                .annotate(prima_calculada=Sum('monto_total'))
                                .order_by('mes_source'))
        df_prima_col = pd.DataFrame(list(prima_mensual_col_qs))
        if not df_prima_col.empty:
            df_prima_col['mes'] = pd.to_datetime(df_prima_col['mes_source']).dt.normalize(
            ).dt.tz_localize(None)  # Asegurar Naive Datetime
            df_prima_col.drop(columns=['mes_source'], inplace=True)
        else:
            df_prima_col = pd.DataFrame(columns=['mes', 'prima_calculada'])

        # Consolidar Primas
        if not df_prima_ind.empty or not df_prima_col.empty:
            df_prima_total_mensual = pd.concat(
                [df_prima_ind, df_prima_col], ignore_index=True)
            if not df_prima_total_mensual.empty and 'prima_calculada' in df_prima_total_mensual.columns:
                prima_agrupada = df_prima_total_mensual.groupby(
                    'mes')['prima_calculada'].sum().reset_index()
                prima_agrupada.rename(
                    columns={'prima_calculada': 'prima_emitida_mes'}, inplace=True)
            else:  # Si después de concatenar queda vacío o sin la columna esperada
                prima_agrupada = pd.DataFrame(
                    columns=['mes', 'prima_emitida_mes'])
        else:
            prima_agrupada = pd.DataFrame(columns=['mes', 'prima_emitida_mes'])

        # Asegurar que 'mes' sea datetime64[ns] incluso si está vacío
        prima_agrupada['mes'] = pd.to_datetime(
            prima_agrupada['mes'], errors='coerce')
        # Eliminar filas donde 'mes' no pudo convertirse
        prima_agrupada = prima_agrupada.dropna(subset=['mes'])

        # --- 2. SINIESTROS PAGADOS MENSUAL ---
        siniestros_pagados_qs = (Pago.objects
                                 .filter(reclamacion__isnull=False, activo=True, fecha_pago__isnull=False, monto_pago__gt=Decimal('0.00'))
                                 # fecha_pago es DateField, TruncMonth devuelve date
                                 .annotate(mes_source=TruncMonth('fecha_pago'))
                                 .values('mes_source')
                                 .annotate(siniestros_del_mes=Sum('monto_pago'))
                                 .order_by('mes_source'))

        df_siniestros = pd.DataFrame(list(siniestros_pagados_qs))
        if not df_siniestros.empty:
            # Convertir date a datetime (será naive)
            df_siniestros['mes'] = pd.to_datetime(df_siniestros['mes_source'])
            df_siniestros.drop(columns=['mes_source'], inplace=True)
            siniestros_agrupados = df_siniestros.rename(
                columns={'siniestros_del_mes': 'siniestros_pagados_mes'})
        else:
            siniestros_agrupados = pd.DataFrame(
                columns=['mes', 'siniestros_pagados_mes'])

        siniestros_agrupados['mes'] = pd.to_datetime(
            siniestros_agrupados['mes'], errors='coerce')
        siniestros_agrupados = siniestros_agrupados.dropna(subset=['mes'])

        # --- 3. COMBINAR DATOS ---
        if prima_agrupada.empty and siniestros_agrupados.empty:
            return plot(generar_figura_sin_datos("No hay datos de primas ni siniestros para tendencia"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Para el merge, asegurar que 'mes' sea el tipo correcto y no haya nulos
        if prima_agrupada.empty:
            df_merged = siniestros_agrupados.copy()
            df_merged['prima_emitida_mes'] = Decimal(
                '0.0')  # Usar Decimal inicialmente
        elif siniestros_agrupados.empty:
            df_merged = prima_agrupada.copy()
            df_merged['siniestros_pagados_mes'] = Decimal('0.0')
        else:
            # Antes del merge, es crucial que la columna 'mes' en ambos DataFrames sea del mismo tipo exacto (datetime64[ns, UTC] o datetime64[ns])
            # La lógica anterior ya debería haberlas dejado como datetime64[ns] (naive)
            logger.debug(
                f"G21 - Tipo 'mes' en prima_agrupada: {prima_agrupada['mes'].dtype}")
            logger.debug(
                f"G21 - Tipo 'mes' en siniestros_agrupados: {siniestros_agrupados['mes'].dtype}")
            df_merged = pd.merge(
                prima_agrupada, siniestros_agrupados, on='mes', how='outer')

        df_merged[['prima_emitida_mes', 'siniestros_pagados_mes']] = df_merged[[
            'prima_emitida_mes', 'siniestros_pagados_mes']].fillna(Decimal('0.0'))
        df_merged = df_merged.sort_values('mes').reset_index(drop=True)

        # Convertir a numérico (float) para cálculo de ratio y Plotly, después de fillna
        df_merged['prima_emitida_mes'] = pd.to_numeric(
            df_merged['prima_emitida_mes'], errors='coerce').fillna(0.0)
        df_merged['siniestros_pagados_mes'] = pd.to_numeric(
            df_merged['siniestros_pagados_mes'], errors='coerce').fillna(0.0)

        # Calcular ratio
        df_merged['ratio'] = df_merged.apply(
            lambda row: (row['siniestros_pagados_mes'] /
                         row['prima_emitida_mes'] * 100)
            if row['prima_emitida_mes'] > 0.005 else 0.0,
            axis=1
        )

        num_meses_display = 24
        if len(df_merged) > num_meses_display:
            df_merged = df_merged.tail(num_meses_display)

        # Chequeo más robusto
        if df_merged.empty or ('mes' in df_merged.columns and df_merged['mes'].isnull().all()):
            return plot(generar_figura_sin_datos("No hay datos suficientes tras procesar para la tendencia"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df_merged['mes_str'] = df_merged['mes'].dt.strftime('%Y-%m')

        # Crear gráfico... (el resto del código del gráfico como lo tenías es probablemente correcto)
        fig = px.line(
            df_merged, x='mes_str', y='ratio',
            labels={'mes_str': 'Mes', 'ratio': 'Ratio Siniestralidad (%)'},
            title="Tendencia Mensual Ratio Siniestralidad (Siniestros Pagados / Prima Emitida en el Mes)",
            markers=True,
            custom_data=['prima_emitida_mes', 'siniestros_pagados_mes']
        )
        fig.update_traces(
            line=dict(color=COLOR_PALETTE.get(
                'secondary', '#E74C3C'), width=3),
            marker=dict(size=7),
            hovertemplate=(
                "<b>Mes:</b> %{x}<br>"
                "<b>Ratio:</b> %{y:.1f}%<br>"
                "Prima Emitida en Mes: $%{customdata[0]:,.0f}<br>"
                "Siniestros Pagados en Mes: $%{customdata[1]:,.0f}<extra></extra>"
            )
        )
        fig.add_hline(y=70, line_dash="dot", line_color="red",
                      annotation_text="Límite Ref. 70%", annotation_position="bottom right")

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['xaxis'] = dict(
            title_text='Mes', type='category', tickangle=45)

        max_ratio_val = df_merged['ratio'].max()
        y_axis_upper_limit = 110
        # Solo ajustar si max_ratio_val es un número válido y positivo
        if pd.notna(max_ratio_val) and max_ratio_val > 0:
            y_axis_upper_limit = max(y_axis_upper_limit, max_ratio_val * 1.15)

        layout_grafico['yaxis'] = dict(
            title_text='Ratio (%)', ticksuffix='%', range=[0, y_axis_upper_limit])
        layout_grafico['hovermode'] = 'x unified'
        layout_grafico['margin'] = dict(t=60, l=70, r=30, b=100)
        fig.update_layout(**layout_grafico)

        logger.info("G21 - Tendencia Mensual Ratio Siniestralidad generada.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:  # Captura más general para ver el tipo exacto de error si persiste
        logger.error(
            f"Error crítico en G21: {type(e).__name__} - {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error al generar G21 ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ----------------------------------------------------------------------
# Gráfico 22 (Nuevo): Distribución de Montos Reclamados (Histograma)
# ------------------------------


def grafico_22():
    """Muestra cómo se distribuyen los montos de las reclamaciones."""
    try:
        montos_qs = (Reclamacion.objects.filter(monto_reclamado__isnull=False,
                     monto_reclamado__gt=0).values_list('monto_reclamado', flat=True))
        if not montos_qs:
            return plot(generar_figura_sin_datos("No hay montos reclamados"), output_type='div', config=GRAPH_CONFIG)
        montos = [float(m) for m in montos_qs]
        if not montos:
            return plot(generar_figura_sin_datos("No hay montos válidos"), output_type='div', config=GRAPH_CONFIG)
        fig = go.Figure(data=[go.Histogram(
            x=montos, marker_color=COLOR_PALETTE.get('secondary'), nbinsx=20)])
        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Distribución de Montos Reclamados', x=0.5)
        layout_grafico['xaxis'] = dict(
            title='Monto Reclamado (USD)', tickprefix='$')
        layout_grafico['yaxis'] = dict(title='Cantidad de Reclamaciones')
        layout_grafico['bargap'] = 0.05
        layout_grafico['margin'] = dict(t=50, b=40, l=50, r=30)
        fig.update_layout(**layout_grafico)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error G22(nuevo): {e}", exc_info=True)
        return plot(generar_figura_sin_datos("Error G22"), output_type='div', config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 23: Prima Emitida vs. Siniestros Incurridos por Rango Edad (Barras Horizontales Agrupadas)
# ------------------------------


def grafico_23():
    """
    Muestra la Prima Emitida vs. Siniestros Incurridos (Monto Reclamado) 
    por Rango de Edad para Contratos Individuales, usando barras horizontales agrupadas.
    """
    try:
        logger.debug(
            "G23 - Iniciando Prima vs Siniestros por Rango Edad (Barras Horizontales)")

        rangos_edad_definidos = [
            (0, 17, '0-17 años'), (18, 25, '18-25 años'), (26, 35, '26-35 años'),
            (36, 45, '36-45 años'), (46, 55, '46-55 años'), (56, 65, '56-65 años'),
            (66, 75, '66-75 años'), (76, 120, '76+ años')
        ]
        when_edad_clauses = [When(edad__gte=min_e, edad__lte=max_e, then=Value(lbl))
                             for min_e, max_e, lbl in rangos_edad_definidos]

        # 1. Prima Emitida por Rango de Edad (Contratos Individuales Activos)
        prima_por_edad_qs = (ContratoIndividual.objects
                             .filter(activo=True, afiliado__fecha_nacimiento__isnull=False, monto_total__gt=Decimal('0.00'))
                             .annotate(
                                 edad=ExtractYear(Now()) -
                                 ExtractYear('afiliado__fecha_nacimiento'),
                                 rango_edad_label=Case(
                                     *when_edad_clauses, default=Value('Otros'), output_field=CharField())
                             )
                             .exclude(rango_edad_label='Otros')
                             .values('rango_edad_label')
                             .annotate(total_prima_rango=Coalesce(Sum('monto_total'), Decimal('0.0')))
                             # Ordenar por el orden definido en 'rangos_edad_definidos' para el gráfico
                             .order_by(Case(*[When(rango_edad_label=label, then=Value(i)) for i, (_, _, label) in enumerate(rangos_edad_definidos)]))
                             )
        df_prima = pd.DataFrame(list(prima_por_edad_qs))
        if df_prima.empty:  # Asegurar columnas si está vacío
            df_prima = pd.DataFrame(
                columns=['rango_edad_label', 'total_prima_rango'])

        # 2. Siniestros Incurridos (Monto Reclamado) por Rango de Edad (de Contratos Individuales Activos)
        siniestros_por_edad_qs = (Reclamacion.objects
                                  .filter(
                                      contrato_individual__isnull=False,
                                      # Asegurar que el contrato del siniestro esté activo
                                      contrato_individual__activo=True,
                                      contrato_individual__afiliado__fecha_nacimiento__isnull=False,
                                      monto_reclamado__gt=Decimal('0.00')
                                  )
                                  .annotate(
                                      edad=ExtractYear(
                                          Now()) - ExtractYear('contrato_individual__afiliado__fecha_nacimiento'),
                                      rango_edad_label=Case(
                                          *when_edad_clauses, default=Value('Otros'), output_field=CharField())
                                  )
                                  .exclude(rango_edad_label='Otros')
                                  .values('rango_edad_label')
                                  .annotate(total_siniestro_rango=Coalesce(Sum('monto_reclamado'), Decimal('0.0')))
                                  .order_by(Case(*[When(rango_edad_label=label, then=Value(i)) for i, (_, _, label) in enumerate(rangos_edad_definidos)]))
                                  )
        df_siniestro = pd.DataFrame(list(siniestros_por_edad_qs))
        if df_siniestro.empty:
            df_siniestro = pd.DataFrame(
                columns=['rango_edad_label', 'total_siniestro_rango'])

        # 3. Combinar datos
        if df_prima.empty and df_siniestro.empty:
            return plot(generar_figura_sin_datos("No hay datos de primas ni siniestros por edad para G23"),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df_merged = pd.merge(df_prima, df_siniestro,
                             on='rango_edad_label', how='outer')
        df_merged[['total_prima_rango', 'total_siniestro_rango']] = df_merged[[
            'total_prima_rango', 'total_siniestro_rango']].fillna(Decimal('0.0'))

        # Asegurar el orden correcto de los rangos si el merge lo desordena
        # y convertir a tipo categórico para Plotly
        rango_order = [lbl for _, _, lbl in rangos_edad_definidos]
        df_merged['rango_edad_label'] = pd.Categorical(
            df_merged['rango_edad_label'], categories=rango_order, ordered=True
        )
        df_merged = df_merged.sort_values('rango_edad_label')
        df_merged = df_merged[(df_merged['total_prima_rango'] > 0) | (
            # Mostrar solo si hay alguna actividad
            df_merged['total_siniestro_rango'] > 0)]

        if df_merged.empty:
            return plot(generar_figura_sin_datos("No hay actividad significativa de primas o siniestros por edad para G23"),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Convertir a float para Plotly
        df_merged['total_prima_float'] = pd.to_numeric(
            df_merged['total_prima_rango'], errors='coerce').fillna(0.0)
        df_merged['total_siniestro_float'] = pd.to_numeric(
            df_merged['total_siniestro_rango'], errors='coerce').fillna(0.0)

        # 4. Crear gráfico de barras horizontales agrupadas
        fig = go.Figure()

        fig.add_trace(go.Bar(
            y=df_merged['rango_edad_label'],  # Rangos en el eje Y
            x=df_merged['total_prima_float'],  # Montos en el eje X
            name='Prima Emitida Total',
            orientation='h',
            marker_color=COLOR_PALETTE.get('success'),
            text=df_merged['total_prima_float'],
            texttemplate='$%{text:,.0f}',
            textposition='auto',  # Podría ser 'outside' si las barras son cortas
            hovertemplate="<b>Rango Edad: %{y}</b><br>Prima Emitida: $%{x:,.0f}<extra></extra>"
        ))

        fig.add_trace(go.Bar(
            y=df_merged['rango_edad_label'],
            x=df_merged['total_siniestro_float'],
            name='Siniestros Incurridos Totales',
            orientation='h',
            marker_color=COLOR_PALETTE.get('secondary'),
            text=df_merged['total_siniestro_float'],
            texttemplate='$%{text:,.0f}',
            textposition='auto',
            hovertemplate="<b>Rango Edad: %{y}</b><br>Siniestros Incurridos: $%{x:,.0f}<extra></extra>"
        ))

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Prima Emitida vs. Siniestros Incurridos por Rango de Edad (Cont. Individuales)', x=0.5)
        layout_grafico['yaxis'] = dict(
            title='Rango de Edad del Afiliado', type='category')  # Y-axis es ahora categórico
        layout_grafico['xaxis'] = dict(
            title='Monto Total (USD)', tickprefix='$', tickformat=',.0f')
        layout_grafico['barmode'] = 'group'
        layout_grafico['legend'] = dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        layout_grafico['height'] = max(
            # Altura dinámica
            400, len(df_merged['rango_edad_label'].unique()) * 50 + 150)
        # Margen izquierdo para labels de rango
        layout_grafico['margin'] = dict(t=80, b=50, l=120, r=30)
        fig.update_layout(**layout_grafico)

        logger.info(
            "G23 - Prima vs Siniestros por Rango Edad (Barras Horizontales) generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(
            f"Error G23 (Barras Horizontales Edad): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error al generar Gráfico 23 ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 24: Tendencia Anual Contratos
# ------------------------------


def grafico_24():
    try:
        data = (ContratoColectivo.objects
                .annotate(year=ExtractYear('fecha_emision'))
                .values('year')
                .annotate(total=Count('id'))
                .order_by('year'))  # Added order_by to the query

        if not data.exists():
            return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Convert QuerySet to list before DataFrame
        df = pd.DataFrame(list(data))

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['year'],
            y=df['total'],
            mode='lines+markers',
            line=dict(color=COLOR_PALETTE['secondary'])
        ))

        fig.update_layout(
            **BASE_LAYOUT,
            title=dict(text='Contratos Colectivos por Año', x=0.5),
            xaxis=dict(title='Año'),
            yaxis=dict(title='Contratos')
        )
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_24: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 25: Rendimiento de Intermediarios (Barras con Ejes Secundarios)
# ------------------------------


def grafico_25():  # Anteriormente Comisiones vs Número de Contratos (Scatter)
    """
    Muestra las Comisiones Totales Estimadas (barras, eje izquierdo) y el 
    Número Total de Contratos Activos (línea, eje derecho) por intermediario.
    Se muestran los Top N intermediarios por comisiones.
    """
    try:
        N_INTERMEDIARIOS = 15  # Mostrar los N principales por comisión
        logger.debug(
            f"G25 - Iniciando Rendimiento Intermediarios (Top {N_INTERMEDIARIOS})")

        data_qs = (Intermediario.objects
                   .filter(activo=True)
                   .annotate(
                       count_contratos_ind=Count('contratoindividual', filter=Q(
                           contratoindividual__activo=True), distinct=True),
                       count_contratos_col=Count('contratos_colectivos', filter=Q(
                           contratos_colectivos__activo=True), distinct=True),
                       comisiones_ind=Coalesce(Sum(
                           F('contratoindividual__monto_total') *
                           F('porcentaje_comision') / Decimal('100.0'),
                           filter=Q(contratoindividual__activo=True,
                                    contratoindividual__monto_total__isnull=False)
                       ), Value(Decimal('0.0')), output_field=DecimalField()),
                       comisiones_col=Coalesce(Sum(
                           F('contratos_colectivos__monto_total') *
                           F('porcentaje_comision') / Decimal('100.0'),
                           filter=Q(contratos_colectivos__activo=True,
                                    contratos_colectivos__monto_total__isnull=False)
                       ), Value(Decimal('0.0')), output_field=DecimalField())
                   )
                   .annotate(
                       total_contratos_intermediario=F(
                           'count_contratos_ind') + F('count_contratos_col'),
                       comision_total_intermediario=F(
                           'comisiones_ind') + F('comisiones_col')
                   )
                   .filter(Q(total_contratos_intermediario__gt=0) | Q(comision_total_intermediario__gt=Decimal('0.005')))
                   # Tomar el Top N
                   .order_by('-comision_total_intermediario')[:N_INTERMEDIARIOS]
                   )

        if not data_qs:
            return plot(generar_figura_sin_datos("No hay datos de actividad de intermediarios para G25"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df_data = []
        for d in data_qs:
            df_data.append({
                'nombre_intermediario': d.nombre_completo,
                'comisiones': float(d.comision_total_intermediario or 0),
                'contratos': int(d.total_contratos_intermediario or 0)
            })

        df = pd.DataFrame(df_data)
        # No es necesario filtrar más si ya se hizo en la query y se tomó el TOP N

        if df.empty:
            return plot(generar_figura_sin_datos("No hay datos válidos tras procesar para Gráfico 25"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Crear figura con ejes Y secundarios
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Barras para Comisiones
        fig.add_trace(go.Bar(
            x=df['nombre_intermediario'],
            y=df['comisiones'],
            name='Comisiones Estimadas',
            marker_color=COLOR_PALETTE.get('primary'),
            text=df['comisiones'],
            texttemplate='$%{text:,.0f}',
            textposition='auto',  # O 'outside'
            hovertemplate="<b>%{x}</b><br>Comisiones: $%{y:,.0f}<extra></extra>"
        ), secondary_y=False)

        # Línea para Número de Contratos
        fig.add_trace(go.Scatter(
            x=df['nombre_intermediario'],
            y=df['contratos'],
            name='N° Contratos Activos',
            mode='lines+markers',
            line=dict(color=COLOR_PALETTE.get('success'), width=3),
            marker=dict(size=8, symbol='circle'),
            hovertemplate="<b>%{x}</b><br>N° Contratos: %{y}<extra></extra>"
        ), secondary_y=True)

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text=f'Top {N_INTERMEDIARIOS} Intermediarios: Comisiones y N° Contratos', x=0.5)
        layout_grafico['xaxis'] = dict(
            title='Intermediario', type='category', tickangle=45)
        layout_grafico['yaxis'] = dict(
            title='Comisiones Totales Estimadas (USD)',
            tickprefix='$',
            side='left',
            showgrid=True,  # Grid para el eje principal
            gridcolor=COLOR_PALETTE.get('light')
        )
        layout_grafico['yaxis2'] = dict(
            title='Número de Contratos Activos',
            side='right',
            overlaying='y',
            showgrid=False,  # No mostrar grid para el secundario para evitar clutter
            rangemode='tozero'  # Asegurar que el eje secundario empiece en cero
        )
        layout_grafico['legend'] = dict(
            orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5)  # Ajustar leyenda
        layout_grafico['margin'] = dict(
            t=60, b=150, l=70, r=70)  # Ajustar márgenes
        fig.update_layout(**layout_grafico)

        logger.info(
            "G25 - Rendimiento Intermediarios (Barras Ejes Secundarios) generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(
            f"Error G25 (Barras Ejes Secundarios): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error al generar Gráfico 25 ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 26 (Nuevo): Top N Reclamaciones por Monto (Aprobadas/Pagadas)
# ------------------------------


def grafico_26():
    """Muestra las N reclamaciones más costosas (estados Aprobada o Pagada)."""
    try:
        N = 15
        top_reclamaciones = (Reclamacion.objects.filter(estado__in=['APROBADA', 'PAGADA'], monto_reclamado__isnull=False).select_related(
            'contrato_individual', 'contrato_colectivo').order_by('-monto_reclamado')[:N])
        if not top_reclamaciones:
            return plot(generar_figura_sin_datos("No hay reclamaciones Aprob/Pagadas"), output_type='div', config=GRAPH_CONFIG)
        labels = []
        montos = []
        for rec in top_reclamaciones:
            contrato_str = f"CI: {rec.contrato_individual.numero_contrato}" if rec.contrato_individual else (
                f"CC: {rec.contrato_colectivo.numero_contrato}" if rec.contrato_colectivo else "")
            labels.append(f"ID: {rec.pk} ({contrato_str})")
            montos.append(float(rec.monto_reclamado))
        fig = go.Figure(data=[go.Bar(y=labels, x=montos, orientation='h', marker_color=COLOR_PALETTE.get(
            'danger'), text=[f"${m:,.0f}" for m in montos], textposition='auto', hoverinfo='x+y')])
        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text=f'Top {N} Reclamaciones (Aprob/Pagadas) por Monto', x=0.5)
        layout_grafico['xaxis'] = dict(
            title='Monto Reclamado (USD)', tickprefix='$')
        layout_grafico['yaxis'] = dict(
            title='Reclamación', autorange="reversed")
        layout_grafico['margin'] = dict(l=250, r=30, t=50, b=40)
        fig.update_layout(**layout_grafico)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error G26(nuevo): {e}", exc_info=True)
        return plot(generar_figura_sin_datos("Error G26"), output_type='div', config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 27: Tiempo por Tipo Reclamación
# ------------------------------


def grafico_27():
    """Muestra el tiempo promedio de resolución en días por tipo de reclamación."""
    try:
        # Calcular duración promedio por tipo
        data_qs = (Reclamacion.objects
                   .filter(fecha_cierre_reclamo__isnull=False, fecha_reclamo__isnull=False)
                   .annotate(
                       duracion=Case(
                           When(fecha_cierre_reclamo__gte=F('fecha_reclamo'),
                                then=ExpressionWrapper(F('fecha_cierre_reclamo') - F('fecha_reclamo'), output_field=DurationField())),
                           default=Value(None)  # Manejar fechas inconsistentes
                       )
                   )
                   .filter(duracion__isnull=False)  # Solo duraciones válidas
                   .values('tipo_reclamacion')
                   # Promedio como timedelta
                   .annotate(tiempo_promedio_td=Avg('duracion'))
                   # Ordenar por duración promedio descendente
                   .order_by('-tiempo_promedio_td'))

        if not data_qs:
            return plot(generar_figura_sin_datos("No hay datos de resolución para mostrar por tipo"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(list(data_qs))
        # Convertir timedelta a días (float)
        df['dias_promedio'] = df['tiempo_promedio_td'].apply(
            lambda x: x.total_seconds() / (24 * 3600) if pd.notnull(x) else 0)
        # Mapear tipo a label
        tipo_map = dict(CommonChoices.TIPO_RECLAMACION)
        df['tipo_label'] = df['tipo_reclamacion'].map(
            tipo_map).fillna(df['tipo_reclamacion'])

        # Crear gráfico de barras
        fig = px.bar(
            df,
            x='tipo_label',
            y='dias_promedio',
            labels={'tipo_label': 'Tipo de Reclamación',
                    'dias_promedio': 'Tiempo Promedio Resolución (Días)'},
            text='dias_promedio',
            color='dias_promedio',
            # Escala de rojo (más días = más rojo)
            color_continuous_scale=px.colors.sequential.Reds
        )

        # Formato de texto
        fig.update_traces(texttemplate='%{text:.1f}d', textposition='outside')

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Tiempo Promedio de Resolución por Tipo de Reclamación', x=0.5)
        layout_grafico['xaxis'] = dict(
            title='Tipo de Reclamación', tickangle=45)
        layout_grafico['yaxis'] = dict(title='Tiempo Promedio (Días)')
        fig.update_layout(**layout_grafico)

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_27: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos("Error al generar Gráfico 27"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 28: Reclamaciones por Tipo y Estado
# ------------------------------


def grafico_28():
    try:
        data = (Reclamacion.objects
                .values('tipo_reclamacion', 'estado')
                .annotate(total=Count('id')))

        if not data.exists():
            return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(data)
        pivot = df.pivot_table(index='tipo_reclamacion',
                               columns='estado', values='total', fill_value=0)

        fig = go.Figure(go.Heatmap(
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            z=pivot.values.tolist(),
            colorscale='Viridis',
            text=pivot.values,
            texttemplate="%{text}"
        ))

        fig.update_layout(
            **BASE_LAYOUT,
            title=dict(text='Reclamaciones por Tipo y Estado', x=0.5),
            xaxis=dict(title='Estado'),
            yaxis=dict(title='Tipo de Reclamación')
        )
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_28: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 29 (Nuevo): Antigüedad Contrato vs. Monto Prom. Reclamado
# ------------------------------


def grafico_29():
    """Analiza si la antigüedad del contrato influye en el monto promedio reclamado."""
    try:
        hoy = date.today()
        rangos_edad = [(0, 17, '0-17'), (18, 25, '18-25'), (26, 35, '26-35'),
                       (36, 45, '36-45'), (46, 55, '46-55'), (56, 65, '56-65'), (66, 120, '66+')]
        when_edad = [When(edad__gte=min_e, edad__lte=max_e, then=Value(lbl))
                     for min_e, max_e, lbl in rangos_edad]
        contratos_con_antiguedad = (ContratoIndividual.objects.filter(fecha_inicio_vigencia__isnull=False).annotate(antiguedad_anos=Case(When(
            fecha_inicio_vigencia__lte=hoy, then=ExtractYear(Value(hoy)) - ExtractYear('fecha_inicio_vigencia')), default=Value(0), output_field=IntegerField())).filter(antiguedad_anos__gte=0))
        avg_monto_reclamado_subquery = (Reclamacion.objects.filter(contrato_individual=OuterRef('pk'), monto_reclamado__isnull=False, monto_reclamado__gt=0).values(
            'contrato_individual').annotate(avg_monto=Avg('monto_reclamado')).values('avg_monto')[:1])
        data_qs = (contratos_con_antiguedad.annotate(monto_prom_reclamado=Subquery(avg_monto_reclamado_subquery, output_field=DecimalField())).filter(
            monto_prom_reclamado__isnull=False).values('antiguedad_anos').annotate(monto_promedio_final=Avg('monto_prom_reclamado')).order_by('antiguedad_anos'))
        if not data_qs:
            return plot(generar_figura_sin_datos("No hay datos suficientes"), output_type='div', config=GRAPH_CONFIG)
        df = pd.DataFrame(list(data_qs))
        df['monto_prom_float'] = pd.to_numeric(
            df['monto_promedio_final'], errors='coerce').fillna(0.0)
        df['antiguedad_anos'] = pd.to_numeric(
            df['antiguedad_anos'], errors='coerce').fillna(0).astype(int)
        df = df.sort_values('antiguedad_anos')
        if df.empty:
            return plot(generar_figura_sin_datos("No hay datos válidos"), output_type='div', config=GRAPH_CONFIG)
        fig = px.line(df, x='antiguedad_anos', y='monto_prom_float', labels={
                      'antiguedad_anos': 'Antigüedad Contrato (Años)', 'monto_prom_float': 'Monto Prom. Reclamado (USD)'}, markers=True, title="Monto Prom. Reclamado vs. Antigüedad Contrato (Ind.)")
        fig.update_traces(line=dict(color=COLOR_PALETTE.get(
            'success'), width=2), marker=dict(size=7))
        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['xaxis'] = dict(
            title='Antigüedad Contrato (Años)', dtick=1)
        layout_grafico['yaxis'] = dict(
            title='Monto Prom. Reclamado (USD)', tickprefix='$')
        layout_grafico['hovermode'] = 'x unified'
        layout_grafico['margin'] = dict(t=60, l=60, r=30, b=50)
        fig.update_layout(**layout_grafico)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error G29(nuevo): {e}", exc_info=True)
        return plot(generar_figura_sin_datos("Error G29"), output_type='div', config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 30: Distribución de los montos de siniestros incurridos
# ------------------------------


def grafico_30():
    """Muestra la distribución de los montos de siniestros incurridos (reclamados)."""
    try:
        # Obtener montos reclamados válidos
        montos_qs = (Reclamacion.objects
                     .filter(activo=True, monto_reclamado__isnull=False, monto_reclamado__gt=0)
                     .values_list('monto_reclamado', flat=True))

        if not montos_qs:
            return plot(generar_figura_sin_datos("No hay montos de siniestros para analizar"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        montos = [float(m) for m in montos_qs]

        if not montos:  # Doble chequeo
            return plot(generar_figura_sin_datos("No hay montos válidos para mostrar"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Crear Histograma
        fig = go.Figure(data=[go.Histogram(
            x=montos,
            marker_color=COLOR_PALETTE.get('secondary'),
            # nbinsx=30 # O definir tamaño de bin: xbins=dict(start=0, end=max(montos)*1.1, size=5000)
            autobinx=True  # Dejar que Plotly decida los bins
        )])

        # Layout
        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Distribución de Montos de Siniestros Incurridos', x=0.5)
        layout_grafico['xaxis'] = dict(
            title='Monto Siniestro Incurrido (USD)', tickprefix='$')
        layout_grafico['yaxis'] = dict(title='Cantidad de Siniestros')
        layout_grafico['bargap'] = 0.05  # Espacio entre barras
        fig.update_layout(**layout_grafico)

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(
            f"Error gráfico_30 (Reemplazo Distribución Siniestros): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos("Error al generar distribución de siniestros"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


# ------------------------------
# Gráfico 31: Tendencia Pagos Mensuales (Optimizado)
# ------------------------------


logger_grafica_31 = logging.getLogger("myapp.graficas.grafico_31")


def grafico_31():
    """
    Muestra la distribución de la cantidad y monto total de pagos 
    por forma de pago en los últimos N meses.
    """
    logger_grafica_31.info(
        "==================== grafico_31: INICIO - Distribución de Pagos por Forma ====================")
    try:
        N_MESES_ATRAS = 6  # Analizar los últimos 6 meses
        hoy = django_timezone.now().date()  # Usar date() ya que fecha_pago es DateField
        fecha_inicio_periodo = hoy - relativedelta(months=N_MESES_ATRAS)
        # Asegurar que sea el primer día de ese mes para una comparación de mes completo
        fecha_inicio_periodo = fecha_inicio_periodo.replace(day=1)

        logger_grafica_31.debug(
            f"Periodo para gráfico 31: Desde {fecha_inicio_periodo} hasta {hoy}")

        pagos_periodo_qs = (
            Pago.objects.filter(
                activo=True,
                fecha_pago__gte=fecha_inicio_periodo,
                fecha_pago__lte=hoy  # Incluir pagos hasta el día de hoy
            )
            .values('forma_pago')
            .annotate(
                cantidad_pagos=Count('id'),
                monto_total_pagado=Coalesce(Sum('monto_pago'), Value(
                    Decimal('0.0')), output_field=DecimalField())
            )
            # Ordenar por monto para destacar las más usadas
            .order_by('-monto_total_pagado')
        )

        if not pagos_periodo_qs.exists():
            logger_grafica_31.info(
                "No se encontraron pagos en el periodo definido para el gráfico 31.")
            return plot(generar_figura_sin_datos_plotly(f"No hay datos de pagos en los últimos {N_MESES_ATRAS} meses."),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df_data = []
        # Asumo que estas son las formas de pago relevantes
        forma_pago_map = dict(CommonChoices.FORMA_PAGO_RECLAMACION)

        for item in pagos_periodo_qs:
            forma_pago_label = forma_pago_map.get(
                item['forma_pago'], item['forma_pago'] or "Desconocida")
            df_data.append({
                'Forma de Pago': forma_pago_label,
                'Cantidad de Pagos': item['cantidad_pagos'],
                # Convertir a float para Plotly
                'Monto Total Pagado': float(item['monto_total_pagado'])
            })

        df = pd.DataFrame(df_data)

        if df.empty:  # Doble chequeo
            logger_grafica_31.info(
                "DataFrame vacío después de procesar datos para gráfico 31.")
            return plot(generar_figura_sin_datos_plotly("No hay datos válidos para mostrar."),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Crear gráfico de barras agrupadas (o podrías hacer dos gráficos separados o un pie)
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Barras para Monto Total Pagado
        fig.add_trace(go.Bar(
            x=df['Forma de Pago'],
            y=df['Monto Total Pagado'],
            name='Monto Total Pagado ($)',
            marker_color=COLOR_PALETTE.get('primary'),
            text=df['Monto Total Pagado'],
            texttemplate='$%{text:,.0f}',
            textposition='auto',
            hovertemplate="<b>%{x}</b><br>Monto Total: $%{y:,.0f}<extra></extra>"
        ), secondary_y=False)

        # Línea para Cantidad de Pagos
        fig.add_trace(go.Scatter(
            x=df['Forma de Pago'],
            y=df['Cantidad de Pagos'],
            name='Cantidad de Pagos',
            mode='lines+markers',
            line=dict(color=COLOR_PALETTE.get('success'), width=2),
            marker=dict(size=7),
            hovertemplate="<b>%{x}</b><br>Cantidad: %{y}<extra></extra>"
        ), secondary_y=True)

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text=f'Distribución de Pagos por Forma (Últimos {N_MESES_ATRAS} Meses)', x=0.5)
        layout_grafico['xaxis'] = dict(title='Forma de Pago', type='category')
        layout_grafico['yaxis'] = dict(
            title='Monto Total Pagado ($)', side='left', tickprefix='$')
        layout_grafico['yaxis2'] = dict(
            title='Cantidad de Pagos', side='right', overlaying='y', showgrid=False, rangemode='tozero')
        layout_grafico['legend'] = dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        # Ajustar márgenes para los dos ejes Y
        layout_grafico['margin'] = dict(t=80, b=80, l=70, r=80)
        fig.update_layout(**layout_grafico)

        logger_grafica_31.info(
            "==================== grafico_31: FIN - Gráfico generado ====================")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger_grafica_31.error(
            f"Error EXCEPCIONAL en grafico_31: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos_plotly(f"Error al generar Gráfico 31 ({type(e).__name__})"),
                    output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 32: Comparación de Tarifas
# ------------------------------


def grafico_32():
    try:
        data = (Tarifa.objects
                .values('ramo')
                .annotate(
                    promedio=Avg('monto_anual'),
                    maximo=Max('monto_anual'),
                    minimo=Min('monto_anual')
                ))

        if not data.exists():
            return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(data)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df['ramo'],
            y=df['promedio'],
            name='Promedio',
            marker_color=COLOR_PALETTE['primary']
        ))
        fig.add_trace(go.Scatter(
            x=df['ramo'],
            y=df['maximo'],
            mode='markers',
            name='Máximo',
            marker=dict(color=COLOR_PALETTE['secondary'], size=10)
        ))
        fig.add_trace(go.Scatter(
            x=df['ramo'],
            y=df['minimo'],
            mode='markers',
            name='Mínimo',
            marker=dict(color=COLOR_PALETTE['success'], size=10)
        ))

        fig.update_layout(
            **BASE_LAYOUT,
            title=dict(text='Comparación de Tarifas por Ramo', x=0.5),
            xaxis=dict(title='Ramo'),
            yaxis=dict(title='Monto Anual', tickprefix='$'),
            barmode='group'
        )
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_32: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 33: Impacto Rango Etario
# ------------------------------


def grafico_33():
    try:
        data = (ContratoIndividual.objects
                .select_related('afiliado')
                .annotate(
                    edad=ExtractYear(Now()) -
                    ExtractYear('afiliado__fecha_nacimiento'),
                    rango_etario=Case(
                        *[When(edad__gte=min, edad__lt=max, then=Value(f"{min}-{max}"))
                          for min, max in [(18, 25), (25, 35), (35, 45), (45, 55), (55, 65)]],
                        output_field=CharField()
                    )
                )
                .values('rango_etario', 'ramo')
                .annotate(total=Sum('monto_total')))

        if not data.exists():
            return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(data)
        pivot = df.pivot_table(
            index='rango_etario', columns='ramo', values='total', aggfunc='sum', fill_value=0)

        fig = go.Figure(go.Heatmap(
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            z=pivot.values.tolist(),
            colorscale='Viridis',
            texttemplate="%{z:$,.0f}"
        ))

        fig.update_layout(
            **BASE_LAYOUT,
            title=dict(text='Distribución Montos por Edad y Ramo', x=0.5),
            xaxis=dict(title='Ramo'),
            yaxis=dict(title='Rango Etario'),
            height=500
        )
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_33: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 34 (Nuevo): Rentabilidad Estimada por Ramo
# ------------------------------


def grafico_34():
    """Muestra la Rentabilidad Estimada (Ingresos Contratos - Egresos Reclamaciones) por Ramo."""
    try:
        logger.debug("G34 - Iniciando Rentabilidad Estimada por Ramo")
        # 1. Calcular Monto Total Contratado por Ramo
        monto_contratado = collections.defaultdict(Decimal)
        contratos_ind_qs = (ContratoIndividual.objects
                            .values('ramo')
                            .annotate(total_contratado_ramo=Sum('monto_total')))
        for item in contratos_ind_qs:
            if item['ramo']:
                monto_contratado[item['ramo']
                                 ] += item['total_contratado_ramo'] or Decimal('0.0')

        contratos_col_qs = (ContratoColectivo.objects
                            .values('ramo')
                            .annotate(total_contratado_ramo=Sum('monto_total')))
        for item in contratos_col_qs:
            if item['ramo']:
                monto_contratado[item['ramo']
                                 ] += item['total_contratado_ramo'] or Decimal('0.0')

        # 2. Calcular Monto Total Reclamado por Ramo
        monto_reclamado = collections.defaultdict(Decimal)
        reclamaciones_ind_qs = (Reclamacion.objects
                                .filter(contrato_individual__isnull=False, contrato_individual__ramo__isnull=False)
                                .values('contrato_individual__ramo')
                                .annotate(total_reclamado_ramo=Sum('monto_reclamado')))
        for item in reclamaciones_ind_qs:
            if item['contrato_individual__ramo']:
                monto_reclamado[item['contrato_individual__ramo']
                                ] += item['total_reclamado_ramo'] or Decimal('0.0')

        reclamaciones_col_qs = (Reclamacion.objects
                                .filter(contrato_colectivo__isnull=False, contrato_colectivo__ramo__isnull=False)
                                .values('contrato_colectivo__ramo')
                                .annotate(total_reclamado_ramo=Sum('monto_reclamado')))
        for item in reclamaciones_col_qs:
            if item['contrato_colectivo__ramo']:
                monto_reclamado[item['contrato_colectivo__ramo']
                                ] += item['total_reclamado_ramo'] or Decimal('0.0')

        # 3. Combinar datos y calcular rentabilidad
        resultados = []
        todos_ramos = set(monto_contratado.keys()) | set(
            monto_reclamado.keys())
        ramo_map = dict(CommonChoices.RAMO)

        for ramo_code in todos_ramos:
            if not ramo_code:
                logger.warning(
                    f"G34 - Se encontró un ramo_code 'None' o vacío. Omitiendo.")
                continue

            contratado = monto_contratado.get(ramo_code, Decimal('0.0'))
            reclamado = monto_reclamado.get(ramo_code, Decimal('0.0'))
            rentabilidad = contratado - reclamado

            resultados.append({
                'ramo_label': ramo_map.get(ramo_code, ramo_code),
                'rentabilidad': float(rentabilidad.quantize(Decimal('0.01'))),
                # Para tooltip
                'contratado_tooltip': float(contratado.quantize(Decimal('0.01'))),
                # Para tooltip
                'reclamado_tooltip': float(reclamado.quantize(Decimal('0.01')))
            })

        if not resultados:
            return plot(generar_figura_sin_datos("No hay datos para rentabilidad por ramo"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(resultados).sort_values(
            'rentabilidad', ascending=False)
        # Opcional: filtrar ramos con rentabilidad cero si no aportan
        df = df[df['rentabilidad'] != 0.0]

        if df.empty:
            return plot(generar_figura_sin_datos("No hay ramos con rentabilidad no nula"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # 4. Crear gráfico de barras
        fig = px.bar(df,
                     x='ramo_label',
                     y='rentabilidad',
                     labels={'ramo_label': 'Ramo',
                             'rentabilidad': 'Rentabilidad Estimada (USD)'},
                     text='rentabilidad',  # Mostrará el valor de rentabilidad en la barra
                     color='rentabilidad',  # Colorear barras según el valor de rentabilidad
                     color_continuous_scale=px.colors.diverging.Portland,  # Escala de color divergente
                     # Datos adicionales para hover
                     custom_data=['contratado_tooltip', 'reclamado_tooltip']
                     )

        fig.update_traces(
            texttemplate='$%{text:,.0f}',
            textposition='auto',
            hovertemplate=(
                "<b>Ramo: %{x}</b><br>"
                "Rentabilidad Estimada: $%{y:,.0f}<br>"
                "Prima Total: $%{customdata[0]:,.0f}<br>"
                "Siniestros Totales: $%{customdata[1]:,.0f}"
                "<extra></extra>"
            )
        )

        # Aplicar layout
        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Rentabilidad Estimada por Ramo', x=0.5)
        layout_grafico['xaxis'] = dict(
            title='Ramo', type='category', tickangle=45)
        layout_grafico['yaxis'] = dict(
            title='Rentabilidad Estimada (USD)', tickprefix='$')
        layout_grafico['margin'] = dict(
            t=50, b=100, l=70, r=30)  # Ajustar márgenes

        # --- MODIFICACIÓN PARA OCULTAR LA LEYENDA DE LA ESCALA DE COLOR ---
        layout_grafico['coloraxis_showscale'] = False
        # --- FIN DE LA MODIFICACIÓN ---

        fig.update_layout(**layout_grafico)

        logger.info("G34 - Rentabilidad Estimada por Ramo generada.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error G34 (Rentabilidad Ramo): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error al generar Gráfico 34 ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 35: Productividad de Intermediarios (Bubble Chart)
# ------------------------------


def grafico_35():  # Anteriormente Rentabilidad de Intermediarios (Scatter)
    """
    Muestra la relación entre Número de Contratos (eje X), Comisiones Totales (eje Y),
    y la Comisión Promedio por Contrato (tamaño de la burbuja) para cada intermediario.
    """
    try:
        N_INTERMEDIARIOS = 25  # Mostrar hasta N intermediarios
        logger.debug(
            f"G35 - Iniciando Productividad Intermediarios (Bubble Chart Top {N_INTERMEDIARIOS})")

        data_qs = (Intermediario.objects
                   .filter(activo=True)
                   .annotate(
                       count_contratos_ind=Count('contratoindividual', filter=Q(
                           contratoindividual__activo=True), distinct=True),
                       count_contratos_col=Count('contratos_colectivos', filter=Q(
                           contratos_colectivos__activo=True), distinct=True),
                       comisiones_ind=Coalesce(Sum(
                           F('contratoindividual__monto_total') *
                           F('porcentaje_comision') / Decimal('100.0'),
                           filter=Q(contratoindividual__activo=True,
                                    contratoindividual__monto_total__isnull=False)
                       ), Value(Decimal('0.0')), output_field=DecimalField()),
                       comisiones_col=Coalesce(Sum(
                           F('contratos_colectivos__monto_total') *
                           F('porcentaje_comision') / Decimal('100.0'),
                           filter=Q(contratos_colectivos__activo=True,
                                    contratos_colectivos__monto_total__isnull=False)
                       ), Value(Decimal('0.0')), output_field=DecimalField())
                   )
                   .annotate(
                       total_contratos_intermediario=F(
                           'count_contratos_ind') + F('count_contratos_col'),
                       comision_total_intermediario=F(
                           'comisiones_ind') + F('comisiones_col')
                   )
                   .annotate(
                       comision_promedio_por_contrato=Case(
                           When(total_contratos_intermediario__gt=0,
                                then=ExpressionWrapper(F('comision_total_intermediario') / F('total_contratos_intermediario'), output_field=DecimalField())),
                           default=Value(Decimal('0.0')),
                           output_field=DecimalField()
                       )
                   )
                   .filter(Q(total_contratos_intermediario__gt=0) | Q(comision_total_intermediario__gt=Decimal('0.005')))
                   .order_by('-comision_total_intermediario')[:N_INTERMEDIARIOS]
                   )

        if not data_qs.exists():
            return plot(generar_figura_sin_datos("No hay datos de actividad de intermediarios para G35"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df_data = []
        for d in data_qs:
            df_data.append({
                'nombre_intermediario': d.nombre_completo,
                'comisiones_totales': float(d.comision_total_intermediario or 0),
                'n_contratos': int(d.total_contratos_intermediario or 0),
                'comision_prom_contrato': float(d.comision_promedio_por_contrato or 0)
            })

        df = pd.DataFrame(df_data)
        # Para que la comision_prom_contrato tenga sentido y evitar división por cero visual
        df = df[df['n_contratos'] > 0]

        if df.empty:
            return plot(generar_figura_sin_datos("No hay datos válidos tras procesar para Gráfico 35"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Crear Bubble Chart
        fig = px.scatter(
            df,
            x="n_contratos",
            y="comisiones_totales",
            size="comision_prom_contrato",  # Tamaño de la burbuja
            # Color por intermediario (si no son demasiados) o quitar color
            color="nombre_intermediario",
            hover_name="nombre_intermediario",  # Nombre al pasar el mouse
            size_max=40,  # Tamaño máximo de burbuja
            labels={
                "n_contratos": "Número de Contratos Activos",
                "comisiones_totales": "Comisiones Totales Estimadas (USD)",
                "comision_prom_contrato": "Comisión Promedio por Contrato (USD)"
            },
            title=f"Productividad de Intermediarios (Top {N_INTERMEDIARIOS} por Comisión)"
        )

        fig.update_traces(
            hovertemplate=(
                "<b>%{hovertext}</b><br><br>"
                "N° Contratos: %{x}<br>"
                "Comisiones Totales: $%{y:,.0f}<br>"
                # Asumiendo que size mapea directo al valor
                "Comisión Prom./Contrato: $%{marker.size:,.0f}"
                "<extra></extra>"
            )
        )

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['xaxis_title'] = 'Número de Contratos Activos'
        layout_grafico['yaxis_title'] = 'Comisiones Totales Estimadas (USD)'
        layout_grafico['yaxis_tickprefix'] = '$'
        layout_grafico['yaxis_tickformat'] = ',.0f'
        layout_grafico['legend_title_text'] = 'Intermediario'
        # layout_grafico['showlegend'] = False # Considerar si hay demasiados intermediarios
        layout_grafico['height'] = 500
        layout_grafico['margin'] = dict(t=60, b=50, l=70, r=30)
        fig.update_layout(**layout_grafico)

        logger.info(
            "G35 - Productividad Intermediarios (Bubble Chart) generada.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error G35 (Bubble Chart): {str(e)}", exc_info=True)
        # ------------------------------
        return plot(generar_figura_sin_datos(f"Error al generar Gráfico 35 ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# Gráfico 36: Estados de Facturación
# ------------------------------


def grafico_36():
    """Muestra el monto total facturado y el saldo pendiente por estado de factura."""
    try:
        logger.debug("G36 - Iniciando Estados de Facturación")

        # Subconsulta para obtener el total pagado por cada factura
        total_pagado_por_factura_subquery = Subquery(
            # Pagos activos de esta factura
            Pago.objects.filter(factura_id=OuterRef('pk'), activo=True)
            .values('factura_id')  # Agrupar por factura
            .annotate(total_pagado_factura=Sum('monto_pago'))
            .values('total_pagado_factura')[:1],  # Tomar el resultado
            output_field=DecimalField()
        )

        # Anotar cada factura con su total pagado y calcular el saldo
        facturas_con_saldo = (Factura.objects
                              .filter(activo=True)  # Solo facturas activas
                              .annotate(
                                  total_pagado_real=Coalesce(
                                      total_pagado_por_factura_subquery, Value(Decimal('0.0')))
                              )
                              .annotate(
                                  saldo_calculado_factura=ExpressionWrapper(
                                      F('monto') - F('total_pagado_real'), output_field=DecimalField()
                                  )
                              )
                              )

        # Agrupar por el 'estatus_factura' (que se actualiza en Factura.save())
        data_agrupada_qs = (facturas_con_saldo
                            # Usar el estatus_factura del modelo
                            .values('estatus_factura')
                            .annotate(
                                # Suma de los montos originales de las facturas
                                monto_total_facturado=Sum('monto'),
                                # Suma de los saldos calculados
                                monto_total_saldo_pendiente=Sum(
                                    'saldo_calculado_factura')
                            )
                            .order_by('estatus_factura')
                            )

        if not data_agrupada_qs.exists():
            return plot(generar_figura_sin_datos("No hay datos de facturación"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(list(data_agrupada_qs))

        # Mapear estatus a labels más amigables si es necesario (usando el de CommonChoices)
        # Convertir tupla de tuplas a dict
        estatus_map = {key: val for key, val in CommonChoices.ESTATUS_FACTURA}
        df['estado_label'] = df['estatus_factura'].map(
            estatus_map).fillna(df['estatus_factura'])

        # Convertir a float para Plotly
        df['monto_total_facturado'] = pd.to_numeric(
            df['monto_total_facturado'], errors='coerce').fillna(0.0)
        df['monto_total_saldo_pendiente'] = pd.to_numeric(
            df['monto_total_saldo_pendiente'], errors='coerce').fillna(0.0)

        # Asegurar que el saldo pendiente no sea negativo (podría pasar por ajustes o errores)
        df['monto_total_saldo_pendiente'] = df['monto_total_saldo_pendiente'].clip(
            lower=0)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df['estado_label'],
            y=df['monto_total_facturado'],
            name='Total Facturado',
            marker_color=COLOR_PALETTE.get('primary'),
            text=df['monto_total_facturado'], texttemplate='$%{text:,.0f}', textposition='auto',
            hovertemplate="<b>Estado: %{x}</b><br>Total Facturado: $%{y:,.0f}<extra></extra>"
        ))
        fig.add_trace(go.Bar(
            x=df['estado_label'],
            y=df['monto_total_saldo_pendiente'],
            name='Saldo Pendiente',
            marker_color=COLOR_PALETTE.get('secondary'),
            text=df['monto_total_saldo_pendiente'], texttemplate='$%{text:,.0f}', textposition='auto',
            hovertemplate="<b>Estado: %{x}</b><br>Saldo Pendiente: $%{y:,.0f}<extra></extra>"
        ))

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Resumen del Estado de Facturación', x=0.5)
        layout_grafico['xaxis'] = dict(
            title='Estado de la Factura', type='category')
        layout_grafico['yaxis'] = dict(
            title='Monto Total (USD)', tickprefix='$')
        layout_grafico['barmode'] = 'group'  # Barras agrupadas
        layout_grafico['legend'] = dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        fig.update_layout(**layout_grafico)

        logger.info("G36 - Estados de Facturación generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error G36: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error al generar Gráfico 36 ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 37: Ratio de Siniestralidad por Ramo (VISUALMENTE CAPEADO AL 100%)
# ------------------------------


def grafico_37():
    """
    Calcula y muestra el ratio de siniestralidad (Monto Reclamado / Monto Contratado) por Ramo.
    La altura de la barra y el texto en la barra se capean visualmente al 100%.
    El tooltip muestra el ratio real calculado y los montos absolutos.
    """
    try:
        logger.debug(
            "G37 - Iniciando Ratio Siniestralidad por Ramo (Visual Capeado 100%)")

        # 1. Calcular Monto Total Contratado por Ramo
        monto_contratado = collections.defaultdict(Decimal)
        contratos_ind_qs = (ContratoIndividual.objects
                            .values('ramo')
                            .annotate(total_contratado_ramo=Sum('monto_total')))
        for item in contratos_ind_qs:
            if item['ramo']:  # Solo procesar si el ramo no es None
                monto_contratado[item['ramo']
                                 ] += item['total_contratado_ramo'] or Decimal('0.0')

        contratos_col_qs = (ContratoColectivo.objects
                            .values('ramo')
                            .annotate(total_contratado_ramo=Sum('monto_total')))
        for item in contratos_col_qs:
            if item['ramo']:
                monto_contratado[item['ramo']
                                 ] += item['total_contratado_ramo'] or Decimal('0.0')

        # 2. Calcular Monto Total Reclamado por Ramo
        monto_reclamado = collections.defaultdict(Decimal)
        reclamaciones_ind_qs = (Reclamacion.objects
                                .filter(contrato_individual__isnull=False, contrato_individual__ramo__isnull=False)
                                .values('contrato_individual__ramo')
                                .annotate(total_reclamado_ramo=Sum('monto_reclamado')))
        for item in reclamaciones_ind_qs:
            if item['contrato_individual__ramo']:
                monto_reclamado[item['contrato_individual__ramo']
                                ] += item['total_reclamado_ramo'] or Decimal('0.0')

        reclamaciones_col_qs = (Reclamacion.objects
                                .filter(contrato_colectivo__isnull=False, contrato_colectivo__ramo__isnull=False)
                                .values('contrato_colectivo__ramo')
                                .annotate(total_reclamado_ramo=Sum('monto_reclamado')))
        for item in reclamaciones_col_qs:
            if item['contrato_colectivo__ramo']:
                monto_reclamado[item['contrato_colectivo__ramo']
                                ] += item['total_reclamado_ramo'] or Decimal('0.0')

        # 3. Combinar datos y calcular ratio
        resultados = []
        todos_ramos = set(monto_contratado.keys()) | set(
            monto_reclamado.keys())
        ramo_map = dict(CommonChoices.RAMO)
        # Límite visual para la altura de la barra Y el texto
        RATIO_CAP_VISUAL = Decimal('100.0')

        for ramo_code in todos_ramos:
            if not ramo_code:  # Omitir si el ramo es None o vacío
                logger.warning(
                    f"G37 - Se encontró un ramo_code 'None' o vacío. Omitiendo.")
                continue

            contratado = monto_contratado.get(ramo_code, Decimal('0.0'))
            reclamado_real = monto_reclamado.get(ramo_code, Decimal('0.0'))

            ratio_bruto = Decimal('0.0')
            # Evitar división por cero o por primas insignificantes
            if contratado > Decimal('0.005'):
                ratio_bruto = (reclamado_real / contratado * 100)

            # Capear el ratio que se usará para la altura de la barra Y para el texto en la barra
            ratio_para_display = min(ratio_bruto, RATIO_CAP_VISUAL)

            texto_en_barra_final = f"{ratio_para_display:.0f}%"
            # Si el ratio bruto era mayor que el capeado, podemos indicarlo en el texto
            if ratio_bruto > RATIO_CAP_VISUAL:
                # Ejemplo: "100%+"
                texto_en_barra_final = f"{RATIO_CAP_VISUAL:.0f}%+"

            logger.debug(
                f"G37 - Ramo: {ramo_map.get(ramo_code, ramo_code)}, Contratado: {contratado:.2f}, Reclamado: {reclamado_real:.2f}, Ratio Bruto: {ratio_bruto:.1f}%, Ratio Display: {ratio_para_display:.1f}%")

            resultados.append({
                'ramo_label': ramo_map.get(ramo_code, ramo_code),
                'monto_contratado': contratado,
                'monto_reclamado_real': reclamado_real,
                # Para altura de barra
                'ratio_graficar': float(ratio_para_display.quantize(Decimal('0.1'))),
                # Para tooltip
                'ratio_real_calculado': float(ratio_bruto.quantize(Decimal('0.1'))),
                'texto_barra_display': texto_en_barra_final  # Para texto en barra
            })

        if not resultados:
            return plot(generar_figura_sin_datos("No hay datos para calcular ratio de siniestralidad"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(resultados)
        if df.empty:  # Chequeo extra
            return plot(generar_figura_sin_datos("No hay datos significativos para el ratio"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Ordenar por el ratio real
        df = df.sort_values('ratio_real_calculado', ascending=False)

        # 4. Crear gráfico
        colors = []
        threshold_saludable = 70.0
        # Colores basados en el ratio_real_calculado para reflejar la situación real
        for ratio_real_val in df['ratio_real_calculado']:
            if ratio_real_val >= 100.0:  # Si el real es >= 100%
                colors.append(COLOR_PALETTE.get('dark', '#34495E'))
            elif ratio_real_val >= threshold_saludable:
                colors.append(COLOR_PALETTE.get('secondary', '#E74C3C'))
            elif ratio_real_val >= threshold_saludable * 0.6:
                colors.append(COLOR_PALETTE.get('warning', '#F39C12'))
            else:
                colors.append(COLOR_PALETTE.get('success', '#27AE60'))

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df['ramo_label'],
            # Usar el ratio capeado para la altura de la barra
            y=df['ratio_graficar'],
            marker_color=colors,
            # Usar el texto formateado (que también está "capeado" o indica capeo)
            text=df['texto_barra_display'],
            textposition='auto',
            customdata=np.stack(
                (df['monto_contratado'], df['monto_reclamado_real'], df['ratio_real_calculado']), axis=-1),
            hovertemplate=(
                "<b>Ramo: %{x}</b><br>"
                "Ratio Siniestralidad (Calculado Real): %{customdata[2]:.1f}%<br>"
                "Prima Total: $%{customdata[0]:,.0f}<br>"
                "Siniestros Totales: $%{customdata[1]:,.0f}"
                "<extra></extra>"
            )
        ))

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Ratio de Siniestralidad por Ramo (Visualizado hasta 100%)', x=0.5)
        layout_grafico['xaxis'] = dict(
            title='Ramo del Seguro', tickangle=45, type='category')
        layout_grafico['yaxis'] = dict(
            title='Ratio Siniestralidad (%)',
            ticksuffix='%',
            range=[0, float(RATIO_CAP_VISUAL * Decimal('1.1'))
                   ]  # Eje Y hasta 110%
        )
        layout_grafico['margin'] = dict(t=50, l=70, r=30, b=120)
        fig.update_layout(**layout_grafico)

        logger.info(
            "G37 - Gráfico de Ratio Siniestralidad por Ramo (Visual Capeado 100%) generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(
            f"Error G37 (Visual Capeado 100%): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error al generar Gráfico 37 ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 38: Antigüedad de las facturas pendientes de pago (Aging Report)
# ------------------------------


def grafico_38():
    """Muestra la antigüedad de las facturas pendientes de pago (Aging Report)."""
    try:
        hoy = date.today()

        # 1. Obtener datos básicos de facturas pendientes con fecha de vencimiento válida
        #    Filtramos directamente las vencidas para reducir el procesamiento en Python
        facturas_qs = (
            Factura.objects
            .filter(
                # Asegurarse que la factura esté activa (si aplica soft delete)
                activo=True,
                pagada=False,
                monto_pendiente__gt=Decimal('0.01'),
                vigencia_recibo_hasta__isnull=False,
                # <-- Filtro clave: Solo facturas cuya fecha de vencimiento ya pasó
                vigencia_recibo_hasta__lt=hoy
            )
            .values(
                'pk',  # Para identificar en logs si hay problemas
                'vigencia_recibo_hasta',
                'monto_pendiente'
            )
        )

        if not facturas_qs.exists():
            logger.info(
                "grafico_38: No se encontraron facturas vencidas pendientes de pago en la consulta inicial.")
            return plot(generar_figura_sin_datos("No hay facturas vencidas pendientes de pago"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        logger.debug(
            f"grafico_38: Se encontraron {facturas_qs.count()} facturas potencialmente vencidas y pendientes.")

        # 2. Procesar en Python para calcular días y asignar rangos
        data_procesada = []
        rangos = [
            (1, 30, '1-30 días'),
            (31, 60, '31-60 días'),
            (61, 90, '61-90 días'),
            (91, 180, '91-180 días'),
            (181, 9999, '181+ días')  # Rango abierto para los más antiguos
        ]

        # Iterar sobre el QuerySet
        for factura_data in facturas_qs:
            fecha_vencimiento = factura_data.get('vigencia_recibo_hasta')
            monto_pendiente = factura_data.get('monto_pendiente')
            factura_pk = factura_data.get('pk')

            # Validaciones robustas de los datos obtenidos
            if not isinstance(fecha_vencimiento, date):
                # Intentar convertir si es datetime
                if isinstance(fecha_vencimiento, datetime):
                    fecha_vencimiento = fecha_vencimiento.date()
                else:
                    logger.warning(
                        f"grafico_38: Factura PK {factura_pk} tiene fecha_vencimiento inválida o tipo incorrecto: {fecha_vencimiento} ({type(fecha_vencimiento)}). Omitiendo.")
                    continue  # Saltar esta factura

            if not isinstance(monto_pendiente, Decimal) or monto_pendiente <= Decimal('0.00'):
                logger.warning(
                    f"grafico_38: Factura PK {factura_pk} tiene monto_pendiente inválido: {monto_pendiente}. Omitiendo.")
                continue

            # Recalcular días vencido en Python
            if fecha_vencimiento >= hoy:  # Doble chequeo por seguridad
                logger.warning(
                    f"grafico_38: Factura PK {factura_pk} con fecha {fecha_vencimiento} no está vencida respecto a hoy ({hoy}). Omitiendo.")
                continue

            dias_vencido = (hoy - fecha_vencimiento).days

            if dias_vencido <= 0:  # No debería pasar por el filtro inicial, pero por si acaso
                logger.warning(
                    f"grafico_38: Factura PK {factura_pk} calculó días_vencido no positivo: {dias_vencido}. Omitiendo.")
                continue

            rango_asignado = None  # Iniciar como None
            for min_d, max_d, lbl in rangos:
                if min_d <= dias_vencido <= max_d:
                    rango_asignado = lbl
                    break

            if rango_asignado:
                data_procesada.append({
                    'rango_antiguedad': rango_asignado,
                    'total_pendiente': monto_pendiente  # Aún no agrupado
                })
            else:
                # Esto indica un problema en la definición de rangos o un valor extremo
                logger.error(
                    f"grafico_38: Factura PK {factura_pk} con {dias_vencido} días vencidos no cayó en ningún rango definido. Revise los rangos.")

        if not data_procesada:
            logger.info(
                "grafico_38: No quedaron facturas válidas tras el procesamiento en Python.")
            return plot(generar_figura_sin_datos("No se encontraron facturas válidas para el informe"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        logger.debug(
            f"grafico_38: Se procesaron {len(data_procesada)} registros de facturas vencidas.")

        # 3. Agrupar con Pandas
        df = pd.DataFrame(data_procesada)
        # Convertir a float ANTES de agrupar para evitar problemas de tipo
        df['total_pendiente'] = pd.to_numeric(
            df['total_pendiente'], errors='coerce').fillna(0.0)

        df_agrupado = df.groupby('rango_antiguedad', observed=False).agg(  # observed=False previene warnings con Categorical
            total_pendiente=('total_pendiente', 'sum')
        ).reset_index()

        # Filtrar rangos con suma cero después de agrupar
        # Usar pequeña tolerancia por floats
        df_agrupado = df_agrupado[df_agrupado['total_pendiente'] > 0.005]

        if df_agrupado.empty:
            logger.info(
                "grafico_38: La suma de montos pendientes por rango resultó cero.")
            return plot(generar_figura_sin_datos("Los montos pendientes en los rangos son cero."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # 4. Ordenar y preparar para Plotly
        rango_order = [lbl for _, _, lbl in rangos]
        # Convertir a categórico para asegurar el orden correcto
        df_agrupado['rango_antiguedad'] = pd.Categorical(
            df_agrupado['rango_antiguedad'],
            categories=rango_order,
            ordered=True
        )
        # Ordenar según el orden categórico
        df_agrupado = df_agrupado.sort_values('rango_antiguedad')

        # Mapa de colores (puede definirse fuera si es reutilizado)
        color_map = {
            '1-30 días': COLOR_PALETTE.get('success'),
            '31-60 días': COLOR_PALETTE.get('info'),
            '61-90 días': COLOR_PALETTE.get('warning'),
            '91-180 días': COLOR_PALETTE.get('secondary'),
            '181+ días': COLOR_PALETTE.get('dark'),
        }

        # 5. Crear gráfico de barras con Plotly Express
        fig = px.bar(
            df_agrupado,
            x='rango_antiguedad',
            y='total_pendiente',
            text='total_pendiente',  # Muestra el valor en la barra
            labels={'rango_antiguedad': 'Antigüedad del Vencimiento',
                    'total_pendiente': 'Monto Pendiente Total (USD)'},
            title="Antigüedad de Saldos Pendientes (Facturas Vencidas)",
            color='rango_antiguedad',  # Usa la columna para determinar el color
            color_discrete_map=color_map  # Mapea los valores a colores específicos
        )

        # Ajustar formato de texto y tooltips
        fig.update_traces(
            texttemplate='$%{text:,.0f}',  # Formato de moneda sin decimales
            textposition='outside',  # Posición del texto
            # Tooltip personalizado
            hovertemplate="<b>%{x}</b><br>Total Pendiente: $%{y:,.0f}<extra></extra>"
        )

        # Ocultar leyenda (redundante con los colores y ejes)
        fig.update_layout(showlegend=False)

        # Ajustes finales del Layout
        layout_grafico = BASE_LAYOUT.copy()
        # Asegurar que el eje X se trate como categoría para mantener el orden
        layout_grafico['xaxis'] = dict(
            title='Antigüedad del Vencimiento', type='category')
        layout_grafico['yaxis'] = dict(
            title='Monto Pendiente Total (USD)', tickprefix='$')
        # Ajustar márgenes según sea necesario
        layout_grafico['margin'] = dict(t=50, l=70, r=30, b=50)
        fig.update_layout(**layout_grafico)

        logger.info(
            "grafico_38: Gráfica de Antigüedad de Saldos generada exitosamente.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    # Captura de excepciones más específica podría ser útil
    except (ValueError, TypeError) as data_err:
        logger.error(
            f"Error de datos o tipos en gráfico_38 (Aging Report): {str(data_err)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error de datos: {str(data_err)}"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        # Captura genérica para cualquier otro error inesperado
        logger.error(
            f"Error crítico inesperado en gráfico_38 (Aging Report): {str(e)}", exc_info=True)
        # Mostrar el tipo de error puede ayudar en la depuración
        return plot(generar_figura_sin_datos(f"Error inesperado ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 39: evolución mensual del costo promedio de los siniestros incurridos
# ------------------------------


def grafico_39():
    """Muestra la evolución mensual del costo promedio de los siniestros incurridos (reclamados)."""
    try:
        # Calcular costo promedio de siniestros cerrados por mes de cierre
        costo_promedio_mes = (Reclamacion.objects
                              # Siniestros cerrados con monto
                              .filter(activo=True, monto_reclamado__isnull=False, monto_reclamado__gt=0, fecha_cierre_reclamo__isnull=False)
                              .annotate(mes_cierre=TruncMonth('fecha_cierre_reclamo'))
                              .values('mes_cierre')
                              .annotate(costo_promedio=Avg('monto_reclamado'))
                              .order_by('mes_cierre')
                              .values('mes_cierre', 'costo_promedio')
                              )

        if not costo_promedio_mes:
            return plot(generar_figura_sin_datos("No hay datos de siniestros cerrados para calcular costo promedio"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(list(costo_promedio_mes))
        df['mes_cierre'] = pd.to_datetime(df['mes_cierre'])
        df['costo_promedio'] = df['costo_promedio'].astype(float)

        # Usar últimos 24 meses si hay muchos datos
        if len(df) > 24:
            df = df.tail(24)

        df['mes_str'] = df['mes_cierre'].dt.strftime('%Y-%m')

        # Crear gráfico de línea
        fig = px.line(
            df,
            x='mes_str',
            y='costo_promedio',
            labels={'mes_str': 'Mes de Cierre Siniestro',
                    'costo_promedio': 'Costo Promedio Siniestro ($)'},
            title="Evolución Mensual del Costo Promedio por Siniestro (Incurrido)",
            markers=True
        )

        fig.update_traces(line=dict(color=COLOR_PALETTE.get(
            'info'), width=3), marker=dict(size=7))

        # Layout
        layout_grafico = BASE_LAYOUT.copy()
        # layout_grafico['title'] ya está en px.line
        layout_grafico['xaxis'] = dict(
            title='Mes de Cierre del Siniestro', type='category', tickangle=45)
        layout_grafico['yaxis'] = dict(
            title='Costo Promedio (USD)', tickprefix='$')
        layout_grafico['hovermode'] = 'x unified'
        # Margen izquierdo para título eje Y
        layout_grafico['margin'] = dict(t=50, l=70, r=30, b=80)
        fig.update_layout(**layout_grafico)

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(
            f"Error gráfico_39 (Reemplazo Costo Promedio Siniestro): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos("Error al generar costo promedio de siniestro"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 40: Análisis Siniestralidad por Edad (Reemplazo)
# ------------------------------


def grafico_40():
    """
    Muestra la Frecuencia (cantidad) y Severidad (monto promedio) de las reclamaciones
    agrupadas por rango de edad del afiliado individual.
    """
    try:
        # Definir rangos de edad
        # Ajusta estos rangos según tus necesidades
        rangos = [
            (0, 17, '0-17'), (18, 25, '18-25'), (26, 35, '26-35'),
            (36, 45, '36-45'), (46, 55, '46-55'), (56, 65, '56-65'),
            # Ajustar límite superior si es necesario
            (66, 75, '66-75'), (76, 120, '76+')
        ]
        when_clauses = [
            When(edad__gte=min_edad, edad__lte=max_edad, then=Value(label))
            for min_edad, max_edad, label in rangos
        ]

        # Consulta para obtener cantidad y monto promedio por rango de edad
        data_qs = (Reclamacion.objects
                   .filter(contrato_individual__isnull=False, contrato_individual__afiliado__fecha_nacimiento__isnull=False)
                   .annotate(
                       edad=ExtractYear(
                           Now()) - ExtractYear('contrato_individual__afiliado__fecha_nacimiento'),
                       rango_edad=Case(
                           *when_clauses, default=Value('Desconocido'), output_field=CharField())
                   )
                   # Excluir desconocidos si no son útiles
                   .exclude(rango_edad='Desconocido')
                   .values('rango_edad')
                   .annotate(
                       cantidad_reclamaciones=Count('id'),
                       monto_promedio_reclamado=Coalesce(Avg('monto_reclamado'), Value(
                           Decimal('0.0')), output_field=DecimalField())
                   )
                   # Ordenar por el orden definido en 'rangos' para el gráfico
                   .order_by(
                       Case(*[When(rango_edad=label, then=Value(i))
                            for i, (_, _, label) in enumerate(rangos)])
                   ))

        if not data_qs.exists():
            return plot(generar_figura_sin_datos("No hay datos de reclamaciones para analizar por edad"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(list(data_qs))
        # Convertir monto promedio a float para Plotly
        df['monto_promedio_float'] = df['monto_promedio_reclamado'].astype(
            float)

        # Crear figura con ejes Y secundarios
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Añadir barras para Cantidad de Reclamaciones (Eje Y Izquierdo)
        fig.add_trace(go.Bar(
            x=df['rango_edad'],
            y=df['cantidad_reclamaciones'],
            name='Cantidad Reclamaciones',
            marker_color=COLOR_PALETTE.get('primary', '#2C3E50'),
            text=df['cantidad_reclamaciones'],
            textposition='auto',
            hoverinfo='x+y+name',
            hovertemplate='<b>%{x}</b><br>Cantidad: %{y}<extra></extra>'
        ), secondary_y=False)

        # Añadir línea para Monto Promedio Reclamado (Eje Y Derecho)
        fig.add_trace(go.Scatter(
            x=df['rango_edad'],
            y=df['monto_promedio_float'],
            name='Monto Promedio ($)',
            mode='lines+markers',
            line=dict(color=COLOR_PALETTE.get(
                'secondary', '#E74C3C'), width=3),
            marker=dict(size=8),
            hoverinfo='x+y+name',
            hovertemplate='<b>%{x}</b><br>Monto Prom.: $%{y:,.2f}<extra></extra>'
        ), secondary_y=True)

        # Configurar layout
        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Frecuencia y Severidad de Reclamaciones por Edad', x=0.5)
        layout_grafico['xaxis'] = dict(title='Rango de Edad')
        layout_grafico['yaxis'] = dict(
            title='Cantidad de Reclamaciones',
            side='left',
            showgrid=True,  # Mostrar grid principal
            gridcolor='#e5e5e5'
        )
        layout_grafico['yaxis2'] = dict(
            title='Monto Promedio Reclamado ($)',
            side='right',
            overlaying='y',
            tickprefix='$',
            showgrid=False  # Ocultar grid secundaria
        )
        layout_grafico['legend'] = dict(
            orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5)
        # Aunque solo hay una serie de barras, es buena práctica
        layout_grafico['barmode'] = 'group'
        # Ajustar márgenes para ambos ejes Y
        layout_grafico['margin'] = dict(t=50, l=60, r=70, b=80)
        fig.update_layout(**layout_grafico)

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_40 (nuevo): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos("Error al generar Gráfico 40"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 41: Correlación Ramos-Reclamaciones
# ------------------------------


def grafico_41():
    try:
        from django.db.models import Case, When, Value, CharField

        data = (Reclamacion.objects
                .annotate(
                    ramo=Case(
                        When(contrato_individual__isnull=False,
                             then=F('contrato_individual__ramo')),
                        When(contrato_colectivo__isnull=False,
                             then=F('contrato_colectivo__ramo')),
                        default=Value('Sin Especificar'),
                        output_field=CharField()
                    )
                )
                .values('ramo', 'tipo_reclamacion')
                .annotate(total=Count('id'))
                .order_by('ramo', 'tipo_reclamacion'))

        if not data.exists():
            return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(data)
        pivot = df.pivot_table(
            index='ramo', columns='tipo_reclamacion', values='total', fill_value=0)

        fig = go.Figure(go.Heatmap(
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            z=pivot.values.tolist(),
            colorscale='Viridis',
            texttemplate="%{z}",
            hoverinfo="x+y+z"
        ))

        fig.update_layout(
            **BASE_LAYOUT,
            title=dict(text='Correlación Ramos-Reclamaciones', x=0.5),
            xaxis=dict(title='Tipo de Reclamación'),
            yaxis=dict(title='Ramo'),
            height=500
        )
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_41: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 42: Top Intermediarios (Comisión y % Retención)
# ------------------------------


def grafico_42():
    """Muestra Top N intermediarios por comisiones estimadas y su tasa de retención de contratos."""
    try:
        N = 10  # Top N intermediarios
        logger.debug(
            f"G42 - Iniciando Top {N} Intermediarios (Comisión y % Retención)")

        # Consulta para obtener los datos necesarios por intermediario
        data_qs = (Intermediario.objects
                   .filter(activo=True)  # Solo intermediarios activos
                   .annotate(
                       # Conteo de contratos individuales TOTALES asociados al intermediario
                       count_ind_total=Count(
                           'contratoindividual', distinct=True),
                       # Conteo de contratos individuales VIGENTES asociados
                       count_ind_vigentes=Count('contratoindividual', filter=Q(
                           contratoindividual__estatus='VIGENTE', contratoindividual__activo=True), distinct=True),
                       # Conteo de contratos colectivos TOTALES
                       count_col_total=Count(
                           'contratos_colectivos', distinct=True),
                       # Conteo de contratos colectivos VIGENTES
                       count_col_vigentes=Count('contratos_colectivos', filter=Q(
                           contratos_colectivos__estatus='VIGENTE', contratos_colectivos__activo=True), distinct=True),

                       # Comisiones estimadas de contratos individuales activos
                       comisiones_ind_est=Coalesce(Sum(
                           F('contratoindividual__monto_total') *
                           F('porcentaje_comision') / Decimal('100.0'),
                           filter=Q(contratoindividual__activo=True,
                                    contratoindividual__monto_total__isnull=False)
                       ), Value(Decimal('0.0')), output_field=DecimalField()),

                       # Comisiones estimadas de contratos colectivos activos
                       comisiones_col_est=Coalesce(Sum(
                           F('contratos_colectivos__monto_total') *
                           F('porcentaje_comision') / Decimal('100.0'),
                           filter=Q(contratos_colectivos__activo=True,
                                    contratos_colectivos__monto_total__isnull=False)
                       ), Value(Decimal('0.0')), output_field=DecimalField())
                   )
                   .annotate(
                       # Totales consolidados por intermediario
                       contratos_total_general=F(
                           'count_ind_total') + F('count_col_total'),
                       contratos_vigentes_general=F(
                           'count_ind_vigentes') + F('count_col_vigentes'),
                       comisiones_total_estimada=F(
                           'comisiones_ind_est') + F('comisiones_col_est')
                   )
                   .annotate(
                       # Tasa de Retención
                       tasa_retencion=Case(
                           When(contratos_total_general__gt=0,
                                then=ExpressionWrapper(F('contratos_vigentes_general') * Decimal('100.0') / F('contratos_total_general'), output_field=FloatField())),
                           # Retención 0 si no hay contratos totales
                           default=Value(0.0),
                           output_field=FloatField()
                       )
                   )
                   # Considerar solo intermediarios con alguna comisión o contrato para el ranking
                   .filter(Q(comisiones_total_estimada__gt=Decimal('0.005')) | Q(contratos_total_general__gt=0))
                   # Top N por comisión
                   .order_by('-comisiones_total_estimada')[:N]
                   )

        if not data_qs:
            return plot(generar_figura_sin_datos("No hay datos de actividad de intermediarios para G42"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df_data = []
        for d in data_qs:
            # Validar que retencion no sea mayor a 100 (podría ser un poco más por redondeo float)
            retencion_calculada = d.tasa_retencion if d.tasa_retencion is not None else 0.0
            # Asegurar entre 0 y 100
            retencion_final = min(max(retencion_calculada, 0.0), 100.0)

            if retencion_calculada > 100.5:  # Si es significativamente mayor, loguear
                logger.warning(
                    f"G42 - Intermediario {d.nombre_completo} (PK:{d.pk}) con retención >100% ({retencion_calculada:.2f}%). Vigentes: {d.contratos_vigentes_general}, Totales: {d.contratos_total_general}. Se capea a 100%.")

            df_data.append({
                'nombre_intermediario': d.nombre_completo,
                'comisiones': float(d.comisiones_total_estimada or 0),
                'retencion': retencion_final,  # Usar el valor potencialmente ajustado
                'contratos_vigentes': d.contratos_vigentes_general,
                'contratos_totales': d.contratos_total_general
            })

        df = pd.DataFrame(df_data)
        if df.empty:
            return plot(generar_figura_sin_datos("No hay datos válidos tras procesar para Gráfico 42"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        fig.add_trace(go.Bar(
            x=df['nombre_intermediario'], y=df['comisiones'], name='Comisiones Estimadas',
            marker_color=COLOR_PALETTE.get('primary'),
            text=[f"${c:,.0f}" for c in df['comisiones']], textposition='auto',
            hovertemplate="<b>%{x}</b><br>Comisiones: $%{y:,.0f}<extra></extra>"
        ), secondary_y=False)

        fig.add_trace(go.Scatter(
            x=df['nombre_intermediario'], y=df['retencion'], name='% Retención Cartera', mode='lines+markers',
            line=dict(color=COLOR_PALETTE.get(
                'success')),  # Cambiado a success
            marker=dict(size=8),
            customdata=np.stack(
                (df['contratos_vigentes'], df['contratos_totales']), axis=-1),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "% Retención: %{y:.1f}%<br>"
                "Vigentes: %{customdata[0]}<br>"
                "Totales: %{customdata[1]}<extra></extra>"
            )
        ), secondary_y=True)

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text=f'Top {N} Intermediarios: Comisiones Estimadas y % Retención de Cartera', x=0.5)
        layout_grafico['xaxis'] = dict(
            title='Intermediario', tickangle=35, type='category')
        layout_grafico['yaxis'] = dict(
            title='Comisiones Estimadas (USD)', tickprefix='$', side='left')
        layout_grafico['yaxis2'] = dict(
            # De 0 a 105%
            title='% Retención', rangemode='tozero', range=[0, 105],
            side='right', overlaying='y', ticksuffix='%', showgrid=False
        )
        # Un poco más alto para mejor visualización
        layout_grafico['height'] = 500
        layout_grafico['legend'] = dict(
            orientation="h", yanchor="top", y=1.15, xanchor="center", x=0.5)  # Leyenda arriba
        layout_grafico['margin'] = dict(
            t=80, b=120, l=70, r=70)  # Ajustar márgenes
        fig.update_layout(**layout_grafico)

        logger.info(
            "G42 - Top Intermediarios (Comisión y % Retención) generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error G42: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error al generar Gráfico 42 ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Descomposición de la Prima Emitida por Ramo y Tipo de Contrato
# ------------------------------


def grafico_43():
    """Muestra la descomposición de la Prima Emitida por Ramo y Tipo de Contrato."""
    try:
        # Obtener prima por Ramo y Tipo
        prima_ind = (ContratoIndividual.objects
                     .filter(activo=True)
                     .values('ramo')
                     .annotate(total_prima=Coalesce(Sum('monto_total'), Decimal('0.0')))
                     .values('ramo', 'total_prima'))
        prima_col = (ContratoColectivo.objects
                     .filter(activo=True)
                     .values('ramo')
                     .annotate(total_prima=Coalesce(Sum('monto_total'), Decimal('0.0')))
                     .values('ramo', 'total_prima'))

        data = []
        has_data = False
        ramo_map = dict(CommonChoices.RAMO)

        for item in prima_ind:
            if item['total_prima'] > 0:
                has_data = True
                ramo_label = ramo_map.get(item['ramo'], item['ramo'])
                data.append(
                    {'Tipo': 'Individual', 'Ramo': ramo_label, 'Prima': item['total_prima']})

        for item in prima_col:
            if item['total_prima'] > 0:
                has_data = True
                ramo_label = ramo_map.get(item['ramo'], item['ramo'])
                data.append({'Tipo': 'Colectivo', 'Ramo': ramo_label,
                            'Prima': item['total_prima']})

        if not has_data or not data:
            return plot(generar_figura_sin_datos("No hay datos de primas para descomponer"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(data)
        df['Prima'] = df['Prima'].astype(float)  # Convertir para Sunburst

        # Crear Sunburst
        fig = px.sunburst(
            df,
            path=['Tipo', 'Ramo'],  # Jerarquía: Tipo -> Ramo
            values='Prima',
            color='Tipo',  # Colorear nivel superior
            color_discrete_map={'Individual': COLOR_PALETTE.get(
                'info'), 'Colectivo': COLOR_PALETTE.get('primary')},
            branchvalues='total',  # Suma de hijos = padre
            hover_data=['Prima']  # Mostrar prima en hover
        )

        # Ajustar texto y hover
        fig.update_traces(
            textinfo='label+percent parent',  # Porcentaje relativo al padre
            hovertemplate='<b>%{label}</b><br>Prima: $%{value:,.0f}<br>(%{percentParent:.1%} del Tipo)<extra></extra>'
        )

        # Layout
        layout_actualizado = BASE_LAYOUT.copy()
        layout_actualizado['title'] = dict(
            text='Descomposición Prima Emitida por Tipo y Ramo', x=0.5)
        layout_actualizado['margin'] = dict(t=50, l=10, r=10, b=10)
        fig.update_layout(**layout_actualizado)

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(
            f"Error gráfico_43 (Reemplazo Sunburst Prima): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos("Error al descomponer primas"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 44: Montos Asegurados
# ------------------------------


def grafico_44():
    """Muestra los N contratos con mayor monto asegurado (Individual + Colectivo)."""
    try:
        N = 15  # Número de contratos top a mostrar (ajustable)

        # Obtener Top N Individuales
        top_ind = (ContratoIndividual.objects
                   .select_related('afiliado')  # Para mostrar nombre
                   .filter(monto_total__isnull=False)
                   .order_by('-monto_total')
                   .values('numero_contrato', 'monto_total', 'afiliado__primer_nombre', 'afiliado__primer_apellido')[:N])

        # Obtener Top N Colectivos
        top_col = (ContratoColectivo.objects
                   .filter(monto_total__isnull=False)
                   .order_by('-monto_total')
                   .values('numero_contrato', 'monto_total', 'razon_social')[:N])

        # Combinar y ordenar los datos top generales
        data_combined = []
        for item in top_ind:
            label = f"CI: {item['numero_contrato']} ({item['afiliado__primer_apellido']})"
            data_combined.append(
                {'label': label, 'monto': item['monto_total'], 'tipo': 'Individual'})
        for item in top_col:
            label = f"CC: {item['numero_contrato']} ({item['razon_social']})"
            data_combined.append(
                {'label': label, 'monto': item['monto_total'], 'tipo': 'Colectivo'})

        # Ordenar combinados por monto y tomar el top N general
        df = pd.DataFrame(data_combined)
        if df.empty:
            return plot(generar_figura_sin_datos("No hay contratos con montos para mostrar"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df['monto'] = pd.to_numeric(df['monto'], errors='coerce').fillna(0.0)
        df_top = df.nlargest(N, 'monto')
        df_top['monto_float'] = df_top['monto'].astype(float)  # Para plotly

        # Crear gráfico de barras horizontales
        fig = px.bar(
            df_top,
            x='monto_float',
            y='label',
            orientation='h',
            color='tipo',  # Colorear por tipo de contrato
            color_discrete_map={'Individual': COLOR_PALETTE.get(
                'info'), 'Colectivo': COLOR_PALETTE.get('primary')},
            labels={'label': 'Contrato (Número y Cliente/Empresa)',
                    'monto_float': 'Monto Total Asegurado (USD)', 'tipo': 'Tipo Contrato'},
            text='monto_float'  # Mostrar monto en la barra
        )

        fig.update_traces(texttemplate='$%{text:,.0f}', textposition='auto')
        # Ordenar de menor a mayor (visualmente el mayor queda arriba)
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text=f'Top {N} Contratos por Mayor Monto Asegurado', x=0.5)
        layout_grafico['xaxis'] = dict(
            title='Monto Total Asegurado (USD)', tickprefix='$')
        layout_grafico['yaxis'] = dict(title='Contrato')
        # Margen izquierdo amplio para nombres
        layout_grafico['margin'] = dict(l=300, r=30, t=50, b=40)
        layout_grafico['legend_title_text'] = 'Tipo'
        fig.update_layout(**layout_grafico)

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_21 (nuevo): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos("Error al generar Gráfico 21"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 45: Tendencia Renovaciones
# ------------------------------


def grafico_45():
    try:
        # <--- ¡¡AJUSTA ESTE VALOR!!
        VALOR_DE_RENOVACION_EN_ESTADO_CONTRATO = 'EN_TRAMITE_RENOVACION'

        data_qs = (ContratoIndividual.objects
                   # Es buena práctica asegurar que la fecha no sea nula
                   .filter(fecha_emision__isnull=False)
                   .annotate(
                       year=ExtractYear('fecha_emision'),
                       es_renovacion=Case(
                           # 2. CAMBIA EL CAMPO Y EL VALOR AQUÍ
                           When(
                               estado_contrato=VALOR_DE_RENOVACION_EN_ESTADO_CONTRATO, then=1),
                           default=0,  # Todos los demás contratos se consideran "Nuevos" en este contexto
                           output_field=IntegerField()
                       )
                   )
                   .values('year')
                   .annotate(
                       nuevos=Count('id', filter=Q(es_renovacion=0)),
                       renovaciones=Count('id', filter=Q(es_renovacion=1))
                   )
                   .order_by('year'))  # Ordenar por año

        if not data_qs.exists():
            return plot(generar_figura_sin_datos("No hay datos para tendencia de nuevos vs renovaciones."),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(list(data_qs))

        if df.empty:
            return plot(generar_figura_sin_datos("No hay datos para tendencia de nuevos vs renovaciones."),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df['year'].astype(str),
            y=df['nuevos'],
            name='Nuevos/Otros',  # Etiqueta para los que no son explícitamente "renovación"
            marker_color=COLOR_PALETTE.get('primary', '#007bff')
        ))
        fig.add_trace(go.Bar(
            x=df['year'].astype(str),
            y=df['renovaciones'],
            # O la etiqueta que corresponda a VALOR_DE_RENOVACION_EN_ESTADO_CONTRATO
            name='Renovaciones',
            marker_color=COLOR_PALETTE.get(
                'success', '#28a745')  # Un color diferente
        ))

        current_layout = BASE_LAYOUT.copy()  # Evitar modificar el global
        current_layout.update(
            title=dict(
                text='Tendencia de Contratos Nuevos vs. Renovaciones (por Año de Emisión)', x=0.5),
            xaxis=dict(title='Año de Emisión', type='category'),
            yaxis=dict(title='Cantidad de Contratos'),
            barmode='stack',  # O 'group' para barras lado a lado
            legend_title_text='Tipo'
        )
        fig.update_layout(**current_layout)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(
            f"Error en grafico_45 (versión simplificada): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error generando gráfico 45: {type(e).__name__}"),
                    output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 46: Distribución Ingresos
# ------------------------------


def grafico_46():
    """Muestra la distribución mensual/anual de la Prima Emitida."""
    try:
        # Obtener prima emitida por mes/año
        data_ind = (ContratoIndividual.objects
                    .filter(activo=True)
                    .annotate(year=ExtractYear('fecha_emision'), month=ExtractMonth('fecha_emision'))
                    .values('year', 'month')
                    .annotate(total_prima=Coalesce(Sum('monto_total'), Decimal('0.0')))
                    .values('year', 'month', 'total_prima'))

        data_col = (ContratoColectivo.objects
                    .filter(activo=True)
                    .annotate(year=ExtractYear('fecha_emision'), month=ExtractMonth('fecha_emision'))
                    .values('year', 'month')
                    .annotate(total_prima=Coalesce(Sum('monto_total'), Decimal('0.0')))
                    .values('year', 'month', 'total_prima'))

        df_ind = pd.DataFrame(list(data_ind))
        df_col = pd.DataFrame(list(data_col))
        df_total = pd.concat([df_ind, df_col])

        if df_total.empty:
            return plot(generar_figura_sin_datos("No hay datos de primas emitidas"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Agrupar prima total por mes y año
        df_agrupado = df_total.groupby(['year', 'month'], as_index=False)[
            'total_prima'].sum()
        df_agrupado['total_prima'] = df_agrupado['total_prima'].astype(
            float)  # Convertir para heatmap

        # Pivotear para Heatmap
        try:
            pivot_df = df_agrupado.pivot_table(
                index='month', columns='year', values='total_prima', fill_value=0
            )
            # Asegurar que todos los meses (1-12) estén presentes
            pivot_df = pivot_df.reindex(index=range(1, 13), fill_value=0)

        except Exception as pivot_error:
            logger.error(
                f"Error al pivotear datos para heatmap G46: {pivot_error}", exc_info=True)
            return plot(generar_figura_sin_datos("Error al procesar datos para heatmap"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Crear Heatmap
        fig = go.Figure(data=go.Heatmap(
            z=pivot_df.values,
            x=pivot_df.columns,  # Años
            y=['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul',
                'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],  # Meses
            colorscale='Greens',  # Escala de verdes para ingresos
            text=pivot_df.values,
            texttemplate="$%{text:,.0f}",
            hoverongaps=False,
            hovertemplate="<b>Mes:</b> %{y}<br><b>Año:</b> %{x}<br><b>Prima Emitida:</b> $%{z:,.0f}<extra></extra>"
        ))

        # Layout
        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Distribución Mensual de Prima Emitida', x=0.5)
        layout_grafico['xaxis'] = dict(title='Año')
        layout_grafico['yaxis'] = dict(title='Mes')
        layout_grafico['margin'] = dict(t=50, l=50, r=30, b=50)
        fig.update_layout(**layout_grafico)

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(
            f"Error gráfico_46 (Reemplazo Heatmap Prima): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos("Error al generar heatmap de primas"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 47: Segmentación Contratos (Treemap)
# ------------------------------


def grafico_47():
    """Segmentación de Contratos Individuales (Treemap)."""
    try:
        data_qs = (ContratoIndividual.objects
                   .values('ramo', 'forma_pago', 'estatus')
                   .annotate(total=Count('id')))

        if not data_qs.exists():
            return plot(generar_figura_sin_datos("No hay Contratos Individuales para segmentar"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(list(data_qs))
        df = df[df['total'] > 0]
        if df.empty:
            return plot(generar_figura_sin_datos("No hay datos válidos para Gráfico 47"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        ramo_map = dict(CommonChoices.RAMO)
        forma_map = dict(CommonChoices.FORMA_PAGO)
        estatus_map = dict(CommonChoices.ESTADOS_VIGENCIA)

        df['ramo_label'] = df['ramo'].map(ramo_map).fillna(df['ramo'])
        df['forma_pago_label'] = df['forma_pago'].map(
            forma_map).fillna(df['forma_pago'])
        df['estatus_label'] = df['estatus'].map(
            estatus_map).fillna(df['estatus'])

        df_treemap_data = []
        root_id = "Total Contratos"
        df_treemap_data.append(
            {'id': root_id, 'parent': '', 'value': df['total'].sum(), 'label': root_id})

        ramos_agg = df.groupby('ramo_label')['total'].sum().reset_index()
        for _, row in ramos_agg.iterrows():
            df_treemap_data.append(
                {'id': row['ramo_label'], 'parent': root_id, 'value': row['total'], 'label': row['ramo_label']})

        forma_agg = df.groupby(['ramo_label', 'forma_pago_label'])[
            'total'].sum().reset_index()
        for _, row in forma_agg.iterrows():
            forma_id = f"{row['ramo_label']}/{row['forma_pago_label']}"
            df_treemap_data.append(
                {'id': forma_id, 'parent': row['ramo_label'], 'value': row['total'], 'label': row['forma_pago_label']})

        estatus_agg = df.groupby(['ramo_label', 'forma_pago_label', 'estatus_label'])[
            'total'].sum().reset_index()
        for _, row in estatus_agg.iterrows():
            parent_id = f"{row['ramo_label']}/{row['forma_pago_label']}"
            estatus_id = f"{parent_id}/{row['estatus_label']}"
            df_treemap_data.append({'id': estatus_id, 'parent': parent_id,
                                   'value': row['total'], 'label': row['estatus_label']})

        df_treemap = pd.DataFrame(df_treemap_data)

        fig = go.Figure(go.Treemap(
            ids=df_treemap['id'],
            labels=df_treemap['label'],
            parents=df_treemap['parent'],
            values=df_treemap['value'],
            branchvalues="total",
            marker=dict(colors=px.colors.qualitative.Pastel),
            textinfo="label+value+percent parent+percent root",
            hoverinfo="label+value+percent parent+percent root"
        ))

        # CORRECCIÓN: Usar método de copia para evitar conflicto con BASE_LAYOUT['margin']
        layout_actualizado = BASE_LAYOUT.copy()
        layout_actualizado['title'] = dict(
            text='Segmentación de Contratos Individuales', x=0.5)
        layout_actualizado['margin'] = dict(
            t=50, l=10, r=10, b=10)  # Margin específico
        fig.update_layout(**layout_actualizado)

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_47: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos("Error al generar Gráfico 47"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
# ------------------------------
# Gráfico 48 (Nuevo): Contratos Próximos a Vencer (Tabla Simple)
# ------------------------------


def grafico_48():
    """Muestra una lista de contratos (Ind y Col) vigentes que vencen en los próximos 30 días."""
    try:
        hoy = date.today()
        fecha_limite = hoy + timedelta(days=30)
        campos_ind = ['pk', 'numero_contrato', 'fecha_fin_vigencia', 'afiliado__pk', 'afiliado__primer_nombre', 'afiliado__segundo_nombre',
                      'afiliado__primer_apellido', 'afiliado__segundo_apellido', 'intermediario__pk', 'intermediario__nombre_completo']
        contratos_ind_vencer = (ContratoIndividual.objects.filter(fecha_fin_vigencia__gte=hoy, fecha_fin_vigencia__lte=fecha_limite,
                                estatus='VIGENTE').select_related('afiliado', 'intermediario').order_by('fecha_fin_vigencia').values(*campos_ind))
        campos_col = ['pk', 'numero_contrato', 'fecha_fin_vigencia',
                      'razon_social', 'intermediario__pk', 'intermediario__nombre_completo']
        contratos_col_vencer = (ContratoColectivo.objects.filter(fecha_fin_vigencia__gte=hoy, fecha_fin_vigencia__lte=fecha_limite,
                                estatus='VIGENTE').select_related('intermediario').order_by('fecha_fin_vigencia').values(*campos_col))
        data_combinada = []
        for c in contratos_ind_vencer:
            afiliado_nombre = f"{c['afiliado__primer_apellido'] or ''} {c['afiliado__segundo_apellido'] or ''}, {c['afiliado__primer_nombre'] or ''} {c['afiliado__segundo_nombre'] or ''}".strip(
                ', ')
            intermediario_nombre = c['intermediario__nombre_completo'] or '-'
            data_combinada.append({'ID': str(c['pk']), 'N° Contrato': str(c['numero_contrato'] or '-'), 'Tipo': 'Individual',
                                  # Mantener fecha como objeto
                                   'Cliente/Empresa': afiliado_nombre, 'Vence': c['fecha_fin_vigencia'], 'Intermediario': intermediario_nombre})
        for c in contratos_col_vencer:
            intermediario_nombre = c['intermediario__nombre_completo'] or '-'
            data_combinada.append({'ID': str(c['pk']), 'N° Contrato': str(c['numero_contrato'] or '-'), 'Tipo': 'Colectivo', 'Cliente/Empresa': str(
                # Mantener fecha como objeto
                c['razon_social'] or '-'), 'Vence': c['fecha_fin_vigencia'], 'Intermediario': intermediario_nombre})
        if not data_combinada:
            return plot(generar_figura_sin_datos("No hay contratos próximos a vencer"), output_type='div', config=GRAPH_CONFIG)
        # Ordenar por fecha objeto
        data_combinada.sort(key=lambda x: x['Vence'] or date.max)
        df = pd.DataFrame(data_combinada)
        df['Vence'] = pd.to_datetime(df['Vence']).dt.strftime(
            '%d/%m/%Y')  # Formatear DESPUÉS de ordenar
        fig = go.Figure(data=[go.Table(header=dict(values=list(df.columns), fill_color=COLOR_PALETTE.get('primary'), align='left', font=dict(color='white', size=12)), cells=dict(
            values=[df[col].tolist() for col in df.columns], fill_color=COLOR_PALETTE.get('light'), align='left', font=dict(color=COLOR_PALETTE.get('dark'), size=11), height=30))])
        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Contratos Vigentes Próximos a Vencer (30 días)', x=0.5)
        layout_grafico['margin'] = dict(l=10, r=10, t=60, b=10)
        layout_grafico['height'] = 60 + (len(df) * 40) if len(df) > 0 else 200
        fig.update_layout(**layout_grafico)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error G48(nuevo): {e}", exc_info=True)
        return plot(generar_figura_sin_datos("Error G48"), output_type='div', config=GRAPH_CONFIG)
# ====================================================================
# Gráfico 49 (NUEVO): Distribución Geográfica de Contratos Activos
# ====================================================================


def grafico_49():
    """Muestra la cantidad de contratos activos (Individuales + Colectivos) por Estado."""
    logger.debug("G49: Iniciando generación...")
    try:
        default_estado = 'DESCONOCIDO'  # Valor para estados nulos/vacíos

        # 1. Contar contratos individuales activos por estado DEL AFILIADO
        contratos_ind_activos = (ContratoIndividual.objects
                                 .filter(activo=True, estatus='VIGENTE')
                                 # --- CORRECCIÓN: Acceder a través de la relación 'afiliado' ---
                                 .annotate(estado_afiliado=Coalesce(F('afiliado__estado'), Value(default_estado), output_field=CharField()))
                                 # Agrupar por el estado del afiliado
                                 .values('estado_afiliado')
                                 # --- FIN CORRECCIÓN ---
                                 .annotate(total_ind=Count('id'))
                                 .exclude(estado_afiliado='')  # Excluir vacíos
                                 # Ordenar por el estado del afiliado
                                 .order_by('estado_afiliado'))

        # 2. Contar contratos colectivos activos por estado DE LA EMPRESA
        #    Nota: ContratoColectivo no tiene estado directo, debemos ir al AfiliadoColectivo.
        #    Si un ContratoColectivo puede tener MÚLTIPLES AfiliadoColectivo, ¿cuál estado usamos?
        #    Asumiremos por ahora que queremos el estado del PRIMER AfiliadoColectivo asociado (puede no ser lo ideal).
        #    O, si el ContratoColectivo tiene un campo RIF/razón social que podríamos usar para buscar
        #    el AfiliadoColectivo principal, sería mejor.
        #    Vamos a simplificar y contar el contrato si *alguno* de sus afiliados colectivos
        #    tiene un estado definido. Esto podría sobrecontar si un contrato tiene afiliados en varios estados.
        #    Una mejor aproximación sería decidir cuál es el estado "principal" del contrato colectivo.

        # --- REVISIÓN LÓGICA COLECTIVOS ---
        # Contaremos CADA instancia de la relación M2M por estado del AfiliadoColectivo
        contratos_col_activos = (ContratoColectivo.objects
                                 # Asegurar que tenga afiliados
                                 .filter(activo=True, estatus='VIGENTE', afiliados_colectivos__isnull=False)
                                 # --- CORRECCIÓN: Acceder a través de M2M 'afiliados_colectivos' ---
                                 .annotate(estado_af_col=Coalesce(F('afiliados_colectivos__estado'), Value(default_estado), output_field=CharField()))
                                 # Agrupar por estado del afiliado colectivo
                                 .values('estado_af_col')
                                 # --- FIN CORRECCIÓN ---
                                 # Contar contratos distintos por estado de afiliado
                                 .annotate(total_col=Count('id', distinct=True))
                                 .exclude(estado_af_col='')
                                 .order_by('estado_af_col'))

        logger.debug(f"G49: Datos Ind Count: {contratos_ind_activos.count()}")
        logger.debug(f"G49: Datos Col Count: {contratos_col_activos.count()}")

        # 3. Combinar los resultados
        estado_counts = collections.defaultdict(int)
        for item in contratos_ind_activos:
            estado_code = item.get('estado_afiliado')  # Usar alias correcto
            if estado_code:
                estado_counts[estado_code] += item.get('total_ind', 0)
        for item in contratos_col_activos:
            estado_code = item.get('estado_af_col')  # Usar alias correcto
            if estado_code:
                estado_counts[estado_code] += item.get('total_col', 0)

        logger.debug(f"G49: estado_counts: {dict(estado_counts)}")

        if not estado_counts:
            return plot(generar_figura_sin_datos("No hay contratos activos para mostrar por estado"),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # 4. Preparar datos para el DataFrame
        estado_map = dict(CommonChoices.ESTADOS_VE)
        data_list = []
        for estado_code, total in estado_counts.items():
            if isinstance(total, (int, float, Decimal)) and total > 0:
                data_list.append({
                    'estado_code': estado_code,
                    # Usar mapa
                    'estado_label': estado_map.get(estado_code, estado_code),
                    'total': total
                })
            else:
                logger.warning(
                    f"G49: Estado '{estado_code}' tiene total inválido '{total}'. Omitiendo.")

        if not data_list:
            return plot(generar_figura_sin_datos("No hay datos válidos por estado tras procesar"),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(data_list).sort_values('total', ascending=False)
        df['total'] = pd.to_numeric(df['total'], errors='coerce').fillna(0.0)
        df = df[df['total'] > 0]

        if df.empty:
            return plot(generar_figura_sin_datos("No hay datos con valores positivos para graficar"),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        logger.debug(f"G49: DataFrame para gráfico:\n{df.to_string()}")

        # 5. Crear gráfico de barras (sin cambios desde aquí)
        fig = px.bar(
            df,
            x='estado_label',
            y='total',
            labels={'estado_label': 'Estado',
                    'total': 'Cantidad Contratos Activos'},
            title="Distribución Geográfica de Contratos Activos por Estado",
            text='total',
            color='total',
            color_continuous_scale=px.colors.sequential.Blues
        )
        fig.update_traces(textposition='outside')
        fig.update_layout(xaxis={'categoryorder': 'total descending'})
        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['xaxis_title'] = "Estados de Venezuela"
        layout_grafico['yaxis_title'] = "N° de Contratos Activos (Ind + Col)"
        layout_grafico['coloraxis_showscale'] = False
        layout_grafico['margin'] = dict(t=50, l=50, r=30, b=120)
        layout_grafico['xaxis_tickangle'] = -45
        fig.update_layout(**layout_grafico)

        logger.info("G49: Gráfica Distribución Geográfica generada.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_49 (Geográfico): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error al generar distribución geográfica ({type(e).__name__})"),
                    output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 50: Tablero Resumen
# ------------------------------


def grafico_50():
    """Distribución de Contratos por Tipo y Estado."""
    try:
        data = []
        has_data = False
        estatus_map = dict(CommonChoices.ESTADOS_VIGENCIA)

        contratos_ind = ContratoIndividual.objects.all()
        total_ind = contratos_ind.count()
        if total_ind > 0:
            has_data = True
            counts = contratos_ind.values(
                'estatus').annotate(total=Count('id'))
            for item in counts:
                if item['total'] > 0:
                    estado_label = estatus_map.get(
                        item['estatus'], item['estatus'])
                    data.append(
                        {'Tipo': 'Individual', 'Estado': estado_label, 'Cantidad': item['total']})

        contratos_col = ContratoColectivo.objects.all()
        total_col = contratos_col.count()
        if total_col > 0:
            has_data = True
            counts = contratos_col.values(
                'estatus').annotate(total=Count('id'))
            for item in counts:
                if item['total'] > 0:
                    estado_label = estatus_map.get(
                        item['estatus'], item['estatus'])
                    data.append(
                        {'Tipo': 'Colectivo', 'Estado': estado_label, 'Cantidad': item['total']})

        if not has_data or not data:
            return plot(generar_figura_sin_datos("No hay datos de contratos para mostrar"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(data)

        # Calcular porcentajes totales para hover/text
        df['Total_General'] = df['Cantidad'].sum()
        df['Porcentaje_Total'] = (df['Cantidad'] / df['Total_General']) * 100

        fig = px.sunburst(
            df,
            path=['Tipo', 'Estado'],
            values='Cantidad',
            color='Estado',  # Colorear por estado final
            color_discrete_map={  # Mapear colores conocidos
                estatus_map.get('VIGENTE', 'VIGENTE'): COLOR_PALETTE.get('success', '#27AE60'),
                estatus_map.get('VENCIDO', 'VENCIDO'): COLOR_PALETTE.get('secondary', '#E74C3C'),
                estatus_map.get('NO_VIGENTE_AUN', 'NO_VIGENTE_AUN'): COLOR_PALETTE.get('warning', '#F39C12'),
                # Color para estados no mapeados
                '(?)': COLOR_PALETTE.get('light', '#ECF0F1')
            },
            branchvalues='total',  # El tamaño del padre es la suma de los hijos
            # Mostrar porcentaje del total
            hover_data={'Porcentaje_Total': ':.2f%'}
        )

        # Ajustar texto para mostrar cantidad y porcentaje relativo al padre inmediato
        fig.update_traces(textinfo='label+percent parent')

        # CORRECCIÓN: Usar método de copia para evitar conflicto con BASE_LAYOUT['margin']
        layout_actualizado = BASE_LAYOUT.copy()
        layout_actualizado['title'] = dict(
            text='Distribución de Contratos por Tipo y Estado', x=0.5)
        layout_actualizado['margin'] = dict(
            t=50, l=10, r=10, b=10)  # Margin específico
        fig.update_layout(**layout_actualizado)

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(f"Error gráfico_50: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos("Error al generar Gráfico 50"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


# ------------------------------
# Gráfico 51 (Nuevo): Concentración de Siniestros (Análisis Pareto Simplificado - Pie Chart)
# ------------------------------
def grafico_51():
    """
    Muestra la concentración del monto total reclamado, comparando el monto de los N% 
    siniestros más costosos contra el monto del resto.
    """
    try:
        logger.debug("G51_nuevo - Iniciando Concentración de Siniestros")

        # Considerar todas las reclamaciones con monto
        reclamaciones_qs = (Reclamacion.objects
                            .filter(monto_reclamado__isnull=False, monto_reclamado__gt=Decimal('0.00'))
                            # Ordenar por monto descendente
                            .order_by('-monto_reclamado')
                            .values('pk', 'monto_reclamado'))
        # Podrías añadir más campos si quieres detalles en tooltips o análisis

        if not reclamaciones_qs.exists():
            return plot(generar_figura_sin_datos("No hay reclamaciones con monto para analizar"),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df_reclamaciones = pd.DataFrame(list(reclamaciones_qs))
        df_reclamaciones['monto_reclamado'] = pd.to_numeric(
            df_reclamaciones['monto_reclamado'], errors='coerce')
        df_reclamaciones.dropna(subset=['monto_reclamado'], inplace=True)

        if df_reclamaciones.empty:
            return plot(generar_figura_sin_datos("No hay reclamaciones válidas tras procesar"),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        total_monto_reclamado_general = df_reclamaciones['monto_reclamado'].sum(
        )
        total_num_reclamaciones = len(df_reclamaciones)

        if total_monto_reclamado_general == 0 or total_num_reclamaciones == 0:
            return plot(generar_figura_sin_datos("Monto total o número de reclamaciones es cero"),
                        output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Definir el porcentaje del "Top" a analizar, ej. Top 10% de los siniestros
        porcentaje_top_siniestros = 10  # Analizar el top 10%
        num_siniestros_top = max(
            1, int(total_num_reclamaciones * (porcentaje_top_siniestros / 100.0)))

        df_top_siniestros = df_reclamaciones.head(num_siniestros_top)
        monto_top_siniestros = df_top_siniestros['monto_reclamado'].sum()

        monto_resto_siniestros = total_monto_reclamado_general - monto_top_siniestros

        num_resto_siniestros = total_num_reclamaciones - num_siniestros_top

        logger.debug(
            f"G51_nuevo - Total Reclamado: {total_monto_reclamado_general:.2f} ({total_num_reclamaciones} siniestros)")
        logger.debug(
            f"G51_nuevo - Top {porcentaje_top_siniestros}% ({num_siniestros_top} siniestros) Monto: {monto_top_siniestros:.2f}")
        logger.debug(
            f"G51_nuevo - Resto ({num_resto_siniestros} siniestros) Monto: {monto_resto_siniestros:.2f}")

        labels = [
            f'Monto del Top {porcentaje_top_siniestros}% de Siniestros (los más costosos)',
            f'Monto del {100-porcentaje_top_siniestros}% Restante de Siniestros'
        ]
        values = [float(monto_top_siniestros), float(monto_resto_siniestros)]

        # Datos para el tooltip
        text_for_hover = [
            f"{num_siniestros_top} siniestros ({(num_siniestros_top/total_num_reclamaciones)*100 if total_num_reclamaciones else 0:.1f}% del total de siniestros)",
            f"{num_resto_siniestros} siniestros ({(num_resto_siniestros/total_num_reclamaciones)*100 if total_num_reclamaciones else 0:.1f}% del total de siniestros)"
        ]

        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.3,
            marker_colors=[COLOR_PALETTE.get(
                'secondary'), COLOR_PALETTE.get('primary')],
            textinfo='percent+label',  # Mostrará el % del monto total
            hoverinfo='label+value+percent+text',  # Añadir 'text' para el custom hover
            text=text_for_hover,  # Usar el texto calculado
            insidetextorientation='horizontal'  # Mejor para labels largos
        )])

        porcentaje_monto_top = (monto_top_siniestros / total_monto_reclamado_general) * \
            100 if total_monto_reclamado_general else 0

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text=f'Concentración de Montos Reclamados: Top {porcentaje_top_siniestros}% de Siniestros representan {porcentaje_monto_top:.1f}% del Total Reclamado',
            x=0.5,
            font=dict(size=14)  # Ajustar tamaño si el título es largo
        )
        layout_grafico['showlegend'] = True
        layout_grafico['legend'] = dict(
            orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        # Más margen para título y leyenda
        layout_grafico['margin'] = dict(t=80, b=80, l=20, r=20)
        fig.update_layout(**layout_grafico)

        logger.info(
            "G51_nuevo - Gráfico de Concentración de Siniestros generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(
            f"Error G51_nuevo (Concentración Siniestros): {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error al generar Gráfico 51 ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


logger_grafica_52 = logging.getLogger("myapp.graficas.grafico_52")


def grafico_52():
    logger_grafica_52.info(
        "==================== grafico_52: INICIO ====================")
    try:
        now_aware = django_timezone.now()
        # Para filtrar DateTimeField
        start_date_aware = now_aware - timedelta(days=365)
        start_date_date = start_date_aware.date()  # Para filtrar DateField

        # Comisiones Generadas por mes
        generadas_por_mes_qs = (RegistroComision.objects.filter(
                                fecha_calculo__gte=start_date_aware  # fecha_calculo es DateTimeField
                                )
                                # TruncMonth devuelve datetime aware
                                .annotate(mes_dt_db=TruncMonth('fecha_calculo'))
                                .values('mes_dt_db')
                                .annotate(total_generado=Coalesce(Sum('monto_comision'), Value(Decimal('0.0')), output_field=DecimalField()))
                                .order_by('mes_dt_db'))

        logger_grafica_52.debug(
            f"QuerySet Comisiones Generadas (generadas_por_mes_qs) count: {generadas_por_mes_qs.count()}")
        # for item in list(generadas_por_mes_qs[:3]): logger_grafica_52.debug(f"  Item Generadas: {item}")

        # Comisiones Pagadas por mes
        pagadas_por_mes_qs = (RegistroComision.objects.filter(
            estatus_pago_comision='PAGADA',
            # fecha_pago_a_intermediario es DateField
            fecha_pago_a_intermediario__gte=start_date_date
        )
            # TruncMonth devuelve date
            .annotate(mes_dt_db=TruncMonth('fecha_pago_a_intermediario'))
            .values('mes_dt_db')
            .annotate(total_pagado=Coalesce(Sum('monto_comision'), Value(Decimal('0.0')), output_field=DecimalField()))
            .order_by('mes_dt_db'))

        logger_grafica_52.debug(
            f"QuerySet Comisiones Pagadas (pagadas_por_mes_qs) count: {pagadas_por_mes_qs.count()}")
        # for item in list(pagadas_por_mes_qs[:3]): logger_grafica_52.debug(f"  Item Pagadas: {item}")

        df_generadas = pd.DataFrame(list(generadas_por_mes_qs))
        df_pagadas = pd.DataFrame(list(pagadas_por_mes_qs))

        # Procesar df_generadas
        if not df_generadas.empty and 'mes_dt_db' in df_generadas.columns:
            df_generadas['mes'] = pd.to_datetime(df_generadas['mes_dt_db'])
            # Si TruncMonth(DateTimeField) devolvió aware
            if df_generadas['mes'].dt.tz is not None:
                df_generadas['mes'] = df_generadas['mes'].dt.tz_convert(
                    'UTC').dt.tz_localize(None)  # Convertir a naive UTC
            df_generadas.drop(columns=['mes_dt_db'], inplace=True)
            df_generadas['total_generado'] = df_generadas['total_generado'].apply(
                lambda x: Decimal(x) if x is not None else Decimal('0.00'))
        else:
            df_generadas = pd.DataFrame(columns=['mes', 'total_generado'])
        logger_grafica_52.debug(
            f"df_generadas procesado head:\n{df_generadas.head().to_string()}\ndtypes:\n{df_generadas.dtypes}")

        # Procesar df_pagadas
        if not df_pagadas.empty and 'mes_dt_db' in df_pagadas.columns:
            # Viene de DateField, será naive Timestamp
            df_pagadas['mes'] = pd.to_datetime(df_pagadas['mes_dt_db'])
            df_pagadas.drop(columns=['mes_dt_db'], inplace=True)
            df_pagadas['total_pagado'] = df_pagadas['total_pagado'].apply(
                lambda x: Decimal(x) if x is not None else Decimal('0.00'))
        else:
            df_pagadas = pd.DataFrame(columns=['mes', 'total_pagado'])
        logger_grafica_52.debug(
            f"df_pagadas procesado head:\n{df_pagadas.head().to_string()}\ndtypes:\n{df_pagadas.dtypes}")

        # Merge y preparación final
        if df_generadas.empty and df_pagadas.empty:
            logger_grafica_52.warning(
                "Ambos DataFrames (generadas y pagadas) están vacíos.")
            return plot(generar_figura_sin_datos("No hay datos de flujo de comisiones."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        if not df_generadas.empty and not df_pagadas.empty:
            df_final = pd.merge(df_generadas, df_pagadas,
                                on='mes', how='outer')
        elif not df_generadas.empty:
            df_final = df_generadas.copy()
            df_final['total_pagado'] = Decimal('0.00')
        elif not df_pagadas.empty:
            df_final = df_pagadas.copy()
            df_final['total_generado'] = Decimal('0.00')
        else:  # No debería llegar aquí
            return plot(generar_figura_sin_datos("Error inesperado al combinar datos de comisiones."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df_final[['total_generado', 'total_pagado']] = df_final[[
            'total_generado', 'total_pagado']].fillna(Decimal('0.00'))
        df_final = df_final.sort_values(by='mes').reset_index(drop=True)

        # Convertir a float para Plotly
        df_final['total_generado_float'] = df_final['total_generado'].astype(
            float)
        df_final['total_pagado_float'] = df_final['total_pagado'].astype(float)

        if 'mes' not in df_final.columns or df_final['mes'].isnull().all():
            logger_grafica_52.warning(
                "Columna 'mes' ausente o toda nula después del merge en grafico_52.")
            return plot(generar_figura_sin_datos("Error procesando fechas para el gráfico de comisiones."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df_final['mes_str'] = df_final['mes'].dt.strftime('%Y-%m')
        logger_grafica_52.debug(
            f"df_final para Plotly head:\n{df_final[['mes_str', 'total_generado_float', 'total_pagado_float']].head().to_string()}")

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_final['mes_str'], y=df_final['total_generado_float'], name='Comisiones Generadas',
            marker_color=COLOR_PALETTE.get('primary'), hovertemplate='<b>Generadas en %{x}:</b> Bs. %{y:,.2f}<extra></extra>'
        ))
        fig.add_trace(go.Bar(
            x=df_final['mes_str'], y=df_final['total_pagado_float'], name='Comisiones Liquidadas',
            marker_color=COLOR_PALETTE.get('success'), hovertemplate='<b>Liquidadas en %{x}:</b> Bs. %{y:,.2f}<extra></extra>'
        ))

        layout_grafico = BASE_LAYOUT.copy()
        layout_grafico['title'] = dict(
            text='Flujo Mensual de Comisiones', x=0.5, font=dict(size=16))
        layout_grafico['barmode'] = 'group'
        layout_grafico['xaxis_title'] = 'Mes'
        layout_grafico['yaxis_title'] = 'Monto Comisiones (Bs.)'
        layout_grafico['xaxis'] = dict(type='category')
        layout_grafico['legend'] = dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        fig.update_layout(**layout_grafico)

        logger_grafica_52.info(
            "==================== grafico_52: FIN - Gráfico generado ====================")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger_grafica_52.error(
            f"Error EXCEPCIONAL en grafico_52: {str(e)}", exc_info=True)
        return plot(generar_figura_sin_datos(f"Error al generar flujo de comisiones ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# --- DATOS TABLA RESUMEN COMISIONES (Esta función es necesaria) ---


def obtener_datos_tabla_resumen_comisiones():
    pendientes = RegistroComision.objects.filter(estatus_pago_comision='PENDIENTE').aggregate(
        total=Coalesce(Sum('monto_comision'), Value(Decimal('0.00')), output_field=DecimalField()))['total']
    pagadas = RegistroComision.objects.filter(estatus_pago_comision='PAGADA').aggregate(
        total=Coalesce(Sum('monto_comision'), Value(Decimal('0.00')), output_field=DecimalField()))['total']
    anuladas = RegistroComision.objects.filter(estatus_pago_comision='ANULADA').aggregate(
        total=Coalesce(Sum('monto_comision'), Value(Decimal('0.00')), output_field=DecimalField()))['total']
    total_registrado = pendientes + pagadas + anuladas
    return {
        'total_registrado_comisiones': total_registrado,
        'total_pagado_comisiones': pagadas,
        'total_pendiente_comisiones': pendientes,
        'total_anulado_comisiones': anuladas,
    }


def generar_figura_sin_datos_plotly(mensaje="No hay datos disponibles"):
    fig = go.Figure()
    fig.add_annotation(text=mensaje, xref="paper", yref="paper", x=0.5,
                       y=0.5, showarrow=False, font={"size": 16, "color": "#888"})
    fig.update_layout(xaxis={'visible': False}, yaxis={
                      'visible': False}, margin=dict(t=10, b=10, l=10, r=10), **BASE_LAYOUT)
    return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def generar_grafico_estados_contrato(data_agregada):
    if not data_agregada:
        return generar_figura_sin_datos_plotly("Estados de contrato no disponibles.")
    colores = [COLOR_PALETTE.get('success'), COLOR_PALETTE.get('danger'), COLOR_PALETTE.get(
        'warning'), COLOR_PALETTE.get('info'), COLOR_PALETTE.get('secondary')]
    fig = go.Figure(data=[go.Pie(labels=list(data_agregada.keys()), values=list(data_agregada.values()), hole=.4, marker_colors=colores,
                    textinfo='percent+label', hoverinfo='label+value+percent', insidetextorientation='radial')])
    layout = BASE_LAYOUT.copy()
    layout['title'] = 'Estado de Contratos'
    layout['showlegend'] = False
    layout['margin'] = dict(t=50, b=0, l=0, r=0)
    fig.update_layout(**layout)
    return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


def generar_grafico_estados_reclamacion(data_agregada):
    if not data_agregada:
        return generar_figura_sin_datos_plotly("Estados de reclamación no disponibles.")
    df = pd.DataFrame(list(data_agregada.items()),
                      columns=['Estado', 'Cantidad'])
    fig = px.bar(df, x='Cantidad', y='Estado', orientation='h', text='Cantidad',
                 color_discrete_sequence=[COLOR_PALETTE.get('secondary')])
    fig.update_traces(texttemplate='%{text}', textposition='outside')
    layout = BASE_LAYOUT.copy()
    layout['title'] = 'Estado de Reclamaciones'
    layout['yaxis'] = {'categoryorder': 'total ascending'}
    layout['xaxis_title'] = "Cantidad"
    layout['yaxis_title'] = None
    layout['margin'] = dict(t=50, b=40, l=150, r=20)
    fig.update_layout(**layout)
    return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


# data_ramos es un dict {'Label Ramo': monto_float}
def generar_grafico_monto_ramo(data_ramos):
    if not data_ramos or not any(v > 0 for v in data_ramos.values()):
        return generar_figura_sin_datos_plotly("No hay montos por ramo disponibles.")
    labels = list(data_ramos.keys())
    values = list(data_ramos.values())
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4, marker_colors=px.colors.qualitative.Pastel, textinfo='percent',
                    insidetextorientation='radial', hoverinfo='label+value+percent', hovertemplate='<b>%{label}</b><br>Monto: Bs. %{value:,.2f}<br>%{percent}<extra></extra>')])
    fig.update_traces(textfont_size=11, marker=dict(
        line=dict(color='#000000', width=1)))
    layout = BASE_LAYOUT.copy()
    layout['title'] = 'Distribución Monto Contratado por Ramo'
    layout['showlegend'] = False
    layout['margin'] = dict(t=60, b=40, l=20, r=20)
    layout['annotations'] = [
        dict(text='Ramos', x=0.5, y=0.5, font_size=18, showarrow=False)]
    fig.update_layout(**layout)
    return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


def generar_grafico_resolucion_gauge(avg_days):
    if avg_days is None:
        avg_days = 0
    max_val = max(avg_days * 1.5, 30)
    fig = go.Figure(go.Indicator(mode="gauge+number", value=float(avg_days), title={'text': "Tiempo Prom. Resolución (Días)"}, number={'suffix': " días", 'valueformat': ".1f"},
                                 gauge={'axis': {'range': [0, max_val]}, 'bar': {'color': COLOR_PALETTE.get('primary')}, 'steps': [{'range': [0, 7], 'color': COLOR_PALETTE.get('success')}, {'range': [7, 15], 'color': COLOR_PALETTE.get('warning')}, {'range': [15, max_val], 'color': COLOR_PALETTE.get('secondary')}]}))
    layout = BASE_LAYOUT.copy()
    layout['height'] = 300
    layout['margin'] = {'t': 70, 'b': 30, 'l': 30, 'r': 30}
    fig.update_layout(**layout)
    return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


# Ahora solo recibe IGTF
def generar_grafico_impuestos_por_categoria(data_igtf_dict):
    if not data_igtf_dict or not data_igtf_dict.get('Categoria') or not data_igtf_dict.get('IGTF') or not data_igtf_dict['Categoria']:
        return generar_figura_sin_datos_plotly("No hay datos de IGTF por categoría.")
    df = pd.DataFrame({'Categoria': data_igtf_dict['Categoria'], 'IGTF': pd.to_numeric(
        data_igtf_dict['IGTF'], errors='coerce').fillna(0.0)})
    df = df[df['IGTF'] > 0].copy()
    if df.empty:
        return generar_figura_sin_datos_plotly("No se recaudó IGTF.")
    total_igtf = df['IGTF'].sum()
    fig = go.Figure(data=[go.Pie(labels=df['Categoria'].tolist(), values=df['IGTF'].tolist(), hole=.45, marker_colors=px.colors.qualitative.Plotly,
                    textinfo='percent', insidetextorientation='radial', hovertemplate='<b>%{label}</b><br>IGTF: Bs. %{value:,.2f}<br>%{percent}<extra></extra>')])
    fig.update_traces(textfont_size=10, marker=dict(
        line=dict(color='#FFFFFF', width=1)))
    layout = BASE_LAYOUT.copy()
    layout['title'] = 'Distribución IGTF por Origen/Ramo'
    layout['showlegend'] = False
    layout['margin'] = dict(t=60, b=40, l=20, r=20)
    layout['annotations'] = [dict(
        text=f'Total IGTF<br>Bs. {total_igtf:,.2f}', x=0.5, y=0.5, font_size=16, showarrow=False)]
    fig.update_layout(**layout)
    return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
