"""Run locally to configure your own Gmail account; passwords never echo."""
from getpass import getpass
from pathlib import Path
import os
import secrets
from dotenv import set_key, dotenv_values


def main():
    path = Path(__file__).resolve().parents[1] / '.env'
    email = input('Your Gmail address (OTP sender): ').strip().lower()
    if '@' not in email or '\n' in email or '\r' in email:
        raise SystemExit('Enter a valid email address.')
    password = getpass('Google App Password (16 characters, hidden): ').replace(' ', '')
    if len(password) != 16:
        raise SystemExit('Use a Google App Password, not your normal Google password.')
    path.touch(mode=0o600, exist_ok=True)
    if os.name != 'nt':
        path.chmod(0o600)
    existing = dotenv_values(path)
    values = {'EMAIL_PROVIDER': 'smtp', 'EMAIL_FROM': email, 'SMTP_HOST': 'smtp.gmail.com',
              'SMTP_PORT': '465', 'SMTP_USERNAME': email, 'SMTP_PASSWORD': password}
    for key in ('SECRET_KEY', 'JWT_SECRET_KEY'):
        if not existing.get(key):
            values[key] = secrets.token_hex(32)
    for key, value in values.items():
        set_key(str(path), key, value)
    print('Saved backend/.env privately. Do not share this file. Restart the backend after changes.')


if __name__ == '__main__':
    main()
