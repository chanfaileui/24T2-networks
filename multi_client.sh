#!/bin/bash

# # Start the server in the background
# python3 server.py 49155 &
# SERVER_PID=$!

# # Give the server some time to start
# sleep 2

# Function to run a client test
run_client_test() {
    local domain=$1
    local type=$2
    local timeout=$3

    echo "Running test: $domain $type with timeout $timeout"
    python3 client.py 49155 $domain $type $timeout
    echo "Test complete: $domain $type"
    echo
}

# Run all the specified client tests
run_client_test "example.com." "A" 10
run_client_test "example.com." "A" 1
run_client_test "bar.example.com." "CNAME" 10
run_client_test "." "NS" 10
run_client_test "bar.example.com." "A" 10
run_client_test "foo.example.com." "A" 10
run_client_test "example.org." "A" 10
run_client_test "example.org." "CNAME" 10
run_client_test "example.org." "NS" 10
run_client_test "www.metalhead.com." "A" 10

# Additional test
run_client_test "foo.example.com." "A" 5

# # Stop the server
# kill $SERVER_PID

# echo "All tests completed."
