import json
import os
from typing import Any, Dict, List, Union

from cryoem_monitor.client.logger import (
    ParameterNames,
    Value_Limits,
    component_enums,
    limits,
)


async def grafana_export(device: str, xml_path: os.PathLike):
    ComponentList: Dict[str, ParameterNames] = component_enums(xml_path=xml_path)
    Limits: Dict[str, Value_Limits] = limits()  # id: Value_Limits

    with open("grafana/template.json") as file:
        Template = json.load(file)

    panels = Template["panels"]
    for componentid in ComponentList:
        name = f"{ComponentList[componentid].name}_PID_{componentid}"
        # Check if Component has limits
        if componentid in Limits:
            thresh_limits = Limits[componentid]
            critical_min = thresh_limits.critical_min
            warning_min = thresh_limits.warning_min
            caution_min = thresh_limits.caution_min
            caution_max = thresh_limits.caution_max
            warning_max = thresh_limits.warning_max
            critical_max = thresh_limits.critical_max
        else:
            critical_min = None
            warning_min = None
            caution_min = None
            caution_max = None
            warning_max = None
            critical_max = None

        # Check if Component is an Enumeration
        if ComponentList[componentid].enumeration is None:
            panels.append(
                return_gauge(
                    name,
                    critical_min,
                    warning_min,
                    caution_min,
                    caution_max,
                    warning_max,
                    critical_max,
                )
            )
        else:
            panels.append(
                return_state(
                    name,
                    critical_min,
                    warning_min,
                    caution_min,
                    caution_max,
                    warning_max,
                    critical_max,
                )
            )

    Template["panels"] = panels

    with open(f"grafana/grafana_{device}.json", "w") as file:
        json.dump(Template, file, indent=4)


# Thresholds definition
def threshold(
    critical_min: Union[int, float, None] = None,
    warning_min: Union[int, float, None] = None,
    caution_min: Union[int, float, None] = None,
    caution_max: Union[int, float, None] = None,
    warning_max: Union[int, float, None] = None,
    critical_max: Union[int, float, None] = None,
) -> List[Dict[str, Any]]:
    if critical_min is None and warning_min is None and caution_min is None:
        thresholds: List[Dict[str, Any]] = [
            {"color": "green", "value": None},
        ]
    else:
        thresholds = [
            {"color": "red", "value": None},
        ]

    least_bad_min = (
        "caution" if caution_min else "warning" if warning_min else "critical"
    )

    if critical_min is not None:
        thresholds.append(
            {
                "color": "green" if least_bad_min == "critical" else "orange",
                "value": critical_min,
            }
        )
    if warning_min is not None:
        thresholds.append(
            {
                "color": "green" if least_bad_min == "warning" else "yellow",
                "value": warning_min,
            }
        )
    if caution_min is not None:
        thresholds.append(
            {
                "color": "green" if least_bad_min == "caution" else "green",
                "value": caution_min,
            }
        )
    if caution_max is not None:
        thresholds.append({"color": "yellow", "value": caution_max})
    if warning_max is not None:
        thresholds.append({"color": "orange", "value": warning_max})
    if critical_max is not None:
        thresholds.append({"color": "red", "value": critical_max})

    return thresholds


# Gauge Panel
def return_gauge(
    gauge_name: str,
    critical_min: Union[int, float, None] = None,
    warning_min: Union[int, float, None] = None,
    caution_min: Union[int, float, None] = None,
    caution_max: Union[int, float, None] = None,
    warning_max: Union[int, float, None] = None,
    critical_max: Union[int, float, None] = None,
) -> dict:
    thresholds = threshold(
        critical_min, warning_min, caution_min, caution_max, warning_max, critical_max
    )

    return {
        "datasource": {"type": "prometheus", "uid": "fdrsvc8u0ao00b"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": thresholds,
                },
            },
            "overrides": [],
        },
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        "id": 4,
        "options": {
            "minVizHeight": 75,
            "minVizWidth": 75,
            "orientation": "auto",
            "reduceOptions": {"calcs": ["lastNotNone"], "fields": "", "values": False},
            "showThresholdLabels": False,
            "showThresholdMarkers": True,
            "sizing": "auto",
        },
        "pluginVersion": "11.1.0",
        "targets": [
            {
                "datasource": {"type": "prometheus", "uid": "fdrsvc8u0ao00b"},
                "disableTextWrap": False,
                "editorMode": "builder",
                "expr": f"{gauge_name}",
                "fullMetaSearch": False,
                "includeNoneMetadata": True,
                "instant": False,
                "legendFormat": "__auto",
                "range": True,
                "refId": "A",
                "useBackend": False,
            }
        ],
        "title": f"{gauge_name}",
        "type": "gauge",
    }


# State Panel
def return_state(
    state_name: str,
    critical_min: Union[int, float, None] = None,
    warning_min: Union[int, float, None] = None,
    caution_min: Union[int, float, None] = None,
    caution_max: Union[int, float, None] = None,
    warning_max: Union[int, float, None] = None,
    critical_max: Union[int, float, None] = None,
) -> dict:
    thresholds = threshold(
        critical_min, warning_min, caution_min, caution_max, warning_max, critical_max
    )

    return {
        "datasource": {"type": "prometheus", "uid": "fdrsvc8u0ao00b"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "custom": {
                    "fillOpacity": 70,
                    "hideFrom": {"legend": False, "tooltip": False, "viz": False},
                    "insertNones": False,
                    "lineWidth": 0,
                    "spanNones": False,
                },
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": thresholds,
                },
            },
            "overrides": [],
        },
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
        "id": 3,
        "options": {
            "alignValue": "left",
            "legend": {
                "displayMode": "list",
                "placement": "bottom",
                "showLegend": True,
            },
            "mergeValues": True,
            "rowHeight": 0.9,
            "showValue": "auto",
            "tooltip": {"mode": "single", "sort": "none"},
        },
        "targets": [
            {
                "datasource": {"type": "prometheus", "uid": "fdrsvc8u0ao00b"},
                "disableTextWrap": False,
                "editorMode": "builder",
                "expr": f"{state_name} == 1",
                "fullMetaSearch": False,
                "includeNoneMetadata": True,
                "instant": False,
                "legendFormat": f"{state_name}",
                "range": True,
                "refId": "A",
                "useBackend": False,
            }
        ],
        "title": f"{state_name}",
        "type": "state-timeline",
    }


# await grafana_export("3594, Talos Arctica")
