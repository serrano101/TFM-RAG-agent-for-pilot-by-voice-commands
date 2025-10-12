import os
import time
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# ---------------------------------
# Utils
# ---------------------------------
def find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    norm = {c.strip().lower(): c for c in df.columns}
    for cand in candidates:
        c = norm.get(cand.strip().lower())
        if c:
            return c
    return None

def normalize_input_type(x: str) -> str:
    s = str(x or "").strip().lower()
    if "audio" in s and "text" in s:
        return "Audio + Text"
    if "audio" in s:
        return "Audio"
    if "text" in s:
        return "Text"
    return "Otro"

@st.cache_data(show_spinner=False)
def load_csv(path: str) -> pd.DataFrame:
    _ = os.path.getmtime(path) if os.path.exists(path) else time.time()
    return pd.read_csv(path)

def pie_chart(counts_labels: list[tuple[int, str]]):
    # counts_labels: [(count, label), ...] sin ceros
    counts = [c for c, _ in counts_labels]
    labels = [l for _, l in counts_labels]
    colors = ["#60A5FA", "#34D399", "#FBBF24", "#CBD5E1"][: len(counts)]
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    wedges, _texts, _autotexts = ax.pie(
        counts,
        labels=None,                # leyenda a parte
        autopct="%1.1f%%",         # % dentro del gráfico
        startangle=140,
        colors=colors,
        pctdistance=0.70,
        wedgeprops={"linewidth": 1, "edgecolor": "white"},
        textprops={"fontsize": 10, "color": "black"},
    )
    legend_labels = [f"{lbl} ({cnt})" for cnt, lbl in counts_labels]
    ax.legend(wedges, legend_labels, title="Input Type", loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False)
    ax.set_aspect("equal")
    fig.tight_layout()
    return fig