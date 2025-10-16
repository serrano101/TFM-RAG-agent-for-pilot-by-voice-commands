import os
import pandas as pd
import streamlit as st
import plotly.express as px

from utils import find_col, normalize_input_type, load_csv

def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")

def _first_words(text: str, n: int = 5) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    parts = s.split()
    return " ".join(parts[:n])

def tiempos_respuesta_show_metrics(DEFAULT_CSV: str):
    st.title("Tiempo de respuesta")

    # Sidebar
    csv_path = st.sidebar.text_input("Ruta CSV", value=DEFAULT_CSV)
    # Mostrar tarjetas con mediana en vez de media (opcional)
    use_median = st.sidebar.checkbox("Usar mediana en tarjetas", value=False)
    if not os.path.exists(csv_path):
        st.error(f"No existe el CSV: {csv_path}")
        st.stop()
    if st.sidebar.button("Recargar"):
        load_csv.clear()

    df = load_csv(csv_path)

    # Columnas necesarias
    col_input = find_col(df, ["Input Type (Text, audio, text+audio)", "Input Type"])
    col_total = find_col(df, ["Total time", "Total Time"])
    col_asr = find_col(df, ["ASR time", "ASR Time"])
    col_rag_time = find_col(df, ["RAG Time"])
    col_tts = find_col(df, ["TTS Time"])
    col_rag_score = find_col(df, ["RAG Avg Score", "RAG Score", "RAG AvgScore"])
    col_rag_status = find_col(df, ["RAG Status"])
    col_text_input = find_col(df, ["Text Input"])
    col_transcribed = find_col(df, ["Transcribed Audio Text"])
    col_answer_correct = find_col(df, ["¿Answer Correct?(Yes/No)", "Answer Correct", "Answer Correct?(Yes/No)"])

    needed = [col_input, col_total, col_rag_time, col_tts, col_rag_status, col_text_input, col_transcribed]
    if any(c is None for c in needed):
        st.error("Faltan columnas requeridas en el CSV (Input Type, Total time, RAG Time, TTS Time, RAG Status, Text Input, Transcribed Audio Text).")
        st.stop()

    # Normalizar tipos de entrada
    type_norm = df[col_input].map(normalize_input_type)

    # Series numéricas
    total_s = _to_num(df[col_total])
    asr_s = _to_num(df[col_asr]) if col_asr else pd.Series([pd.NA] * len(df))
    rag_time_s = _to_num(df[col_rag_time])
    tts_s = _to_num(df[col_tts])

    # Filtros
    mask_text = type_norm.eq("Text")
    mask_with_asr = type_norm.isin(["Audio", "Audio + Text"])

    # Medias
    avg_total_no_asr = total_s[mask_text].dropna().mean()
    avg_total_with_asr = total_s[mask_with_asr].dropna().mean()
    avg_asr = asr_s.dropna().mean()
    avg_rag = rag_time_s.dropna().mean()
    avg_tts = tts_s.dropna().mean()

    # Medianas
    med_total_no_asr = total_s[mask_text].dropna().median()
    med_total_with_asr = total_s[mask_with_asr].dropna().median()
    med_asr = asr_s.dropna().median()
    med_rag = rag_time_s.dropna().median()
    med_tts = tts_s.dropna().median()

    # Tarjetas (media por defecto; opcional mediana)
    c1, c2, c3, c4, c5 = st.columns(5)
    if not use_median:
        c1.metric("Media total sin ASR (s)", f"{(avg_total_no_asr or 0):.2f}")
        c2.metric("Media total con ASR (s)", f"{(avg_total_with_asr or 0):.2f}")
        c3.metric("Media ASR (s)", f"{(avg_asr or 0):.2f}")
        c4.metric("Media RAG (s)", f"{(avg_rag or 0):.2f}")
        c5.metric("Media TTS (s)", f"{(avg_tts or 0):.2f}")
    else:
        c1.metric("Mediana total sin ASR (s)", f"{(med_total_no_asr or 0):.2f}")
        c2.metric("Mediana total con ASR (s)", f"{(med_total_with_asr or 0):.2f}")
        c3.metric("Mediana ASR (s)", f"{(med_asr or 0):.2f}")
        c4.metric("Mediana RAG (s)", f"{(med_rag or 0):.2f}")
        c5.metric("Mediana TTS (s)", f"{(med_tts or 0):.2f}")

    # Segunda fila: 2 columnas
    left, right = st.columns(2)

    # Boxplots por tipo
    with left:
        st.subheader("Distribución por tipo")
        df_box = pd.DataFrame()

        if mask_text.any():
            df_box = pd.concat([
                df_box,
                pd.DataFrame({"Metric": "Total sin ASR", "Value": total_s[mask_text].dropna()})
            ])
        if mask_with_asr.any():
            df_box = pd.concat([
                df_box,
                pd.DataFrame({"Metric": "Total con ASR", "Value": total_s[mask_with_asr].dropna()})
            ])
        if col_asr:
            df_box = pd.concat([df_box, pd.DataFrame({"Metric": "ASR", "Value": asr_s.dropna()})])
        df_box = pd.concat([df_box, pd.DataFrame({"Metric": "RAG", "Value": rag_time_s.dropna()})])
        df_box = pd.concat([df_box, pd.DataFrame({"Metric": "TTS", "Value": tts_s.dropna()})])

        if df_box.empty:
            st.info("No hay datos suficientes para los boxplots.")
        else:
            order = ["Total sin ASR", "Total con ASR", "ASR", "RAG", "TTS"]
            df_box["Metric"] = pd.Categorical(df_box["Metric"], categories=order, ordered=True)
            fig_box = px.box(
                df_box, x="Metric", y="Value", points="outliers", color="Metric",
                color_discrete_map={
                    "Total sin ASR": "#60A5FA",
                    "Total con ASR": "#34D399",
                    "ASR": "#F59E0B",
                    "RAG": "#A78BFA",
                    "TTS": "#F472B6",
                },
                labels={"Value": "t (s)", "Metric": ""}
            )

            # Ocultar la leyenda de los boxes (quedan sin entradas)
            fig_box.for_each_trace(lambda tr: tr.update(showlegend=False))

            # Solo media: marcador como punto rojo pequeño
            means = df_box.groupby("Metric")["Value"].mean().reindex(order)
            fig_box.add_scatter(
                x=means.index,
                y=means.values,
                mode="markers",
                name="Media (promedio)",
                showlegend=True,
                marker=dict(symbol="circle", size=7, color="#EF4444", line=dict(width=0)),
                hovertemplate="Media: %{y:.3f} s<extra></extra>",
            )

            # Aumentar tamaños de ejes y marcas
            fig_box.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title="",
                yaxis_title="t (s)",
                legend=dict(orientation="h", y=1.10, x=0.0, font=dict(size=15)),
                font=dict(size=17),
                xaxis=dict(tickfont=dict(size=17), title_font=dict(size=19)),
                yaxis=dict(tickfont=dict(size=17), title_font=dict(size=19)),
            )
            st.plotly_chart(fig_box, width="stretch")

    # Nueve: Boxplots RAG por estado (success vs no_match)
    with right:
        st.subheader("RAG: Tiempo por estado")
        # Normalizar estado y quedarnos solo con success / no_match
        status_raw = df[col_rag_status].astype(str).str.strip().str.lower()
        def map_status(s: str) -> str | None:
            s = (s or "").lower()
            if s in ("success", "ok"):
                return "success"
            if s in ("no_match", "no-match", "nomatch"):
                return "no_match"
            return None
        df_status = pd.DataFrame({
            "Status": status_raw.map(map_status),
            "Time": rag_time_s
        }).dropna(subset=["Status", "Time"])

        if df_status.empty:
            st.info("No hay datos suficientes para los boxplots por estado.")
        else:
            # Mapa de visualización
            display_map = {"success": "Respuesta", "no_match": "No contenido"}
            order_status = ["success", "no_match"]
            order_display = [display_map[s] for s in order_status]

            df_status = df_status[df_status["Status"].isin(order_status)].copy()
            df_status["Status"] = pd.Categorical(df_status["Status"], categories=order_status, ordered=True)
            df_status["StatusDisp"] = df_status["Status"].map(display_map)

            fig_box_status = px.box(
                df_status,
                x="StatusDisp",
                y="Time",
                color="StatusDisp",
                points="outliers",
                category_orders={"StatusDisp": order_display},
                color_discrete_map={
                    "Respuesta": "#22C55E",   # verde
                    "No contenido": "#94A3B8" # gris
                },
                labels={"StatusDisp": "Estado de respuesta", "Time": "Tiempo RAG (s)"},
            )
            # Ocultar leyenda (el eje X ya nombra cada grupo)
            fig_box_status.update_layout(
                showlegend=False,
                margin=dict(l=10, r=10, t=10, b=10),
                font=dict(size=17),
                xaxis=dict(title_font=dict(size=19), tickfont=dict(size=17)),
                yaxis=dict(title_font=dict(size=19), tickfont=dict(size=17)),
            )
            st.plotly_chart(fig_box_status, width="stretch")
