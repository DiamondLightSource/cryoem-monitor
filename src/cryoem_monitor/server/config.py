import os
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


@router.get("/config")
def get_config():
    return from_file(Path(os.environ["CRYOEM_MONITOR_CONFIG"]))
