import json
import random
from pathlib import Path

CUSTOMERS = [
    ("Rahul Sharma", "+919876543210"),
    ("Amit Patel", "+919876543211"),
    ("Neha Gupta", "+919876543212"),
    ("Priya Singh", "+919876543213"),
    ("Vikram Verma", "+919876543214"),
    ("Suresh Kumar", "+919876543215"),
    ("Pooja Nair", "+919876543216"),
    ("Rohan Mehta", "+919876543217"),
    ("Ananya Roy", "+919876543218"),
    ("Deepak Joshi", "+919876543219")
]

MENU = [
    ("burger", 100.0),
    ("cheese burger", 150.0),
    ("pizza", 300.0),
    ("veg pizza", 250.0),
    ("coke", 40.0),
    ("chai", 20.0),
    ("coffee", 50.0),
    ("veg thali", 180.0),
    ("paneer roll", 120.0),
    ("sandwich", 80.0)
]

QUANTITY_WORDS = {1: ["ek", "1", "one"], 2: ["do", "2", "two"], 3: ["teen", "3", "three"]}


def generate_speech_prompt(customer_name: str, item_name: str, qty: int, unit_price: float) -> str:
    qty_word = random.choice(QUANTITY_WORDS.get(qty, [str(qty)]))
    first_name = customer_name.split()[0]
    
    templates = [
        f"{first_name} ko {qty_word} {item_name} diye, {int(unit_price)} each.",
        f"{first_name} se {qty_word} {item_name} ka payment lena hai.",
        f"{first_name} ko {qty_word} {item_name} diye.",
        f"Customer {first_name}, {qty_word} {item_name} order kiya.",
        f"{first_name} ko {qty_word} {item_name} pack kar diya."
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
        cust_name, cust_phone = random.choice(CUSTOMERS)
        item_name, price = random.choice(MENU)
        qty = random.choice([1, 2, 3])
        expected_total = qty * price
        
        speech = generate_speech_prompt(cust_name, item_name, qty, price)

        if scenario == "FULL":
            paid_amount = expected_total
            status = "PAID"
        elif scenario == "PARTIAL":
            paid_amount = round(expected_total * random.choice([0.3, 0.5, 0.7]), 2)
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
            "expected_customer": cust_name.split()[0],
            "customer_phone": cust_phone,
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
    print(f"Generated {len(data)} evaluation test cases in {out_path}")
