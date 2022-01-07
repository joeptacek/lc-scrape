# lc-scrape

*lc-scrape* is a utility for scraping [subject heading approved lists](https://classweb.org/approved-subjects/) from the Library of Congress (LC) website to a set of output files.

`scrape.json` represents the approved list as an array of update objects (example given below).

`tweets.json` represents the approved list as an array of Tweet threads for use with [*lc-tweet*](https://github.com/joeptacek/lc-tweet).

## Basic usage

Save `source.html`, `scrape.json`, and `tweets.json` to `output/` →

```bash
# install dependancies
pip install -r requirements.txt

# run scrape.py, providing URL and date for approved list
python scrape.py https://classweb.org/approved-subjects/2111b.html 2021-11-12
```

Works with Python 3.9, possibly other versions.

*It's plausible that lc-scrape will eventually break if LC ever changes the structure of its approved lists.*

## Output

Running `scrape.py` yields three output files, `scrape.json`, `tweets.json`, and `source.html`.

With `scrape.json`, updates are represented as objects with various properties, e.g., date, heading type (main subject headings, children's subject headings, genre/form terms, medium of performance terms, demographic group terms), update types (new heading, changed heading, cancelled heading, updated non-heading fields, updated geographic subdivisibility), etc.

LC Linked Data Service URI and LCCN Permalink are inferred from the record number assigned to the proposal.

Example update object from `scrape.json` →

```json
{
  "headingType": "mainSubjectHeadings",
  "listDate": "2021-11-12",
  "listSource": "https://classweb.org/approved-subjects/2111b.html",
  "LCLinkedDataURI": "http://id.loc.gov/authorities/subjects/sh85003553",
  "LCCNPermalink": "https://lccn.loc.gov/sh85003553",
  "approvedBeforeMeeting": false,
  "submittedByCoopLib": false,
  "statusNewHeading": false,
  "statusChangedHeading": false,
  "statusCancelledHeading": true,
  "statusUpdatedField": false,
  "statusAddedField": false,
  "statusDeletedField": false,
  "statusUpdatedGeog": false,
  "statusAddedGeog": false,
  "statusDeletedGeog": false,
  "statusChangedGeog": false,
  "lines": [
    "150 Illegal aliens CANCEL HEADING",
    "682 This authority record has been deleted because the heading is covered by the subject headings Noncitizens (DLC)sh 85003545 and Illegal immigration (DLC)sh2016000739"
  ]
}
```

Other output files →
* `tweets.json` represents updates in a format ideal for threaded display on Twitter
* `source.html` is the HTML file requested from the LC website

## Archive

This repository contains [an archive](https://github.com/joeptacek/lc-scrape/tree/master/archive) of HTML approved lists from LC, along with JSON files I've derived from these using *lc-scrape*.

To update the archive, run `scrape.py` with a new save ID as the final argument. This will save source HTML and scraped JSON to `archive/` and will append `archive/batch.json` with the latest run. By default, the corresponding Tweet thread array will be pushed to an s3 storage bucket for consumption by *lc-tweet*.

```bash
# update archive and push tweets to s3
python scrape.py https://classweb.org/approved-subjects/2111b.html 2021-11-12 0001

# can also --skip-tweets
python scrape.py https://classweb.org/approved-subjects/2111b.html 2021-11-12 0001 --skip-tweets
```

Use `--batch` to update the archive from a batch file. This will skip Tweet-related JSON.

```bash
# update archive from any batch file file, e.g., archive/batch.json
python scrape.py --batch archive/batch.json
```
