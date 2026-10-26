# Polars vs. Pandas: Efektywna ekstrakcja i przetwarzanie danych OpenAlex z wykorzystaniem logiki SQL

Repozytorium na spotkanie naukowe poświęcone nowoczesnym narzędziom inżynierii danych. Głównym bohaterem warsztatów jest biblioteka Polars – wydajna alternatywa dla Pandas, łącząca szybkość języka Rust z intuicyjną logiką zapytań SQL.

Proces ekstrakcji danych jest na podstawie datasetu OpenAlex. Na przykładach różnych typów danych (od identyfikatorów numerycznych po złożone operacje na stringach) przeanalizujemy różnice w składni, optymalizacji zapytań oraz wydajności pomiędzy Pandas, Polars i czystym SQL.

---

## Szybki start — środowisko w 5 krokach (dla osób, które pierwszy raz używają `uv`)

`uv` to menedżer środowisk i pakietów Pythona (od twórców `ruff`). Zastępuje ręczne tworzenie `venv` i instalowanie paczek — **nie musisz samodzielnie instalować Pythona ani `pip`**, `uv` zrobi to za Ciebie.

### Krok 1. Zainstaluj `uv` (jednorazowo)

Wybierz jedną komendę dla swojego systemu:

**macOS / Linux**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**macOS (Homebrew)**

```bash
brew install uv
```

**Windows (PowerShell)**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Po instalacji **zamknij i otwórz ponownie terminal** (albo uruchom `source $HOME/.local/bin/env`), a następnie sprawdź:

```bash
uv --version
```

Jeśli widzisz numer wersji — działa.

### Krok 2. Wejdź do katalogu projektu

```bash
cd Polars_vs_pandas_openalex_dataset
```

### Krok 3. Skonfiguruj klucz API (`.env`)

W katalogu głównym projektu utwórz plik `.env` (jeśli jeszcze go nie ma) i wklej swój klucz OpenAlex:

```dotenv
OPENALEX_API_KEY=twoj_klucz_openalex
```

Klucz jest darmowy — wygenerujesz go na <https://openalex.org/settings/api>. Bez klucza skrypt zadziała wolniej (wspólna pula zapytań), ale nie przestanie działać.

> Plik `.env` jest wpisany do `.gitignore` — nie trafi do repozytorium. Nie commituj swoich kluczy.

### Krok 4. Utwórz środowisko jedną komendą

```bash
uv sync
```

Co się stanie automatycznie:

1. `uv` pobierze odpowiednią wersję Pythona (projekt wymaga **>= 3.11**),
2. utworzy katalog `.venv/` w projekcie,
3. zainstaluje wszystkie zależności z `pyproject.toml` (Polars, Pandas, pandasql, matplotlib, …),
4. wygeneruje plik blokady `uv.lock` (gwarantuje te same wersje u wszystkich).

### Krok 5. Uruchom analizę

Kolejność jest istotna — skrypt `01` tworzy plik CSV, z którego korzystają pozostałe:

```bash
uv run python scripts/01_fetch_openalex.py        # pobranie danych -> data/works_topic_*.csv
uv run python scripts/02_analysis_polars.py       # analiza w Polars
uv run python scripts/03_analysis_pandas.py       # analiza w Pandas
uv run python scripts/04_analysis_sql.py          # analiza w SQL (pandasql)
uv run python scripts/05_compare_results.py       # porównanie + wykresy
```

`uv run` automatycznie używa środowiska `.venv` — **nie trzeba go aktywować** (`source .venv/bin/activate` jest zbędne).

Wyniki pojawią się w katalogu `reports/` — w **XLSX, CSV i Markdown** — oraz w `reports/figures/` (PNG + SVG). Pliki CSV (`wyniki_*_*.csv`, `meta_*_*.csv`, `porownanie_*_*.csv`) otworzysz w każdej przeglądarce i edytorze tekstu, więc **nie trzeba instalować LibreOffice ani Excela**, żeby pokazać wyniki.

---

## Praca w VS Code (Python Interactive Window)

Skrypty mają znaczniki `# %%` (komórki). Aby uruchamiać je komórka po komórce:

1. Otwórz projekt w VS Code.
2. Wybierz interpreter: `Ctrl/Cmd + Shift + P` → **Python: Select Interpreter** → `.venv/bin/python`.
3. Otwórz skrypt (np. `scripts/02_analysis_polars.py`) i uruchom komórkę: **Run Cell** (ikonka nad `# %%`) lub `Shift + Enter`.
4. Pierwsza komórka w każdym skrypcie dodaje katalog `scripts/` do `sys.path`, więc import `common` działa od razu.

---

## Struktura projektu

```text
Polars_vs_pandas_openalex_dataset/
├── config/
│   └── topic.yaml              # KEYWORDS, TOPIC_CONTEXT_TERMS, RESEARCH_TOPIC
├── scripts/
│   ├── common.py               # YAML, .env, ścieżki, zapis wyników
│   ├── 01_fetch_openalex.py    # API OpenAlex -> data/works_topic_*.csv
│   ├── 02_analysis_polars.py   # Q1-Q11 w Polars
│   ├── 03_analysis_pandas.py   # Q1-Q11 w Pandas
│   ├── 04_analysis_sql.py      # Q1-Q11 w SQL (pandasql)
│   └── 05_compare_results.py   # zgodność wyników + wykresy
├── data/                       # dataset CSV (nazwa z timestampem)
├── reports/                    # XLSX + CSV + Markdown
│   └── figures/                # wykresy PNG + SVG
├── prezentacja.md              # prezentacja w formacie Marp
├── .env                        # OPENALEX_API_KEY (nie commitujemy)
└── pyproject.toml              # definicja zależności
```

Aby zmienić temat kwerendy, edytuj wyłącznie `config/topic.yaml` — kod pozostaje bez zmian.

---

## Najczęstsze problemy

| Objaw | Przyczyna | Rozwiązanie |
|---|---|---|
| `command not found: uv` | terminal nie odświeżył `PATH` | zamknij i otwórz terminal ponownie (lub `source $HOME/.local/bin/env`) |
| `No solution found` przy `uv sync` | brak zgodnej wersji Pythona | `uv python install 3.11`, następnie `uv sync` |
| `FileNotFoundError: Brak datasetu` | uruchomiono analizę przed pobraniem | najpierw `uv run python scripts/01_fetch_openalex.py` |
| Puste kolumny w CSV | brak klucza w `.env` | uzupełnij `OPENALEX_API_KEY` i uruchom `01` ponownie |
| Błąd importu `common` | uruchomienie z innego katalogu | uruchamiaj przez `uv run python scripts/...` z katalogu głównego projektu |
| `ModuleNotFoundError: polars` | pominięto `uv sync` | wykonaj `uv sync` |

---

## Podgląd prezentacji (Marp)

Plik `prezentacja.md` używa formatu Marp. Najprościej podejrzeć go w VS Code z rozszerzeniem **Marp for VS Code** (podgląd: ikonka „Preview” w prawym górnym rogu). Ewentualnie przez CLI (wymaga Node.js):

```bash
npx @marp-team/marp-cli prezentacja.md --preview
```
