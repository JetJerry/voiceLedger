import hmac
import hashlib
from backend.app.services.razorpay_service import razorpay_service


def test_payment_link_generation():
    result = razorpay_service.create_payment_link(
        amount=200.0,
        sale_id="sale_test123",
        customer_name="Rahul",
        customer_phone="+919876543210"
    )

    assert result["amount"] == 200.0
    assert result["sale_id"] == "sale_test123"
    assert "short_url" in result
    assert result["id"].startswith("plink_")


def test_webhook_signature_verification():
    secret = "test_webhook_secret_123"
    old_secret = razorpay_service.webhook_secret
    try:
        razorpay_service.webhook_secret = secret
        payload = b'{"event":"payment_link.paid"}'
        valid_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        
        assert razorpay_service.verify_webhook_signature(payload, valid_sig) is True
        assert razorpay_service.verify_webhook_signature(payload, "invalid_sig_abc") is False
    finally:
        razorpay_service.webhook_secret = old_secret
