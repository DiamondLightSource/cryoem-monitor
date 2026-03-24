import os
from importlib.metadata import entry_points
from pathlib import Path

import yaml
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class CryoEMMonitorConfig(BaseModel):
    health_data_path: Path
    health_data_command: list[str]
    health_data_collection_timestep: int
    health_monitor_xml: Path | None = None


def from_file(config_file_path: Path) -> CryoEMMonitorConfig:
    with open(config_file_path) as config_stream:
        config = yaml.safe_load(config_stream)
    return CryoEMMonitorConfig(**config)


def get_config() -> CryoEMMonitorConfig:
    if config_extraction_eps := list(
        entry_points(group="murfey.config.extraction", name="murfey_machine")
    ):
        return config_extraction_eps[0].load()("cryoem_monitor")
    return from_file(Path(os.environ["CRYOEM_MONITOR_CONFIG"]))


@router.get("/config")
def return_config():
    return get_config()
