#!/usr/bin/env python3
"""CLI utility to export/import merchant profiles using the local DB session.

Usage:
  python manage_profiles.py export --merchant-id 1 --out profile.json
  python manage_profiles.py import --merchant-id 1 --in profile.json
"""
import argparse
import json
from backend.app.db.session import SessionLocal
from backend.app.models import Merchant, MerchantProfile


def export_profile(merchant_id: int, out_path: str):
    db = SessionLocal()
    try:
        merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if not merchant:
            print(f"Merchant {merchant_id} not found")
            return 1
        profile = db.query(MerchantProfile).filter(MerchantProfile.merchant_id == merchant.id).first()
        cfg = {}
        if profile:
            try:
                cfg = json.loads(profile.config_json)
            except Exception:
                cfg = {}
        payload = {"merchant_id": merchant.id, "config": cfg}
        if out_path:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            print(f"Exported profile to {out_path}")
        else:
            print(json.dumps(payload, indent=2))
        return 0
    finally:
        db.close()


def import_profile(merchant_id: int, in_path: str):
    db = SessionLocal()
    try:
        merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if not merchant:
            print(f"Merchant {merchant_id} not found")
            return 1
        with open(in_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        cfg = payload.get("config", {})
        cfg_text = json.dumps(cfg)
        profile = db.query(MerchantProfile).filter(MerchantProfile.merchant_id == merchant.id).first()
        from datetime import datetime, timezone
        if not profile:
            profile = MerchantProfile(merchant_id=merchant.id, config_json=cfg_text)
            db.add(profile)
        else:
            profile.config_json = cfg_text
            profile.updated_at = datetime.now(timezone.utc)
        db.commit()
        print(f"Imported profile for merchant {merchant_id}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    e = sub.add_parser("export")
    e.add_argument("--merchant-id", type=int, required=True)
    e.add_argument("--out", dest="out", default=None)

    i = sub.add_parser("import")
    i.add_argument("--merchant-id", type=int, required=True)
    i.add_argument("--in", dest="in_path", required=True)

    args = p.parse_args()
    if args.cmd == "export":
        raise SystemExit(export_profile(args.merchant_id, args.out))
    if args.cmd == "import":
        raise SystemExit(import_profile(args.merchant_id, args.in_path))
    p.print_help()
