import argparse
import asyncio
import subprocess
import time
from pathlib import Path

import requests

from cryoem_monitor.client.logger import push_data


def run():
    parser = argparse.ArgumentParser(description="Start health monitor data collection")
    parser.add_argument(
        "--server",
        metavar="HOST:PORT",
        type=str,
        help="Monitor server to connect to",
        required=True,
    )
    args = parser.parse_args()

    config = requests.get(f"{args.server}/config").json()

    while True:
        try:
            subprocess.run(list(config["health_data_command"].split()))
            asyncio.run(
                push_data(
                    xml_path=Path(config["health_data_path"]), url_base=args.server
                )
            )
            time.sleep(config["health_data_collection_timestep"])
        except KeyboardInterrupt:
            break
