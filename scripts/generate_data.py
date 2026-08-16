import argparse
import random
import json

def generate_data(size: str):
    random.seed(42) # Fixed seed as requested
    
    counts = {
        "small": {"suppliers": 2, "dcs": 1, "stores": 5, "products": 10},
        "medium": {"suppliers": 5, "dcs": 3, "stores": 20, "products": 50},
        "large": {"suppliers": 20, "dcs": 10, "stores": 100, "products": 500},
    }
    
    cfg = counts.get(size.lower(), counts["small"])
    
    data = {
        "locations": [{"id": f"DC{i}", "name": f"Distribution Center {i}", "type": "DC"} for i in range(cfg["dcs"])] +
                     [{"id": f"ST{i}", "name": f"Store {i}", "type": "Store"} for i in range(cfg["stores"])],
        "products": [{"id": f"P{i}", "name": f"Product {i}", "category": "General"} for i in range(cfg["products"])]
    }
    
    print(f"Generated {len(data['locations'])} locations and {len(data['products'])} products.")
    
    with open("data/synthetic/generated_data.json", "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=str, default="small", choices=["small", "medium", "large"])
    args = parser.parse_args()
    generate_data(args.size)
