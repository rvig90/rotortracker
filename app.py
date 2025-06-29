import csv
import os
from datetime import datetime
from collections import defaultdict

CSV_FILE = "rotor_log.csv"

def load_log():
    log = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            log = list(reader)
    return log

def save_log(log):
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['date', 'sizeMM', 'quantity', 'type', 'remarks'])
        writer.writeheader()
        writer.writerows(log)

def add_entry():
    date = input("Enter date (YYYY-MM-DD) [leave empty for today]: ") or datetime.today().strftime('%Y-%m-%d')
    sizeMM = input("Enter rotor size in mm: ")
    quantity = input("Enter quantity: ")
    type_ = input("Enter type (in/out): ").lower()
    remarks = input("Enter remarks: ")

    entry = {
        'date': date,
        'sizeMM': sizeMM,
        'quantity': quantity,
        'type': type_,
        'remarks': remarks
    }

    log = load_log()
    log.append(entry)
    save_log(log)
    print("Entry added successfully.")

def show_inventory():
    log = load_log()
    inventory = defaultdict(int)
    for entry in log:
        qty = int(entry['quantity'])
        size = entry['sizeMM']
        if entry['type'] == 'in':
            inventory[size] += qty
        else:
            inventory[size] -= qty

    print("\nCurrent Inventory:")
    print("------------------------")
    for size, qty in inventory.items():
        print(f"{size} mm: {qty}")
    print("------------------------")

def view_log():
    log = load_log()
    if not log:
        print("No log entries yet.")
        return

    print("\nLog Entries:")
    print("{:<12} {:<8} {:<8} {:<6} {}".format("Date", "Size", "Qty", "Type", "Remarks"))
    print("-" * 50)
    for entry in log:
        print("{:<12} {:<8} {:<8} {:<6} {}".format(
            entry['date'],
            entry['sizeMM'],
            entry['quantity'],
            entry['type'],
            entry['remarks']
        ))
    print("-" * 50)

def main():
    while True:
        print("\nRotor Tracker Menu:")
        print("1. Add Entry")
        print("2. Show Inventory")
        print("3. View Log")
        print("4. Exit")
        choice = input("Enter your choice: ")

        if choice == '1':
            add_entry()
        elif choice == '2':
            show_inventory()
        elif choice == '3':
            view_log()
        elif choice == '4':
            print("Exiting Rotor Tracker.")
            break
        else:
            print("Invalid choice. Try again.")

if __name__ == '__main__':
    main()
