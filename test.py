import subprocess
import time
import random
import re

# Constants
SERVER_CMD = ['python3', 'server.py', '54321']
CLIENT_CMD = 'python3 client.py 54321 {} {} {}'
MASTER_FILE = 'master.txt'
TIMEOUT = 5

# DNS Records for master.txt
dns_records = """\
mydomain.com. A 172.16.254.1
mydomain.com. NS ns1.mydomain.com.
ns1.mydomain.com. A 172.16.254.2
alias.mydomain.com. CNAME realdomain.mydomain.com.
realdomain.mydomain.com. A 172.16.254.3
test.mydomain.com. A 192.168.1.1
network.local. A 10.0.0.1
network.local. NS ns.network.local.
ns.network.local. A 10.0.0.2
mail.mydomain.com. CNAME mailserver.mydomain.com.
mailserver.mydomain.com. A 172.16.254.4
localdomain.local. NS ns1.localdomain.local.
ns1.localdomain.local. A 10.1.1.1
"""

# Expected outputs for each test
expected_outputs = {
    "mydomain.com. A": "mydomain.com. A 172.16.254.1",
    "alias.mydomain.com. CNAME": "alias.mydomain.com. CNAME realdomain.mydomain.com.",
    "localdomain.local. NS": "localdomain.local. NS ns1.localdomain.local.",
    "realdomain.mydomain.com. A": "realdomain.mydomain.com. A 172.16.254.3",
    "mydomain.com. NS": "mydomain.com. NS ns1.mydomain.com.",
    "network.local. A": "network.local. NS ns.network.local.\nns.network.local. A 10.0.0.2",
    "mail.mydomain.com. A": "mail.mydomain.com. CNAME mailserver.mydomain.com.\nmailserver.mydomain.com. A 172.16.254.4",
    "alias.mydomain.com. A": "alias.mydomain.com. CNAME realdomain.mydomain.com.\nrealdomain.mydomain.com. A 172.16.254.3",
    "mail.mydomain.com. A (restart)": "mail.mydomain.com. CNAME mailserver.mydomain.com.\nmailserver.mydomain.com. A 172.16.254.4",
    "timeout": "Request timed out"
}

# Write DNS records to master.txt
with open(MASTER_FILE, 'w') as f:
    f.write(dns_records)

# Function to parse the actual output
def parse_output(output):
    question_section = re.search(r"QUESTION SECTION:\n(.+)", output).group(1).strip()
    answer_section = re.search(r"ANSWER SECTION:\n(.+)", output, re.DOTALL)
    authority_section = re.search(r"AUTHORITY SECTION:\n(.+)", output, re.DOTALL)
    additional_section = re.search(r"ADDITIONAL SECTION:\n(.+)", output, re.DOTALL)
    
    sections = [question_section]
    if answer_section:
        sections.append(answer_section.group(1).strip())
    if authority_section:
        sections.append(authority_section.group(1).strip())
    if additional_section:
        sections.append(additional_section.group(1).strip())
    
    return '\n'.join(sections)

# Start the DNS server
server_proc = subprocess.Popen(SERVER_CMD)
time.sleep(2)  # Wait for server to initialize

# Test cases
test_cases = [
    ("mydomain.com.", "A", TIMEOUT),
    ("alias.mydomain.com.", "CNAME", TIMEOUT),
    ("localdomain.local.", "NS", TIMEOUT),
    ("realdomain.mydomain.com.", "A", TIMEOUT),
    ("mydomain.com.", "NS", TIMEOUT),
    ("network.local.", "A", TIMEOUT),
    ("mail.mydomain.com.", "A", TIMEOUT),
    ("alias.mydomain.com.", "A", TIMEOUT),
    ("mail.mydomain.com.", "A", TIMEOUT),  # Query Restarts and Referrals
    ("network.local.", "A", 1)  # Timeout test
]

# Run test cases
for qname, qtype, timeout in test_cases:
    print(f"Running test: {qname} {qtype} {timeout}")
    client_cmd = CLIENT_CMD.format(qname, qtype, timeout)
    result = subprocess.run(client_cmd.split(), capture_output=True, text=True, timeout=timeout + 2)
    
    if timeout == 1:
        expected_output = expected_outputs["timeout"]
        actual_output = result.stderr.strip() or result.stdout.strip()
    else:
        expected_output = expected_outputs[f"{qname} {qtype}"]
        actual_output = parse_output(result.stdout)
    
    print(f"Expected Output:\n{expected_output}")
    print(f"Actual Output:\n{actual_output}")
    print("Test Passed!" if expected_output in actual_output else "Test Failed!")
    print("-" * 40)

# Terminate the server
server_proc.terminate()
