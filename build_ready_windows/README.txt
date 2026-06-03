eHistorian Gateway - Produkèní Build
Tato složka obsahuje zkompilovanou produkèní verzi eHistorian Gateway, která bìží na pozadí a zprostøedkovává sbìr dat z OPC UA a SQL zdrojù.

Èistá instalace
Pokud chcete gateway nasadit na nový èistý stroj nebo server, není potøeba instalovat Python ani žádné závislosti. Ke zprovoznìní staèí pouze dva soubory:

eHistorianGateway.exe (samotný program)
default.json (výchozí bootstrap konfigurace)
Tyto dva soubory zkopírujte do libovolné prázdné složky na cílovém serveru (napø. C:\eHistorianGateway\).

Spuštìní
Nejjednodušší zpùsob je dvojklik na eHistorianGateway.exe. Aplikace se pøi startu podívá do stejné složky, automaticky si naète soubor default.json a pøipojí se k centrálnímu serveru (API). Pokud používáte pro konfiguraèní soubor jiný název, je nutné ho pøedat pøes pøíkazovou øádku:

powershell
.\eHistorianGateway.exe --bootstrap muj_config.json
Automaticky generované soubory
Hned po prvním úspìšném startu si gateway vedle sebe vytvoøí tyto složky, aby do nich mohla bezpeènì pracovat:

/cache - Zde se ukládá poslední platná konfigurace (current_active.json) pro pøípad, že vypadne spojení se serverem. Také zde naleznete podsložku errorLogs s detailními výpisy, pokud selže pøipojení na OPC UA nebo SQL zdroje.
/data - Obsahuje lokální SQLite databázi (offline-buffer.db), kam se bezpeènì ukládají nasbíraná data, pokud zrovna není dostupné internetové pøipojení na hlavní API, aby se nic neztratilo.
(Poznámka: Chcete-li gateway kompletnì zresetovat do továrního nastavení a smazat historii, staèí pøed jejím spuštìním smazat tyto dvì automaticky vytvoøené složky cache a data).

