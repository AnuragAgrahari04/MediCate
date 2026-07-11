"""Razorpay integration utilities for MediCate."""
import hmac
import hashlib
import razorpay
from django.conf import settings

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import requests
_old_request = requests.Session.request
def _new_request(*args, **kwargs):
    kwargs['verify'] = False
    return _old_request(*args, **kwargs)
requests.Session.request = _new_request


def get_razorpay_client():
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


def create_razorpay_order(amount_inr, appointment_id):
    """
    Create a Razorpay order for the given amount.
    amount_inr: integer, in INR (e.g., 500)
    Returns the order dict from Razorpay or raises an exception.
    """
    client = get_razorpay_client()
    order = client.order.create({
        'amount':   amount_inr * 100,   # Razorpay expects paise
        'currency': 'INR',
        'receipt':  f'appt_{appointment_id}',
        'notes': {
            'appointment_id': str(appointment_id),
            'platform':       'MediCate',
        }
    })
    return order


def verify_razorpay_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """
    Verify the payment signature from Razorpay webhook.
    Returns True if valid, False otherwise.
    """
    try:
        client = get_razorpay_client()
        client.utility.verify_payment_signature({
            'razorpay_order_id':   razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature':  razorpay_signature,
        })
        return True
    except Exception:
        return False


def initiate_refund(payment_id, amount_inr=None):
    """
    Initiate a full or partial refund.
    amount_inr: if None, full refund is done.
    """
    try:
        client = get_razorpay_client()
        params = {}
        if amount_inr:
            params['amount'] = amount_inr * 100
        refund = client.payment.refund(payment_id, params)
        return refund
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'Razorpay refund failed: {e}')
        return None
