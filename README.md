# lc-scrape

lc-scrape is a utility for scraping [subject heading approved lists](https://classweb.org/approved-subjects/) from the Library of Congress (LC) website to a pair of output files.

`scrape.json` represents the approved list as an array of update objects (example given below).

`tweets.json` represents the approved list as an array Tweet threads for use with [lc-tweet](https://github.com/joeptacek/lc-tweet).

*It's quite possible lc-scrape will eventually break if LC ever changes the structure of its approved lists.*

## Usage

```bash
pip install -r requirements.txt
python scrape.py https://classweb.org/approved-subjects/2111b.html 2021-11-12
```

Works with Python 3.9, possibly other versions.

## Output

In `scrape.json`, each update is represented as an object with properties corresponding to subject heading type (main subject headings, children's subject headings, genre/form terms, medium of performance terms, demographic group terms) and types of changes approved (new heading, changed heading, cancelled heading, updated non-heading fields, updated geographic subdivisibility).

In addition, LC Linked Data Service URI and LCCN Permalink are inferred from the record number assigned to the proposal.

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

## Archive

This repository also contains an archive of the original HTML approved lists from LC, along with the representations I've derived from these using lc-scrape (i.e., `scrape.json`). These files are located in [the archive directory](https://github.com/joeptacek/lc-scrape/tree/master/archive).
