# -*- coding: utf-8 -*-
"""
Sample code for using webexteamsbot
"""
import datetime
import os
import time
import urllib
from datetime import timedelta

import requests
import schedule

from webexteamsbot import TeamsBot
from webexteamsbot.models import Response
import sys
import json

# Retrieve required details from environment variables
bot_email = os.getenv("TEAMS_BOT_EMAIL")
teams_token = os.getenv("TEAMS_BOT_TOKEN")
bot_url = os.getenv("TEAMS_BOT_URL")
bot_app_name = os.getenv("TEAMS_BOT_APP_NAME")
message_url = "https://webexapis.com/v1/messages"

global PARTICIPANTS_AVAILABLE
PARTICIPANTS_AVAILABLE = False

global REMINDER_COUNT
REMINDER_COUNT = 0

global MESSAGE_ID_FOR_FORM
MESSAGE_ID_FOR_FORM = ""

global LAST_STATUS_CHECK
LAST_STATUS_CHECK = datetime.datetime.now()
message_url = "https://webexapis.com/v1/messages"

# Example: How to limit the approved Webex Teams accounts for interaction
#          Also uncomment the parameter in the instantiation of the new bot
# List of email accounts of approved users to talk with the bot
# approved_users = [
#     "josmith@demo.local",
# ]

# If any of the bot environment variables are missing, terminate the app
if not bot_email or not teams_token or not bot_url or not bot_app_name:
    print(
        "sample.py - Missing Environment Variable. Please see the 'Usage'"
        " section in the README."
    )
    if not bot_email:
        print("TEAMS_BOT_EMAIL")
    if not teams_token:
        print("TEAMS_BOT_TOKEN")
    if not bot_url:
        print("TEAMS_BOT_URL")
    if not bot_app_name:
        print("TEAMS_BOT_APP_NAME")
    sys.exit()

# Create a Bot Object
#   Note: debug mode prints out more details about processing to terminal
#   Note: the `approved_users=approved_users` line commented out and shown as reference
bot = TeamsBot(
    bot_app_name,
    teams_bot_token=teams_token,
    teams_bot_url=bot_url,
    teams_bot_email=bot_email,
    debug=True,
    # approved_users=approved_users,
    webhook_resource_event=[
        {"resource": "messages", "event": "created"},
        {"resource": "attachmentActions", "event": "created"},
    ],
)

with open("./webexteamsbot/StatusInputCard.json", "r") as card:
    INPUT_CARD = json.load(card)

with open("./webexteamsbot/ReminderInputCard.json", "r") as reminder_card:
    REMINDER_INPUT_CARD = json.load(reminder_card)

with open("./webexteamsbot/MessageBox.json", "r") as message:
    MESSAGE_CARD = json.load(message)

MESSAGE_ID_FOR_FORM = ""
MESSAGE_TEXT_FOR_FORM = ""


# Create a custom bot greeting function returned when no command is given.
# The default behavior of the bot is to return the '/help' command response
def greeting(incoming_msg):
    # Loopkup details about sender
    sender = bot.teams.people.get(incoming_msg.personId)

    # Create a Response object and craft a reply in Markdown.
    response = Response()
    response.markdown = "Hello {}, I'm a chat bot. ".format(sender.firstName)
    response.markdown += "See what I can do by asking for **/help**."
    return response


# Create functions that will be linked to bot commands to add capabilities
# ------------------------------------------------------------------------

# A simple command that returns a basic string that will be sent as a reply
def do_something(incoming_msg):
    """
    Sample function to do some action.
    :param incoming_msg: The incoming message object from Teams
    :return: A text or markdown based reply
    """
    return "i did what you said - {}".format(incoming_msg.text)


# This function generates a basic adaptive card and sends it to the user
# You can use Microsofts Adaptive Card designer here:
# https://adaptivecards.io/designer/. The formatting that Webex Teams
# uses isn't the same, but this still helps with the overall layout
# make sure to take the data that comes out of the MS card designer and
# put it inside of the "content" below, otherwise Webex won't understand
# what you send it.
def show_status_card(incoming_msg):
    global MESSAGE_ID_FOR_FORM
    global MESSAGE_TEXT_FOR_FORM
    global SENDER_EMAIL
    response_message = "status"
    SENDER_EMAIL = incoming_msg.personEmail

    c = create_message_with_attachment(
        incoming_msg.roomId, msgtxt=response_message, attachment=INPUT_CARD
    )
    MESSAGE_ID_FOR_FORM = c["id"]
    MESSAGE_TEXT_FOR_FORM = c["text"]
    return ""


def show_reminder_card(incoming_msg):
    global MESSAGE_ID_FOR_FORM
    global MESSAGE_TEXT_FOR_FORM
    global SENDER_EMAIL
    response_message = "notify"
    SENDER_EMAIL = incoming_msg.personEmail

    c = create_message_with_attachment(
        incoming_msg.roomId, msgtxt=response_message, attachment=REMINDER_INPUT_CARD
    )
    MESSAGE_ID_FOR_FORM = c["id"]
    MESSAGE_TEXT_FOR_FORM = c["text"]
    return ""


# An example of how to process card actions
def handle_cards(api, incoming_msg):
    global REMINDER_COUNT
    """
    Sample function to handle card actions.
    :param api: webexteamssdk object
    :param incoming_msg: The incoming message object from Teams
    :return: A text or markdown based reply
    """

    m = get_attachment_actions(incoming_msg["data"]["id"])
    if MESSAGE_TEXT_FOR_FORM == "notify":
        recipient_email = m["inputs"]["notifyEmail"]
        reminders = m["inputs"]["reminder"]
        message = m["inputs"]["messageContext"]
        processNotify(recipient_email, reminders, message)
        return "{} was successfully notified".format(recipient_email)

    elif MESSAGE_TEXT_FOR_FORM == "status":
        recipient_email = m["inputs"]["trackEmail"]
        default_message = "The status of {} will be notified.".format(recipient_email)
        send_default_message(default_message)
        text_success_format = "{} is active now".format(recipient_email)
        text_failure_format = "{} is unavailable for the past 30 min. Please try again later.".format(recipient_email)
        flag = processStatus(recipient_email)

        if flag is True:
            return text_failure_format
        else:
            return text_success_format

    elif MESSAGE_TEXT_FOR_FORM == "message":
        REMINDER_COUNT = 0
        return ""


def are_participants_available(sender_email_id, receiver_email_id):
    if get_user_current_status(receiver_email_id) == 'active' and get_user_current_status(sender_email_id) == 'active':
        return schedule.CancelJob


def get_user_current_status(email_id):
    get_people_api_string = "https://webexapis.com/v1/people?email=" + email_id
    response = requests.get(get_people_api_string, headers={'Authorization': 'Bearer {}'.format(teams_token)})
    response_json = response.json()
    status = response_json['items'][0]['status']
    print("****The current status of " + email_id + "is :" + status)
    return status


def is_user_active(email_id):
    global LAST_STATUS_CHECK
    LAST_STATUS_CHECK = datetime.datetime.now()
    if get_user_current_status(email_id) == 'active':
        return schedule.CancelJob


def processStatus(recipient_email):
    global SENDER_EMAIL
    flag = False

    start_time = datetime.datetime.now()
    print(start_time)

    schedule.every(10).seconds.until(timedelta(hours=1)).do(is_user_active, email_id=recipient_email)
    while True:
        schedule.run_pending()
        if not schedule.jobs:
            break
        if datetime.datetime.now() - start_time > timedelta(minutes=30):
            flag = True
            schedule.clear()
            break
        time.sleep(1)
    # requests.post(message_url, json=post_body, headers=headers)
    return flag


def send_default_message(message):
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": "Bearer " + teams_token,
    }
    post_body = {
        "toPersonEmail": SENDER_EMAIL,
        "text": message
    }
    requests.post(message_url, json=post_body, headers=headers)


def processNotify(recipient_email, reminders, message):
    global REMINDER_COUNT
    """
    Sample function to do some action.
    :param incoming_msg: The incoming message object from Teams
    :return: A text or markdown based reply
    """

    text_format = "{} wants to talk to you \n RE: {}".format(SENDER_EMAIL, message)
    MESSAGE_CARD["content"]["body"][0]["columns"][0]["items"][1]["text"] = text_format

    schedule.every(10).seconds.until(timedelta(hours=1)).do(are_participants_available, sender_email_id=SENDER_EMAIL,
                                                            receiver_email_id=recipient_email)
    while True:
        schedule.run_pending()
        if not schedule.jobs:
            break
        time.sleep(1)
    send_message_card_to_recipient(recipient_email, MESSAGE_CARD)
    reminder_flag = False

    processReminder(recipient_email,reminders,SENDER_EMAIL)

    return "Pinged {} about - {}".format(recipient_email, message)

def processReminder(recipient_email,reminders,sender_email):
    global REMINDER_COUNT

    REMINDER_COUNT = int(reminders)
    schedule.every(10).seconds.until(timedelta(hours=1)).do(send_reminder_message, recipient_email_id=recipient_email, sender_email_id=sender_email)
    while True:
        schedule.run_pending()
        if not schedule.jobs:
            break
        time.sleep(1)
    if(REMINDER_COUNT == 0):
        send_default_message("Reminder to {} Timed out".format(recipient_email))


def send_reminder_message(recipient_email_id, sender_email_id):
    global REMINDER_COUNT

    if(REMINDER_COUNT == 0):
        return schedule.CancelJob
    headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": "Bearer " + teams_token,
    }
    post_body = {
        "toPersonEmail": email_id,
        "text": "gentle reminder #"+REMINDER_COUNT+" from "+sender_email_id
    }
    requests.post(message_url, json=post_body, headers=headers)
    REMINDER_COUNT = REMINDER_COUNT - 1

def send_message_card_to_recipient(recipient_email, MESSAGE_CARD):
    global MESSAGE_TEXT_FOR_FORM
    global MESSAGE_ID_FOR_FORM
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": "Bearer " + teams_token,
    }
    url = "https://api.ciscospark.com/v1/messages"
    data = {"toPersonEmail": recipient_email, "attachments": [MESSAGE_CARD], "markdown": "message"}
    response = requests.post(url, json=data, headers=headers)
    c = response.json()
    MESSAGE_ID_FOR_FORM = c["id"]
    MESSAGE_TEXT_FOR_FORM = c["text"]
    return ""


def are_participants_available(sender_email_id, receiver_email_id):
    if get_user_current_status(receiver_email_id) == 'active' and get_user_current_status(sender_email_id) == 'active':
        return schedule.CancelJob


# Temporary function to send a message with a card attachment (not yet
# supported by webexteamssdk, but there are open PRs to add this
# functionality)
def create_message_with_attachment(rid, msgtxt, attachment):
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": "Bearer " + teams_token,
    }

    url = "https://api.ciscospark.com/v1/messages"
    data = {"roomId": rid, "attachments": [attachment], "markdown": msgtxt}
    response = requests.post(url, json=data, headers=headers)
    return response.json()


# Temporary function to get card attachment actions (not yet supported
# by webexteamssdk, but there are open PRs to add this functionality)
def get_attachment_actions(attachmentid):
    global MESSAGE_ID_FOR_FORM
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": "Bearer " + teams_token,
    }

    attachment_url = "https://api.ciscospark.com/v1/attachment/actions/" + attachmentid
    attachement_response = requests.get(attachment_url, headers=headers)

    message_url = "https://api.ciscospark.com/v1/messages/" + MESSAGE_ID_FOR_FORM
    message_response = requests.delete(url=message_url, headers=headers)
    print(message_response)
    MESSAGE_ID_FOR_FORM = ""

    return attachement_response.json()


# An example using a Response object.  Response objects allow more complex
# replies including sending files, html, markdown, or text. Rsponse objects
# can also set a roomId to send response to a different room from where
# incoming message was recieved.
def ret_message(incoming_msg):
    """
    Sample function that uses a Response object for more options.
    :param incoming_msg: The incoming message object from Teams
    :return: A Response object based reply
    """
    # Create a object to create a reply.
    response = Response()

    # Set the text of the reply.
    response.text = "Here's a fun little meme."

    # Craft a URL for a file to attach to message
    u = "https://sayingimages.com/wp-content/uploads/"
    u = u + "aaaaaalll-righty-then-alrighty-meme.jpg"
    response.files = u
    return response


# An example command the illustrates using details from incoming message within
# the command processing.
def current_time(incoming_msg):
    """
    Sample function that returns the current time for a provided timezone
    :param incoming_msg: The incoming message object from Teams
    :return: A Response object based reply
    """
    # Extract the message content, without the command "/time"
    timezone = bot.extract_message("/time", incoming_msg.text).strip()

    # Craft REST API URL to retrieve current time
    #   Using API from http://worldclockapi.com
    u = "http://worldclockapi.com/api/json/{timezone}/now".format(timezone=timezone)
    r = requests.get(u).json()

    # If an invalid timezone is provided, the serviceResponse will include
    # error message
    if r["serviceResponse"]:
        return "Error: " + r["serviceResponse"]

    # Format of returned data is "YYYY-MM-DDTHH:MM<OFFSET>"
    #   Example "2018-11-11T22:09-05:00"
    returned_data = r["currentDateTime"].split("T")
    cur_date = returned_data[0]
    cur_time = returned_data[1][:5]
    timezone_name = r["timeZoneName"]

    # Craft a reply string.
    reply = "In {TZ} it is currently {TIME} on {DATE}.".format(
        TZ=timezone_name, TIME=cur_time, DATE=cur_date
    )
    return reply


# Create help message for current_time command
current_time_help = "Look up the current time for a given timezone. "
current_time_help += "_Example: **/time EST**_"

# Set the bot greeting.
bot.set_greeting(greeting)

# Add new commands to the bot.
bot.add_command("attachmentActions", "*", handle_cards)
bot.add_command("check_status", "show a status card", show_status_card)  # CHECK_STATUS
bot.add_command("notify", "notify person about upcoming conversation", show_reminder_card)  # NOTIFY
bot.add_command(
    "/demo", "Sample that creates a Teams message to be returned.", ret_message
)
bot.add_command("/time", current_time_help, current_time)

# Every bot includes a default "/echo" command.  You can remove it, or any
# other command with the remove_command(command) method.
bot.remove_command("/echo")

if __name__ == "__main__":
    # Run Bot
    bot.run(host="0.0.0.0", port=7070)
