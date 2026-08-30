import json
import random
from pathlib import Path

PRODUCTS = [
    ("coffee", 50.0),
    ("sandwich", 80.0),
    ("tea", 20.0),
    ("chai", 20.0),
    ("burger", 100.0),
    ("pizza", 300.0),
    ("coke", 40.0),
    ("notebook", 60.0),
    ("pen", 20.0),
    ("shirt", 500.0)
]

QUANTITY_WORDS = {1: ["ek", "1", "one"], 2: ["do", "2", "two"], 3: ["teen", "3", "three"]}


def generate_speech_prompt(item_name: str, qty: int, unit_price: float) -> str:
    qty_word = random.choice(QUANTITY_WORDS.get(qty, [str(qty)]))
    templates = [
        f"{qty_word} {item_name} diye, {int(unit_price)} each.",
        f"{qty_word} {item_name} ka payment lena hai.",
        f"{qty_word} {item_name} pack kar diya.",
        f"{qty_word} {item_name} {int(unit_price * qty)} rupaye total.",
        f"{qty_word} {item_name} sold."
    ]
    return random.choice(templates)


def generate_dataset(num_samples: int = 100) -> list:
    random.seed(42)
    dataset = []
    
    # 40 FULL, 20 PARTIAL, 20 PENDING, 10 FAILED, 10 UNMATCHED
    scenarios = (
        ["FULL"] * 40 +
        ["PARTIAL"] * 20 +
        ["PENDING"] * 20 +
        ["FAILED"] * 10 +
        ["UNMATCHED"] * 10
    )
    random.shuffle(scenarios)

    for i, scenario in enumerate(scenarios, 1):
        item_name, price = random.choice(PRODUCTS)
        qty = random.choice([1, 2, 3])
        expected_total = qty * price
        
        speech = generate_speech_prompt(item_name, qty, price)

        if scenario == "FULL":
            paid_amount = expected_total
            status = "PAID"
        elif scenario == "PARTIAL":
            paid_amount = round(expected_total * 0.5, 2)
            status = "PARTIAL"
        elif scenario == "PENDING":
            paid_amount = 0.0
            status = "PENDING"
        elif scenario == "FAILED":
            paid_amount = 0.0
            status = "FAILED"
        else: # UNMATCHED
            paid_amount = expected_total
            status = "UNMATCHED"

        entry = {
            "id": f"txn_{i:03d}",
            "speech_input": speech,
            "expected_items": [{"name": item_name, "quantity": qty, "price": price}],
            "expected_total": expected_total,
            "payment_scenario": scenario,
            "payment_amount": paid_amount,
            "target_status": status
        }
        dataset.append(entry)

    return dataset


if __name__ == "__main__":
    data = generate_dataset(100)
    out_path = Path(__file__).resolve().parent / "dataset.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Generated {len(data)} product evaluation test cases in {out_path}")
