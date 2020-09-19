import os

import twilio
from twilio.rest import Client
from utils.logger import log


class sendSMS:

    def validCredentials():
        # unclear how to return the test value directly as a boolean
        if ((os.environ.get('TWILIO_ACCOUNT') != "") & (os.environ.get('TWILIO_TOKEN') != "")):
            sendSMS.send("Starting Bot")
            return True    
        else:
            log.warn("You need to set your TWILIO credentials as environment variables")
            return False

    def send(messageBody):
        log.info(f"sendSMS being called")
        
        # use environment variables to store your Twilio Account and Twilio Token, so they cannot
        # end up in a source control system like GitHub where everyone can take them and use them
        # on Widows "set TWILIO_ACCOUNT=AC123412341234" and "set TWILIO_TOKEN=214351234"
        # before launching app.py
        account = os.environ.get('TWILIO_ACCOUNT')
        token = os.environ.get('TWILIO_TOKEN')
        client = Client(account, token)

        # When using Twilio test credentials, use 
        # from_="+15005550006",
        # to send a successful but fake SMS
        message = client.messages.create(
                                    from_ = '+12184223560',
                                    body = messageBody,
                                    to = '+14252836409' 
                                    )
        log.info("SMS Sent: " + message.sid)
        # no error handling here
