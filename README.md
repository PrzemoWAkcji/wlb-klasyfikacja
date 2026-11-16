# Klasyfikacja WLB

Klasyfikacja generalna Warszawskiej Ligi Biegowej liczona z wyników w Roster Athletics,
osobno dla dystansu, rocznika i płci, według regulaminu WLB.

Strona: https://przemowakcji.github.io/wlb-klasyfikacja/

## Jak to działa

> **Archiwum wyników.** Wyniki imienne publikujemy przez 3 sezony: bieżący i dwa poprzednie (teraz 2024–2026), zgodnie z ustaleniem z inspektorem ochrony danych (regulamin WLB). Starsze sezony nie są pobierane ani przechowywane (`ra.first_season()`). Rekordy ligi zostają na stałe w `data/records-archiwum.json` (tylko imię i nazwisko, rocznik, klub, wynik i data) i są wliczane do pola `records`. Numerów zawodników z Roster w danych strony nie ma.

GitHub Actions ([.github/workflows/update.yml](.github/workflows/update.yml)) uruchamia `update.py`
w niedzielę wieczorem (po rundzie) i w środę (korekty po protestach). Gdy pojawią się nowe wyniki,
commituje `site/index.html` i publikuje go na GitHub Pages. Ręcznie: zakładka **Actions → Odświeżenie klasyfikacji → Run workflow**.

## Pliki

- `update.py` – pełne odświeżenie (terminarz + wyniki + przeliczenie). Ostatnia linia: `ZMIANA` / `BEZ ZMIAN`.
- `plan.py` – czyta terminarz rund z regulaminu na warszawskaligabiegowa.pl → `data/plan.json`.
- `fetch.py` – pobiera wyniki wszystkich rund organizatora (orgId 315) z publicznego API Roster Athletics → `data/raw/<meetingId>.json` (poza repozytorium, w cache Actions). Rundy z ostatnich 14 dni pobiera ponownie.
- `build.py` – liczy klasyfikację (min. 7 startów, suma 7 najlepszych, remis = najlepszy czas w sezonie; biegi łączone przeliczane per rocznik) i wstawia dane do `template.html` → `site/index.html`.
- `ra.py` – mały klient API oraz `first_season()` (granica publikowanych sezonów).
- `data/records-archiwum.json` – najlepszy wynik w każdym sezonie dla rekordów WLB; przeliczane sezony nadpisują swoje wpisy, starsze zostają (commitowany przez workflow).

## Lokalnie

```bash
python update.py
```

Wynik: `site/index.html` (otwórz w przeglądarce). Wymaga tylko Pythona 3, bez dodatkowych bibliotek.
