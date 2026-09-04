#!/usr/bin/env python3
"""
VoiceLedger Operational Fix & Event Replay Script.

Safely establishes the authoritative ProviderConnection for Razorpay and
replays existing RECEIVED PaymentEvents into canonical Payment and OutboxEvent records.

Usage:
    uv run python scripts/operational_fix_and_replay.py
"""
import logging
from pathlib import Path
import sys
import uuid
from datetime import datetime, timezone

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import settings
from backend.app.models.merchant import Merchant
from backend.app.models.provider_connection import ProviderConnection
from backend.app.models.payment import Payment
from backend.app.models.payment_event import PaymentEvent, EventProcessingStatus
from backend.app.models.outbox_event import OutboxEvent
from backend.app.services.payment_event_service import payment_event_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("voiceledger.operations.replay")

DEFAULT_MERCHANT_ID = uuid.UUID("881865c7-d548-419f-8f37-4a451b3804a7")
RAZORPAY_ACCOUNT_ID = "acc_TW86W18hcuWq9g"
RAZORPAY_ACCOUNT_ID_RAW = "TW86W18hcuWq9g"


def main():
    print("=" * 70)
    print(" VoiceLedger — Operational ProviderConnection Setup & Event Replay")
    print("=" * 70)

    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # -------------------------------------------------------------
        # 1. Verify Active Merchant
        # -------------------------------------------------------------
        merchant = db.query(Merchant).filter(Merchant.id == DEFAULT_MERCHANT_ID).first()
        if not merchant:
            print(f"[!] Target merchant {DEFAULT_MERCHANT_ID} not found in database.")
            sys.exit(1)

        print(f"\n[Step 1] Verified Target Merchant:")
        print(f"  - Merchant ID:   {merchant.id}")
        print(f"  - Store Name:    {merchant.name}")
        print(f"  - Status:        {merchant.status}")

        # -------------------------------------------------------------
        # 2. Ensure ProviderConnection Records Exist
        # -------------------------------------------------------------
        print("\n[Step 2] Configuring Authoritative ProviderConnection Records...")
        for acc_ref in [RAZORPAY_ACCOUNT_ID, RAZORPAY_ACCOUNT_ID_RAW]:
            existing_conn = (
                db.query(ProviderConnection)
                .filter(
                    ProviderConnection.merchant_id == merchant.id,
                    ProviderConnection.provider == "RAZORPAY",
                    ProviderConnection.provider_account_reference == acc_ref,
                )
                .first()
            )
            if not existing_conn:
                conn = ProviderConnection(
                    id=uuid.uuid4(),
                    merchant_id=merchant.id,
                    provider="RAZORPAY",
                    provider_account_reference=acc_ref,
                    status="ACTIVE",
                )
                db.add(conn)
                db.commit()
                print(f"  [+] Created ProviderConnection: {acc_ref} -> Merchant {merchant.id}")
            else:
                print(f"  [=] ProviderConnection already exists: {acc_ref} (status: {existing_conn.status})")

        # -------------------------------------------------------------
        # 3. Replay Existing Stuck PaymentEvents
        # -------------------------------------------------------------
        print("\n[Step 3] Inspecting Stuck PaymentEvents (status == 'RECEIVED')...")
        stuck_events = (
            db.query(PaymentEvent)
            .filter(PaymentEvent.processing_status == EventProcessingStatus.RECEIVED.value)
            .order_by(PaymentEvent.received_at.asc())
            .all()
        )

        print(f"  Found {len(stuck_events)} event(s) awaiting processing.\n")

        processed_count = 0
        failed_count = 0

        for idx, event in enumerate(stuck_events, start=1):
            print(f"  [{idx}/{len(stuck_events)}] Replaying Event {event.event_id} ({event.event_type})...")
            print(f"      Provider Payment ID: {event.provider_payment_id}")

            # Safely associate with merchant if currently unassigned
            if event.merchant_id is None:
                event.merchant_id = merchant.id
                db.commit()
                db.refresh(event)

            try:
                # Call PaymentEventService (will fetch payment via provider adapter if needed)
                result = payment_event_service.process_payment_event(
                    db=db,
                    event_id=event.id,
                    auto_commit=True,
                    raise_on_error=False,
                )

                if result.processing_status == EventProcessingStatus.PROCESSED:
                    processed_count += 1
                    print(f"      [OK] SUCCESS -> Payment ID: {result.payment_id}")
                    if result.outbox_event_id:
                        print(f"      [OK] OutboxEvent Created: {result.outbox_event_id}")
                    else:
                        print(f"      [i] No OutboxEvent generated (duplicate or non-actionable state)")
                else:
                    failed_count += 1
                    print(f"      [FAIL]: {result.error_code} - {result.error_message}")

            except Exception as e:
                failed_count += 1
                logger.exception("Error processing event %s: %s", event.id, e)

        # -------------------------------------------------------------
        # 4. Summary & Verification
        # -------------------------------------------------------------
        db.expire_all()
        total_payments = db.query(Payment).filter(Payment.merchant_id == merchant.id).count()
        total_outbox = db.query(OutboxEvent).count()
        pending_outbox = db.query(OutboxEvent).filter(OutboxEvent.status == "PENDING").count()

        print("\n" + "=" * 70)
        print(" Replay Summary & Final Database Verification:")
        print(f"  - Replayed Events:      {processed_count} processed, {failed_count} failed")
        print(f"  - Total Payments in DB: {total_payments}")
        print(f"  - Total Outbox Events:  {total_outbox}")
        print(f"  - Pending Outbox (ready for OutboxWorker): {pending_outbox}")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    main()
