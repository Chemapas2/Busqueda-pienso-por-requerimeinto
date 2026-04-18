from __future__ import annotations

import io
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st
from pypdf import PdfReader
from pypdf.errors import DependencyError


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
    "Reposición de rumiantes": ["recria", "recría", "recria", "recria de rumiantes"],
    "Avicultura": ["aves", "avicultura", "fedna aves"],
    "Porcino": ["porcino", "ganado porcino"],
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
        "nombre pienso",
        "pienso",
        "feed",
        "producto",
        "product",
        "formula",
        "fórmula",
        "nombre formula",
        "specification",
        "feed_name",
        "nombre",
    ],
    "price": [
        "precio",
        "cost",
        "coste",
        "cost/tonne",
        "cost per tonne",
        "€/t",
        "eur/t",
        "price",
        "precio pienso",
        "price_per_tonne",
    ],
}

QUERY_NUTRIENT_SYNONYMS = {
    "proteina": "PROT_BRU",
    "proteína": "PROT_BRU",
    "pb": "PROT_BRU",
    "prot_bru": "PROT_BRU",
    "grasa": "GRASA_BR",
    "ee": "GRASA_BR",
    "extracto etereo": "GRASA_BR",
    "extracto etéreo": "GRASA_BR",
    "fibra": "FIBRA_BR",
    "fb": "FIBRA_BR",
    "fnd": "FND",
    "adf": "FAD",
    "fad": "FAD",
    "almidon": "ALM_EWER",
    "almidón": "ALM_EWER",
    "azucares": "AZUCARES",
    "azúcares": "AZUCARES",
    "lactosa": "LACTOSA",
    "calcio": "CA",
    "ca": "CA",
    "fosforo": "P_",
    "fósforo": "P_",
    "p total": "P_",
    "p digestible": "AVP_AV",
    "p disponible": "AVP_AV",
    "avp": "AVP_AV",
    "sodio": "NA",
    "na": "NA",
    "cloro": "CL",
    "cl": "CL",
    "potasio": "K",
    "k": "K",
    "magnesio": "MG",
    "mg": "MG",
    "lisina": "LYS",
    "lys": "LYS",
    "metionina": "MET",
    "met": "MET",
    "met+cys": "MET_CYS",
    "met_cys": "MET_CYS",
    "met cys": "MET_CYS",
    "treonina": "THR",
    "thr": "THR",
    "triptofano": "TRP",
    "triptófano": "TRP",
    "trp": "TRP",
    "isoleucina": "ILE",
    "ile": "ILE",
    "valina": "VAL",
    "val": "VAL",
    "arginina": "ARG",
    "arg": "ARG",
    "leucina": "LEU",
    "leu": "LEU",
    "energia neta": "NE_SW",
    "energía neta": "NE_SW",
    "en": "NE_SW",
    "energia metabolizable": "ME_SW",
    "energía metabolizable": "ME_SW",
    "em": "ME_SW",
    "ema": "EMA",
    "eman": "EMAN",
    "ufc": "UFC",
    "ufl": "UFL",
    "pdi": "PDI",
    "pdin": "PDIN",
    "pdie": "PDIE",
    "cnf": "CNF",
}

STOPWORDS = {
    "de", "la", "el", "los", "las", "para", "con", "sin", "por", "del", "al",
    "un", "una", "que", "y", "o", "en", "kg", "pienso", "quiero", "necesito",
    "mas", "más", "menos", "tipo", "animal", "produccion", "producción", "fase",
    "formula", "fórmula", "sobre", "segun", "según", "como", "entre", "hasta",
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


def normalize_ascii(text: Any) -> str:
    text = "" if text is None else str(text)
    replacements = str.maketrans(
        {
            "á": "a",
            "é": "e",
            "í": "i",
            "ó": "o",
            "ú": "u",
            "ü": "u",
            "Á": "A",
            "É": "E",
            "Í": "I",
            "Ó": "O",
            "Ú": "U",
            "Ü": "U",
            "ñ": "n",
            "Ñ": "N",
        }
    )
    return text.translate(replacements)


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float, np.integer, np.floating)):
        if pd.isna(value):
            return None
        return float(value)
    text = str(value).strip()
    if text in {"", ".", "nan", "None", "-"}:
        return None
    text = text.replace("%", "").replace("€", "").replace(",", ".")
    text = re.sub(r"[^0-9.\-+]", "", text)
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
    text = text.replace("+", "_")
    text = text.replace("-", "_")
    text = text.replace("/", "_")
    text = text.replace(".", "_")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Z0-9_]", "", text)
    alias_map = {
        "PROTEINA": "PROT_BRU",
        "PROTEINA_BRUTA": "PROT_BRU",
        "PB": "PROT_BRU",
        "CRUDE_PROTEIN": "PROT_BRU",
        "GRASA": "GRASA_BR",
        "GRASA_BRUTA": "GRASA_BR",
        "EE": "GRASA_BR",
        "EXTRACTO_ETEREO": "GRASA_BR",
        "GB": "GRASA_BR",
        "FIBRA": "FIBRA_BR",
        "FIBRA_BRUTA": "FIBRA_BR",
        "FB": "FIBRA_BR",
        "NDF": "FND",
        "ADF": "FAD",
        "ALMIDON": "ALM_EWER",
        "STARCH": "ALM_EWER",
        "CALCIO": "CA",
        "FOSFORO": "P_",
        "FOSFORO_TOTAL": "P_",
        "P_TOTAL": "P_",
        "P": "P_",
        "FOSFORO_DIG": "AVP_AV",
        "FOSFORO_DIGESTIBLE": "AVP_AV",
        "FOSFORO_DISP": "AVP_AV",
        "P_DIGESTIBLE": "AVP_AV",
        "P_DISPONIBLE": "AVP_AV",
        "AVP": "AVP_AV",
        "SODIO": "NA",
        "CLORO": "CL",
        "POTASIO": "K",
        "MAGNESIO": "MG",
        "COBRE": "CU",
        "ZINC": "ZN",
        "MANGANESO": "MN",
        "SELENIO": "SE",
        "LISINA": "LYS",
        "METIONINA": "MET",
        "MET_CIS": "MET_CYS",
        "MET_CISTINA": "MET_CYS",
        "METIONINA_CISTINA": "MET_CYS",
        "TREONINA": "THR",
        "TRIPTOFANO": "TRP",
        "ISOLEUCINA": "ILE",
        "VALINA": "VAL",
        "ARGININA": "ARG",
        "LEUCINA": "LEU",
        "ENERGIA_NETA": "NE_SW",
        "EN": "NE_SW",
        "ENERGIA_METABOLIZABLE": "ME_SW",
        "EM": "EM",
        "ME": "ME_SW",
        "EMA": "EMA",
        "EMAN": "EMAN",
        "UFC_KG": "UFC",
        "UFL_KG": "UFL",
    }
    return alias_map.get(text, text)


def nutrient_label(code: str) -> str:
    return NUTRIENT_LABELS.get(code, code.replace("_", " ").title())


def tokenize(text: Any) -> List[str]:
    text = normalize_ascii(text).lower()
    text = re.sub(r"[^a-z0-9%\.\- ]", " ", text)
    tokens = [tok for tok in text.split() if len(tok) > 1 and tok not in STOPWORDS]
    return tokens


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


MULTIMIX_INGREDIENT_RE = re.compile(
    r"^\s*(?P<code>\S+)\s+(?P<name>.+?)\s{2,}"
    r"(?P<avg>[0-9.,]+)\s+(?P<pct>[0-9.,]+)\s+(?P<kilos>[0-9.,]+)\s+"
    r"(?P<tonnes>[0-9.,]+)\s+(?:(?P<lim>MAX|min|MIN|Max)\s+)?"
    r"(?P<min>[0-9.,.]+|[.])\s+(?P<max>[0-9.,.]+|[.])\s*$"
)

MULTIMIX_ANALYSIS_RE = re.compile(
    r"^\s*(?P<name>\[?\s*[A-Za-z0-9_+\-/ ]+\]?)\s+"
    r"(?P<level>[+-]?[0-9.,]+)(?:\s+(?P<flag>min|max|MIN|MAX))?\s+"
    r"(?P<n1>[0-9.,.]+|[.])\s+(?P<n2>[0-9.,.]+|[.])"
)

MULTIMIX_SPEC_RE = re.compile(
    r"Specification:\s*(?P<code>\S+)\s+(?P<name>.+?)\s*:\s*Cost/tonne:\s*(?P<price>[0-9.,]+)",
    flags=re.IGNORECASE,
)


@st.cache_data(show_spinner=False)
def extract_pdf_pages(file_name: str, file_bytes: bytes) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "pages": [],
        "status": "empty",
        "error": None,
    }
    if not file_bytes:
        result["error"] = "El archivo PDF está vacío o no se pudo leer."
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
            "La app seguirá funcionando con los perfiles FEDNA integrados. Para habilitar estos PDFs en despliegue, "
            "instala 'pypdf[crypto]' o 'cryptography'."
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
    raw_first = pd.read_excel(io.BytesIO(file_bytes), sheet_name=first_sheet, header=None)

    if raw_first.shape[1] == 1 and raw_first.iloc[:, 0].astype(str).str.contains("Specification:", na=False).any():
        feeds_df, details = parse_multimix_workbook(raw_first)
        source_format = "multimix_report"
    else:
        feeds_df, details, source_format, parser_warnings = parse_tabular_workbook(file_bytes)
        warnings.extend(parser_warnings)

    if feeds_df.empty:
        raise ValueError("No se pudieron extraer piensos válidos del Excel cargado.")

    numeric_cols = [
        col
        for col in feeds_df.columns
        if col not in {"feed_name", "feed_code", "price", "source_sheet"}
        and pd.api.types.is_numeric_dtype(feeds_df[col])
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



def parse_multimix_workbook(raw_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    lines = raw_df.iloc[:, 0].astype(str).fillna("").tolist()
    spec_indexes = [idx for idx, line in enumerate(lines) if "Specification:" in line]
    if not spec_indexes:
        raise ValueError("El fichero parece un reporte de texto, pero no se localizaron bloques de Specification.")

    records: List[Dict[str, Any]] = []
    details: Dict[str, Any] = {}

    for i, start in enumerate(spec_indexes):
        end = spec_indexes[i + 1] if i + 1 < len(spec_indexes) else len(lines)
        block = lines[start:end]
        spec_match = MULTIMIX_SPEC_RE.search(block[0])
        if not spec_match:
            continue

        raw_name = spec_match.group("name").strip()
        feed_name = make_multimix_feed_name(raw_name)
        record: Dict[str, Any] = {
            "feed_code": spec_match.group("code").strip(),
            "feed_name": feed_name,
            "price": safe_float(spec_match.group("price")),
        }
        feed_details: Dict[str, Any] = {
            "raw_specification": raw_name,
            "ingredients": [],
            "ingredient_limits": {},
            "nutrient_limits": {},
        }

        in_ingredients = False
        in_analysis = False

        for line in block:
            if "INCLUDED RAW MATERIALS" in line:
                in_ingredients = True
                in_analysis = False
                continue
            if line.strip().startswith("ANALYSIS"):
                in_ingredients = False
                in_analysis = True
                continue

            if in_ingredients:
                parsed = parse_multimix_ingredient_line(line)
                if parsed:
                    feed_details["ingredients"].append(parsed)
                    feed_details["ingredient_limits"][parsed["ingredient_name"]] = {
                        "min": parsed["minimum"],
                        "max": parsed["maximum"],
                        "flag": parsed["limit_flag"],
                    }
            elif in_analysis:
                parsed = parse_multimix_analysis_line(line)
                if parsed:
                    nutrient_code = parsed["nutrient"]
                    record[nutrient_code] = parsed["level"]
                    feed_details["nutrient_limits"][nutrient_code] = {
                        "min": parsed["minimum"],
                        "max": parsed["maximum"],
                        "flag": parsed["flag"],
                    }

        records.append(record)
        details[feed_name] = feed_details

    feeds_df = pd.DataFrame(records)
    numeric_cols = [col for col in feeds_df.columns if col not in {"feed_code", "feed_name"}]
    for col in numeric_cols:
        feeds_df[col] = pd.to_numeric(feeds_df[col], errors="coerce")
    feeds_df = feeds_df.sort_values(["feed_name"]).reset_index(drop=True)
    return feeds_df, details



def parse_multimix_ingredient_line(line: str) -> Optional[Dict[str, Any]]:
    match = MULTIMIX_INGREDIENT_RE.match(line)
    if not match:
        return None
    groups = match.groupdict()
    raw_name = groups["name"].strip()
    ingredient_name = raw_name.split(".", 1)[-1].strip() if "." in raw_name else raw_name
    pct = safe_float(groups["pct"])
    if pct is None:
        return None
    return {
        "ingredient_code": groups["code"].strip(),
        "ingredient_raw": raw_name,
        "ingredient_name": ingredient_name,
        "avg_cost": safe_float(groups["avg"]),
        "pct": pct,
        "kilos": safe_float(groups["kilos"]),
        "tonnes": safe_float(groups["tonnes"]),
        "limit_flag": (groups["lim"] or "").strip(),
        "minimum": safe_float(groups["min"]),
        "maximum": safe_float(groups["max"]),
    }



def parse_multimix_analysis_line(line: str) -> Optional[Dict[str, Any]]:
    match = MULTIMIX_ANALYSIS_RE.match(line)
    if not match:
        return None
    groups = match.groupdict()
    level = safe_float(groups["level"])
    if level is None:
        return None
    minimum = safe_float(groups["n1"])
    maximum = safe_float(groups["n2"])
    flag = groups["flag"]

    if minimum is not None and minimum >= 99999:
        minimum = None
    if maximum is not None and maximum >= 99999:
        maximum = None
    if flag is None and minimum in {0.0, 100.0}:
        minimum = None
    if flag is None and maximum in {0.0, 100.0}:
        maximum = None

    nutrient = canonicalize_label(groups["name"].strip("[] "))
    return {
        "nutrient": nutrient,
        "level": level,
        "minimum": minimum,
        "maximum": maximum,
        "flag": flag,
    }



def parse_tabular_workbook(file_bytes: bytes) -> Tuple[pd.DataFrame, Dict[str, Any], str, List[str]]:
    warnings: List[str] = []
    excel = pd.ExcelFile(io.BytesIO(file_bytes))
    best_df: Optional[pd.DataFrame] = None
    best_sheet = excel.sheet_names[0]
    best_score = -1
    best_header_row = 0

    for sheet in excel.sheet_names:
        preview = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet, header=None, nrows=8)
        for header_row in range(min(5, len(preview))):
            try:
                df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet, header=header_row)
            except Exception:
                continue
            cols = [str(c) for c in df.columns]
            score = 0
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

    df = best_df.copy()
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
    df.columns = [str(c).strip() for c in df.columns]

    feed_col = detect_feed_name_column(df.columns)
    price_col = detect_price_column(df.columns)

    if feed_col is None:
        raise ValueError(
            "No se pudo identificar la columna de nombre de pienso en un formato tabular. "
            "Utiliza un encabezado como 'Pienso', 'Nombre pienso', 'Formula' o 'Feed'."
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
        ingredient_limits: Dict[str, Any] = {}
        nutrient_limits: Dict[str, Any] = {}

        for col in df.columns:
            if col in {feed_col, price_col}:
                continue
            value = row.get(col)
            canonical = canonicalize_label(col)
            if col in ingredient_cols:
                pct = safe_float(value)
                if pct is not None and pct != 0:
                    ingredient_name = re.sub(r"^(ING_|INGREDIENT_|INGREDIENTE_)", "", canonicalize_label(col), flags=re.IGNORECASE)
                    ingredient_name = ingredient_name.replace("PCT_", "")
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

        # Reconstrucción simple de límites desde columnas tipo NUTRIENTE_min y NUTRIENTE_max
        for col in df.columns:
            col_norm = normalize_ascii(col).lower().strip()
            if col in {feed_col, price_col}:
                continue
            if col not in limit_cols:
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
            "ingredient_limits": ingredient_limits,
            "nutrient_limits": nutrient_limits,
        }
        records.append(record)

    feeds_df = pd.DataFrame(records)
    numeric_cols = [col for col in feeds_df.columns if col not in {"feed_name", "source_sheet"}]
    for col in numeric_cols:
        feeds_df[col] = pd.to_numeric(feeds_df[col], errors="coerce")

    warnings.append(
        f"Formato tabular detectado en la hoja '{best_sheet}' (fila de encabezado estimada: {best_header_row + 1})."
    )
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
        if uploaded is None:
            continue
        if uploaded.name in seen_names:
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
        enriched_entries.append(
            {
                **entry,
                "species": assigned_species,
                "pages": extraction.get("pages", []),
                "load_status": extraction.get("status", "empty"),
                "load_error": extraction.get("error"),
            }
        )
    return enriched_entries



def infer_species_from_manual_name(file_name: str) -> Optional[str]:
    lowered = normalize_ascii(file_name).lower()
    for species, hints in MANUAL_FILE_HINTS.items():
        if any(hint in lowered for hint in hints):
            return species
    return None



def retrieve_fedna_snippets(manual_entries: List[Dict[str, Any]], species: str, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    relevant_manuals = [m for m in manual_entries if m.get("species") == species]
    if not relevant_manuals:
        return []

    query_tokens = set(tokenize(query))
    if not query_tokens:
        query_tokens = set(tokenize(species))

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
            scored.append(
                (
                    score,
                    {
                        "file_name": manual["file_name"],
                        "page": page["page"],
                        "text": page["text"],
                    },
                )
            )

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

    synonym_pairs = sorted(QUERY_NUTRIENT_SYNONYMS.items(), key=lambda item: len(item[0]), reverse=True)
    for raw_synonym, nutrient_code in synonym_pairs:
        synonym = normalize_ascii(raw_synonym).lower()
        if synonym not in query_norm:
            continue

        range_pattern = re.compile(
            rf"{re.escape(synonym)}\s*(?:entre|between)\s*([0-9.,]+)\s*(?:y|and|a|to|-)\s*([0-9.,]+)",
            flags=re.IGNORECASE,
        )
        comp_pattern = re.compile(
            rf"{re.escape(synonym)}\s*(>=|<=|>|<|=)\s*([0-9.,]+)",
            flags=re.IGNORECASE,
        )
        min_pattern = re.compile(
            rf"(?:minimo|minimo de|mínimo de|al menos|almenos|como minimo|como mínimo)\s*{re.escape(synonym)}\s*([0-9.,]+)",
            flags=re.IGNORECASE,
        )
        max_pattern = re.compile(
            rf"(?:maximo|maximo de|máximo de|como maximo|como máximo|no mas de|no más de|menos de)\s*{re.escape(synonym)}\s*([0-9.,]+)",
            flags=re.IGNORECASE,
        )

        matched = False
        range_match = range_pattern.search(query_norm)
        if range_match:
            low = safe_float(range_match.group(1))
            high = safe_float(range_match.group(2))
            if low is not None and high is not None:
                nutrient_constraints[nutrient_code] = {"kind": "range", "min": min(low, high), "max": max(low, high), "weight": 2.4}
                matched = True
        if matched:
            continue
        comp_match = comp_pattern.search(query_norm)
        if comp_match:
            sign = comp_match.group(1)
            value = safe_float(comp_match.group(2))
            if value is not None:
                if sign in {">", ">="}:
                    nutrient_constraints[nutrient_code] = {"kind": "min", "value": value, "weight": 2.4}
                elif sign in {"<", "<="}:
                    nutrient_constraints[nutrient_code] = {"kind": "max", "value": value, "weight": 2.4}
                else:
                    nutrient_constraints[nutrient_code] = {"kind": "target", "value": value, "tol": max(abs(value) * 0.08, 0.1), "weight": 2.4}
                matched = True
        if matched:
            continue
        min_match = min_pattern.search(query_norm)
        if min_match:
            value = safe_float(min_match.group(1))
            if value is not None:
                nutrient_constraints[nutrient_code] = {"kind": "min", "value": value, "weight": 2.4}
                matched = True
        if matched:
            continue
        max_match = max_pattern.search(query_norm)
        if max_match:
            value = safe_float(max_match.group(1))
            if value is not None:
                nutrient_constraints[nutrient_code] = {"kind": "max", "value": value, "weight": 2.4}

    # Permitir referencias directas al código canónico presente en el Excel.
    for nutrient_code in available_nutrients:
        code_norm = normalize_ascii(nutrient_code).lower()
        comp_match = re.search(rf"{re.escape(code_norm)}\s*(>=|<=|>|<|=)\s*([0-9.,]+)", query_norm)
        if comp_match:
            sign = comp_match.group(1)
            value = safe_float(comp_match.group(2))
            if value is not None:
                if sign in {">", ">="}:
                    nutrient_constraints[nutrient_code] = {"kind": "min", "value": value, "weight": 2.4}
                elif sign in {"<", "<="}:
                    nutrient_constraints[nutrient_code] = {"kind": "max", "value": value, "weight": 2.4}
                else:
                    nutrient_constraints[nutrient_code] = {"kind": "target", "value": value, "tol": max(abs(value) * 0.08, 0.1), "weight": 2.4}

    price_max = None
    price_match = re.search(r"(?:precio|coste|costo|cost|eur|€)\s*(?:maximo|maximo de|máximo de|<|<=|hasta|tope)?\s*([0-9.,]+)", query_norm)
    if price_match:
        price_max = safe_float(price_match.group(1))

    prefer_low_price = any(keyword in query_norm for keyword in ["barato", "economico", "económico", "menor precio", "mas barato", "más barato"])

    include_ingredients = extract_ingredient_terms(query_norm, mode="include")
    exclude_ingredients = extract_ingredient_terms(query_norm, mode="exclude")

    return {
        "nutrient_constraints": nutrient_constraints,
        "price_max": price_max,
        "prefer_low_price": prefer_low_price,
        "include_ingredients": include_ingredients,
        "exclude_ingredients": exclude_ingredients,
    }



def extract_ingredient_terms(query_norm: str, mode: str = "include") -> List[str]:
    if mode == "exclude":
        patterns = [r"sin\s+([a-z0-9_\- ]+)", r"evitar\s+([a-z0-9_\- ]+)", r"excluir\s+([a-z0-9_\- ]+)"]
    else:
        patterns = [r"con\s+([a-z0-9_\- ]+)", r"incluir\s+([a-z0-9_\- ]+)", r"rico en\s+([a-z0-9_\- ]+)"]

    terms: List[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, query_norm):
            fragment = match.group(1).strip()
            fragment = re.split(r"[,.;]|\s+que\s+|\s+para\s+|\s+y\s+|\s+o\s+", fragment)[0].strip()
            if len(fragment) >= 3:
                terms.append(fragment)
    return list(dict.fromkeys(terms))



def merge_requirements(
    profile: Dict[str, Any],
    query_constraints: Dict[str, Any],
    selected_nutrients: List[str],
    available_nutrients: List[str],
) -> Dict[str, Dict[str, Any]]:
    available_set = set(available_nutrients)
    selected_set = set(selected_nutrients)

    merged = {nutrient: rule.copy() for nutrient, rule in profile.get("requirements", {}).items() if nutrient in available_set}

    if selected_set:
        merged = {nutrient: rule for nutrient, rule in merged.items() if nutrient in selected_set}

    for nutrient, rule in query_constraints.get("nutrient_constraints", {}).items():
        if nutrient in available_set:
            merged[nutrient] = rule.copy()

    return merged



def ingredient_set_for_feed(details: Dict[str, Any], feed_name: str) -> List[str]:
    ingredients = details.get(feed_name, {}).get("ingredients", [])
    return [normalize_ascii(item.get("ingredient_name", "")).lower() for item in ingredients]



def apply_query_filters(
    feeds_df: pd.DataFrame,
    details: Dict[str, Any],
    query_constraints: Dict[str, Any],
) -> Tuple[pd.DataFrame, List[str]]:
    filtered = feeds_df.copy()
    notes: List[str] = []

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

    return filtered, notes



def score_rule(value: Any, rule: Dict[str, Any]) -> float:
    numeric_value = safe_float(value)
    if numeric_value is None:
        return 0.0
    kind = rule.get("kind")
    if kind == "min":
        ref = max(abs(rule["value"]), 1e-6)
        if numeric_value >= rule["value"]:
            return 1.0
        return max(0.0, 1.0 - ((rule["value"] - numeric_value) / ref))
    if kind == "max":
        ref = max(abs(rule["value"]), 1e-6)
        if numeric_value <= rule["value"]:
            return 1.0
        return max(0.0, 1.0 - ((numeric_value - rule["value"]) / ref))
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
    return "n/d"



def rank_feeds(
    feeds_df: pd.DataFrame,
    requirements: Dict[str, Dict[str, Any]],
    selected_nutrients: List[str],
    top_n: int,
    prefer_low_price: bool,
) -> Tuple[pd.DataFrame, Dict[str, Any], List[str]]:
    ranking_rows: List[Dict[str, Any]] = []
    score_details: Dict[str, Any] = {}
    notes: List[str] = []

    nutrients_in_scope = list(requirements.keys())
    if not nutrients_in_scope:
        nutrients_in_scope = [n for n in selected_nutrients if n in feeds_df.columns]
        for nutrient in nutrients_in_scope:
            series = pd.to_numeric(feeds_df[nutrient], errors="coerce")
            target = series.median(skipna=True)
            if pd.notna(target):
                requirements[nutrient] = {
                    "kind": "target",
                    "value": float(target),
                    "tol": max(abs(float(target)) * 0.12, 0.1),
                    "weight": 1.0,
                }
        if nutrients_in_scope:
            notes.append("No había un perfil FEDNA directamente utilizable para todos los nutrientes elegidos; se ha usado como referencia el centro de la distribución del Excel para los nutrientes seleccionados.")

    if not requirements:
        raise ValueError("No se pudo construir una base de ranking con los nutrientes seleccionados y los datos disponibles.")

    price_series = pd.to_numeric(feeds_df.get("price"), errors="coerce") if "price" in feeds_df.columns else pd.Series(dtype=float)
    min_price = price_series.min(skipna=True) if not price_series.empty else np.nan
    max_price = price_series.max(skipna=True) if not price_series.empty else np.nan

    for _, row in feeds_df.iterrows():
        total_weight = 0.0
        total_score = 0.0
        nutrient_breakdown: List[Dict[str, Any]] = []
        hard_failures = 0

        for nutrient, rule in requirements.items():
            if nutrient not in feeds_df.columns:
                continue
            weight = float(rule.get("weight", 1.0))
            score = score_rule(row.get(nutrient), rule)
            total_weight += weight
            total_score += score * weight
            if score < 0.5:
                hard_failures += 1
            nutrient_breakdown.append(
                {
                    "nutrient": nutrient,
                    "label": nutrient_label(nutrient),
                    "value": row.get(nutrient),
                    "requirement": describe_rule(rule),
                    "score": round(score * 100, 1),
                }
            )

        aptitude = 0.0 if total_weight == 0 else 100.0 * total_score / total_weight
        if hard_failures >= max(2, math.ceil(len(requirements) * 0.4)):
            aptitude *= 0.85

        price_bonus = 0.0
        price_value = safe_float(row.get("price"))
        if prefer_low_price and price_value is not None and pd.notna(min_price) and pd.notna(max_price) and max_price > min_price:
            price_bonus = 8.0 * (1.0 - ((price_value - min_price) / (max_price - min_price)))
            aptitude += price_bonus

        ranking_row = {
            "Pienso": row.get("feed_name"),
            "Precio": price_value,
            "Aptitud": round(float(aptitude), 2),
        }
        for nutrient in selected_nutrients:
            if nutrient in feeds_df.columns:
                ranking_row[nutrient_label(nutrient)] = row.get(nutrient)
        ranking_rows.append(ranking_row)
        score_details[row.get("feed_name")] = {
            "nutrient_breakdown": nutrient_breakdown,
            "price_bonus": round(price_bonus, 2),
            "aptitude": round(float(aptitude), 2),
        }

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



def create_comparison_table(
    feed_name: str,
    feeds_df: pd.DataFrame,
    requirements: Dict[str, Dict[str, Any]],
    score_details: Dict[str, Any],
) -> pd.DataFrame:
    row = feeds_df[feeds_df["feed_name"] == feed_name]
    if row.empty:
        return pd.DataFrame()
    row = row.iloc[0]
    breakdown = score_details.get(feed_name, {}).get("nutrient_breakdown", [])
    comparison_rows = []
    for item in breakdown:
        comparison_rows.append(
            {
                "Nutriente": item["label"],
                "Valor del pienso": row.get(item["nutrient"]),
                "Requerimiento": item["requirement"],
                "Score nutriente (%)": item["score"],
            }
        )
    return pd.DataFrame(comparison_rows)



def summarise_feed_reason(feed_name: str, score_details: Dict[str, Any]) -> str:
    breakdown = score_details.get(feed_name, {}).get("nutrient_breakdown", [])
    if not breakdown:
        return "Sin desglose disponible."
    breakdown_sorted = sorted(breakdown, key=lambda item: item["score"], reverse=True)
    strongest = breakdown_sorted[:3]
    weakest = [item for item in breakdown_sorted if item["score"] < 70][:2]
    strong_text = ", ".join(f"{item['label']} ({item['score']:.0f}%)" for item in strongest)
    weak_text = ", ".join(f"{item['label']} ({item['score']:.0f}%)" for item in weakest)
    if weak_text:
        return f"Fortalezas: {strong_text}. Puntos a vigilar: {weak_text}."
    return f"Buen ajuste en: {strong_text}."



def truncate_text(text: str, max_len: int = 340) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."



def generate_assistant_answer(
    species: str,
    query: str,
    profile: Dict[str, Any],
    ranking_df: pd.DataFrame,
    score_details: Dict[str, Any],
    fedna_snippets: List[Dict[str, Any]],
    applied_filters: List[str],
    ranking_notes: List[str],
    selected_nutrients: List[str],
) -> str:
    lines: List[str] = []
    lines.append(f"Perfil FEDNA activo: **{profile.get('name', 'General')}**.")
    if profile.get("source_note"):
        lines.append(profile["source_note"])
    if selected_nutrients:
        lines.append("El ranking se ha calculado con estos nutrientes en foco: " + ", ".join(nutrient_label(n) for n in selected_nutrients) + ".")
    if applied_filters:
        lines.extend(f"- {note}" for note in applied_filters)
    if ranking_notes:
        lines.extend(f"- {note}" for note in ranking_notes)

    if ranking_df.empty:
        lines.append("No se han encontrado piensos tras aplicar los filtros actuales.")
        return "\n".join(lines)

    top_rows = ranking_df.head(min(3, len(ranking_df)))
    lines.append("**Top recomendaciones:**")
    for idx, row in top_rows.iterrows():
        reason = summarise_feed_reason(row["Pienso"], score_details)
        price_text = "n/d" if pd.isna(row.get("Precio")) else f"{row['Precio']:.3f}"
        lines.append(f"{idx + 1}. **{row['Pienso']}** — aptitud {row['Aptitud']:.2f} / 100; precio {price_text}. {reason}")

    if fedna_snippets:
        lines.append("**Fragmentos FEDNA recuperados para contextualizar la consulta:**")
        for snippet in fedna_snippets[:3]:
            excerpt = truncate_text(snippet["text"], max_len=320)
            lines.append(f"- {snippet['file_name']} · p. {snippet['page']}: {excerpt}")

    if query.strip():
        lines.append(f"Consulta interpretada: _{query.strip()}_.")

    return "\n".join(lines)



def generate_summary_report(
    species: str,
    query: str,
    profile: Dict[str, Any],
    ranking_df: pd.DataFrame,
    score_details: Dict[str, Any],
    selected_nutrients: List[str],
    warnings: List[str],
    source_format: str,
) -> str:
    lines = []
    lines.append("# Informe resumen")
    lines.append("")
    lines.append(f"**Especie/categoría:** {species}")
    lines.append(f"**Consulta:** {query or 'Ranking base con el perfil por defecto'}")
    lines.append(f"**Perfil FEDNA activo:** {profile.get('name', 'General')}")
    lines.append(f"**Formato detectado del Excel:** {source_format}")
    if selected_nutrients:
        lines.append("**Nutrientes utilizados en el ranking:** " + ", ".join(nutrient_label(n) for n in selected_nutrients))
    lines.append("")
    lines.append("## Resultados")
    if ranking_df.empty:
        lines.append("No se obtuvieron resultados con los filtros actuales.")
    else:
        for idx, row in ranking_df.iterrows():
            lines.append(f"{idx + 1}. {row['Pienso']} — aptitud {row['Aptitud']:.2f} / 100; precio {row['Precio'] if pd.notna(row['Precio']) else 'n/d'}.")
            lines.append(f"   - {summarise_feed_reason(row['Pienso'], score_details)}")
    lines.append("")
    lines.append("## Recomendación final")
    if not ranking_df.empty:
        best = ranking_df.iloc[0]
        lines.append(
            f"El pienso recomendado es **{best['Pienso']}** porque alcanza la mayor aptitud global con el perfil seleccionado. "
            f"La decisión está basada en el ajuste nutricional frente al perfil FEDNA activo y, cuando procede, en el coste como criterio de desempate."
        )
    else:
        lines.append("No es posible recomendar un pienso con la información y los filtros actuales.")
    lines.append("")
    lines.append("## Supuestos y limitaciones")
    lines.append("- El ranking usa un perfil FEDNA representativo por categoría; no sustituye el ajuste fino por fase, edad, genética, estado sanitario o manejo.")
    lines.append("- Si el Excel no contiene todos los nutrientes del perfil, el algoritmo trabaja con la intersección disponible.")
    lines.append("- Las fórmulas de aptitud son deterministas y explicables; no usan un LLM externo.")
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines)



def default_selected_nutrients(species: str, available_nutrients: List[str], limit: int) -> List[str]:
    profile = FEDNA_PROFILES.get(species, [{}])[0]
    preferred = [n for n in profile.get("requirements", {}).keys() if n in available_nutrients]
    if preferred:
        return preferred[:limit]
    return available_nutrients[:limit]



def render_feed_detail(
    selected_feed_name: str,
    feeds_df: pd.DataFrame,
    details: Dict[str, Any],
    requirements: Dict[str, Dict[str, Any]],
    score_details: Dict[str, Any],
) -> None:
    st.subheader(f"Detalle de {selected_feed_name}")
    feed_row = feeds_df[feeds_df["feed_name"] == selected_feed_name]
    if feed_row.empty:
        st.info("No hay datos detallados para este pienso.")
        return

    feed_row = feed_row.iloc[0]
    col1, col2 = st.columns([1.25, 1])
    with col1:
        ingredients = details.get(selected_feed_name, {}).get("ingredients", [])
        if ingredients:
            ing_df = pd.DataFrame(ingredients)
            ing_df = ing_df[[col for col in ["ingredient_name", "pct", "minimum", "maximum", "limit_flag"] if col in ing_df.columns]]
            ing_df = ing_df.rename(
                columns={
                    "ingredient_name": "Ingrediente",
                    "pct": "% inclusión",
                    "minimum": "Mínimo",
                    "maximum": "Máximo",
                    "limit_flag": "Tipo límite",
                }
            )
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
        limit_rows = []
        for nutrient, values in nutrient_limits.items():
            if values.get("min") is None and values.get("max") is None and not values.get("flag"):
                continue
            limit_rows.append(
                {
                    "Nutriente": nutrient_label(nutrient),
                    "Mínimo fórmula": values.get("min"),
                    "Máximo fórmula": values.get("max"),
                    "Bandera": values.get("flag"),
                }
            )
        if limit_rows:
            with st.expander("Límites internos de la fórmula"):
                st.dataframe(pd.DataFrame(limit_rows), use_container_width=True, hide_index=True)



def render_manual_status(manual_entries: List[Dict[str, Any]], species: str) -> None:
    relevant = [m for m in manual_entries if m.get("species") == species and m.get("load_status") == "ok"]
    if relevant:
        st.success(
            "Manuales FEDNA listos para esta categoría: "
            + ", ".join(f"{m['file_name']} ({m['origin']})" for m in relevant)
        )
    else:
        st.info(
            "No hay un PDF FEDNA utilizable para esta categoría. La app seguirá funcionando con perfiles FEDNA integrados, "
            "pero sin recuperación de fragmentos del manual. Esto no bloquea ni el chat ni el ranking."
        )

    failed = [m for m in manual_entries if m.get("load_status") in {"empty", "error"}]
    if failed:
        with st.expander("Ver incidencias de carga de PDF"):
            for item in failed:
                st.warning(f"{item['file_name']}: {item.get('load_error') or 'No se pudo procesar el archivo.'}")



def get_query_suggestions(species: str, selected_nutrients: List[str]) -> List[str]:
    highlighted = ", ".join(nutrient_label(code) for code in selected_nutrients[:3])
    if not highlighted:
        highlighted = "energía, proteína y aminoácidos clave"

    species_specific = {
        "Porcino": [
            "Quiero el top 5 para porcino de crecimiento-cebo, priorizando lisina, energía neta y proteína bruta, con el menor precio posible.",
            "Busca un pienso de porcino con lisina >= 1.00, calcio entre 0.65 y 0.85 y que evite trigo si aparece en la fórmula.",
            "Dame una recomendación para cerdas en gestación, explicando qué pienso se ajusta mejor y por qué.",
        ],
        "Avicultura": [
            "Quiero el top 3 para pollos de carne, priorizando EMAn, lisina y metionina+cistina, y explica el criterio usado.",
            "Busca una opción avícola con calcio dentro de rango y proteína suficiente, priorizando la alternativa más económica.",
            "Compara los mejores piensos avícolas con foco en energía, lisina y treonina, y resume cuál elegirías.",
        ],
        "Rumiantes de carne": [
            "Quiero el top 5 para terneros de cebo, priorizando proteína bruta, FND y energía, con explicación breve de aptitud.",
            "Busca un pienso para corderos de cebo con FND en rango y almidón moderado, y dime cuál encaja mejor.",
            "Compara las mejores fórmulas para rumiantes de carne dando peso a proteína, FND y calcio.",
        ],
        "Rumiantes de leche": [
            "Busca el mejor pienso para lactación intensiva, priorizando proteína bruta, FND y UFL/UFC, y resume la recomendación final.",
            "Quiero una opción para vacas secas o preparto con calcio y fósforo dentro de rango y fibra suficiente.",
            "Dame el top 4 para rumiantes de leche priorizando fibra, proteína y equilibrio mineral.",
        ],
        "Reposición de rumiantes": [
            "Quiero el top 5 para recría, priorizando proteína bruta, energía y calcio, con un resumen claro del mejor pienso.",
            "Busca una fórmula de reposición con proteína suficiente y fibra moderada, evitando exceso de grasa.",
            "Compara los mejores piensos de recría usando como criterio principal energía, proteína y fósforo.",
        ],
    }

    generic = [
        f"Dame una recomendación para {species.lower()} usando sobre todo {highlighted}.",
        "Quiero una alternativa barata pero técnicamente correcta, con una explicación de los compromisos nutricionales.",
        "Muéstrame el ranking y después explica en detalle el mejor pienso seleccionado.",
    ]
    return species_specific.get(species, []) + generic



def reset_search_state(clear_query: bool = True) -> None:
    st.session_state["chat_history"] = []
    st.session_state["last_result"] = None
    st.session_state["last_query"] = ""
    st.session_state["selected_feed_name"] = None
    if clear_query:
        st.session_state["query_draft"] = ""



def run_recommendation(
    species: str,
    query: str,
    parsed_excel: Dict[str, Any],
    manual_entries: List[Dict[str, Any]],
    selected_nutrients: List[str],
    top_n: int,
) -> Dict[str, Any]:
    feeds_df = parsed_excel["feeds_df"]
    available_nutrients = parsed_excel["numeric_nutrients"]
    details = parsed_excel["details"]

    profile = choose_fedna_profile(species, query)
    query_constraints = parse_query_constraints(query, available_nutrients)
    filtered_df, applied_filters = apply_query_filters(feeds_df, details, query_constraints)
    requirements = merge_requirements(profile, query_constraints, selected_nutrients, available_nutrients)

    ranking_df, score_details, ranking_notes = rank_feeds(
        filtered_df,
        requirements=requirements,
        selected_nutrients=selected_nutrients,
        top_n=top_n,
        prefer_low_price=query_constraints.get("prefer_low_price", False),
    )
    fedna_snippets = retrieve_fedna_snippets(manual_entries, species, query, top_k=3)
    assistant_answer = generate_assistant_answer(
        species=species,
        query=query,
        profile=profile,
        ranking_df=ranking_df,
        score_details=score_details,
        fedna_snippets=fedna_snippets,
        applied_filters=applied_filters,
        ranking_notes=ranking_notes,
        selected_nutrients=selected_nutrients,
    )
    summary_report = generate_summary_report(
        species=species,
        query=query,
        profile=profile,
        ranking_df=ranking_df,
        score_details=score_details,
        selected_nutrients=selected_nutrients,
        warnings=parsed_excel["warnings"],
        source_format=parsed_excel["source_format"],
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
    }



def init_session_state() -> None:
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("query_draft", "")
    st.session_state.setdefault("last_query", "")
    st.session_state.setdefault("selected_feed_name", None)



def main() -> None:
    init_session_state()

    st.title("FEDNA Feed Recommender")
    st.caption(
        "Aplicación Streamlit para relacionar manuales FEDNA con formulaciones de pienso y ordenar los piensos por aptitud nutricional."
    )

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
        st.info(
            "Carga un Excel para empezar. La app soporta tanto un formato tabular clásico (una fila por pienso) como reportes de formulación tipo Multi-Mix con bloques de Specification / Included Raw Materials / Analysis."
        )
        st.markdown(
            "**Sugerencia de uso:** selecciona la categoría, sube el Excel, define los nutrientes a considerar y utiliza la consulta editable para lanzar búsquedas como `quiero un pienso de crecimiento con lisina > 1.0 y precio < 320`."
        )
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

    nutrient_limit = st.number_input(
        "Número máximo de nutrientes a seleccionar",
        min_value=1,
        max_value=max(1, len(available_nutrients)),
        value=min(8, max(1, len(available_nutrients))),
        step=1,
    )
    default_nutrients = default_selected_nutrients(species, available_nutrients, int(nutrient_limit))
    selected_nutrients = st.multiselect(
        "Nutrientes utilizados en el cálculo / búsqueda",
        options=available_nutrients,
        default=default_nutrients,
        format_func=nutrient_label,
        max_selections=int(nutrient_limit),
    )

    st.subheader("Consulta y chat")
    st.caption(
        "El cuadro de consulta es editable y permanece visible. Puedes cargar una propuesta, modificarla, refrescar la búsqueda actual o limpiar el estado para empezar otra nueva."
    )

    suggestions = get_query_suggestions(species, selected_nutrients)
    with st.container(border=True):
        st.markdown("**1) Elige una propuesta editable**")
        chosen_template = st.radio(
            "Propuestas de consulta",
            options=suggestions,
            index=0 if suggestions else None,
            help="Selecciona una propuesta y pulsa 'Usar propuesta'. Después puedes editarla libremente.",
            label_visibility="visible",
        )
        proposal_col, helper_col = st.columns([1, 2])
        if proposal_col.button("Usar propuesta", use_container_width=True):
            st.session_state["query_draft"] = chosen_template or ""
            st.rerun()
        helper_col.info("Estas propuestas sirven como punto de partida. El texto final siempre se edita en el cuadro inferior.")

        st.markdown("**2) Escribe o edita tu consulta**")
        st.text_area(
            "Chat / consulta editable",
            key="query_draft",
            height=180,
            placeholder=(
                "Ejemplo: Quiero el top 5 para porcino en crecimiento-cebo, priorizando lisina, energía neta y proteína bruta, "
                "con el menor precio posible y evitando trigo si aparece en la fórmula."
            ),
        )

    action_col1, action_col2, action_col3, action_col4 = st.columns(4)
    run_query = action_col1.button("Buscar y rankear", type="primary", use_container_width=True)
    refresh_query = action_col2.button(
        "Refrescar resultados",
        use_container_width=True,
        disabled=not bool(st.session_state.get("query_draft", "").strip() or st.session_state.get("last_query", "").strip()),
    )
    run_base = action_col3.button("Ranking base FEDNA", use_container_width=True)
    new_search = action_col4.button("Nueva búsqueda", use_container_width=True)

    if new_search:
        reset_search_state(clear_query=True)
        st.rerun()

    active_query = st.session_state.get("query_draft", "").strip()
    if refresh_query and not active_query:
        active_query = st.session_state.get("last_query", "").strip()
        st.session_state["query_draft"] = active_query

    if run_base:
        try:
            result = run_recommendation(
                species=species,
                query="",
                parsed_excel=parsed_excel,
                manual_entries=manual_entries,
                selected_nutrients=selected_nutrients,
                top_n=top_n,
            )
            st.session_state["last_result"] = result
            st.session_state["last_query"] = ""
            base_message = "Ranking base ejecutado con el perfil FEDNA por defecto de la categoría seleccionada."
            st.session_state["chat_history"].append({"role": "assistant", "content": base_message + "\n\n" + result["assistant_answer"]})
        except Exception as exc:
            st.error(f"No se pudo ejecutar el ranking base: {exc}")

    if run_query or refresh_query:
        if not active_query:
            st.warning("Escribe o carga una consulta editable antes de buscar.")
        else:
            st.session_state["chat_history"].append({"role": "user", "content": active_query})
            try:
                result = run_recommendation(
                    species=species,
                    query=active_query,
                    parsed_excel=parsed_excel,
                    manual_entries=manual_entries,
                    selected_nutrients=selected_nutrients,
                    top_n=top_n,
                )
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
    selected_feed_name = st.selectbox(
        "Selecciona un pienso para ver el detalle",
        options=ranking_options,
        index=ranking_options.index(default_feed),
        key="selected_feed_name",
    )
    render_feed_detail(
        selected_feed_name=selected_feed_name,
        feeds_df=feeds_df,
        details=details,
        requirements=last_result["requirements"],
        score_details=last_result["score_details"],
    )

    st.divider()
    st.subheader("Informe resumen final")
    st.markdown(last_result["summary_report"])
    st.download_button(
        label="Descargar informe resumen (.md)",
        data=last_result["summary_report"].encode("utf-8"),
        file_name="informe_resumen_fedna.md",
        mime="text/markdown",
    )

    fedna_snippets = last_result.get("fedna_snippets", [])
    if fedna_snippets:
        with st.expander("Fragmentos FEDNA recuperados"):
            for snippet in fedna_snippets:
                st.markdown(f"**{snippet['file_name']} · página {snippet['page']}**")
                st.write(truncate_text(snippet["text"], 900))


if __name__ == "__main__":
    main()
