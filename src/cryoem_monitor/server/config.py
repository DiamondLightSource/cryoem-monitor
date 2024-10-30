import os
from backports.entry_points_selectable import entry_points
from pathlib import Path
from typing import List, Optional

import yaml
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class CryoEMMonitorConfig(BaseModel):
    health_data_path: Path
    health_data_command: List[str]
    health_data_collection_timestep: int
    health_monitor_xml: Optional[Path] = None


def from_file(config_file_path: Path) -> CryoEMMonitorConfig:
    with open(config_file_path) as config_stream:
        config = yaml.safe_load(config_stream)
    return CryoEMMonitorConfig(**config)

def get_config() -> CryoEMMonitorConfig:
    if config_extraction_eps := entry_points.select(group="murfey.config.extraction", name="murfey_machine"):
        return config_extraction_eps[0].load()("cryoem_monitor")
    return from_file(Path(os.environ["CRYOEM_MONITOR_CONFIG"]))

@router.get("/config")
def return_config():
    return get_config()
