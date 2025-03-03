import json
import logging
from typing import List, Optional

from iso15118.shared.messages.enums import (
    EnergyTransferModeEnum,
    Protocol,
    ServiceV20,
)
from iso15118.shared.utils import (
    load_requested_energy_services,
    load_requested_protocols,
)

logger = logging.getLogger(__name__)


class EVCCConfig:
    _default_protocols = [
        "DIN_SPEC_70121",
        "ISO_15118_2",
        "ISO_15118_20_AC",
        "ISO_15118_20_DC",
    ]
    _default_supported_energy_services = ["AC"]

    def __init__(self, data: dict = None):
        self.data = data or {}
        self.raw_supported_energy_services: List[str] = data.get(
            "supportedEnergyServices", self._default_supported_energy_services
        )
        self.supported_energy_services: List[ServiceV20] = []
        self.is_cert_install_needed: bool = data.get("isCertInstallNeeded", False)
        self.use_tls: bool = data.get("useTls", True)
        self.sdp_retry_cycles: int = data.get("sdpRetryCycles", 1)
        self.max_contract_certs: int = data.get("maxContractCerts", 3)
        self.enforce_tls: bool = data.get("enforceTls", False)
        self.raw_supported_protocols: List[str] = data.get(
            "supportedProtocols", self._default_protocols
        )
        self.supported_protocols: List[Protocol] = []
        self.energy_transfer_mode: EnergyTransferModeEnum = EnergyTransferModeEnum(
            data.get(
                "energyTransferMode", EnergyTransferModeEnum.AC_THREE_PHASE_CORE.value
            )
        )
        self.max_supporting_points: int = data.get("maxSupportingPoints", 1024)
        self.charge_loop_cycle: int = data.get("chargeLoopCycle", 10)
        self.charge_loop_delay_time: int = data.get("chargeLoopDelay", 5)

        self.load_raw_values()

    def __str__(self):
        return json.dumps(self.data)

    def load_raw_values(self):
        self.supported_energy_services = load_requested_energy_services(
            self.raw_supported_energy_services
        )
        self.supported_protocols = load_requested_protocols(
            self.raw_supported_protocols
        )


def load_from_file(file_name: str) -> EVCCConfig:
    try:
        with open(file_name, "r") as f:
            json_content = f.read()
            data = json.loads(json_content)
            ev_config = EVCCConfig(data)
            logger.info("EVCC Settings")
            for key, value in vars(ev_config).items():
                if not key.startswith("raw"):
                    logger.info(f"{key:30}: {value}")
        return ev_config
    except Exception as err:
        logger.debug(f"Error on loading evcc config file:{err}")
    return EVCCConfig()
