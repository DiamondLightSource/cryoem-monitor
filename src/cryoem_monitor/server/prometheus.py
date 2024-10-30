import os
import re
import traceback
from pathlib import Path
from typing import Dict, List, Union

import uvicorn
from fastapi import APIRouter, FastAPI
from prometheus_client import (
    Counter,
    Enum,
    Gauge,
    Summary,
    make_asgi_app,
)
from pydantic import BaseModel

from cryoem_monitor.client.logger import ParameterNames, component_enums, parse_enums
from cryoem_monitor.server.config import get_config, router

app = FastAPI()

prom_router = APIRouter()

try:
    path = get_config().health_monitor_xml
    if path is not None:
        xml_path: os.PathLike = Path(path)
    else:
        raise ValueError("No path variable added")
except ValueError as e:
    print(f"Error: {e}")


def format_string(s: str) -> str:
    # Add space before capital letters not at the start of the string
    s = re.sub(r"(?<!^)(?=[A-Z][a-z])", " ", s)
    # Handle sequences of capitals possibly followed by a lowercase letter
    s = re.sub(r"(?<=.)([A-Z]+)([A-Z][a-z])", r" \1 \2", s)
    # Insert space between letters and digits if they are adjacent
    s = re.sub(r"(\D)(?=\d)", r"\1 ", s)  # Letters followed by digits
    s = re.sub(r"(\d)(?=\D)", r"\1 ", s)  # Digits followed by letters
    return s.strip()  # Remove any leading/trailing spaces added by the regex


# Metrics to Track
Summary("SERVER_REQUEST", "Overall Server Summary of EM parameter values")

# Create Enumerations for Prometheus Backend
# Call all enumerations and Components from function
Enum_List: Dict[str, Dict[int, str]] = parse_enums(xml_path)
ComponentList: Dict[str, ParameterNames] = component_enums(xml_path)


# Create Enumerations and Gauges from ComponentList
# Note: All Prometheus Metric Names cannot have "." or "-" in the name
Enumerations: Dict[str, Enum] = {}
for componentid in ComponentList:
    enum_val = ComponentList[componentid].enumeration
    if enum_val is not None:
        Enumerations[componentid] = Enum(
            f"{ComponentList[componentid].name}_PID_{componentid}",
            f"PID_{componentid}: {format_string(ComponentList[componentid].name)}",
            states=list(Enum_List[enum_val].values()),
            labelnames=["instrument"],
        )

Gauges: Dict[str, Gauge] = {
    componentid: Gauge(
        f"{ComponentList[componentid].name}_PID_{componentid}",
        f"PID_{componentid}: {format_string(ComponentList[componentid].name)}",
        ["instrument"],
    )
    for componentid in ComponentList
    if ComponentList[componentid].enumeration is None
}

# Counters and Histogram - these are created manually and are extrapolated from Gauges
# NB: This should be done with removing according modifying Gauges
num_loads = Counter("AUTO_LOADER_COUNTER", "Number of loads of the autoloader")
autofill_times = Counter("AUTOFILL_TIMES", "Number of autofill times")

increment_map = {
    "num_loads": num_loads,
    "autofill_times": autofill_times,
}


# Mounting Prometheus Metrics to FastAPI
monitoring_app = make_asgi_app()
app.mount("/metrics", monitoring_app)
app.include_router(router)


class HealthMonitorData(BaseModel):
    type: str
    instrument: str
    value: List[Union[str, float, int]]


# Handle different values based on if it is a gauge or an enum
@prom_router.post("/set")
async def set_value(
    request: HealthMonitorData,
):
    payload = request
    # Check validity of payload value and if it is a list or not
    values = payload.value
    if values is None:
        raise ValueError("Value header is missing or empty.")
    if not isinstance(values, list):
        values = [values]

    try:
        header_type = payload.type
        instrument_name = payload.instrument
        if instrument_name is None:
            raise ValueError("Instrument name is missing or empty.")
        # Check if the header type is in the Enumerations, Gauge or Increment_map
        if header_type in Enumerations:
            for value in values:
                enum_val = ComponentList[header_type].enumeration
                if enum_val is None:
                    raise ValueError("Enumeration is missing or empty.")
                Enumerations[header_type].labels(instrument=instrument_name).state(
                    Enum_List[enum_val][int(value)]
                )
        elif header_type in Gauges:
            # Set the last value and label with the instrument name
            Gauges[header_type].labels(instrument_name).set(float(values[-1]))
        elif header_type in increment_map:
            # If no errors raised, increment counter and label with instrument name
            increment_map[header_type].labels(instrument_name).inc(1)
        else:
            raise ValueError("Invalid type")
    except ValueError as e:
        print(traceback.format_exc())
        print(f"{header_type} and {e}")
        return {"error": str(e)}


app.include_router(prom_router)

# For Debugging Purposes
if __name__ == "__prometheus__":
    uvicorn.run(app, host="http://localhost", port=8000)


# Example Usage of Setting Value of Gauge or Enumeration:
# curl -X POST http://localhost:8000/set -H "Content-Type: application/json" -d '{"type": "ObjectiveMode", "value": [3], "instrument": os"}'  # noqa: E501

# Example Usage of Increment:
# curl -X POST http://localhost:8000/set -H "Content-Type: application/json" -d '{"type": "num_loads", "instrument": Talos"}'  # noqa: E501
