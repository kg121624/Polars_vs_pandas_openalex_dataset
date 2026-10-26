# %%
"""
Modul wspolny dla wszystkich skryptow warsztatu.

Zawiera WYLACZNIE elementy infrastrukturalne:
- wczytywanie konfiguracji YAML (KEYWORDS, TOPIC_CONTEXT_TERMS, RESEARCH_TOPIC),
- wczytywanie zmiennych srodowiskowych (.env),
- sciezki projektu i znaczniki czasu,
- zapis wynikow analizy do Excela (XLSX) i CSV.

Nie zawiera logiki analitycznej - ta jest celowo napisana trzy razy
(Polars / Pandas / SQL), aby pokazac roznice w skladni.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# --- Sciezki projektu -------------------------------------------------------
ROOT: Path = Path(__file__).resolve().parents[1]
CONFIG_DIR: Path = ROOT / "config"
DATA_DIR: Path = ROOT / "data"
REPORTS_DIR: Path = ROOT / "reports"
FIGURES_DIR: Path = REPORTS_DIR / "figures"
DEFAULT_CONFIG: Path = CONFIG_DIR / "topic.yaml"

RESULT_COLUMNS: list[str] = ["id", "pytanie", "szczegol", "wartosc", "typ_danych"]


# --- Konfiguracja i srodowisko ---------------------------------------------
def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Wczytuje plik YAML z tematem, slowami kluczowymi i terminami kontekstu."""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG
    with config_path.open(encoding="utf-8") as handle:
        config: dict[str, Any] = yaml.safe_load(handle) or {}
    config["_config_path"] = str(config_path)
    config["_config_stem"] = config_path.stem
    return config


def load_environment() -> None:
    """Wczytuje plik .env (OPENALEX_API_KEY) do zmiennych srodowiskowych."""
    load_dotenv(ROOT / ".env")


def ensure_dirs() -> None:
    for directory in (DATA_DIR, REPORTS_DIR, FIGURES_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def timestamp() -> str:
    """Znacznik czasu w formacie sortowalnym leksykograficznie: YYYYMMDD_HHMMSS."""
    return time.strftime("%Y%m%d_%H%M%S")


# --- Lokalizowanie plikow ---------------------------------------------------
def latest_dataset(config_stem: str = "topic") -> Path:
    """Zwraca najnowszy plik CSV z datasetem dla danego pliku konfiguracyjnego."""
    ensure_dirs()
    candidates = sorted(DATA_DIR.glob(f"works_{config_stem}_*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"Brak datasetu dla konfiguracji '{config_stem}' w {DATA_DIR}. "
            "Uruchom najpierw scripts/01_fetch_openalex.py."
        )
    return candidates[-1]


def latest_results(method: str) -> Path:
    """Zwraca najnowszy plik wynikow (xlsx) dla danej metody: polars/pandas/sql."""
    ensure_dirs()
    candidates = sorted(REPORTS_DIR.glob(f"wyniki_{method}_*.xlsx"))
    if not candidates:
        raise FileNotFoundError(
            f"Brak wynikow dla metody '{method}'. "
            f"Uruchom najpierw skrypt analityczny dla {method}."
        )
    return candidates[-1]


# --- Zapis wynikow ----------------------------------------------------------
def save_results(
    rows: list[dict[str, Any]],
    method: str,
    elapsed_seconds: float,
    dataset_path: str | Path,
    config: dict[str, Any],
) -> Path:
    """Zapisuje wyniki analizy (format tidy) oraz metadane do Excela i CSV.

    Zwraca sciezke pliku XLSX. Obok niego powstaja dwa pliki CSV o tej samej
    nazwie (``wyniki_<metoda>_<stamp>.csv`` i ``meta_<metoda>_<stamp>.csv``),
    aby wyniki mozna bylo otworzyc bez LibreOffice czy Excela.
    """
    import pandas as pd

    ensure_dirs()
    stamp = timestamp()
    out_path = REPORTS_DIR / f"wyniki_{method}_{stamp}.xlsx"

    results_df = pd.DataFrame(rows, columns=RESULT_COLUMNS)
    meta_df = pd.DataFrame(
        [
            {
                "metoda": method,
                "dataset": str(dataset_path),
                "plik_konfiguracji": config.get("_config_stem", ""),
                "temat_badawczy": config.get("research_topic", ""),
                "liczba_rekordow_wejsciowych": len(results_df),
                "czas_wykonania_s": round(elapsed_seconds, 4),
                "zapisano": stamp,
            }
        ]
    )

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        results_df.to_excel(writer, sheet_name="wyniki", index=False)
        meta_df.to_excel(writer, sheet_name="meta", index=False)

    # CSV z BOM (utf-8-sig), aby polskie znaki byly czytelne w Excelu/arkuszach.
    results_df.to_csv(
        REPORTS_DIR / f"wyniki_{method}_{stamp}.csv", index=False, encoding="utf-8-sig"
    )
    meta_df.to_csv(
        REPORTS_DIR / f"meta_{method}_{stamp}.csv", index=False, encoding="utf-8-sig"
    )

    return out_path
