# according to https://datatracker.ietf.org/doc/html/rfc1035#section-3.2.2
from dataclasses import dataclass
import struct
from typing import List


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

    def to_bytes(self):
        return struct.pack(
            "!HHHHHH",
            self.qid,
            self.flags,
            self.num_questions,
            self.num_answers,
            self.num_authorities,
            self.num_additionals,
        )


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
            qname, qtype, qclass = q
            message += (
                qname.encode("ascii") + b"\0"
            )  # QNAME is a domain name ending with a null byte
            message += struct.pack(
                "!HH", qtype, qclass
            )  # QTYPE and QCLASS are both 2 bytes
        return message

