# What job applications ask

A dated count of the questions on public job application forms, with a link to every form so each number can be checked.

## What this is

On November 16, 2026, a script read 1,297 public application forms from 171 employers that use Greenhouse, a hiring platform. It recorded every question on each form and whether an answer was required. Nothing was submitted to any employer.

## Results

| Question | Employers asking (of 171) | Answer required | Required with no decline choice |
|---|---|---|---|
| Gender | 135 (79%) | 23 | 0 |
| Sexual orientation | 36 (21%) | 8 | 0 |
| Transgender | 33 (19%) | 6 | 0 |
| Pronouns | 22 (13%) | 5 | 3 |
| Race or ethnicity | 136 (80%) | 24 | not checked |
| Veteran status | 132 (77%) | 21 | not checked |
| Disability | 46 (27%) | 15 | not checked |

Where the gender question comes from:

| Source | Employers |
|---|---|
| Greenhouse's standard US equal-employment block only | 78 |
| The employer's own question only | 25 |
| Both | 32 |
| Not asked | 36 |

Other counts:

- The median form has 17 questions. The median number of required questions is 10. The longest form has 38.
- 83 employers (49%) require a written answer in addition to a resume or cover letter.

The row for each employer is in [EMPLOYERS.md](EMPLOYERS.md).

## How to check a number

1. Open [EMPLOYERS.md](EMPLOYERS.md) and pick a row.
2. Click **form** to see the application page, or **data** to see the same questions as Greenhouse publishes them.
3. Compare what you see with the row.

Jobs close, and a closed job's links stop working. The snapshot in `data/forms-2026-11-16.json` holds the questions as they were on the day they were read.

To run the count yourself (Python 3, no packages to install):

```bash
python3 collect.py
python3 summarize.py data/forms-YYYY-MM-DD.json
```

`collect.py` writes a new snapshot named for the day you run it. Your numbers will differ somewhat from the ones above, because employers open and close jobs every day.

## Method

- **Employers.** `employers.txt` lists 179 Greenhouse job boards. They come from the author's own job search. Six boards no longer exist and two had no open jobs, which leaves 171.
- **Forms.** Up to 8 open jobs per employer, jobs with a US location first.
- **Source.** The public Greenhouse Job Board API. It needs no login and returns each form's questions with a `required` flag.
- **Matching.** A question is assigned to a topic by keywords in its text. The exact patterns are in `summarize.py`. Every matched question is listed in `data/matched-labels-2026-11-16.csv`.
- **"Asks."** At least one of the employer's sampled forms has the question.
- **"Answer required."** The form marks the question required on at least one sampled form.
- **"Decline choice."** A required question offers an answer such as "I don't wish to answer" or "Decline to self-identify." A required question with a free-text box is counted as having no decline choice.
- **"Written answer required."** A required long-text question other than a resume or cover letter.

## Limits

- **One job search.** The employers are not a sample of the whole job market.
- **One platform.** Forms on Lever, Ashby, Workday and others are not counted.
- **One day.** Forms change.
- **A sample of each employer's jobs.** An employer with more than 8 open jobs may ask a question on a form that was not read.
- **The standard block.** Greenhouse offers employers a standard set of US equal-employment questions: gender, race, veteran status and disability. Those questions are counted as asked. The gender source table above separates them from questions the employer wrote.
- **Keyword matching can be wrong.** Check `data/matched-labels-2026-11-16.csv` to see what was matched.

## Files

| File | Contents |
|---|---|
| `EMPLOYERS.md` | One row per employer, with links |
| `data/forms-2026-11-16.json` | Every question on every form read |
| `data/employers-2026-11-16.csv` | The employer table as data, with all topics |
| `data/matched-labels-2026-11-16.csv` | Every question text matched to a topic |
| `data/summary-2026-11-16.json` | The totals |
| `collect.py` | Reads the forms |
| `summarize.py` | Counts them and writes the tables |
| `employers.txt` | The job boards read |

## Corrections

If a row is wrong, open an issue with the form link.
