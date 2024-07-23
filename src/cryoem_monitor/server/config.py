import os
from pathlib import Path

import yaml
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class CryoEMMonitorConfig(BaseModel):
    health_data_path: Path
    health_data_command: str
    health_data_collection_timestep: int


def from_file(config_file_path: Path) -> CryoEMMonitorConfig:
    with open(config_file_path) as config_stream:
        config = yaml.safe_load(config_stream)
    return CryoEMMonitorConfig(**config)


@router.get("/config")
def get_config():
    return from_file(Path(os.environ["CRYOEM_MONITOR_CONFIG"]))
