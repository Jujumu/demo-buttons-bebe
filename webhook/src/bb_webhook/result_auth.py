"""Dedicated processor-to-result API credential; never an owner session token."""
import hmac
import re


def configured_secret(settings):
    value=getattr(settings,'processor_result_secret','')
    return value if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_-]{32,256}',value) else ''


def authorized(header,secret):
    return bool(secret) and hmac.compare_digest(header.encode('utf-8'),('Bearer '+secret).encode('utf-8'))
