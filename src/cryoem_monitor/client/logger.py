import asyncio
import json
from typing import Dict, List, Literal, Optional, Union

import requests
from pydantic import ValidationError
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
    value: float | int


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


def collect() -> Dict[str, List[Union[int, float]]]:
    # Load and extract required values from XML file
    with open("src/cryoem_monitor/client/HealthMonitor.xml") as file:
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

    # Extract the required values from the XML data
    setup: Dict[str, List[Union[int, float]]] = {}
    value_data = EMData.values.value_data
    for data in value_data:
        values = data.parameter_value
        name = data.parameter
        # Remove the dots from the parameter name: not allowed in Prometheus metrics
        name = name.replace(".", "")
        setup[name] = []
        for value in values:
            for parameter in value.parameter_value:
                setup[name].append(parameter.value.value)

    return setup


# Saving the parameter names to a JSON file
def save_parameter_names():
    vals: Dict[str, List[Union[int, float]]] = collect()
    with open("src/cryoem_monitor/client/parameter_names.json", "w") as file:
        json.dump({"parameter_names": list(vals.keys())}, file, indent=4)


async def push_data():
    url = "http://localhost:8000/set"
    data: Dict[str, List[Union[int | float]]] = collect()
    for parameter, values in data.items():
        for value in values:
            headers = {"type": parameter, "value": str(value)}
            requests.post(url, headers=headers)
            asyncio.sleep(0.1)


async def main():
    try:
        await push_data()
    except Exception as e:
        print(f"An error has occured: {e}")


if __name__ == "__main__":
    asyncio.run(main())
