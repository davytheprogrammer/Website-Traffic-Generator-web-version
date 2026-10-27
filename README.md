# Website Availability Checker

A small local dashboard for running clearly identified, low-rate availability checks against websites you own or are explicitly authorized to test.

This project intentionally does not simulate visitors or try to influence analytics. It sends at most one request per second to one configured URL, uses a fixed identifying user-agent, stops at 30 requests, and does not crawl pages, follow redirects, rotate proxies, or impersonate browsers.

## Requirements

- Python 3.10+
- A hostname you control or have permission to check

## Run locally

```sh
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt

# Use exact origins only. Include non-default ports; no wildcard entries are supported.
export LOADTEST_ALLOWED_ORIGINS="http://127.0.0.1:5000,https://staging.example.test"
python app.py
```

Open <http://127.0.0.1:5000>. The control panel binds to loopback only. It has no authentication and must not be exposed to the public internet or placed behind a public reverse proxy.

The origin allowlist is a server-side setting, not a browser setting. Each entry must be an exact `http://` or `https://` origin, including a non-default port when needed; wildcards and paths are rejected. Enter a full URL whose origin exactly matches one of the configured entries. Validation only checks URL syntax and the allowlist; it does not contact the target.

## Safeguards

- The UI requires an explicit authorization acknowledgment before it starts a check.
- The server independently checks the exact-origin allowlist for every requested URL.
- Sessions are sequential, limited to 30 requests, and paced at no more than one request per second.
- A target response of HTTP 429 or 503 stops the run early.
- Each request identifies itself as `AuthorizedAvailabilityCheck/1.0`.
- Requests do not follow redirects, persist cookies, fetch page assets, or discover links.
- The dashboard binds to `127.0.0.1` and accepts same-origin control requests only.

Only run checks within an agreed test window and stop if the target owner asks you to. Use a dedicated staging environment when possible. This tool is for availability smoke checks, not high-volume load testing.

## Project files

- `app.py` — local Flask UI and allowlist-checked API
- `availability_checker.py` — bounded, sequential request runner
- `url_validator.py` — URL normalization and exact-host authorization
- `templates/index.html` and `static/css/styles.css` — dashboard

## License

See [LICENSE.md](LICENSE.md).
