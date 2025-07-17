import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional, Union

import requests
from pydantic import BaseModel, ValidationError
from pydantic_xml import BaseXmlModel, attr, element

# Note: pydantic documentation suggests the use of lxml to decode the XML data file,
# but this does not work with the following XML file.
# installing xml.etree.ElementTree as ET instead has shown better results.

# When creating the pydantic schema, add the XML tag attributes when referencing the
# class and not when creating the class.


# Classes for type hinting of XML data - Enumerations
class EMLiteral(BaseXmlModel):
    name: str = attr(name="Name")
    value: int


class EMEnumeration(BaseXmlModel):
    name: str = attr(name="Name")
    instrument: str = attr(name="Instrument")
    literals: list[EMLiteral] = element(tag="Literal")


class Enumerations(BaseXmlModel):
    enumerations: list[EMEnumeration] = element(tag="Enumeration")


# Classes for type hinting of XML data - Instruments
class Parameter(BaseXmlModel):
    parameterid: str = attr(name="ID")
    eventid: str = attr(name="EventID")
    eventname: str = attr(name="EventName")
    name: str = attr(name="Name")
    displayname: str = attr(name="DisplayName")
    datatype: str = attr(name="Type")
    enumerationname: Optional[str] = attr(name="EnumerationName", default=None)
    storageunit: str = attr(name="StorageUnit")
    displayunit: str = attr(name="DisplayUnit")
    displayscale: str = attr(name="DisplayScale")
    formatstring: str = attr(name="FormatString")
    servicecategory: str = attr(name="ServiceCategory")
    maxloginterval: str = attr(name="MaxLogInterval")
    absolutemin: str = attr(name="AbsoluteMinimum")
    absolutemax: str = attr(name="AbsoluteMaximum")


class Component(BaseXmlModel):
    name: str = attr(name="Name")
    displayname: str = attr(name="DisplayName")
    servicecategory: str = attr(name="ServiceCategory")
    # Used to self-reference when you have sub-components of the same type
    # All optional fields are set to None by default or an empty list
    components: Optional[list["Component"]] = element(tag="Component", default=None)
    parameter: Optional[list[Parameter]] = element(
        tag="Parameter", default_factory=list
    )


class Instrument(BaseXmlModel):
    name: str = attr(name="Name")
    displayname: str = attr(name="DisplayName")
    heartbeat: str = attr(name="HeartBeat")
    servicelogbook: str = attr(name="ServiceLogbook")
    component: list[Component] = element(tag="Component")


class Instruments(BaseXmlModel):
    instrument: Instrument = element(tag="Instrument")


# Classes for type hinting of XML data - Values
class ValuePar(BaseXmlModel):
    datatype: str = attr(name="Type")
    value: Union[float, int, str]


class ParameterValue(BaseXmlModel):
    timestamp: str = attr(name="Timestamp")
    value: ValuePar = element(tag="Value")


class ParameterValues(BaseXmlModel):
    parameter_value: list[ParameterValue] = element(tag="ParameterValue")


class ValueThresh(BaseXmlModel):
    datatype: str = attr(name="Type")
    value: Union[int, float]


class Threshold(BaseXmlModel):
    name: Literal[
        "WarningMin",
        "CautionMin",
        "CriticalMin",
        "WarningMax",
        "CautionMax",
        "CriticalMax",
    ] = attr(name="Name")
    # All optional fields are set to None by default or an empty list
    value: Optional[ValueThresh] = element(tag="Value", default=None)


class Limit(BaseXmlModel):
    timestamp: str = attr(name="Timestamp")
    thresholds: list[Threshold] = element(tag="Threshold")


class Limits(BaseXmlModel):
    limit: list[Limit] = element(tag="Limit")


class ValueData(BaseXmlModel):
    start: str = attr(name="Start")
    end: str = attr(name="End")
    valueid: str = attr(name="ParameterID")
    parameter: str = attr(name="Parameter")
    # Sometimes, pydantic cannot identify element as part of list, so initialize
    parameter_value: list[ParameterValues] = element(
        tag="ParameterValues", default_factory=list
    )
    limits: Optional[Limits] = element(tag="Limits", default_factory=list)


class Values(BaseXmlModel):
    start: str = attr(name="Start")
    end: str = attr(name="End")
    instrument: str = attr(name="Instrument")
    value_data: list[ValueData] = element(tag="ValueData")


# Class for type hinting of XML data - HealthMonitor (top level)
class HealthMonitor(BaseXmlModel):
    enumerations: Enumerations = element(tag="Enumerations")
    instruments: Instruments = element(tag="Instruments")
    values: Values = element(tag="Values")


class ResponseData(BaseModel):
    data: dict[str, list[Union[int, float, str]]]
    instrument_name: str


class ParameterNames(BaseModel):
    name: str
    enumeration: Optional[str]


class Value_Limits(BaseModel):
    critical_min: Optional[Union[float, int]]
    warning_min: Optional[Union[float, int]]
    caution_min: Optional[Union[float, int]]
    caution_max: Optional[Union[float, int]]
    warning_max: Optional[Union[float, int]]
    critical_max: Optional[Union[float, int]]


def parse_datetime(datetime_str: str) -> datetime:
    # Parse to datetime object with and wwithout fractional seconds
    known_time_formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f+0Z",
    ]
    for time_format in known_time_formats:
        try:
            return datetime.strptime(datetime_str, time_format)
        except ValueError:
            continue
    raise ValueError(f"No time formats fit for {datetime_str}")


def collect(
    xml_path: os.PathLike,
) -> tuple[str, dict[str, list[Union[int, float, str]]]]:
    # Load and extract required values from XML file
    EMData = parse_xml(xml_path=xml_path)

    # Extract the required values from the XML data
    instrument_name: str = EMData.values.instrument
    time: str = EMData.values.end
    time = time[:26] + "Z"
    time_obj: datetime = parse_datetime(time)
    time_obj = time_obj - timedelta(minutes=1)
    setup: dict[str, list[Union[int, float, str]]] = {}
    value_data = EMData.values.value_data
    for data in value_data:
        # Extract the parameter values and parameter_id
        values = data.parameter_value
        name = data.valueid
        setup[name] = []
        # Append all values for each parameter_id
        for value in values:
            for parameter in value.parameter_value:
                value_time: datetime = parse_datetime(parameter.timestamp)
                value_time = value_time.replace(tzinfo=timezone.utc)
                time_obj = time_obj.replace(tzinfo=timezone.utc)
                if value_time >= time_obj:
                    setup[name].append(parameter.value.value)

    return instrument_name, setup


# Saving the parameter names to a JSON file
def save_parameter_names(
    xml_path: os.PathLike = Path("src/cryoem_monitor/client/HealthMonitor.xml"),
    json_out_path: os.PathLike = Path("src/cryoem_monitor/client/parameter_names.json"),
):
    instrument_name, data = collect(xml_path=xml_path)
    with open(json_out_path, "w") as file:
        json.dump({"parameter_names": list(data.keys())}, file, indent=4)


def parse_xml(
    xml_path: os.PathLike = Path("src/cryoem_monitor/client/HealthMonitor.xml"),
    # xml_path: os.PathLike = Path(
    # "health_monitor_Krios4/3632/HealthMonitorCmd_20240813_145321.xml"
    # ),
) -> HealthMonitor:
    # Load and extract required values from XML file
    with open(xml_path) as file:
        xml_data = file.read()

    # Remove the namespace from the XML data due to this specific one being invalid
    # Normally, this is not needed
    xml_data = xml_data.replace(
        ' xmlns="HealthMonitorExport http://schemas.fei.com/HealthMonitor/Export/2009/07"',
        "",
    )
    try:
        EMData = HealthMonitor.from_xml(xml_data)
    except ValidationError as exc:
        print(exc)

    return EMData


def limits() -> dict[str, Value_Limits]:
    EMData = parse_xml()
    data: dict[str, Value_Limits] = {}

    Data = EMData.values.value_data
    for value in Data:
        value_id = value.valueid
        limits = value.limits
        if limits is not None and limits != []:
            for limit in limits.limit:
                thresholds = limit.thresholds
                for threshold in thresholds:
                    name = threshold.name
                    thresh_value: Union[ValueThresh, None] = threshold.value
                    if thresh_value is not None:
                        data_val = thresh_value.value
                        if value_id not in data:
                            data[value_id] = Value_Limits(
                                critical_min=None,
                                warning_min=None,
                                caution_min=None,
                                caution_max=None,
                                warning_max=None,
                                critical_max=None,
                            )
                        if name == "CriticalMin":
                            data[value_id].critical_min = data_val
                        elif name == "WarningMin":
                            data[value_id].warning_min = data_val
                        elif name == "CautionMin":
                            data[value_id].caution_min = data_val
                        elif name == "CautionMax":
                            data[value_id].caution_max = data_val
                        elif name == "WarningMax":
                            data[value_id].warning_max = data_val
                        elif name == "CriticalMax":
                            data[value_id].critical_max = data_val

    return data


def parse_enums(xml_path: os.PathLike) -> dict[str, dict[int, str]]:
    EMData = parse_xml(xml_path=xml_path)
    # Write the enumeration values to a JSON file
    data: dict[str, dict[int, str]] = {}
    for enum in EMData.enumerations.enumerations:
        name = enum.name
        name = name.replace("_enum", "")
        values = {lit.value: lit.name for lit in enum.literals}
        data[name] = values

    return data


def component_enums(xml_path: os.PathLike) -> dict[str, ParameterNames]:
    EMData = parse_xml(xml_path=xml_path)
    ResponseData: dict[str, ParameterNames] = {}
    for outercomponent in EMData.instruments.instrument.component:
        if outercomponent.components is None and outercomponent.parameter is not None:
            for parameter in outercomponent.parameter:
                id = parameter.parameterid
                name = f"{outercomponent.name}_{parameter.name}"
                name = name.replace(" ", "_").replace(".", "").replace("-", "")
                if isinstance(parameter.enumerationname, str):
                    enumeration = parameter.enumerationname
                    enumeration = enumeration.replace("_enum", "")
                    ResponseData[id] = ParameterNames(
                        name=name, enumeration=enumeration
                    )
                else:
                    ResponseData[id] = ParameterNames(name=name, enumeration=None)
        else:
            if (
                outercomponent.components is not None
                and outercomponent.parameter is not None
            ):
                for innercomponent in outercomponent.components:
                    if innercomponent.parameter is not None:
                        for parameter in innercomponent.parameter:
                            id = parameter.parameterid
                            name = f"{innercomponent.name}_{parameter.name}"
                            name = (
                                name.replace(" ", "_").replace(".", "").replace("-", "")
                            )
                            if isinstance(parameter.enumerationname, str):
                                enumeration = parameter.enumerationname
                                enumeration = enumeration.replace("_enum", "")
                                ResponseData[id] = ParameterNames(
                                    name=name, enumeration=enumeration
                                )
                            else:
                                ResponseData[id] = ParameterNames(
                                    name=name, enumeration=None
                                )

    return ResponseData


async def push_data(
    xml_path: os.PathLike = Path("src/cryoem_monitor/client/HealthMonitor.xml"),
    url_base: str = "http://127.0.0.1:8000",
):
    url = f"{url_base}/set"
    instrument_name, data = collect(xml_path=xml_path)
    for parameter, values in data.items():
        if values:
            payload = {
                "type": parameter,
                "value": [str(v) for v in values],
                "instrument": instrument_name,
            }
            requests.post(url, json=payload)


async def main():
    try:
        await push_data()
    except Exception as e:
        print(f"An error has occured: {e}")


if __name__ == "__main__":
    asyncio.run(main())
