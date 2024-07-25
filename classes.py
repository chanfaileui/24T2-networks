#! /usr/bin/env python3

# according to https://datatracker.ietf.org/doc/html/rfc1035#section-3.2.2
from dataclasses import dataclass
import dataclasses
from io import BytesIO
import struct
from typing import List

# according to https://datatracker.ietf.org/doc/html/rfc1035#section-3.2.2
TYPE_INVALID = 0
TYPE_A = 1
TYPE_NS = 2
TYPE_CNAME = 5

FLAG_QUERY = 0
FLAG_RESPONSE = 1

BUFFERSIZE = 4096


def get_qtype(qtype):
    if qtype == TYPE_A:
        return "A"
    elif qtype == TYPE_CNAME:
        return "CNAME"
    elif qtype == TYPE_NS:
        return "NS"
    else:
        return "INVALID"


# with reference to https://implement-dns.wizardzines.com/book/part_1
@dataclass
class DNSHeader:
    qid: int  # 16-bit unsigned integer as an identifier for the query
    flags: int  # Flags to represent various settings (e.g., query/response)
    num_questions: int = 0
    num_answers: int = 0
    num_authorities: int = 0
    num_additionals: int = 0

    # with reference to https://implement-dns.wizardzines.com/book/part_1
    def to_bytes(self) -> bytes:
        fields = dataclasses.astuple(self)
        return struct.pack("!HHHHHH", *fields)

    # ref https://implement-dns.wizardzines.com/book/part_2
    @staticmethod
    def parse_header(reader):
        print('reader', reader)
        header_data = reader.read(12)
        if len(header_data) != 12:
            raise ValueError(f"Header data is not 12 bytes: {len(header_data)} bytes received. Data: {header_data}")
        items = struct.unpack("!HHHHHH", header_data)
        return DNSHeader(*items)
        # items = struct.unpack("!HHHHHH", reader.read(12))
        # return DNSHeader(*items)


@dataclass
class DNSQuestion:
    qname: str  # target domain name of query
    qtype: int  #  type of the query

    def to_bytes(self) -> bytes:
        if self.qname == ".":
            # Special case for the root domain
            qname_bytes = b"\x00"
        else:
            qname_parts = self.qname.split(".")
            # Remove the last empty part if qname ends with a dot
            if qname_parts[-1] == "":
                qname_parts = qname_parts[:-1]

            qname_bytes = (
                b"".join(
                    (len(part).to_bytes(1, "big") + part.encode("ascii"))
                    for part in qname_parts
                )
                + b"\x00"
            )
        return qname_bytes + self.qtype.to_bytes(2, byteorder="big")


@dataclass
class DNSRecord:
    name: str  # domain name
    type_: int  #  type of the resource record
    data: str  # type-dependent data which describes the resource

    def to_bytes(self) -> bytes:

        if self.name == ".":
            # Special case for the root domain
            name_bytes = b"\x00"
        else:
            name_parts = self.name.split(".")

            # Remove the last empty part if qname ends with a dot
            if name_parts[-1] == "":
                name_parts = name_parts[:-1]

            name_bytes = (
                b"".join(
                    (len(part).to_bytes(1, "big") + part.encode("ascii"))
                    for part in name_parts
                )
                + b"\0"
            )

        data_bytes = self.data.encode("ascii")
        type_bytes = self.type_.to_bytes(2, byteorder="big")
        return (
            name_bytes + type_bytes + struct.pack("!H", len(self.data)) + data_bytes
        )


@dataclass
class DNSResponse:
    header: DNSHeader
    question: List[DNSQuestion]
    answer: List[DNSRecord]
    authority: List[DNSRecord]
    additional: List[DNSRecord]

    def to_bytes(self) -> bytes:
        message = self.header.to_bytes()
        for q in self.question:
            message += q.to_bytes()
        for a in self.answer:
            message += a.to_bytes()
        for auth in self.authority:
            message += auth.to_bytes()
        for add in self.additional:
            message += add.to_bytes()
        return message

    # def to_bytes(self):
    #     message = self.header.to_bytes()
    #     print("message", message)
    #     print("question", self.question)
    #     for q in self.question:
    #         qname, qtype = q
    #         message += (
    #             qname.encode("ascii") + b"\0"
    #         )  # QNAME is a domain name ending with a null byte
    #         message += qtype.to_bytes(2, byteorder='big')  # QTYPE is 2 bytes
    #     print("final sent message", message)
    #     return message

    # @classmethod
    # def decode_name_simple(cls, reader) -> str:
    #     parts = []
    #     while (length := reader.read(1)[0]) != 0:
    #         parts.append(reader.read(length))
    #     return ".".join(parts)

    @classmethod
    def from_bytes(cls, data: bytes):
        print('data', data)
        reader = BytesIO(data)
        if len(data) < 12:
            raise ValueError(f"Data too short: expected at least 12 bytes, got {len(data)} bytes")
        header = DNSHeader.parse_header(reader)

        header = DNSHeader.parse_header(reader)

        questions = []
        for _ in range(header.num_questions):
            qname = cls.decode_name(reader)
            qtype = struct.unpack("!H", reader.read(2))[0]
            questions.append(DNSQuestion(qname, qtype))

        answers = [cls.parse_record(reader) for _ in range(header.num_answers)]
        authorities = [cls.parse_record(reader) for _ in range(header.num_authorities)]
        additionals = [cls.parse_record(reader) for _ in range(header.num_additionals)]

        return cls(header, questions, answers, authorities, additionals)

    # with reference to https://implement-dns.wizardzines.com/book/part_2
    @classmethod
    def decode_name(cls, reader):
        parts = []
        while True:
            length_bytes = reader.read(1)
            if not length_bytes:
                break  # End of buffer reached\\
            length = length_bytes[0]
            if length == 0:
                break
            elif length & 0b11000000 == 0b11000000:
                pointer = struct.unpack(
                    "!H", bytes([length & 0b00111111]) + reader.read(1)
                )[0]
                saved_position = reader.tell()
                reader.seek(pointer)
                parts.append(cls.decode_name(reader))
                reader.seek(saved_position)
                break
            else:
                parts.append(reader.read(length).decode("ascii"))
        
        # Check if parts is empty, indicating a root domain
        if not parts:
            return "."
        
        return ".".join(parts) + "."

    @staticmethod
    def parse_record(reader: BytesIO) -> DNSRecord:
        name = DNSResponse.decode_name(reader)
        type_, data_len = struct.unpack("!HH", reader.read(4))
        data = reader.read(data_len).decode("ascii")
        return DNSRecord(name, type_, data)
