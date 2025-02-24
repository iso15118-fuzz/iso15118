"""
This modules contains classes which implement all the elements of the
ISO 15118-2 XSD file V2G_CI_MsgHeader.xsd (see folder 'schemas').
In particular, this is the header element of the V2GMessages exchanged between
the EVCC and the SECC.


All classes are ultimately subclassed from pydantic's BaseModel to ease
validation when instantiating a class and to reduce boilerplate code.
Pydantic's Field class is used to be able to create a json schema of each model
(or class) that matches the definitions in the XSD schema, including the XSD
element names by using the 'alias' attribute.
"""

from pydantic import Field, validator

from iso15118.shared_evcc.messages import BaseModel
from iso15118.shared_evcc.messages.iso15118_2.datatypes import Notification
from iso15118.shared_evcc.messages.xmldsig import Signature


class MessageHeader(BaseModel):
    """See section 8.3.3 in ISO 15118-2"""

    # XSD type hexBinary with max 8 bytes encoded as 16 hexadecimal characters
    session_id: str = Field(..., alias="SessionID")
    notification: Notification = Field(None, alias="Notification")
    signature: Signature = Field(None, alias="Signature")
