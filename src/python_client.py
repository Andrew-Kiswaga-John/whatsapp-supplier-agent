import os
import sys
import subprocess
import time

def automate_mcp_client():
    # Change directory to the MCP project path
    mcp_path = r"C:\Users\Asus\Documents\LN\MCP\postgres-mcp"
    os.chdir(mcp_path)

    try:
        # Start the MCP client process
        process = subprocess.Popen(
            'cargo run --example mcp_client',
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True
        )

        # Function to send command and get response
        def send_command(command):
            process.stdin.write(f"{command}\n")
            process.stdin.flush()
            time.sleep(1)  # Wait for response
            
        # Execute commands in sequence
        send_command('1')  # Select option 1
        send_command('postgresql://postgres:admin123@localhost:5432/whatsapp-supplier-agent')  # Connection string
        
        send_command('5')  # Select option 5
        # send_command('conn_0')  # Connection ID
        send_command('public')  # Schema name
        
        send_command('12')  # Select option 12
        # send_command('conn_0')  # Connection ID
        
        send_command('13')  # Exit
        
        # Get output
        output, error = process.communicate()
        
        if error:
            print(f"Error output: {error}")
        if output:
            print(f"Process output: {output}")

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        if 'process' in locals():
            process.kill()
        sys.exit(1)

if __name__ == "__main__":
    automate_mcp_client()