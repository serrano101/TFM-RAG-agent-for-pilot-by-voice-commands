import os
import sys
import pandas as pd
from importlib.machinery import SourceFileLoader

IN_CSV = "scripts/batch/resultados.csv"
OUT_CSV = "scripts/batch/resultados_postprocess.csv"
POST_PROCESS_PY = "scripts/batch/post_process.py"

def load_answer_correct(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"No existe {path}")
    mod = SourceFileLoader("yesno_mod", path).load_module()
    ans = getattr(mod, "ANSWER_CORRECT", None)
    if not isinstance(ans, dict) or not ans:
        raise RuntimeError("ANSWER_CORRECT no encontrado o vacío en post_process.py")
    return ans

def find_id_column(df: pd.DataFrame) -> str:
    # Busca una columna 'id' (insensible a mayúsculas)
    for c in df.columns:
        if str(c).strip().lower() == "id":
            return c
    # Fallback: si no existe 'id', usar índice 1..N
    return None

def main():
    # Rutas absolutas por seguridad
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    in_csv = os.path.join(root, IN_CSV)
    out_csv = os.path.join(root, OUT_CSV)
    post_py = os.path.join(root, POST_PROCESS_PY)

    ans_map = load_answer_correct(post_py)

    if not os.path.exists(in_csv):
        raise FileNotFoundError(f"No existe {in_csv}")

    df = pd.read_csv(in_csv)

    # Detectar columna id
    id_col = find_id_column(df)

    # Preparar columna destino
    target_col = "¿Answer Correct?(Yes/No)"
    if target_col not in df.columns:
        # si no existe la creamos al final
        df[target_col] = ""

    # Aplicar mapeo
    if id_col:
        # Usar el valor de la columna id
        def map_yesno(v):
            try:
                k = int(v)
                val = ans_map.get(k)
                return val.lower() if isinstance(val, str) else ""
            except Exception:
                return ""
        df[target_col] = df[id_col].apply(map_yesno)
    else:
        # Sin columna id: usar el índice (1..N)
        def map_idx(idx):
            k = idx + 1
            val = ans_map.get(k)
            return val.lower() if isinstance(val, str) else ""
        df[target_col] = [map_idx(i) for i in range(len(df))]

    # Eliminar columna "RAG Error Menssage" si existe
    drop_col = "RAG Error Menssage"
    if drop_col in df.columns:
        df = df.drop(columns=[drop_col])

    # Guardar CSV
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    df.to_csv(out_csv, index=False, encoding="utf-8")
    print(f"[OK] CSV postprocesado: {out_csv}")

if __name__ == "__main__":
    main()