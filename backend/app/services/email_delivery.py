"""Real email delivery. Never return or log verification codes."""
import os
import smtplib
import ssl
from email.message import EmailMessage
import requests


def send_otp(email, code):
    provider = os.environ.get('EMAIL_PROVIDER', 'smtp')
    subject = 'Your GoGreen verification code'
    body = f'Your GoGreen verification code is {code}. It expires in 10 minutes. Do not share it.'
    sender = os.environ.get('EMAIL_FROM', '')
    if not sender:
        raise RuntimeError('Email delivery is not configured')
    if provider == 'resend':
        key = os.environ.get('RESEND_API_KEY')
        if not key:
            raise RuntimeError('Email delivery is not configured')
        response = requests.post('https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {key}'},
            json={'from': sender, 'to': [email], 'subject': subject, 'text': body}, timeout=20)
        response.raise_for_status()
        return
    if provider != 'smtp':
        raise RuntimeError('Unsupported email provider')
    host = os.environ.get('SMTP_HOST')
    username = os.environ.get('SMTP_USERNAME')
    password = os.environ.get('SMTP_PASSWORD')
    port = int(os.environ.get('SMTP_PORT', '465'))
    if not all((host, username, password)) or port not in (465, 587):
        raise RuntimeError('Configure authenticated SMTP on port 465 or 587')
    message = EmailMessage()
    message['From'] = sender
    message['To'] = email
    message['Subject'] = subject
    message.set_content(body)
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(username, password)
            smtp.send_message(message)
