import json
import os

def patch_json_files():
    data_dir = 'data'
    files_to_patch = ['jongga_v2_latest.json']
    
    # Add any jongga_v2_results_*.json files
    for f in os.listdir(data_dir):
        if f.startswith('jongga_v2_results_') and f.endswith('.json'):
            files_to_patch.append(f)
            
    print(f"Found files to patch: {files_to_patch}")

    for filename in files_to_patch:
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            continue
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            updated = False
            if 'signals' in data:
                for signal in data['signals']:
                    if 'score' in signal:
                        score = signal['score']
                        # Calculate total if missing
                        if 'total' not in score:
                            total = (
                                score.get('news', 0) +
                                score.get('volume', 0) +
                                score.get('chart', 0) +
                                score.get('candle', 0) +
                                score.get('timing', 0) +
                                score.get('supply', 0)
                            )
                            score['total'] = total
                            updated = True
                            
            if updated:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"Patched {filename}")
            else:
                print(f"No changes needed for {filename}")
                
        except Exception as e:
            print(f"Error patching {filename}: {e}")

if __name__ == "__main__":
    patch_json_files()
