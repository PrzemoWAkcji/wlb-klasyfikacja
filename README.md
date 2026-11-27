# Klasyfikacja WLB

Klasyfikacja generalna Warszawskiej Ligi Biegowej liczona z wyników w Roster Athletics,
osobno dla dystansu, rocznika i płci, według regulaminu WLB.

Strona: https://przemowakcji.github.io/wlb-klasyfikacja/

## Jak to działa

> **Archiwum wyników.** Wyniki imienne publikujemy wyłącznie dla sezonu 2026, do 90 dni po ogłoszeniu klasyfikacji końcowej. Sezony 2024–2025 nie są pobierane ani przechowywane (`ra.first_season()`). Rekordy ligi zostają na stałe w `data/records-archiwum.json` (tylko imię i nazwisko, rocznik, klub, wynik i data) i są wliczane do pola `records`. Numerów zawodników z Roster w danych strony nie ma.

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

## Monitor finału i Telegram

`monitor.py` obsługuje halowe rekordy WLB (również wyrównania) oraz podium
całego cyklu. Podium czeka na `resultsComplete=true` w nadrzędnej konkurencji
i wszystkich jej seriach. Kategorie łączone rozdzielane są według rocznika.
Nierozstrzygnięty remis jest oznaczany do decyzji organizatora.
Monitor rozpoznaje korekty/usunięcia wyników i ponowne otwarcie konkurencji.

Wdrożenie: VM `aplikacja`, `/home/przemo/opt/wlb-monitor`, usługi użytkownika
z `deploy/`. Timer uruchamia monitor 13.12.2026 o 08:00 czasu Warszawy;
monitor kończy pracę po 14.12 (pozostawia dzień na korekty).
Przed startem `fetch.py` odświeża wcześniejsze rundy. Finał jest wyszukiwany
po dacie i organizatorze; wymagany jest jeden wynik wyszukiwania oraz hala.
Brak finału oznacza ponowienie wyszukiwania, nie wybór innych zawodów.

Konfiguracja według `deploy/config.example.json` znajduje się w
`~/.config/wlb-monitor/config.json` (uprawnienia 600). Token wyłącznie tam,
poza Git. Stan alertów w `data/state.json` na VM zachowuje wysłane powiadomienia
przez restarty. Nie usuwać stanu w trakcie finału. Oddzielny stan testowy:
`data/dry-state.json`. Blokada pliku uniemożliwia równoległe monitory.
Przy niejednoznacznym błędzie sieci podczas wysyłki Telegram może przy ponowieniu
dostarczyć duplikat — API nie zapewnia klucza idempotencji.

Kontrola na VM:

```bash
systemctl --user status wlb-monitor.timer wlb-monitor.service
journalctl --user -u wlb-monitor.service -n 50
```

Testy lokalne: `python3 -m unittest discover -s tests -v`.
Tryb bez wysyłki: `python3 monitor.py --config /ścieżka/test.json --once --dry-run`.
Dla prób na starszej rundzie ustaw jej datę i właściwe `expected_prior_rounds`.
Monitor nie zmienia publicznej strony ani archiwum rekordów.

Stan instalacji 16.11.2026: monitor zainstalowany na VM; bot
`@WLB_2026_2027_bot` podłączony do grupy `WLB`. Telegram potwierdził wysłanie
wiadomości testowej. Prywatna konfiguracja ma uprawnienia 600. Timer włączony,
start 13.12.2026 o 08:00 Europe/Warsaw. Sam monitor do tego czasu nie pracuje.
