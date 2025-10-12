import os
import ast
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils import find_col, load_csv  # ya existen en tu paquete de dashboards


def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _norm_yesno(x: str) -> str:
    s = str(x or "").strip().lower()
    if s in ("yes", "y", "true", "1"):
        return "yes"
    if s in ("no", "n", "false", "0"):
        return "no"
    return ""


def _norm_status(x: str) -> str:
    s = str(x or "").strip().lower()
    if s in ("success", "ok"):
        return "success"
    if s in ("no_match", "no-match", "nomatch"):
        return "no_match"
    return "other"


# Mapa de color por clave interna (success / no_match / other)
COLOR_STATUS = {
    "success": "#22C55E",
    "no_match": "#94A3B8",
    "other": "#F59E0B",
}
# Etiquetas a mostrar para cada clave interna
DISPLAY_STATUS = {
    "success": "Respuesta",
    "no_match": "No contenido",
    "other": "Otro",
}


def _pie_from_series(series: pd.Series, title: str, color_map: dict[str, str], display_map: dict[str, str]):
    counts = (
        series.value_counts()
        .reindex(["success", "no_match", "other"])
        .fillna(0)
        .astype(int)
        .reset_index()
    )
    counts.columns = ["Status", "Count"]  # Status es la clave interna
    counts = counts[counts["Count"] > 0]
    if counts.empty:
        return None
    counts["Label"] = counts.apply(lambda r: f"{display_map.get(r['Status'], r['Status'])} ({int(r['Count'])})", axis=1)
    fig = px.pie(
        counts,
        names="Label",           # lo que se ve en la leyenda
        values="Count",
        color="Status",          # color por clave interna
        color_discrete_map=color_map,  # color_map con claves internas
        hole=0.0,
    )
    fig.update_traces(
        textposition="inside",
        texttemplate="%{percent:.1%}",
        hovertemplate="<b>%{label}</b><br>Cantidad: %{value}<br>Porcentaje: %{percent:.1%}<extra></extra>",
        sort=False,
        pull=[0.02] * len(counts),
    )
    fig.update_layout(
        title=title,
        legend_title_text="",
        margin=dict(l=10, r=10, t=40, b=10),
        font=dict(size=16),
    )
    return fig


def _pie_counts(series: pd.Series, color_map: dict[str, str], display_map: dict[str, str]):
    vc = (
        series.value_counts()
        .reindex(["success", "no_match", "other"])
        .fillna(0)
        .astype(int)
    )
    # Etiquetas mostradas (sin totales) usando display_map
    labels = [display_map.get(k, k) for k, v in vc.items() if v > 0]
    values = [int(v) for v in vc.values if v > 0]
    colors = [color_map[k] for k, v in vc.items() if v > 0]  # color por clave interna
    return labels, values, colors


def _confusion_counts(expect_yes: pd.Series, status: pd.Series) -> dict[str, int]:
    # VP: expected yes & status success
    vp = ((expect_yes == "yes") & (status == "success")).sum()
    # VN: expected no & status no_match
    vn = ((expect_yes == "no") & (status == "no_match")).sum()
    # FP: expected no & status success
    fp = ((expect_yes == "no") & (status == "success")).sum()
    # FN: expected yes & status no_match
    fn = ((expect_yes == "yes") & (status == "no_match")).sum()
    total = vp + vn + fp + fn
    return dict(VP=vp, VN=vn, FP=fp, FN=fn, TOTAL=total)


def _confusion_matrix_figure(counts: dict[str, int]):
    # Matriz 2x2: filas = Expected (Yes/No), columnas = Real (success/no_match)
    vp, vn, fp, fn = counts["VP"], counts["VN"], counts["FP"], counts["FN"]
    total = max(vp + vn + fp + fn, 1)
    z = np.array([[vp, fn], [fp, vn]])
    text = np.array([
        [f"VP: {vp} ({vp/total:.1%})", f"FN: {fn} ({fn/total:.1%})"],
        [f"FP: {fp} ({fp/total:.1%})", f"VN: {vn} ({vn/total:.1%})"],
    ])
    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=["Respuesta", "No contenido"],
        y=["Si", "No"],
        colorscale="Blues",
        showscale=False,
        text=text,
        hovertemplate="Real: %{x}<br>Esperado: %{y}<br>%{text}<extra></extra>",
    ))
    fig.update_traces(texttemplate="%{text}", textfont={"size": 14})
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        font=dict(size=16),
        xaxis_title="Estado del RAG (Real)",
        yaxis_title="¿Se espera respuesta?",
    )
    return fig


def _metrics_from_confusion(vp: int, vn: int, fp: int, fn: int, vp_correct: int) -> dict[str, float]:
    # Evitar división por 0
    def safe_div(a, b):
        return float(a) / float(b) if b else np.nan

    recall = safe_div(vp, vp + fn)
    recall_real = safe_div(vp_correct, vp + fn)
    specificity = safe_div(vn, vn + fp)
    precision = safe_div(vp, vp + fp)
    precision_real = safe_div(vp_correct, vp + fp)
    # F1 por precision/recall
    f1 = safe_div(2 * precision * recall, (precision + recall))
    accuracy = safe_div(vp + vn, vp + vn + fp + fn)
    accuracy_real = safe_div(vp_correct + vn, vp + vn + fp + fn)
    # F1 real por precision_real/recall_real
    f1_real = safe_div(2 * precision_real * recall_real, (precision_real + recall_real))

    return dict(
        recall=recall,
        recall_real=recall_real,
        specificity=specificity,
        precision=precision,
        precision_real=precision_real,
        f1=f1,
        f1_real=f1_real,
        accuracy=accuracy,
        accuracy_real=accuracy_real,
    )


def _level_metrics(df_level: pd.DataFrame, col_expected_yesno: str, col_status: str, col_answer_correct: str | None):
    expected = df_level[col_expected_yesno].map(_norm_yesno)
    status = df_level[col_status].map(_norm_status)
    ans_correct = df_level[col_answer_correct].map(_norm_yesno) if col_answer_correct else pd.Series([""] * len(df_level))

    counts = _confusion_counts(expected, status)
    vp, vn, fp, fn = counts["VP"], counts["VN"], counts["FP"], counts["FN"]
    vp_correct = ((expected == "yes") & (status == "success") & (ans_correct == "yes")).sum()
    return _metrics_from_confusion(vp, vn, fp, fn, vp_correct)


def calidad_show_metrics(DEFAULT_CSV: str):
    st.title("Calidad de la respuesta")

    # Sidebar
    csv_path = st.sidebar.text_input("Ruta CSV", value=DEFAULT_CSV)
    if not os.path.exists(csv_path):
        st.error(f"No existe el CSV: {csv_path}")
        st.stop()
    if st.sidebar.button("Recargar"):
        load_csv.clear()

    df = load_csv(csv_path)

    # Columnas necesarias
    col_expected_yesno = find_col(df, ["¿Expected answer? (Yes/No)", "Expected answer", "Expected", "Expected (Yes/No)"])
    col_status = find_col(df, ["RAG Status"])
    col_score = find_col(df, ["RAG Avg Score", "RAG Score"])
    col_time_rag = find_col(df, ["RAG Time"])
    col_asr_time = find_col(df, ["ASR time", "ASR Time"])
    col_tts_time = find_col(df, ["TTS Time"])
    col_level = find_col(df, ["Level (N1,N2,N3)", "Level"])
    col_wer = find_col(df, ["WER"])
    col_pages = find_col(df, ["RAG Pages"])
    col_answer_correct = find_col(df, ["¿Answer Correct?(Yes/No)", "Answer Correct"])
    col_text_input = find_col(df, ["Text Input"])
    col_transcribed = find_col(df, ["Transcribed Audio Text"])

    needed = [col_expected_yesno, col_status, col_time_rag, col_level]
    if any(c is None for c in needed):
        st.error("Faltan columnas requeridas (Expected, RAG Status, RAG Time, Level).")
        st.stop()

    # Normalizaciones base
    expected_yesno = df[col_expected_yesno].map(_norm_yesno)
    status_norm = df[col_status].map(_norm_status)

    # Series para gráficos: mantener claves internas (success/no_match/other)
    expected_as_status = expected_yesno.map(lambda s: "success" if s == "yes" else ("no_match" if s == "no" else "other"))
    # (Opcional) figuras sueltas con px.pie si se necesitasen en otro layout
    fig_expected = _pie_from_series(expected_as_status, "Estado esperado", COLOR_STATUS, DISPLAY_STATUS)
    fig_real = _pie_from_series(status_norm, "Estado real", COLOR_STATUS, DISPLAY_STATUS)

    # =====================================================
    # FILA 1: Score vs RAG Time (izquierda) + WER (derecha)
    # =====================================================
    c_left, c_right = st.columns([1, 2])

    # Derecha: Puntuación Búsqueda vs Tiempo RAG (por estado) — ejes: x=Puntuación Búsqueda, y=Tiempo RAG
    with c_right:
        st.subheader("Puntuación Búsqueda vs Tiempo RAG (por estado)")
        if not (col_score and col_time_rag):
            st.info("Faltan columnas de score o tiempo.")
        else:
            score = _to_num(df[col_score])
            time_rag = _to_num(df[col_time_rag])
            ans_corr = df[col_answer_correct].map(_norm_yesno) if col_answer_correct else pd.Series([""] * len(df))
            def make_label(s, a):
                if s == "success":
                    return "Respuesta · Correcto" if a == "yes" else "Respuesta · Incorrecto"
                if s == "no_match":
                    return "No contenido · Correcto" if a == "yes" else "No contenido · Incorrecto"
                return "other"
            df_plot = pd.DataFrame({"Score": score, "RAG Time": time_rag, "Status": status_norm, "Answer": ans_corr})
            df_plot["Label"] = df_plot.apply(lambda r: make_label(r["Status"], r["Answer"]), axis=1)
            df_plot = df_plot.dropna(subset=["Score", "RAG Time"])
            color_map = {
                "Respuesta · Correcto": "#22C55E",
                "Respuesta · Incorrecto": "#EF4444",
                "No contenido · Correcto": "#9CA3AF",
                "No contenido · Incorrecto": "#111827",
                "other": "#F59E0B",
            }
            symbol_map = {
                "Respuesta · Correcto": "circle",
                "Respuesta · Incorrecto": "circle",
                "No contenido · Correcto": "diamond",
                "No contenido · Incorrecto": "diamond",
                "other": "x",
            }
            fig_scatter = px.scatter(
                df_plot,
                x="Score", y="RAG Time",
                color="Label", symbol="Label",
                color_discrete_map=color_map, symbol_map=symbol_map,
                category_orders={"Label": ["Respuesta · Correcto", "Respuesta · Incorrecto",
                                           "No contenido · Correcto", "No contenido · Incorrecto", "other"]},
                labels={"Score": "Puntuación Búsqueda RAG", "RAG Time": "Tiempo RAG (s)", "Label": "Estado"},
                hover_data={"Score": True, "RAG Time": True, "Label": True},
            )
            fig_scatter.update_traces(marker=dict(size=10))
            fig_scatter.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                font=dict(size=16),
                xaxis=dict(title_font=dict(size=18), tickfont=dict(size=16)),
                yaxis=dict(title_font=dict(size=18), tickfont=dict(size=16)),
            )
            st.plotly_chart(fig_scatter, width="stretch")

    # Izquierda: WER
    with c_left:
        st.subheader("Calidad transcripción ASR")
        if col_wer and df[col_wer].notna().any():
            wer = _to_num(df[col_wer]).dropna() * 100.0  # a porcentaje
            if wer.empty:
                st.info("WER sin valores válidos.")
            else:
                fig_wer = px.box(
                    pd.DataFrame({"WER%": wer}),
                    y="WER%",
                    points="outliers",
                    color_discrete_sequence=["#60A5FA"],
                )
                fig_wer.update_layout(
                    showlegend=False,
                    margin=dict(l=10, r=10, t=10, b=10),
                    font=dict(size=16),
                    yaxis=dict(title="WER (%)", title_font=dict(size=18), tickfont=dict(size=16)),
                )
                st.plotly_chart(fig_wer, width="stretch")
        else:
            st.info("No existe columna WER.")

    st.markdown("---")

    # =====================================================
    # FILA 2: tres columnas (pies | matriz | VP)
    # Prioridad de ancho: col2 > col3; damos un poco más a col1 para que no se solapen títulos/leyenda
    # =====================================================
    m1, m2, m3 = st.columns([3, 5, 4])

    with m1:
        st.subheader("Estado")
        # Subplot con dos pies uno debajo del otro
        lab1, val1, col1 = _pie_counts(expected_as_status, COLOR_STATUS, DISPLAY_STATUS)
        lab2, val2, col2 = _pie_counts(status_norm, COLOR_STATUS, DISPLAY_STATUS)
        if not val1 and not val2:
            st.info("Sin datos para los estados esperado y real.")
        else:
            fig_pies = make_subplots(
                rows=2, cols=1,
                specs=[[{"type": "domain"}], [{"type": "domain"}]],
                subplot_titles=("Estado esperado", "Estado real"),
                vertical_spacing=0.15,
            )
            if val1:
                fig_pies.add_trace(
                    go.Pie(
                        labels=lab1, values=val1, marker=dict(colors=col1),
                        hole=0.0,  # pie chart (sin agujero)
                        textposition="inside",
                        texttemplate="%{percent:.1%} (%{value})",
                        hovertemplate="<b>%{label}</b><br>Cantidad: %{value}<br>Porcentaje: %{percent:.1%}<extra></extra>",
                        sort=False, showlegend=True, name="Esperado",
                    ),
                    row=1, col=1
                )
            if val2:
                fig_pies.add_trace(
                    go.Pie(
                        labels=lab2, values=val2, marker=dict(colors=col2),
                        hole=0.0,  # pie chart (sin agujero)
                        textposition="inside",
                        texttemplate="%{percent:.1%} (%{value})",
                        hovertemplate="<b>%{label}</b><br>Cantidad: %{value}<br>Porcentaje: %{percent:.1%}<extra></extra>",
                        sort=False, showlegend=False, name="Real",
                    ),
                    row=2, col=1
                )
            fig_pies.update_layout(
                # Movemos la leyenda abajo y dejamos margen para que no choque con títulos
                margin=dict(l=10, r=10, t=50, b=80),
                font=dict(size=16),
                legend=dict(orientation="h", y=-0.06, x=0.0, font=dict(size=14), title_text=""),
                height=560
            )
            st.plotly_chart(fig_pies, use_container_width=True)

    # Matriz de confusión en la columna central (más ancha)
    counts = _confusion_counts(expected_yesno, status_norm)
    with m2:
        st.subheader("Matriz de confusión")
        fig_cm = _confusion_matrix_figure(counts)
        st.plotly_chart(fig_cm, width="stretch")
        with st.expander("Definiciones"):
            st.markdown(
                "- FP (Falso Positivo): Se espera que no de respuesta y la da\n"
                "- FN (Falso Negativo): Se espera que de respuesta y no la da\n"
                "- VP (Verdadero Positivo): Se espera que de respuesta y la da\n"
                "- VN (Verdadero Negativo): Se espera que no de respuesta y no la da"
            )

    # Desglose VP en la tercera columna (más estrecha)
    with m3:
        st.subheader("Desglose de VP")
        ans_corr = df[col_answer_correct].map(_norm_yesno) if col_answer_correct else pd.Series([""] * len(df))
        vp_mask = (expected_yesno == "yes") & (status_norm == "success")
        vp_total = int(vp_mask.sum())
        vp_correct = int((vp_mask & (ans_corr == "yes")).sum())
        vp_incorrect = int((vp_mask & (ans_corr == "no")).sum())

        if vp_total == 0:
            st.info("No hay VP para desglosar.")
        else:
            df_vp = pd.DataFrame({
                "Grupo": ["VP", "VP"],
                "Contenido de la respuesta": ["Correcto", "Incorrecto"],
                "Count": [vp_correct, vp_incorrect],
                "PctVP": [vp_correct / vp_total * 100.0, vp_incorrect / vp_total * 100.0],
            })
            df_vp["Etiqueta"] = df_vp.apply(lambda r: f"{int(r['Count'])} ({r['PctVP']:.1f}%)", axis=1)

            fig_vp = px.bar(
                df_vp,
                x="Grupo", y="Count", color="Contenido de la respuesta",
                barmode="stack",
                color_discrete_map={
                    "Correcto": "#22C55E",
                    "Incorrecto": "#EF4444",
                },
                text="Etiqueta",
                labels={"Grupo": "", "Count": "Total VP"},
            )
            fig_vp.update_traces(textposition="inside")
            fig_vp.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                font=dict(size=16),
                xaxis=dict(title_font=dict(size=18), tickfont=dict(size=16)),
                yaxis=dict(title_font=dict(size=18), tickfont=dict(size=16)),
                legend=dict(orientation="h", y=1.10, x=0.0, font=dict(size=14)),
            )
            st.plotly_chart(fig_vp, width="stretch")

    st.markdown("---")

    # NUEVA FILA: Métricas (2 columnas)
    r1, r2 = st.columns(2)
    vp, vn, fp, fn = counts["VP"], counts["VN"], counts["FP"], counts["FN"]
    # reutilizar vp_correct si existe; si no, calcular:
    if 'vp_correct' not in locals():
        ans_corr = df[col_answer_correct].map(_norm_yesno) if col_answer_correct else pd.Series([""] * len(df))
        vp_mask = (expected_yesno == "yes") & (status_norm == "success")
        vp_correct = int((vp_mask & (ans_corr == "yes")).sum())
    metrics = _metrics_from_confusion(vp, vn, fp, fn, vp_correct)
    def latex_pct(val: float) -> str:
        # Solo porcentaje (ej. 87.5%)
        return "—" if pd.isna(val) else f"{100*val:.1f}\\%"

    with r1:
        st.subheader("Métricas (I)")
        st.latex(rf"\textbf{{Recall}}=\frac{{VP}}{{VP+FN}}=\frac{{{vp}}}{{{vp}+{fn}}}={latex_pct(metrics['recall'])}")
        st.latex(rf"\textbf{{Recall\ real}}=\frac{{VP_{{\text{{correctos}}}}}}{{VP+FN}}=\frac{{{vp_correct}}}{{{vp}+{fn}}}={latex_pct(metrics['recall_real'])}")
        st.latex(rf"\textbf{{Especificidad}}=\frac{{VN}}{{VN+FP}}=\frac{{{vn}}}{{{vn}+{fp}}}={latex_pct(metrics['specificity'])}")
        st.latex(rf"\textbf{{Exactitud}}=\frac{{VP+VN}}{{VP+VN+FP+FN}}=\frac{{{vp}+{vn}}}{{{vp}+{vn}+{fp}+{fn}}}={latex_pct(metrics['accuracy'])}")
        st.latex(rf"\textbf{{Exactitud\ real}}=\frac{{VP_{{\text{{correctos}}}}+VN}}{{VP+VN+FP+FN}}=\frac{{{vp_correct}+{vn}}}{{{vp}+{vn}+{fp}+{fn}}}={latex_pct(metrics['accuracy_real'])}")
    with r2:
        st.subheader("Métricas (II)")
        st.latex(rf"\textbf{{Precision}}=\frac{{VP}}{{VP+FP}}=\frac{{{vp}}}{{{vp}+{fp}}}={latex_pct(metrics['precision'])}")
        st.latex(rf"\textbf{{Precision\ real}}=\frac{{VP_{{\text{{correctos}}}}}}{{VP+FP}}=\frac{{{vp_correct}}}{{{vp}+{fp}}}={latex_pct(metrics['precision_real'])}")
        # Sustitución con valores decimales de precision y recall
        pr, rc = metrics['precision'], metrics['recall']
        prr, rcr = metrics['precision_real'], metrics['recall_real']
        st.latex(rf"\textbf{{F1}}=\frac{{2\cdot \text{{Precision}}\cdot \text{{Recall}}}}{{\text{{Precision}}+\text{{Recall}}}}"
                 rf"=\frac{{2\cdot {pr:.3f}\cdot {rc:.3f}}}{{{pr:.3f}+{rc:.3f}}}={latex_pct(metrics['f1'])}")
        st.latex(rf"\textbf{{F1\ real}}=\frac{{2\cdot \text{{Precision real}}\cdot \text{{Recall real}}}}{{\text{{Precision real}}+\text{{Recall real}}}}"
                 rf"=\frac{{2\cdot {prr:.3f}\cdot {rcr:.3f}}}{{{prr:.3f}+{rcr:.3f}}}={latex_pct(metrics['f1_real'])}")


    st.markdown("---")

    # 3ª FILA: dos columnas (barras agrupadas por nivel con métricas % + boxplots ASR/RAG/TTS por nivel)
    g1, g2 = st.columns(2)

    with g1:
        st.subheader("Métricas por nivel (N1/N2/N3)")
        if not col_level:
            st.info("No existe la columna de nivel.")
        else:
            levels = ["N1", "N2", "N3"]
            rows = []
            for lvl in levels:
                part = df[df[col_level].astype(str).str.strip().str.upper() == lvl]
                if part.empty:
                    continue
                m = _level_metrics(part, col_expected_yesno, col_status, col_answer_correct)
                rows += [
                    dict(Level=lvl, Metric="recall_real", Value=m["recall_real"]),
                    dict(Level=lvl, Metric="precision_real", Value=m["precision_real"]),
                    dict(Level=lvl, Metric="especificidad", Value=m["specificity"]),
                    # usar valores reales
                    dict(Level=lvl, Metric="exactitud_real", Value=m["accuracy_real"]),
                    dict(Level=lvl, Metric="f1_real", Value=m["f1_real"]),
                ]
            if not rows:
                st.info("Sin datos por nivel.")
            else:
                dfm = pd.DataFrame(rows)
                dfm["Percent"] = dfm["Value"] * 100.0
                order_metrics = ["recall_real", "precision_real", "especificidad", "exactitud_real", "f1_real"]
                dfm["Metric"] = pd.Categorical(dfm["Metric"], categories=order_metrics, ordered=True)
                fig_grp = px.bar(
                    dfm,
                    x="Metric",
                    y="Percent",
                    color="Level",
                    barmode="group",
                    range_y=[0, 100],
                    category_orders={"Metric": order_metrics, "Level": ["N1", "N2", "N3"]},
                    color_discrete_map={"N1": "#60A5FA", "N2": "#34D399", "N3": "#FBBF24"},
                    labels={"Percent": "%", "Metric": "Métrica"},
                    text=dfm["Percent"].round(1).astype(str) + "%",
                )
                fig_grp.update_traces(textposition="outside")
                fig_grp.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(orientation="h", y=1.12, x=0.0, font=dict(size=14)),
                    font=dict(size=16),
                    xaxis=dict(title_font=dict(size=18), tickfont=dict(size=16)),
                    yaxis=dict(title_font=dict(size=18), tickfont=dict(size=16)),
                )
                st.plotly_chart(fig_grp, width="stretch")

    with g2:
        st.subheader("Tiempos por etapa y nivel")
        # Construir long DF con ASR/RAG/TTS y Level
        stacks = []
        if col_asr_time:
            stacks.append(pd.DataFrame({"Stage": "ASR", "Value": _to_num(df[col_asr_time]), "Level": df[col_level]}))
        stacks.append(pd.DataFrame({"Stage": "RAG", "Value": _to_num(df[col_time_rag]), "Level": df[col_level]}))
        if col_tts_time:
            stacks.append(pd.DataFrame({"Stage": "TTS", "Value": _to_num(df[col_tts_time]), "Level": df[col_level]}))
        long_df = pd.concat(stacks, ignore_index=True)
        long_df = long_df.dropna(subset=["Value", "Level"])
        if long_df.empty:
            st.info("Sin datos de tiempos para boxplots.")
        else:
            long_df["Level"] = long_df["Level"].astype(str).str.strip().str.upper()
            fig_box_lvl = px.box(
                long_df,
                x="Stage",
                y="Value",
                color="Level",
                category_orders={"Stage": ["ASR", "RAG", "TTS"], "Level": ["N1", "N2", "N3"]},
                points="outliers",
                labels={"Value": "t (s)", "Stage": ""},
                color_discrete_map={"N1": "#60A5FA", "N2": "#34D399", "N3": "#FBBF24"},
            )
            fig_box_lvl.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                font=dict(size=16),
                xaxis=dict(title_font=dict(size=18), tickfont=dict(size=16)),
                yaxis=dict(title_font=dict(size=18), tickfont=dict(size=16)),
            )
            st.plotly_chart(fig_box_lvl, width="stretch")

    st.markdown("---")

    # =====================================================
    # FILA FINAL: solo histograma de páginas a ancho completo
    # =====================================================
    st.subheader("Consulta de las páginas del PDF")
    # Parsear arrays de páginas, aplanar y contar
    if not col_pages or df[col_pages].isna().all():
        st.info("No hay datos de RAG Pages.")
    else:
        pages = []
        for val in df[col_pages].dropna():
            v = val
            if isinstance(v, str):
                try:
                    v = ast.literal_eval(v)
                except Exception:
                    continue
            if isinstance(v, (list, tuple, set)):
                for x in v:
                    try:
                        pages.append(int(float(x)))
                    except Exception:
                        continue
            else:
                try:
                    pages.append(int(float(v)))
                except Exception:
                    continue

        if not pages:
            st.info("No se pudieron extraer páginas.")
        else:
            ser = pd.Series(pages)
            counts = ser.value_counts().sort_index()
            df_pages = pd.DataFrame({"Page": counts.index.astype(int), "Count": counts.values})
            fig_hist_pages = px.bar(
                df_pages,
                x="Page",
                y="Count",
                labels={"Page": "Número de páginas", "Count": "Frecuencia"},
                color_discrete_sequence=["#1D4ED8"],
            )
            fig_hist_pages.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                font=dict(size=16),
                xaxis=dict(title_font=dict(size=18), tickfont=dict(size=16)),
                yaxis=dict(title_font=dict(size=18), tickfont=dict(size=16)),
            )
            # Eje X con saltos de 1 en 1
            fig_hist_pages.update_xaxes(tickmode="linear", dtick=1)
            st.plotly_chart(fig_hist_pages, use_container_width=True)
