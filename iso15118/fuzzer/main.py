import asyncio
import json
import logging
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict

import atheris  # type: ignore

from iso15118.fuzzer.consts import KNOWN_MUTATION_COUNTER
from iso15118.shared_evcc.messages.enums import EnergyTransferModeEnum

with atheris.instrument_imports():
    from iso15118.evcc import Config as EVCCConfig
    from iso15118.evcc import EVCCHandler
    from iso15118.evcc.controller.simulator import SimEVController
    from iso15118.evcc.evcc_config import load_from_file, EVCCConfig as EVCCFileConfig
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
        finally:
            pass

    sim_evse_controller = SimEVSEController()
    await sim_evse_controller.set_status(ServiceStatus.STARTING)
    await asyncio.gather(run_secc(), run_evcc())


counter = Counter()

def generate_config(fdp, run_count) -> EVCCConfig:
    conf_data: Dict[str, object] = {}

    # Generate supportedEnergyServices with at least one valid entry
    valid_services = [
        "AC",
        "DC",
        "WPT",
        "DC_ACDP",
        "AC_BPT",
        "DC_BPT",
        "DC_ACDP_BPT",
        "INTERNET",
        "PARKING_STATUS",
    ]
    # num_services = fdp.ConsumeIntInRange(1, 9)
    supported_energy_services = []
    supported_energy_services = valid_services
    # for _ in range(num_services):
    #     if not supported_energy_services or fdp.ConsumeBool():
    #         supported_energy_services.append(fdp.PickValueInList(valid_services))
    conf_data["supportedEnergyServices"] = supported_energy_services

    # Generate supportedProtocols with at least one valid entry
    valid_protocols = [
        "ISO_15118_20_AC",
        "ISO_15118_20_DC",
        "ISO_15118_2",
        "DIN_SPEC_70121",
    ]
    num_protocols = fdp.ConsumeIntInRange(1, 4)
    supported_protocols = []
    for _ in range(num_protocols):
        if not supported_protocols or fdp.ConsumeBool():
            supported_protocols.append(fdp.PickValueInList(valid_protocols))
    conf_data["supportedProtocols"] = supported_protocols

    conf_data["isCertInstallNeeded"] = False
    conf_data["useTls"] = False
    conf_data["enforceTls"] = False
    conf_data["sdpRetryCycles"] = 1
    conf_data["maxContractCerts"] = 3
    conf_data["maxSupportingPoints"] = 1024
    conf_data["chargeLoopCycle"] = 10
    conf_data["chargeLoopDelay"] = 0

    # Handle energyTransferMode as valid enum name
    try:
        energy_modes = [e.value for e in EnergyTransferModeEnum]
        conf_data["energyTransferMode"] = fdp.PickValueInList(energy_modes)
    except IndexError:
        pass  # Skip if no enum members

    if run_count < len(evcc_file_configs):
        return evcc_file_configs[run_count]
    try:
        config = EVCCFileConfig(conf_data)
    except Exception as e:
        # Report unexpected exceptions
        raise e
    return config


def run(data: bytes = b""):
    global run_count
    injector = atheris.FuzzInjector()
    l: list[int] = injector.mutation_list
    n = len(l)
    idx_list = [i for i in range(n)]
    idx_list.sort(key=lambda x: KNOWN_MUTATION_COUNTER.get(x, 0), reverse=True)
    logger.info(f"idx_list: {idx_list}")
    l.clear()
    logger.info(f"data length: {len(data)}, data: {data.hex()}")
    fdp = atheris.FuzzedDataProvider(data)
    # evcc_file_config = generate_config(fdp, run_count)
    evcc_file_config = evcc_file_configs[run_count % len(evcc_file_configs)]
    for _ in range(n):
        l.append(0)
    for i in range(n):
        if run_count < len(evcc_file_configs):
            continue
        l[idx_list[i]] = fdp.ConsumeUInt(1)
    logger.info(f"list length: {len(l)}, mutation list: {l}")
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
        f"Status Counter: {counter}"
    )
    run_count += 1
    atheris.FuzzInjector().dump(False, False, False)


if __name__ == "__main__":
    injector = atheris.FuzzInjector()
    for k, v in KNOWN_MUTATION_COUNTER.items():
        logger.info(f"known mutation count: {v}, {injector.mutation_map[k]}")
    injector.dump()
    if len(sys.argv) > 1 and sys.argv[1] == "--run_once":
        for _ in evcc_file_configs:
            run()
    elif len(sys.argv) > 1 and sys.argv[1] == "--run_no":
        exit(0)
    elif len(sys.argv) > 1 and sys.argv[1] == "--get_json":
        res = {}
        for k, v in injector.mutation_map.items():
            res[k] = str(v[2])
        print(json.dumps(res))
        exit(0)
    else:
        atheris.Setup(sys.argv, run)
        atheris.Fuzz()
