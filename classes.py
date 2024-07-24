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


# with reference to https://implement-dns.wizardzines.com/book/part_1
@dataclass
class DNSHeader:
    qid: int  # 16-bit unsigned integer as an identifier for the query
    flags: int  # Flags to represent various settings (e.g., query/response)
    num_questions: int = 0
    num_answers: int = 0
    num_authorities: int = 0
    num_additionals: int = 0

    def to_bytes(self) -> bytes:
        fields = dataclasses.astuple(self)
        return struct.pack("!HHHHHH", *fields)

    # ref https://implement-dns.wizardzines.com/book/part_2
    def parse_header(reader):
        items = struct.unpack("!HHHHHH", reader.read(12))
        return DNSHeader(*items)


@dataclass
class DNSQuestion:
    qname: int  # target domain name of query
    qtype: int  #  type of the query
    # qclass: int = 1  # 1 for internet


@dataclass
class DNSRecord:
    name: bytes  # domain name
    type_: int  #  type of the resource record
    data: bytes  # type-dependent data which describes the resource

    def to_bytes(self):
        return (
            self.name
            + struct.pack("!HHI", self.type_, 1, 300)
            + struct.pack("!H", len(self.data))
            + self.data
        )


@dataclass
class DNSResponse:
    header: DNSHeader
    question: List[DNSQuestion]
    answer: List[DNSRecord]
    authority: List[DNSRecord]
    additional: List[DNSRecord]

    def to_bytes(self):
        message = self.header.to_bytes()
        print("message", message)
        print("question", self.question)
        for q in self.question:
            qname, qtype = q
            message += (
                qname.encode("ascii") + b"\0"
            )  # QNAME is a domain name ending with a null byte
            message += qtype.to_bytes(2, byteorder='big')  # QTYPE is 2 bytes
        print("final sent message", message)
        return message

    @classmethod
    def decode_name_simple(cls, reader) -> str:
        parts = []
        while (length := reader.read(1)[0]) != 0:
            parts.append(reader.read(length))
        return ".".join(parts)

    @classmethod
    def from_bytes(cls, data: bytes):
        reader = BytesIO(data)
        header = DNSHeader.parse_header(reader)
        print("received header", header)

        # Parse the questions
        questions = []
        for _ in range(header.num_questions):
            name = cls.decode_name(reader)
            data = reader.read(2)
            type_ = struct.unpack("!H", data) 
            # int.from_bytes(data, byteorder='big')

            questions.append(DNSQuestion(name, type_))
        print("questions", questions)

        # Parse the answers
        answers = []
        for _ in range(header.num_answers):
            answers.append(cls.parse_record(reader))

        # Parse the authority records
        authorities = []
        for _ in range(header.num_authorities):
            authorities.append(cls.parse_record(reader))

        # Parse the additional records
        additionals = []
        for _ in range(header.num_additionals):
            additionals.append(cls.parse_record(reader))

        return cls(header, questions, answers, authorities, additionals)

    @classmethod
    def decode_name(cls, reader):
        parts = []
        while True:
            length_bytes = reader.read(1)
            if not length_bytes:
                break  # End of buffer reached
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
        return ".".join(parts) if parts else ""

    @staticmethod
    def parse_record(reader: BytesIO) -> DNSRecord:
        name = DNSResponse.decode_name(reader)
        type_, data_len = struct.unpack("!HH", reader.read(10))
        data = reader.read(data_len)
        return DNSRecord(name, type_, data)
