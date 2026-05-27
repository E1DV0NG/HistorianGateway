# Analýza a struktura kódu — eHistorian Gateway

Tento dokument popisuje celkovou architekturu projektu **eHistorianGateway**, fungování jeho jednotlivých částí a obsahuje návrhy na zjednodušení či restrukturalizaci kódu.

---

## 1. Celková architektura a princip fungování

Projekt reprezentuje **průmyslovou datovou bránu (Gateway)** pro sběr dat ze senzorů a zařízení (zdroje OPC UA a SQL databáze) a jejich odesílání do centrálního serveru. Systém se skládá ze tří hlavních částí:

1. **Unified Server (`server.py`)**:
   - Flask aplikace běžící na portu `5000`.
   - Slouží jako webový administrační panel (Control Panel) a zároveň simuluje vzdálené API.
   - Poskytuje API pro spuštění/zastavení brány, úpravu konfigurace a stahování logů.
   - Přijímá odeslaná data na endpointu `/api/ehistorian/gateway/ingest` a ukládá je do složky `logs/` jako `.json` soubory.

2. **eHistorian Gateway (`ehistorian_gateway`)**:
   - Samostatná konzolová aplikace napsaná s využitím asynchronního frameworku `asyncio`.
   - Načte konfiguraci (buď lokálně z bootstrap souboru, nebo vzdáleně ze serveru).
   - Spustí asynchronní sběrače dat (kolektory) pro OPC UA a SQL.
   - Data procházejí **pipeline**:
     - **Normalizer**: Převádí specifické události ze zdrojů na jednotný formát `UnifiedEvent`.
     - **Batcher**: Seskupuje události do dávek (podle času nebo velikosti).
     - **SQLite Queue (`sqlite_queue.py`)**: Ukládá dávky do lokální SQLite databáze. Tím je zajištěna odolnost proti výpadku sítě (offline buffer).
     - **Sender Loop**: Na pozadí čte dávky z SQLite a odesílá je přes HTTP REST API na server. Pokud odeslání selže, aplikuje se exponenciální zpětné čekání (backoff) a dávka se zkusí odeslat znovu.
   - Běží zde také vestavěný lehký TCP server na portu `8088`, který poskytuje stavové informace a metriky (endpoint `/health`).

3. **Webové UI (`ui/`)**:
   - Single Page Application (SPA) postavená na čistém HTML, CSS a JavaScriptu.
   - Komunikuje s Flask serverem. Umožňuje spravovat OPC UA a SQL zdroje, sledovat stav brány, stahovat a mazat logy a ručně vyvolat testovací událost.

---

## 2. Detailní struktura kódu a popis částí

Níže je uvedena kompletní adresářová struktura s popisem funkčnosti každého souboru.

### Hlavní adresář projektu
| Soubor / Složka | Typ | Popis |
| :--- | :--- | :--- |
| `server.py` | Soubor | Hlavní Flask server zajišťující webové rozhraní, správu konfigurace a simulaci příjmu dat (ingest). Spouští proces brány jako podproces. |
| `ui/` | Složka | Statické soubory uživatelského rozhraní (HTML, CSS, JS). |
| `eHistorian.Gateway/` | Složka | Zdrojové kódy samotné datové brány. |
| Spouštěcí `.bat` soubory | Soubory | Skripty pro usnadnění instalace virtuálního prostředí a spouštění na platformě Windows (`START_ALL.bat`, `run_server.bat`, atd.). |

---

### Složka `ui/` (Uživatelské rozhraní)
- **`index.html`**: Struktura administrátorské stránky. Obsahuje záložky pro Dashboard, Nastavení (OPC UA / SQL), Prohlížeč konfigurace v JSON a správu logů.
- **`styles.css`**: Kaskádové styly definující vizuální vzhled (tmavé rozvržení, layouty karet, tabulky a responzivitu).
- **`app.js`**: Klientská logika. Pravidelně se dotazuje na stav brány, odesílá požadavky na spuštění/zastavení procesů, dynamicky generuje formuláře pro přidávání/odebírání zdrojů a vykresluje seznam logů.

---

### Složka `eHistorian.Gateway/ehistorian_gateway/` (Jádro brány)
- **`main.py`**: Centrální bod aplikace. Inicializuje asynchronní smyčku, spouští a zastavuje sběrače při změně konfigurace, spouští normalizátor, batcher, odesílací smyčku a lehký HTTP server na socketu pro stav /health.
- **`config/`**
  - **`manager.py`**: Zajišťuje načtení konfigurace. Nejprve se pokusí stáhnout konfiguraci ze vzdáleného API. Pokud selže, použije lokální bootstrap soubor. Obsahuje metodu `watch`, která v pravidelných intervalech kontroluje změny konfigurace na serveru a při změně vyvolá callback.
- **`models/`**
  - **`config.py`**: Datové třídy (Dataclasses) reprezentující konfiguraci brány, OPC UA zdrojů a SQL zdrojů. Zahrnuje serializaci z/do slovníku (JSON).
  - **`event.py`**: Definice datových modelů pro události (`SourceEvent` z kolektorů, `UnifiedEvent` po normalizaci a `PersistedBatch` pro uložení do databáze).
- **`opcua/`**
  - **`client.py`**: Správce připojení k OPC UA serveru. V případě odpojení realizuje automatické znovupřipojení s exponenciálním čekáním.
  - **`subscription_manager.py`**: Nastavuje asynchronní odběr změn (Subscription) na OPC UA uzlech. Třída `OpcUaSubscriptionHandler` reaguje na změnu hodnoty uzlu a publikuje ji do sběrnice jako `SourceEvent`.
- **`pipeline/`**
  - **`event_bus.py`**: Generická asynchronní fronta (obálka nad `asyncio.Queue`) sloužící jako komunikační sběrnice mezi komponentami. Měří metriky (počet publikovaných a dropovaných zpráv, maximální zaplnění fronty).
  - **`normalizer.py`**: Běží jako samostatná asynchronní úloha. Odebírá raw události z `source_bus`, validuje jejich kvalitu, doplňuje ID brány a posílá je do `target_bus` jako `UnifiedEvent`.
  - **`batcher.py`**: Seskupuje normalizované události do dávek. K zápisu dávky do SQLite dochází buď při dosažení limitu velikosti (`batch_size`), nebo po uplynutí časového intervalu (`batch_flush_interval_seconds`).
- **`sender/`**
  - **`rest_client.py`**: Zajišťuje fyzické odeslání dávky dat na cílový server pomocí POST požadavku. Využívá `urllib.request` spouštěný asynchronně ve vlákně přes `asyncio.to_thread`.
  - **`retry.py`**: Vypočítává zpoždění před dalším pokusem o odeslání při selhání sítě (exponenciální nárůst s přidaným náhodným šumem/jitterem pro zamezení zahlcení serveru).
- **`sql/`**
  - **`change_detector.py`**: Porovnává aktuálně načtené hodnoty z SQL s předchozím stavem. Zajišťuje, že se dále do pipeline pošlou pouze skutečně změněné hodnoty (minimalizuje duplicitu).
  - **`sql_client.py`**: Zajišťuje fyzické připojení k relační databázi pomocí pyodbc. Sestavuje dynamický dotaz SELECT na základě konfigurace a validuje názvy tabulek a sloupců proti SQL injection.
  - **`sql_poller.py`**: Pravidelně v intervalu `polling_ms` spouští dotaz do SQL databáze přes `SqlClient`, filtruje výsledky přes `ChangeDetector` a změněné záznamy odesílá do sběrnice.
- **`storage/`**
  - **`sqlite_queue.py`**: Asynchronní rozhraní pro SQLite (`aiosqlite`). Zajišťuje transakční chování fronty zpráv (FIFO). Dávka se označí jako `sending`, a buď se smaže po úspěšném odeslání (`mark_sent`), nebo se vrátí do stavu `pending` s novým časem dostupnosti při chybě (`mark_retry`).
- **`utils/`**
  - **`logging.py`**: Nastavuje jednotné formátování logů do formátu JSON (vhodné pro centralizované zpracování logů).

---

## 3. Analýza možností zjednodušení a refaktorizace (Restrukturalizace)

Při analýze kódu byly identifikovány následující oblasti, kde by zjednodušení nebo drobná restrukturalizace přispěla k vyšší efektivitě, lepší čitelnosti a spolehlivosti kódu:

### A. Správa připojení k SQLite (aiosqlite)
- **Současný stav**: V `sqlite_queue.py` se v každé metodě (`enqueue_batch`, `lease_next_batch`, `mark_sent`, `mark_retry`, `pending_count`) otevírá a ihned zavírá nové připojení k databázi pomocí bloku `async with aiosqlite.connect(self._path) as db`.
- **Doporučená restrukturalizace**: Vytvořit a držet jedno sdílené připojení k SQLite po celou dobu běhu instance `SQLiteQueue` (otevřít při inicializaci a zavřít při shutdownu brány). Tím se eliminuje režie spojená s neustálým otevíráním souboru na disku a inicializací knihovny SQLite, což výrazně zrychlí zápisy a čtení dávek.

### B. Přechod na plně asynchronního HTTP klienta
- **Současný stav**: Knihovna `urllib.request` použitá v `rest_client.py` a `config/manager.py` je blokující (synchronní). Kód toto omezení obchází voláním `await asyncio.to_thread(fetch)`.
- **Doporučená restrukturalizace**: Nahradit `urllib` plně asynchronním HTTP klientem (např. `httpx` nebo `aiohttp`). To by zjednodušilo kód, eliminovalo nutnost správy systémových vláken přes `to_thread` a umožnilo nativní asynchronní timeouty a efektivnější sdílení HTTP connections (Connection Pooling).

### C. Duplicita kódu pro ošetření chyb a opětovné připojení (Backoff)
- **Současný stav**: V `opcua/client.py` (řádky 41-50) a `sql/sql_poller.py` (řádky 50-59) je duplicitně naimplementována logika pro exponenciální zpětné čekání (backoff) při selhání připojení/dotazu.
- **Doporučená restrukturalizace**: Zobecnit výpočet a správu stavu backoffu do samostatné pomocné třídy (např. `BackoffTracker` v rámci složky `utils`), nebo znovu použít stávající třídu `RetryPolicy` ze složky `sender/retry.py` s drobnou úpravou parametrů.

### D. Blokující chování EventBus při zaplnění
- **Současný stav**: Třída `EventBus` ve svém rozhraní definuje metriku `dropped` (ztracené zprávy), ale v metodě `publish` volá pouze `await self._queue.put(item)`. Pokud fronta dosáhne limitu `maxsize`, asynchronní úloha (např. OPC UA handler nebo SQL poller) se zablokuje a čeká, dokud se neuvolní místo. Zprávy se reálně nikdy nedropují.
- **Doporučená restrukturalizace**: Pokud je cílem data při přetížení zahazovat (dropovat), měla by metoda `publish` používat synchronní metodu `put_nowait()` odchycenou v bloku `try-except asyncio.QueueFull`. Pokud se fronta zaplní, zpráva se zahodí a inkrementuje se čítač `dropped`. Pokud je chování blokováním žádoucí, měla by se z třídy `EventBusMetrics` odstranit nepoužívaná metrika `dropped`.

### E. Zjednodušení ručního parsování HTTP v health serveru
- **Současný stav**: V `main.py` (metoda `_run_health_server`, řádky 182-230) je implementován vlastní jednoúčelový HTTP parser nad surovým TCP socketem přes `asyncio.start_server`. Kód ručně čte řádky, parsuje text `GET /health ` a skládá HTTP hlavičky odpovědi jako bajtové řetězce.
- **Doporučená restrukturalizace**: Ačkoliv je toto řešení funkční a nezávislé na externích knihovnách, zvyšuje riziko chyb při nestandardních HTTP požadavcích. Vhodnější by bylo použít lehkou asynchronní knihovnu (např. `aiohttp` nebo `FastAPI` / `Starlette`), která by jedním dekorátorem nahradila celou definici TCP socketu a parsování.
