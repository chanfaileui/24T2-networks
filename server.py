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
import datetime, time  # to calculate the time delta of packet transmission
import logging, sys  # to write the log
import socket  # Core lib, to send packet via UDP socket
from threading import (
    Thread,
)  # (Optional)threading will make the timer easily implemented
import random  # for flp and rlp function


from dataclasses import dataclass
import dataclasses
import struct
from typing import List

from client import DNSQuestion

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
        logging.debug(
            f"The sender is using the address {self.server_address} to receive message!"
        )
        self.server_socket = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_DGRAM
        )
        self.server_socket.bind(self.server_address)

    def run(self) -> None:
        """
        This function contain the main logic of the server
        """
        while True:
            # try to receive any incoming message from the sender
            try:
                incoming_message, sender_address = self.server_socket.recvfrom(
                    BUFFERSIZE
                )
                logging.debug(
                    f"Get a new message: {incoming_message} from {sender_address}"
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
                    qtype, qclass = struct.unpack(
                        "!HH", incoming_message[offset : offset + 4]
                    )  # 2 bytes for QTYPE, 2 bytes for QCLASS
                    offset += 4
                    questions.append((qname, qtype, qclass))
                    logging.debug(
                        f"Question: {qname}, QTYPE: {qtype}, QCLASS: {qclass}"
                    )

                # answers = []
                # for _ in range(ancount):
                #     name, offset = self.decode_qname(incoming_message, offset)
                #     rtype, rclass, ttl, rdlength = struct.unpack('!HHIH', incoming_message[offset:offset + 10])
                #     offset += 10
                #     rdata = incoming_message[offset:offset + rdlength]
                #     offset += rdlength
                #     answers.append((name, rtype, rclass, ttl, rdlength, rdata))
                #     logging.debug(f'Answer: {name}, TYPE: {rtype}, CLASS: {rclass}, TTL: {ttl}, RDLENGTH: {rdlength}, RDATA: {rdata}')

            except ConnectionResetError:
                continue

            logging.debug(
                f"client{sender_address} send a message: len= {len(incoming_message.decode('utf-8'))}"
            )
            # with open(self.filename, "a+") as file:
            #     file.write(incoming_message.decode())

            # reply "ACK" once receive any message from sender
            reply_header = DNSHeader(
                qid=qid, flags=FLAG_RESPONSE, num_questions=qdcount
            )
            reply_message = DNSResponse(
                header=reply_header,
                question=questions,
                answer=[],
                authority=[],
                additional=[],
            )

            # print("reply_message.to_bytes()", reply_message.to_bytes())
            self.server_socket.sendto(reply_message.to_bytes(), sender_address)

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
        format="%(asctime)s,%(msecs)03d %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d:%H:%M:%S",
    )

    if len(sys.argv) != 2:
        print("\n===== Error usage, python3 server.py server_port ======\n")
        exit(0)

    server = Server(*sys.argv[1:])
    server.run()
