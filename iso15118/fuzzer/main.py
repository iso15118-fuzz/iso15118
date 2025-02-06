import asyncio
import logging
import sys

import atheris

with atheris.instrument_imports():
    from iso15118.evcc import Config as EVCCConfig
    from iso15118.evcc import EVCCHandler
    from iso15118.evcc.controller.simulator import SimEVController
    from iso15118.evcc.evcc_config import load_from_file
    from iso15118.shared.exificient_exi_codec import (
        ExificientEXICodec as EVCCExificientEXICodec,
    )

atheris.FuzzInjector().dump()


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


def run(data):
    # TODO: set mutation list according to data
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.debug("program terminated manually")


def main():
    atheris.Setup(sys.argv, run)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
