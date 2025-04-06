# whatsapp_tool.py

import requests

class WhatsAppTool:
    def __init__(self, mcp_server_url: str):
        """
        Initialize the WhatsAppTool with the MCP server URL.

        :param mcp_server_url: URL of the WhatsApp MCP server.
        """
        self.mcp_server_url = mcp_server_url

    def send_message(self, recipient: str, message: str) -> bool:
        """
        Send a message to a WhatsApp recipient.

        :param recipient: The recipient's phone number in international format.
        :param message: The message to send.
        :return: True if the message was sent successfully, False otherwise.
        """
        payload = {
            "recipient": recipient,
            "message": message
        }
        try:
            response = requests.post(f"{self.mcp_server_url}/send_message", json=payload)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"Failed to send message: {e}")
            return False

    def send_file(self, recipient: str, file_path: str) -> bool:
        """
        Send a file to a WhatsApp recipient.

        :param recipient: The recipient's phone number in international format.
        :param file_path: The path to the file to send.
        :return: True if the file was sent successfully, False otherwise.
        """
        try:
            with open(file_path, 'rb') as file:
                files = {'file': file}
                data = {'recipient': recipient}
                response = requests.post(f"{self.mcp_server_url}/send_file", files=files, data=data)
                response.raise_for_status()
            return True
        except (requests.RequestException, IOError) as e:
            print(f"Failed to send file: {e}")
            return False
