import asyncio
import logging
import sys
import time
from collections import Counter
from pathlib import Path

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
evcc_file_configs = []
for f in Path("iso15118/shared/examples/evcc").glob("**/*.json"):
    evcc_file_config = load_from_file(f.__str__())
    evcc_file_config.charge_loop_delay_time = 0
    evcc_file_configs.append(evcc_file_config)


class EVCCError(Exception):
    pass


run_count = 0


async def main(evcc_file_config):
    logger.info(f"Running with evcc_file_config: {evcc_file_config}")

    async def run_secc():
        await SECCHandler(
            exi_codec=ExificientEXICodec(),
            evse_controller=sim_evse_controller,
            config=secc_config,
        ).start(secc_config.iface)

    async def run_evcc():
        try:
            await EVCCHandler(
                evcc_config=evcc_file_config,
                iface=evcc_config.iface,
                exi_codec=ExificientEXICodec(),
                ev_controller=SimEVController(evcc_file_config),
            ).start()
        except Exception as e:
            logger.error(f"EVCC terminated: {e}")
            raise EVCCError(e)

    sim_evse_controller = SimEVSEController()
    await sim_evse_controller.set_status(ServiceStatus.STARTING)
    await asyncio.gather(run_secc(), run_evcc())


counter = Counter()
KNOWN_MUTATION_COUNTER = {
    298: 34105,
    338: 20936,
    308: 17050,
    379: 15356,
    469: 1880,
    26: 1135,
    435: 1038,
    23: 852,
    385: 852,
    386: 852,
    393: 847,
    394: 847,
    31: 847,
    11: 847,
    12: 847,
    332: 847,
    175: 377,
    176: 377,
    54: 377,
    459: 94,
    111: 94,
}


def generate_config(fdp, run_count):
    i = run_count % len(evcc_file_configs)
    evcc_file_config = evcc_file_configs[i]
    return evcc_file_config


def run(data: bytes = b""):
    global run_count
    injector = atheris.FuzzInjector()
    l: list[int] = injector.mutation_list
    n = len(l)
    idx_list = [i for i in range(n)]
    idx_list.sort(key=lambda x: KNOWN_MUTATION_COUNTER.get(x, 0), reverse=True)
    l.clear()
    fdp = atheris.FuzzedDataProvider(data)
    evcc_file_config = generate_config(fdp, run_count)
    import random

    # random.seed(fdp.ConsumeInt(4))
    # random.seed(0)
    for _ in range(n):
        l.append(0)
    for i in range(n):
        if run_count < len(evcc_file_configs):
            continue
        l[idx_list[i]] = fdp.ConsumeUInt(1)
        # l[i] = random.randint(0, 255)
    logger.info(f"data length: {len(data)}, list length: {len(l)}, mutation list: {l}")
    start_time = time.time()
    logger.info(f"Running main #{run_count}")
    timeout = 15
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            asyncio.wait_for(main(evcc_file_config), timeout=timeout)
        )
        counter["normal"] += 1
    except asyncio.TimeoutError:
        logger.error(f"Main function timed out after {timeout} seconds")
        counter["timeout"] += 1
    except EVCCError as e:
        logger.error(f"EVCCError: {e}")
        counter[f"evcc_error_{e.args[0].__class__.__name__}"] += 1
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
    logger.info(
        f"Running main done #{run_count}, "
        f"Time: {time.time() - start_time:.2f} s, "
        f"Counter: {counter}"
    )
    run_count += 1
    atheris.FuzzInjector().dump(False, False, False, True)


if __name__ == "__main__":
    atheris.FuzzInjector().dump()  # 648 LOAD_FAST, 1124 LOAD_CONST
    if len(sys.argv) > 1 and sys.argv[1] == "--run_once":
        for _ in evcc_file_configs:
            run()
    elif len(sys.argv) > 1 and sys.argv[1] == "--run_no":
        exit(0)
    else:
        atheris.Setup(sys.argv, run)
        atheris.Fuzz()
