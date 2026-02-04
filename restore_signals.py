import json
import csv
import os

def restore():
    json_path = 'curl_output.json'
    csv_path = 'data/signals_log.csv'
    
    if not os.path.exists(json_path):
        print("curl_output.json not found")
        return

    with open(json_path, 'r') as f:
        data = json.load(f)
        
    signals = data.get('signals', [])
    if not signals:
        print("No signals in JSON")
        return

    print(f"Found {len(signals)} signals in JSON to restore.")
    
    # Read existing CSV to verify columns and avoid duplicates?
    # Actually, we know the file was overwritten/truncated to old data, so just append.
    # But let's check headers first to be safe.
    
    with open(csv_path, 'r') as f:
        lines = f.readlines()
        
    # Check if 2026-02-05 already exists (unlikely given previous check)
    if any('2026-02-05' in line for line in lines):
        print("2026-02-05 data already exists in CSV. Skipping restore.")
        # return 
        # Forcing append for now as user said it's missing
        
    # Header: ticker,name,signal_date,market,status,score,contraction_ratio,entry_price,foreign_5d,inst_5d,vcp_score,current_price,return_pct
    
    with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        count = 0
        for s in signals:
            try:
                # Map fields
                vcp_score = 0
                if s.get('gemini_recommendation'):
                    vcp_score = s['gemini_recommendation'].get('confidence', 0)
                
                row = [
                    s.get('ticker'),
                    s.get('name'),
                    s.get('signal_date'),
                    s.get('market'),
                    s.get('status'),
                    s.get('score'),
                    s.get('contraction_ratio'),
                    s.get('entry_price'),
                    s.get('foreign_5d'),
                    s.get('inst_5d'),
                    vcp_score,
                    s.get('current_price'),
                    s.get('return_pct')
                ]
                writer.writerow(row)
                count += 1
            except Exception as e:
                print(f"Error skipping row: {e}")
                
    print(f"Successfully restored {count} rows.")

if __name__ == "__main__":
    restore()
