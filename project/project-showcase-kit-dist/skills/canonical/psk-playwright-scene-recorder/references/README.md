# References

Troubleshooting priorities:

- Validate browser/service readiness first with preflight.
- Check `project/video/evidence/record_summary.json` for failed scene IDs.
- Use `project/video/evidence/*.png` and `project/video/evidence/*.zip` to inspect selector/runtime failures.
- Re-run only failed scenes before full pipeline rerun.
