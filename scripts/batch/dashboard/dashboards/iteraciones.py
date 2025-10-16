import os
import pandas as pd
import streamlit as st
import plotly.express as px

from utils import find_col, normalize_input_type, load_csv  # pie_chart ya no se usa


def iteraciones_show_metrics(DEFAULT_CSV: str):
    st.title("Interacciones")
    # Sidebar
    csv_path = st.sidebar.text_input("Ruta CSV", value=DEFAULT_CSV)
    if not os.path.exists(csv_path):
        st.error(f"No existe el CSV: {csv_path}")
        st.stop()
    if st.sidebar.button("Recargar"):
        load_csv.clear()

    df = load_csv(csv_path)

    # Columnas necesarias
    col_input = find_col(df, ["Input Type (Text, audio, text+audio)", "Input Type"])
    col_procedure = find_col(df, ["Procedure"])
    if not col_input or not col_procedure:
        st.error("Faltan columnas: 'Input Type (Text, audio, text+audio)' y/o 'Procedure'.")
        st.stop()

    # Métricas base
    total_rows = len(df)
    types_norm = df[col_input].map(normalize_input_type)

    # Claves internas (del CSV) y etiquetas mostradas
    order = ["Text", "Audio", "Audio + Text", "Otro"]  # internas
    display_map = {
        "Text": "Texto",
        "Audio": "Audio",
        "Audio + Text": "Audio + Texto",
        "Otro": "Otro",
    }
    color_map_display = {
        "Texto": "#60A5FA",
        "Audio": "#34D399",
        "Audio + Texto": "#FBBF24",
        "Otro": "#CBD5E1",
    }

    dist = types_norm.value_counts().reindex(order).fillna(0).astype(int)

    top3 = (
        df[col_procedure]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .value_counts()
        .head(3)
    )

    # Layout: 2 columnas
    col1, col2 = st.columns(2)

    # Columna 1: Tarjeta + Top 3 (barras horizontales)
    with col1:
        st.subheader("Nº Total de interacciones")
        # Número grande y en negrita
        st.markdown(f"<div style='font-size: 56px; font-weight: 800; line-height:1; margin: 8px 0 24px 0;'>{total_rows}</div>", unsafe_allow_html=True)

        st.subheader("Top 3 procedimientos")
        if top3.empty:
            st.info("Sin datos de procedimientos.")
        else:
            top3_df = pd.DataFrame({"Procedure": top3.index, "Count": top3.values}).sort_values("Count")
            fig_bar = px.bar(
                top3_df,
                x="Count",
                y="Procedure",
                orientation="h",
                text="Count",
                # color="Count",
                # color_continuous_scale=["#93C5FD", "#60A5FA", "#1D4ED8"],
            )
            fig_bar.update_traces(
                textposition="outside",
                textfont=dict(size=18),  # etiquetas grandes
                hovertemplate="<b>%{y}</b><br>Apariciones: %{x}<extra></extra>",
            )
            fig_bar.update_layout(
                xaxis_title="<b>Apariciones</b>",
                yaxis_title="",
                font=dict(size=16),  # fuente base
                xaxis=dict(title_font=dict(size=18), tickfont=dict(size=14)),
                yaxis=dict(title_font=dict(size=18), tickfont=dict(size=14)),
                coloraxis_showscale=False,
                margin=dict(l=10, r=10, t=10, b=10),
            )
            st.plotly_chart(fig_bar, width="stretch")

    # Columna 2: Pie chart distribución Input Type
    with col2:
        st.subheader("Distribución del tipo de entrada")
        dist_nonzero = dist[dist > 0]
        if dist_nonzero.empty:
            st.info("No hay datos de tipos de entrada.")
        else:
            # DF con clave interna, etiqueta mostrada y total
            dist_df = (
                pd.DataFrame({"InputType": dist_nonzero.index, "Count": dist_nonzero.values})
                .reset_index(drop=True)
            )
            dist_df["Display"] = dist_df["InputType"].map(display_map).fillna(dist_df["InputType"])
            dist_df["Label"] = dist_df.apply(lambda r: f"{r['Display']} ({int(r['Count'])})", axis=1)

            fig_pie = px.pie(
                dist_df,
                names="Label",          # lo que aparece en la leyenda
                values="Count",
                hole=0.0,               # pie (no donut)
                color="Display",        # color por etiqueta mostrada
                color_discrete_map=color_map_display,
            )
            fig_pie.update_traces(
                textposition="inside",
                texttemplate="<b>%{percent:.1%}</b>",
                textfont=dict(size=18),
                hovertemplate="<b>%{label}</b><br>Porcentaje: %{percent:.1%}<br>Cantidad: %{value}<extra></extra>",
                sort=False,
                pull=[0.02] * len(dist_df),
                marker=dict(line=dict(color="white", width=2)),
            )
            fig_pie.update_layout(
                legend=dict(font=dict(size=14)),
                font=dict(size=16),
                margin=dict(l=10, r=10, t=10, b=10),
            )
            st.plotly_chart(fig_pie, width="stretch")