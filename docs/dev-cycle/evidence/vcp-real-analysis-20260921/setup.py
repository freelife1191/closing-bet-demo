"""Create a secret-free execution checkout; no product imports."""
import hashlib, json, os, pathlib, subprocess, tarfile, tempfile
r=pathlib.Path.cwd(); e=r/'docs/dev-cycle/evidence/vcp-real-analysis-20260921'
s=pathlib.Path(tempfile.mkdtemp(prefix='vcp-real-analysis-20260921-')).resolve()
archive=s/'source.tar'
subprocess.run(['git','archive','--format=tar','-o',str(archive),'HEAD'],check=True)
with tarfile.open(archive) as t: t.extractall(s,filter='data')
archive.unlink(); (s/'tmp').mkdir(); (s/'venv').symlink_to(r/'venv',target_is_directory=True)
subprocess.run(['cp','-cR',str(r/'frontend/node_modules'),str(s/'frontend/node_modules')],check=True)
policy='(version 1)\n(allow default)\n'
policy+=f'(deny file-write* (subpath "{r}"))\n'
for p in ['.env','.env.production','.env.vertex','data','logs']:
 policy+=f'(deny file-read* (subpath "{r/p}"))\n'
policy+='(deny network*)\n(allow network* (local ip "localhost:*") (remote ip "localhost:*"))\n'
policy+='(deny network* (remote ip "localhost:3500") (remote ip "localhost:5501"))\n'
(s/'qa.sb').write_text(policy)
info={'base':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'scratch':str(s),'root_package_sha256':hashlib.sha256((r/'package.json').read_bytes()).hexdigest()}
(e/'review-input.json').write_text(json.dumps(info,indent=2)+'\n')
print(json.dumps(info))
