import codecs
import requests
import json
from bs4 import BeautifulSoup

# targetURL = "https://classweb.org/approved-subjects/2109.html"
# htmlText = requests.get(targetURL).text

htmlText = codecs.open("2109.html", "r", "utf-8").read()
soup = BeautifulSoup(htmlText, 'html.parser')

def initNewRec(fn, fc):
    initializedRec = {"heading": fc, "fieldList": []}
    initializedRec["fieldList"].append({"fieldNumber": fn, "fieldContent": fc})
    return initializedRec

def squashSpaces(s):
    return " ".join(s.split())

records = {
    "mainHeadings": [],
    "genreFormTerms": [],
    "childrensSubjectHeadings": [],
    "mediumOfPerformanceTerms": [],
    "demographicGroupTerms": []
}

firstHeading = True
targetList = "mainHeadings"
nextTargetList = ""
changeHeading = False
for tr in soup.select("table > tr > td"): # iterate through all the table rows
    # print(tr)

    # watch for major headings
    if "GENRE/FORM TERMS" in tr.text: nextTargetList = "genreFormTerms"
    if "CHILDREN'S SUBJECT HEADINGS" in tr.text: nextTargetList = "childrensSubjectHeadings"
    if "MEDIUM OF PERFORMANCE TERMS" in tr.text: nextTargetList = "mediumOfPerformanceTerms"
    if "DEMOGRAPHIC GROUP TERMS" in tr.text: nextTargetList = "demographicGroupTerms"

    if tr.select_one("table"): # focus on the table rows containing sub-tables
        fn = tr.select_one("table > tr > td:first-child").get_text()
        fc = squashSpaces(tr.select_one("table > tr > td:last-child").get_text())
        if fn[0] == "1":
            if "CHANGE HEADING" in tr.text: changeHeading = True
            if firstHeading:
                newRecord = initNewRec(fn, fc)
                firstHeading = False
            else:
                records[targetList].append(newRecord)
                if nextTargetList: targetList = nextTargetList
                newRecord = initNewRec(fn, fc)
        else:
            newRecord["fieldList"].append({"fieldNumber": fn, "fieldContent": fc})

records[targetList].append(newRecord) # last rec
print(json.dumps(records, indent=2, ensure_ascii=False))

with open('output.json', 'w') as outfile:
    json.dump(records, outfile, indent=2, ensure_ascii=False)
