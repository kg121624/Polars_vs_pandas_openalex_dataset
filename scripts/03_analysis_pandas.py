# %%
"""
KROK 2b - Analiza danych w PANDAS.

Ten sam zestaw 11 pytan (Q1-Q11) co w Polars (02) i SQL (04).
Porownaj skladnie obu bibliotek linia po linii.
Q10-Q11 to zaawansowana operacja na stringach (str.split + explode).
"""

# %% Importy i sciezki
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))

from common import latest_dataset, load_config, save_results  # noqa: E402

METODA = "pandas"

# %% Konfiguracja i lokalizacja danych
config = load_config()
dataset_path = latest_dataset(config["_config_stem"])
print(f"Metoda  : {METODA}")
print(f"Dataset : {dataset_path}")
print(f"Temat   : {config['research_topic']}")

# %% Wczytanie danych (START POMIARU CZASU)
start = time.perf_counter()

df = pd.read_csv(dataset_path)

# Sprzatanie: analizujemy tylko rekordy z tytulem (analogicznie jak w Polars).
df = df[df["title"].notna() & (df["title"] != "")].copy()
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
q1 = len(df)
print(f"Q1. Liczba prac: {q1}")
dodaj("Q1", "Liczba prac w datasecie", "-", q1, "int")

# %% Q2 - liczba prac z unikalnym DOI (int)
q2 = df["doi"].nunique()
print(f"Q2. Liczba unikalnych DOI: {q2} (rekordow bez DOI: {int(df['doi'].isna().sum())})")
dodaj("Q2", "Liczba unikalnych DOI", "-", q2, "int")

# %% Q3 - liczba prac wedlug roku publikacji (int, grupowanie)
q3 = (
    df.dropna(subset=["publication_year"])
    .assign(publication_year=lambda d: d["publication_year"].astype(int))
    .groupby("publication_year")
    .size()
    .reset_index(name="n")
    .sort_values("publication_year")
)
print("Q3. Prace wedlug roku:")
print(q3.to_string(index=False))
for row in q3.itertuples(index=False):
    dodaj("Q3", "Liczba prac wedlug roku publikacji", str(row.publication_year), row.n, "int")

# %% Q4 - top 10 jezykow publikacji (str, grupowanie + sortowanie)
q4 = (
    df.dropna(subset=["language"])
    .groupby("language")
    .size()
    .reset_index(name="n")
    .sort_values(["n", "language"], ascending=[False, True])
    .head(10)
)
print("Q4. Top jezyki publikacji:")
print(q4.to_string(index=False))
for row in q4.itertuples(index=False):
    dodaj("Q4", "Top 10 jezykow publikacji", row.language, row.n, "int")

# %% Q5 - top 5 najczesciej cytowanych prac (str + int, sortowanie + limit)
q5 = df.sort_values(["cited_by_count", "title"], ascending=[False, True]).head(5)
print("Q5. Top 5 najczesciej cytowanych prac:")
print(q5[["title", "cited_by_count"]].to_string(index=False))
for ranking, row in enumerate(q5.itertuples(index=False), start=1):
    dodaj(
        "Q5",
        "Top 5 najczesciej cytowanych prac",
        f"{ranking}. {row.title}",
        row.cited_by_count,
        "int",
    )

# %% Q6 - srednia liczba cytowan na prace (float, agregacja)
q6 = df["cited_by_count"].mean()
print(f"Q6. Srednia liczba cytowan: {q6:.4f}")
dodaj("Q6", "Srednia liczba cytowan na prace (float)", "-", q6, "float")

# %% Q7 - srednia wartosc FWCI (float, agregacja z brakami)
q7 = df["fwci"].mean()
print(f"Q7. Srednia wartosc FWCI: {q7:.4f} (braki: {int(df['fwci'].isna().sum())})")
dodaj("Q7", "Srednia wartosc FWCI (float)", "-", q7, "float")

# %% Q8 - srednia dlugosc tytulu w znakach (str -> float)
q8 = df["title"].str.len().mean()
print(f"Q8. Srednia dlugosc tytulu: {q8:.2f} znakow")
dodaj("Q8", "Srednia dlugosc tytulu w znakach (float)", "-", q8, "float")

# %% Q9 - top 5 czasopism wedlug liczby prac (str, grupowanie + sortowanie + limit)
q9 = (
    df.dropna(subset=["source_name"])
    .groupby("source_name")
    .size()
    .reset_index(name="n")
    .sort_values(["n", "source_name"], ascending=[False, True])
    .head(5)
)
print("Q9. Top 5 czasopism:")
print(q9.to_string(index=False))
for row in q9.itertuples(index=False):
    dodaj("Q9", "Top 5 czasopism wedlug liczby prac", row.source_name, row.n, "int")

# %% Q10/Q11 - przygotowanie: rozbicie kolumny 'keywords' na pojedyncze slowa kluczowe
# Zaawansowana operacja na stringach: str.split -> explode (po jednym wierszu na pare praca-keyword).
kw = (
    df[["id", "keywords"]]
    .assign(keyword=df["keywords"].str.split("; "))
    .explode("keyword")
    .dropna(subset=["keyword"])
)
kw["keyword"] = kw["keyword"].str.strip()
kw = kw[kw["keyword"] != ""]
print(f"Par (praca, keyword): {len(kw)}")

# %% Q10 - liczba unikalnych slow kluczowych w calym datasecie (int)
q10 = kw["keyword"].nunique()
print(f"Q10. Unikalnych slow kluczowych: {q10}")
dodaj("Q10", "Liczba unikalnych slow kluczowych", "-", q10, "int")

# %% Q11 - top 10 najczestszych slow kluczowych (str, grupowanie + sortowanie + limit)
q11 = (
    kw.groupby("keyword")
    .size()
    .reset_index(name="n")
    .sort_values(["n", "keyword"], ascending=[False, True])
    .head(10)
)
print("Q11. Top 10 slow kluczowych:")
print(q11.to_string(index=False))
for row in q11.itertuples(index=False):
    dodaj("Q11", "Top 10 najczestszych slow kluczowych", row.keyword, row.n, "int")

# %% Zapis wynikow (STOP POMIARU CZASU)
elapsed = time.perf_counter() - start
out_path = save_results(wyniki, METODA, elapsed, dataset_path, config)
print(f"Zapisano {len(wyniki)} wierszy wynikow w {out_path}")
print(f"Czas wykonania: {elapsed:.4f} s")
