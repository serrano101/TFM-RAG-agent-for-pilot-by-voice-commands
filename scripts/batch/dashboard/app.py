
import streamlit as st

DEFAULT_CSV = "scripts/batch/resultados_postprocess.csv"

from dashboards.iteraciones import iteraciones_show_metrics
from dashboards.tiempos_respuesta import tiempos_respuesta_show_metrics
from dashboards.calidad_respuesta import calidad_show_metrics

# ---------------------------------
# App
# ---------------------------------

st.set_page_config(page_title="DASHBOARDS", page_icon="📊", layout="wide")
# Mostrar en el menu el dashboard que que quiere mostrar como tab
menu = st.sidebar.radio("Navigation", ["Interacciones", "Tiempo de respuesta", "Calidad de respuesta"])

if menu == "Interacciones":
    iteraciones_show_metrics(DEFAULT_CSV)
elif menu == "Tiempo de respuesta":
    tiempos_respuesta_show_metrics(DEFAULT_CSV)
elif menu == "Calidad de respuesta":
    calidad_show_metrics(DEFAULT_CSV)
