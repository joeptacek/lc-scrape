# lc-scrape

lc-scrape is a utility for scraping [subject heading approval lists](https://classweb.org/approved-subjects/) from the Library of Congress (LC) website to a pair of output files, `output-scrape.json` and `output-tweets.json`.

`output-scrape.json` is a basic representation of the LC approval list. I'm currently using [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) to parse the source HTML. List items are categorized according to subject heading type (main subject headings, children's subject headings, genre/form terms, medium of performance terms, demographic group terms) and according to what types of changes were approved (new heading, changed heading, cancelled heading, updated non-heading fields, updated geographic subdivisibility). An LC Linked Data Service URI is inferred from the record number assigned to the proposal.

`output-tweets.json` transforms `output-scrape.json` to a list of Tweet threads, for use with [lc-tweets](https://github.com/joeptacek/lc-tweet).

## Archive

This repository contains archived versions of the original HTML source files from LC and the JSON files I generated from them using lc-scrape—these files are located in the [archive directory](https://github.com/joeptacek/lc-scrape/tree/master/archive).

## Example usage

```bash
pip install -r requirements.txt
python scrape.py https://classweb.org/approved-subjects/2111b.html "Nov. 12, 2021"
```

Works with Python 3.9, possibly other versions.
