import asyncio
import logging
import sys
import time

import atheris  # type: ignore

with atheris.instrument_imports():
    from iso15118.evcc import Config as EVCCConfig
    from iso15118.evcc import EVCCHandler
    from iso15118.evcc.controller.simulator import SimEVController
    from iso15118.evcc.evcc_config import load_from_file
    from iso15118.shared.exificient_exi_codec import (
        ExificientEXICodec as EVCCExificientEXICodec,
    )

atheris.FuzzInjector().dump()  # 648 LOAD_FAST, 1124 LOAD_CONST

from iso15118.secc import SECCHandler
from iso15118.secc.controller.interface import ServiceStatus
from iso15118.secc.controller.simulator import SimEVSEController
from iso15118.secc.secc_settings import Config as SECCConfig
from iso15118.shared.exificient_exi_codec import (
    ExificientEXICodec as SECCExificientEXICodec,
)

logger = logging.getLogger(__name__)


async def main():
    """
    Entrypoint function that starts the ISO 15118 code running on
    the EVCC (EV Communication Controller)
    """
    secc_config = SECCConfig()
    secc_config.load_envs()
    evcc_config = EVCCConfig()
    evcc_config.load_envs()
    evcc_file_config = await load_from_file(evcc_config.ev_config_file_path)
    evcc_file_config.charge_loop_delay_time = 0

    sim_evse_controller = SimEVSEController()
    await sim_evse_controller.set_status(ServiceStatus.STARTING)
    await asyncio.gather(
        SECCHandler(
            exi_codec=SECCExificientEXICodec(),
            evse_controller=sim_evse_controller,
            config=secc_config,
        ).start(secc_config.iface),
        EVCCHandler(
            evcc_config=evcc_file_config,
            iface=evcc_config.iface,
            exi_codec=EVCCExificientEXICodec(),
            ev_controller=SimEVController(evcc_file_config),
        ).start(),
    )


def run(data: bytes = b""):
    injector = atheris.FuzzInjector()
    l: list[int] = injector.mutation_list
    n = len(l)
    l.clear()
    fdp = atheris.FuzzedDataProvider(data)
    for i in range(n):
        value = fdp.ConsumeInt(4)
        l.append(value)
    logger.info(f"data length: {len(data)}, list length {len(l)} list {l}")
    start_time = time.time()
    logger.info("Running main")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    finally:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        asyncio.set_event_loop(None)
    logger.info(f"Running main done, Time: {time.time() - start_time:.2f} s")


if __name__ == "__main__":
    atheris.Setup(sys.argv, run)
    atheris.Fuzz()
    # run()
