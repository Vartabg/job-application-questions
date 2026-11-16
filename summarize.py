"""Summarize a forms snapshot made by collect.py.

Usage:
    python3 summarize.py data/forms-YYYY-MM-DD.json

Writes, named after the snapshot's fetched_on date:
    data/employers-<date>.csv        one row per employer
    data/matched-labels-<date>.csv   every question label matched to a topic
    data/summary-<date>.json         headline numbers
    EMPLOYERS.md                     one table row per employer
and prints the headline numbers.
"""
import csv
import json
import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent

TOPICS = {
    "gender": re.compile(r"\bgender\b", re.I),
    "pronouns": re.compile(r"\bpronouns?\b", re.I),
    "orientation": re.compile(r"sexual|orientation|lgbt", re.I),
    "transgender": re.compile(r"transgender", re.I),
    "race": re.compile(r"\brace\b|ethnic|hispanic", re.I),
    "veteran": re.compile(r"veteran", re.I),
    "disability": re.compile(r"disab", re.I),
}
SENSITIVE = ("gender", "pronouns", "orientation", "transgender")
DECLINE = re.compile(
    r"decline|prefer not|don.?t wish|do not wish|not to (say|answer|disclose|identify|specify)|choose not|rather not",
    re.I,
)
SKIP_LONG = re.compile(r"resume|\bcv\b|cover letter", re.I)

NOT_ASKED = "—"
OPTIONAL = "optional"
REQ_DECLINE = "required, can decline"
REQ_NO_DECLINE = "required, no decline choice"
REQ_FREE = "required, free text"


def matches(question):
    return [t for t, pat in TOPICS.items() if pat.search(question["label"])]


def topic_status(forms, topic):
    """Cell wording for one employer and topic, over all of its sampled forms."""
    hits = [q for f in forms for q in f["questions"] if topic in matches(q)]
    if not hits:
        return NOT_ASKED
    required = [q for q in hits if q["required"]]
    if not required:
        return OPTIONAL
    no_decline = [q for q in required if not any(DECLINE.search(o) for o in q["options"])]
    if not no_decline:
        return REQ_DECLINE
    if any(q["options"] for q in no_decline):
        return REQ_NO_DECLINE
    return REQ_FREE


def gender_source(forms):
    secs = {q["section"] for f in forms for q in f["questions"] if "gender" in matches(q)}
    eeoc = "eeoc" in secs
    own = bool(secs & {"demographic", "custom"})
    if eeoc and own:
        return "both"
    if eeoc:
        return "standard EEO block"
    if own:
        return "employer's own question"
    return NOT_ASKED


def is_written_answer(q):
    return (
        q["section"] == "custom"
        and q["required"]
        and "textarea" in q["field_types"]
        and not SKIP_LONG.search(q["label"])
    )


def example_form(forms):
    for topic in ("orientation", "gender"):
        for f in forms:
            if any(topic in matches(q) for q in f["questions"]):
                return f
    return forms[0]


def main(path):
    snap = json.loads(Path(path).read_text())
    date = snap["fetched_on"]
    names = snap["boards"]
    by_board = defaultdict(list)
    for f in snap["forms"]:
        by_board[f["board"]].append(f)
    boards = sorted(by_board, key=lambda b: (names.get(b, b).lower(), b))
    forms = snap["forms"]
    n_forms, n_emp = len(forms), len(boards)

    totals = [len(f["questions"]) for f in forms]
    reqs = [sum(1 for q in f["questions"] if q["required"]) for f in forms]

    rows = []
    for b in boards:
        fs = by_board[b]
        ex = example_form(fs)
        row = {
            "employer": names.get(b, b),
            "board": b,
            "forms_read": len(fs),
            "gender": topic_status(fs, "gender"),
            "gender_source": gender_source(fs),
            "orientation": topic_status(fs, "orientation"),
            "transgender": topic_status(fs, "transgender"),
            "pronouns": topic_status(fs, "pronouns"),
            "race": topic_status(fs, "race"),
            "veteran": topic_status(fs, "veteran"),
            "disability": topic_status(fs, "disability"),
            "written_answer_required": "yes" if any(is_written_answer(q) for f in fs for q in f["questions"]) else "no",
            "forms_with_written_answer_required": sum(1 for f in fs if any(is_written_answer(q) for q in f["questions"])),
            "has_eeoc_section_question": "yes" if any(q["section"] == "eeoc" for f in fs for q in f["questions"]) else "no",
            "has_demographic_section_question": "yes" if any(q["section"] == "demographic" for f in fs for q in f["questions"]) else "no",
            "example_form_url": ex["form_url"],
            "example_api_url": ex["api_url"],
        }
        rows.append(row)

    data = HERE / "data"
    data.mkdir(exist_ok=True)
    with open(data / f"employers-{date}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    # matched labels, for auditing the keyword matching
    agg = defaultdict(lambda: [set(), set()])
    for f in forms:
        for q in f["questions"]:
            for t in matches(q):
                # collapse runs of whitespace so each label fits on one CSV line
                key = (t, q["section"], " ".join(q["label"].split()))
                agg[key][0].add((f["board"], f["job"]))
                agg[key][1].add(f["board"])
    order = list(TOPICS)
    with open(data / f"matched-labels-{date}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["topic", "section", "label", "forms", "employers"])
        for (t, s, label), (fset, eset) in sorted(agg.items(), key=lambda kv: (order.index(kv[0][0]), -len(kv[1][0]), kv[0][1], kv[0][2])):
            w.writerow([t, s, label, len(fset), len(eset)])

    # headline numbers
    asks = {t: set() for t in TOPICS}
    required = {t: set() for t in TOPICS}
    nodecline = {t: set() for t in SENSITIVE}
    for f in forms:
        for q in f["questions"]:
            for t in matches(q):
                asks[t].add(f["board"])
                if q["required"]:
                    required[t].add(f["board"])
                    if t in SENSITIVE and not any(DECLINE.search(o) for o in q["options"]):
                        nodecline[t].add(f["board"])
    written_forms = [f for f in forms if any(is_written_answer(q) for q in f["questions"])]
    written_emp = {f["board"] for f in written_forms}
    src = {k: sum(1 for r in rows if r["gender_source"] == k) for k in ("standard EEO block", "employer's own question", "both")}
    secs = {s: len({f["board"] for f in forms for q in f["questions"] if q["section"] == s}) for s in ("eeoc", "demographic", "custom")}

    summary = {
        "fetched_on": date,
        "source": snap["source"],
        "per_board_limit": snap["per_board_limit"],
        "forms": n_forms,
        "employers": n_emp,
        "questions_per_form": {"median": st.median(totals), "max": max(totals)},
        "required_per_form": {"median": st.median(reqs), "max": max(reqs)},
        "employers_asking": {t: len(asks[t]) for t in TOPICS},
        "employers_requiring_an_answer": {t: len(required[t]) for t in TOPICS},
        "required_without_decline_choice": {
            t: {
                "employers": sorted(nodecline[t]),
                "free_text": sorted(r["board"] for r in rows if r[t] == REQ_FREE),
                "fixed_list": sorted(r["board"] for r in rows if r[t] == REQ_NO_DECLINE),
            }
            for t in SENSITIVE
        },
        "written_answer_required": {"forms": len(written_forms), "employers": len(written_emp)},
        "gender_source_employers": {
            "standard EEO block only": src["standard EEO block"],
            "employer's own question only": src["employer's own question"],
            "both": src["both"],
            "not asked": sum(1 for r in rows if r["gender_source"] == NOT_ASKED),
        },
        "employers_with_eeoc_section_question": secs["eeoc"],
        "employers_with_demographic_section_question": secs["demographic"],
        "employers_with_custom_section_question": secs["custom"],
    }
    (data / f"summary-{date}.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")

    # EMPLOYERS.md
    def esc(s):
        return str(s).replace("|", "\\|")

    lines = [
        "# Employers",
        "",
        f"Snapshot {date}. Forms read = sampled forms per employer (up to {snap['per_board_limit']}). "
        "Gender, Sexual orientation, Transgender and Pronouns show whether any sampled form has a matching question: "
        f"{NOT_ASKED} not asked, optional, or required (with or without a decline choice, or free text). "
        "Gender source says which part of the form holds the gender question. "
        "Written answer required = a required free-text question other than resume or cover letter. "
        "Example form links to a public form and its API data.",
        "",
        "| Employer | Forms read | Gender | Gender source | Sexual orientation | Transgender | Pronouns | Written answer required | Example form |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "| " + " | ".join(
                [
                    esc(r["employer"]), str(r["forms_read"]), r["gender"], r["gender_source"], r["orientation"],
                    r["transgender"], r["pronouns"], r["written_answer_required"],
                    f"[form]({r['example_form_url']}) · [data]({r['example_api_url']})",
                ]
            ) + " |"
        )
    (HERE / "EMPLOYERS.md").write_text("\n".join(lines) + "\n")

    # stdout
    out = [
        f"snapshot {date}: forms {n_forms}, employers {n_emp}",
        f"questions per form: median {st.median(totals)}, max {max(totals)}",
        f"required per form: median {st.median(reqs)}, max {max(reqs)}",
        "topic | employers asking | share | employers requiring an answer | required, no decline choice",
    ]
    for t in TOPICS:
        a = len(asks[t])
        nd = len(nodecline[t]) if t in SENSITIVE else "-"
        out.append(f"{t} | {a} | {round(100 * a / n_emp)}% | {len(required[t])} | {nd}")
    for t in SENSITIVE:
        if nodecline[t]:
            free = sorted(r["board"] for r in rows if r[t] == REQ_FREE)
            fixed = sorted(r["board"] for r in rows if r[t] == REQ_NO_DECLINE)
            out.append(f"  no decline choice, {t}: free text {free}; fixed list {fixed}")
        if required[t]:
            out.append(f"  required {t}: {sorted(required[t])}")
    out.append(
        f"required written-answer question: {len(written_forms)} forms ({round(100 * len(written_forms) / n_forms)}%), "
        f"{len(written_emp)} employers ({round(100 * len(written_emp) / n_emp)}%)"
    )
    g = summary["gender_source_employers"]
    own_key = "employer's own question only"
    out.append(
        f"gender source (employers): standard EEO block only {g['standard EEO block only']}, "
        f"employer's own question only {g[own_key]}, both {g['both']}, not asked {g['not asked']}"
    )
    out.append(
        f"employers with an eeoc-section question: {secs['eeoc']}; with a demographic-section question: {secs['demographic']}"
    )
    print("\n".join(out))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 summarize.py SNAPSHOT.json")
    main(sys.argv[1])
