[![CI](https://github.com/DiamondLightSource/cryoem-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/DiamondLightSource/cryoem-monitor/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/DiamondLightSource/cryoem-monitor/branch/main/graph/badge.svg)](https://codecov.io/gh/DiamondLightSource/cryoem-monitor)

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

# cryoem-monitor

Electron Microscope Monitoring System using Prometheus with an Visualisation using Grafana Endpoint

Source          | <https://github.com/DiamondLightSource/cryoem-monitor>
:---:           | :---:
Releases        | <https://github.com/DiamondLightSource/cryoem-monitor/releases>



```python
from cryoem_monitor import __version__

print(f"Hello cryoem_monitor {__version__}")
```

Run FastAPI Server 

Before you create the FastAPI server, export the path variable where the XML file from the EM is stored.

```
export ${PATH_VARIABLE}
fastapi run src/cryoem_monitor/server/prometheus.py
```


Run Diagnostic Data Collection
- XML_file_path is where you have HealthMonitor Data setup (It should be the same as the ${PATH_VARIABLE})
- Sever port is the link to the FastAPI prometheus server which is interfaced with

```
cryoem_monitor.run --path ${XML_file_path} --server ${server_port}
```

Export Base Grafana Template 
- This creates a base Grafana Dashboard JSON file that can be imported containing all Parameters 

```
cryoem_monitor.graf-export --device ${EM_device_name}
```