import logging
import os

import twilio
from twilio.rest import Client

log = logging.getLogger(__name__)
formatter = logging.Formatter(
    "%(asctime)s : %(message)s", datefmt="%d%m%Y %I:%M:%S %p"
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
log.setLevel(10)
log.addHandler(handler)


class sendSMS:

    def send():
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
                                    from_='+12184223560',
                                    body='NVidia Card!',
                                    to='+14252836409' 
                                    )
        log.info("SMS Sent: " + message.sid)
        # no error handling here

