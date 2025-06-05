# graficas.py
from datetime import date  # No necesitas timedelta aquí directamente
from django.utils import timezone
from django.db.models import Count, Case, When, Value, IntegerField, DurationField, F  # Asegurar F
import copy
import copy  # IMPORTANTE
from django.db.models import Count, OuterRef
from django.db.models.functions import ExtractYear, Coalesce
from django.db.models import (
    Case, Value, When, DurationField, BooleanField, ExpressionWrapper, CharField,
    IntegerField, DecimalField, Sum, Avg, Max, Min, Q, F, FloatField, Subquery
)
from django.db.models.functions import Now, TruncMonth, ExtractMonth
from django.http import JsonResponse
from datetime import datetime, timezone, date, timedelta
import plotly.express as px
from dateutil.relativedelta import relativedelta
from plotly.offline import plot
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import time
from django.utils import timezone as django_timezone
import logging
import collections
from decimal import Decimal
from django.core.cache import cache
# Importaciones locales
from myapp.models import (
    ContratoIndividual, AfiliadoIndividual, Reclamacion, Pago,
    ContratoColectivo, Intermediario, Tarifa, Factura, RegistroComision
)
from myapp.forms import CommonChoices


logger = logging.getLogger(__name__)

# Paleta de colores consistente
COLOR_PALETTE = {
    'primary': '#2C3E50', 'secondary': '#E74C3C', 'success': '#27AE60',
    'warning': '#F39C12', 'info': '#3498DB', 'light': '#ECF0F1', 'dark': '#34495E',
}

# Configuración de diseño base para todas las gráficas (RESPONSIVE)
BASE_LAYOUT = {
    'paper_bgcolor': 'rgba(255, 255, 255, 0.85)',
    'plot_bgcolor': 'rgba(255, 255, 255, 0.85)',
    'font': {
        'family': 'Arial, sans-serif',
        'size': 12
    },
    'margin': {
        't': 30, 'l': 35, 'r': 15, 'b': 45
    },
    'autosize': True,  # Habilita autoajuste de tamaño
    'xaxis': {
        'automargin': True,  # Autoajuste de márgenes en X
        'tickangle': -45,    # Ángulo para mejor visualización en móviles
        'title_font': {'size': 10},
        'tickfont': {'size': 8}  # Texto más pequeño para móviles
    },
    'yaxis': {
        'automargin': True,   # Autoajuste de márgenes en Y
        'title_font': {'size': 10},
        'tickfont': {'size': 8}  # Texto más pequeño para móviles
    },
    'legend': {
        'orientation': 'h',  # Horizontal para ahorrar espacio
        'yanchor': 'bottom',
        'y': 1.02,
        'xanchor': 'right',
        'x': 1,
        'bgcolor': 'rgba(255,255,255,0.7)',
        'bordercolor': 'rgba(0,0,0,0.1)',
        'borderwidth': 1,
        'font': {'size': 10},  # Texto de leyenda más pequeño
        'traceorder': 'normal',
        'itemsizing': 'constant'
    },
}

# Configuración global de gráficas (RESPONSIVE)
GRAPH_CONFIG = {
    'displayModeBar': True,
    'responsive': True,      # Habilita comportamiento responsivo
    'autosizable': True,     # Permite redimensionamiento automático
    'displaylogo': False,
    'modeBarButtonsToRemove': ['lasso2d', 'select2d'],  # Optimiza para móviles
}

GRAPH_CACHE_CONFIG = {
    'dynamic': {'timeout': 1800, 'graphs': [4, 5, 7, 9, 11, 29, 31, 39, 40]},
    'moderate': {'timeout': 3600, 'graphs': [1, 2, 3, 6, 8, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 30, 32, 33, 34, 35, 36, 37, 38, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52]},
    'default': {'timeout': 3600}
}

# --- FUNCIONES PRINCIPALES CON MODIFICACIONES RESPONSIVE ---


def obtener_configuracion_graficas(request):
    config = {"glassConfig": copy.deepcopy(
        BASE_LAYOUT), "colors": COLOR_PALETTE.copy()}
    return JsonResponse(config)


def generar_figura_sin_datos(mensaje="No hay datos disponibles"):
    fig = go.Figure()
    fig.add_annotation(
        text=mensaje, xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        font={"size": 16, "color": COLOR_PALETTE.get('secondary', '#E74C3C')}
    )
    layout_actualizado = copy.deepcopy(BASE_LAYOUT)
    layout_actualizado['xaxis']['visible'] = False
    layout_actualizado['yaxis']['visible'] = False
    layout_actualizado['margin'] = dict(
        t=10, b=10, l=10, r=10)  # Márgenes mínimos
    layout_actualizado.pop('legend', None)
    layout_actualizado.pop('title', None)
    fig.update_layout(**layout_actualizado)
    return fig
# Asumo que esta es similar


def generar_figura_sin_datos_plotly(mensaje="No hay datos disponibles"):
    fig = go.Figure()
    fig.add_annotation(text=mensaje, xref="paper", yref="paper", x=0.5, y=0.5,
                       showarrow=False, font={"size": 16, "color": "#888"})
    layout_actualizado = copy.deepcopy(BASE_LAYOUT)
    if 'xaxis' in layout_actualizado:
        layout_actualizado['xaxis']['visible'] = False
    else:
        layout_actualizado['xaxis'] = {'visible': False}
    if 'yaxis' in layout_actualizado:
        layout_actualizado['yaxis']['visible'] = False
    else:
        layout_actualizado['yaxis'] = {'visible': False}
    layout_actualizado['margin'] = dict(t=10, b=10, l=10, r=10)
    layout_actualizado.pop('legend', None)
    layout_actualizado.pop('title', None)
    fig.update_layout(**layout_actualizado)
    return fig


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def validate_graph_html(html_content):
    required_elements = ['plotly-graph-div', 'js-plotly-plot']
    return all(element in html_content for element in required_elements)


def wrap_error_content(error_msg):
    return (f'<div class="plotly-graph-div" style="height:500px; width:100%;">'
            f'<div class="graph-error alert alert-danger">{error_msg}</div></div>')


def get_cached_graph(graph_id, force_refresh=False):
    cache_key = f"graph_{graph_id}"
    config = next(
        (cfg for cfg in GRAPH_CACHE_CONFIG.values()
         if graph_id in cfg.get('graphs', [])),
        GRAPH_CACHE_CONFIG['default']
    )
    if not force_refresh:
        cached_data = cache.get(cache_key)
        if cached_data and validate_graph_html(cached_data.get('html', '')):
            logger.debug(f"Gráfica {graph_id} válida desde caché")
            return {**cached_data, 'from_cache': True}
        if cached_data:
            logger.warning(
                f"Gráfica {graph_id} en caché no válida, regenerando")

    try:
        start_time = time.time()
        graph_func_name = f'grafico_{graph_id:02d}'
        graph_func = globals().get(graph_func_name)
        if not graph_func:
            # Intenta importar tardíamente si no se encontró (útil en algunos setups)
            # from . import graficas_modulo_X # Si estuvieran en otro archivo
            # graph_func = globals().get(graph_func_name)
            # if not graph_func:
            raise ValueError(
                f"Función {graph_func_name} no encontrada en globals()")

        # Generar el HTML de la gráfica. La función grafico_XX ahora devuelve el HTML directamente.
        html_content = graph_func()

        # Validar el HTML generado
        if not validate_graph_html(html_content):
            logger.error(
                f"Gráfica {graph_id} generó HTML inválido: {html_content[:200]}...")
            html_content = wrap_error_content(
                f"Error de estructura en gráfica {graph_id}.")

        result = {
            'html': html_content,
            'generated_at': django_timezone.now(),
            'generation_time': round(time.time() - start_time, 2),
            'from_cache': False,
            'error': None  # Asumimos que no hay error si llegamos aquí y el HTML es válido
        }
        # Solo cachear si el HTML es válido y no es un mensaje de error envuelto
        if validate_graph_html(html_content) and "graph-error" not in html_content:
            cache.set(cache_key, result, config['timeout'])
            logger.info(f"Gráfica {graph_id} almacenada en caché")
        else:
            logger.error(
                f"Gráfica {graph_id} no cacheable. HTML: {html_content[:200]}...")
        return result

    except Exception as e:
        error_msg = f"Excepción al generar gráfica {graph_id}: {type(e).__name__} - {str(e)}"
        logger.error(error_msg, exc_info=True)
        # Devolver un HTML de error consistente
        error_html = wrap_error_content(
            f"Error interno al generar gráfica {graph_id}. Detalles en log.")
        return {
            'html': error_html,
            'generated_at': django_timezone.now(),
            'generation_time': 0,
            'from_cache': False,
            'error': error_msg  # Guardar el mensaje de error real para posible depuración
        }


def clear_graph_cache(graph_id=None):
    if graph_id:
        cache.delete(f"graph_{graph_id}")
        logger.info(f"Caché de gráfica {graph_id} eliminado")
    else:
        for i in range(1, 53):
            cache.delete(f"graph_{i}")
        logger.info("Caché de todas las gráficas eliminado")

# --- INICIO DE FUNCIONES DE GRÁFICAS MODIFICADAS (01-10) ---


def grafico_01():
    try:
        data_ind_qs = ContratoIndividual.objects.values(
            'ramo').annotate(total=Count('id'))
        data_col_qs = ContratoColectivo.objects.values(
            'ramo').annotate(total=Count('id'))
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
            fig_error = generar_figura_sin_datos("No hay contratos")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        ramo_choices = dict(CommonChoices.RAMO)
        df_total['label'] = df_total['ramo'].apply(
            lambda x: ramo_choices.get(x, x or "N/A"))
        fig = go.Figure(data=[go.Pie(
            labels=df_total['label'], values=df_total['total'], hole=0.35,
            marker_colors=px.colors.qualitative.Pastel, textinfo='percent+label',
            hoverinfo='label+value+percent', insidetextorientation='radial',
            pull=[0.05 if i == df_total['total'].idxmax()
                  else 0 for i in df_total.index]
        )])
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Distribución Total de Contratos por Ramo', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['showlegend'] = False
        layout_actualizado['margin'] = {'t': 40, 'b': 20, 'l': 20, 'r': 20}
        if 'xaxis' in layout_actualizado:
            layout_actualizado['xaxis']['visible'] = False
        if 'yaxis' in layout_actualizado:
            layout_actualizado['yaxis']['visible'] = False
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_01: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 01")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_02():
    """Composición de la Cartera de Contratos Individuales por Antigüedad."""
    try:
        hoy = django_timezone.now().date()
        rangos_antiguedad = [
            {'label': 'Nuevos (<6m)', 'min_days': 0, 'max_days': 180},
            {'label': 'Recientes (6m-2a)', 'min_days': 181,
             'max_days': 365 * 2},
            {'label': 'Establecidos (2a-5a)',
             'min_days': (365 * 2) + 1, 'max_days': 365 * 5},
            {'label': 'Antiguos (>5a)', 'min_days': (
                365 * 5) + 1, 'max_days': 99999},
        ]
        contratos_con_antiguedad = ContratoIndividual.objects.filter(
            estatus='VIGENTE', activo=True,
            fecha_inicio_vigencia__isnull=False, fecha_inicio_vigencia__lte=hoy
        ).annotate(
            dias_desde_inicio_vigencia_raw=ExpressionWrapper(
                Value(hoy) - F('fecha_inicio_vigencia'), output_field=DurationField()
            )
        )
        data_para_df = []
        for contrato in contratos_con_antiguedad:
            if contrato.dias_desde_inicio_vigencia_raw:
                dias = contrato.dias_desde_inicio_vigencia_raw.days
                categoria_asignada = 'Otros'
                for rango in rangos_antiguedad:
                    if rango['min_days'] <= dias <= rango['max_days']:
                        categoria_asignada = rango['label']
                        break
                data_para_df.append(
                    {'categoria_antiguedad': categoria_asignada})

        if not data_para_df:
            fig_error = generar_figura_sin_datos(
                "No hay contratos vigentes para analizar por antigüedad.")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(data_para_df)
        df_counts = df['categoria_antiguedad'].value_counts().reset_index()
        df_counts.columns = ['categoria_antiguedad', 'total']
        ordered_labels = [r['label'] for r in rangos_antiguedad] + ['Otros']
        df_counts['categoria_antiguedad'] = pd.Categorical(
            df_counts['categoria_antiguedad'], categories=ordered_labels, ordered=True)
        df_counts = df_counts.sort_values('categoria_antiguedad').dropna(
            subset=['categoria_antiguedad'])

        if df_counts.empty or df_counts['total'].sum() == 0:
            fig_error = generar_figura_sin_datos(
                "No hay datos válidos de antigüedad para mostrar.")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # --- PIE CHART CON AJUSTES PARA TAMAÑO ---
        fig = go.Figure(data=[go.Pie(
            labels=df_counts['categoria_antiguedad'],
            values=df_counts['total'],
            hole=0.35,  # Hueco moderado
            textinfo='percent',  # Mostrar solo porcentaje dentro, etiquetas fuera si es necesario
            hoverinfo='label+value+percent',
            textfont_size=8,  # Tamaño de fuente DENTRO del pie MUY PEQUEÑO
            insidetextorientation='radial',
            marker_colors=px.colors.qualitative.Pastel1,
            # AJUSTE: Definir el dominio que puede ocupar el Pie Chart
            # Esto lo "encoge" dentro del área de la figura.
            # [x0, y0] es la esquina inferior izquierda, [x1, y1] la superior derecha.
            # Valores entre 0 y 1 (fracción del área total del layout).
            # Deja un 10% de margen a cada lado
            domain={'x': [0.1, 0.9], 'y': [0.1, 0.9]}
        )])

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        # Título principal corto y fuente pequeña
        layout_actualizado['title'] = {
            'text': 'Cartera por Antigüedad', 'x': 0.5, 'font': {'size': 10}}

        # La leyenda podría ser útil si las etiquetas del pie son muy pequeñas o se ocultan
        # layout_actualizado['showlegend'] = True
        # if 'legend' in layout_actualizado:
        #    layout_actualizado['legend']['font']['size'] = 8 # Leyenda muy pequeña
        #    layout_actualizado['legend']['y'] = -0.1 # Debajo del gráfico
        #    layout_actualizado['legend']['x'] = 0.5
        #    layout_actualizado['legend']['xanchor'] = 'center'
        # Por ahora, mantenemos sin leyenda
        layout_actualizado['showlegend'] = False

        # Márgenes generales del layout. Si el 'domain' del pie es más pequeño,
        # estos márgenes definirán el espacio alrededor de ese dominio.
        layout_actualizado['margin'] = {'t': 30, 'b': 30, 'l': 20, 'r': 20}

        # Ocultar ejes para Pie Chart
        if 'xaxis' in layout_actualizado:
            layout_actualizado['xaxis']['visible'] = False
        if 'yaxis' in layout_actualizado:
            layout_actualizado['yaxis']['visible'] = False

        # Tamaño de fuente general del layout (afecta a títulos no especificados, etc.)
        layout_actualizado['font']['size'] = 8  # Muy pequeño

        # Oculta texto si es muy pequeño para caber
        layout_actualizado['uniformtext'] = dict(minsize=6, mode='hide')

        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e:
        logger.error(
            f"Error gráfico_02 (antigüedad cartera): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar Gráfico 02 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_03():
    try:
        logger.debug("G03 - Iniciando KPIs Financieros Clave")
        prima_ind_activos = ContratoIndividual.objects.filter(activo=True).aggregate(
            total=Coalesce(Sum('monto_total'), Decimal('0.0')))['total']
        prima_col_activos = ContratoColectivo.objects.filter(activo=True).aggregate(
            total=Coalesce(Sum('monto_total'), Decimal('0.0')))['total']
        prima_emitida_total_activos = prima_ind_activos + prima_col_activos
        siniestros_pagados = Pago.objects.filter(reclamacion__isnull=False, activo=True).aggregate(
            total=Coalesce(Sum('monto_pago'), Decimal('0.0')))['total']
        ratio_siniestralidad_actual = Decimal('0.0')
        if prima_emitida_total_activos > Decimal('0.005'):
            ratio_siniestralidad_actual = (
                siniestros_pagados / prima_emitida_total_activos * 100)
        contratos_activos_count = ContratoIndividual.objects.filter(
            activo=True).count() + ContratoColectivo.objects.filter(activo=True).count()

        fig = make_subplots(rows=1, cols=4, specs=[[{'type': 'indicator'}]*4])
        fig.add_trace(go.Indicator(mode='number', value=float(prima_emitida_total_activos), title={'text': "Prima Cartera Activa", 'font': {
                      'size': 14}}, number={'prefix': "$", 'valueformat': ',.0f'}, domain={'row': 0, 'column': 0}), row=1, col=1)
        fig.add_trace(go.Indicator(mode='number', value=float(siniestros_pagados), title={'text': "Siniestros Pagados (Global)", 'font': {
                      'size': 14}}, number={'prefix': "$", 'valueformat': ',.0f'}, domain={'row': 0, 'column': 1}), row=1, col=2)
        fig.add_trace(go.Indicator(mode='number+delta', value=float(ratio_siniestralidad_actual), title={'text': "Ratio Sinies. (Pag/Prima Activa)", 'font': {'size': 14}}, number={'suffix': "%", 'valueformat': '.1f'}, delta={
                      'reference': 70, 'increasing': {'color': COLOR_PALETTE['secondary']}, 'decreasing': {'color': COLOR_PALETTE['success']}}, domain={'row': 0, 'column': 2}), row=1, col=3)
        fig.add_trace(go.Indicator(mode='number', value=contratos_activos_count, title={'text': "N° Contratos Activos", 'font': {
                      'size': 14}}, number={'valueformat': ',.0f'}, domain={'row': 0, 'column': 3}), row=1, col=4)

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Indicadores Financieros Clave del Negocio', 'x': 0.5, 'font': {'size': 11}}
        # Altura específica para indicadores
        layout_actualizado['height'] = 250
        # Márgenes ajustados para indicadores
        layout_actualizado['margin'] = {'t': 60, 'l': 10, 'r': 10, 'b': 10}
        fig.update_layout(**layout_actualizado)
        logger.info("G03 - KPIs Financieros Clave generados.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error G03 (KPIs Financieros): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar KPIs Financieros ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_04():
    try:
        edades_queryset = (AfiliadoIndividual.objects.annotate(
            edad=ExtractYear(Now()) - ExtractYear('fecha_nacimiento')).order_by('edad'))
        if not edades_queryset.exists():
            fig_error = generar_figura_sin_datos("No hay datos de edades")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        edades = edades_queryset.values_list('edad', flat=True)
        np_edades = np.array(list(filter(None, edades)))
        if np_edades.size == 0:
            fig_error = generar_figura_sin_datos("No hay edades válidas")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        mean_age = np.mean(np_edades)
        hist, bins = np.histogram(np_edades, bins=15, range=(0, 100))
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=bins[:-1], y=hist, marker_color=COLOR_PALETTE['info'], opacity=0.8,
            width=np.diff(bins), hoverinfo='y+text',
            hovertext=[
                f'Rango: {bins[i]}-{bins[i+1]} años' for i in range(len(bins)-1)]
        ))
        fig.add_vline(x=mean_age, line_dash="dot",
                      line_color=COLOR_PALETTE['secondary'], annotation_text=f'Media: {mean_age:.1f} años')

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Distribución de Edades', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Edad'
        layout_actualizado['xaxis']['dtick'] = 10
        layout_actualizado['xaxis']['range'] = [0, 100]
        layout_actualizado['xaxis']['fixedrange'] = True
        layout_actualizado['yaxis']['title_text'] = 'Cantidad de Afiliados'
        layout_actualizado['bargap'] = 0.05
        layout_actualizado['hovermode'] = 'x'
        layout_actualizado['showlegend'] = False
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_04: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar Gráfico 04 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_05():
    try:
        stats = (Reclamacion.objects
                 .filter(tipo_reclamacion='MEDICA', fecha_cierre_reclamo__isnull=False, fecha_reclamo__isnull=False)
                 .annotate(duracion_field=Case(
                     When(fecha_cierre_reclamo__gte=F('fecha_reclamo'), then=ExpressionWrapper(
                         F('fecha_cierre_reclamo') - F('fecha_reclamo'), output_field=DurationField())),
                     default=Value(None), output_field=DurationField()))
                 .filter(duracion_field__isnull=False)
                 .aggregate(promedio=Coalesce(Avg('duracion_field'), timedelta(days=0)),
                            maximo=Coalesce(
                                Max('duracion_field'), timedelta(days=0)),
                            minimo=Coalesce(
                                Min('duracion_field'), timedelta(days=0)),
                            total=Count('id')))
        if not stats['total'] or stats['total'] == 0:
            fig_error = generar_figura_sin_datos(
                "No hay datos de cierre de reclamaciones médicas")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        avg_days = stats['promedio'].days
        max_days = stats['maximo'].days
        min_days = stats['minimo'].days
        # Usar max_days para el delta, pero avg_days para la aguja
        max_gauge_val = max(max_days, avg_days, 1)

        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta", value=avg_days,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Tiempo Promedio Autorización Médica (días)", 'font': {
                'size': 12}},  # Tamaño de fuente ajustado
            delta={'reference': max_gauge_val, 'increasing': {
                # Referencia al valor máximo del gauge
                'color': COLOR_PALETTE['secondary']}},
            gauge={
                # Rango del gauge
                'axis': {'range': [0, max(max_gauge_val + 5, 30)], 'tickwidth': 1},
                'bar': {'color': COLOR_PALETTE['primary'], 'thickness': 0.25},
                'steps': [
                    {'range': [0, max(0, min_days)],
                     'color': COLOR_PALETTE['success']},
                    {'range': [max(0, min_days), avg_days],
                     'color': COLOR_PALETTE['warning']},
                    {'range': [avg_days, max_gauge_val],
                        'color': COLOR_PALETTE['secondary']}
                ],
                'threshold': {'line': {'color': COLOR_PALETTE['dark'], 'width': 4}, 'thickness': 0.8, 'value': avg_days}
            }
        ))
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        # El título ya está en el indicador, así que no lo ponemos en el layout principal
        layout_actualizado.pop('title', None)
        layout_actualizado['height'] = 300  # Altura más compacta para gauges
        layout_actualizado['margin'] = {
            't': 60, 'b': 20, 'l': 20, 'r': 20}  # Márgenes ajustados
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_05: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 05")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_06():
    try:
        hoy = django_timezone.now().date()
        data = (ContratoIndividual.objects
                .annotate(es_moroso=Case(When(fecha_fin_vigencia__lt=hoy, then=Value(True)), default=Value(False), output_field=BooleanField()))
                .values('es_moroso').annotate(total=Count('id')))
        if not data.exists():
            fig_error = generar_figura_sin_datos("No hay datos de morosidad")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        labels = ['Al Día', 'Morosos']
        morosos_count = 0
        al_dia_count = 0
        for item in data:
            if item['es_moroso']:
                morosos_count = item['total']
            else:
                al_dia_count = item['total']
        values = [al_dia_count, morosos_count]

        if sum(values) == 0:
            fig_error = generar_figura_sin_datos(
                "No hay contratos para estado de morosidad")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = go.Figure(data=[go.Pie(
            labels=labels, values=values, hole=0.5,
            marker=dict(colors=[COLOR_PALETTE['success'], COLOR_PALETTE['secondary']], line=dict(
                color=COLOR_PALETTE['light'], width=2)),
            textposition='inside', textinfo='percent+label', insidetextorientation='radial'
        )])
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Estado de Morosidad', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['showlegend'] = False
        layout_actualizado['annotations'] = [dict(
            # Reducido font_size
            text=f'Total: {sum(values)}', x=0.5, y=0.5, font_size=18, showarrow=False)]
        layout_actualizado['margin'] = {'t': 40, 'b': 20, 'l': 20, 'r': 20}
        if 'xaxis' in layout_actualizado:
            layout_actualizado['xaxis']['visible'] = False
        if 'yaxis' in layout_actualizado:
            layout_actualizado['yaxis']['visible'] = False
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_06: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 06")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_07():
    try:
        hoy = django_timezone.now()
        rango_meses_dt = [
            hoy - relativedelta(months=x) for x in range(11, -1, -1)]
        meses_str_base = [m.strftime('%Y-%m') for m in rango_meses_dt]
        data_qs = (Pago.objects.annotate(mes_dt_db=TruncMonth('fecha_pago'))
                   .values('mes_dt_db').annotate(total=Sum('monto_pago'))
                   .filter(total__isnull=False).order_by('mes_dt_db'))
        df_base = pd.DataFrame({'mes_str': meses_str_base})
        df_base['total'] = Decimal('0.00')
        if data_qs.exists():
            df_real = pd.DataFrame(list(data_qs))
            df_real['mes_dt_obj'] = pd.to_datetime(
                df_real['mes_dt_db'], errors='coerce')
            df_real.dropna(subset=['mes_dt_obj'], inplace=True)
            if not df_real.empty:
                df_real['mes_str'] = df_real['mes_dt_obj'].dt.strftime('%Y-%m')
                df_real['total'] = df_real['total'].apply(
                    lambda x: Decimal(x) if x is not None else Decimal('0.00'))
                df_merged = pd.merge(df_base[['mes_str']], df_real[[
                                     'mes_str', 'total']], on='mes_str', how='left')
                df_merged['total'] = df_merged['total'].fillna(Decimal('0.00'))
                df = df_merged
            else:
                df = df_base
        else:
            df = df_base
        if df.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos para la tendencia de pagos.")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df['total_float'] = df['total'].astype(float)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['mes_str'], y=df['total_float'], mode='lines+markers',
            line=dict(color=COLOR_PALETTE.get(
                'primary'), width=3, shape='spline'),
            marker=dict(size=8, color=COLOR_PALETTE.get('secondary')),
            fill='tozeroy', fillcolor=f"rgba{(*hex_to_rgb(COLOR_PALETTE.get('primary')), 0.1)}", name='Monto Pagado'
        ))
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Flujo de Pagos Mensuales', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Mes'
        layout_actualizado['xaxis']['type'] = 'category'
        layout_actualizado['xaxis']['gridcolor'] = '#f0f0f0'
        layout_actualizado['yaxis']['title_text'] = 'Monto Total Pagado'
        layout_actualizado['yaxis']['tickprefix'] = '$'
        layout_actualizado['yaxis']['gridcolor'] = '#f5f5f5'
        layout_actualizado['hoverlabel'] = dict(bgcolor=COLOR_PALETTE.get(
            'dark'), font_size=12, font_color='white')  # Reducido font_size
        layout_actualizado['margin'] = {
            't': 50, 'l': 60, 'r': 30, 'b': 80}  # Ajustado b
        layout_actualizado['showlegend'] = True  # Mostrar leyenda para esta
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar Gráfico 07 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_08():
    try:
        data = (Reclamacion.objects.values(
            'estado').annotate(total=Count('id')))
        if not data.exists():
            fig_error = generar_figura_sin_datos(
                "No hay datos de reclamaciones")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        estado_map = dict(CommonChoices.ESTADO_RECLAMACION)
        df = pd.DataFrame(data)
        df['estado_label'] = df['estado'].map(estado_map).fillna(
            'Desconocido')  # Renombrar para evitar conflicto
        df = df.sort_values('total', ascending=False)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df['estado_label'], y=df['total'], marker_color=COLOR_PALETTE['primary'],
            opacity=0.85, text=df['total'], textposition='auto', texttemplate='%{text:,}',
            hoverinfo='y+name', textfont=dict(color='white')
        ))
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Estado de Reclamaciones', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Estado'
        layout_actualizado['yaxis']['title_text'] = 'Cantidad'
        layout_actualizado['hovermode'] = 'x unified'
        layout_actualizado['clickmode'] = 'event+select'
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_08: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 08")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_09():
    try:
        data_qs = (Reclamacion.objects.filter(contrato_individual__afiliado__fecha_nacimiento__isnull=False)
                   .annotate(edad=ExtractYear(Now()) - ExtractYear('contrato_individual__afiliado__fecha_nacimiento'))
                   .values('edad'))
        if not data_qs.exists():
            fig_error = generar_figura_sin_datos(
                "No hay reclamaciones con edad de afiliado")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        edades = [d['edad'] for d in data_qs if d['edad'] is not None]
        if not edades:
            fig_error = generar_figura_sin_datos(
                "No hay edades válidas para mostrar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        fig = go.Figure(data=[go.Histogram(
            x=edades, marker_color=COLOR_PALETTE.get('secondary'),
            xbins=dict(start=min(edades) if edades else 0,
                       end=max(edades) + 5 if edades else 100, size=5)
        )])
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Distribución de Reclamaciones por Edad del Afiliado', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis'][
            'title_text'] = 'Edad del Afiliado (al momento de la reclamación)'
        layout_actualizado['yaxis']['title_text'] = 'Cantidad de Reclamaciones'
        layout_actualizado['bargap'] = 0.1
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_09: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 09")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_10():
    try:
        data = (Reclamacion.objects.values(
            'tipo_reclamacion').annotate(total=Count('id')))
        if not data.exists():
            fig_error = generar_figura_sin_datos("No hay tipos de reclamación")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        tipo_map = dict(CommonChoices.TIPO_RECLAMACION)
        df = pd.DataFrame(list(data))
        df['tipo_label'] = df['tipo_reclamacion'].map(
            tipo_map).fillna(df['tipo_reclamacion'])  # Renombrar
        df = df.sort_values('total', ascending=False)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df['tipo_label'], y=df['total'], marker_color=COLOR_PALETTE['primary'],
            opacity=0.85, text=df['total'], textposition='auto', texttemplate='%{text:,}',
            # hoverinfo='y+name' es por defecto para bar
            textfont=dict(color='white')
        ))
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Frecuencia de Tipos de Reclamación', 'x': 0.5, 'font': {'size': 11}}
        # tickangle ya en BASE_LAYOUT
        layout_actualizado['xaxis']['title_text'] = 'Tipo de Reclamación'
        layout_actualizado['yaxis']['title_text'] = 'Cantidad'
        layout_actualizado['hovermode'] = 'x unified'
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_10: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 10")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 11: Tiempo Resolución Reclamaciones (Histograma)
# ------------------------------


def grafico_11():
    """Muestra la distribución del tiempo de resolución de reclamaciones en días."""
    try:
        tiempos_qs = (Reclamacion.objects
                      .filter(fecha_cierre_reclamo__isnull=False, fecha_reclamo__isnull=False)
                      .annotate(duracion=Case(
                          When(fecha_cierre_reclamo__gte=F('fecha_reclamo'),
                               then=ExpressionWrapper(F('fecha_cierre_reclamo') - F('fecha_reclamo'), output_field=DurationField())),
                          default=Value(None)))
                      .filter(duracion__isnull=False).values_list('duracion', flat=True))

        if not tiempos_qs:
            fig_error = generar_figura_sin_datos(
                "No hay datos de resolución para mostrar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        dias = [t.days for t in tiempos_qs if t is not None and t.days >= 0]
        if not dias:
            fig_error = generar_figura_sin_datos(
                "No hay duraciones válidas para mostrar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = go.Figure(data=[go.Histogram(
            x=dias, marker_color=COLOR_PALETTE.get('primary'),
            xbins=dict(start=0, end=max(dias) + 10 if dias else 50, size=10)
        )])
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Distribución del Tiempo de Resolución de Reclamaciones', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Días para Resolución'
        layout_actualizado['yaxis']['title_text'] = 'Cantidad de Reclamaciones'
        layout_actualizado['bargap'] = 0.1
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_11: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 11")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 12: Ahorro por Pago Anual (Bar Chart)
# ------------------------------


def grafico_12():
    try:
        data = (Tarifa.objects.values('ramo')
                .annotate(descuento=Sum(F('monto_anual') * Decimal('0.10'), output_field=DecimalField())))
        if not data.exists():
            fig_error = generar_figura_sin_datos(
                "No hay datos de tarifas para ahorro")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Asegurar que descuento no sea None y convertir a float
        y_values = []
        for d in data:
            descuento_val = d.get('descuento')
            y_values.append(float(descuento_val)
                            if descuento_val is not None else 0.0)

        x_values = [d['ramo'] for d in data]

        # Filtrar datos donde y_values sea mayor a 0 para no graficar barras de cero si todos son cero
        filtered_data = [{'x': x, 'y': y} for x, y in zip(
            x_values, y_values) if y > 0.001]  # Pequeña tolerancia

        if not filtered_data:
            fig_error = generar_figura_sin_datos(
                "Ahorro estimado es cero para todos los ramos")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        x_plot = [item['x'] for item in filtered_data]
        y_plot = [item['y'] for item in filtered_data]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=x_plot, y=y_plot,
            marker_color=COLOR_PALETTE['success'], opacity=0.8
        ))
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Ahorro Estimado por Pago Anual', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Ramo'
        layout_actualizado['yaxis']['title_text'] = 'Ahorro Estimado (USD)'
        layout_actualizado['yaxis']['tickprefix'] = '$'
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_12: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 12")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 13: Heatmap Edad vs Cobertura (Ramo)
# ------------------------------


def grafico_13():
    try:
        data = (ContratoIndividual.objects.select_related('afiliado')
                .annotate(
                    edad=ExtractYear(Now()) -
            ExtractYear('afiliado__fecha_nacimiento'),
                    rango_edad=Case(
                        *[When(edad__gte=min_val, edad__lt=max_val, then=Value(f"{min_val}-{max_val}"))
                          for min_val, max_val in [(18, 25), (25, 35), (35, 45), (45, 55), (55, 65)]],
                        # Manejar edades fuera de rango explícitamente
                        default=Value(None),
                        output_field=CharField()
                    )
        )
            # Excluir los que no cayeron en un rango
            .filter(rango_edad__isnull=False)
            .values('rango_edad', 'ramo').annotate(total=Count('id')))

        if not data.exists():
            fig_error = generar_figura_sin_datos(
                "No hay datos para Edad vs Ramo")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(list(data))
        # Mapear códigos de ramo a etiquetas legibles
        ramo_map = dict(CommonChoices.RAMO)
        df['ramo_label'] = df['ramo'].map(ramo_map).fillna(df['ramo'])

        pivot = df.pivot_table(
            index='rango_edad', columns='ramo_label', values='total', fill_value=0)

        if pivot.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos válidos tras pivotar para Edad vs Ramo")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = go.Figure(go.Heatmap(
            x=pivot.columns.tolist(), y=pivot.index.tolist(), z=pivot.values.tolist(),
            colorscale='Viridis', text=pivot.values, texttemplate="%{text}", hoverinfo="x+y+z"
        ))
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Distribución de Contratos por Edad y Ramo', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Ramo'
        layout_actualizado['yaxis']['title_text'] = 'Rango de Edad'
        # layout_actualizado['height'] = 500 # Puedes descomentar si necesitas altura fija
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_13: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 13")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 14: Estado de Continuidad de Contratos del Último Mes Completo
# ------------------------------


def grafico_14():
    try:
        logger.debug(
            "G14_nuevo - Iniciando Estado de Continuidad de Contratos (Último Mes)")
        hoy = date.today()
        primer_dia_mes_actual = hoy.replace(day=1)
        ultimo_dia_mes_anterior = primer_dia_mes_actual - timedelta(days=1)
        primer_dia_mes_anterior = ultimo_dia_mes_anterior.replace(day=1)
        mes_anterior_label = primer_dia_mes_anterior.strftime("%B %Y")

        base_contratos_ind_qs = ContratoIndividual.objects.filter(
            fecha_fin_vigencia__gte=primer_dia_mes_anterior, fecha_fin_vigencia__lte=ultimo_dia_mes_anterior)
        total_podian_continuar_ind = base_contratos_ind_qs.count()
        no_continuaron_ind = base_contratos_ind_qs.filter(
            estatus='VENCIDO').count()
        continuaron_ind = total_podian_continuar_ind - no_continuaron_ind

        base_contratos_col_qs = ContratoColectivo.objects.filter(
            fecha_fin_vigencia__gte=primer_dia_mes_anterior, fecha_fin_vigencia__lte=ultimo_dia_mes_anterior)
        total_podian_continuar_col = base_contratos_col_qs.count()
        no_continuaron_col = base_contratos_col_qs.filter(
            estatus='VENCIDO').count()
        continuaron_col = total_podian_continuar_col - no_continuaron_col

        total_general_podian_continuar = total_podian_continuar_ind + \
            total_podian_continuar_col
        total_general_no_continuaron = no_continuaron_ind + no_continuaron_col
        total_general_continuaron = continuaron_ind + continuaron_col

        if total_general_podian_continuar == 0:
            fig_error = generar_figura_sin_datos(
                f"No hubo contratos finalizando vigencia en {mes_anterior_label}")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        labels_pie = ['Contratos que Continuaron',
                      'Contratos que No Continuaron (Lapsos)']
        values_pie = [total_general_continuaron, total_general_no_continuaron]

        fig = go.Figure(data=[go.Pie(
            labels=labels_pie, values=values_pie, hole=0.3,
            marker_colors=[COLOR_PALETTE.get(
                'success'), COLOR_PALETTE.get('secondary')],
            textinfo='percent+label+value', hoverinfo='label+value+percent', insidetextorientation='radial'
        )])
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {'text': f'Estado de Continuidad (Vencimiento en {mes_anterior_label})', 'x': 0.5, 'font': {
            'size': 10}}  # Título más corto
        layout_actualizado['showlegend'] = True
        layout_actualizado['margin'] = {'t': 60, 'b': 40, 'l': 20, 'r': 20}
        if 'xaxis' in layout_actualizado:
            layout_actualizado['xaxis']['visible'] = False
        if 'yaxis' in layout_actualizado:
            layout_actualizado['yaxis']['visible'] = False
        fig.update_layout(**layout_actualizado)
        logger.info(
            f"G14_nuevo - Gráfico de Continuidad de Contratos generado para {mes_anterior_label}")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error G14_nuevo (Continuidad Contratos): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar Gráfico 14 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 15: Monto Asegurado Promedio y Máximo por Rango de Edad
# ------------------------------


def grafico_15():
    try:
        logger.debug(
            "G15 - Iniciando Monto Asegurado Promedio/Máximo por Rango Edad (Barras)")
        rangos_edad_definidos = [
            (0, 17, '0-17 años'), (18, 25, '18-25 años'), (26, 35, '26-35 años'),
            (36, 45, '36-45 años'), (46, 55, '46-55 años'), (56, 65, '56-65 años'),
            (66, 75, '66-75 años'), (76, 120, '76+ años')]
        when_edad_clauses = [When(edad__gte=min_e, edad__lte=max_e, then=Value(
            lbl)) for min_e, max_e, lbl in rangos_edad_definidos]
        data_qs = (ContratoIndividual.objects
                   .filter(activo=True, afiliado__fecha_nacimiento__isnull=False, monto_total__isnull=False, monto_total__gt=0)
                   .annotate(edad=ExtractYear(Now()) - ExtractYear('afiliado__fecha_nacimiento'),
                             rango_edad_label=Case(*when_edad_clauses, default=Value('Otros'), output_field=CharField()))
                   .exclude(rango_edad_label='Otros').values('rango_edad_label')
                   .annotate(monto_asegurado_promedio=Coalesce(Avg('monto_total'), Value(Decimal('0.0'))),
                             monto_asegurado_maximo=Coalesce(Max('monto_total'), Value(Decimal('0.0'))))
                   .order_by(Case(*[When(rango_edad_label=label, then=Value(i)) for i, (_, _, label) in enumerate(rangos_edad_definidos)])))
        if not data_qs.exists():
            fig_error = generar_figura_sin_datos(
                "No hay contratos individuales con montos y edad para analizar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(list(data_qs))
        df['monto_asegurado_promedio'] = pd.to_numeric(
            df['monto_asegurado_promedio'], errors='coerce').fillna(0.0)
        df['monto_asegurado_maximo'] = pd.to_numeric(
            df['monto_asegurado_maximo'], errors='coerce').fillna(0.0)
        if df.empty or (df['monto_asegurado_promedio'].sum() == 0 and df['monto_asegurado_maximo'].sum() == 0):
            fig_error = generar_figura_sin_datos(
                "No hay datos de montos asegurados válidos tras procesar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df['rango_edad_label'], y=df['monto_asegurado_promedio'], name='Monto Asegurado Promedio', marker_color=COLOR_PALETTE.get(
            'info'), text=df['monto_asegurado_promedio'], texttemplate='$%{text:,.0f}', textposition='auto', hovertemplate="<b>Rango Edad:</b> %{x}<br>Promedio: $%{y:,.0f}<extra></extra>"))
        fig.add_trace(go.Bar(x=df['rango_edad_label'], y=df['monto_asegurado_maximo'], name='Monto Asegurado Máximo', marker_color=COLOR_PALETTE.get(
            'primary'), text=df['monto_asegurado_maximo'], texttemplate='$%{text:,.0f}', textposition='auto', hovertemplate="<b>Rango Edad:</b> %{x}<br>Máximo: $%{y:,.0f}<extra></extra>"))

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            # Título más corto
            'text': 'Monto Asegurado Prom./Max. por Rango Edad (Cont. Ind.)', 'x': 0.5, 'font': {'size': 10}}
        layout_actualizado['xaxis']['title_text'] = 'Rango de Edad del Afiliado'
        layout_actualizado['xaxis']['type'] = 'category'
        layout_actualizado['yaxis']['title_text'] = 'Monto Total Asegurado (USD)'
        layout_actualizado['yaxis']['tickprefix'] = '$'
        layout_actualizado['yaxis']['tickformat'] = ',.0f'
        layout_actualizado['barmode'] = 'group'
        # Ajustar y de leyenda si es necesario
        layout_actualizado['legend']['y'] = 1.1
        # Más espacio abajo para etiquetas X
        layout_actualizado['margin']['b'] = 80
        fig.update_layout(**layout_actualizado)
        logger.info(
            "G15 - Monto Asegurado Prom/Max por Rango Edad (Barras) generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error G15 (Barras Prom/Max): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar Gráfico 15 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_16():
    try:
        N = 10
        logger.debug(f"G16 - Iniciando Desempeño Top {N} Intermediarios")
        siniestros_ind_sub = Subquery(Reclamacion.objects.filter(contrato_individual__intermediario_id=OuterRef('pk'), activo=True, contrato_individual__activo=True).values(
            'contrato_individual__intermediario_id').annotate(total_siniestro=Sum('monto_reclamado')).values('total_siniestro')[:1], output_field=DecimalField())
        siniestros_col_sub = Subquery(Reclamacion.objects.filter(contrato_colectivo__intermediario_id=OuterRef('pk'), activo=True, contrato_colectivo__activo=True).values(
            'contrato_colectivo__intermediario_id').annotate(total_siniestro=Sum('monto_reclamado')).values('total_siniestro')[:1], output_field=DecimalField())
        intermediarios_data_qs = (Intermediario.objects.filter(activo=True)
                                  .annotate(prima_ind=Coalesce(Sum('contratoindividual__monto_total', filter=Q(contratoindividual__activo=True)), Decimal('0.0')),
                                            prima_col=Coalesce(Sum('contratos_colectivos__monto_total', filter=Q(
                                                contratos_colectivos__activo=True)), Decimal('0.0')),
                                            siniestros_ind_calc=Coalesce(
                                                siniestros_ind_sub, Decimal('0.0')),
                                            siniestros_col_calc=Coalesce(siniestros_col_sub, Decimal('0.0')))
                                  .annotate(prima_total_calc=F('prima_ind') + F('prima_col'),
                                            siniestros_total_calc=F(
                                      'siniestros_ind_calc') + F('siniestros_col_calc'),
            comision_estimada_calc=((F('prima_ind') + F('prima_col')) * F('porcentaje_comision') / Decimal('100.0')))
            .filter(prima_total_calc__gt=Decimal('0.005')).order_by('-prima_total_calc')[:N])
        if not intermediarios_data_qs:
            fig_error = generar_figura_sin_datos(
                "No hay datos de intermediarios con primas para G16")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df_data = []
        for inter in intermediarios_data_qs:
            prima_total = inter.prima_total_calc
            siniestros_total = inter.siniestros_total_calc
            comision_estimada = inter.comision_estimada_calc
            resultado_tecnico = prima_total - siniestros_total - comision_estimada
            ratio_resultado_tecnico = (
                resultado_tecnico / prima_total * 100) if prima_total > Decimal('0.005') else Decimal('0.0')
            df_data.append({'nombre_completo': inter.nombre_completo, 'prima_total': float(prima_total), 'siniestros_total': float(siniestros_total), 'comision_estimada': float(
                comision_estimada), 'resultado_tecnico': float(resultado_tecnico), 'ratio_resultado_tecnico': float(ratio_resultado_tecnico)})
        df = pd.DataFrame(df_data)
        if df.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos válidos de intermediarios para G16")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        fig = px.bar(df, y='nombre_completo', x='prima_total', orientation='h', color='ratio_resultado_tecnico',
                     color_continuous_scale=px.colors.diverging.RdYlGn, color_continuous_midpoint=0,
                     labels={'nombre_completo': 'Intermediario', 'prima_total': 'Prima Emitida Total (USD)', 'ratio_resultado_tecnico': 'Margen Técnico Bruto (%)'}, text='prima_total')
        fig.update_traces(texttemplate='$%{text:,.0f}', textposition='auto',
                          customdata=df[['siniestros_total', 'comision_estimada',
                                         'resultado_tecnico', 'ratio_resultado_tecnico']],
                          hovertemplate="<b>Intermediario: %{y}</b><br><br>Prima Emitida Total: $%{x:,.0f}<br>Siniestros Incurridos: $%{customdata[0]:,.0f}<br>Comisión Estimada: $%{customdata[1]:,.0f}<br><b>Resultado Técnico Bruto: $%{customdata[2]:,.0f}</b><br>(Margen Técnico: %{customdata[3]:.1f}%)<extra></extra>")
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': f'Desempeño Top {N} Intermediarios por Prima Emitida', 'x': 0.5, 'font': {'size': 10}}
        layout_actualizado['xaxis']['title_text'] = 'Prima Emitida Total (USD)'
        layout_actualizado['yaxis']['title_text'] = 'Intermediario'
        layout_actualizado['yaxis']['autorange'] = "reversed"
        layout_actualizado['height'] = max(
            400, N * 35 + 120)  # Altura dinámica más ajustada
        layout_actualizado['coloraxis_colorbar_title_text'] = 'Margen (%)'
        layout_actualizado['margin'] = {
            't': 60, 'b': 50, 'l': 200, 'r': 50}  # Ajustado 'l'
        fig.update_layout(**layout_actualizado)
        logger.info(
            "G16 - Desempeño Top Intermediarios (Barras Horizontales) generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error G16 (Desempeño Intermediarios): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar Gráfico 16 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_17():
    try:
        individual = (ContratoIndividual.objects.annotate(mes=TruncMonth(
            'fecha_emision')).values('mes').annotate(total=Sum('monto_total')).order_by('mes'))
        colectivo = (ContratoColectivo.objects.annotate(mes=TruncMonth(
            'fecha_emision')).values('mes').annotate(total=Sum('monto_total')).order_by('mes'))
        df_ind = pd.DataFrame(list(individual)) if individual.exists(
        ) else pd.DataFrame(columns=['mes', 'total'])
        df_col = pd.DataFrame(list(colectivo)) if colectivo.exists(
        ) else pd.DataFrame(columns=['mes', 'total'])

        # Convertir a float para Plotly y manejar None
        if not df_ind.empty:
            df_ind['total'] = pd.to_numeric(
                df_ind['total'], errors='coerce').fillna(0.0)
        if not df_col.empty:
            df_col['total'] = pd.to_numeric(
                df_col['total'], errors='coerce').fillna(0.0)

        if df_ind.empty and df_col.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos para evolución de montos")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = go.Figure()
        if not df_ind.empty:
            fig.add_trace(go.Scatter(x=df_ind['mes'], y=df_ind['total'], name='Individual', line=dict(
                color=COLOR_PALETTE['primary'])))
        if not df_col.empty:
            fig.add_trace(go.Scatter(x=df_col['mes'], y=df_col['total'], name='Colectivo', line=dict(
                color=COLOR_PALETTE['secondary'])))

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Evolución de Montos Contratados', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Mes'
        layout_actualizado['yaxis']['title_text'] = 'Monto Total (USD)'
        layout_actualizado['yaxis']['tickprefix'] = '$'
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_17: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 17")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_18():
    try:
        logger.debug(
            "G18 - Iniciando Ratio Siniestralidad por Rango Edad (Visual Capeado 100%)")
        rangos_edad_definidos = [(0, 17, '0-17'), (18, 25, '18-25'), (26, 35, '26-35'), (36, 45,
                                                                                         '36-45'), (46, 55, '46-55'), (56, 65, '56-65'), (66, 75, '66-75'), (76, 120, '76+')]
        when_edad_clauses = [When(edad__gte=min_e, edad__lte=max_e, then=Value(
            lbl)) for min_e, max_e, lbl in rangos_edad_definidos]
        contratado_por_edad_qs = (ContratoIndividual.objects.filter(activo=True, afiliado__fecha_nacimiento__isnull=False)
                                  .annotate(edad=ExtractYear(Now()) - ExtractYear('afiliado__fecha_nacimiento'), rango_edad_calc=Case(*when_edad_clauses, default=Value('Otro'), output_field=CharField()))
                                  .exclude(rango_edad_calc='Otro').values('rango_edad_calc').annotate(total_contratado_rango=Coalesce(Sum('monto_total'), Value(Decimal('0.0')))))
        dict_contratado = {item['rango_edad_calc']: item['total_contratado_rango']
                           for item in contratado_por_edad_qs}
        reclamado_por_edad_qs = (Reclamacion.objects.filter(contrato_individual__isnull=False, contrato_individual__activo=True, contrato_individual__afiliado__fecha_nacimiento__isnull=False)
                                 .annotate(edad=ExtractYear(Now()) - ExtractYear('contrato_individual__afiliado__fecha_nacimiento'), rango_edad_calc=Case(*when_edad_clauses, default=Value('Otro'), output_field=CharField()))
                                 .exclude(rango_edad_calc='Otro').values('rango_edad_calc').annotate(total_reclamado_rango=Coalesce(Sum('monto_reclamado'), Value(Decimal('0.0')))))
        dict_reclamado = {item['rango_edad_calc']: item['total_reclamado_rango']
                          for item in reclamado_por_edad_qs}
        resultados = []
        labels_ordenados_grafico = [lbl for _, _, lbl in rangos_edad_definidos]
        RATIO_CAP_VISUAL = Decimal('100.0')
        for rango_label in labels_ordenados_grafico:
            contratado = dict_contratado.get(rango_label, Decimal('0.0'))
            reclamado_real = dict_reclamado.get(rango_label, Decimal('0.0'))
            ratio_bruto = (reclamado_real / contratado *
                           100) if contratado > Decimal('0.005') else Decimal('0.0')
            ratio_para_display = min(ratio_bruto, RATIO_CAP_VISUAL)
            texto_en_barra_final = f"{ratio_para_display:.0f}%" + \
                ("+" if ratio_bruto > RATIO_CAP_VISUAL else "")
            resultados.append({'rango': rango_label, 'monto_contratado': contratado, 'monto_reclamado_real': reclamado_real, 'ratio_graficar': float(
                ratio_para_display.quantize(Decimal('0.1'))), 'ratio_real_calculado': float(ratio_bruto.quantize(Decimal('0.1'))), 'texto_barra_display': texto_en_barra_final})
        if not resultados:
            fig_error = generar_figura_sin_datos(
                "No hay datos suficientes para ratio por edad")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(resultados)
        colors = [COLOR_PALETTE.get('dark') if r >= 100 else (COLOR_PALETTE.get('secondary') if r >= 70 else (
            COLOR_PALETTE.get('warning') if r >= 70 * 0.6 else COLOR_PALETTE.get('success'))) for r in df['ratio_real_calculado']]
        fig = go.Figure(data=[go.Bar(x=df['rango'], y=df['ratio_graficar'], marker_color=colors, text=df['texto_barra_display'], textposition='auto',
                                     customdata=np.stack(
                                         (df['monto_contratado'], df['monto_reclamado_real'], df['ratio_real_calculado']), axis=-1),
                                     hovertemplate="<b>Rango Edad: %{x}</b><br>Ratio Siniestralidad (Calculado Real): %{customdata[2]:.1f}%<br>Prima Total: $%{customdata[0]:,.0f}<br>Siniestros Totales: $%{customdata[1]:,.0f}<extra></extra>")])
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {'text': 'Ratio Siniestralidad por Rango de Edad (Visualizado hasta 100%)', 'x': 0.5, 'font': {
            'size': 10}}  # Título más corto
        layout_actualizado['xaxis']['title_text'] = 'Rango de Edad'
        layout_actualizado['xaxis']['type'] = 'category'
        layout_actualizado['yaxis']['title_text'] = 'Ratio Siniestralidad (%)'
        layout_actualizado['yaxis']['ticksuffix'] = '%'
        layout_actualizado['yaxis']['range'] = [
            0, float(RATIO_CAP_VISUAL * Decimal('1.1'))]
        layout_actualizado['margin']['b'] = 80  # Espacio para etiquetas X
        fig.update_layout(**layout_actualizado)
        logger.info(
            "G18 - Gráfico de Ratio Siniestralidad por Edad (Visual Capeado 100%) generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error G18 (Visual Capeado 100%): {e}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar Gráfico 18 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_19():
    try:
        data = (ContratoIndividual.objects.values(
            'estatus').annotate(total=Count('id')).order_by('-total'))
        if not data.exists():
            fig_error = generar_figura_sin_datos(
                "No hay datos de estados de contrato")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        labels = [d['estatus'] for d in data]
        values = [d['total'] for d in data]
        fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.4, marker=dict(
            # Usar solo colores necesarios
            colors=list(COLOR_PALETTE.values())[:len(labels)])))

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Estados de Contratos', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['margin'] = {
            't': 40, 'b': 20, 'l': 20, 'r': 20}  # Ajustar para pie
        if 'xaxis' in layout_actualizado:
            layout_actualizado['xaxis']['visible'] = False
        if 'yaxis' in layout_actualizado:
            layout_actualizado['yaxis']['visible'] = False
        # layout_actualizado['showlegend'] = True # O False, dependiendo de si las etiquetas en el pie son suficientes

        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_19: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 19")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_20():
    try:
        data = (ContratoIndividual.objects.order_by('-monto_total')
                [:10].values('numero_contrato', 'monto_total'))
        if not data.exists():
            fig_error = generar_figura_sin_datos(
                "No hay Contratos Individuales para mostrar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        montos = [float(d['monto_total'] or 0) for d in data]
        numeros = [d['numero_contrato']
                   or f"Contrato ID {i}" for i, d in enumerate(data)]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=numeros, x=montos, orientation='h', marker_color=COLOR_PALETTE.get('primary'),
            text=[f"${m:,.2f}" for m in montos], textposition='auto', hoverinfo='x+y'
        ))
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Top 10 Contratos Individuales por Monto', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Monto Total (USD)'
        layout_actualizado['xaxis']['tickprefix'] = '$'
        layout_actualizado['yaxis']['title_text'] = 'Número de Contrato'
        layout_actualizado['yaxis']['autorange'] = "reversed"
        layout_actualizado['margin'] = {'l': 180, 'r': 20, 't': 50, 'b': 40}
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_20: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 20")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)

# ... (continuación de tu archivo graficas.py, después de grafico_20) ...
# ... (asegúrate de que import copy, BASE_LAYOUT, etc., ya están definidos arriba) ...

# ------------------------------
# Gráfico 21: Tendencia Mensual Ratio Siniestralidad
# ------------------------------


def grafico_21():
    try:
        logger.debug("G21 - Iniciando Tendencia Mensual Ratio Siniestralidad")
        prima_mensual_ind_qs = (ContratoIndividual.objects
                                .filter(activo=True, fecha_emision__isnull=False, monto_total__gt=Decimal('0.00'))
                                .annotate(mes_source=TruncMonth('fecha_emision')).values('mes_source')
                                .annotate(prima_calculada=Sum('monto_total')).order_by('mes_source'))
        df_prima_ind = pd.DataFrame(list(prima_mensual_ind_qs))
        if not df_prima_ind.empty:
            df_prima_ind['mes'] = pd.to_datetime(
                df_prima_ind['mes_source']).dt.normalize().dt.tz_localize(None)
            df_prima_ind.drop(columns=['mes_source'], inplace=True)
        else:
            df_prima_ind = pd.DataFrame(columns=['mes', 'prima_calculada'])

        prima_mensual_col_qs = (ContratoColectivo.objects
                                .filter(activo=True, fecha_emision__isnull=False, monto_total__gt=Decimal('0.00'))
                                .annotate(mes_source=TruncMonth('fecha_emision')).values('mes_source')
                                .annotate(prima_calculada=Sum('monto_total')).order_by('mes_source'))
        df_prima_col = pd.DataFrame(list(prima_mensual_col_qs))
        if not df_prima_col.empty:
            df_prima_col['mes'] = pd.to_datetime(
                df_prima_col['mes_source']).dt.normalize().dt.tz_localize(None)
            df_prima_col.drop(columns=['mes_source'], inplace=True)
        else:
            df_prima_col = pd.DataFrame(columns=['mes', 'prima_calculada'])

        if not df_prima_ind.empty or not df_prima_col.empty:
            df_prima_total_mensual = pd.concat(
                [df_prima_ind, df_prima_col], ignore_index=True)
            if not df_prima_total_mensual.empty and 'prima_calculada' in df_prima_total_mensual.columns:
                prima_agrupada = df_prima_total_mensual.groupby(
                    'mes')['prima_calculada'].sum().reset_index()
                prima_agrupada.rename(
                    columns={'prima_calculada': 'prima_emitida_mes'}, inplace=True)
            else:
                prima_agrupada = pd.DataFrame(
                    columns=['mes', 'prima_emitida_mes'])
        else:
            prima_agrupada = pd.DataFrame(columns=['mes', 'prima_emitida_mes'])
        prima_agrupada['mes'] = pd.to_datetime(
            prima_agrupada['mes'], errors='coerce')
        prima_agrupada = prima_agrupada.dropna(subset=['mes'])

        siniestros_pagados_qs = (Pago.objects
                                 .filter(reclamacion__isnull=False, activo=True, fecha_pago__isnull=False, monto_pago__gt=Decimal('0.00'))
                                 .annotate(mes_source=TruncMonth('fecha_pago')).values('mes_source')
                                 .annotate(siniestros_del_mes=Sum('monto_pago')).order_by('mes_source'))
        df_siniestros = pd.DataFrame(list(siniestros_pagados_qs))
        if not df_siniestros.empty:
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

        if prima_agrupada.empty and siniestros_agrupados.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos de primas ni siniestros para tendencia")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        if prima_agrupada.empty:
            df_merged = siniestros_agrupados.copy()
            df_merged['prima_emitida_mes'] = Decimal('0.0')
        elif siniestros_agrupados.empty:
            df_merged = prima_agrupada.copy()
            df_merged['siniestros_pagados_mes'] = Decimal('0.0')
        else:
            df_merged = pd.merge(
                prima_agrupada, siniestros_agrupados, on='mes', how='outer')
        df_merged[['prima_emitida_mes', 'siniestros_pagados_mes']] = df_merged[[
            'prima_emitida_mes', 'siniestros_pagados_mes']].fillna(Decimal('0.0'))
        df_merged = df_merged.sort_values('mes').reset_index(drop=True)
        df_merged['prima_emitida_mes'] = pd.to_numeric(
            df_merged['prima_emitida_mes'], errors='coerce').fillna(0.0)
        df_merged['siniestros_pagados_mes'] = pd.to_numeric(
            df_merged['siniestros_pagados_mes'], errors='coerce').fillna(0.0)
        df_merged['ratio'] = df_merged.apply(lambda row: (
            row['siniestros_pagados_mes'] / row['prima_emitida_mes'] * 100) if row['prima_emitida_mes'] > 0.005 else 0.0, axis=1)
        if len(df_merged) > 24:
            df_merged = df_merged.tail(24)
        if df_merged.empty or ('mes' in df_merged.columns and df_merged['mes'].isnull().all()):
            fig_error = generar_figura_sin_datos(
                "No hay datos suficientes tras procesar para la tendencia")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df_merged['mes_str'] = df_merged['mes'].dt.strftime('%Y-%m')

        fig = px.line(df_merged, x='mes_str', y='ratio', markers=True, custom_data=[
                      'prima_emitida_mes', 'siniestros_pagados_mes'])
        fig.update_traces(
            line=dict(color=COLOR_PALETTE.get('secondary'), width=3), marker=dict(size=7),
            hovertemplate="<b>Mes:</b> %{x}<br><b>Ratio:</b> %{y:.1f}%<br>Prima Emitida en Mes: $%{customdata[0]:,.0f}<br>Siniestros Pagados en Mes: $%{customdata[1]:,.0f}<extra></extra>"
        )
        fig.add_hline(y=70, line_dash="dot", line_color="red",
                      annotation_text="Límite Ref. 70%", annotation_position="bottom right")

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            # Título más corto
            'text': 'Tendencia Mensual Ratio Siniestralidad (Pagados/Emitida en Mes)', 'x': 0.5, 'font': {'size': 10}}
        layout_actualizado['xaxis']['title_text'] = 'Mes'
        # tickangle ya en BASE_LAYOUT
        layout_actualizado['xaxis']['type'] = 'category'

        max_ratio_val = df_merged['ratio'].max()
        y_axis_upper_limit = 110
        if pd.notna(max_ratio_val) and max_ratio_val > 0:
            y_axis_upper_limit = max(y_axis_upper_limit, max_ratio_val * 1.15)
        layout_actualizado['yaxis']['title_text'] = 'Ratio (%)'
        layout_actualizado['yaxis']['ticksuffix'] = '%'
        layout_actualizado['yaxis']['range'] = [0, y_axis_upper_limit]
        layout_actualizado['hovermode'] = 'x unified'
        # Aumentar margen inferior para etiquetas X y anotación hline
        layout_actualizado['margin']['b'] = 100
        fig.update_layout(**layout_actualizado)
        logger.info("G21 - Tendencia Mensual Ratio Siniestralidad generada.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error crítico en G21: {type(e).__name__} - {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar G21 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_22():
    try:
        montos_qs = (Reclamacion.objects.filter(monto_reclamado__isnull=False,
                     monto_reclamado__gt=0).values_list('monto_reclamado', flat=True))
        if not montos_qs:
            fig_error = generar_figura_sin_datos("No hay montos reclamados")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        montos = [float(m) for m in montos_qs]
        if not montos:
            fig_error = generar_figura_sin_datos("No hay montos válidos")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        fig = go.Figure(data=[go.Histogram(
            x=montos, marker_color=COLOR_PALETTE.get('secondary'), nbinsx=20)])

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Distribución de Montos Reclamados', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Monto Reclamado (USD)'
        layout_actualizado['xaxis']['tickprefix'] = '$'
        layout_actualizado['yaxis']['title_text'] = 'Cantidad de Reclamaciones'
        layout_actualizado['bargap'] = 0.05
        # layout_actualizado['margin'] = {'t': 50, 'b': 40, 'l': 50, 'r': 30} # Márgenes ya en BASE_LAYOUT, ajustar si es necesario
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error G22(nuevo): {e}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error G22")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_23():
    try:
        logger.debug(
            "G23 - Iniciando Prima vs Siniestros por Rango Edad (Barras Horizontales)")
        rangos_edad_definidos = [(0, 17, '0-17 años'), (18, 25, '18-25 años'), (26, 35, '26-35 años'), (36, 45, '36-45 años'),
                                 (46, 55, '46-55 años'), (56, 65, '56-65 años'), (66, 75, '66-75 años'), (76, 120, '76+ años')]
        when_edad_clauses = [When(edad__gte=min_e, edad__lte=max_e, then=Value(
            lbl)) for min_e, max_e, lbl in rangos_edad_definidos]
        prima_por_edad_qs = (ContratoIndividual.objects.filter(activo=True, afiliado__fecha_nacimiento__isnull=False, monto_total__gt=Decimal('0.00'))
                             .annotate(edad=ExtractYear(Now()) - ExtractYear('afiliado__fecha_nacimiento'), rango_edad_label=Case(*when_edad_clauses, default=Value('Otros'), output_field=CharField()))
                             .exclude(rango_edad_label='Otros').values('rango_edad_label').annotate(total_prima_rango=Coalesce(Sum('monto_total'), Decimal('0.0')))
                             .order_by(Case(*[When(rango_edad_label=label, then=Value(i)) for i, (_, _, label) in enumerate(rangos_edad_definidos)])))
        df_prima = pd.DataFrame(list(prima_por_edad_qs))
        if df_prima.empty:
            df_prima = pd.DataFrame(
                columns=['rango_edad_label', 'total_prima_rango'])
        siniestros_por_edad_qs = (Reclamacion.objects.filter(contrato_individual__isnull=False, contrato_individual__activo=True, contrato_individual__afiliado__fecha_nacimiento__isnull=False, monto_reclamado__gt=Decimal('0.00'))
                                  .annotate(edad=ExtractYear(Now()) - ExtractYear('contrato_individual__afiliado__fecha_nacimiento'), rango_edad_label=Case(*when_edad_clauses, default=Value('Otros'), output_field=CharField()))
                                  .exclude(rango_edad_label='Otros').values('rango_edad_label').annotate(total_siniestro_rango=Coalesce(Sum('monto_reclamado'), Decimal('0.0')))
                                  .order_by(Case(*[When(rango_edad_label=label, then=Value(i)) for i, (_, _, label) in enumerate(rangos_edad_definidos)])))
        df_siniestro = pd.DataFrame(list(siniestros_por_edad_qs))
        if df_siniestro.empty:
            df_siniestro = pd.DataFrame(
                columns=['rango_edad_label', 'total_siniestro_rango'])
        if df_prima.empty and df_siniestro.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos de primas ni siniestros por edad para G23")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df_merged = pd.merge(df_prima, df_siniestro,
                             on='rango_edad_label', how='outer')
        df_merged[['total_prima_rango', 'total_siniestro_rango']] = df_merged[[
            'total_prima_rango', 'total_siniestro_rango']].fillna(Decimal('0.0'))
        rango_order = [lbl for _, _, lbl in rangos_edad_definidos]
        df_merged['rango_edad_label'] = pd.Categorical(
            df_merged['rango_edad_label'], categories=rango_order, ordered=True)
        df_merged = df_merged.sort_values('rango_edad_label')
        df_merged = df_merged[(df_merged['total_prima_rango'] > 0) | (
            df_merged['total_siniestro_rango'] > 0)]
        if df_merged.empty:
            fig_error = generar_figura_sin_datos(
                "No hay actividad significativa de primas o siniestros por edad para G23")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df_merged['total_prima_float'] = pd.to_numeric(
            df_merged['total_prima_rango'], errors='coerce').fillna(0.0)
        df_merged['total_siniestro_float'] = pd.to_numeric(
            df_merged['total_siniestro_rango'], errors='coerce').fillna(0.0)
        fig = go.Figure()
        fig.add_trace(go.Bar(y=df_merged['rango_edad_label'], x=df_merged['total_prima_float'], name='Prima Emitida Total', orientation='h', marker_color=COLOR_PALETTE.get(
            'success'), text=df_merged['total_prima_float'], texttemplate='$%{text:,.0f}', textposition='auto', hovertemplate="<b>Rango Edad: %{y}</b><br>Prima Emitida: $%{x:,.0f}<extra></extra>"))
        fig.add_trace(go.Bar(y=df_merged['rango_edad_label'], x=df_merged['total_siniestro_float'], name='Siniestros Incurridos Totales', orientation='h', marker_color=COLOR_PALETTE.get(
            'secondary'), text=df_merged['total_siniestro_float'], texttemplate='$%{text:,.0f}', textposition='auto', hovertemplate="<b>Rango Edad: %{y}</b><br>Siniestros Incurridos: $%{x:,.0f}<extra></extra>"))

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {'text': 'Prima vs. Siniestros por Rango Edad (Cont. Ind.)', 'x': 0.5, 'font': {
            'size': 10}}  # Título más corto
        layout_actualizado['yaxis']['title_text'] = 'Rango de Edad del Afiliado'
        layout_actualizado['yaxis']['type'] = 'category'
        layout_actualizado['xaxis']['title_text'] = 'Monto Total (USD)'
        layout_actualizado['xaxis']['tickprefix'] = '$'
        layout_actualizado['xaxis']['tickformat'] = ',.0f'
        layout_actualizado['barmode'] = 'group'
        # layout_actualizado['legend']['y'] = 1.02 # yanchor y xanchor ya en BASE_LAYOUT
        layout_actualizado['height'] = max(400, len(df_merged['rango_edad_label'].unique(
        )) * 40 + 150)  # Ajustar multiplicador si es necesario
        layout_actualizado['margin']['l'] = 120  # Más espacio para etiquetas Y
        fig.update_layout(**layout_actualizado)
        logger.info(
            "G23 - Prima vs Siniestros por Rango Edad (Barras Horizontales) generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error G23 (Barras Horizontales Edad): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar Gráfico 23 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_24():
    try:
        data = (ContratoColectivo.objects.annotate(year=ExtractYear(
            'fecha_emision')).values('year').annotate(total=Count('id')).order_by('year'))
        if not data.exists():
            fig_error = generar_figura_sin_datos(
                "No hay datos de contratos colectivos")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(list(data))
        # Para que se trate como categoría en el eje X
        df['year'] = df['year'].astype(str)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['year'], y=df['total'], mode='lines+markers', line=dict(color=COLOR_PALETTE['secondary'])))

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Contratos Colectivos por Año', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Año'
        # Asegurar que sea categórico
        layout_actualizado['xaxis']['type'] = 'category'
        layout_actualizado['yaxis']['title_text'] = 'N° Contratos'
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_24: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 24")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_25():
    try:
        N_INTERMEDIARIOS = 15
        logger.debug(
            f"G25 - Iniciando Rendimiento Intermediarios (Top {N_INTERMEDIARIOS})")
        data_qs = (Intermediario.objects.filter(activo=True)
                   .annotate(
                       count_contratos_ind=Count('contratoindividual', filter=Q(
                           contratoindividual__activo=True), distinct=True),
                       count_contratos_col=Count('contratos_colectivos', filter=Q(
                           contratos_colectivos__activo=True), distinct=True),
                       comisiones_ind=Coalesce(Sum(F('contratoindividual__monto_total') * F('porcentaje_comision') / Decimal('100.0'), filter=Q(
                           contratoindividual__activo=True, contratoindividual__monto_total__isnull=False)), Value(Decimal('0.0')), output_field=DecimalField()),
                       comisiones_col=Coalesce(Sum(F('contratos_colectivos__monto_total') * F('porcentaje_comision') / Decimal('100.0'), filter=Q(contratos_colectivos__activo=True, contratos_colectivos__monto_total__isnull=False)), Value(Decimal('0.0')), output_field=DecimalField()))
                   .annotate(total_contratos_intermediario=F('count_contratos_ind') + F('count_contratos_col'), comision_total_intermediario=F('comisiones_ind') + F('comisiones_col'))
                   .filter(Q(total_contratos_intermediario__gt=0) | Q(comision_total_intermediario__gt=Decimal('0.005')))
                   .order_by('-comision_total_intermediario')[:N_INTERMEDIARIOS])
        if not data_qs:
            fig_error = generar_figura_sin_datos(
                "No hay datos de actividad de intermediarios para G25")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df_data = [{'nombre_intermediario': d.nombre_completo, 'comisiones': float(
            d.comision_total_intermediario or 0), 'contratos': int(d.total_contratos_intermediario or 0)} for d in data_qs]
        df = pd.DataFrame(df_data)
        if df.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos válidos tras procesar para Gráfico 25")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=df['nombre_intermediario'], y=df['comisiones'], name='Comisiones Estimadas', marker_color=COLOR_PALETTE.get(
            'primary'), text=df['comisiones'], texttemplate='$%{text:,.0f}', textposition='auto', hovertemplate="<b>%{x}</b><br>Comisiones: $%{y:,.0f}<extra></extra>"), secondary_y=False)
        fig.add_trace(go.Scatter(x=df['nombre_intermediario'], y=df['contratos'], name='N° Contratos Activos', mode='lines+markers', line=dict(color=COLOR_PALETTE.get(
            'success'), width=3), marker=dict(size=8, symbol='circle'), hovertemplate="<b>%{x}</b><br>N° Contratos: %{y}<extra></extra>"), secondary_y=True)

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': f'Top {N_INTERMEDIARIOS} Intermediarios: Comisiones y N° Contratos', 'x': 0.5, 'font': {'size': 10}}
        layout_actualizado['xaxis']['title_text'] = 'Intermediario'
        # tickangle ya en BASE_LAYOUT
        layout_actualizado['xaxis']['type'] = 'category'
        layout_actualizado['yaxis']['title_text'] = 'Comisiones Estimadas (USD)'
        layout_actualizado['yaxis']['tickprefix'] = '$'
        layout_actualizado['yaxis']['side'] = 'left'
        layout_actualizado['yaxis']['showgrid'] = True
        layout_actualizado['yaxis']['gridcolor'] = COLOR_PALETTE.get(
            'light', '#ECF0F1')
        layout_actualizado['yaxis2'] = {'title_text': 'Número de Contratos Activos',
                                        'side': 'right', 'overlaying': 'y', 'showgrid': False, 'rangemode': 'tozero'}
        # Ajustar leyenda para que no se solape con etiquetas X rotadas
        layout_actualizado['legend']['y'] = -0.5
        layout_actualizado['legend']['x'] = 0.5
        layout_actualizado['legend']['xanchor'] = 'center'
        # Más espacio para etiquetas X y leyenda
        layout_actualizado['margin']['b'] = 150
        fig.update_layout(**layout_actualizado)
        logger.info(
            "G25 - Rendimiento Intermediarios (Barras Ejes Secundarios) generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error G25 (Barras Ejes Secundarios): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar Gráfico 25 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_26():
    try:
        N = 15
        top_reclamaciones = (Reclamacion.objects.filter(estado__in=['APROBADA', 'PAGADA'], monto_reclamado__isnull=False)
                             .select_related('contrato_individual', 'contrato_colectivo')
                             .order_by('-monto_reclamado')[:N])
        if not top_reclamaciones:
            fig_error = generar_figura_sin_datos(
                "No hay reclamaciones Aprob/Pagadas")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        labels = []
        montos = []
        for rec in top_reclamaciones:
            contrato_str = ""
            if rec.contrato_individual and rec.contrato_individual.numero_contrato:
                contrato_str = f"CI: {rec.contrato_individual.numero_contrato}"
            elif rec.contrato_colectivo and rec.contrato_colectivo.numero_contrato:
                contrato_str = f"CC: {rec.contrato_colectivo.numero_contrato}"

            # Etiqueta un poco más corta: ID + (Tipo Contrato: Numero)
            label_texto = f"ID {rec.pk}"
            if contrato_str:
                # Solo "CI" o "CC"
                label_texto += f" ({contrato_str.split(':')[0]})"
            # Considerar si las etiquetas son demasiado largas
            labels.append(label_texto)
            montos.append(float(rec.monto_reclamado))

        fig = go.Figure(data=[go.Bar(
            y=labels,
            x=montos,
            orientation='h',
            marker_color=COLOR_PALETTE.get('danger'),
            text=[f"${m:,.0f}" for m in montos],
            textposition='auto',  # 'auto' o 'outside'
            hoverinfo='x+y'
        )])

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': f'Top {N} Reclamaciones (Aprob/Pagadas) por Monto', 'x': 0.5, 'font': {'size': 10}}

        layout_actualizado['xaxis']['title_text'] = 'Monto Reclamado (USD)'
        layout_actualizado['xaxis']['tickprefix'] = '$'

        layout_actualizado['yaxis']['title_text'] = 'Reclamación'
        layout_actualizado['yaxis']['autorange'] = "reversed"
        layout_actualizado['yaxis']['tickfont'] = {
            'size': 7}  # Etiquetas Y más pequeñas

        # Ajustar márgenes
        # Reducido drásticamente, dependerá de la longitud de las nuevas etiquetas Y
        layout_actualizado['margin']['l'] = 80
        layout_actualizado['margin']['r'] = 20
        layout_actualizado['margin']['t'] = 40
        layout_actualizado['margin']['b'] = 40

        # Altura dinámica AJUSTADA
        # Probar con un factor más pequeño por ítem, y una base menor.
        # El '+ 100' es para el título, márgenes superior/inferior, y título del eje X.
        # El 'N * 20' es 20px por cada barra/etiqueta.
        altura_base_grafica = 100  # Para títulos, márgenes, etc.
        # Espacio vertical por barra (incluye padding entre barras)
        altura_por_barra = 22
        altura_minima_total = 280  # Una altura mínima razonable

        layout_actualizado['height'] = max(
            altura_minima_total, N * altura_por_barra + altura_base_grafica)

        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error G26(nuevo): {e}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error G26")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_27():
    try:
        data_qs = (Reclamacion.objects.filter(fecha_cierre_reclamo__isnull=False, fecha_reclamo__isnull=False)
                   .annotate(duracion=Case(When(fecha_cierre_reclamo__gte=F('fecha_reclamo'), then=ExpressionWrapper(F('fecha_cierre_reclamo') - F('fecha_reclamo'), output_field=DurationField())), default=Value(None)))
                   .filter(duracion__isnull=False).values('tipo_reclamacion')
                   .annotate(tiempo_promedio_td=Avg('duracion')).order_by('-tiempo_promedio_td'))
        if not data_qs:
            fig_error = generar_figura_sin_datos(
                "No hay datos de resolución para mostrar por tipo")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(list(data_qs))
        df['dias_promedio'] = df['tiempo_promedio_td'].apply(
            lambda x: x.total_seconds() / (24 * 3600) if pd.notnull(x) else 0)
        tipo_map = dict(CommonChoices.TIPO_RECLAMACION)
        df['tipo_label'] = df['tipo_reclamacion'].map(
            tipo_map).fillna(df['tipo_reclamacion'])
        fig = px.bar(df, x='tipo_label', y='dias_promedio', text='dias_promedio',
                     color='dias_promedio', color_continuous_scale=px.colors.sequential.Reds)
        fig.update_traces(texttemplate='%{text:.1f}d', textposition='outside')

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Tiempo Promedio de Resolución por Tipo de Reclamación', 'x': 0.5, 'font': {'size': 10}}
        # tickangle ya en BASE_LAYOUT
        layout_actualizado['xaxis']['title_text'] = 'Tipo de Reclamación'
        layout_actualizado['yaxis']['title_text'] = 'Tiempo Promedio (Días)'
        # Ocultar barra de color si ocupa mucho
        layout_actualizado['coloraxis_showscale'] = False
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_27: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 27")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_28():
    try:
        data = (Reclamacion.objects.values(
            'tipo_reclamacion', 'estado').annotate(total=Count('id')))
        if not data.exists():
            fig_error = generar_figura_sin_datos(
                "No hay datos de reclamaciones por tipo y estado")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(list(data))

        # Mapear códigos a etiquetas
        tipo_map = dict(CommonChoices.TIPO_RECLAMACION)
        estado_map = dict(CommonChoices.ESTADO_RECLAMACION)
        df['tipo_reclamacion_label'] = df['tipo_reclamacion'].map(
            tipo_map).fillna(df['tipo_reclamacion'])
        df['estado_label'] = df['estado'].map(estado_map).fillna(df['estado'])

        pivot = df.pivot_table(index='tipo_reclamacion_label',
                               columns='estado_label', values='total', fill_value=0)
        if pivot.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos válidos tras pivotar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = go.Figure(go.Heatmap(
            x=pivot.columns.tolist(), y=pivot.index.tolist(), z=pivot.values.tolist(),
            colorscale='Viridis', text=pivot.values, texttemplate="%{text}", hoverinfo="x+y+z"
        ))
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Reclamaciones por Tipo y Estado', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Estado'
        layout_actualizado['yaxis']['title_text'] = 'Tipo de Reclamación'
        # layout_actualizado['height'] = 500 # Descomentar si se necesita altura fija
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_28: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 28")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_29():
    try:
        hoy = date.today()
        contratos_con_antiguedad = (ContratoIndividual.objects.filter(fecha_inicio_vigencia__isnull=False)
                                    .annotate(antiguedad_anos=Case(When(fecha_inicio_vigencia__lte=hoy, then=ExtractYear(Value(hoy)) - ExtractYear('fecha_inicio_vigencia')), default=Value(0), output_field=IntegerField()))
                                    .filter(antiguedad_anos__gte=0))
        avg_monto_reclamado_subquery = (Reclamacion.objects.filter(contrato_individual=OuterRef('pk'), monto_reclamado__isnull=False, monto_reclamado__gt=0)
                                        .values('contrato_individual').annotate(avg_monto=Avg('monto_reclamado')).values('avg_monto')[:1])
        data_qs = (contratos_con_antiguedad.annotate(monto_prom_reclamado=Subquery(avg_monto_reclamado_subquery, output_field=DecimalField()))
                   .filter(monto_prom_reclamado__isnull=False).values('antiguedad_anos')
                   .annotate(monto_promedio_final=Avg('monto_prom_reclamado')).order_by('antiguedad_anos'))
        if not data_qs:
            fig_error = generar_figura_sin_datos(
                "No hay datos suficientes para G29")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(list(data_qs))
        df['monto_prom_float'] = pd.to_numeric(
            df['monto_promedio_final'], errors='coerce').fillna(0.0)
        df['antiguedad_anos'] = pd.to_numeric(
            df['antiguedad_anos'], errors='coerce').fillna(0).astype(int)
        df = df.sort_values('antiguedad_anos')
        # Chequear si hay valores para graficar
        if df.empty or df['monto_prom_float'].sum() == 0:
            fig_error = generar_figura_sin_datos(
                "No hay datos válidos para G29")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = px.line(df, x='antiguedad_anos',
                      y='monto_prom_float', markers=True)
        fig.update_traces(line=dict(color=COLOR_PALETTE.get(
            'success'), width=2), marker=dict(size=7))

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Monto Prom. Reclamado vs. Antigüedad Contrato (Ind.)', 'x': 0.5, 'font': {'size': 10}}
        layout_actualizado['xaxis']['title_text'] = 'Antigüedad Contrato (Años)'
        layout_actualizado['xaxis']['dtick'] = 1  # Mostrar cada año
        layout_actualizado['yaxis']['title_text'] = 'Monto Prom. Reclamado (USD)'
        layout_actualizado['yaxis']['tickprefix'] = '$'
        layout_actualizado['hovermode'] = 'x unified'
        # layout_actualizado['margin'] = {'t': 60, 'l': 60, 'r': 30, 'b': 50} # Ajustar si es necesario
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error G29(nuevo): {e}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error G29")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_30():
    try:
        montos_qs = (Reclamacion.objects.filter(activo=True, monto_reclamado__isnull=False,
                     monto_reclamado__gt=0).values_list('monto_reclamado', flat=True))
        if not montos_qs:
            fig_error = generar_figura_sin_datos(
                "No hay montos de siniestros para analizar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        montos = [float(m) for m in montos_qs]
        if not montos:
            fig_error = generar_figura_sin_datos(
                "No hay montos válidos para mostrar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        fig = go.Figure(data=[go.Histogram(
            x=montos, marker_color=COLOR_PALETTE.get('secondary'), autobinx=True)])

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Distribución de Montos de Siniestros Incurridos', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Monto Siniestro Incurrido (USD)'
        layout_actualizado['xaxis']['tickprefix'] = '$'
        layout_actualizado['yaxis']['title_text'] = 'Cantidad de Siniestros'
        layout_actualizado['bargap'] = 0.05
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error gráfico_30 (Reemplazo Distribución Siniestros): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            "Error al generar distribución de siniestros")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


# ------------------------------
# Gráfico 31: Distribución de Pagos por Forma (Últimos N Meses)
# ------------------------------
# Mantener logger específico si lo usas
logger_grafica_31 = logging.getLogger("myapp.graficas.grafico_31")


def grafico_31():
    try:
        N_MESES_ATRAS = 6
        hoy = django_timezone.now().date()
        fecha_inicio_periodo = hoy - relativedelta(months=N_MESES_ATRAS)
        fecha_inicio_periodo = fecha_inicio_periodo.replace(day=1)
        logger_grafica_31.debug(
            f"Periodo para gráfico 31: Desde {fecha_inicio_periodo} hasta {hoy}")

        pagos_periodo_qs = (Pago.objects.filter(activo=True, fecha_pago__gte=fecha_inicio_periodo, fecha_pago__lte=hoy)
                            .values('forma_pago')
                            .annotate(cantidad_pagos=Count('id'),
                                      monto_total_pagado=Coalesce(Sum('monto_pago'), Value(Decimal('0.0')), output_field=DecimalField()))
                            .order_by('-monto_total_pagado'))
        if not pagos_periodo_qs.exists():
            fig_error = generar_figura_sin_datos_plotly(
                # Usar la función correcta
                f"No hay datos de pagos en los últimos {N_MESES_ATRAS} meses.")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df_data = []
        forma_pago_map = dict(CommonChoices.FORMA_PAGO_RECLAMACION)
        for item in pagos_periodo_qs:
            forma_pago_label = forma_pago_map.get(
                item['forma_pago'], item['forma_pago'] or "Desconocida")
            df_data.append({'Forma de Pago': forma_pago_label, 'Cantidad de Pagos': item['cantidad_pagos'],
                            'Monto Total Pagado': float(item['monto_total_pagado'])})
        df = pd.DataFrame(df_data)
        if df.empty:
            fig_error = generar_figura_sin_datos_plotly(
                "No hay datos válidos para mostrar.")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=df['Forma de Pago'], y=df['Monto Total Pagado'], name='Monto Total Pagado ($)', marker_color=COLOR_PALETTE.get(
            'primary'), text=df['Monto Total Pagado'], texttemplate='$%{text:,.0f}', textposition='auto', hovertemplate="<b>%{x}</b><br>Monto Total: $%{y:,.0f}<extra></extra>"), secondary_y=False)
        fig.add_trace(go.Scatter(x=df['Forma de Pago'], y=df['Cantidad de Pagos'], name='Cantidad de Pagos', mode='lines+markers', line=dict(
            color=COLOR_PALETTE.get('success'), width=2), marker=dict(size=7), hovertemplate="<b>%{x}</b><br>Cantidad: %{y}<extra></extra>"), secondary_y=True)

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {'text': f'Pagos por Forma (Últimos {N_MESES_ATRAS} Meses)', 'x': 0.5, 'font': {
            'size': 10}}  # Título más corto
        layout_actualizado['xaxis']['title_text'] = 'Forma de Pago'
        layout_actualizado['xaxis']['type'] = 'category'
        layout_actualizado['yaxis']['title_text'] = 'Monto Total Pagado ($)'
        layout_actualizado['yaxis']['side'] = 'left'
        layout_actualizado['yaxis']['tickprefix'] = '$'
        layout_actualizado['yaxis2'] = {'title_text': 'Cantidad de Pagos', 'side': 'right', 'overlaying': 'y', 'showgrid': False, 'rangemode': 'tozero', 'title_font': {
            'size': BASE_LAYOUT['yaxis']['title_font']['size']}, 'tickfont': {'size': BASE_LAYOUT['yaxis']['tickfont']['size']}}
        layout_actualizado['legend']['y'] = 1.1  # Ajustar leyenda
        layout_actualizado['margin'] = {
            't': 70, 'b': 80, 'l': 70, 'r': 80}  # Ajustar márgenes
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger_grafica_31.error(
            f"Error EXCEPCIONAL en grafico_31: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos_plotly(
            f"Error al generar Gráfico 31 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_32():
    try:
        data = (Tarifa.objects.values('ramo').annotate(promedio=Avg(
            'monto_anual'), maximo=Max('monto_anual'), minimo=Min('monto_anual')))
        if not data.exists():
            fig_error = generar_figura_sin_datos("No hay datos de tarifas")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(list(data))
        # Convertir a float y manejar None
        df['promedio'] = pd.to_numeric(
            df['promedio'], errors='coerce').fillna(0.0)
        df['maximo'] = pd.to_numeric(df['maximo'], errors='coerce').fillna(0.0)
        df['minimo'] = pd.to_numeric(df['minimo'], errors='coerce').fillna(0.0)

        if df.empty or (df['promedio'].sum() == 0 and df['maximo'].sum() == 0 and df['minimo'].sum() == 0):
            fig_error = generar_figura_sin_datos(
                "No hay datos válidos de tarifas para mostrar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = go.Figure()
        fig.add_trace(go.Bar(x=df['ramo'], y=df['promedio'],
                      name='Promedio', marker_color=COLOR_PALETTE['primary']))
        fig.add_trace(go.Scatter(x=df['ramo'], y=df['maximo'], mode='markers', name='Máximo', marker=dict(
            color=COLOR_PALETTE['secondary'], size=10)))
        fig.add_trace(go.Scatter(x=df['ramo'], y=df['minimo'], mode='markers', name='Mínimo', marker=dict(
            color=COLOR_PALETTE['success'], size=10)))

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Comparación de Tarifas por Ramo', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Ramo'
        layout_actualizado['yaxis']['title_text'] = 'Monto Anual'
        layout_actualizado['yaxis']['tickprefix'] = '$'
        layout_actualizado['barmode'] = 'group'
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_32: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 32")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_33():
    try:
        data = (ContratoIndividual.objects.select_related('afiliado')
                .annotate(edad=ExtractYear(Now()) - ExtractYear('afiliado__fecha_nacimiento'),
                          rango_etario=Case(*[When(edad__gte=min_val, edad__lt=max_val, then=Value(f"{min_val}-{max_val}"))
                                            for min_val, max_val in [(18, 25), (25, 35), (35, 45), (45, 55), (55, 65)]],
                                            default=Value(None), output_field=CharField()))
                .filter(rango_etario__isnull=False)
                # Usar Coalesce
                .values('rango_etario', 'ramo').annotate(total=Coalesce(Sum('monto_total'), Decimal('0.0'))))
        if not data.exists():
            fig_error = generar_figura_sin_datos(
                "No hay datos para impacto rango etario")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(list(data))
        df['total'] = pd.to_numeric(df['total'], errors='coerce').fillna(
            0.0)  # Convertir a float

        # Mapear códigos de ramo a etiquetas legibles
        ramo_map = dict(CommonChoices.RAMO)
        df['ramo_label'] = df['ramo'].map(ramo_map).fillna(df['ramo'])

        pivot = df.pivot_table(index='rango_etario', columns='ramo_label',
                               values='total', aggfunc='sum', fill_value=0)
        if pivot.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos válidos tras pivotar para G33")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = go.Figure(go.Heatmap(
            x=pivot.columns.tolist(), y=pivot.index.tolist(), z=pivot.values.tolist(),
            colorscale='Viridis', texttemplate="%{z:$,.0f}", hoverinfo="x+y+z"
        ))
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Distribución Montos por Edad y Ramo', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Ramo'
        layout_actualizado['yaxis']['title_text'] = 'Rango Etario'
        # layout_actualizado['height'] = 500 # Descomentar si se necesita
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_33: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 33")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_34():
    try:
        logger.debug("G34 - Iniciando Rentabilidad Estimada por Ramo")
        monto_contratado = collections.defaultdict(Decimal)
        for item in ContratoIndividual.objects.values('ramo').annotate(total_contratado_ramo=Coalesce(Sum('monto_total'), Decimal('0.0'))):
            if item['ramo']:
                monto_contratado[item['ramo']] += item['total_contratado_ramo']
        for item in ContratoColectivo.objects.values('ramo').annotate(total_contratado_ramo=Coalesce(Sum('monto_total'), Decimal('0.0'))):
            if item['ramo']:
                monto_contratado[item['ramo']] += item['total_contratado_ramo']
        monto_reclamado = collections.defaultdict(Decimal)
        for item in Reclamacion.objects.filter(contrato_individual__isnull=False, contrato_individual__ramo__isnull=False).values('contrato_individual__ramo').annotate(total_reclamado_ramo=Coalesce(Sum('monto_reclamado'), Decimal('0.0'))):
            if item['contrato_individual__ramo']:
                monto_reclamado[item['contrato_individual__ramo']
                                ] += item['total_reclamado_ramo']
        for item in Reclamacion.objects.filter(contrato_colectivo__isnull=False, contrato_colectivo__ramo__isnull=False).values('contrato_colectivo__ramo').annotate(total_reclamado_ramo=Coalesce(Sum('monto_reclamado'), Decimal('0.0'))):
            if item['contrato_colectivo__ramo']:
                monto_reclamado[item['contrato_colectivo__ramo']
                                ] += item['total_reclamado_ramo']

        resultados = []
        todos_ramos = set(monto_contratado.keys()) | set(
            monto_reclamado.keys())
        ramo_map = dict(CommonChoices.RAMO)
        for ramo_code in todos_ramos:
            if not ramo_code:
                continue
            contratado = monto_contratado.get(ramo_code, Decimal('0.0'))
            reclamado = monto_reclamado.get(ramo_code, Decimal('0.0'))
            rentabilidad = contratado - reclamado
            resultados.append({'ramo_label': ramo_map.get(ramo_code, ramo_code), 'rentabilidad': float(rentabilidad.quantize(Decimal(
                '0.01'))), 'contratado_tooltip': float(contratado.quantize(Decimal('0.01'))), 'reclamado_tooltip': float(reclamado.quantize(Decimal('0.01')))})
        if not resultados:
            fig_error = generar_figura_sin_datos(
                "No hay datos para rentabilidad por ramo")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(resultados).sort_values(
            'rentabilidad', ascending=False)
        df = df[df['rentabilidad'] != 0.0]
        if df.empty:
            fig_error = generar_figura_sin_datos(
                "No hay ramos con rentabilidad no nula")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        fig = px.bar(df, x='ramo_label', y='rentabilidad', text='rentabilidad', color='rentabilidad',
                     color_continuous_scale=px.colors.diverging.Portland, custom_data=['contratado_tooltip', 'reclamado_tooltip'])
        fig.update_traces(texttemplate='$%{text:,.0f}', textposition='auto',
                          hovertemplate="<b>Ramo: %{x}</b><br>Rentabilidad Estimada: $%{y:,.0f}<br>Prima Total: $%{customdata[0]:,.0f}<br>Siniestros Totales: $%{customdata[1]:,.0f}<extra></extra>")

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Rentabilidad Estimada por Ramo', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Ramo'
        # tickangle ya en BASE_LAYOUT
        layout_actualizado['xaxis']['type'] = 'category'
        layout_actualizado['yaxis']['title_text'] = 'Rentabilidad Estimada (USD)'
        layout_actualizado['yaxis']['tickprefix'] = '$'
        layout_actualizado['margin']['b'] = 100  # Más espacio para etiquetas X
        layout_actualizado['coloraxis_showscale'] = False
        fig.update_layout(**layout_actualizado)
        logger.info("G34 - Rentabilidad Estimada por Ramo generada.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error G34 (Rentabilidad Ramo): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar Gráfico 34 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_35():
    try:
        N_INTERMEDIARIOS = 25
        logger.debug(
            f"G35 - Iniciando Productividad Intermediarios (Bubble Chart Top {N_INTERMEDIARIOS})")
        data_qs = (Intermediario.objects.filter(activo=True)
                   .annotate(count_contratos_ind=Count('contratoindividual', filter=Q(contratoindividual__activo=True), distinct=True),
                             count_contratos_col=Count('contratos_colectivos', filter=Q(
                                 contratos_colectivos__activo=True), distinct=True),
                             comisiones_ind=Coalesce(Sum(F('contratoindividual__monto_total') * F('porcentaje_comision') / Decimal('100.0'), filter=Q(
                                 contratoindividual__activo=True, contratoindividual__monto_total__isnull=False)), Value(Decimal('0.0')), output_field=DecimalField()),
                             comisiones_col=Coalesce(Sum(F('contratos_colectivos__monto_total') * F('porcentaje_comision') / Decimal('100.0'), filter=Q(contratos_colectivos__activo=True, contratos_colectivos__monto_total__isnull=False)), Value(Decimal('0.0')), output_field=DecimalField()))
                   .annotate(total_contratos_intermediario=F('count_contratos_ind') + F('count_contratos_col'), comision_total_intermediario=F('comisiones_ind') + F('comisiones_col'))
                   .annotate(comision_promedio_por_contrato=Case(When(total_contratos_intermediario__gt=0, then=ExpressionWrapper(F('comision_total_intermediario') / F('total_contratos_intermediario'), output_field=DecimalField())), default=Value(Decimal('0.0')), output_field=DecimalField()))
                   .filter(Q(total_contratos_intermediario__gt=0) | Q(comision_total_intermediario__gt=Decimal('0.005'))).order_by('-comision_total_intermediario')[:N_INTERMEDIARIOS])
        if not data_qs.exists():
            fig_error = generar_figura_sin_datos(
                "No hay datos de actividad de intermediarios para G35")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df_data = [{'nombre_intermediario': d.nombre_completo, 'comisiones_totales': float(d.comision_total_intermediario or 0), 'n_contratos': int(
            d.total_contratos_intermediario or 0), 'comision_prom_contrato': float(d.comision_promedio_por_contrato or 0)} for d in data_qs]
        df = pd.DataFrame(df_data)
        # Asegurar que haya contratos para que el promedio tenga sentido
        df = df[df['n_contratos'] > 0]
        if df.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos válidos tras procesar para Gráfico 35")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = px.scatter(df, x="n_contratos", y="comisiones_totales", size="comision_prom_contrato",
                         color="nombre_intermediario", hover_name="nombre_intermediario", size_max=40)
        fig.update_traces(
            hovertemplate="<b>%{hovertext}</b><br><br>N° Contratos: %{x}<br>Comisiones Totales: $%{y:,.0f}<br>Comisión Prom./Contrato: $%{marker.size:,.0f}<extra></extra>")

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['xaxis']['title_text'] = 'Número de Contratos Activos'
        layout_actualizado['yaxis'][
            'title_text'] = 'Comisiones Totales Estimadas (USD)'
        layout_actualizado['yaxis']['tickprefix'] = '$'
        layout_actualizado['yaxis']['tickformat'] = ',.0f'
        layout_actualizado['legend']['title_text'] = 'Intermediario'
        # Leyenda más pequeña si hay muchos items
        layout_actualizado['legend']['font']['size'] = 7
        layout_actualizado['height'] = 500
        # layout_actualizado['showlegend'] = False # Descomentar si son demasiados para mostrar
        fig.update_layout(**layout_actualizado)
        logger.info(
            "G35 - Productividad Intermediarios (Bubble Chart) generada.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error G35 (Bubble Chart): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar Gráfico 35 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_36():
    try:
        logger.debug("G36 - Iniciando Estados de Facturación")
        total_pagado_por_factura_subquery = Subquery(Pago.objects.filter(factura_id=OuterRef('pk'), activo=True).values(
            'factura_id').annotate(total_pagado_factura=Sum('monto_pago')).values('total_pagado_factura')[:1], output_field=DecimalField())
        facturas_con_saldo = (Factura.objects.filter(activo=True)
                              .annotate(total_pagado_real=Coalesce(total_pagado_por_factura_subquery, Value(Decimal('0.0'))))
                              .annotate(saldo_calculado_factura=ExpressionWrapper(F('monto') - F('total_pagado_real'), output_field=DecimalField())))
        data_agrupada_qs = (facturas_con_saldo.values('estatus_factura')
                            .annotate(monto_total_facturado=Sum('monto'), monto_total_saldo_pendiente=Sum('saldo_calculado_factura'))
                            .order_by('estatus_factura'))
        if not data_agrupada_qs.exists():
            fig_error = generar_figura_sin_datos("No hay datos de facturación")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(list(data_agrupada_qs))
        estatus_map = {key: val for key, val in CommonChoices.ESTATUS_FACTURA}
        df['estado_label'] = df['estatus_factura'].map(
            estatus_map).fillna(df['estatus_factura'])
        df['monto_total_facturado'] = pd.to_numeric(
            df['monto_total_facturado'], errors='coerce').fillna(0.0)
        df['monto_total_saldo_pendiente'] = pd.to_numeric(
            df['monto_total_saldo_pendiente'], errors='coerce').fillna(0.0).clip(lower=0)

        if df.empty or (df['monto_total_facturado'].sum() == 0 and df['monto_total_saldo_pendiente'].sum() == 0):
            fig_error = generar_figura_sin_datos(
                "No hay montos significativos en facturación")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = go.Figure()
        fig.add_trace(go.Bar(x=df['estado_label'], y=df['monto_total_facturado'], name='Total Facturado', marker_color=COLOR_PALETTE.get(
            'primary'), text=df['monto_total_facturado'], texttemplate='$%{text:,.0f}', textposition='auto', hovertemplate="<b>Estado: %{x}</b><br>Total Facturado: $%{y:,.0f}<extra></extra>"))
        fig.add_trace(go.Bar(x=df['estado_label'], y=df['monto_total_saldo_pendiente'], name='Saldo Pendiente', marker_color=COLOR_PALETTE.get(
            'secondary'), text=df['monto_total_saldo_pendiente'], texttemplate='$%{text:,.0f}', textposition='auto', hovertemplate="<b>Estado: %{x}</b><br>Saldo Pendiente: $%{y:,.0f}<extra></extra>"))

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Resumen del Estado de Facturación', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Estado de la Factura'
        layout_actualizado['xaxis']['type'] = 'category'
        layout_actualizado['yaxis']['title_text'] = 'Monto Total (USD)'
        layout_actualizado['yaxis']['tickprefix'] = '$'
        layout_actualizado['barmode'] = 'group'
        # Leyenda se hereda de BASE_LAYOUT
        fig.update_layout(**layout_actualizado)
        logger.info("G36 - Estados de Facturación generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error G36: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar Gráfico 36 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_37():
    try:
        logger.debug(
            "G37 - Iniciando Ratio Siniestralidad por Ramo (Visual Capeado 100%)")
        monto_contratado = collections.defaultdict(Decimal)
        for item in ContratoIndividual.objects.values('ramo').annotate(total_contratado_ramo=Coalesce(Sum('monto_total'), Decimal('0.0'))):
            if item['ramo']:
                monto_contratado[item['ramo']] += item['total_contratado_ramo']
        for item in ContratoColectivo.objects.values('ramo').annotate(total_contratado_ramo=Coalesce(Sum('monto_total'), Decimal('0.0'))):
            if item['ramo']:
                monto_contratado[item['ramo']] += item['total_contratado_ramo']
        monto_reclamado = collections.defaultdict(Decimal)
        for item in Reclamacion.objects.filter(contrato_individual__isnull=False, contrato_individual__ramo__isnull=False).values('contrato_individual__ramo').annotate(total_reclamado_ramo=Coalesce(Sum('monto_reclamado'), Decimal('0.0'))):
            if item['contrato_individual__ramo']:
                monto_reclamado[item['contrato_individual__ramo']
                                ] += item['total_reclamado_ramo']
        for item in Reclamacion.objects.filter(contrato_colectivo__isnull=False, contrato_colectivo__ramo__isnull=False).values('contrato_colectivo__ramo').annotate(total_reclamado_ramo=Coalesce(Sum('monto_reclamado'), Decimal('0.0'))):
            if item['contrato_colectivo__ramo']:
                monto_reclamado[item['contrato_colectivo__ramo']
                                ] += item['total_reclamado_ramo']

        resultados = []
        todos_ramos = set(monto_contratado.keys()) | set(
            monto_reclamado.keys())
        ramo_map = dict(CommonChoices.RAMO)
        RATIO_CAP_VISUAL = Decimal('100.0')
        for ramo_code in todos_ramos:
            if not ramo_code:
                continue
            contratado = monto_contratado.get(ramo_code, Decimal('0.0'))
            reclamado_real = monto_reclamado.get(ramo_code, Decimal('0.0'))
            ratio_bruto = (reclamado_real / contratado *
                           100) if contratado > Decimal('0.005') else Decimal('0.0')
            ratio_para_display = min(ratio_bruto, RATIO_CAP_VISUAL)
            texto_en_barra_final = f"{ratio_para_display:.0f}%" + \
                ("+" if ratio_bruto > RATIO_CAP_VISUAL else "")
            resultados.append({'ramo_label': ramo_map.get(ramo_code, ramo_code), 'monto_contratado': contratado, 'monto_reclamado_real': reclamado_real, 'ratio_graficar': float(
                ratio_para_display.quantize(Decimal('0.1'))), 'ratio_real_calculado': float(ratio_bruto.quantize(Decimal('0.1'))), 'texto_barra_display': texto_en_barra_final})
        if not resultados:
            fig_error = generar_figura_sin_datos(
                "No hay datos para calcular ratio de siniestralidad")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(resultados)
        if df.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos significativos para el ratio")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = df.sort_values('ratio_real_calculado', ascending=False)
        colors = [COLOR_PALETTE.get('dark') if r >= 100 else (COLOR_PALETTE.get('secondary') if r >= 70 else (
            COLOR_PALETTE.get('warning') if r >= 70 * 0.6 else COLOR_PALETTE.get('success'))) for r in df['ratio_real_calculado']]
        fig = go.Figure(data=[go.Bar(x=df['ramo_label'], y=df['ratio_graficar'], marker_color=colors, text=df['texto_barra_display'], textposition='auto',
                                     customdata=np.stack(
                                         (df['monto_contratado'], df['monto_reclamado_real'], df['ratio_real_calculado']), axis=-1),
                                     hovertemplate="<b>Ramo: %{x}</b><br>Ratio Siniestralidad (Calculado Real): %{customdata[2]:.1f}%<br>Prima Total: $%{customdata[0]:,.0f}<br>Siniestros Totales: $%{customdata[1]:,.0f}<extra></extra>")])
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Ratio Siniestralidad por Ramo (Visualizado hasta 100%)', 'x': 0.5, 'font': {'size': 10}}
        layout_actualizado['xaxis']['title_text'] = 'Ramo del Seguro'
        # tickangle ya en BASE_LAYOUT
        layout_actualizado['xaxis']['type'] = 'category'
        layout_actualizado['yaxis']['title_text'] = 'Ratio Siniestralidad (%)'
        layout_actualizado['yaxis']['ticksuffix'] = '%'
        layout_actualizado['yaxis']['range'] = [
            0, float(RATIO_CAP_VISUAL * Decimal('1.1'))]
        layout_actualizado['margin']['b'] = 120  # Más espacio para etiquetas X
        fig.update_layout(**layout_actualizado)
        logger.info(
            "G37 - Gráfico de Ratio Siniestralidad por Ramo (Visual Capeado 100%) generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error G37 (Visual Capeado 100%): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar Gráfico 37 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_38():
    try:
        hoy = date.today()
        facturas_qs = (Factura.objects.filter(activo=True, pagada=False, monto_pendiente__gt=Decimal('0.01'), vigencia_recibo_hasta__isnull=False, vigencia_recibo_hasta__lt=hoy)
                       .values('pk', 'vigencia_recibo_hasta', 'monto_pendiente'))
        if not facturas_qs.exists():
            fig_error = generar_figura_sin_datos(
                "No hay facturas vencidas pendientes de pago")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        data_procesada = []
        rangos = [(1, 30, '1-30 días'), (31, 60, '31-60 días'), (61, 90,
                                                                 '61-90 días'), (91, 180, '91-180 días'), (181, 9999, '181+ días')]
        for factura_data in facturas_qs:
            fecha_vencimiento = factura_data.get('vigencia_recibo_hasta')
            monto_pendiente = factura_data.get('monto_pendiente')
            if not isinstance(fecha_vencimiento, date):
                fecha_vencimiento = fecha_vencimiento.date() if isinstance(
                    fecha_vencimiento, datetime) else None
            if not fecha_vencimiento or not isinstance(monto_pendiente, Decimal) or monto_pendiente <= Decimal('0.00') or fecha_vencimiento >= hoy:
                continue
            dias_vencido = (hoy - fecha_vencimiento).days
            if dias_vencido <= 0:
                continue
            rango_asignado = next(
                (lbl for min_d, max_d, lbl in rangos if min_d <= dias_vencido <= max_d), None)
            if rango_asignado:
                data_procesada.append(
                    {'rango_antiguedad': rango_asignado, 'total_pendiente': monto_pendiente})
        if not data_procesada:
            fig_error = generar_figura_sin_datos(
                "No se encontraron facturas válidas para el informe")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(data_procesada)
        df['total_pendiente'] = pd.to_numeric(
            df['total_pendiente'], errors='coerce').fillna(0.0)
        df_agrupado = df.groupby('rango_antiguedad', observed=False).agg(
            total_pendiente=('total_pendiente', 'sum')).reset_index()
        df_agrupado = df_agrupado[df_agrupado['total_pendiente'] > 0.005]
        if df_agrupado.empty:
            fig_error = generar_figura_sin_datos(
                "Los montos pendientes en los rangos son cero.")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        rango_order = [lbl for _, _, lbl in rangos]
        df_agrupado['rango_antiguedad'] = pd.Categorical(
            df_agrupado['rango_antiguedad'], categories=rango_order, ordered=True)
        df_agrupado = df_agrupado.sort_values('rango_antiguedad')
        color_map = {'1-30 días': COLOR_PALETTE.get('success'), '31-60 días': COLOR_PALETTE.get('info'), '61-90 días': COLOR_PALETTE.get(
            'warning'), '91-180 días': COLOR_PALETTE.get('secondary'), '181+ días': COLOR_PALETTE.get('dark')}
        fig = px.bar(df_agrupado, x='rango_antiguedad', y='total_pendiente',
                     text='total_pendiente', color='rango_antiguedad', color_discrete_map=color_map)
        fig.update_traces(texttemplate='$%{text:,.0f}', textposition='outside',
                          hovertemplate="<b>%{x}</b><br>Total Pendiente: $%{y:,.0f}<extra></extra>")

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Antigüedad de Saldos Pendientes (Facturas Vencidas)', 'x': 0.5, 'font': {'size': 10}}
        layout_actualizado['xaxis']['title_text'] = 'Antigüedad del Vencimiento'
        layout_actualizado['xaxis']['type'] = 'category'
        layout_actualizado['yaxis']['title_text'] = 'Monto Pendiente Total (USD)'
        layout_actualizado['yaxis']['tickprefix'] = '$'
        layout_actualizado['showlegend'] = False
        fig.update_layout(**layout_actualizado)
        logger.info(
            "grafico_38: Gráfica de Antigüedad de Saldos generada exitosamente.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error crítico inesperado en gráfico_38 (Aging Report): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error inesperado ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_39():
    try:
        costo_promedio_mes = (Reclamacion.objects.filter(activo=True, monto_reclamado__isnull=False, monto_reclamado__gt=0, fecha_cierre_reclamo__isnull=False)
                              .annotate(mes_cierre=TruncMonth('fecha_cierre_reclamo')).values('mes_cierre')
                              .annotate(costo_promedio=Avg('monto_reclamado')).order_by('mes_cierre').values('mes_cierre', 'costo_promedio'))
        if not costo_promedio_mes:
            fig_error = generar_figura_sin_datos(
                "No hay datos de siniestros cerrados para calcular costo promedio")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(list(costo_promedio_mes))
        df['mes_cierre'] = pd.to_datetime(df['mes_cierre'])
        df['costo_promedio'] = pd.to_numeric(
            # Convertir y manejar None
            df['costo_promedio'], errors='coerce').fillna(0.0)
        if len(df) > 24:
            df = df.tail(24)
        # Chequear si hay valores para graficar
        if df.empty or df['costo_promedio'].sum() == 0:
            fig_error = generar_figura_sin_datos(
                "No hay costos promedio válidos para mostrar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df['mes_str'] = df['mes_cierre'].dt.strftime('%Y-%m')
        fig = px.line(df, x='mes_str', y='costo_promedio', markers=True)
        fig.update_traces(line=dict(color=COLOR_PALETTE.get(
            'info'), width=3), marker=dict(size=7))

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Evolución Mensual del Costo Promedio por Siniestro (Incurrido)', 'x': 0.5, 'font': {'size': 10}}
        layout_actualizado['xaxis']['title_text'] = 'Mes de Cierre del Siniestro'
        # tickangle ya en BASE_LAYOUT
        layout_actualizado['xaxis']['type'] = 'category'
        layout_actualizado['yaxis']['title_text'] = 'Costo Promedio (USD)'
        layout_actualizado['yaxis']['tickprefix'] = '$'
        layout_actualizado['hovermode'] = 'x unified'
        layout_actualizado['margin']['b'] = 80  # Más espacio para etiquetas X
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error gráfico_39 (Reemplazo Costo Promedio Siniestro): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            "Error al generar costo promedio de siniestro")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_40():
    try:
        rangos = [(0, 17, '0-17'), (18, 25, '18-25'), (26, 35, '26-35'), (36, 45, '36-45'),
                  (46, 55, '46-55'), (56, 65, '56-65'), (66, 75, '66-75'), (76, 120, '76+')]
        when_clauses = [When(edad__gte=min_edad, edad__lte=max_edad, then=Value(
            label)) for min_edad, max_edad, label in rangos]
        data_qs = (Reclamacion.objects.filter(contrato_individual__isnull=False, contrato_individual__afiliado__fecha_nacimiento__isnull=False)
                   .annotate(edad=ExtractYear(Now()) - ExtractYear('contrato_individual__afiliado__fecha_nacimiento'),
                             rango_edad=Case(*when_clauses, default=Value('Desconocido'), output_field=CharField()))
                   .exclude(rango_edad='Desconocido').values('rango_edad')
                   .annotate(cantidad_reclamaciones=Count('id'),
                             monto_promedio_reclamado=Coalesce(Avg('monto_reclamado'), Value(Decimal('0.0')), output_field=DecimalField()))
                   .order_by(Case(*[When(rango_edad=label, then=Value(i)) for i, (_, _, label) in enumerate(rangos)])))
        if not data_qs.exists():
            fig_error = generar_figura_sin_datos(
                "No hay datos de reclamaciones para analizar por edad")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(list(data_qs))
        df['monto_promedio_float'] = pd.to_numeric(
            # Convertir y manejar None
            df['monto_promedio_reclamado'], errors='coerce').fillna(0.0)

        if df.empty or (df['cantidad_reclamaciones'].sum() == 0 and df['monto_promedio_float'].sum() == 0):
            fig_error = generar_figura_sin_datos(
                "No hay datos válidos para frecuencia/severidad por edad")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=df['rango_edad'], y=df['cantidad_reclamaciones'], name='Cantidad Reclamaciones', marker_color=COLOR_PALETTE.get(
            'primary'), text=df['cantidad_reclamaciones'], textposition='auto', hoverinfo='x+y+name', hovertemplate='<b>%{x}</b><br>Cantidad: %{y}<extra></extra>'), secondary_y=False)
        fig.add_trace(go.Scatter(x=df['rango_edad'], y=df['monto_promedio_float'], name='Monto Promedio ($)', mode='lines+markers', line=dict(color=COLOR_PALETTE.get(
            'secondary'), width=3), marker=dict(size=8), hoverinfo='x+y+name', hovertemplate='<b>%{x}</b><br>Monto Prom.: $%{y:,.2f}<extra></extra>'), secondary_y=True)

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Frecuencia y Severidad de Reclamaciones por Edad', 'x': 0.5, 'font': {'size': 10}}
        layout_actualizado['xaxis']['title_text'] = 'Rango de Edad'
        layout_actualizado['yaxis']['title_text'] = 'Cantidad de Reclamaciones'
        layout_actualizado['yaxis']['side'] = 'left'
        layout_actualizado['yaxis']['showgrid'] = True
        layout_actualizado['yaxis']['gridcolor'] = '#e5e5e5'
        layout_actualizado['yaxis2'] = {'title_text': 'Monto Promedio Reclamado ($)', 'side': 'right', 'overlaying': 'y', 'tickprefix': '$', 'showgrid': False, 'title_font': {
            'size': BASE_LAYOUT['yaxis']['title_font']['size']}, 'tickfont': {'size': BASE_LAYOUT['yaxis']['tickfont']['size']}}
        layout_actualizado['legend']['y'] = -0.4  # Ajustar leyenda
        layout_actualizado['legend']['x'] = 0.5
        layout_actualizado['legend']['xanchor'] = 'center'
        layout_actualizado['barmode'] = 'group'
        # Más espacio para etiquetas X y leyenda
        layout_actualizado['margin']['b'] = 120
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_40 (nuevo): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 40")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)

# ... (continuación de tu archivo graficas.py, después de grafico_40) ...
# ... (asegúrate de que import copy, BASE_LAYOUT, etc., ya están definidos arriba) ...

# ------------------------------
# Gráfico 41: Correlación Ramos-Reclamaciones
# ------------------------------


def grafico_41():
    try:
        # from django.db.models import Case, When, Value, CharField # Ya importado arriba
        data = (Reclamacion.objects
                .annotate(ramo=Case(
                    When(contrato_individual__isnull=False,
                         then=F('contrato_individual__ramo')),
                    When(contrato_colectivo__isnull=False,
                         then=F('contrato_colectivo__ramo')),
                    default=Value('Sin Especificar'), output_field=CharField()))
                .values('ramo', 'tipo_reclamacion')
                .annotate(total=Count('id')).order_by('ramo', 'tipo_reclamacion'))
        if not data.exists():
            fig_error = generar_figura_sin_datos(
                "No hay datos para correlación Ramos-Reclamaciones")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(list(data))
        # Mapear códigos a etiquetas legibles
        ramo_map = dict(CommonChoices.RAMO)
        tipo_reclamacion_map = dict(CommonChoices.TIPO_RECLAMACION)
        df['ramo_label'] = df['ramo'].map(ramo_map).fillna(df['ramo'])
        df['tipo_reclamacion_label'] = df['tipo_reclamacion'].map(
            tipo_reclamacion_map).fillna(df['tipo_reclamacion'])

        pivot = df.pivot_table(
            index='ramo_label', columns='tipo_reclamacion_label', values='total', fill_value=0)
        if pivot.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos válidos tras pivotar para G41")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = go.Figure(go.Heatmap(
            x=pivot.columns.tolist(), y=pivot.index.tolist(), z=pivot.values.tolist(),
            # Añadido text=pivot.values
            colorscale='Viridis', texttemplate="%{z}", text=pivot.values, hoverinfo="x+y+z"
        ))
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            # Título más corto
            'text': 'Correlación Ramos - Tipos de Reclamación', 'x': 0.5, 'font': {'size': 10}}
        layout_actualizado['xaxis']['title_text'] = 'Tipo de Reclamación'
        layout_actualizado['yaxis']['title_text'] = 'Ramo'
        layout_actualizado['xaxis']['tickangle'] = - \
            30  # Ajustar ángulo para mejor visualización
        # Etiquetas Y más pequeñas si son muchas
        layout_actualizado['yaxis']['tickfont']['size'] = 7
        # Etiquetas X más pequeñas
        layout_actualizado['xaxis']['tickfont']['size'] = 7
        layout_actualizado['height'] = max(
            500, len(pivot.index) * 30 + 150)  # Altura dinámica
        # Más espacio para etiquetas de Ramo
        layout_actualizado['margin']['l'] = 100
        # Más espacio para etiquetas de Tipo de Reclamación
        layout_actualizado['margin']['b'] = 120
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_41: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 41")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)

# ------------------------------
# Gráfico 42: Top Intermediarios (Comisión y % Retención)
# ------------------------------


def grafico_42():
    try:
        N = 10
        logger.debug(
            f"G42 - Iniciando Top {N} Intermediarios (Comisión y % Retención)")
        data_qs = (Intermediario.objects.filter(activo=True)
                   .annotate(count_ind_total=Count('contratoindividual', distinct=True),
                             count_ind_vigentes=Count('contratoindividual', filter=Q(
                                 contratoindividual__estatus='VIGENTE', contratoindividual__activo=True), distinct=True),
                             count_col_total=Count(
                                 'contratos_colectivos', distinct=True),
                             count_col_vigentes=Count('contratos_colectivos', filter=Q(
                                 contratos_colectivos__estatus='VIGENTE', contratos_colectivos__activo=True), distinct=True),
                             comisiones_ind_est=Coalesce(Sum(F('contratoindividual__monto_total') * F('porcentaje_comision') / Decimal('100.0'), filter=Q(
                                 contratoindividual__activo=True, contratoindividual__monto_total__isnull=False)), Value(Decimal('0.0')), output_field=DecimalField()),
                             comisiones_col_est=Coalesce(Sum(F('contratos_colectivos__monto_total') * F('porcentaje_comision') / Decimal('100.0'), filter=Q(contratos_colectivos__activo=True, contratos_colectivos__monto_total__isnull=False)), Value(Decimal('0.0')), output_field=DecimalField()))
                   .annotate(contratos_total_general=F('count_ind_total') + F('count_col_total'),
                             contratos_vigentes_general=F(
                                 'count_ind_vigentes') + F('count_col_vigentes'),
                             comisiones_total_estimada=F('comisiones_ind_est') + F('comisiones_col_est'))
                   .annotate(tasa_retencion=Case(When(contratos_total_general__gt=0, then=ExpressionWrapper(F('contratos_vigentes_general') * Decimal('100.0') / F('contratos_total_general'), output_field=FloatField())), default=Value(0.0), output_field=FloatField()))
                   .filter(Q(comisiones_total_estimada__gt=Decimal('0.005')) | Q(contratos_total_general__gt=0))
                   .order_by('-comisiones_total_estimada')[:N])
        if not data_qs:
            fig_error = generar_figura_sin_datos(
                "No hay datos de actividad de intermediarios para G42")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df_data = []
        for d in data_qs:
            retencion_calculada = d.tasa_retencion if d.tasa_retencion is not None else 0.0
            retencion_final = min(max(retencion_calculada, 0.0), 100.0)
            if retencion_calculada > 100.5:
                logger.warning(
                    f"G42 - Intermediario {d.nombre_completo} (PK:{d.pk}) con retención >100% ({retencion_calculada:.2f}%). Se capea a 100%.")
            df_data.append({'nombre_intermediario': d.nombre_completo, 'comisiones': float(d.comisiones_total_estimada or 0),
                           'retencion': retencion_final, 'contratos_vigentes': d.contratos_vigentes_general, 'contratos_totales': d.contratos_total_general})
        df = pd.DataFrame(df_data)
        if df.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos válidos tras procesar para Gráfico 42")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=df['nombre_intermediario'], y=df['comisiones'], name='Comisiones Estimadas', marker_color=COLOR_PALETTE.get('primary'), text=[
                      f"${c:,.0f}" for c in df['comisiones']], textposition='auto', hovertemplate="<b>%{x}</b><br>Comisiones: $%{y:,.0f}<extra></extra>"), secondary_y=False)
        fig.add_trace(go.Scatter(x=df['nombre_intermediario'], y=df['retencion'], name='% Retención Cartera', mode='lines+markers', line=dict(color=COLOR_PALETTE.get('success')), marker=dict(size=8), customdata=np.stack(
            (df['contratos_vigentes'], df['contratos_totales']), axis=-1), hovertemplate="<b>%{x}</b><br>% Retención: %{y:.1f}%<br>Vigentes: %{customdata[0]}<br>Totales: %{customdata[1]}<extra></extra>"), secondary_y=True)

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': f'Top {N} Intermediarios: Comisiones y % Retención', 'x': 0.5, 'font': {'size': 10}}
        layout_actualizado['xaxis']['title_text'] = 'Intermediario'
        # tickangle ya en BASE_LAYOUT
        layout_actualizado['yaxis']['title_text'] = 'Comisiones Estimadas (USD)'
        layout_actualizado['yaxis']['tickprefix'] = '$'
        layout_actualizado['yaxis']['side'] = 'left'
        layout_actualizado['yaxis2'] = {'title_text': '% Retención', 'rangemode': 'tozero', 'range': [0, 105], 'side': 'right', 'overlaying': 'y', 'ticksuffix': '%',
                                        'showgrid': False, 'title_font': {'size': BASE_LAYOUT['yaxis']['title_font']['size']}, 'tickfont': {'size': BASE_LAYOUT['yaxis']['tickfont']['size']}}
        layout_actualizado['height'] = 500
        layout_actualizado['legend']['y'] = 1.15  # Ajustar posición
        layout_actualizado['margin']['b'] = 120  # Espacio para etiquetas X
        fig.update_layout(**layout_actualizado)
        logger.info(
            "G42 - Top Intermediarios (Comisión y % Retención) generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error G42: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar Gráfico 42 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_43():
    try:
        prima_ind = (ContratoIndividual.objects.filter(activo=True).values('ramo').annotate(
            total_prima=Coalesce(Sum('monto_total'), Decimal('0.0'))).values('ramo', 'total_prima'))
        prima_col = (ContratoColectivo.objects.filter(activo=True).values('ramo').annotate(
            total_prima=Coalesce(Sum('monto_total'), Decimal('0.0'))).values('ramo', 'total_prima'))
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
            fig_error = generar_figura_sin_datos(
                "No hay datos de primas para descomponer")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(data)
        df['Prima'] = df['Prima'].astype(float)
        fig = px.sunburst(df, path=['Tipo', 'Ramo'], values='Prima', color='Tipo', color_discrete_map={'Individual': COLOR_PALETTE.get(
            'info'), 'Colectivo': COLOR_PALETTE.get('primary')}, branchvalues='total', hover_data=['Prima'])
        fig.update_traces(textinfo='label+percent parent',
                          hovertemplate='<b>%{label}</b><br>Prima: $%{value:,.0f}<br>(%{percentParent:.1%} del Tipo)<extra></extra>')

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Descomposición Prima Emitida por Tipo y Ramo', 'x': 0.5, 'font': {'size': 10}}
        layout_actualizado['margin'] = {'t': 50, 'l': 10, 'r': 10, 'b': 10}
        # Sunburst no tiene ejes X/Y tradicionales visibles
        if 'xaxis' in layout_actualizado:
            layout_actualizado['xaxis']['visible'] = False
        if 'yaxis' in layout_actualizado:
            layout_actualizado['yaxis']['visible'] = False
        # El sunburst es su propia leyenda
        layout_actualizado['showlegend'] = False
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error gráfico_43 (Reemplazo Sunburst Prima): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al descomponer primas ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_44():
    try:
        N = 15
        top_ind = (ContratoIndividual.objects.select_related('afiliado').filter(monto_total__isnull=False).order_by(
            '-monto_total').values('numero_contrato', 'monto_total', 'afiliado__primer_nombre', 'afiliado__primer_apellido')[:N])
        top_col = (ContratoColectivo.objects.filter(monto_total__isnull=False).order_by(
            '-monto_total').values('numero_contrato', 'monto_total', 'razon_social')[:N])
        data_combined = []
        for item in top_ind:
            data_combined.append(
                {'label': f"CI: {item['numero_contrato']} ({item['afiliado__primer_apellido']})", 'monto': item['monto_total'], 'tipo': 'Individual'})
        for item in top_col:
            data_combined.append(
                {'label': f"CC: {item['numero_contrato']} ({item['razon_social']})", 'monto': item['monto_total'], 'tipo': 'Colectivo'})
        if not data_combined:
            fig_error = generar_figura_sin_datos(
                "No hay contratos con montos para mostrar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(data_combined)
        df['monto'] = pd.to_numeric(df['monto'], errors='coerce').fillna(0.0)
        df_top = df.nlargest(N, 'monto')
        df_top['monto_float'] = df_top['monto'].astype(float)
        if df_top.empty:
            fig_error = generar_figura_sin_datos(
                "No hay contratos válidos para mostrar en Top N")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = px.bar(df_top, x='monto_float', y='label', orientation='h', color='tipo', color_discrete_map={
                     'Individual': COLOR_PALETTE.get('info'), 'Colectivo': COLOR_PALETTE.get('primary')}, text='monto_float')
        fig.update_traces(texttemplate='$%{text:,.0f}', textposition='auto')
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': f'Top {N} Contratos por Mayor Monto Asegurado', 'x': 0.5, 'font': {'size': 10}}
        layout_actualizado['xaxis']['title_text'] = 'Monto Total Asegurado (USD)'
        layout_actualizado['xaxis']['tickprefix'] = '$'
        layout_actualizado['yaxis']['title_text'] = 'Contrato'
        # Etiquetas Y más pequeñas para nombres largos
        layout_actualizado['yaxis']['tickfont']['size'] = 7
        # Más espacio para etiquetas de contrato
        layout_actualizado['margin']['l'] = 200
        layout_actualizado['height'] = max(400, N * 30 + 100)
        layout_actualizado['legend']['title_text'] = 'Tipo'
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        # El logger original decía "gráfico_21 (nuevo)", lo corregí a 44
        logger.error(f"Error gráfico_44: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 44")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_45():
    try:
        # Asegúrate que este valor sea correcto
        VALOR_DE_RENOVACION_EN_ESTADO_CONTRATO = 'EN_TRAMITE_RENOVACION'
        data_qs = (ContratoIndividual.objects.filter(fecha_emision__isnull=False)
                   .annotate(year=ExtractYear('fecha_emision'),
                             es_renovacion=Case(When(estado_contrato=VALOR_DE_RENOVACION_EN_ESTADO_CONTRATO, then=1), default=0, output_field=IntegerField()))
                   .values('year').annotate(nuevos=Count('id', filter=Q(es_renovacion=0)), renovaciones=Count('id', filter=Q(es_renovacion=1))).order_by('year'))
        if not data_qs.exists():
            fig_error = generar_figura_sin_datos(
                "No hay datos para tendencia de nuevos vs renovaciones.")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(list(data_qs))
        if df.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos para tendencia de nuevos vs renovaciones.")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = go.Figure()
        fig.add_trace(go.Bar(x=df['year'].astype(
            str), y=df['nuevos'], name='Nuevos/Otros', marker_color=COLOR_PALETTE.get('primary')))
        fig.add_trace(go.Bar(x=df['year'].astype(str), y=df['renovaciones'],
                      name='Renovaciones', marker_color=COLOR_PALETTE.get('success')))

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Tendencia Contratos Nuevos vs. Renovaciones (Año Emisión)', 'x': 0.5, 'font': {'size': 10}}
        layout_actualizado['xaxis']['title_text'] = 'Año de Emisión'
        layout_actualizado['xaxis']['type'] = 'category'
        layout_actualizado['yaxis']['title_text'] = 'Cantidad de Contratos'
        layout_actualizado['barmode'] = 'stack'
        layout_actualizado['legend']['title_text'] = 'Tipo'
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error en grafico_45 (versión simplificada): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error generando gráfico 45: {type(e).__name__}")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_46():
    try:
        data_ind = (ContratoIndividual.objects.filter(activo=True).annotate(year=ExtractYear('fecha_emision'), month=ExtractMonth('fecha_emision')).values(
            'year', 'month').annotate(total_prima=Coalesce(Sum('monto_total'), Decimal('0.0'))).values('year', 'month', 'total_prima'))
        data_col = (ContratoColectivo.objects.filter(activo=True).annotate(year=ExtractYear('fecha_emision'), month=ExtractMonth('fecha_emision')).values(
            'year', 'month').annotate(total_prima=Coalesce(Sum('monto_total'), Decimal('0.0'))).values('year', 'month', 'total_prima'))
        df_ind = pd.DataFrame(list(data_ind))
        df_col = pd.DataFrame(list(data_col))
        # ignore_index para evitar problemas de índice
        df_total = pd.concat([df_ind, df_col], ignore_index=True)
        if df_total.empty or 'total_prima' not in df_total.columns or df_total['total_prima'].isnull().all():
            fig_error = generar_figura_sin_datos(
                "No hay datos de primas emitidas")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df_total['total_prima'] = pd.to_numeric(
            df_total['total_prima'], errors='coerce').fillna(0.0)
        df_agrupado = df_total.groupby(['year', 'month'], as_index=False)[
            'total_prima'].sum()
        if df_agrupado.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos de primas tras agrupar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        try:
            pivot_df = df_agrupado.pivot_table(
                index='month', columns='year', values='total_prima', fill_value=0)
            pivot_df = pivot_df.reindex(index=range(1, 13), fill_value=0)
        except Exception as pivot_error:
            logger.error(
                f"Error al pivotear datos para heatmap G46: {pivot_error}", exc_info=True)
            fig_error = generar_figura_sin_datos(
                "Error al procesar datos para heatmap")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        if pivot_df.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos en pivot para heatmap")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = go.Figure(data=go.Heatmap(
            # Asegurar que años sean string para eje X
            z=pivot_df.values, x=pivot_df.columns.astype(str),
            y=['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],
            colorscale='Greens', text=pivot_df.values, texttemplate="$%{text:,.0f}", hoverongaps=False,
            hovertemplate="<b>Mes:</b> %{y}<br><b>Año:</b> %{x}<br><b>Prima Emitida:</b> $%{z:,.0f}<extra></extra>"
        ))
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Distribución Mensual de Prima Emitida', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['xaxis']['title_text'] = 'Año'
        # Tratar años como categorías
        layout_actualizado['xaxis']['type'] = 'category'
        layout_actualizado['yaxis']['title_text'] = 'Mes'
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error gráfico_46 (Reemplazo Heatmap Prima): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            "Error al generar heatmap de primas")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_47():
    try:
        data_qs = (ContratoIndividual.objects.values(
            'ramo', 'forma_pago', 'estatus').annotate(total=Count('id')))
        if not data_qs.exists():
            fig_error = generar_figura_sin_datos(
                "No hay Contratos Individuales para segmentar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(list(data_qs))
        df = df[df['total'] > 0]
        if df.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos válidos para Gráfico 47")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
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
        if df_treemap.empty:
            fig_error = generar_figura_sin_datos("No hay datos para treemap")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = go.Figure(go.Treemap(
            ids=df_treemap['id'], labels=df_treemap['label'], parents=df_treemap['parent'], values=df_treemap['value'],
            branchvalues="total", marker=dict(colors=px.colors.qualitative.Pastel),
            textinfo="label+value+percent parent+percent root", hoverinfo="label+value+percent parent+percent root"
        ))
        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Segmentación de Contratos Individuales', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['margin'] = {'t': 50, 'l': 10, 'r': 10, 'b': 10}
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_47: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 47")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_48():
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
                                  'Cliente/Empresa': afiliado_nombre, 'Vence': c['fecha_fin_vigencia'], 'Intermediario': intermediario_nombre})
        for c in contratos_col_vencer:
            intermediario_nombre = c['intermediario__nombre_completo'] or '-'
            data_combinada.append({'ID': str(c['pk']), 'N° Contrato': str(c['numero_contrato'] or '-'), 'Tipo': 'Colectivo', 'Cliente/Empresa': str(
                c['razon_social'] or '-'), 'Vence': c['fecha_fin_vigencia'], 'Intermediario': intermediario_nombre})
        if not data_combinada:
            fig_error = generar_figura_sin_datos(
                "No hay contratos próximos a vencer")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        data_combinada.sort(key=lambda x: x['Vence'] or date.max)
        df = pd.DataFrame(data_combinada)
        df['Vence'] = pd.to_datetime(df['Vence']).dt.strftime('%d/%m/%Y')
        fig = go.Figure(data=[go.Table(header=dict(values=list(df.columns), fill_color=COLOR_PALETTE.get('primary'), align='left', font=dict(color='white', size=10)),  # Font size header
                                       # Font size cells and height
                                       cells=dict(values=[df[col].tolist() for col in df.columns], fill_color=COLOR_PALETTE.get('light'), align='left', font=dict(color=COLOR_PALETTE.get('dark'), size=9), height=28))])

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Contratos Vigentes Próximos a Vencer (30 días)', 'x': 0.5, 'font': {'size': 11}}
        # Márgenes ajustados para tabla
        layout_actualizado['margin'] = {'l': 5, 'r': 5, 't': 50, 'b': 5}
        layout_actualizado['height'] = 100 + \
            (len(df) * 30) if len(df) > 0 else 200  # Altura dinámica
        # Tablas no usan ejes X/Y tradicionales
        if 'xaxis' in layout_actualizado:
            layout_actualizado['xaxis']['visible'] = False
        if 'yaxis' in layout_actualizado:
            layout_actualizado['yaxis']['visible'] = False
        layout_actualizado.pop('legend', None)  # No leyenda para tablas

        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error G48(nuevo): {e}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error G48")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_49():
    logger.debug("G49: Iniciando generación...")
    try:
        default_estado = 'DESCONOCIDO'
        contratos_ind_activos = (ContratoIndividual.objects.filter(activo=True, estatus='VIGENTE').annotate(estado_afiliado=Coalesce(F('afiliado__estado'), Value(
            default_estado), output_field=CharField())).values('estado_afiliado').annotate(total_ind=Count('id')).exclude(estado_afiliado='').order_by('estado_afiliado'))
        contratos_col_activos = (ContratoColectivo.objects.filter(activo=True, estatus='VIGENTE', afiliados_colectivos__isnull=False).annotate(estado_af_col=Coalesce(F('afiliados_colectivos__estado'), Value(
            default_estado), output_field=CharField())).values('estado_af_col').annotate(total_col=Count('id', distinct=True)).exclude(estado_af_col='').order_by('estado_af_col'))
        estado_counts = collections.defaultdict(int)
        for item in contratos_ind_activos:
            estado_counts[item.get('estado_afiliado')
                          ] += item.get('total_ind', 0)
        for item in contratos_col_activos:
            estado_counts[item.get('estado_af_col')
                          ] += item.get('total_col', 0)
        if not estado_counts:
            fig_error = generar_figura_sin_datos(
                "No hay contratos activos para mostrar por estado")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        estado_map = dict(CommonChoices.ESTADOS_VE)
        data_list = [{'estado_code': estado_code, 'estado_label': estado_map.get(
            estado_code, estado_code), 'total': total} for estado_code, total in estado_counts.items() if isinstance(total, (int, float, Decimal)) and total > 0]
        if not data_list:
            fig_error = generar_figura_sin_datos(
                "No hay datos válidos por estado tras procesar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df = pd.DataFrame(data_list).sort_values('total', ascending=False)
        df['total'] = pd.to_numeric(df['total'], errors='coerce').fillna(0.0)
        df = df[df['total'] > 0]
        if df.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos con valores positivos para graficar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        fig = px.bar(df, x='estado_label', y='total', text='total',
                     color='total', color_continuous_scale=px.colors.sequential.Blues)
        fig.update_traces(textposition='outside')

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Distribución Geográfica de Contratos Activos por Estado', 'x': 0.5, 'font': {'size': 10}}
        layout_actualizado['xaxis']['title_text'] = "Estados de Venezuela"
        # Ordenar por total
        layout_actualizado['xaxis']['categoryorder'] = 'total descending'
        # tickangle ya en BASE_LAYOUT
        layout_actualizado['yaxis']['title_text'] = "N° de Contratos Activos (Ind + Col)"
        layout_actualizado['coloraxis_showscale'] = False  # px.bar crea esto
        # Más espacio para etiquetas X rotadas
        layout_actualizado['margin']['b'] = 120
        fig.update_layout(**layout_actualizado)
        logger.info("G49: Gráfica Distribución Geográfica generada.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error gráfico_49 (Geográfico): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar distribución geográfica ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_50():
    try:
        data = []
        has_data = False
        estatus_map = dict(CommonChoices.ESTADOS_VIGENCIA)
        contratos_ind = ContratoIndividual.objects.all()
        if contratos_ind.exists():
            has_data = True
            counts = contratos_ind.values(
                'estatus').annotate(total=Count('id'))
            for item in counts:
                if item['total'] > 0:
                    data.append({'Tipo': 'Individual', 'Estado': estatus_map.get(
                        item['estatus'], item['estatus']), 'Cantidad': item['total']})

        contratos_col = ContratoColectivo.objects.all()
        if contratos_col.exists():
            has_data = True
            counts = contratos_col.values(
                'estatus').annotate(total=Count('id'))
            for item in counts:
                if item['total'] > 0:
                    data.append({'Tipo': 'Colectivo', 'Estado': estatus_map.get(
                        item['estatus'], item['estatus']), 'Cantidad': item['total']})

        if not has_data or not data:
            fig_error = generar_figura_sin_datos(
                "No hay datos de contratos para mostrar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(data)
        # Asegurar que Cantidad existe y suma a algo
        if df.empty or 'Cantidad' not in df.columns or df['Cantidad'].sum() == 0:
            fig_error = generar_figura_sin_datos(
                "No hay cantidades válidas de contratos")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Calcular Total_General como un escalar
        total_general_scalar = df['Cantidad'].sum()

        if total_general_scalar > 0:
            df['Porcentaje_Total'] = (
                df['Cantidad'] / total_general_scalar) * 100
        else:
            df['Porcentaje_Total'] = 0

        fig = px.sunburst(df, path=['Tipo', 'Estado'], values='Cantidad', color='Estado',
                          color_discrete_map={estatus_map.get('VIGENTE', 'VIGENTE'): COLOR_PALETTE.get('success'),
                                              estatus_map.get('VENCIDO', 'VENCIDO'): COLOR_PALETTE.get('secondary'),
                                              estatus_map.get('NO_VIGENTE_AUN', 'NO_VIGENTE_AUN'): COLOR_PALETTE.get('warning'),
                                              '(?)': COLOR_PALETTE.get('light')},
                          branchvalues='total', hover_data={'Porcentaje_Total': ':.2f%'})
        fig.update_traces(textinfo='label+percent parent')

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Distribución de Contratos por Tipo y Estado', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['margin'] = {'t': 50, 'l': 10, 'r': 10, 'b': 10}
        if 'xaxis' in layout_actualizado:
            layout_actualizado['xaxis']['visible'] = False
        if 'yaxis' in layout_actualizado:
            layout_actualizado['yaxis']['visible'] = False
        layout_actualizado['showlegend'] = False
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        # El log ya incluye el traceback
        logger.error(f"Error gráfico_50: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos("Error al generar Gráfico 50")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


def grafico_51():
    try:
        logger.debug("G51_nuevo - Iniciando Concentración de Siniestros")
        reclamaciones_qs = (Reclamacion.objects.filter(monto_reclamado__isnull=False, monto_reclamado__gt=Decimal(
            '0.00')).order_by('-monto_reclamado').values('pk', 'monto_reclamado'))
        if not reclamaciones_qs.exists():
            fig_error = generar_figura_sin_datos(
                "No hay reclamaciones con monto para analizar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df_reclamaciones = pd.DataFrame(list(reclamaciones_qs))
        df_reclamaciones['monto_reclamado'] = pd.to_numeric(
            df_reclamaciones['monto_reclamado'], errors='coerce').fillna(0.0)
        # Re-aplicar por si fillna(0.0) no es suficiente para lógica posterior
        df_reclamaciones.dropna(subset=['monto_reclamado'], inplace=True)
        # Asegurar montos positivos
        df_reclamaciones = df_reclamaciones[df_reclamaciones['monto_reclamado'] > 0]
        if df_reclamaciones.empty:
            fig_error = generar_figura_sin_datos(
                "No hay reclamaciones válidas tras procesar")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        total_monto_reclamado_general = df_reclamaciones['monto_reclamado'].sum(
        )
        total_num_reclamaciones = len(df_reclamaciones)
        if total_monto_reclamado_general == 0 or total_num_reclamaciones == 0:
            fig_error = generar_figura_sin_datos(
                "Monto total o número de reclamaciones es cero")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        porcentaje_top_siniestros = 10
        num_siniestros_top = max(
            1, int(total_num_reclamaciones * (porcentaje_top_siniestros / 100.0)))
        df_top_siniestros = df_reclamaciones.head(num_siniestros_top)
        monto_top_siniestros = df_top_siniestros['monto_reclamado'].sum()
        monto_resto_siniestros = total_monto_reclamado_general - monto_top_siniestros
        num_resto_siniestros = total_num_reclamaciones - num_siniestros_top
        labels = [f'Monto del Top {porcentaje_top_siniestros}% de Siniestros',
                  f'Monto del {100-porcentaje_top_siniestros}% Restante']
        values = [float(monto_top_siniestros), float(monto_resto_siniestros)]
        text_for_hover = [f"{num_siniestros_top} siniestros ({(num_siniestros_top/total_num_reclamaciones)*100 if total_num_reclamaciones else 0:.1f}% del total)",
                          f"{num_resto_siniestros} siniestros ({(num_resto_siniestros/total_num_reclamaciones)*100 if total_num_reclamaciones else 0:.1f}% del total)"]

        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.3, marker_colors=[COLOR_PALETTE.get('secondary'), COLOR_PALETTE.get(
            'primary')], textinfo='percent+label', hoverinfo='label+value+percent+text', text=text_for_hover, insidetextorientation='horizontal')])
        porcentaje_monto_top = (monto_top_siniestros / total_monto_reclamado_general) * \
            100 if total_monto_reclamado_general else 0

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            # Título más corto
            'text': f'Concentración Montos: Top {porcentaje_top_siniestros}% Siniestros = {porcentaje_monto_top:.1f}% del Total', 'x': 0.5, 'font': {'size': 9}}
        layout_actualizado['showlegend'] = True
        layout_actualizado['legend']['y'] = -0.1  # Ajustar leyenda
        layout_actualizado['legend']['x'] = 0.5
        layout_actualizado['legend']['xanchor'] = 'center'
        # Más espacio para título y leyenda
        layout_actualizado['margin'] = {'t': 50, 'b': 80, 'l': 20, 'r': 20}
        if 'xaxis' in layout_actualizado:
            layout_actualizado['xaxis']['visible'] = False
        if 'yaxis' in layout_actualizado:
            layout_actualizado['yaxis']['visible'] = False
        fig.update_layout(**layout_actualizado)
        logger.info(
            "G51_nuevo - Gráfico de Concentración de Siniestros generado.")
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error G51_nuevo (Concentración Siniestros): {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar Gráfico 51 ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)


logger_grafica_52 = logging.getLogger("myapp.graficas.grafico_52")


def grafico_52():
    try:
        now_aware = django_timezone.now()
        start_date_aware = now_aware - timedelta(days=365)
        start_date_date = start_date_aware.date()
        generadas_por_mes_qs = (RegistroComision.objects.filter(fecha_calculo__gte=start_date_aware).annotate(mes_dt_db=TruncMonth('fecha_calculo')).values(
            'mes_dt_db').annotate(total_generado=Coalesce(Sum('monto_comision'), Value(Decimal('0.0')), output_field=DecimalField())).order_by('mes_dt_db'))
        pagadas_por_mes_qs = (RegistroComision.objects.filter(estatus_pago_comision='PAGADA', fecha_pago_a_intermediario__gte=start_date_date).annotate(mes_dt_db=TruncMonth(
            'fecha_pago_a_intermediario')).values('mes_dt_db').annotate(total_pagado=Coalesce(Sum('monto_comision'), Value(Decimal('0.0')), output_field=DecimalField())).order_by('mes_dt_db'))
        df_generadas = pd.DataFrame(list(generadas_por_mes_qs))
        df_pagadas = pd.DataFrame(list(pagadas_por_mes_qs))
        if not df_generadas.empty and 'mes_dt_db' in df_generadas.columns:
            df_generadas['mes'] = pd.to_datetime(df_generadas['mes_dt_db'])
            df_generadas['mes'] = df_generadas['mes'].dt.tz_convert('UTC').dt.tz_localize(
                None) if df_generadas['mes'].dt.tz is not None else df_generadas['mes'].dt.tz_localize(None)
            df_generadas.drop(columns=['mes_dt_db'], inplace=True)
            df_generadas['total_generado'] = df_generadas['total_generado'].apply(
                lambda x: Decimal(x) if x is not None else Decimal('0.00'))
        else:
            df_generadas = pd.DataFrame(columns=['mes', 'total_generado'])
        if not df_pagadas.empty and 'mes_dt_db' in df_pagadas.columns:
            df_pagadas['mes'] = pd.to_datetime(df_pagadas['mes_dt_db'])
            df_pagadas.drop(columns=['mes_dt_db'], inplace=True)
            df_pagadas['total_pagado'] = df_pagadas['total_pagado'].apply(
                lambda x: Decimal(x) if x is not None else Decimal('0.00'))
        else:
            df_pagadas = pd.DataFrame(columns=['mes', 'total_pagado'])
        if df_generadas.empty and df_pagadas.empty:
            fig_error = generar_figura_sin_datos(
                "No hay datos de flujo de comisiones.")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        if not df_generadas.empty and not df_pagadas.empty:
            df_final = pd.merge(df_generadas, df_pagadas,
                                on='mes', how='outer')
        elif not df_generadas.empty:
            df_final = df_generadas.copy()
            df_final['total_pagado'] = Decimal('0.00')
        elif not df_pagadas.empty:
            df_final = df_pagadas.copy()
            df_final['total_generado'] = Decimal('0.00')
        else:
            fig_error = generar_figura_sin_datos(
                "Error combinando datos de comisiones.")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df_final[['total_generado', 'total_pagado']] = df_final[[
            'total_generado', 'total_pagado']].fillna(Decimal('0.00'))
        df_final = df_final.sort_values(by='mes').reset_index(drop=True)
        df_final['total_generado_float'] = df_final['total_generado'].astype(
            float)
        df_final['total_pagado_float'] = df_final['total_pagado'].astype(float)
        if 'mes' not in df_final.columns or df_final['mes'].isnull().all():
            fig_error = generar_figura_sin_datos(
                "Error procesando fechas para comisiones.")
            return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        df_final['mes_str'] = df_final['mes'].dt.strftime('%Y-%m')
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_final['mes_str'], y=df_final['total_generado_float'], name='Comisiones Generadas', marker_color=COLOR_PALETTE.get(
            'primary'), hovertemplate='<b>Generadas en %{x}:</b> Bs. %{y:,.2f}<extra></extra>'))
        fig.add_trace(go.Bar(x=df_final['mes_str'], y=df_final['total_pagado_float'], name='Comisiones Liquidadas', marker_color=COLOR_PALETTE.get(
            'success'), hovertemplate='<b>Liquidadas en %{x}:</b> Bs. %{y:,.2f}<extra></extra>'))

        layout_actualizado = copy.deepcopy(BASE_LAYOUT)
        layout_actualizado['title'] = {
            'text': 'Flujo Mensual de Comisiones', 'x': 0.5, 'font': {'size': 11}}
        layout_actualizado['barmode'] = 'group'
        layout_actualizado['xaxis']['title_text'] = 'Mes'
        layout_actualizado['xaxis']['type'] = 'category'
        layout_actualizado['yaxis']['title_text'] = 'Monto Comisiones (Bs.)'
        # legend y margin ya en BASE_LAYOUT, se pueden ajustar aquí si es necesario
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger_grafica_52.error(
            f"Error EXCEPCIONAL en grafico_52: {str(e)}", exc_info=True)
        fig_excepcion = generar_figura_sin_datos(
            f"Error al generar flujo de comisiones ({type(e).__name__})")
        return plot(fig_excepcion, output_type='div', config=GRAPH_CONFIG)

# --- FUNCIONES AUXILIARES generar_grafico_... ---


def generar_grafico_estados_contrato(data_agregada):
    if not data_agregada:
        fig_error = generar_figura_sin_datos_plotly(
            "Estados de contrato no disponibles.")
        return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    colores = [COLOR_PALETTE.get('success'), COLOR_PALETTE.get('danger'), COLOR_PALETTE.get(
        'warning'), COLOR_PALETTE.get('info'), COLOR_PALETTE.get('secondary')]
    fig = go.Figure(data=[go.Pie(labels=list(data_agregada.keys()), values=list(data_agregada.values(
    )), hole=.4, marker_colors=colores, textinfo='percent+label', hoverinfo='label+value+percent', insidetextorientation='radial')])

    layout_actualizado = copy.deepcopy(BASE_LAYOUT)
    layout_actualizado['title'] = {
        'text': 'Estado de Contratos', 'x': 0.5, 'font': {'size': 11}}
    layout_actualizado['showlegend'] = False
    layout_actualizado['margin'] = {'t': 50, 'b': 0, 'l': 0, 'r': 0}
    if 'xaxis' in layout_actualizado:
        layout_actualizado['xaxis']['visible'] = False
    if 'yaxis' in layout_actualizado:
        layout_actualizado['yaxis']['visible'] = False
    fig.update_layout(**layout_actualizado)
    return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


def generar_grafico_estados_reclamacion(data_agregada):
    if not data_agregada:
        fig_error = generar_figura_sin_datos_plotly(
            "Estados de reclamación no disponibles.")
        return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    df = pd.DataFrame(list(data_agregada.items()),
                      columns=['Estado', 'Cantidad'])
    fig = px.bar(df, x='Cantidad', y='Estado', orientation='h', text='Cantidad',
                 color_discrete_sequence=[COLOR_PALETTE.get('secondary')])
    fig.update_traces(texttemplate='%{text}', textposition='outside')

    layout_actualizado = copy.deepcopy(BASE_LAYOUT)
    layout_actualizado['title'] = {
        'text': 'Estado de Reclamaciones', 'x': 0.5, 'font': {'size': 11}}
    layout_actualizado['yaxis']['categoryorder'] = 'total ascending'
    layout_actualizado['yaxis']['title_text'] = None  # No title para Y
    layout_actualizado['xaxis']['title_text'] = "Cantidad"
    layout_actualizado['margin'] = {
        't': 50, 'b': 40, 'l': 150, 'r': 20}  # Más margen izquierdo
    layout_actualizado['showlegend'] = False
    fig.update_layout(**layout_actualizado)
    return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


def generar_grafico_monto_ramo(data_ramos):
    if not data_ramos or not any(v > 0 for v in data_ramos.values()):
        fig_error = generar_figura_sin_datos_plotly(
            "No hay montos por ramo disponibles.")
        return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    labels = list(data_ramos.keys())
    values = list(data_ramos.values())
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4, marker_colors=px.colors.qualitative.Pastel, textinfo='percent',
                    insidetextorientation='radial', hoverinfo='label+value+percent', hovertemplate='<b>%{label}</b><br>Monto: Bs. %{value:,.2f}<br>%{percent}<extra></extra>')])
    fig.update_traces(textfont_size=10, marker=dict(
        line=dict(color='#000000', width=1)))

    layout_actualizado = copy.deepcopy(BASE_LAYOUT)
    layout_actualizado['title'] = {
        'text': 'Distribución Monto Contratado por Ramo', 'x': 0.5, 'font': {'size': 11}}
    layout_actualizado['showlegend'] = False
    layout_actualizado['margin'] = {'t': 60, 'b': 40, 'l': 20, 'r': 20}
    layout_actualizado['annotations'] = [
        dict(text='Ramos', x=0.5, y=0.5, font_size=18, showarrow=False)]
    if 'xaxis' in layout_actualizado:
        layout_actualizado['xaxis']['visible'] = False
    if 'yaxis' in layout_actualizado:
        layout_actualizado['yaxis']['visible'] = False
    fig.update_layout(**layout_actualizado)
    return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


def generar_grafico_resolucion_gauge(avg_days):
    if avg_days is None:
        avg_days = 0
    max_val = max(avg_days * 1.5, 30)
    fig = go.Figure(go.Indicator(mode="gauge+number", value=float(avg_days), title={'text': "Tiempo Prom. Resolución (Días)", 'font': {'size': 10}}, number={'suffix': " días", 'valueformat': ".1f"},
                                 gauge={'axis': {'range': [0, max_val]}, 'bar': {'color': COLOR_PALETTE.get('primary')}, 'steps': [{'range': [0, 7], 'color': COLOR_PALETTE.get('success')}, {'range': [7, 15], 'color': COLOR_PALETTE.get('warning')}, {'range': [15, max_val], 'color': COLOR_PALETTE.get('secondary')}]}))

    layout_actualizado = copy.deepcopy(BASE_LAYOUT)
    layout_actualizado.pop('title', None)  # El título está en el indicador
    layout_actualizado['height'] = 250  # Más compacto
    layout_actualizado['margin'] = {
        't': 50, 'b': 10, 'l': 10, 'r': 10}  # Márgenes ajustados
    fig.update_layout(**layout_actualizado)
    return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


def generar_grafico_impuestos_por_categoria(data_igtf_dict):
    if not data_igtf_dict or not data_igtf_dict.get('Categoria') or not data_igtf_dict.get('IGTF') or not data_igtf_dict['Categoria']:
        fig_error = generar_figura_sin_datos_plotly(
            "No hay datos de IGTF por categoría.")
        return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    df = pd.DataFrame({'Categoria': data_igtf_dict['Categoria'], 'IGTF': pd.to_numeric(
        data_igtf_dict['IGTF'], errors='coerce').fillna(0.0)})
    df = df[df['IGTF'] > 0].copy()
    if df.empty:
        fig_error = generar_figura_sin_datos_plotly("No se recaudó IGTF.")
        return plot(fig_error, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    total_igtf = df['IGTF'].sum()
    fig = go.Figure(data=[go.Pie(labels=df['Categoria'].tolist(), values=df['IGTF'].tolist(), hole=.45, marker_colors=px.colors.qualitative.Plotly,
                    textinfo='percent', insidetextorientation='radial', hovertemplate='<b>%{label}</b><br>IGTF: Bs. %{value:,.2f}<br>%{percent}<extra></extra>')])
    fig.update_traces(textfont_size=10, marker=dict(
        line=dict(color='#FFFFFF', width=1)))

    layout_actualizado = copy.deepcopy(BASE_LAYOUT)
    layout_actualizado['title'] = {
        'text': 'Distribución IGTF por Origen/Ramo', 'x': 0.5, 'font': {'size': 11}}
    layout_actualizado['showlegend'] = False
    layout_actualizado['margin'] = {'t': 60, 'b': 40, 'l': 20, 'r': 20}
    layout_actualizado['annotations'] = [dict(
        # Font size anotación
        text=f'Total IGTF<br>Bs. {total_igtf:,.2f}', x=0.5, y=0.5, font_size=14, showarrow=False)]
    if 'xaxis' in layout_actualizado:
        layout_actualizado['xaxis']['visible'] = False
    if 'yaxis' in layout_actualizado:
        layout_actualizado['yaxis']['visible'] = False
    fig.update_layout(**layout_actualizado)
    return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

# --- FIN DE TODAS LAS FUNCIONES DE GRÁFICAS MODIFICADAS ---
