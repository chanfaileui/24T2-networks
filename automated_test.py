import subprocess
import time
import re
from tqdm import tqdm  # Use tqdm for a progress bar

# Constants
SERVER_CMD = ['python3', 'server.py', '54321']
CLIENT_CMD = 'python3 client.py 54321 {} {} {}'
MASTER_FILE = 'master.txt'
TIMEOUT = 5

# DNS Records for master.txt
dns_records = """\
foo.example.com.     CNAME  bar.example.com.
d.gtld-servers.net.  A      192.31.80.30
foobar.example.com.  A      192.0.2.23
bar.example.com.     CNAME  foobar.example.com.
.                    NS     b.root-servers.net.
a.root-servers.net.  A      198.41.0.4
example.com.         A      93.184.215.14
foobar.example.com.  A      192.0.2.24
com.                 NS     d.gtld-servers.net.
www.metalhead.com.   CNAME  metalhead.com.
.                    NS     a.root-servers.net.
"""

# Expected outputs for each test based on assignment specifications
expected_outputs = {
    "example.com. A": "example.com. A 93.184.215.14",
    "bar.example.com. CNAME": "bar.example.com. CNAME foobar.example.com.",
    ". NS": ". NS b.root-servers.net. . NS a.root-servers.net.",
    "bar.example.com. A": "bar.example.com. CNAME foobar.example.com. foobar.example.com. A 192.0.2.23 foobar.example.com. A 192.0.2.24",
    "foo.example.com. A": "foo.example.com. CNAME bar.example.com. bar.example.com. CNAME foobar.example.com. foobar.example.com. A 192.0.2.23 foobar.example.com. A 192.0.2.24",
    "example.org. A": ". NS b.root-servers.net. . NS a.root-servers.net. a.root-servers.net. A 198.41.0.4",
    "example.org. CNAME": ". NS b.root-servers.net. . NS a.root-servers.net. a.root-servers.net. A 198.41.0.4",
    "example.org. NS": ". NS b.root-servers.net. . NS a.root-servers.net. a.root-servers.net. A 198.41.0.4",
    "www.metalhead.com. A": "www.metalhead.com. CNAME metalhead.com. com. NS d.gtld-servers.net. d.gtld-servers.net. A 192.31.80.30",
    "timeout": "Request timed out"
}

# Write DNS records to master.txt
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

# Start the DNS server
server_proc = subprocess.Popen(SERVER_CMD)
time.sleep(2)  # Wait for server to initialize

# Test cases based on the assignment specifications
test_cases = [
    ("example.com.", "A", TIMEOUT),
    ("bar.example.com.", "CNAME", TIMEOUT),
    (".", "NS", TIMEOUT),
    ("bar.example.com.", "A", TIMEOUT),
    ("foo.example.com.", "A", TIMEOUT),
    ("example.org.", "A", TIMEOUT),
    ("example.org.", "CNAME", TIMEOUT),
    ("example.org.", "NS", TIMEOUT),
    ("www.metalhead.com.", "A", TIMEOUT),  # Query Restarts and Referrals
    ("example.com.", "A", 1)  # Timeout test
]

# Tally for passed and failed tests
passed_tests = 0
failed_tests = 0

# Run test cases with progress bar
for qname, qtype, timeout in tqdm(test_cases, desc="Running Tests"):
    print(f"Running test: {qname} {qtype} {timeout}")
    client_cmd = CLIENT_CMD.format(qname, qtype, timeout)
    result = subprocess.run(client_cmd.split(), capture_output=True, text=True, timeout=timeout + 10)
    
    if timeout == 1:
        expected_output = expected_outputs["timeout"]
        actual_output = result.stderr.strip() or result.stdout.strip()
    else:
        expected_output = expected_outputs[f"{qname} {qtype}"]
        actual_output = parse_output(result.stdout)
    
    expected_output_normalized = normalize_output(expected_output)
    actual_output_normalized = normalize_output(actual_output)
    
    print(f"Expected Output:\n{expected_output_normalized}")
    print(f"Actual Output:\n{actual_output_normalized}")
    
    if expected_output_normalized in actual_output_normalized:
        print("Test Passed!")
        passed_tests += 1
    else:
        print("Test Failed!")
        failed_tests += 1
    print("-" * 40)

# Terminate the server
server_proc.terminate()

# Summary of test results
print(f"All Tests Completed. Passed: {passed_tests}, Failed: {failed_tests}")
