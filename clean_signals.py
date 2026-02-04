import csv
import os

def clean_csv():
    csv_path = 'data/signals_log.csv'
    if not os.path.exists(csv_path):
        print("CSV not found")
        return
    
    # Read all lines
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        rows = list(reader)
        
    print(f"Original Row Count: {len(rows)}")
    
    # Dedup logic: Keep LAST occurrence of (ticker, signal_date)
    # Use a dict to store rows, key = (ticker, signal_date)
    # By iterating and overwriting, we effectively keep the last one.
    
    unique_rows = {}
    for row in rows:
        if len(row) < 3: continue # Skip malformed
        ticker = row[0]
        # name = row[1]
        signal_date = row[2]
        
        unique_rows[(ticker, signal_date)] = row
        
    cleaned_rows = list(unique_rows.values())
    print(f"Cleaned Row Count: {len(cleaned_rows)}")
    
    # Ensure correct order? Or just preserve as is?
    # Usually we want date sorted.
    # Let's sort by date descending to be nice.
    cleaned_rows.sort(key=lambda x: x[2], reverse=True)
    
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        if header:
            writer.writerow(header)
        writer.writerows(cleaned_rows)
        
    print("Successfully cleaned signals_log.csv")

if __name__ == "__main__":
    clean_csv()
