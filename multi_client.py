#! /usr/bin/env python3

import subprocess
import threading
import time

def run_client_test(port, domain, record_type, timeout):
    try:
        result = subprocess.run(
            ["python3", "client.py", str(port), domain, record_type, str(timeout)],
            capture_output=True,
            text=True,
            timeout=timeout  # Extra time to capture the output
        )
        print(f"Test: {domain} {record_type} (timeout: {timeout})\nOutput:\n{result.stdout}")
    except subprocess.TimeoutExpired:
        print(f"Test: {domain} {record_type} (timeout: {timeout})\nOutput:\nTimed out\n")
    except Exception as e:
        print(f"Test: {domain} {record_type} (timeout: {timeout})\nError:\n{e}\n")

def main():
    port = 49155
    # # Start the server
    # server_process = subprocess.Popen(["python3", server_script, str(port)])
    # time.sleep(2)  # Give the server a moment to start

    # Test cases
    test_cases = [
        ("example.com.", "A", 10),
        ("example.com.", "A", 1),
        ("bar.example.com.", "CNAME", 10),
        (".", "NS", 10),
        ("bar.example.com.", "A", 10),
        ("foo.example.com.", "A", 10),
        ("example.org.", "A", 10),
        ("example.org.", "CNAME", 10),
        ("example.org.", "NS", 10),
        ("www.metalhead.com.", "A", 10),
        ("foo.example.com.", "A", 10),  # Additional test case
    ]

    threads = []
    for domain, record_type, timeout in test_cases:
        t = threading.Thread(target=run_client_test, args=(port, domain, record_type, timeout))
        t.start()
        threads.append(t)
        time.sleep(1)  # Slight delay to avoid overwhelming the server

    for t in threads:
        t.join()

    # # Stop the server
    # server_process.terminate()
    # server_process.wait()

if __name__ == "__main__":
    main()
