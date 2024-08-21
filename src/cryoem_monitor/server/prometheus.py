import re
import traceback
from typing import Dict, List, Union

import uvicorn
from fastapi import FastAPI
from prometheus_client import (
    Counter,
    Enum,
    Gauge,
    Summary,
    make_asgi_app,
)
from pydantic import BaseModel

from cryoem_monitor.client.logger import ParameterNames, component_enums, parse_enums
from cryoem_monitor.server.config import router

app = FastAPI()


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
Enum_List: Dict[str, Dict[int, str]] = parse_enums()
ComponentList: Dict[str, ParameterNames] = component_enums()


# Create Enumerations and Gauges from ComponentList
# Note: All Prometheus Metric Names cannot have "." or "-" in the name

Enumerations: Dict[str, Enum] = {
    componentid: Enum(
        f"{ComponentList[componentid].name}_PID_{componentid}",
        f"PID_{componentid}: {format_string(ComponentList[componentid].name)}",
        states=list(Enum_List[ComponentList[componentid].enumeration].values()),
        labelnames=["instrument"],
    )
    for componentid in ComponentList
    if ComponentList[componentid].enumeration is not None
}

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
@app.post("/set")
async def set_value(
    request: HealthMonitorData,
):
    payload = request
    try:
        header_type = payload.type
        instrument_name = payload.instrument
        if instrument_name is None:
            raise ValueError("Instrument name is missing or empty.")
        if header_type in Enumerations:
            values = payload.value
            if values is None:
                raise ValueError("Value header is missing or empty.")
            for value in values:
                Enumerations[header_type].labels(instrument=instrument_name).state(
                    Enum_List[ComponentList[header_type].enumeration][int(value)]
                )
        elif header_type in Gauges:
            value = payload.value
            if value is None:
                raise ValueError("Value header is missing or empty.")

            # If no errors raised, set the last value and label with the instrument name
            if isinstance(value, list):
                Gauges[header_type].labels(instrument_name).set(float(value[-1]))
            else:
                Gauges[header_type].labels(instrument_name).set(float(value))
        elif header_type in increment_map:
            # If no errors raised, increment counter and label with instrument name
            increment_map[header_type].labels(instrument_name).inc(1)
        else:
            raise ValueError("Invalid type")
    except ValueError as e:
        print(traceback.format_exc())
        print(f"{header_type} and {e}")
        return {"error": str(e)}


# For Debugging Purposes
if __name__ == "__prometheus__":
    uvicorn.run(app, host="http://localhost", port=8000)


# Example Usage of Setting Value of Gauge or Enumeration:
# curl -X POST http://localhost:8000/set -H "Content-Type: application/json" -d '{"type": "ObjectiveMode", "value": [3], "instrument": os"}'  # noqa: E501

# Example Usage of Increment:
# curl -X POST http://localhost:8000/set -H "Content-Type: application/json" -d '{"type": "num_loads", "instrument": Talos"}'  # noqa: E501
