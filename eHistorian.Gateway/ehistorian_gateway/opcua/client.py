from __future__ import annotations

import asyncio
import logging

from asyncua import Client

from ehistorian_gateway.models.config import OpcUaSourceConfig
from ehistorian_gateway.opcua.subscription_manager import SubscriptionManager
from ehistorian_gateway.pipeline.event_bus import EventBus
from ehistorian_gateway.models.event import SourceEvent


class OpcUaSourceRunner:
    def __init__(self, source_id: str, config: OpcUaSourceConfig, event_bus: EventBus[SourceEvent], stop_event: asyncio.Event, on_error=None) -> None:
        self._source_id = source_id
        self._config = config
        self._event_bus = event_bus
        self._stop_event = stop_event
        self._on_error = on_error
        self._logger = logging.getLogger("ehistorian_gateway.opcua")

    async def run(self) -> None:
        backoff = 1.0
        
        while not self._stop_event.is_set():
            # Inicializace klienta - bezpečnější je držet instanci čistou pro každý pokus
            client = Client(url=self._config.url)
            subscription_manager: SubscriptionManager | None = None
            
            try:
                self._logger.debug("Attempting to connect to OPC UA server", extra={"source_id": self._source_id, "url": self._config.url})
                
                # POJISTKA 1: Timeout na připojení (např. 10 sekund), ať gateway nezamrzne
                await asyncio.wait_for(client.connect(), timeout=10.0)
                
                # POJISTKA 3: Zapnutí Keep-Alive (posílá ping každých X sekund). 
                # Pokud server neodpoví, spojení se přeruší a vyvolá se výjimka do except bloku.
                # (interval si uprav podle potřeby, např. 30s)
                # client.start_keepalive(30) # Od asyncua v3+ je to často automatické, ale explicitní registrace neuškodí, případně přes event handler.

                subscription_manager = SubscriptionManager(
                    client=client,
                    asset_id=self._config.asset_id,
                    source_id=self._source_id,
                    sampling_ms=self._config.sampling_ms,
                    tags=self._config.tags,
                    event_bus=self._event_bus,
                )
                await subscription_manager.start()
                
                self._logger.info("Connected OPC UA source", extra={"source_id": self._source_id, "url": self._config.url})
                backoff = 1.0
                
                # Čekáme na stop signál. Pokud mezitím spadne spojení na pozadí knihovny asyncua, 
                # musíme zajistit, aby to probralo tento task. asyncua obvykle shodí probíhající čtení/subscriptions.
                await self._stop_event.wait()
                
            except Exception as exc:
                self._logger.warning(
                    "OPC UA source connection error or disconnected",
                    extra={"source_id": self._source_id, "url": self._config.url, "error": str(exc), "backoff_seconds": backoff},
                )
                if self._on_error:
                    import traceback
                    self._on_error(self._source_id, f"Error: {str(exc)}\n\nTraceback:\n{traceback.format_exc()}")
                
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                
                backoff = min(backoff * 2, 30.0)
                
            finally:
                # Korektní a bezpečné ukončení v opačném pořadí
                if subscription_manager is not None:
                    try:
                        await subscription_manager.stop()
                    except Exception as e:
                        self._logger.debug("Ignoring OPC UA subscription shutdown error", extra={"source_id": self._source_id, "error": str(e)})
                
                try:
                    # Před odpojením je dobré stopnout keepalive, pokud byl explicitně spuštěn
                    # client.close_keepalive() 
                    await client.disconnect()
                except Exception as e:
                    self._logger.debug("Ignoring OPC UA client disconnect error", extra={"source_id": self._source_id, "error": str(e)})