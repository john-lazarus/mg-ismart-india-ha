from __future__ import annotations
from functools import lru_cache
import time
from typing import Any
import asn1tools

TAP_RESERVED_SIZE = 16
PROTOCOL = 513
STATUS_APP_ID = "511"
CONTROL_APP_ID = "510"
PIN_APP_ID = "313"

ASN_V21 = """MGIndiaTapModule
DEFINITIONS AUTOMATIC TAGS ::= BEGIN
MPDispatcherBody ::= SEQUENCE { uid IA5String(SIZE(50)) OPTIONAL, token IA5String(SIZE(40)) OPTIONAL, applicationID IA5String(SIZE(3)), vin IA5String(SIZE(17)) OPTIONAL, messageID INTEGER(0..255), eventCreationTime INTEGER(0..2147483647), eventID INTEGER(0..2147483647) OPTIONAL, ulMessageCounter INTEGER(0..65535) OPTIONAL, dlMessageCounter INTEGER(0..65535) OPTIONAL, ackMessageCounter INTEGER(0..65535) OPTIONAL, ackRequired BOOLEAN OPTIONAL, applicationDataLength INTEGER(0..65535) OPTIONAL, applicationDataEncoding DataEncodingType OPTIONAL, applicationDataProtocolVersion INTEGER(0..65535) OPTIONAL, testFlag INTEGER(1..3) OPTIONAL, result INTEGER(0..65535) OPTIONAL, errorMessage OCTET STRING(SIZE(1..1024)) OPTIONAL }
DataEncodingType ::= ENUMERATED { perUnaligned(0), der(1), ber(2) }
OTARVMVehicleStatusReq ::= SEQUENCE { vehStatusReqType INTEGER(0..255) }
OTARVCReq ::= SEQUENCE { rvcReqType OCTET STRING(SIZE(1)), rvcParams SEQUENCE SIZE(1..10) OF RvcReqParam OPTIONAL }
RvcReqParam ::= SEQUENCE { paramId INTEGER(0..65535), paramValue OCTET STRING(SIZE(1..255)) }
OTARVMVehicleStatusResp513 ::= SEQUENCE { statusTime INTEGER(0..2147483647), gpsPosition RvsPosition, basicVehicleStatus RvsBasicStatus513, extendedVehicleStatus RvsExtStatus OPTIONAL }
OTARVCStatus513 ::= SEQUENCE { rvcReqType OCTET STRING(SIZE(1)), rvcReqSts OCTET STRING(SIZE(1)), failureType INTEGER(0..255) OPTIONAL, gpsPosition RvsPosition, basicVehicleStatus RvsBasicStatus513 }
RvsPosition ::= SEQUENCE { wayPoint RvsWayPoint, timestamp4Short Timestamp4Short, gpsStatus GPSStatus }
RvsWayPoint ::= SEQUENCE { position RvsWGS84Point, heading INTEGER(0..359), speed INTEGER(-1000..4500), hdop INTEGER(0..1000), satellites INTEGER(0..16) }
RvsWGS84Point ::= SEQUENCE { latitude INTEGER(-90000000..90000000), longitude INTEGER(-180000000..180000000), altitude INTEGER(-100..8900) }
Timestamp4Short ::= SEQUENCE { seconds INTEGER(0..2147483647) }
GPSStatus ::= ENUMERATED { noGpsSignal(0), timeFix(1), fix2D(2), fix3D(3) }
RvsBasicStatus513 ::= SEQUENCE { driverDoor BOOLEAN, passengerDoor BOOLEAN, rearLeftDoor BOOLEAN, rearRightDoor BOOLEAN, bootStatus BOOLEAN, bonnetStatus BOOLEAN, lockStatus BOOLEAN, driverWindow BOOLEAN OPTIONAL, passengerWindow BOOLEAN OPTIONAL, rearLeftWindow BOOLEAN OPTIONAL, rearRightWindow BOOLEAN OPTIONAL, sunroofStatus BOOLEAN OPTIONAL, frontRrightTyrePressure INTEGER(0..255) OPTIONAL, frontLeftTyrePressure INTEGER(0..255) OPTIONAL, rearRightTyrePressure INTEGER(0..255) OPTIONAL, rearLeftTyrePressure INTEGER(0..255) OPTIONAL, wheelTyreMonitorStatus INTEGER(0..255) OPTIONAL, sideLightStatus BOOLEAN, dippedBeamStatus BOOLEAN, mainBeamStatus BOOLEAN, vehicleAlarmStatus INTEGER(0..255) OPTIONAL, engineStatus INTEGER(0..255), powerMode INTEGER(0..255), lastKeySeen INTEGER(0..65535), currentJourneyDistance INTEGER(0..65535), currentJourneyID INTEGER(0..2147483647), interiorTemperature INTEGER(-128..127), exteriorTemperature INTEGER(-128..127), fuelLevelPrc INTEGER(0..255), fuelRange INTEGER(0..65535), remoteClimateStatus INTEGER(0..255), frontLeftSeatHeatLevel INTEGER(0..255) OPTIONAL, frontRightSeatHeatLevel INTEGER(0..255) OPTIONAL, canBusActive BOOLEAN, timeOfLastCANBUSActivity INTEGER(0..2147483647), clstrDspdFuelLvlSgmt INTEGER(0..255), mileage INTEGER(0..2147483647), batteryVoltage INTEGER(0..65535), extendedData1 INTEGER(0..2147483647) OPTIONAL, extendedData2 INTEGER(0..2147483647) OPTIONAL, handBrake BOOLEAN }
RvsExtStatus ::= SEQUENCE { vehicleAlerts SEQUENCE SIZE(0..64) OF VehicleAlertInfo }
VehicleAlertInfo ::= SEQUENCE { id INTEGER(0..255), value INTEGER(0..255) }
END
"""
ASN_V11 = """MGIndiaTapV11Module
DEFINITIONS AUTOMATIC TAGS ::= BEGIN
MPDispatcherBodyV11 ::= SEQUENCE { uid IA5String(SIZE(50)) OPTIONAL, token IA5String(SIZE(40)) OPTIONAL, applicationID IA5String(SIZE(3)), vin IA5String(SIZE(17)) OPTIONAL, eventCreationTime INTEGER(0..4294967295), eventID INTEGER(0..281474976710655) OPTIONAL, messageID INTEGER(0..255), messageCounter MessageCounter OPTIONAL, ackRequired BOOLEAN OPTIONAL, statelessDispatcherMessage BOOLEAN OPTIONAL, crqmRequest BOOLEAN OPTIONAL, basicPosition BasicPosition OPTIONAL, networkInfo NetworkInfo OPTIONAL, simInfo NumericString(SIZE(19)) OPTIONAL, hmiLanguage LanguageType OPTIONAL, iccID NumericString(SIZE(20)), applicationDataLength INTEGER(0..4294967295), applicationDataEncoding DataEncodingType OPTIONAL, applicationDataProtocolVersion INTEGER(0..65535), testFlag INTEGER(1..3) OPTIONAL, result INTEGER(0..65535) OPTIONAL, errorMessage OCTET STRING(SIZE(1..1024)) OPTIONAL }
MessageCounter ::= SEQUENCE { uplinkCounter INTEGER(0..255), downlinkCounter INTEGER(0..255) }
BasicPosition ::= SEQUENCE { latitude INTEGER(-90000000..90000000), longitude INTEGER(-180000000..180000000) }
NetworkInfo ::= SEQUENCE { mccNetwork NumericString(SIZE(3)), mncNetwork NumericString(SIZE(3)), mccSim NumericString(SIZE(3)), mncSim NumericString(SIZE(3)), signalStrength INTEGER(0..99) }
LanguageType ::= ENUMERATED { simplifiedChinese(0), english(1), spanish(2), arabic(3), hindi(4) }
DataEncodingType ::= ENUMERATED { perUnaligned(0), der(1), ber(2) }
PINVerificationReq ::= SEQUENCE { pin IA5String(SIZE(32)) }
END
"""


@lru_cache(maxsize=1)
def codec21():
    return asn1tools.compile_string(ASN_V21, "uper")


@lru_cache(maxsize=1)
def codec11():
    return asn1tools.compile_string(ASN_V11, "uper")


def _dispatcher(
        uid: str,
        token: str,
        vin: str,
        app_id: str,
        app: bytes,
        event_id: int,
        msg_id: int = 0) -> bytes:
    return codec21().encode("MPDispatcherBody",
                            {"uid": uid,
                             "token": token,
                             "applicationID": app_id,
                             "vin": vin,
                             "messageID": msg_id,
                             "eventCreationTime": int(time.time()),
                             "eventID": event_id,
                             "applicationDataLength": len(app),
                             "applicationDataEncoding": "perUnaligned",
                             "applicationDataProtocolVersion": PROTOCOL}) + (b"\x00" * TAP_RESERVED_SIZE) + app


def encode_status_request(
        uid: str,
        token: str,
        vin: str,
        event_id: int) -> str:
    app = codec21().encode("OTARVMVehicleStatusReq", {"vehStatusReqType": 2})
    return (
        _dispatcher(
            uid,
            token,
            vin,
            STATUS_APP_ID,
            app,
            event_id)).hex().upper()


def encode_control_request(uid: str,
                           token: str,
                           vin: str,
                           event_id: int,
                           typ: int,
                           params: list[tuple[int,
                                              bytes]]) -> str:
    app = codec21().encode("OTARVCReq", {"rvcReqType": bytes([typ]), "rvcParams": [
        {"paramId": i, "paramValue": v} for i, v in params]})
    return (
        _dispatcher(
            uid,
            token,
            vin,
            CONTROL_APP_ID,
            app,
            event_id,
            1)).hex().upper()


def encode_pin_request(
        uid: str,
        token: str,
        vin: str,
        event_id: int,
        pin_hash: str) -> str:
    app = codec11().encode("PINVerificationReq", {"pin": pin_hash})
    body = codec11().encode("MPDispatcherBodyV11",
                            {"uid": uid,
                             "token": token,
                             "applicationID": PIN_APP_ID,
                             "vin": vin,
                             "eventCreationTime": int(time.time()),
                             "eventID": event_id,
                             "messageID": 1,
                             "iccID": "00000000000000000000",
                             "applicationDataLength": len(app),
                             "applicationDataEncoding": "perUnaligned",
                             "applicationDataProtocolVersion": PROTOCOL}) + (b"\x00" * TAP_RESERVED_SIZE) + app
    return body.hex().upper()


def _decode_v21(raw: str) -> tuple[dict[str, Any], bytes | None]:
    data = bytes.fromhex(raw)
    dispatcher = codec21().decode("MPDispatcherBody", data)
    length = dispatcher.get("applicationDataLength") or 0
    return dispatcher, data[-length:] if length else None


def decode_status_response(
        raw: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    disp, app = _decode_v21(raw)
    return disp, codec21().decode("OTARVMVehicleStatusResp513", app) if app else None


def decode_control_response(
        raw: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    disp, app = _decode_v21(raw)
    return disp, codec21().decode("OTARVCStatus513", app) if app else None
