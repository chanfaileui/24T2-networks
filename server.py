#! /usr/bin/env python3

"""
    Sample code for server
    Python 3
    Usage: python3 server.py server_port
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
import json
from pathlib import Path
import threading
import datetime, time  # to calculate the time delta of packet transmission
import logging, sys  # to write the log
import socket  # Core lib, to send packet via UDP socket
from threading import (
    Thread,
)  # (Optional)threading will make the timer easily implemented
import random  # for flp and rlp function

import struct

from classes import (
    DNSHeader,
    DNSQuestion,
    DNSRecord,
    DNSResponse,
    BUFFERSIZE,
    FLAG_RESPONSE,
    get_qtype,
    TYPE_A,
    TYPE_CNAME,
    TYPE_NS,
    TYPE_INVALID,
    get_qtype,
)

MASTER_FILE = "sample_master.txt"


class DNSCache:
    def __init__(self):
        self.cache = {}

    def get_cache(self):
        return self.cache

    def add_record(self, qname: str, qtype: str, record: str):
        qname = qname.lower()
        if qname not in self.cache:
            self.cache[qname] = {}
        if qtype not in self.cache[qname]:
            self.cache[qname][qtype] = []
        self.cache[qname][qtype].append(record)

    def get_records(self, qname: str, qtype: str) -> list:
        qname = qname.lower()
        return self.cache.get(qname, {}).get(qtype, [])

    def print(self):
        for qname, qtypes in self.cache.items():
            for qtype, records in qtypes.items():
                for record in records:
                    print(qname, qtype, record)


class Server:
    def __init__(self, server_port: int) -> None:
        """
        The server receives DNS query from the sender via UDP

        :param server_port: The UDP port number on which the server is listening.
        """
        self.address = "127.0.0.1"
        self.server_port = int(server_port)
        self.server_address = (self.address, self.server_port)

        # init the UDP socket
        # define socket for the server side and bind address
        self.server_socket = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_DGRAM
        )
        self.server_socket.bind(self.server_address)

        # creating DNS cache
        self.cache = DNSCache()
        self.load_records(MASTER_FILE)  # You need to implement this method

    def load_records(self, filename: str):
        # Implement loading records from the master file into self.cache
        filepath = Path(filename)

        if not filepath.exists():
            sys.exit(f"Error: {filename} does not exist.")

        with open(filename, "r") as f:
            for line in f:
                qname, qtype, record = line.split()
                self.cache.add_record(qname, qtype, record)

        # logging.info(f"Loaded {len(self.cache.get_cache())} records from {filename}")

    def run(self) -> None:
        # logging.info(
        #     f"The sender is using the address {self.server_address} to receive messages!"
        # )
        logging.info(f"Receiving at {self.server_address}:")
        while True:
            try:
                incoming_message, client_address = self.server_socket.recvfrom(
                    BUFFERSIZE
                )
                thread = threading.Thread(
                    target=self.handle_query, args=(incoming_message, client_address)
                )
                thread.start()
            except Exception as e:
                logging.error(f"Error in main loop: {e}")

    def handle_query(self, incoming_message, client_address) -> None:
        """
        This function contain the main logic of the server
        """
        # while True:
        # try to receive any incoming message from the sender
        try:
            received_time = datetime.datetime.now()
            # logging.debug(
            #     f"Get a new message: {incoming_message} from {client_address}"
            # )
            # header = incoming_message[:12]  # 12 bytes header
            # (qid, flags, qdcount, ancount, nscount, arcount) = struct.unpack(
            #     "!HHHHHH", header
            # )

            header = DNSHeader.parse_header(BytesIO(incoming_message[:12]))
            logging.debug(
                f"ID: {header.qid}, Flags: {header.flags}, QD_COUNT: {header.num_questions}, AN_COUNT: {header.num_answers}, AU_COUNT: {header.num_authorities}, ADD_COUNT: {header.num_additionals}"
            )

            questions = self.parse_questions(incoming_message, header.num_questions)
            if questions:
                for question in questions:
                    # TODO: UNCOMMENT BEFORE SUBMITTING!!!
                    # delay = random.randint(0, 4)
                    # print(f"{received_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} rcv {client_address[1]:<5}: {header.qid:<4} {question.qname:<15} {get_qtype(question.qtype):<5} (delay: {delay}s)")

                    # time.sleep(delay)

                    response = self.process_query(header.qid, question)
                    self.server_socket.sendto(response, client_address)

                    print("sent response", response)

                    sent_time = datetime.datetime.now()
                    print(
                        f"{sent_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} snd {client_address[1]:<5}: {header.qid:<4} {question.qname:<15} {get_qtype(question.qtype)}"
                    )

        except Exception as e:
            logging.error(f"Error handling query: {e}")

    def parse_questions(self, message, qdcount):
        try:
            offset = 12
            questions = []
            for _ in range(qdcount):
                qname, offset = self.decode_qname(message, offset)
                qtype = struct.unpack("!H", message[offset : offset + 2])[0]
                offset += 2  # 2 bytes for QTYPE
                questions.append(DNSQuestion(qname, qtype))
            return questions
        except Exception as e:
            logging.error(f"Error parsing question: {e}")

    def process_query(self, qid: int, question: DNSQuestion) -> bytes | None:
        try:
            qname = question.qname
            qtype = get_qtype(question.qtype)

            if qtype == "INVALID":
                raise ValueError("Invalid qtype")

            answers_str = self.cache.get_records(question.qname, qtype)
            answers = [
                DNSRecord(
                    name=question.qname,
                    type_=question.qtype,
                    data=self.encode_rdata(question.qtype, answer),
                )
                for answer in answers_str
            ]

            # resolve query
            if not answers and qtype != TYPE_CNAME:
                # check for a CNAME
                self.resolve_query(answers, qname)

            authority = []
            additional = []
            if not answers:
                ns_records = self.find_closest_nameservers(qname)
                authority = ns_records
                for ns_record in ns_records:
                    additional_record_name = self.cache.get_records(ns_record.data, "A")
                    if additional_record_name:
                        additional_records = [
                            DNSRecord(name=ns_record.data, type_=TYPE_A, data=ad)
                            for ad in additional_record_name
                        ]
                        additional.extend(additional_records)

            header = DNSHeader(
                qid=qid,
                flags=FLAG_RESPONSE,
                num_questions=1,
                num_answers=len(answers),
                num_authorities=len(authority),
                num_additionals=len(additional),
            )
            response = DNSResponse(
                header=header,
                question=[question],
                answer=answers,
                authority=authority,
                additional=additional,
            )

            return response.to_bytes()
        except Exception as e:
            logging.error(f"Error processing question: {e}")

    # CNAME resolution
    def resolve_query(self, answers, qname):
        cname_records = self.cache.get_records(qname, "CNAME")
        if cname_records:
            cname_record = cname_records[0]
            answers.append(DNSRecord(name=qname, type_=TYPE_CNAME, data=cname_record))

            new_qname = cname_record

            # find matching A records
            a_results = self.cache.get_records(new_qname, "A")
            if a_results:
                answers.extend(
                    [
                        DNSRecord(
                            name=new_qname,
                            type_=TYPE_A,
                            data=self.encode_rdata(TYPE_A, a),
                        )
                        for a in a_results
                    ]
                )
                return answers
            else:
                self.resolve_query(answers, new_qname)

        # no cname records or a records
        return answers

    def find_closest_nameservers(self, qname: str):
        ancestor_parts = qname.split(".")

        while ancestor_parts:
            ancestor = ".".join(ancestor_parts)
            ancestor = ancestor if ancestor else "."  # root domain

            resolve_ns = self.cache.get_records(ancestor, "NS")
            # print(self.cache.get_cache())
            if resolve_ns:
                ns_records = [
                    DNSRecord(name=ancestor, type_=TYPE_NS, data=ns)
                    for ns in resolve_ns
                ]
                logging.info("resolved NS")
                print("ns_records", ns_records)
                return ns_records

            ancestor_parts = ancestor_parts[1:]

        # If we've exhausted all ancestors (including root '.'), return an empty list
        return []

    @staticmethod
    def decode_qname(message, offset):
        # print(message[offset:])
        labels = []
        while True:
            length = message[offset]
            if length == 0:  # If the length is 0, it indicates the end of the QNAME
                offset += 1  # Move the offset past the null byte
                break
            labels.append(message[offset + 1 : offset + 1 + length].decode("ascii"))
            offset += 1 + length

        qname = ".".join(labels) + "."  # Re-add the trailing dot
        return qname, offset

    @staticmethod
    def encode_rdata(qtype: int, data: str):
        # if qtype == TYPE_A:
        #     return socket.inet_aton(data)  # Convert IP address to 4-byte format
        # else:
        # return data.encode("ascii")  # For other types, return ASCII-encoded bytes
        return data


if __name__ == "__main__":
    # logging is useful for the log part: https://docs.python.org/3/library/logging.html
    logging.basicConfig(
        # filename="server_log.txt",
        stream=sys.stderr,
        level=logging.DEBUG,
        # format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
        # datefmt="%Y-%m-%d %H:%M:%S",
        format="%(asctime)s.%(msecs)03d [%(threadName)s] %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if len(sys.argv) != 2:
        print("\n===== Error usage, python3 server.py server_port ======\n")
        exit(0)

    server = Server(int(sys.argv[1]))
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nExiting...")
