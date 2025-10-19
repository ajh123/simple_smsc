"""High level encode/decode helpers for application/vnd.3gpp.sms."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Tuple, Union
import binascii

from ..utils import (
    Address,
    decode_address,
    decode_relative_validity,
    decode_smsc,
    decode_timestamp,
    encode_address,
    encode_relative_validity,
    encode_smsc,
    encode_timestamp,
)
from .dcs import DataCodingScheme
from .messages import SMSDeliver, SMSMessage, SMSStatusReport, SMSSubmit
from .user_data import (
    UserData,
    decode_user_data,
    encode_user_data,
    extract_user_data_bytes,
)


def decode_sms(data: Union[bytes, str]) -> SMSMessage:
    raw = binascii.unhexlify(data) if isinstance(data, str) else bytes(data)
    if not raw:
        raise ValueError("Empty payload is not a valid TPDU")
    idx = 0
    smsc, idx = decode_smsc(raw, idx)
    if idx >= len(raw):
        raise ValueError("Missing TPDU after SMSC header")
    first_octet = raw[idx]
    mti = first_octet & 0x03
    if mti == 0:
        tpdu, idx = _decode_deliver(raw, idx)
    elif mti == 1:
        tpdu, idx = _decode_submit(raw, idx)
    elif mti == 2:
        tpdu, idx = _decode_status_report(raw, idx)
    else:
        raise ValueError(f"Unsupported MTI {mti}")
    if idx != len(raw):
        raise ValueError("Extra trailing data detected in TPDU")
    return SMSMessage(smsc=smsc, tpdu=tpdu)


def encode_sms(message: SMSMessage) -> bytes:
    result = bytearray()
    result.extend(encode_smsc(message.smsc))
    result.extend(_encode_tpdu(message.tpdu))
    return bytes(result)


def encode_sms_hex(message: SMSMessage) -> str:
    return binascii.hexlify(encode_sms(message)).decode("ascii")


def _encode_tpdu(tpdu: Union[SMSDeliver, SMSSubmit, SMSStatusReport]) -> bytes:
    if isinstance(tpdu, SMSDeliver):
        return _encode_deliver(tpdu)
    if isinstance(tpdu, SMSSubmit):
        return _encode_submit(tpdu)
    if isinstance(tpdu, SMSStatusReport):
        return _encode_status_report(tpdu)
    raise TypeError("Unsupported TPDU type")


def _decode_deliver(data: bytes, offset: int) -> Tuple[SMSDeliver, int]:
    first_octet = data[offset]
    offset += 1
    reply_path = bool(first_octet & 0x80)
    udhi = bool(first_octet & 0x40)
    status_report_indication = bool(first_octet & 0x20)
    more_messages = not bool(first_octet & 0x04)
    originating, offset = decode_address(data, offset)
    pid = data[offset]
    dcs = DataCodingScheme(data[offset + 1])
    offset += 2
    scts = decode_timestamp(data[offset : offset + 7])
    offset += 7
    udl = data[offset]
    offset += 1
    ud_bytes, offset = extract_user_data_bytes(data, offset, udl, dcs.alphabet, udhi)
    user_data = decode_user_data(ud_bytes, udl, dcs, udhi)
    deliver = SMSDeliver(
        originating_address=originating,
        pid=pid,
        dcs=dcs,
        service_center_time_stamp=scts,
        user_data=user_data,
        status_report_indication=status_report_indication,
        more_messages=more_messages,
        reply_path=reply_path,
    )
    return deliver, offset


def _encode_deliver(deliver: SMSDeliver) -> bytes:
    first_octet = 0
    if deliver.reply_path:
        first_octet |= 0x80
    if deliver.user_data.header is not None:
        first_octet |= 0x40
    if deliver.status_report_indication:
        first_octet |= 0x20
    if not deliver.more_messages:
        first_octet |= 0x04
    result = bytearray([first_octet])
    result.extend(encode_address(deliver.originating_address))
    result.append(deliver.pid & 0xFF)
    result.append(deliver.dcs.raw & 0xFF)
    result.extend(encode_timestamp(deliver.service_center_time_stamp))
    udl, ud_bytes = encode_user_data(deliver.user_data, deliver.dcs)
    result.append(udl & 0xFF)
    result.extend(ud_bytes)
    return bytes(result)


def _decode_submit(data: bytes, offset: int) -> Tuple[SMSSubmit, int]:
    first_octet = data[offset]
    offset += 1
    reply_path = bool(first_octet & 0x80)
    udhi = bool(first_octet & 0x40)
    status_report_request = bool(first_octet & 0x20)
    vpf = (first_octet >> 3) & 0x03
    reject_duplicates = bool(first_octet & 0x04)
    mr = data[offset]
    offset += 1
    destination, offset = decode_address(data, offset)
    pid = data[offset]
    dcs = DataCodingScheme(data[offset + 1])
    offset += 2
    vp_value: Optional[Union[timedelta, datetime]] = None
    vp_format = "none"
    if vpf == 2:
        vp_value = decode_relative_validity(data[offset])
        vp_format = "relative"
        offset += 1
    elif vpf == 3:
        vp_value = decode_timestamp(data[offset : offset + 7])
        vp_format = "absolute"
        offset += 7
    udl = data[offset]
    offset += 1
    ud_bytes, offset = extract_user_data_bytes(data, offset, udl, dcs.alphabet, udhi)
    user_data = decode_user_data(ud_bytes, udl, dcs, udhi)
    submit = SMSSubmit(
        message_reference=mr,
        destination_address=destination,
        pid=pid,
        dcs=dcs,
        user_data=user_data,
        status_report_request=status_report_request,
        reject_duplicates=reject_duplicates,
        reply_path=reply_path,
        validity_period=vp_value,
        validity_period_format=vp_format,
    )
    return submit, offset


def _encode_submit(submit: SMSSubmit) -> bytes:
    first_octet = 0x01
    if submit.reply_path:
        first_octet |= 0x80
    if submit.user_data.header is not None:
        first_octet |= 0x40
    if submit.status_report_request:
        first_octet |= 0x20
    if submit.reject_duplicates:
        first_octet |= 0x04
    vpf_bits = 0
    vp_field: list[int] = []
    vp = submit.validity_period
    fmt = submit.validity_period_format or "none"
    if vp is not None:
        if isinstance(vp, timedelta) and fmt in ("none", "relative"):
            vpf_bits = 0x10
            vp_field.append(encode_relative_validity(vp))
        elif isinstance(vp, datetime) and fmt == "absolute":
            vpf_bits = 0x18
            vp_field.extend(encode_timestamp(vp))
        elif fmt == "relative" and isinstance(vp, timedelta):
            vpf_bits = 0x10
            vp_field.append(encode_relative_validity(vp))
        elif fmt == "absolute" and isinstance(vp, datetime):
            vpf_bits = 0x18
            vp_field.extend(encode_timestamp(vp))
        else:
            raise ValueError("Unsupported validity period format")
    first_octet |= vpf_bits
    result = bytearray([first_octet, submit.message_reference & 0xFF])
    result.extend(encode_address(submit.destination_address))
    result.append(submit.pid & 0xFF)
    result.append(submit.dcs.raw & 0xFF)
    result.extend(vp_field)
    udl, ud_bytes = encode_user_data(submit.user_data, submit.dcs)
    result.append(udl & 0xFF)
    result.extend(ud_bytes)
    return bytes(result)


def _decode_status_report(data: bytes, offset: int) -> Tuple[SMSStatusReport, int]:
    first_octet = data[offset]
    offset += 1
    reply_path = bool(first_octet & 0x80)
    udhi = bool(first_octet & 0x40)
    status_report_qualifier = bool(first_octet & 0x20)
    more_messages = not bool(first_octet & 0x04)
    mr = data[offset]
    offset += 1
    recipient, offset = decode_address(data, offset)
    scts = decode_timestamp(data[offset : offset + 7])
    offset += 7
    dt = decode_timestamp(data[offset : offset + 7])
    offset += 7
    status = data[offset]
    offset += 1
    pid: Optional[int] = None
    dcs: Optional[DataCodingScheme] = None
    user_data: Optional[UserData] = None
    if offset < len(data):
        tp_pi = data[offset]
        offset += 1
        if tp_pi & 0x01:
            pid = data[offset]
            offset += 1
        if tp_pi & 0x02:
            dcs = DataCodingScheme(data[offset])
            offset += 1
        if tp_pi & 0x04:
            if dcs is None:
                raise ValueError("TP-UD requested but TP-DCS missing in status report")
            udl = data[offset]
            offset += 1
            ud_bytes, offset = extract_user_data_bytes(
                data, offset, udl, dcs.alphabet, udhi
            )
            user_data = decode_user_data(ud_bytes, udl, dcs, udhi)
    report = SMSStatusReport(
        message_reference=mr,
        recipient_address=recipient,
        service_center_time_stamp=scts,
        discharge_time=dt,
        status=status,
        pid=pid,
        dcs=dcs,
        user_data=user_data,
        more_messages=more_messages,
        status_report_qualifier=status_report_qualifier,
        reply_path=reply_path,
    )
    return report, offset


def _encode_status_report(report: SMSStatusReport) -> bytes:
    first_octet = 0x02
    if report.reply_path:
        first_octet |= 0x80
    if report.user_data and report.user_data.header is not None:
        first_octet |= 0x40
    if report.status_report_qualifier:
        first_octet |= 0x20
    if not report.more_messages:
        first_octet |= 0x04
    result = bytearray([first_octet, report.message_reference & 0xFF])
    result.extend(encode_address(report.recipient_address))
    result.extend(encode_timestamp(report.service_center_time_stamp))
    result.extend(encode_timestamp(report.discharge_time))
    result.append(report.status & 0xFF)
    tp_pi = 0
    payload = bytearray()
    if report.pid is not None:
        tp_pi |= 0x01
        payload.append(report.pid & 0xFF)
    if report.dcs is not None:
        tp_pi |= 0x02
        payload.append(report.dcs.raw & 0xFF)
    if report.user_data is not None:
        if report.dcs is None:
            raise ValueError("Status report user data requires a data coding scheme")
        tp_pi |= 0x04
        udl, ud_bytes = encode_user_data(report.user_data, report.dcs)
        payload.append(udl & 0xFF)
        payload.extend(ud_bytes)
    if tp_pi:
        result.append(tp_pi & 0xFF)
        result.extend(payload)
    return bytes(result)


__all__ = ["decode_sms", "encode_sms", "encode_sms_hex"]
