import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Literal, Optional, Union

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
    literals: List[EMLiteral] = element(tag="Literal")


class Enumerations(BaseXmlModel):
    enumerations: List[EMEnumeration] = element(tag="Enumeration")


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
    components: Optional[List["Component"]] = element(tag="Component", default=None)
    parameter: Optional[List[Parameter]] = element(
        tag="Parameter", default_factory=list
    )


class Instrument(BaseXmlModel):
    name: str = attr(name="Name")
    displayname: str = attr(name="DisplayName")
    heartbeat: str = attr(name="HeartBeat")
    servicelogbook: str = attr(name="ServiceLogbook")
    component: List[Component] = element(tag="Component")


class Instruments(BaseXmlModel):
    instrument: Instrument = element(tag="Instrument")


# Classes for type hinting of XML data - Values
class ValuePar(BaseXmlModel):
    datatype: str = attr(name="Type")
    value: float | int | str


class ParameterValue(BaseXmlModel):
    timestamp: str = attr(name="Timestamp")
    value: ValuePar = element(tag="Value")


class ParameterValues(BaseXmlModel):
    parameter_value: List[ParameterValue] = element(tag="ParameterValue")


class ValueThresh(BaseXmlModel):
    datatype: str = attr(name="Type")
    value: int | float


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


class Limit(BaseXmlModel, tag="Limit"):
    timestamp: str = attr(name="Timestamp")
    thresholds: List[Threshold] = element(tag="Threshold")


class Limits(BaseXmlModel):
    limit: List[Limit] = element(tag="Limit")


class ValueData(BaseXmlModel):
    start: str = attr(name="Start")
    end: str = attr(name="End")
    valueid: str = attr(name="ParameterID")
    parameter: str = attr(name="Parameter")
    # Sometimes, pydantic cannot identify element as part of list, so initialize
    parameter_value: List[ParameterValues] = element(
        tag="ParameterValues", default_factory=list
    )
    limits: Optional[Limits] = element(tag="Limits", default_factory=list)


class Values(BaseXmlModel):
    start: str = attr(name="Start")
    end: str = attr(name="End")
    instrument: str = attr(name="Instrument")
    value_data: List[ValueData] = element(tag="ValueData")


# Class for type hinting of XML data - HealthMonitor (top level)
class HealthMonitor(
    BaseXmlModel,
    tag="HealthMonitor",
):
    enumerations: Enumerations = element(tag="Enumerations")
    instruments: Instruments = element(tag="Instruments")
    values: Values = element(tag="Values")


class ResponseData(BaseModel):
    data: Dict[str, List[Union[int, float]]]
    instrument_name: str


class ParameterNames(BaseModel):
    name: str
    enumeration: Optional[str]


def parse_datetime(datetime_str: str) -> datetime:
    # Parse to datetime object with and wwithout fractional seconds
    try:
        return datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%SZ")


def collect() -> ResponseData:
    # Load and extract required values from XML file
    EMData = parse_xml()

    # Extract the required values from the XML data
    instrument_name: str = EMData.values.instrument
    time: str = EMData.values.end
    time = time[:26] + "Z"
    time_obj: datetime = parse_datetime(time)
    time_obj = time_obj - timedelta(minutes=25)
    setup: Dict[str, List[Union[int, float]]] = {}
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
                if value_time >= time_obj:
                    setup[name].append(parameter.value.value)

    response = ResponseData(data=setup, instrument_name=instrument_name)
    return response


# Saving the parameter names to a JSON file
def save_parameter_names(
    xml_path: os.PathLike = Path("src/cryoem_monitor/client/HealthMonitor.xml"),
    json_out_path: os.PathLike = Path("src/cryoem_monitor/client/parameter_names.json"),
):
    vals: ResponseData = collect()
    with open(json_out_path, "w") as file:
        json.dump({"parameter_names": list(vals.data.keys())}, file, indent=4)


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


def parse_enums() -> Dict[str, Dict[int, str]]:
    EMData = parse_xml()
    # Write the enumeration values to a JSON file
    data: Dict[str, Dict[int, str]] = {}
    for enum in EMData.enumerations.enumerations:
        name = enum.name
        name = name.replace("_enum", "")
        values = {lit.value: lit.name for lit in enum.literals}
        data[name] = values

    return data


def component_enums() -> Dict[str, ParameterNames]:
    EMData = parse_xml()
    ResponseData: Dict[str, ParameterNames] = {}
    for outercomponent in EMData.instruments.instrument.component:
        if outercomponent.components is None:
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
            for innercomponent in outercomponent.components:
                for parameter in innercomponent.parameter:
                    id = parameter.parameterid
                    name = f"{innercomponent.name}_{parameter.name}"
                    name = name.replace(" ", "_").replace(".", "").replace("-", "")
                    if isinstance(parameter.enumerationname, str):
                        enumeration = parameter.enumerationname
                        enumeration = enumeration.replace("_enum", "")
                        ResponseData[id] = ParameterNames(
                            name=name, enumeration=enumeration
                        )
                    else:
                        ResponseData[id] = ParameterNames(name=name, enumeration=None)

    return ResponseData


async def push_data(
    xml_path: os.PathLike = Path("src/cryoem_monitor/client/HealthMonitor.xml"),
    url_base: str = "http://127.0.0.1:8000",
):
    url = f"{url_base}/set"
    response: ResponseData = collect()
    data: Dict[str, List[Union[int | float]]] = response.data
    instrument_name: str = response.instrument_name
    for parameter, values in data.items():
        if values:
            payload = {
                "type": parameter,
                "value": values,
                "instrument": instrument_name,
            }
            requests.post(url, json=payload)


async def main():
    try:
        component_enums()
        # save_parameter_names()
        await push_data()
    except Exception as e:
        print(f"An error has occured: {e}")


if __name__ == "__main__":
    asyncio.run(main())
