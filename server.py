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
    FLAG_QUERY,
    TYPE_A,
    TYPE_CNAME,
    TYPE_NS,
    TYPE_INVALID,
    FLAG_QUERY,
    FLAG_RESPONSE,
)

MASTER_FILE = "sample_master.txt"


class DNSCache:
    def __init__(self):
        self.cache = {}

    def get_cache(self):
        return self.cache

    def add_record(self, qname, qtype, record):
        if qname not in self.cache:
            self.cache[qname] = {}
        if qtype not in self.cache[qname]:
            self.cache[qname][qtype] = []
        self.cache[qname][qtype].append(record)

    def get_records(self, qname, qtype):
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
        records = {}
        filepath = Path(filename)

        if not filepath.exists():
            sys.exit(f"Error: {filename} does not exist.")

        with open(filename, "r") as f:
            for line in f:
                qname, qtype, record = line.split()
                self.cache.add_record(qname, qtype, record)

        logging.info(f"Loaded {len(self.cache.get_cache())} records from {filename}")
        # print(self.cache.get_cache())

    def run(self) -> None:
        logging.info(
            f"The sender is using the address {self.server_address} to receive messages!"
        )
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
            logging.debug(
                f"Get a new message: {incoming_message} from {client_address}"
            )
            header = incoming_message[:12]  # 12 bytes header
            (qid, flags, qdcount, ancount, nscount, arcount) = struct.unpack(
                "!HHHHHH", header
            )

            logging.debug(
                f"ID: {qid}, Flags: {flags}, QDCOUNT: {qdcount}, ANCOUNT: {ancount}, NSCOUNT: {nscount}, ARCOUNT: {arcount}"
            )

            offset = 12
            questions = []
            for _ in range(qdcount):
                qname, offset = self.decode_qname(incoming_message, offset)
                qtype = int.from_bytes(
                    incoming_message[offset : offset + 2], byteorder="big"
                )  # 2 bytes for QTYPE
                offset += 2
                questions.append((qname, qtype))
                logging.debug(f"Question: {qname}, QTYPE: {qtype}")

            # answers = []
            # for _ in range(ancount):
            #     name, offset = self.decode_qname(incoming_message, offset)
            #     rtype, rclass, ttl, rdlength = struct.unpack('!HHIH', incoming_message[offset:offset + 10])
            #     offset += 10
            #     rdata = incoming_message[offset:offset + rdlength]
            #     offset += rdlength
            #     answers.append((name, rtype, rclass, ttl, rdlength, rdata))
            #     logging.debug(f'Answer: {name}, TYPE: {rtype}, CLASS: {rclass}, TTL: {ttl}, RDLENGTH: {rdlength}, RDATA: {rdata}')

        except Exception as e:
            logging.error(f"Error handling query: {e}")

        logging.debug(
            f"client{client_address} send a message: len= {len(incoming_message.decode('utf-8'))}"
        )
        reply_header = DNSHeader(qid=qid, flags=FLAG_RESPONSE, num_questions=qdcount)
        reply_message = DNSResponse(
            header=reply_header,
            question=questions,
            answer=[],
            authority=[],
            additional=[],
        )

        # print("reply_message.to_bytes()", reply_message.to_bytes())
        self.server_socket.sendto(reply_message.to_bytes(), client_address)

    def process_query(self, qid, question):
        pass

    def find_closest_nameservers(self, qname):
        # Implement logic to find the closest ancestor zone with known name servers
        pass

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
        return ".".join(labels), offset


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

    server = Server(*sys.argv[1:])
    server.run()
