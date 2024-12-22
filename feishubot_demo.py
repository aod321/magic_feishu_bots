# %%
import requests
import hmac
import hashlib
import base64
import time
import json
from typing import Union, List, Dict, Optional

class FeishuRobotSender:
    def __init__(self, webhook_url: str, secret: Optional[str] = None):
        """
        Initialize the Feishu Robot Sender.
        
        :param webhook_url: The webhook URL of the Feishu custom robot
        :param secret: Optional secret for signature verification
        """
        self.webhook_url = webhook_url
        self.secret = secret

    def _generate_sign(self) -> Dict[str, str]:
        """
        Generate signature for webhook request if secret is provided.
        
        :return: Dictionary with timestamp and sign
        """
        if not self.secret:
            return {}
        
        timestamp = int(time.time())
        string_to_sign = f"{timestamp}\n{self.secret}"
        
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"), 
            digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode('utf-8')
        
        return {
            "timestamp": str(timestamp),
            "sign": sign
        }

    def send_text_message(
        self, 
        text: str, 
        at_users: Optional[List[str]] = None, 
        at_all: bool = False
    ) -> Dict:
        """
        Send a text message to the Feishu robot.
        
        :param text: Message text
        :param at_users: List of user Open IDs to mention
        :param at_all: Whether to mention all members
        :return: Response from the webhook
        """
        # Construct @ mentions
        if at_users:
            at_text = ' '.join([f'<at user_id="{user_id}"></at>' for user_id in at_users])
            text = f"{at_text} {text}"
        
        if at_all:
            text = '<at user_id="all"></at> ' + text

        payload = {
            "msg_type": "text",
            "content": {
                "text": text
            }
        }
        
        return self._send_message(payload)

    def send_post_message(
        self, 
        title: str, 
        content: List[List[Dict]], 
        language: str = 'zh_cn'
    ) -> Dict:
        """
        Send a rich text (post) message.
        
        :param title: Message title
        :param content: Rich text content structure
        :param language: Language of the message (zh_cn or en_us)
        :return: Response from the webhook
        """
        payload = {
            "msg_type": "post",
            "content": {
                "post": {
                    language: {
                        "title": title,
                        "content": content
                    }
                }
            }
        }
        
        return self._send_message(payload)

    def send_card_message(self, card: Dict) -> Dict:
        """
        Send an interactive card message.
        
        :param card: Card message structure
        :return: Response from the webhook
        """
        payload = {
            "msg_type": "interactive",
            "card": card
        }
        
        return self._send_message(payload)

    def _send_message(self, payload: Dict) -> Dict:
        """
        Send message to Feishu webhook with optional signature.
        
        :param payload: Message payload
        :return: Response from the webhook
        """
        # Add signature if secret is provided
        sign_params = self._generate_sign()
        payload.update(sign_params)
        
        try:
            response = requests.post(
                self.webhook_url, 
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {
                "error": str(e),
                "payload": payload
            }

# Example usage
def main():
    # Replace with your actual webhook URL and optional secret
    WEBHOOK_URL = 'https://open.feishu.cn/open-apis/bot/v2/hook/4ff10d4b-50d3-4f3e-99b5-cac11cacbd2d'
    SECRET = None  # Optional: set to your webhook secret if using signature verification

    # Initialize the sender
    robot = FeishuRobotSender(WEBHOOK_URL, SECRET)

    # Send a simple text message
    text_response = robot.send_text_message(
        "Hello, this is a test message!", 
        at_users=["user_open_id_1", "user_open_id_2"],
        at_all=False
    )
    print("Text Message Response:", text_response)

    # Send a rich text message
    post_response = robot.send_post_message(
        "Project Update", 
        [
            [
                {"tag": "text", "text": "Project status: "},
                {"tag": "a", "text": "View Details", "href": "http://example.com"}
            ]
        ]
    )
    print("Post Message Response:", post_response)

    # Send an interactive card message
    card_message = {
        "header": {
            "title": {
                "content": "Notification",
                "tag": "plain_text"
            }
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "content": "**Important Update**\nSomething requires your attention.",
                    "tag": "lark_md"
                }
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "content": "View Details",
                            "tag": "lark_md"
                        },
                        "url": "http://example.com",
                        "type": "default"
                    }
                ]
            }
        ]
    }
    card_response = robot.send_card_message(card_message)
    print("Card Message Response:", card_response)

if __name__ == "__main__":
    main()

# %%
