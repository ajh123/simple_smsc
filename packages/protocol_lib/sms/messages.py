"""Dataclasses describing SMS PDUs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Union

from ..utils import Address
from .dcs import DataCodingScheme
from .user_data import UserData


@dataclass
class SMSDeliver:
    originating_address: Address
    pid: int
    dcs: DataCodingScheme
    service_center_time_stamp: datetime
    user_data: UserData
    status_report_indication: bool = False
    more_messages: bool = False
    reply_path: bool = False


@dataclass
class SMSSubmit:
    message_reference: int
    destination_address: Address
    pid: int
    dcs: DataCodingScheme
    user_data: UserData
    status_report_request: bool = False
    reject_duplicates: bool = False
    reply_path: bool = False
    validity_period: Optional[Union[timedelta, datetime]] = None
    validity_period_format: str = "none"


@dataclass
class SMSStatusReport:
    message_reference: int
    recipient_address: Address
    service_center_time_stamp: datetime
    discharge_time: datetime
    status: int
    pid: Optional[int] = None
    dcs: Optional[DataCodingScheme] = None
    user_data: Optional[UserData] = None
    more_messages: bool = False
    status_report_qualifier: bool = False
    reply_path: bool = False


@dataclass
class SMSMessage:
    smsc: Optional[Address]
    tpdu: Union[SMSDeliver, SMSSubmit, SMSStatusReport]

    @property
    def mti(self) -> int:
        if isinstance(self.tpdu, SMSDeliver):
            return 0
        if isinstance(self.tpdu, SMSSubmit):
            return 1
        return 2


__all__ = [
    "SMSDeliver",
    "SMSSubmit",
    "SMSStatusReport",
    "SMSMessage",
]
