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
atheris.FuzzInjector().disable()
with atheris.instrument_imports():
    from iso15118.secc import SECCHandler
    from iso15118.secc.controller.interface import ServiceStatus
    from iso15118.secc.controller.simulator import SimEVSEController
    from iso15118.secc.secc_settings import Config as SECCConfig

    from iso15118.shared.exificient_exi_codec import ExificientEXICodec

logger = logging.getLogger(__name__)

secc_config = SECCConfig()
secc_config.load_envs()
evcc_config = EVCCConfig()
evcc_config.load_envs()
evcc_file_config = load_from_file(evcc_config.ev_config_file_path)
evcc_file_config.charge_loop_delay_time = 0

async def main():
    sim_evse_controller = SimEVSEController()
    await sim_evse_controller.set_status(ServiceStatus.STARTING)
    await asyncio.gather(
        SECCHandler(
            exi_codec=ExificientEXICodec(),
            evse_controller=sim_evse_controller,
            config=secc_config,
        ).start(secc_config.iface),
        EVCCHandler(
            evcc_config=evcc_file_config,
            iface=evcc_config.iface,
            exi_codec=ExificientEXICodec(),
            ev_controller=SimEVController(evcc_file_config),
        ).start(),
    )


def run(data: bytes = b""):
    injector = atheris.FuzzInjector()
    l: list[int] = injector.mutation_list
    n = len(l)
    l.clear()
    fdp = atheris.FuzzedDataProvider(data)
    import random

    random.seed(fdp.ConsumeInt(4))
    # random.seed(0)
    for i in range(n):
        value = 0
        # value = fdp.ConsumeInt(4)
        value = random.randint(0, 256)
        l.append(value)
    logger.info(f"data length: {len(data)}, list length {len(l)} list {l}")
    start_time = time.time()
    logger.info("Running main")
    timeout = 9
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.wait_for(main(), timeout=timeout))
    except asyncio.TimeoutError:
        logger.error(f"Main function timed out after {timeout} seconds")
    except Exception as e:
        raise e
    finally:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        asyncio.set_event_loop(None)
    logger.info(f"Running main done, Time: {time.time() - start_time:.2f} s")
    print(f"Running main done, Time: {time.time() - start_time:.2f} s")


if __name__ == "__main__":
    atheris.FuzzInjector().dump()  # 648 LOAD_FAST, 1124 LOAD_CONST
    if len(sys.argv) > 1 and sys.argv[1] == "--run_once":
        run()
    else:
        atheris.Setup(sys.argv, run)
        atheris.Fuzz()
