import subprocess
import threading
import sys
import time
import argparse
def pipe_stream(source, dest, name, output):
    """Reads from source, writes to dest, logs to stderr.
    
    Args:
        source: Input stream to read from
        dest: Output stream to write to  
        name: Name for logging purposes
        output: True if dest expects text, False if dest expects bytes
    """
    try:
        for line in iter(source.readline, b''):
            if not line:  # EOF
                break
                
            # Decode for logging if it's bytes
            if isinstance(line, bytes):
                try:
                    line_str = line.decode('utf-8', errors='replace').rstrip('\n\r')
                    print(f"INTERCEPT {name}: {line_str}", file=sys.stderr)
                except UnicodeDecodeError:
                    print(f"INTERCEPT {name}: <binary data {len(line)} bytes>", file=sys.stderr)
            else:
                line_str = line.rstrip('\n\r')
                print(f"INTERCEPT {name}: {line_str}", file=sys.stderr)
            
            # Handle encoding/decoding for the destination
            if output and isinstance(line, bytes):
                # Destination expects text, source is bytes
                line = line.decode('utf-8', errors='replace')
            elif not output and isinstance(line, str):
                # Destination expects bytes, source is text
                line = line.encode('utf-8')
            
            dest.write(line)
            dest.flush()
            
    except (BrokenPipeError, OSError) as e:
        print(f"INTERCEPT {name}: Pipe broken - {e}", file=sys.stderr)
    except Exception as e:
        print(f"INTERCEPT {name}: Error - {e}", file=sys.stderr)
if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Intercept and log MCP server communication')
    parser.add_argument('server_command', nargs='+', 
                       help='Command to run the MCP server (e.g., python3 ./src/mcp_server_time/__main__.py)')
    args = parser.parse_args()
    
    # Use the provided server command
    server_cmd = args.server_command
    
    print("Starting interceptor...", file=sys.stderr)
    # Start the server subprocess
    server_proc = subprocess.Popen(
        server_cmd,
        stdin=subprocess.PIPE,  # Server's stdin will be our pipe
        stdout=subprocess.PIPE, # Server's stdout will be our pipe
        stderr=sys.stderr,      # Server's stderr goes directly to our stderr
        # bufsize=1,              # Line buffered
        universal_newlines=False # Work with bytes
    )
    # Create threads to pipe and log
    server_to_client_thread = threading.Thread(
        target=pipe_stream,
        args=(sys.stdin, server_proc.stdin, "CLIENT_TO_SERVER", False)
    )
    client_to_server_thread = threading.Thread(
        target=pipe_stream,
        args=(server_proc.stdout, sys.stdout, "SERVER_TO_CLIENT", True)
    )
    server_to_client_thread.daemon = True
    client_to_server_thread.daemon = True
    server_to_client_thread.start()
    client_to_server_thread.start()
    # Keep the main thread alive as long as subprocesses are running
    try:
        while server_proc.poll() is None:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Interceptor shutting down...", file=sys.stderr)
    finally:
        server_proc.terminate()
        server_proc.wait()
        print("Interceptor finished.", file=sys.stderr)

