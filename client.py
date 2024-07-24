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
import threading
import datetime, time  # to calculate the time delta of packet transmission
import logging, sys  # to write the log
import random
import socket  # Core lib, to send packet via UDP socket
from threading import (
    Thread,
)  # (Optional)threading will make the timer easily implemented
import dataclasses
import struct

from classes import (
    DNSHeader,
    DNSQuestion,
    # DNSRecord,
    DNSResponse,
    BUFFERSIZE,
    FLAG_QUERY,
    TYPE_A,
    TYPE_CNAME,
    TYPE_NS,
    TYPE_INVALID,
    get_qtype,
)


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

        #  (Optional) start the listening sub-thread first
        self._is_active = True  # for the multi-threading
        self.response_received_event = threading.Event()
        self.listen_thread = Thread(target=self.listen)
        self.listen_thread.start()

    def create_and_send_query(self):
        """
        Construct and send the DNS query to the server.

        """
        qid = random.randint(1, 2**16 - 1)
        header = DNSHeader(qid=qid, flags=FLAG_QUERY, num_questions=1)
        header_bytes = header.to_bytes()

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
        question_bytes = question.to_bytes()

        content = header_bytes + question_bytes

        # logging.debug(f"ts: {datetime.datetime.timestamp(datetime.datetime.now())}")
        self.client_socket.sendto(content, self.server_address)
        # logging.debug(f"Sent DNS query for {self.qname} ({self.qtype})")

    def listen(self):
        """(Multithread is used)listen the response from receiver"""
        logging.debug("Sub-thread for listening is running")

        while self._is_active:
            try:
                self.client_socket.settimeout(self.timeout)
                incoming_message, _ = self.client_socket.recvfrom(BUFFERSIZE)
                # logging.info(f"received reply from receiver:, {incoming_message}")
                # decoded_message = incoming_message.decode("utf-8")
                # logging.info(f"decoded reply from receiver:, {decoded_message}")
                self.handle_response(incoming_message)
                self.response_received_event.set()
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
            incoming_message, _ = self.client_socket.recvfrom(BUFFERSIZE)

    def handle_response(self, response):
        """
        Process the DNS response from the server.

        :param response: The response packet from the server.
        """
        # print("response received:", response)
        dns_response = DNSResponse.from_bytes(response)
        # print('dns reponse', dns_response)

        header = dns_response.header
        questions = dns_response.question
        answers = dns_response.answer
        authorities = dns_response.authority
        additionals = dns_response.additional

        # Print the response in the required format
        print(f"QID: {header.qid}")

        print("\nQUESTION SECTION:")
        for question in questions:
            print(f"{question.qname:20}{get_qtype(question.qtype):5}")

        if answers:
            print("\nANSWER SECTION:")
            for answer in answers:
                self.print_record(answer)

        if authorities:
            print("\nAUTHORITY SECTION:")
            for authority in authorities:
                self.print_record(authority)

        if additionals:
            print("\nADDITIONAL SECTION:")
            for additional in additionals:
                self.print_record(additional)

        return dns_response

    def print_record(self, record):
        print(
            f"{record.name:20}{get_qtype(record.type_):5}{record.data:20}"
        )

    def decode_name(self, reader):
        parts = []

        length_bytes = reader.read(1)
        if not length_bytes:  # Check if no bytes were read
            raise IndexError("No more bytes to read.")

        while (length := reader.read(1)[0]) != 0:
            if length & 0b1100_0000:
                parts.append(self.decode_compressed_name(length, reader))
                break
            else:
                parts.append(reader.read(length).decode("utf-8"))
        return ".".join(parts) + "."

    def decode_compressed_name(self, length, reader):
        pointer_bytes = bytes([length & 0b0011_1111]) + reader.read(1)
        pointer = struct.unpack("!H", pointer_bytes)[0]
        current_pos = reader.tell()
        reader.seek(pointer)
        result = self.decode_name(reader)
        reader.seek(current_pos)
        return result

    def run(self):
        """
        This function contain the main logic of the receiver
        """
        self.create_and_send_query()

        self.response_received_event.wait(self.timeout + 1)
        self._is_active = False  # close the sub-thread

        self.client_socket.close()
        logging.info("Socket closed.")
        self.listen_thread.join()


if __name__ == "__main__":
    # logging is useful for the log part: https://docs.python.org/3/library/logging.html
    logging.basicConfig(
        # filename="client_log.txt",
        stream=sys.stderr,
        level=logging.DEBUG,
        format="%(asctime)s.%(msecs)03d [%(threadName)s] %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if len(sys.argv) != 5:
        print(
            "\n===== Error usage, python3 client.py server_port qname qtype timeout ======\n"
        )
        exit(0)

    client = Client(int(sys.argv[1]), sys.argv[2], sys.argv[3], int(sys.argv[4]))
    try:
        client.run()
    except KeyboardInterrupt:
        print("\nExiting...")
