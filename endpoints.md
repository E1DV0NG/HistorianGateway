# Přehled Endpointů v eHistorian Gateway

Gateway komunikuje primárně se serverovým API (odchozí požadavky) a vystavuje jeden lokální endpoint pro zjištění svého stavu (příchozí požadavky). Zde je jejich kompletní přehled včetně míst, kde je lze v kódu najít nebo upravit.

## 1. Odchozí endpointy na Server (Server API)
Tyto endpointy se skládají z kořenové adresy `apiUrl` (nastavené v konfiguraci) a specifické cesty.

### Načítání konfigurace
* **Endpoint:** `GET {apiUrl}/api/ehistorian/gateway/config/{gatewayId}`
* **Účel:** Slouží k automatickému (hot-reload) stahování konfigurace pro danou gateway.
* **Kde se upravuje:** [manager.py](file:///d:/HistorianGateway/eHistorian.Gateway/ehistorian_gateway/config/manager.py#L111)

### Odesílání dat (Ingest)
* **Endpoint:** `POST {apiUrl}/api/ehistorian/gateway/ingest`
* **Účel:** Odesílání shromážděných a normalizovaných dat (eventů) v dávkách na server.
* **Kde se upravuje:** [rest_client.py](file:///d:/HistorianGateway/eHistorian.Gateway/ehistorian_gateway/sender/rest_client.py#L30)

### Reportování stavu konfigurace
* **Endpoint:** `POST {apiUrl}/api/ehistorian/gateway/config-status`
* **Účel:** Informuje server o tom, zda se gateway úspěšně přepnula na novou konfiguraci nebo zda nastala chyba.
* **Kde se upravuje:** [test_component.py (report_config_status)](file:///d:/HistorianGateway/eHistorian.Gateway/ehistorian_gateway/test_component.py#L6)

### Odesílání Health statistik
* **Endpoint:** `POST {apiUrl}/api/ehistorian/gateway/health-status`
* **Účel:** Pravidelné (každých 30 vteřin) odesílání "health" metrik samotné gateway (fronty, stav kolektorů, časy posledního odeslání atd.) na server. Odesílá se **pouze** pokud je v configu zapnuto `sendLogs=1`. 
* **Zpracování chyb:** Nově v sobě payload nese atribut `collectorErrors`. V případě pádu jednoho ze sběračů (OPC UA nebo SQL) se k tomuto počítadlu přičte `+1` a konkrétní chyba (traceback) se zapíše do diskové mezipaměti `cache/errorLogs`. Pokud server na tento POST odpoví JSON tělem obsahujícím `{"resetErrorCount": 1}`, gateway tento čítač automaticky vynuluje a chyby počítá od znova.
* **Kde se upravuje:** [main.py (_health_reporter_loop)](file:///d:/HistorianGateway/eHistorian.Gateway/ehistorian_gateway/main.py#L239)

### Lokální Healthcheck
* **Endpoint:** `GET /health` (Lokální port `8088` na samotné gateway)
* **Účel:** Gateway vystavuje přesně ty samé informace z `health-status` pouze pro čtení komukoliv na lokální síti. Hodí se to např. na prozkoumání `collectorErrors` mimo server nebo zjištění základního zdravotního stavu přes Docker healthchecks či systémy typu Prometheus.
* **Kde se upravuje:** [main.py (_run_health_server)](file:///d:/HistorianGateway/eHistorian.Gateway/ehistorian_gateway/main.py#L274)

### Reportování statistik bufferu
* **Endpoint:** `POST {apiUrl}/api/ehistorian/gateway/buffer-status`
* **Účel:** Průběžné odesílání statistik o stavu lokální SQLite fronty (velikost, počet položek). Odesílá se pouze pokud je v configu zapnuto `sendLogs=1`.
* **Kde se upravuje:** [test_component.py (test_buffer_status_reporter)](file:///d:/HistorianGateway/eHistorian.Gateway/ehistorian_gateway/test_component.py#L45)


## 2. Lokální příchozí endpointy (Health Check)
Tento endpoint slouží pro dohledové systémy v rámci lokální sítě, kde gateway běží. Nastavení portu a bind IP se čte z proměnných `healthHost` a `healthPort`.

### Gateway Health Check
* **Endpoint:** `GET http://{healthHost}:{healthPort}/health` (standardně port `8088`)
* **Účel:** Vrací JSON s detailními metrikami o běhu gateway (fronty, stav kolektorů, časy posledního odeslání atd.).
* **Kde se upravuje:** [main.py (_run_health_server)](file:///d:/HistorianGateway/eHistorian.Gateway/ehistorian_gateway/main.py#L231)
