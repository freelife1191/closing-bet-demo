"""Losslessly archive only this round's closed plain-text evidence."""
import gzip, hashlib, json
from pathlib import Path
root=Path(__file__).resolve().parent
index=json.loads((root/"raw-index.json").read_text()) if (root/"raw-index.json").exists() else {}
for path in sorted(root.iterdir()):
    if path.suffix=='.log' or path.name=='review-diff.txt' or path.name.startswith('ego-') and path.suffix=='.txt':
        raw=path.read_bytes()
        packed=gzip.compress(raw,mtime=0)
        dest=path.with_name(path.name+'.gz')
        dest.write_bytes(packed)
        assert gzip.decompress(dest.read_bytes())==raw
        index[dest.name]={'raw_sha256':hashlib.sha256(raw).hexdigest(),'raw_bytes':len(raw)}
        path.unlink()
(root/'raw-index.json').write_text(json.dumps(index,indent=2)+'\n')
