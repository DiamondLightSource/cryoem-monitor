import argparse
import asyncio
import subprocess
import time
from pathlib import Path

import requests

from cryoem_monitor.client.logger import push_data
from cryoem_monitor.server.grafana_export import grafana_export


def run():
    parser = argparse.ArgumentParser(description="Start health monitor data collection")
    # For each individual argument
    parser.add_argument(
        "--server",
        metavar="HOST:PORT",
        type=str,
        help="Monitor server to connect to",
        required=True,
    )
    parser.add_argument(
        "--path",
        type=str,
        help="Path to health data XML file",
        required=True,
    )
    args = parser.parse_args()

    config = requests.get(f"{args.server}/config").json()

    while True:
        try:
            subprocess.run(config["health_data_command"])
            xml_path = list(Path(config["health_data_path"]).glob("*.xml"))[0]
            asyncio.run(push_data(xml_path=xml_path, url_base=args.server))
            time.sleep(config["health_data_collection_timestep"])
        except KeyboardInterrupt:
            break


def export():
    parser = argparse.ArgumentParser(description="Export Grafana Dashboard JSON")
    # For each individual argument
    parser.add_argument(
        "--device",
        type=str,
        help="Electron Microscope to create Grafana Dashboard for",
        required=True,
    )
    args = parser.parse_args()

    try:
        asyncio.run(grafana_export(device=args.device))
    except KeyboardInterrupt:
        pass
