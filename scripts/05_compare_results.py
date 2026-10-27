# %%
"""
KROK 3 - Porownanie wynikow trzech metod (Polars / Pandas / SQL).

Skrypt:
  1. wczytuje trzy pliki wynikow z katalogu reports/,
  2. scala je po (id pytania, szczegol) i sprawdza, czy wartosci sa identyczne,
  3. zapisuje raport do Excela, CSV i Markdown,
  4. generuje wykresy (PNG + SVG) do katalogu reports/figures/.
"""

# %% Importy i sciezki
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # brak okna graficznego - zapis do plikow

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.append(str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    FIGURES_DIR,
    REPORTS_DIR,
    ensure_dirs,
    latest_results,
    load_config,
    timestamp,
)

METODY = ["polars", "pandas", "sql"]
TOLERANCJA = 1e-6

# %% Wczytanie wynikow i metadanych
ensure_dirs()
config = load_config()
stamp = timestamp()

wyniki: dict[str, pd.DataFrame] = {}
metadane: dict[str, pd.Series] = {}
sciezki: dict[str, Path] = {}

for metoda in METODY:
    path = latest_results(metoda)
    sciezki[metoda] = path
    wyniki[metoda] = pd.read_excel(path, sheet_name="wyniki")
    metadane[metoda] = pd.read_excel(path, sheet_name="meta").iloc[0]
    print(f"{metoda:7s} <- {path.name} ({len(wyniki[metoda])} wierszy)")

# %% Scalenie wynikow po (id, szczegol)
porownanie = wyniki["polars"][["id", "pytanie", "szczegol", "wartosc"]].rename(
    columns={"wartosc": "polars"}
)
for metoda in ("pandas", "sql"):
    porownanie = porownanie.merge(
        wyniki[metoda][["id", "szczegol", "wartosc"]].rename(columns={"wartosc": metoda}),
        on=["id", "szczegol"],
        how="outer",
    )

# Uzupelnienie brakujacych opisow pytan (gdyby ktorys skrypt pominieto krok)
opis = wyniki["polars"].set_index("id")["pytanie"].to_dict()
porownanie["pytanie"] = porownanie["pytanie"].fillna(porownanie["id"].map(opis))

# %% Ocena zgodnosci (liczby porownujemy z tolerancja, teksty dokladnie)
def ocen_zgodnosc(row: pd.Series) -> str:
    wartosci = [row["polars"], row["pandas"], row["sql"]]
    if any(pd.isna(w) for w in wartosci):
        return "BRAK DANYCH"
    try:
        liczby = [float(w) for w in wartosci]
    except (TypeError, ValueError):
        return "ZGODNE" if len(set(map(str, wartosci))) == 1 else "ROZNE"
    maximum = max(abs(v) for v in liczby)
    return "ZGODNE" if (maximum - min(liczby)) <= TOLERANCJA else "ROZNE"


porownanie["zgodnosc"] = porownanie.apply(ocen_zgodnosc, axis=1)

liczba_wierszy = len(porownanie)
liczba_zgodnych = int((porownanie["zgodnosc"] == "ZGODNE").sum())
liczba_roznych = int((porownanie["zgodnosc"] == "ROZNE").sum())
print(f"\nWierszy: {liczba_wierszy} | zgodnych: {liczba_zgodnych} | roznych: {liczba_roznych}")

# %% Zestawienie czasow wykonania
czasy = pd.DataFrame(
    {
        "metoda": METODY,
        "czas_s": [round(float(metadane[m]["czas_wykonania_s"]), 4) for m in METODY],
        "zapisano": [str(metadane[m]["zapisano"]) for m in METODY],
        "plik": [sciezki[m].name for m in METODY],
    }
)
czasy["udzial_proc"] = (czasy["czas_s"] / czasy["czas_s"].sum() * 100).round(1)
print("\nCzasy wykonania:")
print(czasy.to_string(index=False))

# %% Podsumowanie zgodnosci per pytanie
per_pytanie = (
    porownanie.groupby(["id", "pytanie"], as_index=False)
    .agg(wierszy=("zgodnosc", "size"), roznych=("zgodnosc", lambda s: int((s == "ROZNE").sum())))
    .sort_values("id")
)
print("\nZgodnosc per pytanie:")
print(per_pytanie.to_string(index=False))

# %% Zapis raportu do Excela i CSV
raport_path = REPORTS_DIR / f"porownanie_{stamp}.xlsx"
with pd.ExcelWriter(raport_path, engine="openpyxl") as writer:
    porownanie.sort_values(["id", "szczegol"]).to_excel(writer, sheet_name="porownanie", index=False)
    czasy.to_excel(writer, sheet_name="czasy", index=False)
    per_pytanie.to_excel(writer, sheet_name="per_pytanie", index=False)
print(f"\nRaport Excel: {raport_path}")

# Ten sam raport w CSV - czytelny bez LibreOffice/Excela (utf-8-sig = polskie znaki).
for nazwa, tabela in (
    ("porownanie", porownanie.sort_values(["id", "szczegol"])),
    ("czasy", czasy),
    ("per_pytanie", per_pytanie),
):
    csv_path = REPORTS_DIR / f"porownanie_{stamp}_{nazwa}.csv"
    tabela.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"Raport CSV:   {csv_path}")

# %% Wykres 1 - czas wykonania (PNG + SVG)
fig, ax = plt.subplots(figsize=(6.5, 4.0), dpi=150)
kolor = ["#2f6fdb", "#1f9e5a", "#d1562b"]
kreski = ax.bar(czasy["metoda"], czasy["czas_s"], color=kolor, width=0.55)
ax.bar_label(kreski, fmt="%.3f s", padding=3, fontsize=9)
ax.set_title("Czas wykonania analizy (Q1-Q12)")
ax.set_ylabel("sekundy")
ax.set_ylim(0, float(czasy["czas_s"].max()) * 1.25)
ax.grid(axis="y", linestyle=":", alpha=0.5)
fig.tight_layout()
for rozszerzenie in ("png", "svg"):
    fig.savefig(FIGURES_DIR / f"czas_wykonania.{rozszerzenie}")
plt.close(fig)
print(f"Wykres: {FIGURES_DIR / 'czas_wykonania.png'} (+ .svg)")

# %% Wykres 2 - liczba prac wedlug roku (PNG + SVG)
per_rok = (
    porownanie[porownanie["id"] == "Q3"][["szczegol", "polars"]]
    .assign(rok=lambda d: d["szczegol"].astype(float).astype(int))
    .sort_values("rok")
)
fig, ax = plt.subplots(figsize=(7.5, 4.0), dpi=150)
ax.plot(per_rok["rok"], per_rok["polars"], marker="o", markersize=3.5, color="#2f6fdb")
ax.set_title("Liczba prac wedlug roku publikacji")
ax.set_xlabel("rok publikacji")
ax.set_ylabel("liczba prac")
ax.grid(linestyle=":", alpha=0.5)
fig.tight_layout()
for rozszerzenie in ("png", "svg"):
    fig.savefig(FIGURES_DIR / f"publikacje_per_rok.{rozszerzenie}")
plt.close(fig)
print(f"Wykres: {FIGURES_DIR / 'publikacje_per_rok.png'} (+ .svg)")


# %% Raport Markdown
def formatuj(wartosc) -> str:
    if pd.isna(wartosc):
        return "-"
    if isinstance(wartosc, float):
        return f"{wartosc:.4f}"
    return str(wartosc)


wiersze_md = [
    "# Porownanie metod: Polars vs Pandas vs SQL",
    "",
    f"- **Temat badawczy:** {config['research_topic']}",
    f"- **Konfiguracja:** `{Path(config['_config_path']).name}`",
    f"- **Wierszy wynikow:** {liczba_wierszy} "
    f"(zgodnych: {liczba_zgodnych}, roznych: {liczba_roznych})",
    "",
    "## 1. Czas wykonania",
    "",
    "| Metoda | Czas [s] | Udzial [%] | Plik |",
    "|---|---|---|---|",
]
for row in czasy.itertuples(index=False):
    wiersze_md.append(f"| {row.metoda} | {row.czas_s:.4f} | {row.udzial_proc} | {row.plik} |")

wiersze_md += [
    "",
    "## 2. Zgodnosc wynikow (Q1-Q12)",
    "",
    "| Pytanie | Wierszy | Roznych |",
    "|---|---|---|",
]
for row in per_pytanie.itertuples(index=False):
    wiersze_md.append(f"| {row.id} - {row.pytanie} | {row.wierszy} | {row.roznych} |")

wiersze_md += [
    "",
    "## 3. Przykladowe porownanie wartosci",
    "",
    "| id | szczegol | Polars | Pandas | SQL | Zgodnosc |",
    "|---|---|---|---|---|---|",
]
przyklady = porownanie[
    porownanie["id"].isin(["Q1", "Q2", "Q6", "Q7", "Q8", "Q10"])
    | (porownanie["id"].isin(["Q4", "Q9", "Q11", "Q12"]) & (porownanie["szczegol"] != "-"))
].sort_values(["id", "szczegol"])
for row in przyklady.itertuples(index=False):
    szczegol = str(row.szczegol)
    if len(szczegol) > 45:
        szczegol = szczegol[:42] + "..."
    wiersze_md.append(
        f"| {row.id} | {szczegol} | {formatuj(row.polars)} | {formatuj(row.pandas)} "
        f"| {formatuj(row.sql)} | {row.zgodnosc} |"
    )

wniosek = (
    "Wszystkie trzy metody zwrocily identyczne wyniki."
    if liczba_roznych == 0
    else f"Wykryto {liczba_roznych} rozbieznosci - sprawdz tabele powyzej."
)

liczba_rekordow = int(porownanie.loc[porownanie["id"] == "Q1", "polars"].iloc[0])
czas_polars = float(czasy.loc[czasy["metoda"] == "polars", "czas_s"].iloc[0])
czas_pandas = float(czasy.loc[czasy["metoda"] == "pandas", "czas_s"].iloc[0])
czas_sql = float(czasy.loc[czasy["metoda"] == "sql", "czas_s"].iloc[0])
szybszy = "Polars" if czas_polars < czas_pandas else "Pandas"

wiersze_md += [
    "",
    "## 4. Wnioski",
    "",
    f"1. **Poprawnosc.** {wniosek} Roznice moga wynikac z odmiennego traktowania "
    "wartosci pustych (Polars grupuje NULL, Pandas domyslnie je pomija, SQL ma osobna grupe NULL).",
    "2. **Skladnia.** Kazde pytanie analityczne da sie zapisac w trzech jezykach; "
    "Polars zastepuje `groupby` przez `group_by`, Pandas uzywa lancuchow metod, "
    "a SQL operuje na deklaratywnych klauzulach SELECT/GROUP BY/ORDER BY.",
    f"3. **Wydajnosc przy {liczba_rekordow:,} rekordach.** {szybszy} okazal sie najszybszy. "
    f"Pandas byl ok. {czas_pandas / czas_polars:.1f}x wolniejszy od Polars, "
    f"a SQL (pandasql) ok. {czas_sql / czas_polars:.1f}x wolniejszy - "
    "roznicę widać już przy kilkunastu tysiącach wierszy.",
    "",
]

md_path = REPORTS_DIR / f"porownanie_{stamp}.md"
md_path.write_text("\n".join(wiersze_md), encoding="utf-8")
print(f"Raport Markdown: {md_path}")
