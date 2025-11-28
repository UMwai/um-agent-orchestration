#!/usr/bin/env python3
"""
Debug utility to test PTY functionality with Claude CLI.
"""

import os
import pty
import select
import subprocess
import threading
import time
import signal
import sys


def test_pty_claude():
    """Test PTY interaction with Claude CLI."""
    print("Testing PTY interaction with Claude CLI...")

    try:
        # Create PTY pair
        master, slave = pty.openpty()
        print(f"Created PTY: master={master}, slave={slave}")

        # Start Claude process
        cmd = ["claude", "--dangerously-skip-permissions"]
        print(f"Starting Claude: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=os.environ.copy(),
            preexec_fn=os.setsid,
        )

        # Close slave in parent
        os.close(slave)

        print(f"Claude process started with PID: {process.pid}")

        # Set up signal handler for cleanup
        def signal_handler(signum, frame):
            print("\nTerminating Claude process...")
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                process.kill()
            os.close(master)
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        # Read output in separate thread
        def read_output():
            while True:
                try:
                    ready, _, _ = select.select([master], [], [], 0.1)
                    if ready:
                        data = os.read(master, 1024)
                        if data:
                            output = data.decode("utf-8", errors="replace")
                            print(f"CLAUDE: {repr(output)}", flush=True)
                        else:
                            break
                except (OSError, ValueError):
                    break
                except Exception as e:
                    print(f"Output error: {e}")
                    break

        # Start output thread
        output_thread = threading.Thread(target=read_output, daemon=True)
        output_thread.start()

        # Wait for initialization
        print("Waiting for Claude to initialize...")
        time.sleep(5)

        # Test sending commands
        test_commands = ["Hello Claude! Can you respond?", "What is 2+2?", "exit"]

        for cmd in test_commands:
            print(f"\nSending: {cmd}")
            try:
                os.write(master, f"{cmd}\n".encode("utf-8"))
                time.sleep(3)  # Wait for response
            except Exception as e:
                print(f"Write error: {e}")
                break

        print("\nTest completed. Press Ctrl+C to exit.")

        # Keep running until interrupted
        while process.poll() is None:
            time.sleep(1)

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Cleanup
        try:
            if "process" in locals() and process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        except:
            if "process" in locals():
                process.kill()

        try:
            if "master" in locals():
                os.close(master)
        except:
            pass


if __name__ == "__main__":
    test_pty_claude()
