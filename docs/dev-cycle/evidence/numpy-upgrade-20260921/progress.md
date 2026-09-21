# NumPy migration progress

Critic ACCEPT after concrete venv/fixture/UI specification. Setup prefix/numpy/pip paths proven owned. First pip attempt never started: sandbox-exec rejects literal IP hosts (only * or localhost). Installation profile now permits HTTPS port443/DNS only; pip index fixed to officialPyPI withconfigsdisabled, wheel URLs checked in pip report. Product/test profile still denies external network. Originalvenv writes denied.

Second install setup failed at DNS inside Seatbelt; no packages changed. Safer alternate: bounded stdlib downloader retrieves two hash-verified official PyPI wheels into owned scratch, then pip runs offline under normal no-external-network sandbox. No widening product network policy.

Encoder NumPy2 RED2fail→alias removal targetGREEN. Actual installed pykrx source inspected; index-name lookup lives in stock_api.get_index_ticker_name (not krx namespace); plan mapping corrected. Clean subprocess isolates earlier suite module doubles; six real public APIs incl daily-flow tested with Post.read only and ISIN/name metadata doubles, all HTTP guard.

SECURITY BLOCK: source1.2.7 introduced auth session in Get; actual KRXSession.get_headers + actual Naver publicAPI with invented cookie captured Cookie on HTTP Naver URL; externalrequests0. Latest1.2.9/master same perofficialsource. No safe version-only upgrade; no customvendor shim in approved minimaldesign. Candidate5files preserved under candidate/, rootrequirements/encoder restored exactly HEAD and own3tests removed. No originalvenv changes. INFRA018 remainsblocked, not archived.
