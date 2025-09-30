import re
from typing import List, Union, Dict

SECTION_KEYS = {
    "procedure": ("procedure", "procedimiento"),
    "conditions": ("conditions", "condiciones"),
    "steps": ("steps", "pasos"),
    "notes": ("notes", "notas"),
}

def _norm_token(s: str) -> str:
    s = s.strip()
    s = s.strip("'\"`")
    s = s.replace("**", "")
    return s.strip()

def clean_rag_answer(raw: Union[str, List[str]]) -> Dict[str, List[str] | str]:
    """
    Devuelve dict normalizado con keys: procedure, conditions, steps, notes.
    Acepta una cadena (con saltos) o una lista de tokens.
    """
    if isinstance(raw, str):
        # Separar por saltos o comas si viene plano
        parts = re.split(r"(?:\n|,)", raw)
    else:
        parts = list(raw)

    tokens = [_norm_token(p) for p in parts if _norm_token(p)]
    current_section = None
    data = {
        "procedure": "",
        "conditions": [],
        "steps": [],
        "notes": []
    }

    def detect_section(t: str):
        low = t.lower().rstrip(":")
        for key, aliases in SECTION_KEYS.items():
            if low in aliases:
                return key
        return None

    for t in tokens:
        sec = detect_section(t)
        if sec:
            current_section = sec
            continue
        # Filtrar tokens basura como '1.' sin contenido
        if re.fullmatch(r"\d+\.", t):
            # Podría ser marcador suelto sin texto → ignorar
            continue
        if current_section is None:
            # Si aún no marcó sección, intentar detectar si es nombre del procedimiento
            if not data["procedure"]:
                data["procedure"] = t
            else:
                # Anexar a procedure si son varios tokens
                data["procedure"] += f" {t}"
            continue
        if current_section == "procedure":
            if not data["procedure"]:
                data["procedure"] = t
            else:
                data["procedure"] += f" {t}"
        elif current_section == "conditions":
            data["conditions"].append(re.sub(r"^\d+\.\s*", "", t))
        elif current_section == "steps":
            data["steps"].append(re.sub(r"^\d+\.\s*", "", t))
        elif current_section == "notes":
            data["notes"].append(re.sub(r"^\d+\.\s*", "", t))

    # Deduplicar y limpiar espacios
    data["conditions"] = _dedupe_order(data["conditions"])
    data["steps"] = _dedupe_order(data["steps"])
    data["notes"] = _dedupe_order(data["notes"])
    data["procedure"] = data["procedure"].strip()
    return data

def _dedupe_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for it in items:
        norm = it.strip()
        if not norm:
            continue
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out

def format_clean_answer(clean: Dict[str, List[str] | str]) -> str:
    lines = []
    if clean.get("procedure"):
        lines.append(f"Procedure: {clean['procedure']}")
    if clean.get("conditions"):
        lines.append("Conditions:")
        for c in clean["conditions"]:
            lines.append(f"- {c}")
    if clean.get("steps"):
        lines.append("Steps:")
        for i, s in enumerate(clean["steps"], 1):
            lines.append(f"{i}. {s}")
    if clean.get("notes"):
        lines.append("Notes:")
        for i, n in enumerate(clean["notes"], 1):
            lines.append(f"{i}. {n}")
    return "\n".join(lines)