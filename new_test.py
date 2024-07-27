import subprocess
import time
import re
from tqdm import tqdm  # Use tqdm for a progress bar
from threading import Thread

# Constants
SERVER_CMD = ['python3', 'server.py', '54321']
CLIENT_CMD = 'python3 client.py 54321 {} {} {}'
MASTER_FILE = 'new_master.txt'
TIMEOUT = 5

# DNS Records for new_master.txt
dns_records = """\
example.net.         A      192.168.1.1
example.org.         NS     ns1.example.org.
example.org.         NS     ns2.example.org.
ns1.example.org.     A      192.168.2.1
ns2.example.org.     A      192.168.2.2
alias.example.com.   CNAME  real.example.com.
real.example.com.    A      192.168.3.1
test.example.com.    A      192.168.4.1
test.example.com.    A      192.168.4.2
example.edu.         NS     ns1.example.edu.
example.edu.         NS     ns2.example.edu.
ns1.example.edu.     A      192.168.5.1
ns2.example.edu.     A      192.168.5.2
www.example.com.     CNAME  example.com.
example.com.         A      192.168.6.1
"""

# Expected outputs for each test based on assignment specifications
expected_outputs = {
    "example.net. A": "example.net. A 192.168.1.1",
    "alias.example.com. CNAME": "alias.example.com. CNAME real.example.com.",
    "example.org. NS": "example.org. NS ns1.example.org. example.org. NS ns2.example.org.",
    "test.example.com. A": "test.example.com. A 192.168.4.1 test.example.com. A 192.168.4.2",
    "example.edu. NS": "example.edu. NS ns1.example.edu. example.edu. NS ns2.example.edu.",
    "www.example.com. A": "www.example.com. CNAME example.com. example.com. A 192.168.6.1",
    "timeout": "Request timed out"
}

# Write DNS records to new_master.txt
with open(MASTER_FILE, 'w') as f:
    f.write(dns_records)

# Function to parse the actual output, excluding the question section
def parse_output(output):
    answer_section = re.search(r"ANSWER SECTION:\n(.+?)(?=\n[A-Z ]+ SECTION:|\Z)", output, re.DOTALL)
    authority_section = re.search(r"AUTHORITY SECTION:\n(.+?)(?=\n[A-Z ]+ SECTION:|\Z)", output, re.DOTALL)
    additional_section = re.search(r"ADDITIONAL SECTION:\n(.+?)(?=\n[A-Z ]+ SECTION:|\Z)", output, re.DOTALL)
    
    sections = []
    if answer_section:
        sections.append(answer_section.group(1).strip())
    if authority_section:
        sections.append(authority_section.group(1).strip())
    if additional_section:
        sections.append(additional_section.group(1).strip())
    
    return '\n'.join(sections)

# Normalize output for comparison (ignore spacing and section headers)
def normalize_output(output):
    output = re.sub(r'\s+', ' ', output).strip()
    output = re.sub(r' (AUTHORITY|ADDITIONAL) SECTION:', '', output)
    return output

# Function to run a single client test
def run_client_test(qname, qtype, timeout, expected_output_key):
    client_cmd = CLIENT_CMD.format(qname, qtype, timeout)
    result = subprocess.run(client_cmd.split(), capture_output=True, text=True, timeout=timeout + 2)
    
    if timeout == 1:
        expected_output = expected_outputs["timeout"]
        actual_output = result.stderr.strip() or result.stdout.strip()
    else:
        expected_output = expected_outputs[expected_output_key]
        actual_output = parse_output(result.stdout)
    
    expected_output_normalized = normalize_output(expected_output)
    actual_output_normalized = normalize_output(actual_output)
    
    print(f"Running test: {qname} {qtype} {timeout}")
    print(f"Expected Output:\n{expected_output_normalized}")
    print(f"Actual Output:\n{actual_output_normalized}")
    
    if expected_output_normalized in actual_output_normalized:
        print("Test Passed!")
        return True
    else:
        print("Test Failed!")
        return False

# Start the DNS server
server_proc = subprocess.Popen(SERVER_CMD)
time.sleep(2)  # Wait for server to initialize

# Define multithreaded test cases
multithread_test_cases = [
    ("example.net.", "A", TIMEOUT, "example.net. A"),
    ("alias.example.com.", "CNAME", TIMEOUT, "alias.example.com. CNAME"),
    ("example.org.", "NS", TIMEOUT, "example.org. NS"),
    ("test.example.com.", "A", TIMEOUT, "test.example.com. A"),
    ("example.edu.", "NS", TIMEOUT, "example.edu. NS"),
    ("www.example.com.", "A", TIMEOUT, "www.example.com. A"),
]

# Tally for passed and failed tests
passed_tests = 0
failed_tests = 0

# Run multithreaded test cases with progress bar
threads = []
for qname, qtype, timeout, expected_output_key in tqdm(multithread_test_cases, desc="Running Multithreaded Tests"):
    thread = Thread(target=lambda: run_client_test(qname, qtype, timeout, expected_output_key))
    thread.start()
    threads.append(thread)

# Wait for all threads to complete
for thread in threads:
    thread.join()

# Check results
for qname, qtype, timeout, expected_output_key in multithread_test_cases:
    if run_client_test(qname, qtype, timeout, expected_output_key):
        passed_tests += 1
    else:
        failed_tests += 1

# Terminate the server
server_proc.terminate()

# Summary of test results
print(f"All Tests Completed. Passed: {passed_tests}, Failed: {failed_tests}")
