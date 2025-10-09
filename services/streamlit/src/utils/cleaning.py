import re
from typing import List, Union, Dict, Any

SECTION_KEYS = {
    "procedure": ("procedure", "procedimiento"),
    "conditions": ("conditions", "condiciones"),
    "steps": ("steps", "pasos"),
    "notes": ("notes", "notas"),
}

SECTION_PATTERN = re.compile(
    r"^\s*(procedure|procedimiento|conditions|condiciones|steps|pasos|notes|notas)\s*:\s*$",
    re.IGNORECASE
)

BULLET_PATTERN = re.compile(r"^\s*(?:[-*•]|>\s+)")
ENUM_PATTERN = re.compile(r"^\s*(\d+)[\).\:-]\s*")

def _norm_token(s: str) -> str:
    if not s:
        return ""
    # Eliminar énfasis Markdown y comillas envolventes
    s = s.replace("**", "").replace("__", "")
    s = s.strip().strip("'\"`").strip()
    # Colapsar espacios
    s = re.sub(r"\s+", " ", s)
    # Quitar restos de backticks/code
    s = s.strip("`")
    return s

def _split_raw(raw: Union[str, List[str]]) -> List[str]:
    if isinstance(raw, list):
        parts = raw
    else:
        # Separar primero por saltos de línea
        if "\n" in raw:
            parts = raw.splitlines()
        elif raw.count(",") >= 3:
            parts = raw.split(",")
        else:
            # Intentar separar por punto si parece lista
            parts = re.split(r"(?<=\.)\s+", raw)
    return [p for p in (part.strip() for part in parts) if p]

def _detect_section(line: str) -> str | None:
    low = line.lower().rstrip(":").strip()
    for key, aliases in SECTION_KEYS.items():
        if low in aliases:
            return key
    return None

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

def universal_clean(raw: Union[str, List[str]]) -> Dict[str, Any]:
    """
    Limpieza universal:
    - Extrae secciones si se detectan.
    - Heurísticas para pasos (líneas enumeradas) y bullets (conditions).
    - Siempre devuelve raw_clean (texto plano limpio).
    - 'structured' indica si se pudo interpretar la estructura.
    """
    parts = _split_raw(raw)
    norm_lines = [_norm_token(p) for p in parts if _norm_token(p)]
    if not norm_lines:
        return {
            "procedure": "",
            "conditions": [],
            "steps": [],
            "notes": [],
            "raw_clean": "",
            "structured": False
        }

    data = {
        "procedure": "",
        "conditions": [],
        "steps": [],
        "notes": []
    }

    current_section = None
    section_hits = set()

    # Primera pasada: detectar secciones explícitas
    for line in norm_lines:
        sec = _detect_section(line.rstrip(":"))
        if sec:
            current_section = sec
            section_hits.add(sec)
            continue

        # Si es enumeración tipo "1. Algo"
        enum_match = ENUM_PATTERN.match(line)
        bullet_match = BULLET_PATTERN.match(line)

        content = line
        # Quitar prefijos enumeración / bullet para guardar limpio
        if enum_match:
            content = line[enum_match.end():].strip()
        elif bullet_match:
            content = line[bullet_match.end():].strip()

        if current_section:
            if current_section == "procedure":
                # acumulativo en una sola línea
                if data["procedure"]:
                    data["procedure"] += " " + content
                else:
                    data["procedure"] = content
            elif current_section == "conditions":
                if content:
                    data["conditions"].append(content)
            elif current_section == "steps":
                if content:
                    data["steps"].append(content)
            elif current_section == "notes":
                if content:
                    data["notes"].append(content)
        else:
            # Sin sección activa: heurísticas
            if enum_match:
                data["steps"].append(content)
            elif bullet_match:
                data["conditions"].append(content)
            else:
                # Podría ser el título (procedure) si aún vacío y corto
                if not data["procedure"] and len(content.split()) <= 8:
                    data["procedure"] = content
                else:
                    # Fallback: si luego se marca estructurado esto se ignora,
                    # si no, se mantendrá en raw_clean solamente.
                    pass

    # Deduplicar
    data["conditions"] = _dedupe_order(data["conditions"])
    data["steps"] = _dedupe_order(data["steps"])
    data["notes"] = _dedupe_order(data["notes"])
    data["procedure"] = data["procedure"].strip()

    # Criterio de estructura mínima:
    structured = (
        bool(data["procedure"]) and
        (len(data["steps"]) >= 1 or len(data["conditions"]) >= 1 or len(data["notes"]) >= 1) and
        (len(section_hits) >= 1 or len(data["steps"]) >= 2)
    )

    # raw_clean siempre: unir líneas normalizadas (sin modificar)
    raw_clean = "\n".join(norm_lines)

    return {
        **data,
        "raw_clean": raw_clean,
        "structured": structured
    }

def clean_rag_answer(raw: Union[str, List[str]]) -> Dict[str, List[str] | str]:
    """
    Retrocompat, ahora incluye raw_clean para poder hacer fallback.
    """
    uc = universal_clean(raw)
    return {
        "procedure": uc["procedure"],
        "conditions": uc["conditions"],
        "steps": uc["steps"],
        "notes": uc["notes"],
        "raw_clean": uc["raw_clean"],
        "structured": uc["structured"],
    }

def format_clean_answer(clean: Dict[str, List[str] | str]) -> str:
    """
    Formatea la respuesta limpia en un string estructurado.
    Si no hay estructura mínima, se hace fallback a raw_clean.
    """
    # Si hay estructura mínima, formatea; si no, fallback a raw_clean
    has_structure = any([
        clean.get("procedure"),
        clean.get("conditions"),
        clean.get("steps"),
        clean.get("notes")
    ])
    if not has_structure and clean.get("raw_clean"):
        return str(clean["raw_clean"]).strip()

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

__all__ = [
    "universal_clean",
    "clean_rag_answer",
    "format_clean_answer"
]