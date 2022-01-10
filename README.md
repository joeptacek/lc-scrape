# lc-scrape

*lc-scrape* is a utility for scraping [subject heading approved lists](https://classweb.org/approved-subjects/) from the Library of Congress (LC) website to a set of output files →

* `source.html` contains the original HTML
* `scrape.json` contains an array of objects representing updated headings
* `tweets.json` contains an array of Tweet threads for use with [*lc-tweet*](https://github.com/joeptacek/lc-tweet)

This repository also includes [an archive](https://github.com/joeptacek/lc-scrape/tree/master/archive) of approved lists retrieved from the LC website using *lc-scrape*, both in HTML and JSON format.

## Usage

Save `source.html`, `scrape.json`, and `tweets.json` to `output/` →

```bash
# clone this repository and install python dependencies
git clone https://github.com/joeptacek/lc-scrape.git && cd lc-scrape
pip install -r requirements.txt

# scrape an approved list
python3.9 scrape.py https://classweb.org/approved-subjects/2111b.html 2021-11-12
```

*It's plausible that lc-scrape will eventually break if LC changes the structure of its approved lists.*

## Output

An example update object from `scrape.json` →

```json
{
  "headingType": "mainSubjectHeading",
  "listDate": "2021-11-12",
  "listSource": "https://classweb.org/approved-subjects/2111b.html",
  "LCLinkedDataURI": "http://id.loc.gov/authorities/subjects/sh85003553",
  "LCCNPermalink": "https://lccn.loc.gov/sh85003553",
  "statusApprovedBeforeMeeting": false,
  "statusSubmittedByCoopLib": false,
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

Possible values for `headingType` →
* `mainSubjectHeading`
* `childrensSubjectHeading`
* `genreFormTerm`
* `mediumOfPerformanceTerm`
* `demographicGroupTerm`

`LCLinkedDataURI` and `LCCNPermalink` are inferred from the record number assigned to the proposal.
