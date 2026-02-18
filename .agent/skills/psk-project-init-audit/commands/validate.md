# Validate

Run init audit and ensure all required evidence files exist.

```bash
python3 .agent/skills/psk-project-init-audit/scripts/run_init_audit.py --project-root .
test -f project/video/evidence/project_audit.json
test -f project/video/evidence/project_runbook.md
test -f project/video/evidence/project_flows.md
```
