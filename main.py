
from __future__ import annotations

import io
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st
from openpyxl.utils import get_column_letter

try:
    from pypdf import PdfReader
    from pypdf.errors import DependencyError
except Exception:
    PdfReader = None
    class DependencyError(Exception):
        pass


st.set_page_config(
    page_title="FEDNA Feed Recommender",
    page_icon="🐄",
    layout="wide",
    initial_sidebar_state="expanded",
)

SPECIES_OPTIONS = [
    "Rumiantes de carne",
    "Rumiantes de leche",
    "Reposición de rumiantes",
    "Avicultura",
    "Porcino",
]

MANUAL_FILE_HINTS = {
    "Rumiantes de carne": ["cebo", "rumiantes cebo"],
    "Rumiantes de leche": ["leche", "rumiantes leche"],
    "Reposición de rumiantes": ["recria", "recría", "recria de rumiantes", "reposicion"],
    "Avicultura": ["aves", "avicultura", "fedna aves", "pollos", "broiler"],
    "Porcino": ["porcino", "cerdas", "cerda", "ganado porcino"],
}

NUTRIENT_LABELS = {
    "PROT_BRU": "Proteína bruta (%)",
    "GRASA_BR": "Grasa bruta (%)",
    "FIBRA_BR": "Fibra bruta (%)",
    "FND": "FND (%)",
    "FAD": "FAD (%)",
    "LAD": "LAD (%)",
    "ALM_EWER": "Almidón (%)",
    "AZUCARES": "Azúcares (%)",
    "LACTOSA": "Lactosa (%)",
    "CA": "Calcio (%)",
    "P_": "Fósforo total (%)",
    "AVP_AV": "Fósforo disponible/digestible (%)",
    "NA": "Sodio (%)",
    "CL": "Cloro (%)",
    "K": "Potasio (%)",
    "MG": "Magnesio (%)",
    "CU": "Cobre (ppm o mg/kg)",
    "ZN": "Zinc (ppm o mg/kg)",
    "MN": "Manganeso (ppm o mg/kg)",
    "SE": "Selenio (ppm o mg/kg)",
    "LYS": "Lisina (%)",
    "MET": "Metionina (%)",
    "MET_CYS": "Met + Cys (%)",
    "THR": "Treonina (%)",
    "TRP": "Triptófano (%)",
    "ILE": "Isoleucina (%)",
    "VAL": "Valina (%)",
    "ARG": "Arginina (%)",
    "LEU": "Leucina (%)",
    "NE_SW": "Energía neta / EN",
    "ME_SW": "Energía metabolizable / EM",
    "EM": "EM",
    "EMA": "EMA",
    "EMAN": "EMAn",
    "UFC": "UFC",
    "UFL": "UFL",
    "PDI": "PDI",
    "PDIN": "PDIN",
    "PDIE": "PDIE",
    "CNF": "CNF (%)",
}

COLUMN_ROLE_ALIASES = {
    "feed_name": [
        "nombre pienso", "pienso", "feed", "producto", "product", "formula", "fórmula",
        "nombre formula", "specification", "feed_name", "nombre",
    ],
    "price": [
        "precio", "cost", "coste", "cost/tonne", "cost per tonne", "€/t", "eur/t",
        "price", "precio pienso", "price_per_tonne",
    ],
}

QUERY_NUTRIENT_SYNONYMS = {
    "proteina": "PROT_BRU", "proteína": "PROT_BRU", "pb": "PROT_BRU", "prot_bru": "PROT_BRU",
    "grasa": "GRASA_BR", "ee": "GRASA_BR", "extracto etereo": "GRASA_BR", "extracto etéreo": "GRASA_BR",
    "fibra": "FIBRA_BR", "fb": "FIBRA_BR", "fnd": "FND", "adf": "FAD", "fad": "FAD",
    "almidon": "ALM_EWER", "almidón": "ALM_EWER", "azucares": "AZUCARES", "azúcares": "AZUCARES",
    "lactosa": "LACTOSA", "calcio": "CA", "ca": "CA", "fosforo": "P_", "fósforo": "P_",
    "p total": "P_", "p digestible": "AVP_AV", "p disponible": "AVP_AV", "avp": "AVP_AV",
    "sodio": "NA", "na": "NA", "cloro": "CL", "cl": "CL", "potasio": "K", "k": "K",
    "magnesio": "MG", "mg": "MG", "lisina": "LYS", "lys": "LYS", "metionina": "MET",
    "met": "MET", "met+cys": "MET_CYS", "met_cys": "MET_CYS", "met cys": "MET_CYS",
    "treonina": "THR", "thr": "THR", "triptofano": "TRP", "triptófano": "TRP", "trp": "TRP",
    "isoleucina": "ILE", "ile": "ILE", "valina": "VAL", "val": "VAL", "arginina": "ARG",
    "arg": "ARG", "leucina": "LEU", "leu": "LEU", "energia neta": "NE_SW", "energía neta": "NE_SW",
    "en": "NE_SW", "energia metabolizable": "ME_SW", "energía metabolizable": "ME_SW", "em": "ME_SW",
    "ema": "EMA", "eman": "EMAN", "ufc": "UFC", "ufl": "UFL", "pdi": "PDI", "pdin": "PDIN",
    "pdie": "PDIE", "cnf": "CNF",
}

STOPWORDS = {
    "de", "la", "el", "los", "las", "para", "con", "sin", "por", "del", "al", "un", "una", "que",
    "y", "o", "en", "kg", "pienso", "quiero", "necesito", "mas", "más", "menos", "tipo", "animal",
    "produccion", "producción", "fase", "formula", "fórmula", "sobre", "segun", "según", "como", "entre", "hasta",
}

FEDNA_PROFILES: Dict[str, List[Dict[str, Any]]] = {
    "Porcino": [
        {
            "name": "Crecimiento-cebo 20-60 kg",
            "keywords": ["20-60", "20 60", "cebo", "crecimiento", "engorde"],
            "source_note": "Perfil derivado de las recomendaciones FEDNA para cerdos en crecimiento-cebo 20-60 kg.",
            "requirements": {
                "NE_SW": {"kind": "min", "value": 2400.0, "weight": 2.0},
                "ME_SW": {"kind": "min", "value": 3180.0, "weight": 1.5},
                "PROT_BRU": {"kind": "range", "min": 16.2, "max": 18.0, "weight": 1.8},
                "FIBRA_BR": {"kind": "range", "min": 3.4, "max": 5.4, "weight": 1.0},
                "FND": {"kind": "range", "min": 11.0, "max": 15.5, "weight": 1.2},
                "ALM_EWER": {"kind": "min", "value": 35.0, "weight": 1.0},
                "LYS": {"kind": "min", "value": 0.89, "weight": 2.0},
                "MET": {"kind": "min", "value": 0.28, "weight": 1.2},
                "MET_CYS": {"kind": "min", "value": 0.53, "weight": 1.2},
                "THR": {"kind": "min", "value": 0.58, "weight": 1.2},
                "TRP": {"kind": "min", "value": 0.17, "weight": 1.0},
                "CA": {"kind": "range", "min": 0.67, "max": 0.80, "weight": 1.0},
                "P_": {"kind": "min", "value": 0.55, "weight": 0.8},
                "AVP_AV": {"kind": "min", "value": 0.28, "weight": 1.0},
                "NA": {"kind": "min", "value": 0.18, "weight": 0.6},
                "CL": {"kind": "min", "value": 0.14, "weight": 0.6},
            },
        },
        {
            "name": "Cerdas reproductoras: gestación estándar",
            "keywords": ["gestacion", "gestación", "cerda", "reproductora", "madre"],
            "source_note": "Perfil orientativo basado en FEDNA para gestación estándar.",
            "requirements": {
                "NE_SW": {"kind": "min", "value": 2130.0, "weight": 1.6},
                "ME_SW": {"kind": "min", "value": 2875.0, "weight": 1.2},
                "PROT_BRU": {"kind": "range", "min": 13.7, "max": 15.8, "weight": 1.6},
                "FIBRA_BR": {"kind": "range", "min": 6.0, "max": 10.0, "weight": 1.1},
                "FND": {"kind": "min", "value": 18.0, "weight": 1.0},
                "LYS": {"kind": "min", "value": 0.51, "weight": 1.8},
                "THR": {"kind": "min", "value": 0.37, "weight": 1.0},
                "TRP": {"kind": "min", "value": 0.10, "weight": 0.8},
                "CA": {"kind": "range", "min": 0.81, "max": 1.05, "weight": 1.0},
                "AVP_AV": {"kind": "min", "value": 0.29, "weight": 1.0},
            },
        },
    ],
    "Avicultura": [
        {
            "name": "Pollos de carne - crecimiento",
            "keywords": ["broiler", "pollo", "carne", "crecimiento", "industrial"],
            "source_note": "Perfil orientativo FEDNA basado en pollos de carne de producción industrial (fase crecimiento).",
            "requirements": {
                "EMAN": {"kind": "min", "value": 3050.0, "weight": 2.0},
                "EMA": {"kind": "min", "value": 3050.0, "weight": 2.0},
                "PROT_BRU": {"kind": "min", "value": 20.0, "weight": 1.8},
                "FIBRA_BR": {"kind": "range", "min": 3.0, "max": 4.1, "weight": 1.0},
                "LYS": {"kind": "min", "value": 1.10, "weight": 2.0},
                "MET": {"kind": "min", "value": 0.45, "weight": 1.2},
                "MET_CYS": {"kind": "min", "value": 0.84, "weight": 1.3},
                "THR": {"kind": "min", "value": 0.73, "weight": 1.1},
                "TRP": {"kind": "min", "value": 0.20, "weight": 0.9},
                "ILE": {"kind": "min", "value": 0.75, "weight": 0.8},
                "VAL": {"kind": "min", "value": 0.87, "weight": 0.8},
                "CA": {"kind": "range", "min": 0.82, "max": 0.87, "weight": 1.0},
                "P_": {"kind": "min", "value": 0.49, "weight": 0.7},
                "AVP_AV": {"kind": "min", "value": 0.39, "weight": 1.0},
                "NA": {"kind": "range", "min": 0.16, "max": 0.20, "weight": 0.6},
                "CL": {"kind": "range", "min": 0.16, "max": 0.27, "weight": 0.5},
            },
        },
        {
            "name": "Pollos de carne - acabado",
            "keywords": ["acabado", "finisher", "final"],
            "source_note": "Perfil orientativo FEDNA basado en pollos de carne, fase acabado.",
            "requirements": {
                "EMAN": {"kind": "min", "value": 3120.0, "weight": 2.0},
                "EMA": {"kind": "min", "value": 3120.0, "weight": 2.0},
                "PROT_BRU": {"kind": "min", "value": 17.5, "weight": 1.6},
                "FIBRA_BR": {"kind": "range", "min": 3.05, "max": 4.4, "weight": 1.0},
                "LYS": {"kind": "min", "value": 0.92, "weight": 1.8},
                "MET": {"kind": "min", "value": 0.38, "weight": 1.1},
                "MET_CYS": {"kind": "min", "value": 0.70, "weight": 1.2},
                "THR": {"kind": "min", "value": 0.61, "weight": 1.0},
                "TRP": {"kind": "min", "value": 0.17, "weight": 0.8},
                "CA": {"kind": "range", "min": 0.70, "max": 0.75, "weight": 1.0},
                "AVP_AV": {"kind": "min", "value": 0.32, "weight": 0.9},
            },
        },
    ],
    "Rumiantes de carne": [
        {
            "name": "Terneros de cebo",
            "keywords": ["ternero", "cebo", "engorde", "carne", "vacuno"],
            "source_note": "Perfil orientativo FEDNA para concentrados de terneros de cebo.",
            "requirements": {
                "EM": {"kind": "range", "min": 2.66, "max": 2.95, "weight": 1.8},
                "UFC": {"kind": "range", "min": 0.92, "max": 1.05, "weight": 1.2},
                "PDI": {"kind": "range", "min": 103.0, "max": 123.0, "weight": 1.2},
                "PROT_BRU": {"kind": "range", "min": 14.0, "max": 17.0, "weight": 1.7},
                "FND": {"kind": "range", "min": 15.0, "max": 20.0, "weight": 1.4},
                "CNF": {"kind": "max", "value": 55.0, "weight": 1.0},
                "ALM_EWER": {"kind": "max", "value": 45.0, "weight": 1.0},
                "GRASA_BR": {"kind": "max", "value": 6.5, "weight": 0.9},
                "CA": {"kind": "range", "min": 0.50, "max": 0.80, "weight": 0.9},
                "P_": {"kind": "range", "min": 0.30, "max": 0.40, "weight": 0.9},
                "NA": {"kind": "range", "min": 0.20, "max": 0.30, "weight": 0.8},
                "MG": {"kind": "range", "min": 0.10, "max": 0.30, "weight": 0.6},
            },
        },
        {
            "name": "Corderos de cebo",
            "keywords": ["cordero", "ovino", "ligero", "precoz"],
            "source_note": "Perfil orientativo FEDNA para corderos de cebo.",
            "requirements": {
                "UFC": {"kind": "range", "min": 0.99, "max": 1.03, "weight": 1.3},
                "PROT_BRU": {"kind": "range", "min": 15.5, "max": 18.0, "weight": 1.6},
                "FND": {"kind": "range", "min": 15.0, "max": 20.0, "weight": 1.4},
                "CNF": {"kind": "max", "value": 55.0, "weight": 1.0},
                "ALM_EWER": {"kind": "max", "value": 45.0, "weight": 1.0},
                "GRASA_BR": {"kind": "max", "value": 6.5, "weight": 0.9},
                "CA": {"kind": "range", "min": 0.70, "max": 1.25, "weight": 0.9},
                "P_": {"kind": "min", "value": 0.35, "weight": 0.8},
                "NA": {"kind": "range", "min": 0.25, "max": 1.00, "weight": 0.4},
            },
        },
    ],
    "Rumiantes de leche": [
        {
            "name": "Lactación intensiva - perfil general",
            "keywords": ["lactacion", "lactación", "leche", "vaca", "cabra", "oveja"],
            "source_note": "Perfil general FEDNA para rumiantes de leche, pensado como referencia práctica y no como ración cerrada.",
            "requirements": {
                "PROT_BRU": {"kind": "range", "min": 14.0, "max": 16.5, "weight": 1.6},
                "FND": {"kind": "range", "min": 25.0, "max": 33.0, "weight": 1.5},
                "GRASA_BR": {"kind": "max", "value": 7.0, "weight": 0.8},
                "ALM_EWER": {"kind": "max", "value": 45.0, "weight": 0.9},
                "CA": {"kind": "range", "min": 0.60, "max": 2.80, "weight": 0.9},
                "P_": {"kind": "range", "min": 0.30, "max": 2.10, "weight": 0.8},
                "NA": {"kind": "range", "min": 0.16, "max": 0.40, "weight": 0.6},
                "UFL": {"kind": "range", "min": 0.89, "max": 1.01, "weight": 1.4},
                "UFC": {"kind": "range", "min": 0.89, "max": 1.01, "weight": 1.4},
            },
        },
        {
            "name": "Secado / preparto",
            "keywords": ["preparto", "secado", "seca", "transicion", "transición"],
            "source_note": "Perfil orientativo FEDNA para vacas secas y preparto.",
            "requirements": {
                "PROT_BRU": {"kind": "range", "min": 13.0, "max": 17.0, "weight": 1.5},
                "FND": {"kind": "range", "min": 25.0, "max": 45.0, "weight": 1.4},
                "FAD": {"kind": "range", "min": 20.0, "max": 35.0, "weight": 0.9},
                "CA": {"kind": "range", "min": 0.44, "max": 0.48, "weight": 1.0},
                "P_": {"kind": "range", "min": 0.22, "max": 0.26, "weight": 1.0},
                "NA": {"kind": "range", "min": 0.10, "max": 0.14, "weight": 0.7},
                "CL": {"kind": "range", "min": 0.13, "max": 0.20, "weight": 0.7},
            },
        },
    ],
    "Reposición de rumiantes": [
        {
            "name": "Recría - transición / crecimiento",
            "keywords": ["recria", "recría", "reposicion", "reposición", "ternera", "novilla", "destete"],
            "source_note": "Perfil orientativo FEDNA para recría de rumiantes basado en transición y crecimiento.",
            "requirements": {
                "EM": {"kind": "range", "min": 2.59, "max": 3.13, "weight": 1.8},
                "UFC": {"kind": "range", "min": 1.00, "max": 1.01, "weight": 1.2},
                "PROT_BRU": {"kind": "range", "min": 16.7, "max": 22.3, "weight": 1.7},
                "FND": {"kind": "range", "min": 14.9, "max": 30.0, "weight": 1.3},
                "GRASA_BR": {"kind": "max", "value": 4.0, "weight": 0.8},
                "ALM_EWER": {"kind": "range", "min": 30.0, "max": 40.5, "weight": 0.8},
                "CA": {"kind": "range", "min": 0.90, "max": 1.20, "weight": 0.8},
                "P_": {"kind": "range", "min": 0.50, "max": 0.70, "weight": 0.8},
                "NA": {"kind": "range", "min": 0.25, "max": 0.40, "weight": 0.6},
            },
        }
    ],
}

REPORT_SPEC_RE = re.compile(r"Specification:\s*(?P<code>\S+)\s+(?P<name>.+?)\s*:\s*Cost/tonne:\s*(?P<price>[0-9.,]+)", re.I)
REPORT_SP_RE = re.compile(r"\bSP:\s*(?P<code>\S+)\s+(?P<name>.+?)\s+100(?:[.,]0+)?\s*%,.*?Recost:\s*(?P<price>[0-9.,]+)", re.I)
NUMERIC_TOKEN_RE = re.compile(r"^[+\-]?(?:\d+(?:[.,]\d+)?|\.)$")


def normalize_ascii(text: Any) -> str:
    text = "" if text is None else str(text)
    replacements = str.maketrans({"á":"a","é":"e","í":"i","ó":"o","ú":"u","ü":"u","Á":"A","É":"E","Í":"I","Ó":"O","Ú":"U","Ü":"U","ñ":"n","Ñ":"N"})
    return text.translate(replacements)


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float, np.integer, np.floating)):
        if pd.isna(value):
            return None
        return float(value)
    text = str(value).strip()
    if text in {"", ".", "nan", "None", "-", "--"}:
        return None
    text = text.replace("%", "").replace("€", "").replace(",", ".")
    text = re.sub(r"[^0-9.\-+]", "", text)
    while text.endswith(".") and text not in {".", "-.", "+."}:
        text = text[:-1]
    if text in {"", ".", "-", "+"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def canonicalize_label(label: Any) -> str:
    text = normalize_ascii(label).strip().upper()
    text = text.replace("%", "")
    text = text.replace("(", " ").replace(")", " ")
    text = text.replace("+", "_").replace("-", "_").replace("/", "_").replace(".", "_")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Z0-9_]", "", text)
    alias_map = {
        "PROTEINA": "PROT_BRU", "PROTEINA_BRUTA": "PROT_BRU", "PB": "PROT_BRU", "PB_ANALIZA": "PROT_BRU",
        "CRUDE_PROTEIN": "PROT_BRU", "GRASA": "GRASA_BR", "GRASA_BRUTA": "GRASA_BR", "EE": "GRASA_BR",
        "EXTRACTO_ETEREO": "GRASA_BR", "GB": "GRASA_BR", "FIBRA": "FIBRA_BR", "FIBRA_BRUTA": "FIBRA_BR",
        "FB": "FIBRA_BR", "NDF": "FND", "ADF": "FAD", "ALMIDON": "ALM_EWER", "ALM_EWERS": "ALM_EWER",
        "STARCH": "ALM_EWER", "CALCIO": "CA", "CA_ANALIZA": "CA", "FOSFORO": "P_", "FOSFORO_TOTAL": "P_",
        "P_TOTAL": "P_", "P": "P_", "FOSFORO_DIG": "AVP_AV", "FOSFORO_DIGESTIBLE": "AVP_AV", "FOSFORO_DISP": "AVP_AV",
        "P_DIGESTIBLE": "AVP_AV", "P_DISPONIBLE": "AVP_AV", "AVP": "AVP_AV", "SODIO": "NA", "CLORO": "CL",
        "POTASIO": "K", "MAGNESIO": "MG", "COBRE": "CU", "ZINC": "ZN", "MANGANESO": "MN", "SELENIO": "SE",
        "LISINA": "LYS", "METIONINA": "MET", "MET_CIS": "MET_CYS", "MET_CISTINA": "MET_CYS",
        "METIONINA_CISTINA": "MET_CYS", "TREONINA": "THR", "TRIPTOFANO": "TRP", "ISOLEUCINA": "ILE",
        "VALINA": "VAL", "ARGININA": "ARG", "LEUCINA": "LEU", "ENERGIA_NETA": "NE_SW", "EN": "NE_SW",
        "ENERGIA_METABOLIZABLE": "ME_SW", "ME": "ME_SW", "EMA": "EMA", "EMAN": "EMAN", "UFC_KG": "UFC", "UFL_KG": "UFL",
    }
    return alias_map.get(text, text)


def nutrient_label(code: str) -> str:
    return NUTRIENT_LABELS.get(code, code.replace("_", " ").title())


def tokenize(text: Any) -> List[str]:
    text = normalize_ascii(text).lower()
    text = re.sub(r"[^a-z0-9%\.\- ]", " ", text)
    return [tok for tok in text.split() if len(tok) > 1 and tok not in STOPWORDS]


def find_first_matching_column(columns: Iterable[str], aliases: List[str]) -> Optional[str]:
    normalized_cols = {normalize_ascii(col).lower().strip(): col for col in columns}
    for alias in aliases:
        alias_norm = normalize_ascii(alias).lower().strip()
        for col_norm, original in normalized_cols.items():
            if alias_norm == col_norm or alias_norm in col_norm:
                return original
    return None


def detect_price_column(columns: Iterable[str]) -> Optional[str]:
    return find_first_matching_column(columns, COLUMN_ROLE_ALIASES["price"])


def detect_feed_name_column(columns: Iterable[str]) -> Optional[str]:
    return find_first_matching_column(columns, COLUMN_ROLE_ALIASES["feed_name"])


def make_multimix_feed_name(raw_name: str) -> str:
    raw_name = str(raw_name).strip()
    if "." in raw_name:
        prefix, suffix = raw_name.split(".", 1)
        if any(ch.isalpha() for ch in suffix):
            return suffix.strip()
    return raw_name


def token_is_numeric(token: Any) -> bool:
    return bool(NUMERIC_TOKEN_RE.match(str(token).strip()))


def rowwise_lines(raw_df: pd.DataFrame) -> List[str]:
    lines: List[str] = []
    for _, row in raw_df.fillna("").iterrows():
        parts = [str(cell).strip() for cell in row.tolist() if str(cell).strip() and str(cell).strip().lower() != "nan"]
        lines.append(" ".join(parts).strip())
    return lines


def is_report_workbook(lines: List[str]) -> bool:
    return any("Specification:" in line for line in lines) or any(re.search(r"\bSP:", line) for line in lines)


def parse_report_header(line: str) -> Optional[Dict[str, Any]]:
    text = " ".join(str(line).split())
    for regex, mode in [(REPORT_SPEC_RE, "multimix"), (REPORT_SP_RE, "singlemix")]:
        match = regex.search(text)
        if match:
            raw_name = match.group("name").strip()
            return {
                "mode": mode,
                "feed_code": match.group("code").strip(),
                "raw_name": raw_name,
                "feed_name": make_multimix_feed_name(raw_name),
                "price": safe_float(match.group("price")),
            }
    return None


def guess_ingredient_numeric_layout(values: List[Optional[float]]) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], int]:
    lead_len = len(values)
    pct = avg_cost = kilos = tonnes = None
    if lead_len >= 4 and values[0] is not None and values[1] is not None and values[0] > 100 and values[1] <= 100:
        avg_cost, pct, kilos, tonnes = values[0], values[1], values[2], values[3]
        return pct, avg_cost, kilos, tonnes, 4
    if lead_len >= 3 and values[0] is not None and values[1] is not None and values[2] is not None and values[0] <= 100 and values[1] > 100:
        pct, kilos, avg_cost = values[0], values[1], values[2]
        return pct, avg_cost, kilos, tonnes, 3
    if lead_len >= 3 and values[0] is not None and values[1] is not None and values[2] is not None:
        pct, kilos, avg_cost = values[0], values[1], values[2]
        return pct, avg_cost, kilos, tonnes, 3
    if lead_len >= 2:
        pct, kilos = values[0], values[1]
        return pct, avg_cost, kilos, tonnes, 2
    if lead_len >= 1:
        pct = values[0]
        return pct, avg_cost, kilos, tonnes, 1
    return pct, avg_cost, kilos, tonnes, 0


def parse_report_ingredient_line(line: str) -> Optional[Dict[str, Any]]:
    stripped = " ".join(str(line).split())
    if not stripped or stripped.startswith("-"):
        return None
    if any(key in stripped.upper() for key in ["INCLUDED RAW MATERIALS", "REJECTED RAW MATERIALS", "NUTRIENT ANALYSIS", "ANALYSIS"]):
        return None
    tokens = stripped.split()
    if len(tokens) < 4:
        return None
    if not re.match(r"^[A-Za-z0-9]+$", tokens[0]):
        return None

    first_data_idx = None
    for i in range(1, len(tokens)):
        if token_is_numeric(tokens[i]):
            first_data_idx = i
            break
    if first_data_idx is None or first_data_idx <= 1:
        return None

    raw_name = " ".join(tokens[1:first_data_idx]).strip()
    data_tokens = tokens[first_data_idx:]
    limit_pos = next((i for i, token in enumerate(data_tokens) if token.upper() in {"MIN", "MAX"}), None)
    leading_tokens = data_tokens[:limit_pos] if limit_pos is not None else data_tokens
    leading_values = [safe_float(token) for token in leading_tokens if token_is_numeric(token)]
    pct, avg_cost, kilos, tonnes, consumed = guess_ingredient_numeric_layout(leading_values)

    if pct is None:
        return None

    limit_flag = data_tokens[limit_pos].upper() if limit_pos is not None else ""
    if limit_pos is not None:
        minimum = safe_float(data_tokens[limit_pos + 1]) if len(data_tokens) > limit_pos + 1 else None
        maximum = safe_float(data_tokens[limit_pos + 2]) if len(data_tokens) > limit_pos + 2 else None
    else:
        minimum = safe_float(data_tokens[consumed]) if len(data_tokens) > consumed else None
        maximum = safe_float(data_tokens[consumed + 1]) if len(data_tokens) > consumed + 1 else None

    ingredient_name = raw_name.split(".", 1)[-1].strip() if "." in raw_name else raw_name
    return {
        "ingredient_code": tokens[0].strip(),
        "ingredient_raw": raw_name,
        "ingredient_name": ingredient_name,
        "avg_cost": avg_cost,
        "pct": pct,
        "kilos": kilos,
        "tonnes": tonnes,
        "limit_flag": limit_flag,
        "minimum": minimum,
        "maximum": maximum,
    }


def parse_report_analysis_line(line: str) -> Optional[Dict[str, Any]]:
    stripped = " ".join(str(line).split())
    if not stripped or stripped.startswith("-"):
        return None
    if any(key in stripped.upper() for key in ["NUTRIENT ANALYSIS", "RAW MATERIAL SENSITIVITY", "INCLUDED RAW MATERIALS", "REJECTED RAW MATERIALS"]):
        return None

    tokens = stripped.split()
    if len(tokens) < 2:
        return None

    name_tokens: List[str] = []
    i = 0
    if tokens[0] == "[":
        while i < len(tokens):
            name_tokens.append(tokens[i])
            if tokens[i] == "]":
                i += 1
                break
            i += 1
    else:
        name_tokens.append(tokens[0])
        i = 1
        units = {"%", "KCAL/KG", "MJ/KG", "G/KG", "MG/KG", "IU/KG", "PPM", "MJ", "KCAL"}
        if i < len(tokens) and not token_is_numeric(tokens[i]) and tokens[i].upper() not in units and tokens[i].upper() not in {"MIN", "MAX"}:
            name_tokens.append(tokens[i])
            i += 1

    if i < len(tokens) and tokens[i].upper() in {"%", "KCAL/KG", "MJ/KG", "G/KG", "MG/KG", "IU/KG", "PPM", "MJ", "KCAL"}:
        i += 1

    while i < len(tokens) and not token_is_numeric(tokens[i]):
        i += 1
    if i >= len(tokens):
        return None

    level = safe_float(tokens[i])
    if level is None:
        return None
    i += 1

    flag = ""
    if i < len(tokens) and tokens[i].upper() in {"MIN", "MAX"}:
        flag = tokens[i].upper()
        i += 1

    minimum = safe_float(tokens[i]) if i < len(tokens) else None
    maximum = safe_float(tokens[i + 1]) if i + 1 < len(tokens) else None

    if minimum is not None and minimum >= 99999:
        minimum = None
    if maximum is not None and maximum >= 99999:
        maximum = None

    nutrient = canonicalize_label(" ".join(name_tokens).strip("[] "))
    if not nutrient:
        return None

    return {
        "nutrient": nutrient,
        "level": level,
        "minimum": minimum,
        "maximum": maximum,
        "flag": flag,
    }


@st.cache_data(show_spinner=False)
def extract_pdf_pages(file_name: str, file_bytes: bytes) -> Dict[str, Any]:
    result: Dict[str, Any] = {"pages": [], "status": "empty", "error": None}
    if not file_bytes:
        result["error"] = "El archivo PDF está vacío o no se pudo leer."
        return result
    if PdfReader is None:
        result["status"] = "error"
        result["error"] = "La librería pypdf no está disponible en este entorno."
        return result

    try:
        reader = PdfReader(io.BytesIO(file_bytes), strict=False)
        if getattr(reader, "is_encrypted", False):
            try:
                reader.decrypt("")
            except Exception:
                pass
    except DependencyError:
        result["status"] = "error"
        result["error"] = (
            "El PDF parece estar protegido/cifrado y el entorno no tiene soporte criptográfico para leerlo. "
            "La app seguirá funcionando con los perfiles FEDNA integrados."
        )
        return result
    except Exception as exc:
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    pages: List[Dict[str, Any]] = []
    for idx, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        page_text = re.sub(r"\s+", " ", page_text).strip()
        if page_text:
            pages.append({"file_name": file_name, "page": idx, "text": page_text})

    if pages:
        result["pages"] = pages
        result["status"] = "ok"
    else:
        result["error"] = "No se pudo extraer texto útil del PDF."
    return result


@st.cache_data(show_spinner=False)
def parse_excel_bytes(file_bytes: bytes, file_name: str) -> Dict[str, Any]:
    warnings: List[str] = []
    excel = pd.ExcelFile(io.BytesIO(file_bytes))
    first_sheet = excel.sheet_names[0]
    raw_first = pd.read_excel(io.BytesIO(file_bytes), sheet_name=first_sheet, header=None, dtype=str)
    raw_lines = rowwise_lines(raw_first)

    if is_report_workbook(raw_lines):
        feeds_df, details, report_warnings = parse_report_workbook(raw_lines)
        warnings.extend(report_warnings)
        source_format = "report_specification_sp"
    else:
        feeds_df, details, source_format, parser_warnings = parse_tabular_workbook(file_bytes)
        warnings.extend(parser_warnings)

    if feeds_df.empty:
        raise ValueError("No se pudieron extraer piensos válidos del Excel cargado.")

    numeric_cols = [
        col for col in feeds_df.columns
        if col not in {"feed_name", "feed_code", "price", "source_sheet"} and pd.api.types.is_numeric_dtype(feeds_df[col])
    ]

    if "feed_name" not in feeds_df.columns:
        raise ValueError("No se ha podido identificar el nombre del pienso.")

    if "price" not in feeds_df.columns:
        warnings.append("No se identificó una columna de precio; el ranking no podrá desempatar por coste.")
        feeds_df["price"] = np.nan

    nutrient_display_map = {col: nutrient_label(col) for col in numeric_cols}
    return {
        "feeds_df": feeds_df,
        "details": details,
        "source_format": source_format,
        "warnings": warnings,
        "numeric_nutrients": numeric_cols,
        "nutrient_display_map": nutrient_display_map,
        "sheet_names": excel.sheet_names,
    }


def parse_report_workbook(lines: List[str]) -> Tuple[pd.DataFrame, Dict[str, Any], List[str]]:
    starts = [i for i, line in enumerate(lines) if parse_report_header(line)]
    if not starts:
        raise ValueError("Se detectó un reporte de texto, pero no se localizaron bloques 'Specification:' ni 'SP:'.")

    warnings: List[str] = []
    records: List[Dict[str, Any]] = []
    details: Dict[str, Any] = {}

    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        block = lines[start:end]
        header = parse_report_header(block[0])
        if not header:
            continue

        record: Dict[str, Any] = {
            "feed_code": header["feed_code"],
            "feed_name": header["feed_name"],
            "price": header["price"],
        }
        feed_details: Dict[str, Any] = {
            "raw_specification": header["raw_name"],
            "ingredients": [],
            "ingredient_limits": {},
            "nutrient_limits": {},
        }

        section = None
        for raw_line in block[1:]:
            line = " ".join(str(raw_line).split())
            upper = normalize_ascii(line).upper()
            if not line:
                continue
            if "INCLUDED RAW MATERIALS" in upper:
                section = "ingredients"
                continue
            if "REJECTED RAW MATERIALS" in upper:
                section = "rejected"
                continue
            if upper.startswith("ANALYSIS") or "NUTRIENT ANALYSIS" in upper:
                section = "analysis"
                continue
            if "RAW MATERIAL SENSITIVITY" in upper:
                section = None
                continue
            if line.startswith("-"):
                continue

            if section == "ingredients":
                parsed = parse_report_ingredient_line(line)
                if parsed:
                    feed_details["ingredients"].append(parsed)
                    feed_details["ingredient_limits"][parsed["ingredient_name"]] = {
                        "min": parsed["minimum"],
                        "max": parsed["maximum"],
                        "flag": parsed["limit_flag"],
                    }
            elif section == "analysis":
                parsed = parse_report_analysis_line(line)
                if parsed:
                    record[parsed["nutrient"]] = parsed["level"]
                    feed_details["nutrient_limits"][parsed["nutrient"]] = {
                        "min": parsed["minimum"],
                        "max": parsed["maximum"],
                        "flag": parsed["flag"],
                    }

        if len(feed_details["ingredients"]) == 0:
            warnings.append(f"El pienso '{header['feed_name']}' se leyó sin ingredientes explícitos.")
        records.append(record)
        details[header["feed_name"]] = feed_details

    feeds_df = pd.DataFrame(records)
    numeric_cols = [col for col in feeds_df.columns if col not in {"feed_code", "feed_name"}]
    for col in numeric_cols:
        feeds_df[col] = pd.to_numeric(feeds_df[col], errors="coerce")
    feeds_df = feeds_df.sort_values(["feed_name"]).reset_index(drop=True)
    return feeds_df, details, warnings


def parse_tabular_workbook(file_bytes: bytes) -> Tuple[pd.DataFrame, Dict[str, Any], str, List[str]]:
    warnings: List[str] = []
    excel = pd.ExcelFile(io.BytesIO(file_bytes))
    best_df: Optional[pd.DataFrame] = None
    best_sheet = excel.sheet_names[0]
    best_score = -1.0
    best_header_row = 0

    for sheet in excel.sheet_names:
        preview = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet, header=None, nrows=8)
        for header_row in range(min(5, len(preview))):
            try:
                df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet, header=header_row)
            except Exception:
                continue
            cols = [str(c) for c in df.columns]
            score = 0.0
            if detect_feed_name_column(cols):
                score += 3
            if detect_price_column(cols):
                score += 2
            numeric_ratio = float(df.select_dtypes(include=[np.number]).shape[1]) / max(len(df.columns), 1)
            score += numeric_ratio
            if score > best_score:
                best_score = score
                best_df = df.copy()
                best_sheet = sheet
                best_header_row = header_row

    if best_df is None:
        raise ValueError("No se pudo leer ninguna hoja útil del Excel.")

    df = best_df.dropna(axis=1, how="all").dropna(axis=0, how="all").copy()
    df.columns = [str(c).strip() for c in df.columns]

    feed_col = detect_feed_name_column(df.columns)
    price_col = detect_price_column(df.columns)

    if feed_col is None:
        raise ValueError(
            "No se pudo identificar la columna de nombre de pienso en formato tabular. "
            "Usa un encabezado como 'Pienso', 'Nombre pienso', 'Formula' o 'Feed'."
        )

    records: List[Dict[str, Any]] = []
    details: Dict[str, Any] = {}

    ingredient_cols = [
        col for col in df.columns
        if normalize_ascii(col).lower().startswith(("ing_", "ingrediente_", "ingredient_"))
        or normalize_ascii(col).lower().startswith("% ")
        or normalize_ascii(col).lower().startswith("pct_")
    ]
    limit_cols = [
        col for col in df.columns
        if re.search(r"(^min_|_min$|^max_|_max$|limite|minimo|maximo)", normalize_ascii(col).lower())
    ]

    for _, row in df.iterrows():
        feed_name = str(row.get(feed_col, "")).strip()
        if not feed_name or feed_name.lower() == "nan":
            continue
        record: Dict[str, Any] = {
            "feed_name": feed_name,
            "price": safe_float(row.get(price_col)) if price_col else None,
            "source_sheet": best_sheet,
        }
        ingredients: List[Dict[str, Any]] = []
        nutrient_limits: Dict[str, Any] = {}

        for col in df.columns:
            if col in {feed_col, price_col}:
                continue
            value = row.get(col)
            canonical = canonicalize_label(col)
            if col in ingredient_cols:
                pct = safe_float(value)
                if pct is not None and pct != 0:
                    display_name = str(col).split("_", 1)[-1].replace("%", "").strip()
                    ingredients.append(
                        {
                            "ingredient_code": "",
                            "ingredient_raw": display_name,
                            "ingredient_name": display_name,
                            "avg_cost": None,
                            "pct": pct,
                            "kilos": None,
                            "tonnes": None,
                            "limit_flag": "",
                            "minimum": None,
                            "maximum": None,
                        }
                    )
                continue
            if col in limit_cols:
                continue
            numeric_value = safe_float(value)
            if numeric_value is not None:
                record[canonical] = numeric_value

        for col in df.columns:
            col_norm = normalize_ascii(col).lower().strip()
            if col in {feed_col, price_col} or col not in limit_cols:
                continue
            if col_norm.startswith("min_"):
                base = canonicalize_label(col[4:])
                nutrient_limits.setdefault(base, {})["min"] = safe_float(row.get(col))
            elif col_norm.startswith("max_"):
                base = canonicalize_label(col[4:])
                nutrient_limits.setdefault(base, {})["max"] = safe_float(row.get(col))
            elif col_norm.endswith("_min"):
                base = canonicalize_label(col[:-4])
                nutrient_limits.setdefault(base, {})["min"] = safe_float(row.get(col))
            elif col_norm.endswith("_max"):
                base = canonicalize_label(col[:-4])
                nutrient_limits.setdefault(base, {})["max"] = safe_float(row.get(col))

        details[feed_name] = {
            "raw_specification": feed_name,
            "ingredients": ingredients,
            "ingredient_limits": {},
            "nutrient_limits": nutrient_limits,
        }
        records.append(record)

    feeds_df = pd.DataFrame(records)
    numeric_cols = [col for col in feeds_df.columns if col not in {"feed_name", "source_sheet"}]
    for col in numeric_cols:
        feeds_df[col] = pd.to_numeric(feeds_df[col], errors="coerce")

    warnings.append(f"Formato tabular detectado en la hoja '{best_sheet}' (fila de encabezado estimada: {best_header_row + 1}).")
    return feeds_df, details, "tabular", warnings


def choose_fedna_profile(species: str, query: str) -> Dict[str, Any]:
    profiles = FEDNA_PROFILES.get(species, [])
    if not profiles:
        return {"name": "Perfil vacío", "requirements": {}, "source_note": ""}
    query_norm = normalize_ascii(query).lower()
    best_profile = profiles[0]
    best_hits = -1
    for profile in profiles:
        hits = sum(1 for kw in profile.get("keywords", []) if normalize_ascii(kw).lower() in query_norm)
        if hits > best_hits:
            best_hits = hits
            best_profile = profile
    return best_profile


def infer_species_from_manual_name(file_name: str) -> Optional[str]:
    lowered = normalize_ascii(file_name).lower()
    for species, hints in MANUAL_FILE_HINTS.items():
        if any(hint in lowered for hint in hints):
            return species
    return None


def build_manual_entries(uploaded_manuals: List[Any]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    seen_names = set()
    local_dir = Path("fedna_manuals")
    if local_dir.exists():
        for path in sorted(local_dir.glob("*.pdf")):
            try:
                file_bytes = path.read_bytes()
            except Exception:
                continue
            seen_names.add(path.name)
            entries.append({"file_name": path.name, "file_bytes": file_bytes, "origin": "local"})
    for uploaded in uploaded_manuals:
        if uploaded is None or uploaded.name in seen_names:
            continue
        try:
            file_bytes = uploaded.getvalue()
        except Exception:
            continue
        entries.append({"file_name": uploaded.name, "file_bytes": file_bytes, "origin": "uploaded"})
        seen_names.add(uploaded.name)

    enriched_entries = []
    for entry in entries:
        assigned_species = infer_species_from_manual_name(entry["file_name"])
        extraction = extract_pdf_pages(entry["file_name"], entry["file_bytes"])
        enriched_entries.append({**entry, "species": assigned_species, "pages": extraction.get("pages", []), "load_status": extraction.get("status", "empty"), "load_error": extraction.get("error")})
    return enriched_entries


def retrieve_fedna_snippets(manual_entries: List[Dict[str, Any]], species: str, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    relevant_manuals = [m for m in manual_entries if m.get("species") == species and m.get("load_status") == "ok"]
    if not relevant_manuals:
        return []
    query_tokens = set(tokenize(query)) or set(tokenize(species))
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for manual in relevant_manuals:
        for page in manual["pages"]:
            page_tokens = set(tokenize(page["text"]))
            overlap = query_tokens & page_tokens
            if not overlap:
                continue
            score = float(len(overlap))
            if any(term in normalize_ascii(page["text"]).lower() for term in ["tabla", "recomendaciones", "nutricional", "fedna"]):
                score += 1.0
            scored.append((score, {"file_name": manual["file_name"], "page": page["page"], "text": page["text"]}))
    scored.sort(key=lambda item: item[0], reverse=True)
    top_pages: List[Dict[str, Any]] = []
    seen = set()
    for _, page in scored:
        key = (page["file_name"], page["page"])
        if key in seen:
            continue
        seen.add(key)
        top_pages.append(page)
        if len(top_pages) >= top_k:
            break
    return top_pages


def parse_query_constraints(query: str, available_nutrients: List[str]) -> Dict[str, Any]:
    query_norm = normalize_ascii(query).lower()
    nutrient_constraints: Dict[str, Dict[str, Any]] = {}
    nutrient_preferences: Dict[str, Dict[str, Any]] = {}

    synonym_pairs = sorted(QUERY_NUTRIENT_SYNONYMS.items(), key=lambda item: len(item[0]), reverse=True)
    prioritization_words = ["prioriza", "priorizando", "priorizar", "maximiza", "maximizar"]

    for raw_synonym, nutrient_code in synonym_pairs:
        synonym = normalize_ascii(raw_synonym).lower()
        synonym_present = re.search(rf"(?<![a-z0-9]){re.escape(synonym)}(?![a-z0-9])", query_norm)
        if not synonym_present:
            continue

        range_pattern = re.compile(rf"{re.escape(synonym)}\s*(?:entre|between)\s*([0-9.,]+)\s*(?:y|and|a|to|-)\s*([0-9.,]+)", re.I)
        comp_pattern = re.compile(rf"{re.escape(synonym)}\s*(>=|<=|>|<|=)\s*([0-9.,]+)", re.I)
        min_pattern = re.compile(rf"(?:minimo|minimo de|mínimo de|al menos|almenos|como minimo|como mínimo)\s*{re.escape(synonym)}\s*([0-9.,]+)", re.I)
        max_pattern = re.compile(rf"(?:maximo|maximo de|máximo de|como maximo|como máximo|no mas de|no más de|menos de)\s*{re.escape(synonym)}\s*([0-9.,]+)", re.I)

        matched = False
        range_match = range_pattern.search(query_norm)
        if range_match:
            low = safe_float(range_match.group(1))
            high = safe_float(range_match.group(2))
            if low is not None and high is not None:
                nutrient_constraints[nutrient_code] = {"kind": "range", "min": min(low, high), "max": max(low, high), "weight": 2.6}
                matched = True
        if matched:
            continue

        comp_match = comp_pattern.search(query_norm)
        if comp_match:
            sign = comp_match.group(1)
            value = safe_float(comp_match.group(2))
            if value is not None:
                if sign in {">", ">="}:
                    nutrient_constraints[nutrient_code] = {"kind": "min", "value": value, "weight": 2.6}
                elif sign in {"<", "<="}:
                    nutrient_constraints[nutrient_code] = {"kind": "max", "value": value, "weight": 2.6}
                else:
                    nutrient_constraints[nutrient_code] = {"kind": "target", "value": value, "tol": max(abs(value) * 0.08, 0.1), "weight": 2.6}
                matched = True
        if matched:
            continue

        min_match = min_pattern.search(query_norm)
        if min_match:
            value = safe_float(min_match.group(1))
            if value is not None:
                nutrient_constraints[nutrient_code] = {"kind": "min", "value": value, "weight": 2.6}
                matched = True
        if matched:
            continue

        max_match = max_pattern.search(query_norm)
        if max_match:
            value = safe_float(max_match.group(1))
            if value is not None:
                nutrient_constraints[nutrient_code] = {"kind": "max", "value": value, "weight": 2.6}
                matched = True
        if matched:
            continue

        higher_pref_patterns = [
            rf"(?:alto en|alta en|rico en|rica en|ricos en|ricas en|mas|más|mayor)\s+{re.escape(synonym)}",
            rf"{re.escape(synonym)}\s+(?:alto|alta|elevado|elevada|mayor)",
            rf"(?:{'|'.join(prioritization_words)})[^.\n]*{re.escape(synonym)}",
        ]
        lower_pref_patterns = [
            rf"(?:bajo en|baja en|menos|menor|minimiza|minimizar|reducir|reducido en)\s+{re.escape(synonym)}",
            rf"{re.escape(synonym)}\s+(?:bajo|baja|reducido|reducida|menor)",
        ]
        if any(re.search(pattern, query_norm, re.I) for pattern in higher_pref_patterns):
            nutrient_preferences[nutrient_code] = {"kind": "preference_max", "weight": 1.5}
            continue
        if any(re.search(pattern, query_norm, re.I) for pattern in lower_pref_patterns):
            nutrient_preferences[nutrient_code] = {"kind": "preference_min", "weight": 1.5}

    for nutrient_code in available_nutrients:
        code_norm = normalize_ascii(nutrient_code).lower()
        comp_match = re.search(rf"(?<![a-z0-9]){re.escape(code_norm)}(?![a-z0-9])\s*(>=|<=|>|<|=)\s*([0-9.,]+)", query_norm)
        if comp_match:
            sign = comp_match.group(1)
            value = safe_float(comp_match.group(2))
            if value is not None:
                if sign in {">", ">="}:
                    nutrient_constraints[nutrient_code] = {"kind": "min", "value": value, "weight": 2.6}
                elif sign in {"<", "<="}:
                    nutrient_constraints[nutrient_code] = {"kind": "max", "value": value, "weight": 2.6}
                else:
                    nutrient_constraints[nutrient_code] = {"kind": "target", "value": value, "tol": max(abs(value) * 0.08, 0.1), "weight": 2.6}

    price_max = None
    price_match = re.search(r"(?:precio|coste|costo|cost|eur|€)\s*(?:maximo|maximo de|máximo de|<|<=|hasta|tope)?\s*([0-9.,]+)", query_norm)
    if price_match:
        price_max = safe_float(price_match.group(1))

    prefer_low_price = any(keyword in query_norm for keyword in ["barato", "economico", "económico", "menor precio", "mas barato", "más barato", "precio bajo"])

    if "energia alta" in query_norm or "energia elevada" in query_norm:
        for energy_code in ["NE_SW", "ME_SW", "EMAN", "EMA", "EM", "UFL", "UFC"]:
            if energy_code in available_nutrients and energy_code not in nutrient_constraints and energy_code not in nutrient_preferences:
                nutrient_preferences[energy_code] = {"kind": "preference_max", "weight": 1.5}
                break
    if "energia baja" in query_norm:
        for energy_code in ["NE_SW", "ME_SW", "EMAN", "EMA", "EM", "UFL", "UFC"]:
            if energy_code in available_nutrients and energy_code not in nutrient_constraints and energy_code not in nutrient_preferences:
                nutrient_preferences[energy_code] = {"kind": "preference_min", "weight": 1.5}
                break

    include_ingredients = extract_ingredient_terms(query_norm, mode="include")
    exclude_ingredients = extract_ingredient_terms(query_norm, mode="exclude")
    name_terms = extract_name_terms_from_query(query_norm, available_nutrients)

    return {
        "nutrient_constraints": nutrient_constraints,
        "nutrient_preferences": nutrient_preferences,
        "price_max": price_max,
        "prefer_low_price": prefer_low_price,
        "include_ingredients": include_ingredients,
        "exclude_ingredients": exclude_ingredients,
        "ingredient_limit_filters": [],
        "name_terms": name_terms,
    }


def extract_ingredient_terms(query_norm: str, mode: str = "include") -> List[str]:
    patterns = [r"con\s+([a-z0-9_\- ]+)", r"incluir\s+([a-z0-9_\- ]+)", r"rico en\s+([a-z0-9_\- ]+)"] if mode == "include" else [r"sin\s+([a-z0-9_\- ]+)", r"evitar\s+([a-z0-9_\- ]+)", r"excluir\s+([a-z0-9_\- ]+)"]
    nutrient_term_tokens = set()
    for synonym in QUERY_NUTRIENT_SYNONYMS:
        nutrient_term_tokens.update(tokenize(synonym))
    blocked_tokens = nutrient_term_tokens | {"alto", "alta", "altos", "altas", "bajo", "baja", "bajos", "bajas", "precio", "barato", "economico", "económico", "energia", "energía"}

    terms: List[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, query_norm):
            fragment = match.group(1).strip()
            fragment = re.split(r"[,.;]|\s+que\s+|\s+para\s+|\s+y\s+|\s+o\s+", fragment)[0].strip()
            fragment_tokens = tokenize(fragment)
            if len(fragment) < 3 or not fragment_tokens or all(tok in blocked_tokens for tok in fragment_tokens):
                continue
            terms.append(fragment)
    return list(dict.fromkeys(terms))


def extract_name_terms_from_query(query_norm: str, available_nutrients: List[str]) -> List[str]:
    nutrient_tokens = set()
    for synonym in QUERY_NUTRIENT_SYNONYMS:
        nutrient_tokens.update(tokenize(synonym))
    available_tokens = set()
    for nutrient in available_nutrients:
        available_tokens.update(tokenize(nutrient))
        available_tokens.update(tokenize(nutrient_label(nutrient)))

    generic_tokens = set(STOPWORDS) | nutrient_tokens | available_tokens | {
        "fedna", "top", "mejor", "mejores", "busca", "buscar", "dame", "quiero", "necesito", "recomienda",
        "recomendacion", "recomendación", "explica", "comparar", "compara", "prioriza", "priorizando", "priorizar",
        "cumple", "cumplan", "cumpla", "requisito", "requisitos", "nivel", "niveles", "mayor", "menor", "alto", "alta",
        "bajo", "baja", "economico", "económico", "barato", "cara", "caro", "precio", "coste", "costo", "excel", "chat",
        "selector", "rumiantes", "porcino", "avicultura", "aves", "carne", "leche", "recria", "recría", "gestacion",
        "gestación", "produccion", "producción", "objetivo", "objetivos", "usar", "utiliza", "utilizar", "solo",
        "solamente", "piensos", "formula", "formulas", "filtra", "filtrar", "posible", "posibles",
    }
    extracted: List[str] = []
    for tok in tokenize(query_norm):
        tok = tok.strip(".-_ ")
        if not tok or tok in generic_tokens or re.fullmatch(r"[0-9.]+", tok):
            continue
        extracted.append(tok)
    return list(dict.fromkeys(extracted))


def default_preference_kind(nutrient: str) -> str:
    return "preference_min" if nutrient in {"FIBRA_BR", "FAD", "LAD", "NA", "CL"} else "preference_max"


def value_satisfies_rule(value: Any, rule: Dict[str, Any]) -> bool:
    numeric_value = safe_float(value)
    if numeric_value is None:
        return False
    kind = rule.get("kind")
    if kind == "min":
        return numeric_value >= float(rule["value"])
    if kind == "max":
        return numeric_value <= float(rule["value"])
    if kind == "target":
        tol = max(float(rule.get("tol", abs(float(rule["value"])) * 0.08)), 1e-6)
        return abs(numeric_value - float(rule["value"])) <= tol
    if kind == "range":
        return float(rule["min"]) <= numeric_value <= float(rule["max"])
    return True


def feed_search_blob(details: Dict[str, Any], feed_name: str) -> str:
    ingredients = details.get(feed_name, {}).get("ingredients", [])
    ingredient_names = " ".join(str(item.get("ingredient_name", "")) for item in ingredients)
    return normalize_ascii(f"{feed_name} {ingredient_names}").lower()


def text_match_ratio(text_blob: str, name_terms: List[str]) -> float:
    if not name_terms:
        return 0.0
    hits = sum(1 for term in name_terms if term in text_blob)
    return hits / max(len(name_terms), 1)


def merge_requirements(profile: Dict[str, Any], query_constraints: Dict[str, Any], selected_nutrients: List[str], available_nutrients: List[str]) -> Dict[str, Dict[str, Any]]:
    available_set = set(available_nutrients)
    merged: Dict[str, Dict[str, Any]] = {}

    for nutrient, rule in query_constraints.get("nutrient_constraints", {}).items():
        if nutrient in available_set:
            merged[nutrient] = rule.copy()
    for nutrient, rule in query_constraints.get("nutrient_preferences", {}).items():
        if nutrient in available_set and nutrient not in merged:
            merged[nutrient] = rule.copy()

    if not merged:
        for nutrient in selected_nutrients:
            if nutrient in available_set:
                merged[nutrient] = {"kind": default_preference_kind(nutrient), "weight": 1.0, "fallback": True}
    return merged


def ingredient_set_for_feed(details: Dict[str, Any], feed_name: str) -> List[str]:
    ingredients = details.get(feed_name, {}).get("ingredients", [])
    return [normalize_ascii(item.get("ingredient_name", "")).lower() for item in ingredients]


def describe_rule(rule: Dict[str, Any]) -> str:
    kind = rule.get("kind")
    if kind == "min":
        return f"≥ {rule['value']:.3f}"
    if kind == "max":
        return f"≤ {rule['value']:.3f}"
    if kind == "target":
        return f"≈ {rule['value']:.3f}"
    if kind == "range":
        return f"{rule['min']:.3f} – {rule['max']:.3f}"
    if kind == "preference_max":
        return "priorizar valor alto"
    if kind == "preference_min":
        return "priorizar valor bajo"
    return "n/d"


def apply_query_filters(feeds_df: pd.DataFrame, details: Dict[str, Any], query_constraints: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
    filtered = feeds_df.copy()
    notes: List[str] = []

    for nutrient, rule in query_constraints.get("nutrient_constraints", {}).items():
        if nutrient not in filtered.columns:
            notes.append(f"El nutriente {nutrient_label(nutrient)} se pidió en la consulta, pero no está disponible en el Excel.")
            continue
        previous = len(filtered)
        mask = filtered[nutrient].apply(lambda value: value_satisfies_rule(value, rule))
        filtered = filtered[mask]
        notes.append(f"Filtro por {nutrient_label(nutrient)} aplicado ({describe_rule(rule)}). Se mantienen {len(filtered)} de {previous} piensos.")

    price_max = query_constraints.get("price_max")
    if price_max is not None and "price" in filtered.columns:
        previous = len(filtered)
        filtered = filtered[filtered["price"].fillna(np.inf) <= price_max]
        notes.append(f"Filtro por precio aplicado: ≤ {price_max:.3f}. Se mantienen {len(filtered)} de {previous} piensos.")

    include_terms = query_constraints.get("include_ingredients", [])
    for term in include_terms:
        previous = len(filtered)
        mask = filtered["feed_name"].apply(lambda name: any(term in ing for ing in ingredient_set_for_feed(details, name)))
        filtered = filtered[mask]
        notes.append(f"Filtro de ingredientes incluidos aplicado: '{term}'. Se mantienen {len(filtered)} de {previous} piensos.")

    exclude_terms = query_constraints.get("exclude_ingredients", [])
    for term in exclude_terms:
        previous = len(filtered)
        mask = filtered["feed_name"].apply(lambda name: not any(term in ing for ing in ingredient_set_for_feed(details, name)))
        filtered = filtered[mask]
        notes.append(f"Filtro de exclusión aplicado: sin '{term}'. Se mantienen {len(filtered)} de {previous} piensos.")

    name_terms = query_constraints.get("name_terms", [])
    if name_terms:
        original_scores = feeds_df["feed_name"].apply(lambda name: text_match_ratio(feed_search_blob(details, name), name_terms))
        current_scores = filtered["feed_name"].apply(lambda name: text_match_ratio(feed_search_blob(details, name), name_terms)) if not filtered.empty else pd.Series(dtype=float)
        exact_mask = current_scores >= 0.999 if not current_scores.empty else pd.Series(dtype=bool)
        partial_mask = current_scores > 0 if not current_scores.empty else pd.Series(dtype=bool)

        if not exact_mask.empty and exact_mask.any():
            previous = len(filtered)
            filtered = filtered[exact_mask]
            notes.append("Filtro textual aplicado con coincidencia completa en nombre/fórmula: " + ", ".join(name_terms) + f". Se mantienen {len(filtered)} de {previous} piensos.")
        elif not partial_mask.empty and partial_mask.any():
            previous = len(filtered)
            filtered = filtered[partial_mask]
            notes.append("Filtro textual aplicado con coincidencia parcial en nombre/fórmula: " + ", ".join(name_terms) + f". Se mantienen {len(filtered)} de {previous} piensos.")
        elif (original_scores > 0).any():
            notes.append("Sí existen productos relacionados con " + ", ".join(name_terms) + " en el Excel, pero ninguno cumple además los filtros nutricionales y/o de precio indicados.")
            filtered = filtered.iloc[0:0]
        else:
            notes.append("La consulta incluye términos textuales (" + ", ".join(name_terms) + "), pero no hay coincidencias directas en el nombre o la fórmula del Excel.")
    return filtered, notes


def score_rule(value: Any, rule: Dict[str, Any]) -> float:
    numeric_value = safe_float(value)
    if numeric_value is None:
        return 0.0
    kind = rule.get("kind")
    if kind == "min":
        ref = max(abs(rule["value"]), 1e-6)
        return 1.0 if numeric_value >= rule["value"] else max(0.0, 1.0 - ((rule["value"] - numeric_value) / ref))
    if kind == "max":
        ref = max(abs(rule["value"]), 1e-6)
        return 1.0 if numeric_value <= rule["value"] else max(0.0, 1.0 - ((numeric_value - rule["value"]) / ref))
    if kind == "target":
        target = rule["value"]
        tol = max(rule.get("tol", abs(target) * 0.10), 1e-6)
        return max(0.0, 1.0 - (abs(numeric_value - target) / tol))
    if kind == "range":
        low = float(rule["min"])
        high = float(rule["max"])
        midpoint = (low + high) / 2.0
        half_span = max((high - low) / 2.0, abs(midpoint) * 0.05, 1e-6)
        distance = abs(numeric_value - midpoint)
        if low <= numeric_value <= high:
            return max(0.65, 1.0 - 0.35 * (distance / half_span))
        extra = abs(numeric_value - (low if numeric_value < low else high))
        return max(0.0, 0.65 - 0.65 * (extra / half_span))
    return 0.0


def rank_feeds(feeds_df: pd.DataFrame, requirements: Dict[str, Dict[str, Any]], selected_nutrients: List[str], top_n: int, prefer_low_price: bool, details: Optional[Dict[str, Any]] = None, query_constraints: Optional[Dict[str, Any]] = None) -> Tuple[pd.DataFrame, Dict[str, Any], List[str]]:
    ranking_rows: List[Dict[str, Any]] = []
    score_details: Dict[str, Any] = {}
    notes: List[str] = []

    working_requirements = {nutrient: rule.copy() for nutrient, rule in requirements.items()}
    query_constraints = query_constraints or {}
    details = details or {}
    name_terms = query_constraints.get("name_terms", [])

    if feeds_df.empty:
        raise ValueError("No hay piensos para ordenar después de aplicar los filtros.")

    if not working_requirements and not name_terms and not prefer_low_price:
        if selected_nutrients:
            for nutrient in selected_nutrients:
                if nutrient in feeds_df.columns:
                    working_requirements[nutrient] = {"kind": default_preference_kind(nutrient), "weight": 1.0, "fallback": True}
            if working_requirements:
                notes.append("No se detectaron restricciones numéricas en el chat; se usa un ranking exploratorio del Excel basado en los nutrientes seleccionados.")
        if not working_requirements and "price" in feeds_df.columns:
            prefer_low_price = True
            notes.append("No había restricciones técnicas utilizables; se ordena el Excel por precio ascendente como criterio exploratorio.")

    if not working_requirements and not name_terms and not prefer_low_price:
        raise ValueError("No se pudo construir un criterio de búsqueda útil a partir del chat y del Excel disponible.")

    pref_score_maps: Dict[str, Dict[Any, float]] = {}
    for nutrient, rule in working_requirements.items():
        if rule.get("kind") not in {"preference_max", "preference_min"} or nutrient not in feeds_df.columns:
            continue
        series = pd.to_numeric(feeds_df[nutrient], errors="coerce")
        valid = series.dropna()
        if valid.empty:
            pref_score_maps[nutrient] = {}
            continue
        min_val, max_val = float(valid.min()), float(valid.max())
        nutrient_scores: Dict[Any, float] = {}
        for row_idx, value in series.items():
            numeric_value = safe_float(value)
            if numeric_value is None:
                nutrient_scores[row_idx] = 0.0
            elif max_val <= min_val:
                nutrient_scores[row_idx] = 1.0
            elif rule.get("kind") == "preference_max":
                nutrient_scores[row_idx] = max(0.0, min(1.0, (numeric_value - min_val) / (max_val - min_val)))
            else:
                nutrient_scores[row_idx] = max(0.0, min(1.0, (max_val - numeric_value) / (max_val - min_val)))
        pref_score_maps[nutrient] = nutrient_scores

    price_scores: Dict[Any, float] = {}
    price_series = pd.to_numeric(feeds_df.get("price"), errors="coerce") if "price" in feeds_df.columns else pd.Series(dtype=float)
    if prefer_low_price and not price_series.empty:
        valid_price = price_series.dropna()
        if not valid_price.empty:
            min_price, max_price = float(valid_price.min()), float(valid_price.max())
            for row_idx, value in price_series.items():
                numeric_value = safe_float(value)
                if numeric_value is None:
                    price_scores[row_idx] = 0.0
                elif max_price <= min_price:
                    price_scores[row_idx] = 1.0
                else:
                    price_scores[row_idx] = max(0.0, min(1.0, (max_price - numeric_value) / (max_price - min_price)))

    text_scores: Dict[Any, float] = {}
    if name_terms:
        for row_idx, row in feeds_df.iterrows():
            text_scores[row_idx] = text_match_ratio(feed_search_blob(details, row.get("feed_name")), name_terms)

    for row_idx, row in feeds_df.iterrows():
        total_weight = 0.0
        total_score = 0.0
        nutrient_breakdown: List[Dict[str, Any]] = []

        for nutrient, rule in working_requirements.items():
            if nutrient not in feeds_df.columns:
                continue
            weight = float(rule.get("weight", 1.0))
            kind = rule.get("kind")
            if kind in {"min", "max", "target", "range"}:
                score = score_rule(row.get(nutrient), rule)
            elif kind in {"preference_max", "preference_min"}:
                score = pref_score_maps.get(nutrient, {}).get(row_idx, 0.0)
            else:
                score = 0.0

            total_weight += weight
            total_score += score * weight
            nutrient_breakdown.append({
                "nutrient": nutrient,
                "label": nutrient_label(nutrient),
                "value": row.get(nutrient),
                "requirement": describe_rule(rule),
                "score": round(score * 100, 1),
            })

        if name_terms:
            text_score = text_scores.get(row_idx, 0.0)
            total_weight += 1.2
            total_score += text_score * 1.2
            nutrient_breakdown.append({
                "nutrient": "__TEXT__",
                "label": "Coincidencia textual",
                "value": ", ".join(term for term in name_terms if term in feed_search_blob(details, row.get("feed_name"))),
                "requirement": "coincidir con el chat",
                "score": round(text_score * 100, 1),
            })

        if prefer_low_price and price_scores:
            p_score = price_scores.get(row_idx, 0.0)
            total_weight += 0.9
            total_score += p_score * 0.9
            nutrient_breakdown.append({
                "nutrient": "__PRICE__",
                "label": "Precio",
                "value": row.get("price"),
                "requirement": "priorizar precio bajo",
                "score": round(p_score * 100, 1),
            })

        aptitude = 0.0 if total_weight == 0 else 100.0 * total_score / total_weight
        ranking_row = {"Pienso": row.get("feed_name"), "Precio": safe_float(row.get("price")), "Aptitud": round(float(aptitude), 2)}
        for nutrient in selected_nutrients:
            if nutrient in feeds_df.columns:
                ranking_row[nutrient_label(nutrient)] = row.get(nutrient)
        ranking_rows.append(ranking_row)
        score_details[row.get("feed_name")] = {"nutrient_breakdown": nutrient_breakdown, "aptitude": round(float(aptitude), 2)}

    ranking_df = pd.DataFrame(ranking_rows)
    if ranking_df.empty:
        raise ValueError("No hay piensos para ordenar después de aplicar los filtros.")
    sort_cols = ["Aptitud"]
    ascending = [False]
    if "Precio" in ranking_df.columns:
        sort_cols.append("Precio")
        ascending.append(True)
    ranking_df = ranking_df.sort_values(sort_cols, ascending=ascending).head(top_n).reset_index(drop=True)
    return ranking_df, score_details, notes


def create_comparison_table(feed_name: str, feeds_df: pd.DataFrame, requirements: Dict[str, Dict[str, Any]], score_details: Dict[str, Any]) -> pd.DataFrame:
    row = feeds_df[feeds_df["feed_name"] == feed_name]
    if row.empty:
        return pd.DataFrame()
    row = row.iloc[0]
    breakdown = score_details.get(feed_name, {}).get("nutrient_breakdown", [])
    rows = []
    for item in breakdown:
        rows.append({"Nutriente": item["label"], "Valor del pienso": row.get(item["nutrient"]), "Requerimiento": item["requirement"], "Score nutriente (%)": item["score"]})
    return pd.DataFrame(rows)


def summarise_feed_reason(feed_name: str, score_details: Dict[str, Any]) -> str:
    breakdown = score_details.get(feed_name, {}).get("nutrient_breakdown", [])
    if not breakdown:
        return "Sin desglose disponible."
    breakdown_sorted = sorted(breakdown, key=lambda item: item["score"], reverse=True)
    strongest = breakdown_sorted[:3]
    weakest = [item for item in breakdown_sorted if item["score"] < 70][:2]
    strong_text = ", ".join(f"{item['label']} ({item['score']:.0f}%)" for item in strongest)
    weak_text = ", ".join(f"{item['label']} ({item['score']:.0f}%)" for item in weakest)
    return f"Fortalezas: {strong_text}. Puntos a vigilar: {weak_text}." if weak_text else f"Buen ajuste en: {strong_text}."


def truncate_text(text: str, max_len: int = 340) -> str:
    text = text.strip()
    return text if len(text) <= max_len else text[: max_len - 3].rstrip() + "..."


def generate_assistant_answer(species: str, query: str, profile: Dict[str, Any], ranking_df: pd.DataFrame, score_details: Dict[str, Any], fedna_snippets: List[Dict[str, Any]], applied_filters: List[str], ranking_notes: List[str], selected_nutrients: List[str]) -> str:
    lines: List[str] = []
    lines.append("La búsqueda y el ranking se han hecho solo con el Excel cargado.")
    lines.append("FEDNA se usa aquí únicamente como contexto técnico para el chat, no como motor de ordenación de productos.")
    if selected_nutrients:
        lines.append("Nutrientes visibles / considerados en esta ejecución: " + ", ".join(nutrient_label(n) for n in selected_nutrients) + ".")
    if applied_filters:
        lines.append("**Filtros aplicados sobre el Excel:**")
        lines.extend(f"- {note}" for note in applied_filters)
    if ranking_notes:
        lines.extend(f"- {note}" for note in ranking_notes)

    if ranking_df.empty:
        lines.append("No se han encontrado piensos que cumplan los criterios activos del chat.")
        if fedna_snippets:
            lines.append("")
            lines.append("**Contexto FEDNA para la categoría seleccionada:**")
            for snippet in fedna_snippets[:2]:
                lines.append(f"- {snippet['file_name']} · p. {snippet['page']}: {truncate_text(snippet['text'], 280)}")
        return "\n".join(lines)

    lines.append("**Top recomendaciones del Excel:**")
    for idx, row in ranking_df.head(min(3, len(ranking_df))).iterrows():
        price_text = "n/d" if pd.isna(row.get("Precio")) else f"{row['Precio']:.3f}"
        lines.append(f"{idx + 1}. **{row['Pienso']}** — aptitud {row['Aptitud']:.2f} / 100; precio {price_text}. {summarise_feed_reason(row['Pienso'], score_details)}")
    if query.strip():
        lines.append(f"Consulta interpretada: _{query.strip()}_.")
    if fedna_snippets:
        lines.append("")
        lines.append("**Contexto FEDNA relacionado con la categoría seleccionada (solo informativo):**")
        for snippet in fedna_snippets[:3]:
            lines.append(f"- {snippet['file_name']} · p. {snippet['page']}: {truncate_text(snippet['text'], 280)}")
    return "\n".join(lines)


def generate_summary_report(species: str, query: str, profile: Dict[str, Any], ranking_df: pd.DataFrame, score_details: Dict[str, Any], selected_nutrients: List[str], warnings: List[str], source_format: str) -> str:
    lines = [
        "# Informe resumen",
        "",
        f"**Especie/categoría:** {species}",
        f"**Consulta:** {query or 'Ranking exploratorio basado en el Excel'}",
        "**Uso de FEDNA:** contexto técnico para el chat; no interviene en el ranking de productos.",
        f"**Perfil FEDNA contextual:** {profile.get('name', 'General')}",
        f"**Formato detectado del Excel:** {source_format}",
    ]
    if selected_nutrients:
        lines.append("**Nutrientes mostrados / considerados:** " + ", ".join(nutrient_label(n) for n in selected_nutrients))
    lines.extend(["", "## Resultados"])
    if ranking_df.empty:
        lines.append("No se obtuvieron resultados que cumplieran los filtros del chat.")
    else:
        for idx, row in ranking_df.iterrows():
            lines.append(f"{idx + 1}. {row['Pienso']} — aptitud {row['Aptitud']:.2f} / 100; precio {row['Precio'] if pd.notna(row['Precio']) else 'n/d'}.")
            lines.append(f"   - {summarise_feed_reason(row['Pienso'], score_details)}")
    lines.extend(["", "## Recomendación final"])
    if not ranking_df.empty:
        best = ranking_df.iloc[0]
        lines.append(f"El pienso recomendado es **{best['Pienso']}** porque es el que mejor encaja con los filtros y prioridades leídos desde el chat y contrastados exclusivamente contra el Excel cargado.")
    else:
        lines.append("No es posible recomendar un pienso con la consulta actual. Conviene revisar si el Excel contiene productos compatibles con lo pedido.")
    lines.extend(["", "## Supuestos y limitaciones"])
    lines.append("- Los productos se ordenan con datos del Excel y con reglas deterministas; no se usa un LLM externo para calcular la aptitud.")
    lines.append("- FEDNA se muestra como soporte técnico contextual y no modifica el ranking.")
    lines.append("- Si el chat pide un nutriente o criterio que no existe en el Excel, el sistema lo indica y sigue trabajando con lo disponible.")
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines)


def default_selected_nutrients(species: str, available_nutrients: List[str], limit: int) -> List[str]:
    profile = FEDNA_PROFILES.get(species, [{}])[0]
    preferred = [n for n in profile.get("requirements", {}).keys() if n in available_nutrients]
    return preferred[:limit] if preferred else available_nutrients[:limit]


def render_feed_detail(selected_feed_name: str, feeds_df: pd.DataFrame, details: Dict[str, Any], requirements: Dict[str, Dict[str, Any]], score_details: Dict[str, Any]) -> None:
    st.subheader(f"Detalle de {selected_feed_name}")
    feed_row = feeds_df[feeds_df["feed_name"] == selected_feed_name]
    if feed_row.empty:
        st.info("No hay datos detallados para este pienso.")
        return
    col1, col2 = st.columns([1.25, 1])
    with col1:
        ingredients = details.get(selected_feed_name, {}).get("ingredients", [])
        if ingredients:
            ing_df = pd.DataFrame(ingredients)
            cols = [col for col in ["ingredient_name", "pct", "minimum", "maximum", "limit_flag"] if col in ing_df.columns]
            ing_df = ing_df[cols].rename(columns={"ingredient_name": "Ingrediente", "pct": "% inclusión", "minimum": "Mínimo", "maximum": "Máximo", "limit_flag": "Tipo límite"})
            st.markdown("**Fórmula completa (ingredientes y porcentajes)**")
            st.dataframe(ing_df, use_container_width=True, hide_index=True)
        else:
            st.info("Este formato de Excel no aporta desglose explícito de ingredientes para el pienso seleccionado.")
    with col2:
        comparison_df = create_comparison_table(selected_feed_name, feeds_df, requirements, score_details)
        if not comparison_df.empty:
            st.markdown("**Informe de nutrientes frente al requerimiento activo**")
            st.dataframe(comparison_df, use_container_width=True, hide_index=True)
        else:
            st.info("No hay comparación nutricional disponible para este pienso.")

    nutrient_limits = details.get(selected_feed_name, {}).get("nutrient_limits", {})
    if nutrient_limits:
        rows = []
        for nutrient, values in nutrient_limits.items():
            if values.get("min") is None and values.get("max") is None and not values.get("flag"):
                continue
            rows.append({"Nutriente": nutrient_label(nutrient), "Mínimo fórmula": values.get("min"), "Máximo fórmula": values.get("max"), "Bandera": values.get("flag")})
        if rows:
            with st.expander("Límites internos de la fórmula"):
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_manual_status(manual_entries: List[Dict[str, Any]], species: str) -> None:
    relevant = [m for m in manual_entries if m.get("species") == species and m.get("load_status") == "ok"]
    if relevant:
        st.success("Manuales FEDNA listos para esta categoría: " + ", ".join(f"{m['file_name']} ({m['origin']})" for m in relevant))
    else:
        st.info("No hay un PDF FEDNA utilizable para esta categoría. La app seguirá funcionando con perfiles FEDNA integrados, pero sin recuperación de fragmentos del manual.")
    failed = [m for m in manual_entries if m.get("load_status") in {"empty", "error"}]
    if failed:
        with st.expander("Ver incidencias de carga de PDF"):
            for item in failed:
                st.warning(f"{item['file_name']}: {item.get('load_error') or 'No se pudo procesar el archivo.'}")


def get_query_suggestions(species: str, selected_nutrients: List[str], available_nutrients: List[str], feeds_df: pd.DataFrame, details: Dict[str, Any], limit: int = 50) -> List[str]:
    nutrient_pool = [nutrient_label(code) for code in (selected_nutrients or available_nutrients)[:8]]
    while len(nutrient_pool) < 4 and len(nutrient_pool) < len(available_nutrients):
        nutrient_pool.append(nutrient_label(available_nutrients[len(nutrient_pool)]))
    sample_feeds = feeds_df["feed_name"].dropna().astype(str).head(8).tolist() if "feed_name" in feeds_df.columns else []
    ingredient_counter: Dict[str, int] = {}
    for feed_name in list(details.keys())[: min(len(details), 80)]:
        for item in details.get(feed_name, {}).get("ingredients", [])[:40]:
            ing_name = str(item.get("ingredient_name", "")).strip()
            if not ing_name:
                continue
            key = normalize_ascii(ing_name).lower()
            ingredient_counter[key] = ingredient_counter.get(key, 0) + 1
    sample_ingredients = [
        next(str(item.get("ingredient_name", "")).strip() for feed_name in details for item in details.get(feed_name, {}).get("ingredients", []) if normalize_ascii(str(item.get("ingredient_name", "")).strip()).lower() == key)
        for key, _ in sorted(ingredient_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    ]
    species_terms = {
        "Porcino": ["crecimiento", "acabado", "gestación", "lactación"],
        "Avicultura": ["iniciación", "crecimiento", "acabado", "puesta"],
        "Rumiantes de carne": ["cebo", "arranque", "acabado", "transición"],
        "Rumiantes de leche": ["lactación", "transición", "alta producción", "secado"],
        "Reposición de rumiantes": ["starter", "recría", "crecimiento", "preparto"],
    }.get(species, [species.lower()])
    templates: List[str] = []
    price_limit = 300
    for phase in species_terms:
        templates.append(f"Busca piensos para {phase} con precio <= {price_limit} y ordénalos por precio ascendente.")
        templates.append(f"Busca piensos para {phase} con proteína alta y precio <= {price_limit}.")
        if nutrient_pool:
            templates.append(f"Busca piensos para {phase} con {nutrient_pool[0]} >= 0.70 y precio <= {price_limit}.")
        if len(nutrient_pool) > 1:
            templates.append(f"Busca piensos para {phase} con {nutrient_pool[0]} alta y {nutrient_pool[1]} alta.")
        if len(nutrient_pool) > 2:
            templates.append(f"Busca piensos para {phase} con {nutrient_pool[2]} baja y buen precio.")
    for nutrient in nutrient_pool[:6]:
        templates.append(f"Ordena el Excel priorizando {nutrient} y después el precio más bajo.")
        templates.append(f"Filtra piensos con {nutrient} >= 0.50 y devuelve el top 10.")
        templates.append(f"Muéstrame los piensos con {nutrient} más alto y compara el precio.")
    for ingredient in sample_ingredients[:6]:
        templates.append(f"Busca piensos con {ingredient} en la fórmula y ordénalos por precio.")
        templates.append(f"Busca piensos sin {ingredient} y prioriza {nutrient_pool[0] if nutrient_pool else 'los nutrientes seleccionados'}.")
    for feed_name in sample_feeds[:10]:
        templates.append(f"Busca por nombre del pienso: {feed_name}.")
        templates.append(f"Muéstrame el detalle y la comparación nutricional del pienso {feed_name}.")
    templates.extend([
        "Busca un producto barato que además cumpla mis límites de nutrientes.",
        "Filtra por el nombre del producto o por ingredientes y luego ordénalo por aptitud.",
        "Quiero todos los productos cuyo nombre contenga starter o arranque.",
        "Compara varios piensos seleccionados manualmente y muestra siempre el precio.",
        "Busca los piensos con más proteína y menos precio.",
        "Busca los piensos con más energía y menos precio.",
        "Busca piensos que cumplan calcio entre 0.80 y 1.10 y fósforo >= 0.40.",
        "Busca piensos con lisina alta, proteína alta y precio bajo.",
    ])
    unique_templates: List[str] = []
    seen = set()
    for item in templates:
        clean = " ".join(str(item).split())
        if clean and clean not in seen:
            seen.add(clean)
            unique_templates.append(clean)
        if len(unique_templates) >= limit:
            break
    filler_index = 1
    while len(unique_templates) < limit:
        dynamic_nutrient = nutrient_pool[(filler_index - 1) % max(len(nutrient_pool), 1)] if nutrient_pool else "el nutriente seleccionado"
        unique_templates.append(f"Propuesta editable {filler_index}: filtra por {dynamic_nutrient}, ajusta el precio y revisa el top {min(10, max(3, filler_index % 10 + 1))}.")
        filler_index += 1
    return unique_templates[:limit]


def build_selected_feed_comparison(selected_feed_names: List[str], feeds_df: pd.DataFrame, details: Dict[str, Any], selected_nutrients: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if not selected_feed_names:
        return pd.DataFrame(), pd.DataFrame()
    subset = feeds_df[feeds_df["feed_name"].isin(selected_feed_names)].copy()
    if subset.empty:
        return pd.DataFrame(), pd.DataFrame()
    subset["__order__"] = pd.Categorical(subset["feed_name"], categories=selected_feed_names, ordered=True)
    subset = subset.sort_values("__order__").drop(columns="__order__")
    comparison_cols = ["feed_name", "price"] + [n for n in selected_nutrients if n in subset.columns]
    nutrient_df = subset[comparison_cols].rename(columns={"feed_name": "Pienso", "price": "Precio"}).copy()
    nutrient_df = nutrient_df.rename(columns={code: nutrient_label(code) for code in selected_nutrients if code in nutrient_df.columns})

    ingredient_names = sorted({
        str(item.get("ingredient_name", "")).strip()
        for feed_name in selected_feed_names
        for item in details.get(feed_name, {}).get("ingredients", [])
        if str(item.get("ingredient_name", "")).strip()
    })
    if not ingredient_names:
        return nutrient_df, pd.DataFrame()

    ingredient_rows: List[Dict[str, Any]] = []
    for ingredient in ingredient_names:
        row: Dict[str, Any] = {"Ingrediente": ingredient}
        present_somewhere = False
        for feed_name in selected_feed_names:
            ingredients = details.get(feed_name, {}).get("ingredients", [])
            match = next((item for item in ingredients if str(item.get("ingredient_name", "")).strip() == ingredient), None)
            if match is None:
                row[feed_name] = np.nan
                continue
            present_somewhere = True
            row[feed_name] = safe_float(match.get("pct"))
        if present_somewhere:
            ingredient_rows.append(row)

    ingredient_df = pd.DataFrame(ingredient_rows)
    if not ingredient_df.empty:
        ingredient_df["Presente en nº piensos"] = ingredient_df[selected_feed_names].notna().sum(axis=1)
        ingredient_df = ingredient_df.sort_values(["Presente en nº piensos", "Ingrediente"], ascending=[False, True]).reset_index(drop=True)
    return nutrient_df, ingredient_df


def reset_search_state(clear_query: bool = True) -> None:
    st.session_state["chat_history"] = []
    st.session_state["last_result"] = None
    st.session_state["last_query"] = ""
    st.session_state["selected_feed_name"] = None
    st.session_state["pending_query_prefill"] = None
    st.session_state["selected_feed_compare"] = []
    st.session_state.pop("proposal_selector", None)
    if clear_query:
        st.session_state["query_draft"] = ""


def queue_new_search() -> None:
    st.session_state["pending_new_search"] = True


def queue_query_prefill(query: str) -> None:
    st.session_state["pending_query_prefill"] = query


def apply_pending_state_actions() -> None:
    if st.session_state.pop("pending_new_search", False):
        reset_search_state(clear_query=True)
    pending_prefill = st.session_state.pop("pending_query_prefill", None)
    if pending_prefill is not None:
        st.session_state["query_draft"] = pending_prefill


def run_recommendation(species: str, query: str, parsed_excel: Dict[str, Any], manual_entries: List[Dict[str, Any]], selected_nutrients: List[str], top_n: int) -> Dict[str, Any]:
    feeds_df = parsed_excel["feeds_df"]
    available_nutrients = parsed_excel["numeric_nutrients"]
    details = parsed_excel["details"]

    profile = choose_fedna_profile(species, query)
    query_constraints = parse_query_constraints(query, available_nutrients)
    filtered_df, applied_filters = apply_query_filters(feeds_df, details, query_constraints)
    requirements = merge_requirements(profile, query_constraints, selected_nutrients, available_nutrients)
    fedna_snippets = retrieve_fedna_snippets(manual_entries, species, query or species, top_k=3)

    if filtered_df.empty:
        ranking_df = pd.DataFrame(columns=["Pienso", "Precio", "Aptitud"])
        score_details = {}
        ranking_notes = ["No quedan productos tras aplicar los filtros leídos desde el chat sobre el Excel."]
    else:
        ranking_df, score_details, ranking_notes = rank_feeds(
            filtered_df,
            requirements=requirements,
            selected_nutrients=selected_nutrients,
            top_n=top_n,
            prefer_low_price=query_constraints.get("prefer_low_price", False),
            details=details,
            query_constraints=query_constraints,
        )

    assistant_answer = generate_assistant_answer(
        species=species, query=query, profile=profile, ranking_df=ranking_df, score_details=score_details,
        fedna_snippets=fedna_snippets, applied_filters=applied_filters, ranking_notes=ranking_notes,
        selected_nutrients=selected_nutrients,
    )
    summary_report = generate_summary_report(
        species=species, query=query, profile=profile, ranking_df=ranking_df, score_details=score_details,
        selected_nutrients=selected_nutrients, warnings=parsed_excel["warnings"], source_format=parsed_excel["source_format"],
    )
    return {
        "profile": profile,
        "query_constraints": query_constraints,
        "ranking_df": ranking_df,
        "score_details": score_details,
        "requirements": requirements,
        "assistant_answer": assistant_answer,
        "summary_report": summary_report,
        "fedna_snippets": fedna_snippets,
        "applied_filters": applied_filters,
        "ranking_notes": ranking_notes,
    }


def init_session_state() -> None:
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("query_draft", "")
    st.session_state.setdefault("last_query", "")
    st.session_state.setdefault("selected_feed_name", None)
    st.session_state.setdefault("pending_new_search", False)
    st.session_state.setdefault("pending_query_prefill", None)
    st.session_state.setdefault("selected_feed_compare", [])
    st.session_state.setdefault("proposal_selector", None)


def sanitize_sheet_name(name: str, used_names: Optional[set] = None) -> str:
    cleaned = re.sub(r'[\/*?:\[\]]', '_', str(name or 'Hoja')).strip()
    cleaned = cleaned[:31] or 'Hoja'
    if used_names is None:
        return cleaned
    base = cleaned
    counter = 1
    while cleaned in used_names:
        suffix = f"_{counter}"
        cleaned = (base[: 31 - len(suffix)] + suffix) if len(base) + len(suffix) > 31 else base + suffix
        counter += 1
    used_names.add(cleaned)
    return cleaned


def dataframe_to_excel_bytes(sheets: Dict[str, pd.DataFrame]) -> bytes:
    output = io.BytesIO()
    used_names: set = set()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in sheets.items():
            safe_name = sanitize_sheet_name(sheet_name, used_names)
            export_df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame(df)
            export_df.to_excel(writer, sheet_name=safe_name, index=False)
            worksheet = writer.sheets[safe_name]
            for idx, col in enumerate(export_df.columns, start=1):
                max_len = max([len(str(col))] + [len(str(v)) for v in export_df[col].head(200).fillna('').tolist()])
                worksheet.column_dimensions[get_column_letter(idx)].width = min(max(max_len + 2, 12), 45)
    output.seek(0)
    return output.getvalue()


def build_feed_formula_dataframe(feed_name: str, details: Dict[str, Any]) -> pd.DataFrame:
    ingredients = details.get(feed_name, {}).get('ingredients', [])
    if not ingredients:
        return pd.DataFrame()
    df = pd.DataFrame(ingredients)
    keep_cols = [col for col in ['ingredient_name', 'pct', 'minimum', 'maximum', 'limit_flag', 'avg_cost'] if col in df.columns]
    df = df[keep_cols].copy()
    rename_map = {
        'ingredient_name': 'Ingrediente',
        'pct': '% inclusión',
        'minimum': 'Mínimo',
        'maximum': 'Máximo',
        'limit_flag': 'Tipo límite',
        'avg_cost': 'Coste medio',
    }
    return df.rename(columns=rename_map)


def build_breakdown_export_dataframe(score_details: Dict[str, Any], feed_names: List[str]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for feed_name in feed_names:
        breakdown = score_details.get(feed_name, {}).get('nutrient_breakdown', [])
        for item in breakdown:
            rows.append({
                'Pienso': feed_name,
                'Nutriente': item.get('label'),
                'Valor': item.get('value'),
                'Requerimiento': item.get('requirement'),
                'Score nutriente (%)': item.get('score'),
            })
    return pd.DataFrame(rows)


def markdown_text_to_dataframe(text: str) -> pd.DataFrame:
    lines = [line for line in str(text).splitlines()]
    return pd.DataFrame({'Informe': lines if lines else ['']})


def build_ranking_export_excel(
    species: str,
    query: str,
    parsed_excel: Dict[str, Any],
    selected_nutrients: List[str],
    last_result: Dict[str, Any],
    selected_feed_name: str,
    feeds_df: pd.DataFrame,
    details: Dict[str, Any],
) -> bytes:
    ranking_df = last_result.get('ranking_df', pd.DataFrame()).copy()
    summary_df = pd.DataFrame([
        {'Campo': 'Especie/categoría', 'Valor': species},
        {'Campo': 'Consulta', 'Valor': query or 'Ranking base Excel'},
        {'Campo': 'Formato Excel detectado', 'Valor': parsed_excel.get('source_format')},
        {'Campo': 'Perfil FEDNA contextual', 'Valor': last_result.get('profile', {}).get('name', '')},
        {'Campo': 'Nutrientes seleccionados', 'Valor': ', '.join(nutrient_label(n) for n in selected_nutrients)},
    ])

    filters_df = pd.DataFrame({'Notas': (last_result.get('applied_filters', []) + last_result.get('ranking_notes', [])) or ['Sin notas adicionales']})
    detail_df = create_comparison_table(selected_feed_name, feeds_df, last_result.get('requirements', {}), last_result.get('score_details', {}))
    formula_df = build_feed_formula_dataframe(selected_feed_name, details)
    breakdown_df = build_breakdown_export_dataframe(last_result.get('score_details', {}), ranking_df['Pienso'].tolist() if not ranking_df.empty else [])

    snippets = last_result.get('fedna_snippets', [])
    snippets_df = pd.DataFrame(snippets) if snippets else pd.DataFrame({'file_name': [], 'page': [], 'text': []})
    if not snippets_df.empty:
        snippets_df = snippets_df.rename(columns={'file_name': 'Archivo PDF', 'page': 'Página', 'text': 'Fragmento'})

    sheets: Dict[str, pd.DataFrame] = {
        'Resumen': summary_df,
        'Ranking': ranking_df if not ranking_df.empty else pd.DataFrame({'Pienso': [], 'Precio': [], 'Aptitud': []}),
        'Notas filtros': filters_df,
        'Detalle pienso': detail_df if not detail_df.empty else pd.DataFrame({'Detalle': ['Sin detalle disponible']}),
        'Fórmula pienso': formula_df if not formula_df.empty else pd.DataFrame({'Detalle': ['Sin fórmula detallada disponible']}),
        'Desglose ranking': breakdown_df if not breakdown_df.empty else pd.DataFrame({'Detalle': ['Sin desglose disponible']}),
        'Informe': markdown_text_to_dataframe(last_result.get('summary_report', '')),
    }
    if not snippets_df.empty:
        sheets['Fragmentos FEDNA'] = snippets_df
    return dataframe_to_excel_bytes(sheets)


def build_comparison_export_excel(
    compare_selection: List[str],
    nutrient_compare_df: pd.DataFrame,
    ingredient_compare_df: pd.DataFrame,
    details: Dict[str, Any],
) -> bytes:
    summary_df = pd.DataFrame([
        {'Campo': 'Número de piensos comparados', 'Valor': len(compare_selection)},
        {'Campo': 'Piensos incluidos', 'Valor': ', '.join(compare_selection)},
    ])
    sheets: Dict[str, pd.DataFrame] = {
        'Resumen': summary_df,
        'Nutrientes': nutrient_compare_df if not nutrient_compare_df.empty else pd.DataFrame({'Detalle': ['Sin comparativa nutricional disponible']}),
        'Ingredientes': ingredient_compare_df if not ingredient_compare_df.empty else pd.DataFrame({'Detalle': ['Sin comparativa de ingredientes disponible']}),
    }
    for feed_name in compare_selection:
        formula_df = build_feed_formula_dataframe(feed_name, details)
        sheets[f'Fórmula {feed_name}'] = formula_df if not formula_df.empty else pd.DataFrame({'Detalle': ['Sin fórmula detallada disponible']})
    return dataframe_to_excel_bytes(sheets)


def main() -> None:
    init_session_state()
    apply_pending_state_actions()

    st.title("FEDNA Feed Recommender")
    st.caption("Aplicación Streamlit para buscar y ordenar piensos a partir del Excel cargado. FEDNA se usa como contexto técnico en el chat, no para decidir el ranking.")

    with st.sidebar:
        st.header("Configuración")
        species = st.selectbox("Especie/categoría", SPECIES_OPTIONS, index=4)
        top_n = st.slider("Top N de piensos recomendados", min_value=1, max_value=15, value=5)
        excel_file = st.file_uploader("Carga el Excel mensual de formulación", type=["xlsx", "xlsm", "xls"])
        manual_files = st.file_uploader(
            "PDFs FEDNA (opcional, múltiples)",
            type=["pdf"],
            accept_multiple_files=True,
            help="Si no se cargan aquí, la app buscará PDFs en ./fedna_manuals/. Los PDFs que fallen no bloquearán la app.",
        )

    try:
        manual_entries = build_manual_entries(manual_files or [])
    except Exception as exc:
        st.warning(f"No se pudieron procesar los PDF FEDNA: {exc}")
        manual_entries = []
    render_manual_status(manual_entries, species)

    if excel_file is None:
        st.info("Carga un Excel para empezar. La app soporta formato tabular clásico y reportes tipo formulación con bloques 'Specification:' o 'SP:' más sus secciones de ingredientes y análisis.")
        st.markdown("**Sugerencia de uso:** selecciona la categoría, sube el Excel, define los nutrientes a mostrar y utiliza la consulta editable para buscar sobre el propio Excel, por ejemplo: `busca gestantes con lisina > 0.70 y precio < 290`.")
        return

    try:
        parsed_excel = parse_excel_bytes(excel_file.getvalue(), excel_file.name)
    except Exception as exc:
        st.error(f"Error al procesar el Excel: {exc}")
        return

    for warning in parsed_excel["warnings"]:
        st.warning(warning)

    feeds_df = parsed_excel["feeds_df"]
    details = parsed_excel["details"]
    available_nutrients = parsed_excel["numeric_nutrients"]

    st.subheader("Datos cargados")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Piensos detectados", len(feeds_df))
    col_b.metric("Nutrientes numéricos detectados", len(available_nutrients))
    col_c.metric("Formato del Excel", parsed_excel["source_format"])

    with st.expander("Vista previa del dataset normalizado"):
        preview_cols = [col for col in ["feed_name", "price"] + available_nutrients[:8] if col in feeds_df.columns]
        st.dataframe(feeds_df[preview_cols].head(15), use_container_width=True, hide_index=True)

    nutrient_limit = st.number_input("Número máximo de nutrientes a seleccionar", min_value=1, max_value=max(1, len(available_nutrients)), value=min(8, max(1, len(available_nutrients))), step=1)
    default_nutrients = default_selected_nutrients(species, available_nutrients, int(nutrient_limit))
    selected_nutrients = st.multiselect(
        "Nutrientes utilizados en el cálculo / búsqueda",
        options=available_nutrients,
        default=default_nutrients,
        format_func=nutrient_label,
        max_selections=int(nutrient_limit),
    )

    st.subheader("Consulta y chat")
    st.caption("La consulta es editable y visible. La app interpreta el chat para filtrar y ordenar el Excel; FEDNA solo se usa para añadir contexto técnico en la respuesta.")

    suggestions = get_query_suggestions(species, selected_nutrients, available_nutrients, feeds_df, details, limit=50)
    with st.container(border=True):
        st.markdown("**1) Elige una propuesta editable (50 opciones)**")
        chosen_template = st.selectbox(
            "Propuestas de consulta",
            options=suggestions,
            index=0 if suggestions else None,
            key="proposal_selector",
            help="Selecciona una de las 50 propuestas, pulsa 'Usar propuesta' y después edítala libremente.",
            label_visibility="visible",
        )
        proposal_col, helper_col = st.columns([1, 2])
        if proposal_col.button("Usar propuesta", use_container_width=True):
            queue_query_prefill(chosen_template or "")
            st.rerun()
        helper_col.info("Estas propuestas sirven solo como borrador. Puedes cambiar nombres de piensos, ingredientes, nutrientes y cifras antes de buscar.")
        st.markdown("**2) Escribe o edita tu consulta**")
        st.text_area(
            "Chat / consulta editable",
            key="query_draft",
            height=180,
            placeholder="Ejemplo: Quiero el top 5 para porcino en crecimiento-cebo, priorizando lisina, energía neta y proteína bruta, con el menor precio posible y evitando trigo si aparece en la fórmula.",
        )

    st.subheader("Comparativa directa de piensos")
    st.caption("Selecciona varios piensos de toda la base de datos para compararlos por fórmula, nutrientes seleccionados y precio.")
    st.multiselect(
        "Selecciona uno o varios piensos de la base de datos",
        options=feeds_df["feed_name"].dropna().astype(str).tolist(),
        default=st.session_state.get("selected_feed_compare", []),
        key="selected_feed_compare",
        max_selections=12,
    )

    action_col1, action_col2, action_col3, action_col4 = st.columns(4)
    run_query = action_col1.button("Buscar y rankear", type="primary", use_container_width=True)
    refresh_query = action_col2.button("Refrescar resultados", use_container_width=True, disabled=not bool(st.session_state.get("query_draft", "").strip() or st.session_state.get("last_query", "").strip()))
    run_base = action_col3.button("Ranking base Excel", use_container_width=True)
    new_search = action_col4.button("Nueva búsqueda", use_container_width=True)

    if new_search:
        queue_new_search()
        st.rerun()

    active_query = st.session_state.get("query_draft", "").strip()
    if refresh_query and not active_query:
        active_query = st.session_state.get("last_query", "").strip()
        if active_query:
            queue_query_prefill(active_query)

    if run_base:
        try:
            result = run_recommendation(species=species, query="", parsed_excel=parsed_excel, manual_entries=manual_entries, selected_nutrients=selected_nutrients, top_n=top_n)
            st.session_state["last_result"] = result
            st.session_state["last_query"] = ""
            st.session_state["chat_history"].append({"role": "assistant", "content": "Ranking exploratorio ejecutado sobre el Excel cargado.\n\n" + result["assistant_answer"]})
        except Exception as exc:
            st.error(f"No se pudo ejecutar el ranking base: {exc}")

    if run_query or refresh_query:
        if not active_query:
            st.warning("Escribe o carga una consulta editable antes de buscar.")
        else:
            st.session_state["chat_history"].append({"role": "user", "content": active_query})
            try:
                result = run_recommendation(species=species, query=active_query, parsed_excel=parsed_excel, manual_entries=manual_entries, selected_nutrients=selected_nutrients, top_n=top_n)
                st.session_state["last_result"] = result
                st.session_state["last_query"] = active_query
                st.session_state["chat_history"].append({"role": "assistant", "content": result["assistant_answer"]})
            except Exception as exc:
                error_text = f"No se pudo generar la recomendación: {exc}"
                st.session_state["chat_history"].append({"role": "assistant", "content": error_text})
                st.error(error_text)

    if st.session_state["chat_history"]:
        st.markdown("#### Historial")
        for message in st.session_state["chat_history"]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    compare_selection = st.session_state.get("selected_feed_compare", [])
    if compare_selection:
        nutrient_compare_df, ingredient_compare_df = build_selected_feed_comparison(compare_selection, feeds_df, details, selected_nutrients)
        st.divider()
        st.subheader("Comparativa de los piensos seleccionados")
        st.caption("Puedes descargar esta comparativa en Excel con los nutrientes, la fórmula por ingredientes y una hoja individual por cada pienso seleccionado.")
        if not nutrient_compare_df.empty:
            st.markdown("**Nutrientes seleccionados y precio**")
            st.dataframe(nutrient_compare_df, use_container_width=True, hide_index=True)
        else:
            st.info("No se pudo construir la comparativa de nutrientes para la selección actual.")
        if not ingredient_compare_df.empty:
            st.markdown("**Comparativa de fórmula por ingredientes (% inclusión)**")
            st.dataframe(ingredient_compare_df, use_container_width=True, hide_index=True)
        else:
            st.info("No hay desglose de ingredientes suficiente para comparar las fórmulas seleccionadas.")

        comparison_excel = build_comparison_export_excel(compare_selection, nutrient_compare_df, ingredient_compare_df, details)
        st.download_button(
            "Descargar comparativa en Excel",
            data=comparison_excel,
            file_name="comparativa_piensos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    last_result = st.session_state.get("last_result")
    if not last_result:
        return

    st.divider()
    st.subheader("Top N recomendados")
    ranking_df = last_result["ranking_df"]
    if ranking_df.empty:
        st.warning("No hay resultados para mostrar.")
        return

    st.dataframe(ranking_df, use_container_width=True, hide_index=True)

    ranking_options = ranking_df["Pienso"].tolist()
    default_feed = st.session_state.get("selected_feed_name")
    if default_feed not in ranking_options:
        default_feed = ranking_options[0]
        st.session_state["selected_feed_name"] = default_feed
    selected_feed_name = st.selectbox("Selecciona un pienso para ver el detalle", options=ranking_options, index=ranking_options.index(default_feed), key="selected_feed_name")
    render_feed_detail(selected_feed_name, feeds_df, details, last_result["requirements"], last_result["score_details"])

    ranking_excel = build_ranking_export_excel(
        species=species,
        query=st.session_state.get("last_query", "").strip(),
        parsed_excel=parsed_excel,
        selected_nutrients=selected_nutrients,
        last_result=last_result,
        selected_feed_name=selected_feed_name,
        feeds_df=feeds_df,
        details=details,
    )
    st.download_button(
        "Descargar análisis y ranking en Excel",
        data=ranking_excel,
        file_name="analisis_ranking_fedna.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.divider()
    st.subheader("Informe resumen final")
    st.markdown(last_result["summary_report"])
    st.download_button("Descargar informe resumen (.md)", data=last_result["summary_report"].encode("utf-8"), file_name="informe_resumen_fedna.md", mime="text/markdown")

    fedna_snippets = last_result.get("fedna_snippets", [])
    if fedna_snippets:
        with st.expander("Fragmentos FEDNA recuperados"):
            for snippet in fedna_snippets:
                st.markdown(f"**{snippet['file_name']} · página {snippet['page']}**")
                st.write(truncate_text(snippet["text"], 900))


if __name__ == "__main__":
    main()
