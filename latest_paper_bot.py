#%%
import feedparser
import time
import requests
from datetime import datetime, timedelta
from typing import Optional
import pytz
import hmac
import hashlib
import base64
import json
import click
import logging
import logging.handlers
import os
import sys


# Set up logging
def setup_logging(debug: bool = False):
    """Set up logging configuration"""
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    # Configure file handler
    log_file = os.path.join(log_dir, "paper_bot.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    
    # Configure console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


class FeishuRobotSender:
    def __init__(self, webhook_url: str, secret: Optional[str] = None):
        self.webhook_url = webhook_url
        self.secret = secret
        self.logger = logging.getLogger(__name__)

    def _generate_sign(self) -> dict:
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

    def send_text_message(self, text: str) -> dict:
        payload = {
            "msg_type": "text",
            "content": {
                "text": text
            }
        }
        return self._send_message(payload)

    def send_card_message(self, card: dict) -> dict:
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

    def _send_message(self, payload: dict) -> dict:
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
            self.logger.error(f"Failed to send message: {str(e)}")
            return {"error": str(e), "payload": payload}


def get_new_notifications(rss_url: str, last_checked: datetime, sent_entries: set, debug: bool = False):
    """
    Fetch new notifications from the RSS feed.
    Args:
        rss_url: RSS feed URL
        last_checked: Last check timestamp (should be in UTC)
        sent_entries: Set of already sent entry IDs
        debug: Debug mode flag
    """
    logger = logging.getLogger(__name__)
    feed = feedparser.parse(rss_url)
    new_notifications = []

    # 确保 last_checked 是 UTC 时间
    if last_checked.tzinfo is None:
        last_checked = last_checked.replace(tzinfo=pytz.UTC)

    if debug:
        logger.debug("=== Time Debug Info ===")
        logger.debug(f"Current Beijing time: {datetime.now(pytz.timezone('Asia/Shanghai'))}")
        logger.debug(f"Current UTC time: {datetime.now(pytz.UTC)}")
        logger.debug(f"Last checked (UTC): {last_checked}")

    for entry in feed.entries:
        entry_id = entry.get('id', entry.link)
        
        if entry_id in sent_entries:
            continue
            
        # Parse published time as UTC
        published_time = datetime(*entry.published_parsed[:6], tzinfo=pytz.UTC)
        
        if debug:
            logger.debug("=== Entry Debug Info ===")
            logger.debug(f"Entry title: {entry.title}")
            logger.debug(f"Published time (UTC): {published_time}")
            logger.debug(f"Published time (Beijing): {published_time.astimezone(pytz.timezone('Asia/Shanghai'))}")
            logger.debug(f"Is new? {published_time > last_checked}")
        
        if published_time > last_checked:
            new_notifications.append({
                "title": entry.title,
                "content": entry.summary,
                "published": published_time,
                "id": entry_id
            })
    
    return new_notifications


@click.command()
@click.option('--webhook-url', default='https://open.feishu.cn/open-apis/bot/v2/hook/4ff10d4b-50d3-4f3e-99b5-cac11cacbd2d',
              help='Feishu webhook URL')
@click.option('--rss-url', default='https://notifier.in/rss/mx853qfq9ale56gsx0vm48d0w8w1e0tb.xml',
              help='RSS feed URL')
@click.option('--debug/--no-debug', default=False, help='Enable debug mode')
@click.option('--reference-time', default='2024-12-22 19:19:22',
              help='Reference time in format YYYY-MM-DD HH:MM:SS')
def main(webhook_url: str, rss_url: str, debug: bool, reference_time: str):
    """Monitor RSS feed and send notifications via Feishu."""
    # Set up logging
    logger = setup_logging(debug)
    logger.info("Starting paper notification bot...")
    
    # Initialize Feishu robot sender
    robot = FeishuRobotSender(webhook_url)

    # 开发模式设置
    CHECK_INTERVAL = 60 if debug else 3600  # 测试时1分钟检查一次，正式环境1小时检查
    logger.info(f"Check interval set to {CHECK_INTERVAL} seconds")

    # 使用用户提供的参考时间
    reference_dt = datetime.strptime(reference_time, "%Y-%m-%d %H:%M:%S")
    reference_dt = pytz.timezone('Asia/Shanghai').localize(reference_dt)
    last_checked = reference_dt.astimezone(pytz.UTC)  # 转换为UTC时间
    logger.info(f"Reference time set to {reference_time} (Beijing time)")
    sent_entries = set()

    while True:
        try:
            logger.debug("Checking for new notifications...")
            new_notifications = get_new_notifications(rss_url, last_checked, sent_entries, debug)
            
            if new_notifications:
                logger.info(f"Found {len(new_notifications)} new notifications")
                
                for notification in new_notifications:
                    title = notification["title"]
                    content = notification["content"]
                    beijing_time = notification["published"].astimezone(
                        pytz.timezone('Asia/Shanghai')
                    ).strftime("%Y-%m-%d %H:%M:%S %Z")
                    
                    logger.debug(f"Processing notification: {title}")
                    
                    # Create card message
                    card = {
                        "header": {
                            "title": {
                                "content": "New Paper Notification",
                                "tag": "plain_text"
                            },
                            "template": "blue"
                        },
                        "elements": [
                            {
                                "tag": "div",
                                "text": {
                                    "content": f"**Title**\n{title}",
                                    "tag": "lark_md"
                                }
                            },
                            {
                                "tag": "div",
                                "text": {
                                    "content": f"**Content**\n{content}",
                                    "tag": "lark_md"
                                }
                            },
                            {
                                "tag": "div",
                                "text": {
                                    "content": f"**Published Time**\n{beijing_time}",
                                    "tag": "lark_md"
                                }
                            }
                        ]
                    }
                    
                    response = robot.send_card_message(card)
                    logger.info(f"Sent notification: {title}")
                    logger.debug(f"Feishu Response: {response}")

                    sent_entries.add(notification["id"])

            else:
                logger.debug(f"No new notifications at {datetime.now()}")

        except Exception as e:
            logger.error(f"Error occurred: {str(e)}", exc_info=True)

        # Update the last checked time (in UTC)
        last_checked = datetime.now(pytz.UTC)
        logger.debug(f"Updated last_checked to {last_checked}")
        
        # Sleep for the specified interval
        logger.debug(f"Sleeping for {CHECK_INTERVAL} seconds")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
