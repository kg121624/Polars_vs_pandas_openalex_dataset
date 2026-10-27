---
marp: true
theme: default
paginate: true
size: 16:9
header: 'Polars vs Pandas vs SQL — warsztat OpenAlex'
footer: 'Warsztat dla studentów · 2h'
style: |
  section {
    font-size: 23px;
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
  }
  section.lead h1 { font-size: 46px; }
  section.lead p { color: #555; }
  h1 { color: #2f6fdb; }
  h2 { color: #2f6fdb; border-bottom: 2px solid #e6e6e6; padding-bottom: 4px; }
  code { font-size: 0.86em; }
  pre { font-size: 0.72em; line-height: 1.25; }
  table { font-size: 0.82em; }
  .dense { font-size: 18px; }
  .dense pre { font-size: 0.62em; line-height: 1.15; }
  .dense table { font-size: 0.72em; }
  .dense li { margin: 1px 0; }
  .columns { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
  .columns-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
  .ok { color: #1f9e5a; font-weight: 600; }
  .note { background: #f3f7ff; border-left: 4px solid #2f6fdb; padding: 8px 12px; }
---

<!-- _class: lead -->

# Polars vs Pandas vs SQL

## Od zapytania do OpenAlex do wniosku analitycznego

**Warsztat 2h** · dataset OpenAlex · trzy języki, jeden wynik

`uv run` · Python Interactive Window (`# %%`) · CSV / XLSX / Markdown

---

## Plan warsztatu (ok. 2 h)

<div class="dense">

| # | Etap | Czas | Efekt |
|---|------|------|-------|
| 1 | Konfiguracja tematu (YAML) + kwerenda OpenAlex | 15 min | `data/works_topic_*.csv` |
| 2 | Analiza w **Polars** (Q1–Q12) | 20 min | `reports/wyniki_polars_*.xlsx` |
| 3 | Analiza w **Pandas** (te same Q1–Q12) | 20 min | `reports/wyniki_pandas_*.xlsx` |
| 4 | Analiza w **SQL / pandasql** (te same Q1–Q12) | 20 min | `reports/wyniki_sql_*.xlsx` |
| 5 | Porównanie wyników + wykresy | 15 min | `reports/porownanie_*.xlsx` |
| 6 | Dyskusja: składnia, typy, pułapki NULL | 10 min | wnioski |

</div>

<div class="note">

Cel nie jest „która biblioteka jest szybsza”, ale **pokazanie różnic w składni** na tym samym zadaniu analitycznym.

</div>

---

## Cel projektu i pytanie badawcze

**Temat:** Ekonometryczna walidacja modelu wspomagania decyzji zarządczych

**Pytanie:** Jak szybko — zaczynając od zera — zbudować mały dataset naukowy i wyciągnąć z niego wnioski w trzech różnych językach zapytań?

**Trzy kroki:**

1. **Ekstrakcja** — kwerenda do OpenAlex na podstawie konfiguracji YAML → CSV.
2. **Analiza** — 12 identycznych pytań (Q1–Q12) wykonanych osobno w Polars, Pandas i SQL.
3. **Porównanie** — czy wyniki są zgodne? które zapisy są najkrótsze? gdzie są pułapki?

<div class="note">

Kluczowa zasada: **logika jest ta sama**, zmieniamy tylko język zapytania.

</div>

---

<!-- _class: dense -->

## Krok 1 — konfiguracja tematu w osobnym pliku

Zamiast kodu zmieniamy jeden plik: `config/topic.yaml`

```yaml
research_topic: >-
  Ekonometryczna walidacja modelu wspomagania decyzji zarzadczych

keywords:                    # część A: OR
  - optimization
  - net benefit
  - efficiency

topic_context_terms:         # część B: OR
  - Human resources
  - financials
  - management
  - customer

query:
  per_page: 200
  max_records: 12000
  search_field: title_and_abstract
  extra_filters: ["type:article", "has_abstract:true"]
```

<div class="note">

Zapytanie = `(KEYWORDS) AND (TOPIC_CONTEXT_TERMS)`. Zmiana tematu = edycja YAML, **zero zmian w kodzie**.

</div>

---

<!-- _class: dense -->

## Krok 1 — co trafia do OpenAlex

Kwerenda zbudowana deterministycznie (posortowane frazy) i zapisana jako `filter`:

```text
title_and_abstract.search:
  ("efficiency" OR "net benefit" OR "optimization")
  AND
  ("customer" OR "financials" OR "management" OR "Human resources")
, type:article, has_abstract:true
```

| Miara | Wartość |
|---|---|
| Prac dostępnych w API | **835 374** |
| Pobranych do datasetu | **11 881** (pobrano 12 000, usunięto 119 duplikatów) |
| Sposób stronicowania | **kursor** (`cursor=*`), nie `page` |
| Rekordów pominiętych w walidacji | 0 |

<div class="note">

Dlaczego kursor? Przy głębokim stronicowaniu parametrem `page` OpenAlex zwraca **~1% duplikatów** (niestabilny podział wyników). Kursor `cursor=*` gwarantuje spójny, niepowtarzalny zbiór — i pozwala przekroczyć limit 10 000 rekordów.

</div>

---

<!-- _class: dense -->

## Struktura projektu

```text
Polars_vs_pandas_openalex_dataset/
├── config/
│   └── topic.yaml              # KEYWORDS, TOPIC_CONTEXT_TERMS, RESEARCH_TOPIC
├── scripts/
│   ├── common.py               # YAML, .env, ścieżki, zapis wyników
│   ├── 01_fetch_openalex.py    # API → data/works_topic_*.csv
│   ├── 02_analysis_polars.py   # Q1–Q12 w Polars
│   ├── 03_analysis_pandas.py   # Q1–Q12 w Pandas
│   ├── 04_analysis_sql.py      # Q1–Q12 w SQL (pandasql)
│   └── 05_compare_results.py   # zgodność + wykresy
├── data/                       # dataset CSV (timestamp w nazwie)
├── reports/                    # XLSX + CSV + Markdown + figures/ (PNG, SVG)
├── .env                        # OPENALEX_API_KEY
└── pyproject.toml              # zależności (uv)
```

<div class="note">

Każdy skrypt używa znaczników `# %%` — uruchamiasz komórka po komórce w Python Interactive Window.

</div>

---

<!-- _class: dense -->

## Krok 2 — dwanaście pytań analitycznych (Q1–Q12)

| id | Pytanie | Typ danych | Operacja |
|----|---------|-----------|----------|
| Q1 | Liczba prac w datasecie | int | licznik wierszy |
| Q2 | Liczba unikalnych DOI | int | distinct |
| Q3 | Liczba prac według roku | int | grupowanie |
| Q4 | Top 10 języków publikacji | str | grupowanie + sort + limit |
| Q5 | Top 5 najczęściej cytowanych prac | str/int | sort + limit |
| Q6 | Średnia liczba cytowań | float | agregacja |
| Q7 | Średnia wartość FWCI | float | agregacja z brakami |
| Q8 | Średnia długość tytułu (znaki) | str→float | operacja na stringu |
| Q9 | Top 5 czasopism | str | grupowanie + sort + limit |
| Q10 | Liczba unikalnych słów kluczowych | int | **split → explode → distinct** |
| Q11 | Top 10 najczęstszych słów kluczowych | str/int | **split → explode → grupowanie** |
| Q12 | Wiersze 11–20 (kolejność pliku) | str/int | **wybór wierszy (slice / offset)** |

<div class="note">

Świadomie mieszamy **int / float / str**, żeby zobaczyć różnice w typowaniu, sortowaniu i obsłudze wartości pustych. Q10–Q11 to zaawansowana praca na stringach, Q12 to wybór wierszy po pozycji.

</div>

---

<!-- _class: dense -->

## Składnia — rozbicie stringów na słowa (Q10/Q11)

Kolumna `keywords` to tekst rozdzielony `"; "` (np. `"efficiency; management"`). Trzeba go **rozbic na pary (praca, słowo)** — to operacja *split → explode*.

<div class="columns-3">

<div>

**Polars**

```python
kw = (
  df.select("id", "keywords")
    .with_columns(
      pl.col("keywords")
        .str.split("; ")
        .alias("keyword"))
    .explode("keyword")
    .with_columns(
      pl.col("keyword")
        .str.strip_chars())
)

kw["keyword"].n_unique()
```

</div>

<div>

**Pandas**

```python
kw = (
  df[["id", "keywords"]]
    .assign(keyword=df["keywords"]
       .str.split("; "))
    .explode("keyword")
    .dropna(subset=["keyword"])
)
kw["keyword"] = kw["keyword"].str.strip()

kw["keyword"].nunique()
```

</div>

<div>

**SQL**

```sql
-- SQLite nie ma SPLIT:
-- rozbijamy rekurencyjnym CTE
WITH RECURSIVE kw_pairs(
    work_id, keyword, rest) AS (
  SELECT id,
    TRIM(SUBSTR(keywords||'; ',
      1, INSTR(keywords||'; ',
               '; ')-1)),
    SUBSTR(keywords||'; ',
      INSTR(keywords||'; ',
            '; ')+2)
  FROM df
  UNION ALL
  SELECT work_id,
    TRIM(SUBSTR(rest, 1,
      INSTR(rest, '; ')-1)),
    SUBSTR(rest,
      INSTR(rest, '; ')+2)
  FROM kw_pairs
  WHERE rest <> ''
)
SELECT COUNT(DISTINCT keyword)
FROM kw_pairs
```

</div>

</div>

<div class="note">

Ten sam efekt, bardzo różny koszt. Polars i Pandas mają `explode` w jednej linii; w SQL trzeba **ręcznie** rozbijać tekst rekurencyjnym `CTE` — to pokazuje, gdzie SQL przestaje być wygodny.

</div>

---

<!-- _class: dense -->

## Składnia — wybór 10 wierszy od pozycji 11 (Q12)

Bez sortowania — bierzemy wiersze **11.–20.** w kolejności pliku (pomijamy 10 pierwszych):

<div class="columns-3">

<div>

**Polars**

```python
df.select(
    "title", "cited_by_count"
  ).slice(10, 10)
# slice(offset, length)
```

</div>

<div>

**Pandas**

```python
df.iloc[10:20][
    ["title", "cited_by_count"]]
# iloc[start:stop] - stop wykluczony
```

</div>

<div>

**SQL**

```sql
SELECT title, cited_by_count
FROM df
LIMIT 10 OFFSET 10
-- pomin 10, wez 10
```

</div>

</div>

<div class="note">

Polars używa pary **offset + długość** (`slice(10, 10)`), Pandas i Python — **wycinka** `[start:stop]` (koniec wykluczony), a SQL **`LIMIT` + `OFFSET`**. Uwaga: bez `ORDER BY` kolejność jest zależna od silnika — SQLite zwraca wiersze w kolejności wstawiania.

</div>

---

<!-- _class: dense -->

## Krok 3 — porównanie: zgodność wyników

Wszystkie 115 wierszy wyników (Q1–Q12) porównane po `(id, szczegol)`:

| id | Pytanie | Wierszy | Różnych |
|----|---------|--------:|--------:|
| Q1 | Liczba prac | 1 | **0** |
| Q2 | Unikalne DOI | 1 | **0** |
| Q3 | Prace według roku | 69 | **0** |
| Q4 | Top 10 języków | 10 | **0** |
| Q5 | Top 5 cytowanych | 5 | **0** |
| Q6 | Średnia cytowań | 1 | **0** |
| Q7 | Średnia FWCI | 1 | **0** |
| Q8 | Średnia długość tytułu | 1 | **0** |
| Q9 | Top 5 czasopism | 5 | **0** |
| Q10 | Unikalne słowa kluczowe | 1 | **0** |
| Q11 | Top 10 słów kluczowych | 10 | **0** |
| Q12 | Wiersze 11–20 | 10 | **0** |

<p class="ok">Wynik: 115 / 115 zgodnych — 0 rozbieżności.</p>

---

<!-- _class: dense -->

## Składnia — wczytanie pliku CSV

<div class="columns-3">

<div>

**Polars**

```python
import polars as pl

df = pl.read_csv(
  path,
  schema_overrides={
    "publication_year": pl.Int32,
    "fwci": pl.Float64,
  },
)
```

</div>

<div>

**Pandas**

```python
import pandas as pd

df = pd.read_csv(path)
```

</div>

<div>

**SQL**

```python
from pandasql import sqldf

df = pd.read_csv(path)

def sql(q):
  return sqldf(q, {"df": df})
```

</div>

</div>

<div class="note">

Polars pozwala z góry narzucić typy kolumn (rekomendowane). SQL nie ma etapu „wczytania” — tabelę `df` podaje pandasql.

</div>

---

<!-- _class: dense -->

## Składnia — grupowanie i zliczanie

<div class="columns-3">

<div>

**Polars**

```python
df.drop_nulls("language") \
  .group_by("language") \
  .len() \
  .sort(["len", "language"],
        descending=[True, False]) \
  .head(10)
```

</div>

<div>

**Pandas**

```python
df.dropna(subset=["language"]) \
  .groupby("language") \
  .size() \
  .reset_index(name="n") \
  .sort_values(["n", "language"],
    ascending=[False, True]) \
  .head(10)
```

</div>

<div>

**SQL**

```sql
SELECT language, COUNT(*) AS n
FROM df
WHERE language IS NOT NULL
GROUP BY language
ORDER BY n DESC, language ASC
LIMIT 10
```

</div>

</div>

<div class="note">

Trzy zapisy jednej myśli: „policz rekordy na grupę i pokaż 10 największych”.

</div>

---

<!-- _class: dense -->

## Składnia — sortowanie, limit i stringi

<div class="columns">

<div>

**Top 5 najczęściej cytowanych (Q5)**

```python
# Polars
df.select("title", "cited_by_count") \
  .sort(["cited_by_count", "title"],
        descending=[True, False]).head(5)

# Pandas
df.sort_values(["cited_by_count", "title"],
    ascending=[False, True]).head(5)
```

```sql
-- SQL
SELECT title, cited_by_count
FROM df
ORDER BY cited_by_count DESC, title ASC
LIMIT 5
```

</div>

<div>

**Średnia długość tytułu (Q8)**

```python
# Polars
df.select(pl.col("title")
    .str.len_chars().mean()).item()

# Pandas
df["title"].str.len().mean()
```

```sql
-- SQL
SELECT AVG(LENGTH(title)) AS n FROM df
```

</div>

</div>

<div class="note">

**Wspólny trik:** zawsze dodajemy sortowanie pomocnicze (np. po `title`) — bez niego kolejność przy remisach może się różnić między metodami.

</div>

---

<!-- _class: dense -->

## Krok 3 — przykładowe wartości (te same w trzech metodach)

| id | Szczegół | Polars | Pandas | SQL |
|----|----------|-------:|-------:|----:|
| Q1 | liczba prac | 11881 | 11881 | 11881 |
| Q2 | unikalne DOI | 8908 | 8908 | 8908 |
| Q6 | średnia cytowań | 14.7456 | 14.7456 | 14.7456 |
| Q7 | średnia FWCI | 1.8796 | 1.8796 | 1.8796 |
| Q8 | dł. tytułu | 90.2211 | 90.2211 | 90.2211 |
| Q9 | RePEc | 277 | 277 | 277 |
| Q9 | Zenodo | 294 | 294 | 294 |
| Q10 | unikalne słowa kluczowe | 30818 | 30818 | 30818 |
| Q11 | human resource management | 731 | 731 | 731 |
| Q11 | customer satisfaction | 667 | 667 | 667 |
| Q12 | 11. Human Resources Management… | 0 | 0 | 0 |
| Q12 | 12. The Role of Information… | 7 | 7 | 7 |

<div class="note">

Typy `int` (zliczenia), `float` (średnie) i `str` (nazwy czasopism/języków, słowa kluczowe) dają identyczne rezultaty w każdej z metod. Q12 pokazuje, że **ten sam wiersz** o tej samej pozycji trafia do wyniku we wszystkich trzech językach.

</div>

---

<!-- _class: dense -->

## Krok 3 — czas wykonania (11 881 rekordów)

| Metoda | Czas [s] | Udział |
|--------|---------:|-------:|
| **Polars** | 0.1551 | 8.6% |
| **Pandas** | 0.2191 | 12.1% |
| **SQL (pandasql)** | 1.4354 | 79.3% |

![w:680](reports/figures/czas_wykonania.png)

<div class="note">

Przy ~12 tys. rekordów różnice są widoczne: Pandas ok. **1,4×**, a pandasql ok. **9,3×** wolniejsze od Polars. Część kosztu SQL to „podatek” za tłumaczenie SQL → SQLite oraz ręczne rozbijanie stringów w Q10/Q11.

</div>

---

<!-- _class: dense -->

## Wnioski

1. **Poprawność.** Trzy języki → jeden wynik (115/115 zgodnych). Składnia się różni, logika nie.
2. **Typy danych.** Polars pozwala narzucić schemat (`schema_overrides`); Pandas inferuje i często wstawia `float64` tam, gdzie spodziewamy się `int`.
3. **Puste wartości — główne źródło rozbieżności.** Polars grupuje `NULL`, Pandas domyślnie je pomija, SQL ma osobną grupę `NULL`. Dlatego jawnie filtrujemy braki.
4. **Remisy.** Bez sortowania pomocniczego kolejność `top-N` bywa różna między metodami — zawsze dodawaj drugi klucz sortowania.
5. **Stringi (Q10/Q11).** Rozbicie tekstu na słowa to jedna linia w Polars/Pandas (`str.split` + `explode`), ale w SQLite wymaga rekurencyjnego `CTE` — tu SQL traci przewagę prostoty.
6. **Wybór wierszy (Q12).** Polars to `slice(offset, length)`, Pandas `iloc[start:stop]`, SQL `LIMIT` + `OFFSET`. Bez `ORDER BY` kolejność jest zależna od silnika.
7. **Czytelność.** SQL bywa najkrótszy dla agregacji; Polars jest zwięzły i typowany; Pandas najbardziej „rozproszony” składniowo.

---

<!-- _class: dense -->

## Ściągawka — jeden problem, trzy zapisy

| Operacja | Polars | Pandas | SQL |
|----------|--------|--------|-----|
| Wczytanie | `pl.read_csv(path)` | `pd.read_csv(path)` | `sqldf(q, {"df": df})` |
| Liczba wierszy | `df.height` | `len(df)` | `SELECT COUNT(*)` |
| Unikalne | `col.n_unique()` | `df["c"].nunique()` | `COUNT(DISTINCT c)` |
| Grupowanie | `group_by().len()` | `groupby().size()` | `GROUP BY … COUNT(*)` |
| Sortowanie | `.sort(col)` | `.sort_values(col)` | `ORDER BY col` |
| Top-N | `.head(n)` | `.head(n)` | `LIMIT n` |
| Średnia | `col.mean()` | `df["c"].mean()` | `AVG(c)` |
| Długość tekstu | `col.str.len_chars()` | `df["c"].str.len()` | `LENGTH(c)` |
| Rozbicie tekstu | `col.str.split("; ")` | `df["c"].str.split("; ")` | `SPLIT` (brak w SQLite) |
| Rozwinięcie listy | `.explode("keyword")` | `.explode("keyword")` | rekurencyjny `WITH RECURSIVE` |
| Przycięcie spacji | `col.str.strip_chars()` | `df["c"].str.strip()` | `TRIM(c)` |
| Wybór wierszy | `.slice(10, 10)` | `.iloc[10:20]` | `LIMIT 10 OFFSET 10` |
| Braki | `drop_nulls()` | `dropna()` | `WHERE c IS NOT NULL` |

---

<!-- _class: lead -->

# Ćwiczenia dla studentów

1. Zmień `keywords` w `config/topic.yaml` i ponownie uruchom cały potok.
2. Dodaj **Q13**: „średnia liczba autorów na pracę” (`n_authors`) w trzech metodach.
3. Rozszerz Q11: znajdź słowa kluczowe występujące tylko w pracach z jednego kraju (`country`).
4. Powtórz Q12 z `ORDER BY title` — czy wyniki nadal są zgodne między metodami?
5. Dodaj filtr `publication_year:>2015` i sprawdź, czy wyniki nadal się zgadzają.
6. Zwiększ `max_records` do 30 000 i porównaj czasy wykonania.

<div class="note">

Uruchomienie: `uv sync`, następnie kolejno `scripts/01…05` w Python Interactive Window.

</div>
