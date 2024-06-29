from fastapi import FastAPI, Request
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    make_asgi_app,
)

app = FastAPI()

# Metrics to Track
Summary = Summary("SERVER_REQUEST", "Overall Server Summary of EM parameter values")
autofill_time = Histogram("AUTOFILL_TIME", "Time taken to autofill of ...")
lens_temp = Gauge("LENS_TEMPERATURE", "Temperature of the lens")
camera_temp = Gauge("CAMERA_TEMPERATURE", "Temperature of the camera")
vacuum_pressure = Gauge("VACUUM_PRESSURE", "Pressure of the vacuum")
fig_brightness = Gauge("FIG_BRIGHTNESS", "Brightness of the fig")
num_loads = Counter("AUTO_LOADER_COUNTER", "Number of loads of the autoloader")
autofill_times = Counter("AUTOFILL_TIMES", "Number of autofill times")

# Mapping the Prometheus Metrics to the FastAPI Endpoints based on their type
guage_map = {
    "lens_temp": lens_temp.set,
    "camera_temp": camera_temp.set,
    "vacuum_pressure": vacuum_pressure.set,
    "fig_brightness": fig_brightness.set,
}

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
    header_type = headers.get("type")
    if header_type in guage_map:
        value = headers.get("value")
        guage_map[header_type](value)
    else:
        return {"error": "Invalid type"}


# Example Usage:
# curl -X POST http://localhost:8000/set -H "type: fig_brightness" -H "value: 220"


@app.post("/increment")
async def increment_counter(request: Request):
    headers = request.headers
    header_type = headers.get("type")
    if header_type in increment_map:
        increment_map[header_type](1)
    else:
        return {"error": "Invalid type"}


# Example Usage:
# curl -X POST http://localhost:8000/increment -H "type: num_loads
