import json
import re
from typing import Dict, List

from fastapi import FastAPI, Request
from prometheus_client import (
    Counter,
    Gauge,
    Summary,
    make_asgi_app,
)

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

# Gauges - these are dynamically created by the JSON file containing all parameters
with open("src/cryoem_monitor/client/parameter_names.json") as file:
    parameters: List[str] = json.load(file)["parameter_names"]
guages: Dict[str, Gauge] = {
    parameter: Gauge(parameter, format_string(parameter)) for parameter in parameters
}

# Counters and Histogram - these are created manually and are extrapolated from Gauges
# NB: This should be done with removing according modifying Gauges
num_loads = Counter("AUTO_LOADER_COUNTER", "Number of loads of the autoloader")
autofill_times = Counter("AUTOFILL_TIMES", "Number of autofill times")


increment_map = {
    "num_loads": num_loads.inc,
    "autofill_times": autofill_times.inc,
}

# Mounting Prometheus Metrics to FastAPI
monitoring_app = make_asgi_app()
app.mount("/metrics", monitoring_app)


@app.post("/set")
async def set_value(request: Request):
    headers = request.headers
    try:
        header_type = headers.get("type")
        if header_type in guages:
            value = headers.get("value")
            if value is None:
                raise ValueError("Value header is missing or empty.")

            guages[header_type].set(float(value))
        elif header_type in increment_map:
            increment_map[header_type](1)
        else:
            raise ValueError("Invalid type")
    except ValueError as e:
        return {"error": str(e)}


# Example Usage of Setting Value:
# curl -X POST http://localhost:8000/set -H "type: ADLTemperature" -H "value: 220"

# Example Usage of Increment:
# curl -X POST http://localhost:8001/set -H "type: num_loads"
