# %%
"""
KROK 1 - Pobranie danych z OpenAlex.

Roznice wzgledem skryptu referencyjnego (Gap_Reaserch_Agents/openalex_search.py):
  1. KEYWORDS, TOPIC_CONTEXT_TERMS i RESEARCH_TOPIC sa w osobnym pliku YAML
     (config/topic.yaml) - studenci zmieniaja temat bez dotykania kodu.
  2. Wynik zapisywany jest do CSV (a nie JSON), w formacie plaskim (tidy),
     gotowym do wczytania przez Polars / Pandas / SQL.

Zapytanie jest deterministyczne: (KEYWORDS) AND (TOPIC_CONTEXT_TERMS),
z posortowanymi frazami i cache'owaniem odpowiedzi API.
"""

# %% Importy i sciezki
from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

sys.path.append(str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    CONFIG_DIR,
    DATA_DIR,
    ROOT,
    ensure_dirs,
    latest_dataset,
    load_config,
    load_environment,
    timestamp,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("OpenAlexFetch")

OPENALEX_API: str = "https://api.openalex.org/works"
USER_AGENT: str = "OpenAlexWorkshop/1.0 (+mailto:research@example.edu)"
MAX_RETRIES: int = 5
RETRY_BACKOFF: float = 2.0
CACHE_DIR: Path = ROOT / ".cache"

# Kolumny pliku wyjsciowego - plaski schemat pod analize w trzech bibliotekach.
CSV_COLUMNS: list[str] = [
    "id",
    "doi",
    "title",
    "publication_year",
    "publication_date",
    "type",
    "language",
    "cited_by_count",
    "referenced_works_count",
    "fwci",
    "is_open_access",
    "source_name",
    "host_organization_name",
    "n_authors",
    "first_author_name",
    "author_names",
    "institution_names",
    "keywords",
    "concepts",
    "abstract_text",
]


# %% Budowa zapytania na podstawie konfiguracji YAML
def build_deterministic_query(keywords: list[str], context_terms: list[str]) -> str:
    """Sklada czesc wyszukiwania (A) AND (B); kolejnosc fraz ustalona deterministycznie."""
    def join_sorted(terms: list[str]) -> str:
        ordered = sorted(terms, key=lambda term: (len(term), term.lower()))
        return " OR ".join(f'"{term}"' for term in ordered)

    return f"({join_sorted(keywords)}) AND ({join_sorted(context_terms)})"


def build_filter(search_field: str, boolean_query: str, extra_filters: list[str]) -> str:
    """Sklada parametr 'filter' OpenAlex: pole wyszukiwania + filtry dodatkowe (AND)."""
    parts = [f"{search_field}.search:{boolean_query}", *extra_filters]
    return ",".join(part for part in parts if part)


def query_signature(query: str, per_page: int, mail_to: str) -> str:
    payload = f"{query}|{per_page}|{mail_to}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]


# %% Cache zapytan (zapewnia powtarzalnosc i oszczedza limity API)
def cache_path_for(sig: str, batch: int) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"openalex_{sig}_c{batch:04d}.json"


def load_cache(sig: str, batch: int) -> dict[str, Any] | None:
    file_path = cache_path_for(sig, batch)
    if file_path.exists():
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("Uszkodzony cache %s: %s", file_path, exc)
    return None


def save_cache(sig: str, batch: int, data: dict[str, Any]) -> None:
    cache_path_for(sig, batch).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# %% Pobieranie pojedynczej partii z retry (paginacja kursorowa)
def fetch_batch(
    filter_query: str,
    cursor: str,
    batch: int,
    per_page: int,
    mail_to: str,
    api_key: str | None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Pobiera partie wynikow.

    Uzywamy paginacji KURSOROWEJ (parametr 'cursor'), a nie 'page'. Powod:
    przy glebokim stronicowaniu 'page' OpenAlex zwraca ok. 1% duplikatow
    (niestabilny podzial wynikow). Kursor gwarantuje unikalne rekordy.
    """
    sig = query_signature(filter_query, per_page, mail_to)
    if use_cache:
        cached = load_cache(sig, batch)
        if cached is not None:
            logger.info("Cache HIT dla partii %d (sig=%s)", batch, sig)
            return cached

    params: dict[str, Any] = {
        "filter": filter_query,
        "per_page": per_page,
        "cursor": cursor,
        "mailto": mail_to,
    }
    if api_key:
        params["api_key"] = api_key
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(OPENALEX_API, params=params, headers=headers, timeout=60)
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = RETRY_BACKOFF**attempt
                logger.warning(
                    "HTTP %d - ponawiam %d/%d za %.1fs...",
                    resp.status_code,
                    attempt,
                    MAX_RETRIES,
                    wait,
                )
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            save_cache(sig, batch, data)
            logger.info("Pobrano partie %d (status=%d, sig=%s)", batch, resp.status_code, sig)
            return data
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            wait = RETRY_BACKOFF**attempt
            logger.warning(
                "Blad zadania (%d/%d): %s - ponawiam za %.1fs...",
                attempt,
                MAX_RETRIES,
                exc,
                wait,
            )
            time.sleep(wait)
    raise RuntimeError(f"OpenAlex nie odpowiedzial po {MAX_RETRIES} probach: {last_exc}")


# %% Walidacja i ekstrakcja rekordu
def inverted_index_to_text(index: dict[str, list[int]] | None) -> str | None:
    """Zamienia abstract_inverted_index na zwykly tekst."""
    if not index:
        return None
    positions: list[tuple[int, str]] = []
    for word, pos_list in index.items():
        positions.extend((int(pos), word) for pos in pos_list)
    positions.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positions)


def validate_work(work: dict[str, Any]) -> tuple[bool, list[str]]:
    """Minimalna walidacja - chroni kolejne kroki przed brakami w danych."""
    errors: list[str] = []
    if not isinstance(work, dict):
        return False, ["rekord nie jest slownikiem"]
    if not work.get("id"):
        errors.append("brak 'id'")
    if not work.get("title"):
        errors.append("brak 'title'")
    if not isinstance(work.get("authorships"), list):
        errors.append("brak 'authorships'")
    year = work.get("publication_year")
    if year is not None and not isinstance(year, int):
        errors.append("'publication_year' nie jest liczba calkowita")
    return len(errors) == 0, errors


def extract_row(work: dict[str, Any]) -> dict[str, Any]:
    """Spłaszcza rekord OpenAlex do wiersza CSV."""
    primary_location = work.get("primary_location") or {}
    source = (primary_location or {}).get("source") or {}
    open_access = work.get("open_access") or {}
    authorships = work.get("authorships") or []

    author_names = [
        (a.get("author") or {}).get("display_name")
        for a in authorships
        if (a.get("author") or {}).get("display_name")
    ]
    institutions: list[str] = []
    for authorship in authorships:
        for inst in authorship.get("institutions") or []:
            name = inst.get("display_name")
            if name and name not in institutions:
                institutions.append(name)

    keywords = [
        kw.get("display_name")
        for kw in (work.get("keywords") or [])
        if kw.get("display_name")
    ]
    concepts = [
        c.get("display_name")
        for c in sorted(work.get("concepts") or [], key=lambda c: -c.get("score", 0))[:5]
        if c.get("display_name")
    ]

    return {
        "id": work.get("id", ""),
        "doi": work.get("doi"),
        "title": work.get("title"),
        "publication_year": work.get("publication_year"),
        "publication_date": work.get("publication_date"),
        "type": work.get("type"),
        "language": work.get("language"),
        "cited_by_count": work.get("cited_by_count", 0),
        "referenced_works_count": work.get("referenced_works_count"),
        "fwci": work.get("fwci"),
        "is_open_access": int(bool(open_access.get("is_oa"))),
        "source_name": source.get("display_name"),
        "host_organization_name": source.get("host_organization_name"),
        "n_authors": len(authorships),
        "first_author_name": author_names[0] if author_names else None,
        "author_names": "; ".join(author_names),
        "institution_names": "; ".join(institutions),
        "keywords": "; ".join(keywords),
        "concepts": "; ".join(concepts),
        "abstract_text": inverted_index_to_text(work.get("abstract_inverted_index")),
    }


# %% Glowna funkcja pobierajaca
def fetch_dataset(
    config_path: str | Path | None = None,
    use_cache: bool = True,
) -> Path:
    ensure_dirs()
    load_environment()
    config = load_config(config_path)

    keywords: list[str] = config["keywords"]
    context_terms: list[str] = config["topic_context_terms"]
    query_cfg: dict[str, Any] = config.get("query", {})
    per_page: int = int(query_cfg.get("per_page", 200))
    max_records: int = int(query_cfg.get("max_records", 10_000))
    mail_to: str = str(query_cfg.get("mail_to", "research@example.edu"))
    search_field: str = str(query_cfg.get("search_field", "title_and_abstract"))
    extra_filters: list[str] = list(query_cfg.get("extra_filters") or [])
    api_key: str | None = os.getenv("OPENALEX_API_KEY")

    boolean_query = build_deterministic_query(keywords, context_terms)
    filter_query = build_filter(search_field, boolean_query, extra_filters)
    logger.info("Temat badawczy: %s", config.get("research_topic"))
    logger.info("Zapytanie OpenAlex (filter): %s", filter_query)
    logger.info("Cel: %d rekordow (partie po %d)", max_records, per_page)

    rows: list[dict[str, Any]] = []
    validation_failures: list[dict[str, Any]] = []
    total_count = 0
    cursor = "*"
    batch = 0

    while cursor and len(rows) < max_records:
        batch += 1
        data = fetch_batch(filter_query, cursor, batch, per_page, mail_to, api_key, use_cache)
        meta = data.get("meta") or {}
        total_count = meta.get("count", total_count)
        cursor = meta.get("next_cursor")
        batch_results = data.get("results") or []
        if not batch_results:
            logger.info("Brak kolejnych rekordow - koniec.")
            break

        for work in batch_results:
            ok, errors = validate_work(work)
            if not ok:
                validation_failures.append({"id": work.get("id"), "errors": errors})
            rows.append(extract_row(work))

        logger.info(
            "Partia %d: pobrano %d rekordow (razem %d / cel %d, dostepnych w API: %d)",
            batch,
            len(batch_results),
            len(rows),
            max_records,
            total_count,
        )

    # Przytnij do celu i usun ewentualne duplikaty po identyfikatorze pracy.
    rows = rows[:max_records]
    unikalne: dict[str, dict[str, Any]] = {}
    for row in rows:
        unikalne.setdefault(row["id"], row)
    duplikaty = len(rows) - len(unikalne)
    rows = list(unikalne.values())
    if duplikaty:
        logger.warning("Usunieto %d duplikatow po 'id'.", duplikaty)

    stamp = timestamp()
    out_path = DATA_DIR / f"works_{config['_config_stem']}_{stamp}.csv"
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Zapisano %d rekordow do %s", len(rows), out_path)
    logger.info(
        "Podsumowanie: dostepnych w API=%d, zapisanych=%d, bledy walidacji=%d",
        total_count,
        len(rows),
        len(validation_failures),
    )
    return out_path


# %% Uruchomienie
if __name__ == "__main__":
    dataset_path = fetch_dataset(config_path=CONFIG_DIR / "topic.yaml")
    print(f"Dataset zapisany w: {dataset_path}")
    print(f"Kolejne skrypty uzyja pliku: {latest_dataset()}")
