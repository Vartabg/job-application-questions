"""Collect the questions on public Greenhouse job-application forms.

Reads board tokens from employers.txt, lists each board's open jobs, reads up
to PER_BOARD forms per board (US locations first) and writes a dated snapshot
to data/forms-<today>.json. Only public, unauthenticated GET requests are made.
Nothing is submitted.

Usage:
    python3 collect.py [--out PATH] [--limit-boards N]
"""
import argparse
import datetime
import json
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
BOARD = "https://boards-api.greenhouse.io/v1/boards/{}"
LIST = "https://boards-api.greenhouse.io/v1/boards/{}/jobs"
FORM = "https://boards-api.greenhouse.io/v1/boards/{}/jobs/{}?questions=true"
FORM_URL = "https://boards.greenhouse.io/{}/jobs/{}"
PER_BOARD = 8
UA = {"User-Agent": "form-question-count/1.0"}

STATES = (
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND "
    "OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC"
).split()
US = re.compile(
    r"\b(US|USA|U\.S\.A?\.?|United States)\b|,\s*(" + "|".join(STATES) + r")\b|"
    r"New York|San Francisco|Austin|Seattle|Chicago|Boston|Denver|Atlanta|Los Angeles",
)


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15) as r:
            return json.load(r), ""
    except urllib.error.HTTPError as e:
        return None, f"http {e.code}"
    except Exception as e:  # noqa: BLE001
        return None, type(e).__name__


def read_boards(path=HERE / "employers.txt"):
    return sorted({line.strip() for line in Path(path).read_text().splitlines() if line.strip()})


def read_form(board, job):
    d, err = get(FORM.format(board, job["id"]))
    loc = (job.get("location") or {}).get("name") or ""
    rec = {"board": board, "job": job["id"], "location": loc, "us": bool(US.search(loc)), "error": err, "q": []}
    if not d:
        return rec
    for q in d.get("questions") or []:
        fields = q.get("fields") or []
        opts = [v.get("label") or "" for f in fields for v in f.get("values") or []]
        types = sorted({f.get("type") or "" for f in fields})
        rec["q"].append(["custom", q.get("label") or "", bool(q.get("required")), types, opts])
    for block in d.get("compliance") or []:
        for q in block.get("questions") or []:
            opts = [v.get("label") or "" for f in q.get("fields") or [] for v in f.get("values") or []]
            rec["q"].append(["eeoc", q.get("label") or "", bool(q.get("required")), [], opts])
    for q in (d.get("demographic_questions") or {}).get("questions") or []:
        opts = [o.get("label") or "" for o in q.get("answer_options") or []]
        rec["q"].append(["demographic", q.get("label") or "", bool(q.get("required")), [], opts])
    return rec


def do_board(board):
    d, err = get(LIST.format(board))
    if not d:
        return board, err, [], 0
    jobs = d.get("jobs") or []
    us = [j for j in jobs if US.search((j.get("location") or {}).get("name") or "")]
    rest = [j for j in jobs if j not in us]
    picked = (us + rest)[:PER_BOARD]
    return board, "", [read_form(board, j) for j in picked], len(jobs)


def board_name(board):
    d, _err = get(BOARD.format(board))
    if not d:  # one retry for transient failures
        d, _err = get(BOARD.format(board))
    return board, (d or {}).get("name") or board, bool(d and d.get("name"))


def fetch_names(tokens):
    """Return ({token: display name}, [tokens whose name could not be fetched])."""
    with ThreadPoolExecutor(max_workers=4) as pool:
        res = list(pool.map(board_name, tokens))
    return {t: n for t, n, _ in res}, [t for t, _, ok in res if not ok]


def to_snapshot(raw_forms, names, fetched_on):
    forms = []
    for f in raw_forms:
        assert not f.get("error"), f"form error on {f['board']}/{f['job']}: {f['error']}"
        forms.append(
            {
                "board": f["board"],
                "job": f["job"],
                "location": f["location"],
                "us": f["us"],
                "form_url": FORM_URL.format(f["board"], f["job"]),
                "api_url": FORM.format(f["board"], f["job"]),
                "questions": [
                    {"section": s, "label": label, "required": req, "field_types": types, "options": opts}
                    for s, label, req, types, opts in f["q"]
                ],
            }
        )
    with_forms = sorted({f["board"] for f in forms})
    return {
        "fetched_on": fetched_on,
        "source": "Greenhouse Job Board API",
        "per_board_limit": PER_BOARD,
        "boards": {b: names.get(b, b) for b in with_forms},
        "forms": forms,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", help="output path (default data/forms-<today>.json)")
    ap.add_argument("--limit-boards", type=int, help="only read the first N boards (quick test)")
    args = ap.parse_args()

    today = datetime.date.today().isoformat()
    out = Path(args.out) if args.out else HERE / "data" / f"forms-{today}.json"
    boards = read_boards()
    if args.limit_boards:
        boards = boards[: args.limit_boards]

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(do_board, boards))
    raw, board_err = [], {}
    for _b, err, forms, _n in results:
        if err:
            board_err[_b] = err
            continue
        raw.extend(forms)
    # keep forms that failed to load out of the snapshot, but report them
    bad = [f for f in raw if f["error"]]
    raw = [f for f in raw if not f["error"]]
    names, name_fail = fetch_names(sorted({f["board"] for f in raw}))
    snap = to_snapshot(raw, names, today)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, indent=1, ensure_ascii=False) + "\n")
    print(f"boards read: {len(boards)}  boards failed: {len(board_err)}  form errors: {len(bad)}")
    print(f"forms written: {len(snap['forms'])}  employers: {len(snap['boards'])}  names not fetched: {len(name_fail)}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
