#! /usr/bin/env python3

"""
    Sample code for client (multi-threading)
    Python 3
    Usage: python3 client.py server_port qname qtype timeout
    coding: utf-8

    Notes:
        Try to run the server first with the command:
            python3 server.py server_port
        Then run the client:
            python3 client.py server_port qname qtype timeout

    Author: Fai Chan (z5411219)
    With reference to template material from Rui Li (Tutor for COMP3331/9331)
    https://github.com/lrlrlrlr/COMP3331_9331_23T1_Labs/tree/main/demo%20w8
"""
# here are the libs you may find it useful:
from io import BytesIO
import datetime, time  # to calculate the time delta of packet transmission
import logging, sys  # to write the log
import random
import socket  # Core lib, to send packet via UDP socket
from threading import (
    Thread,
)  # (Optional)threading will make the timer easily implemented
from dataclasses import dataclass
import dataclasses
import struct
from typing import List

BUFFERSIZE = 1024

HEADER_FIELDS = 4

FLAG_QUERY = 0
FLAG_RESPONSE = 1

# according to https://datatracker.ietf.org/doc/html/rfc1035#section-3.2.2
TYPE_INVALID = 0
TYPE_A = 1
TYPE_NS = 2
TYPE_CNAME = 5


# with reference to https://implement-dns.wizardzines.com/book/part_1
@dataclass
class DNSHeader:
    qid: int  # 16-bit unsigned integer as an identifier for the query
    flags: int  # Flags to represent various settings (e.g., query/response)
    num_questions: int = 0
    num_answers: int = 0
    num_authorities: int = 0
    num_additionals: int = 0

    @classmethod
    def from_bytes(cls, data: bytes):
        qid, flags, num_questions, num_answers, num_authorities, num_additionals = struct.unpack('!HHHHHH', data[:12])
        return cls(qid, flags, num_questions, num_answers, num_authorities, num_additionals)



@dataclass
class DNSQuestion:
    qname: int  # target domain name of query
    qtype: int  #  type of the query
    qclass: int = 1  # 1 for internet


@dataclass
class DNSRecord:
    name: bytes  # domain name
    type_: int  #  type of the resource record
    data: bytes  # type-dependent data which describes the resource


@dataclass
class DNSResponse:
    header: DNSHeader
    question: List[DNSQuestion]
    answer: List[DNSRecord]
    authority: List[DNSRecord]
    additional: List[DNSRecord]

    @classmethod
    def from_bytes(cls, data: bytes):
        reader = BytesIO(data)
        
        # Parse the header
        header = DNSHeader.from_bytes(reader.read(12))

        # Parse the questions
        questions = []
        for _ in range(header.num_questions):
            qname = cls.decode_name(reader)
            qtype, qclass = struct.unpack('!HH', reader.read(4))
            questions.append(DNSQuestion(qname, qtype, qclass))

        # Parse the answers
        answers = [cls.parse_record(reader) for _ in range(header.num_answers)]

        # Parse the authorities
        authorities = [cls.parse_record(reader) for _ in range(header.num_authorities)]

        # Parse the additionals
        additionals = [cls.parse_record(reader) for _ in range(header.num_additionals)]

        return cls(header, questions, answers, authorities, additionals)

    @staticmethod
    def decode_name(reader: BytesIO) -> str:
        parts = []
        while True:
            length = reader.read(1)[0]
            if length == 0:
                break
            elif length & 0b11000000 == 0b11000000:
                pointer = struct.unpack('!H', reader.read(1))[0] & 0x3FFF
                current_pos = reader.tell()
                reader.seek(pointer)
                parts.append(DNSResponse.decode_name(reader))
                reader.seek(current_pos)
                break
            else:
                parts.append(reader.read(length).decode('ascii'))
        return '.'.join(parts)

    @staticmethod
    def parse_record(reader: BytesIO) -> DNSRecord:
        name = DNSResponse.decode_name(reader)
        type_, class_, ttl, data_len = struct.unpack('!HHIH', reader.read(10))
        data = reader.read(data_len)
        return DNSRecord(name, type_, class_, ttl, data_len, data)



class Client:
    def __init__(
        self,
        server_port: int,
        qname: str,
        qtype: str,
        timeout: int,
    ) -> None:
        """
        Initialize the Client instance for querying DNS records via UDP.

        :param server_port: The UDP port number on which the server is listening.
        :param qname: The target domain name of the query.
        :param qtype: The type of the query ('A', 'CNAME', 'NS').
        :param timeout: The duration (in seconds) the client should wait for a response before considering it a failure.
        :param client_port: The UDP port number to be used by the client for sending queries (default is CLIENT_PORT).
        """
        self.server_port = int(server_port)
        self.server_address = ("127.0.0.1", self.server_port)
        self.qname = qname
        self.qtype = qtype
        self.timeout = int(timeout)

        # init the UDP socket (ephemeral port)
        self.client_socket = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_DGRAM
        )
        logging.debug(f"The client is using the address {self.client_socket}")

        #  (Optional) start the listening sub-thread first
        self._is_active = True  # for the multi-threading
        self.listen_thread = Thread(target=self.listen)
        self.listen_thread.start()

        # todo add codes here
        pass

    def create_and_send_query(self):
        """
        Construct and send the DNS query to the server.

        """
        qid = random.randint(1, 2 ^ 16 - 1)
        header = DNSHeader(qid=qid, flags=FLAG_QUERY, num_questions=1)
        header_bytes = self.header_to_bytes(header)

        # Determine the query type based on the input
        qtype = (
            TYPE_A
            if self.qtype == "A"
            else (
                TYPE_CNAME
                if self.qtype == "CNAME"
                else TYPE_NS if self.qtype == "NS" else TYPE_INVALID
            )
        )
        question = DNSQuestion(qname=self.qname, qtype=qtype)
        question_bytes = self.question_to_bytes(question)

        content = header_bytes + question_bytes

        logging.debug(f"ts: {datetime.datetime.timestamp(datetime.datetime.now())}")
        self.client_socket.sendto(content, self.server_address)
        logging.debug(f"Sent DNS query for {self.qname} ({self.qtype})")

    def listen(self):
        """(Multithread is used)listen the response from receiver"""
        logging.debug("Sub-thread for listening is running")

        while self._is_active:
            try:
                self.client_socket.settimeout(self.timeout)
                incoming_message, _ = self.client_socket.recvfrom(BUFFERSIZE)
                logging.info(f"received reply from receiver:, {incoming_message}")
                # decoded_message = incoming_message.decode("utf-8")
                # logging.info(f"decoded reply from receiver:, {decoded_message}")
                self.handle_response(incoming_message)
                # logging.info(
                #     f"received reply from receiver:, {incoming_message.decode('utf-8')}"
                # )
                # self.handle_response(incoming_message)
                self._is_active = False  # Stop listening after receiving the response
            except socket.timeout:
                logging.error("Request timed out")
                self._is_active = False
            except OSError as e:
                if not self._is_active:
                    # Socket was closed as expected
                    break
                else:
                    raise e

        while self._is_active:
            # todo add socket
            incoming_message, _ = self.client_socket.recvfrom(BUFFERSIZE)

    def handle_response(self, response):
        """
        Process the DNS response from the server.

        :param response: The response packet from the server.
        """
        print('response received:', response)
        dns_response = DNSResponse.from_bytes(response)
        print(dns_response)
        # reader = BytesIO(response)
        # header = self.parse_header(reader)
        # questions = [self.parse_question(reader) for _ in range(header.num_questions)]
        # answers = [self.parse_record(reader) for _ in range(header.num_answers)]
        # authorities = [self.parse_record(reader) for _ in range(header.num_authorities)]
        # additionals = [self.parse_record(reader) for _ in range(header.num_additionals)]

        # # Print the response in the required format
        # print(f"QID: {header.qid}")

        # print("\nQuestion Section:")
        # for question in questions:
        #     print(f"QNAME: {question.qname}, QTYPE: {question.qtype}")

        # if answers:
        #     print("\nAnswer Section:")
        #     for answer in answers:
        #         self.print_record(answer)

        # if authorities:
        #     print("\nAuthority Section:")
        #     for authority in authorities:
        #         self.print_record(authority)

        # if additionals:
        #     print("\nAdditional Section:")
        #     for additional in additionals:
        #         self.print_record(additional)

    def decode_name(self, reader):
        parts = []
        while (length := reader.read(1)[0]) != 0:
            if length & 0b1100_0000:
                parts.append(self.decode_compressed_name(length, reader))
                break
            else:
                parts.append(reader.read(length))
        return b".".join(parts)

    def decode_compressed_name(self, length, reader):
        pointer_bytes = bytes([length & 0b0011_1111]) + reader.read(1)
        pointer = struct.unpack("!H", pointer_bytes)[0]
        current_pos = reader.tell()
        reader.seek(pointer)
        result = self.decode_name(reader)
        reader.seek(current_pos)
        return result

    def parse_record(self, reader):
        name = self.decode_name(reader)
        data = reader.read(10)
        type_, class_, ttl, data_len = struct.unpack("!HHIH", data)
        data = reader.read(data_len)
        return DNSRecord(name, type_, class_, ttl, data)

    def parse_question(self, reader):
        name = self.decode_name(reader)
        data = reader.read(4)
        type_, class_ = struct.unpack("!HH", data)
        return DNSQuestion(name, type_, class_)

    def parse_header(self, reader):
        items = struct.unpack("!HHHHHH", reader.read(12))
        # see "a note on BytesIO" for an explanation of `reader` here
        return DNSHeader(*items)

    def run(self):
        """
        This function contain the main logic of the receiver
        """
        self.create_and_send_query()

        time.sleep(self.timeout + 1)
        self._is_active = False  # close the sub-thread

        self.client_socket.close()
        logging.info("Socket closed.")
        self.listen_thread.join()

    # with reference to https://implement-dns.wizardzines.com/book/part_1
    @staticmethod
    def header_to_bytes(header: DNSHeader) -> bytes:
        fields = dataclasses.astuple(header)
        return struct.pack(
            "!HHHHHH", *fields
        )  # there are 4 `H`s because there are 4 fields

    @staticmethod
    def question_to_bytes(question: DNSQuestion) -> bytes:
        """
        Convert the DNSQuestion dataclass to bytes.

        :param question: DNSQuestion dataclass instance
        :return: Byte representation of the DNS question
        """
        qname_parts = question.qname.split(".")
        qname_bytes = (
            b"".join(
                (len(part).to_bytes(1, "big") + part.encode("ascii"))
                for part in qname_parts
            )
            # + b"\x00"
        )
        return qname_bytes + struct.pack(
            "!HH", question.qtype, 1
        )  # 1 here means "IN" (the internet)


if __name__ == "__main__":
    # logging is useful for the log part: https://docs.python.org/3/library/logging.html
    logging.basicConfig(
        # filename="client_log.txt",
        stream=sys.stderr,
        level=logging.DEBUG,
        format="%(asctime)s,%(msecs)03d [%(threadName)s] %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d:%H:%M:%S",
    )

    if len(sys.argv) != 5:
        print(
            "\n===== Error usage, python3 client.py server_port qname qtype timeout ======\n"
        )
        exit(0)

    client = Client(*sys.argv[1:])
    client.run()
