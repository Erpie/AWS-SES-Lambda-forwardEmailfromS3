# Copyright 2010-2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# This file is licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License. A copy of the
# License is located at
#
# http://aws.amazon.com/apache2.0/
#
# This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS
# OF ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

import os
import boto3
import email
import re
from botocore.exceptions import ClientError
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

region = os.environ['Region']
sender = os.environ['MailSender']
recipient = os.environ['MailRecipient'] 


def get_message_from_s3(message_id):

    incoming_email_bucket = os.environ['MailS3Bucket']
    incoming_email_prefix = os.environ['MailS3Prefix']

    if incoming_email_prefix:
        object_path = (incoming_email_prefix + "/" + message_id)
    else:
        object_path = message_id

    object_http_path = (f"http://s3.console.aws.amazon.com/s3/object/{incoming_email_bucket}/{object_path}?region={region}")

    # Create a new S3 client.
    client_s3 = boto3.client("s3")

    # Get the email object from the S3 bucket.
    object_s3 = client_s3.get_object(Bucket=incoming_email_bucket, Key=object_path)
    
    # Read the content of the message.
    file = object_s3['Body'].read()

    file_dict = {
        "file": file,
        "path": object_http_path
    }

    return file_dict


def create_message(file_dict):

    separator = ";"

    # Parse the email body.
    mail_object = email.message_from_string(file_dict['file'].decode('utf-8'))

    # Create a new subject line.
    subject_original = mail_object['Subject']
    sent_date = mail_object['date']
    subject = "FW: " + subject_original

   # The body text of the email.
    body_text = ("The attached message was received from "
              + separator.join(mail_object.get_all('From'))
              + ". This message is archived at " + file_dict['path'])
                 
    # The file name to use for the attached message. Uses regex to remove all
    # non-alphanumeric characters, and appends a file extension.
    filename = re.sub('[^0-9a-zA-Z]+', '_', subject_original) + ".eml"
    
    # Create a MIME container.
    msg = MIMEMultipart()
    
    # Create a MIME text part.
    text_part = MIMEText(body_text, _subtype="html")

    # Attach the text part to the MIME message.
    msg.attach(text_part)

    # Add subject, from and to lines.
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient
    
    # Attach the file object to the message.
    msg.attach(mail_object)
    
    return msg


def send_email(message):
    
    # Create a new SES client.
    client_ses = boto3.client('ses', os.environ['Region'])

    # Send the email.
    try:
        #Provide the contents of the email.
        response = client_ses.send_raw_email(
            Source=message['Source'],
            Destinations=[
                message['Destinations']
            ],
            RawMessage={
                'Data':message['Data']
            }
        ) 

    # Display an error if something goes wrong.
    except ClientError as e:
        output = e.response['Error']['Message']
    else:
        output = "Email sent! Message ID: " + response['MessageId']

    return output


def lambda_handler(event, context):
    
    # Get the unique ID of the message. This corresponds to the name of the file in S3.
    message_id = event['Records'][0]['ses']['mail']['messageId']
    print(f"Received message ID {message_id}")

    # Retrieve the file from the S3 bucket.
    file_dict = get_message_from_s3(message_id)

    # Create the message.
    message = create_message(file_dict)

    # Send the email and print the result.
    server = smtplib.SMTP(os.environ['MailSMTPserver'], 587)
    server.starttls()
    server.login(os.environ['MailSMTPuser'], os.environ['MailSMTPpassword'])
    result = server.sendmail(sender, recipient, message.as_string())
    print(result)
    server.quit()