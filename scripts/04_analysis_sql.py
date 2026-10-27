# %%
"""
KROK 2c - Analiza danych w SQL (silnik SQLite przez biblioteke pandasql).

Ten sam zestaw 12 pytan (Q1-Q12) co w Polars (02) i Pandas (03).
Zapytania SQL dzialaja na ramce pandas (df) udostepnianej jako tabela "df".
Q10-Q11 to zaawansowana operacja na stringach - rozbicie 'keywords'
rekurencyjnym CTE (SQLite nie ma funkcji SPLIT).
"""

# %% Importy i sciezki
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
from pandasql import sqldf

sys.path.append(str(Path(__file__).resolve().parent))

from common import latest_dataset, load_config, save_results  # noqa: E402

METODA = "sql"

# %% Konfiguracja i lokalizacja danych
config = load_config()
dataset_path = latest_dataset(config["_config_stem"])
print(f"Metoda  : {METODA}")
print(f"Dataset : {dataset_path}")
print(f"Temat   : {config['research_topic']}")

# %% Wczytanie danych (START POMIARU CZASU)
start = time.perf_counter()

df = pd.read_csv(dataset_path)

# Sprzatanie: analizujemy tylko rekordy z tytulem (analogicznie jak w Polars/Pandas).
df = df[df["title"].notna() & (df["title"] != "")].copy()
print(f"Ksztalt danych: {df.shape}")


def sql(query: str) -> pd.DataFrame:
    """Wykonuje zapytanie SQL na ramce df (pandasql -> SQLite)."""
    return sqldf(query, {"df": df})


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


# %% Q1 - liczba prac (int) - SELECT COUNT(*)
q1 = int(sql("SELECT COUNT(*) AS n FROM df").iloc[0, 0])
print(f"Q1. Liczba prac: {q1}")
dodaj("Q1", "Liczba prac w datasecie", "-", q1, "int")

# %% Q2 - liczba prac z unikalnym DOI (int) - COUNT(DISTINCT ...)
q2 = int(sql("SELECT COUNT(DISTINCT doi) AS n FROM df").iloc[0, 0])
print(f"Q2. Liczba unikalnych DOI: {q2}")
dodaj("Q2", "Liczba unikalnych DOI", "-", q2, "int")

# %% Q3 - liczba prac wedlug roku publikacji (int, GROUP BY)
q3 = sql(
    """
    SELECT CAST(publication_year AS INTEGER) AS rok, COUNT(*) AS n
    FROM df
    WHERE publication_year IS NOT NULL
    GROUP BY rok
    ORDER BY rok
    """
)
print("Q3. Prace wedlug roku:")
print(q3.to_string(index=False))
for row in q3.itertuples(index=False):
    dodaj("Q3", "Liczba prac wedlug roku publikacji", str(row.rok), row.n, "int")

# %% Q4 - top 10 jezykow publikacji (str, GROUP BY + ORDER BY + LIMIT)
q4 = sql(
    """
    SELECT language, COUNT(*) AS n
    FROM df
    WHERE language IS NOT NULL
    GROUP BY language
    ORDER BY n DESC, language ASC
    LIMIT 10
    """
)
print("Q4. Top jezyki publikacji:")
print(q4.to_string(index=False))
for row in q4.itertuples(index=False):
    dodaj("Q4", "Top 10 jezykow publikacji", row.language, row.n, "int")

# %% Q5 - top 5 najczesciej cytowanych prac (str + int, ORDER BY + LIMIT)
q5 = sql(
    """
    SELECT title, cited_by_count
    FROM df
    WHERE title IS NOT NULL
    ORDER BY cited_by_count DESC, title ASC
    LIMIT 5
    """
)
print("Q5. Top 5 najczesciej cytowanych prac:")
print(q5.to_string(index=False))
for ranking, row in enumerate(q5.itertuples(index=False), start=1):
    dodaj(
        "Q5",
        "Top 5 najczesciej cytowanych prac",
        f"{ranking}. {row.title}",
        row.cited_by_count,
        "int",
    )

# %% Q6 - srednia liczba cytowan na prace (float, AVG)
q6 = float(sql("SELECT AVG(cited_by_count) AS n FROM df").iloc[0, 0])
print(f"Q6. Srednia liczba cytowan: {q6:.4f}")
dodaj("Q6", "Srednia liczba cytowan na prace (float)", "-", q6, "float")

# %% Q7 - srednia wartosc FWCI (float, AVG z brakami - SQL ignoruje NULL)
q7 = float(sql("SELECT AVG(fwci) AS n FROM df").iloc[0, 0])
print(f"Q7. Srednia wartosc FWCI: {q7:.4f} (braki: {int(df['fwci'].isna().sum())})")
dodaj("Q7", "Srednia wartosc FWCI (float)", "-", q7, "float")

# %% Q8 - srednia dlugosc tytulu w znakach (str -> float, LENGTH())
q8 = float(sql("SELECT AVG(LENGTH(title)) AS n FROM df").iloc[0, 0])
print(f"Q8. Srednia dlugosc tytulu: {q8:.2f} znakow")
dodaj("Q8", "Srednia dlugosc tytulu w znakach (float)", "-", q8, "float")

# %% Q9 - top 5 czasopism wedlug liczby prac (str, GROUP BY + ORDER BY + LIMIT)
q9 = sql(
    """
    SELECT source_name, COUNT(*) AS n
    FROM df
    WHERE source_name IS NOT NULL
    GROUP BY source_name
    ORDER BY n DESC, source_name ASC
    LIMIT 5
    """
)
print("Q9. Top 5 czasopism:")
print(q9.to_string(index=False))
for row in q9.itertuples(index=False):
    dodaj("Q9", "Top 5 czasopism wedlug liczby prac", row.source_name, row.n, "int")

# %% Q10/Q11 - wspolny CTE: rozbicie kolumny 'keywords' na pary (praca, keyword)
# SQLite nie ma funkcji SPLIT, dlatego rozbijamy string rekurencyjnym CTE,
# krok po kroku odcinajac wszystko do pierwszego separatora '; '.
KW_SPLIT_CTE = """
WITH RECURSIVE kw_pairs(work_id, keyword, rest) AS (
    SELECT id,
           TRIM(SUBSTR(keywords || '; ', 1, INSTR(keywords || '; ', '; ') - 1)),
           SUBSTR(keywords || '; ', INSTR(keywords || '; ', '; ') + 2)
    FROM df
    WHERE keywords IS NOT NULL AND TRIM(keywords) <> ''
    UNION ALL
    SELECT work_id,
           TRIM(SUBSTR(rest, 1, INSTR(rest, '; ') - 1)),
           SUBSTR(rest, INSTR(rest, '; ') + 2)
    FROM kw_pairs
    WHERE rest <> ''
)
"""

# %% Q10 - liczba unikalnych slow kluczowych w calym datasecie (int, COUNT DISTINCT)
q10 = int(
    sql(KW_SPLIT_CTE + "SELECT COUNT(DISTINCT keyword) AS n FROM kw_pairs WHERE keyword <> ''").iloc[0, 0]
)
print(f"Q10. Unikalnych slow kluczowych: {q10}")
dodaj("Q10", "Liczba unikalnych slow kluczowych", "-", q10, "int")

# %% Q11 - top 10 najczestszych slow kluczowych (str, GROUP BY + ORDER BY + LIMIT)
q11 = sql(
    KW_SPLIT_CTE
    + """
    SELECT keyword, COUNT(*) AS n
    FROM kw_pairs
    WHERE keyword <> ''
    GROUP BY keyword
    ORDER BY n DESC, keyword ASC
    LIMIT 10
    """
)
print("Q11. Top 10 slow kluczowych:")
print(q11.to_string(index=False))
for row in q11.itertuples(index=False):
    dodaj("Q11", "Top 10 najczestszych slow kluczowych", row.keyword, row.n, "int")

# %% Q12 - wybor wierszy: pozycje 11-20 w kolejnosci pliku (bez sortowania)
# Odpowiednik LIMIT/OFFSET: "pomin 10 wierszy, wez kolejne 10".
# Uwaga: bez ORDER BY kolejnosc jest zalezna od silnika - SQLite dla prostego
# skanu zwraca wiersze w kolejnosci wstawiania (czyli tak jak w pliku CSV).
q12 = sql(
    """
    SELECT title, cited_by_count
    FROM df
    LIMIT 10 OFFSET 10
    """
)
print("Q12. Wiersze 11-20:")
print(q12.to_string(index=False))
for ranking, row in enumerate(q12.itertuples(index=False), start=11):
    dodaj("Q12", "Wiersze 11-20 w kolejnosci pliku", f"{ranking}. {row.title}", row.cited_by_count, "int")

# %% Zapis wynikow (STOP POMIARU CZASU)
elapsed = time.perf_counter() - start
out_path = save_results(wyniki, METODA, elapsed, dataset_path, config)
print(f"Zapisano {len(wyniki)} wierszy wynikow w {out_path}")
print(f"Czas wykonania: {elapsed:.4f} s")
