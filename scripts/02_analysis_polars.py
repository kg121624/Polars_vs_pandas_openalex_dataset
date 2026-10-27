# %%
"""
KROK 2a - Analiza danych w POLARS.

Ten sam zestaw 12 pytan (Q1-Q12) realizujemy tutaj w Polars, a nastepnie -
identycznie - w Pandas (03) i w SQL (04). Celem jest porownanie SKLADNI,
a nie wydajnosci. Q10-Q11 to zaawansowana operacja na stringach: rozbicie
kolumny 'keywords' na pojedyncze slowa kluczowe i ich zliczenie.

Uruchamiaj kolejne komorki (# %%) w Python Interactive Window.
"""

# %% Importy i sciezki
from __future__ import annotations

import sys
import time
from pathlib import Path

import polars as pl

sys.path.append(str(Path(__file__).resolve().parent))

from common import latest_dataset, load_config, save_results  # noqa: E402

METODA = "polars"

# %% Konfiguracja i lokalizacja danych
config = load_config()
dataset_path = latest_dataset(config["_config_stem"])
print(f"Metoda  : {METODA}")
print(f"Dataset : {dataset_path}")
print(f"Temat   : {config['research_topic']}")

# %% Wczytanie danych (START POMIARU CZASU)
start = time.perf_counter()

df = pl.read_csv(
    dataset_path,
    schema_overrides={
        "publication_year": pl.Int32,
        "cited_by_count": pl.Int64,
        "referenced_works_count": pl.Int64,
        "n_authors": pl.Int64,
        "fwci": pl.Float64,
        "is_open_access": pl.Int8,
    },
    infer_schema_length=10_000,
)

# Sprzatanie: analizujemy tylko rekordy z tytulem (reszta jest bezuzyteczna dla Q5/Q8).
df = df.filter(pl.col("title").is_not_null() & (pl.col("title") != ""))
print(f"Ksztalt danych: {df.shape}")

# %% Lista wynikow (format tidy: id, pytanie, szczegol, wartosc, typ_danych)
wyniki: list[dict] = []


def dodaj(qid: str, pytanie: str, szczegol: str, wartosc, typ: str) -> None:
    if typ == "int":
        wartosc = int(wartosc)
    elif typ == "float":
        wartosc = round(float(wartosc), 6)
    wyniki.append(
        {"id": qid, "pytanie": pytanie, "szczegol": szczegol, "wartosc": wartosc, "typ_danych": typ}
    )


# %% Q1 - liczba prac (int)
q1 = df.height
print(f"Q1. Liczba prac: {q1}")
dodaj("Q1", "Liczba prac w datasecie", "-", q1, "int")

# %% Q2 - liczba prac z unikalnym DOI (int)
q2 = df.select(pl.col("doi").drop_nulls().n_unique()).item()
print(f"Q2. Liczba unikalnych DOI: {q2} (rekordow bez DOI: {df['doi'].null_count()})")
dodaj("Q2", "Liczba unikalnych DOI", "-", q2, "int")

# %% Q3 - liczba prac wedlug roku publikacji (int, grupowanie)
q3 = (
    df.drop_nulls("publication_year")
    .group_by("publication_year")
    .len()
    .sort("publication_year")
)
print("Q3. Prace wedlug roku:")
print(q3)
for row in q3.iter_rows(named=True):
    dodaj("Q3", "Liczba prac wedlug roku publikacji", str(row["publication_year"]), row["len"], "int")

# %% Q4 - top 10 jezykow publikacji (str, grupowanie + sortowanie)
q4 = (
    df.drop_nulls("language")
    .group_by("language")
    .len()
    .sort(["len", "language"], descending=[True, False])
    .head(10)
)
print("Q4. Top jezyki publikacji:")
print(q4)
for row in q4.iter_rows(named=True):
    dodaj("Q4", "Top 10 jezykow publikacji", row["language"], row["len"], "int")

# %% Q5 - top 5 najczesciej cytowanych prac (str + int, sortowanie + limit)
q5 = df.select("title", "cited_by_count").sort(
    ["cited_by_count", "title"], descending=[True, False]
).head(5)
print("Q5. Top 5 najczesciej cytowanych prac:")
print(q5)
for ranking, row in enumerate(q5.iter_rows(named=True), start=1):
    dodaj(
        "Q5",
        "Top 5 najczesciej cytowanych prac",
        f"{ranking}. {row['title']}",
        row["cited_by_count"],
        "int",
    )

# %% Q6 - srednia liczba cytowan na prace (float, agregacja)
q6 = df.select(pl.col("cited_by_count").mean()).item()
print(f"Q6. Srednia liczba cytowan: {q6:.4f}")
dodaj("Q6", "Srednia liczba cytowan na prace (float)", "-", q6, "float")

# %% Q7 - srednia wartosc FWCI (float, agregacja z brakami)
q7 = df.select(pl.col("fwci").mean()).item()
print(f"Q7. Srednia wartosc FWCI: {q7:.4f} (braki: {df['fwci'].null_count()})")
dodaj("Q7", "Srednia wartosc FWCI (float)", "-", q7, "float")

# %% Q8 - srednia dlugosc tytulu w znakach (str -> float)
q8 = df.select(pl.col("title").str.len_chars().mean()).item()
print(f"Q8. Srednia dlugosc tytulu: {q8:.2f} znakow")
dodaj("Q8", "Srednia dlugosc tytulu w znakach (float)", "-", q8, "float")

# %% Q9 - top 5 czasopism wedlug liczby prac (str, grupowanie + sortowanie + limit)
q9 = (
    df.drop_nulls("source_name")
    .group_by("source_name")
    .len()
    .sort(["len", "source_name"], descending=[True, False])
    .head(5)
)
print("Q9. Top 5 czasopism:")
print(q9)
for row in q9.iter_rows(named=True):
    dodaj("Q9", "Top 5 czasopism wedlug liczby prac", row["source_name"], row["len"], "int")

# %% Q10/Q11 - przygotowanie: rozbicie kolumny 'keywords' na pojedyncze slowa kluczowe
# Zaawansowana operacja na stringach: split -> explode (po jednym wierszu na pare praca-keyword).
kw = (
    df.select("id", "keywords")
    .with_columns(pl.col("keywords").str.split("; ").alias("keyword"))
    .explode("keyword")
    .with_columns(pl.col("keyword").str.strip_chars())
    .filter(pl.col("keyword").is_not_null() & (pl.col("keyword") != ""))
)
print(f"Par (praca, keyword): {kw.height}")

# %% Q10 - liczba unikalnych slow kluczowych w calym datasecie (int)
q10 = kw["keyword"].n_unique()
print(f"Q10. Unikalnych slow kluczowych: {q10}")
dodaj("Q10", "Liczba unikalnych slow kluczowych", "-", q10, "int")

# %% Q11 - top 10 najczestszych slow kluczowych (str, grupowanie + sortowanie + limit)
q11 = (
    kw.group_by("keyword")
    .len()
    .sort(["len", "keyword"], descending=[True, False])
    .head(10)
)
print("Q11. Top 10 slow kluczowych:")
print(q11)
for row in q11.iter_rows(named=True):
    dodaj("Q11", "Top 10 najczestszych slow kluczowych", row["keyword"], row["len"], "int")

# %% Q12 - wybor wierszy: pozycje 11-20 w kolejnosci pliku (bez sortowania)
# Odpowiednik .slice(offset, length): "pomin 10 wierszy, wez kolejne 10".
q12 = df.select("title", "cited_by_count").slice(10, 10)
print("Q12. Wiersze 11-20:")
print(q12)
for ranking, row in enumerate(q12.iter_rows(named=True), start=11):
    dodaj("Q12", "Wiersze 11-20 w kolejnosci pliku", f"{ranking}. {row['title']}", row["cited_by_count"], "int")

# %% Zapis wynikow (STOP POMIARU CZASU)
elapsed = time.perf_counter() - start
out_path = save_results(wyniki, METODA, elapsed, dataset_path, config)
print(f"Zapisano {len(wyniki)} wierszy wynikow w {out_path}")
print(f"Czas wykonania: {elapsed:.4f} s")
