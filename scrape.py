# approved subject lists here: https://classweb.org/approved-subjects/
#
# example use:
# python scrape.py lcsh-html/211b.html "November 12, 2021"
# python scrape.py https://classweb.org/approved-subjects/2111b.html "November 12, 2021"

import json
import re
import textwrap
import sys
import requests
from bs4 import BeautifulSoup

# get html text from arg 1
approvalURL = sys.argv[1]
htmlText = requests.get(approvalURL).text

# todo: save html file to lcsh-html archive

# can use local html for testing instead
# import codecs
# htmlText = codecs.open(lcsh-html/2111y.html, "r", "utf-8").read()

# get date from arg 2
approvalDate = sys.argv[2]

def initNewRec(recordType):
    return {
        "recordType": recordType,
        "linkedDataURI": None,
        "statusNewHeading": False,
        "statusChangedHeading": False,
        "statusCancelledHeading": False,
        "statusUpdatedField": False,
        "statusAddedField": False,
        "statusDeletedField": False,
        "statusUpdatedGeog": False,
        "statusAddedGeog": False,
        "statusDeletedGeog": False,
        "statusChangedGeog": False,
        "lines": []
    }

def squashSpaces(s):
    return " ".join(s.split())

def extractRecordId(string):
    outputString = string
    outputRecordId = None
    pattern = r"\[(sp|gp|dp|pp).+]"
    found = re.search(pattern, string)
    if not found: raise Exception("Expected field content to contain a record ID: ", string)
    outputString = re.sub(pattern, "", string).strip()
    # remove stray spaces, opening and closing bracket
    outputRecordId = found.group().replace(" ", "")[1:-1]
    return outputString, outputRecordId

def getURI(recordIdProposed, currentRecordType):
    if currentRecordType == "mainSubjectHeadings":
        recordIdApproved = recordIdProposed.replace("sp", "sh")
        linkedDataURI = "http://id.loc.gov/authorities/subjects/" + recordIdApproved
    elif currentRecordType == "genreFormTerms":
        recordIdApproved = recordIdProposed.replace("gp", "gf")
        linkedDataURI = "http://id.loc.gov/authorities/genreForms/" + recordIdApproved
    elif currentRecordType == "childrensSubjectHeadings":
        recordIdApproved = recordIdProposed.replace("sp", "sj")
        linkedDataURI = "http://id.loc.gov/authorities/childrensSubjects/" + recordIdApproved
    elif currentRecordType == "mediumOfPerformanceTerms":
        recordIdApproved = recordIdProposed.replace("pp", "mp")
        linkedDataURI = "http://id.loc.gov/authorities/performanceMediums/" + recordIdApproved
    elif currentRecordType == "demographicGroupTerms":
        recordIdApproved = recordIdProposed.replace("dp", "dg")
        linkedDataURI = "http://id.loc.gov/authorities/demographicTerms" + recordIdApproved
    return linkedDataURI

# scrape records from htmltext
soup = BeautifulSoup(htmlText, 'html.parser')
records = []
currentRecordType = "mainSubjectHeadings" # LC always starts with this?
addingRecord = False
for tr in soup.select("body > table > tr"):
    if "GENRE/FORM TERMS" in tr.text: currentRecordType = "genreFormTerms"
    if "CHILDREN'S SUBJECT HEADINGS" in tr.text: currentRecordType = "childrensSubjectHeadings"
    if "MEDIUM OF PERFORMANCE TERMS" in tr.text: currentRecordType = "mediumOfPerformanceTerms"
    if "DEMOGRAPHIC GROUP TERMS" in tr.text: currentRecordType = "demographicGroupTerms"
    changeHeadingLine = True if "CHANGE HEADING" in tr.text else False
    cancelHeadingLine = True if "CANCEL HEADING" in tr.text else False
    addFieldLine = True if "ADD FIELD" in tr.text else False
    deleteFieldLine = True if "DELETE FIELD" in tr.text else False
    addGeogLine = True if "ADD GEOG" in tr.text else False
    deleteGeogLine = True if "DELETE GEOG" in tr.text else False
    changeGeogLine = True if "CHANGE GEOG" in tr.text else False

    if addingRecord == False:
        if tr.select_one("table"): # beginning new record, first line (1xx)
            addingRecord = True
            newRecord = initNewRec(currentRecordType)
            fn = tr.select_one("td > table > tr > td:first-child").get_text()
            fc = squashSpaces(tr.select_one("td > table > tr > td:last-child").get_text())
            if fn[0] != "1": raise Exception("Expected record to start with 1xx, instead: ", fn)
            if changeHeadingLine: # 1xx for changed heading; represents old heading
                newRecord["statusChangedHeading"] = True
                newRecord["lines"].append(fn + " " + fc)
            else: # 1xx for non-changed heading
                if cancelHeadingLine: newRecord["statusCancelledHeading"] = True
                if addGeogLine or deleteGeogLine or changeGeogLine:
                    newRecord["statusUpdatedGeog"] = True
                    if addGeogLine: newRecord["statusAddedGeog"] = True
                    if deleteGeogLine: newRecord["statusDeletedGeog"] = True
                    if changeGeogLine: newRecord["statusChangedGeog"] = True
                fcNew, recordIdProposed = extractRecordId(fc)
                linkedDataURI = getURI(recordIdProposed, currentRecordType)
                newRecord["linkedDataURI"] = linkedDataURI
                newRecord["lines"].append(fn + " " + fcNew)
        else: # blank rows
            continue
    else:
        if tr.select_one("table"): # adding record lines
            fn = tr.select_one("td > table > tr > td:first-child").get_text()
            fc = squashSpaces(tr.select_one("td > table > tr > td:last-child").get_text())
            if fn[0] == "1": # 1xx after changed heading; represents new heading
                if addGeogLine or deleteGeogLine or changeGeogLine:
                    newRecord["statusUpdatedGeog"] = True
                    if addGeogLine: newRecord["statusAddedGeog"] = True
                    if deleteGeogLine: newRecord["statusDeletedGeog"] = True
                    if changeGeogLine: newRecord["statusChangedGeog"] = True
                fcNew, recordIdProposed = extractRecordId(fc)
                linkedDataURI = getURI(recordIdProposed, currentRecordType)
                newRecord["linkedDataURI"] = linkedDataURI
                newRecord["lines"].append(fn + " " + fcNew)
            else: # non-1xx lines
                if addFieldLine or deleteFieldLine:
                    newRecord["statusUpdatedField"] = True
                    if addFieldLine: newRecord["statusAddedField"] = True
                    if deleteFieldLine: newRecord["statusDeletedField"] = True
                newRecord["lines"].append(fn + " " + fc)
        else:
            addingRecord = False # done adding record
            if not (newRecord["statusChangedHeading"] or newRecord["statusCancelledHeading"] or newRecord["statusUpdatedField"] or newRecord["statusUpdatedGeog"]): newRecord["statusNewHeading"] = True
            records.append(newRecord)

# generate tweet threads from records
allTweetThreads = []
for record in records:
    if record["recordType"] == "mainSubjectHeadings": hashtags = "#newLCSH"
    if record["recordType"] == "genreFormTerms": hashtags = "#newLCGFT"
    if record["recordType"] == "childrensSubjectHeadings": hashtags = "#newLCSHAC"
    if record["recordType"] == "mediumOfPerformanceTerms": hashtags = "#newLCMPT"
    if record["recordType"] == "demographicGroupTerms": hashtags = "#newLCDGT"
    if record["statusNewHeading"]: hashtags += " #newHeading"
    if record["statusChangedHeading"]: hashtags += " #changedHeading"
    if record["statusCancelledHeading"]: hashtags += " #cancelledHeading"
    if record["statusUpdatedField"]: hashtags += " #updatedField"
    if record["statusUpdatedGeog"]: hashtags += " #updatedGeog"

    tweetThread = []
    tweetBody = ""
    for index, line in enumerate(record["lines"]):
        if index == 0:
            tweetThread.append(f"{line}\n{hashtags}")
        elif index == 1 and record["statusChangedHeading"]:
            tweetThread.append(f"New heading →\n{line}")
        else:
            if tweetBody == "":
                tweetBody += line
            else:
                tweetBody += "\n" + line

    if tweetBody:
        tweetBodyChunks = textwrap.wrap(tweetBody, width=274, replace_whitespace=False, break_on_hyphens=False)
        if len(tweetBodyChunks) == 1:
            tweetThread.append(tweetBodyChunks[0])
        else:
            tweetThread.append(tweetBodyChunks[0] + "...")
            for chunk in tweetBodyChunks[1:-1]:
                tweetThread.append("..." + chunk + "...")
            tweetThread.append("..." + tweetBodyChunks[-1])

    tweetThread.append(f"Approved on {approvalDate} →\n{approvalURL}")

    # make sure to confirm URLs work! LC doesn't always have this ready right away
    tweetThread.append(f"LC linked data service entry →\n{record['linkedDataURI']}")

    allTweetThreads.append(tweetThread)

print(
    "----------------------------------",
    "TOTAL RECORDS:                " + str(len(records)),
    "----------------------------------",
    "Main subject headings:        " + str(len([rec for rec in records if rec["recordType"] == "mainSubjectHeadings"])),
    "Genre/form terms:             " + str(len([rec for rec in records if rec["recordType"] == "genreFormTerms"])),
    "Children's subject headings:  " + str(len([rec for rec in records if rec["recordType"] == "childrensSubjectHeadings"])),
    "Medium of performance terms:  " + str(len([rec for rec in records if rec["recordType"] == "mediumOfPerformanceTerms"])),
    "Demographic group terms:      " + str(len([rec for rec in records if rec["recordType"] == "demographicGroupTerms"])),
    "----------------------------------",
    "New headings:                 " + str(len([rec for rec in records if rec["statusNewHeading"]])),
    "Changed headings:             " + str(len([rec for rec in records if rec["statusChangedHeading"]])),
    "├──With added geog:           " + str(len([rec for rec in records if (rec["statusAddedGeog"] and rec["statusChangedHeading"])])),
    "├──With deleted geog:         " + str(len([rec for rec in records if (rec["statusDeletedGeog"] and rec["statusChangedHeading"])])),
    "└──With changed geog:         " + str(len([rec for rec in records if (rec["statusChangedGeog"] and rec["statusChangedHeading"])])),
    "Cancelled headings:           " + str(len([rec for rec in records if rec["statusCancelledHeading"]])),
    "With other changes:           " + str(len([rec for rec in records if (rec["statusUpdatedField"] or rec["statusUpdatedGeog"] and not rec["statusChangedHeading"])])),
    "├──With added field(s):       " + str(len([rec for rec in records if rec["statusAddedField"]])),
    "├──With deleted field(s):     " + str(len([rec for rec in records if rec["statusDeletedField"]])),
    "├──With added geog:           " + str(len([rec for rec in records if (rec["statusAddedGeog"] and not rec["statusChangedHeading"])])),
    "├──With deleted geog:         " + str(len([rec for rec in records if (rec["statusDeletedGeog"] and not rec["statusChangedHeading"])])),
    "└──With changed geog:         " + str(len([rec for rec in records if (rec["statusChangedGeog"] and not rec["statusChangedHeading"])])),
    "----------------------------------",
    sep="\n"
)

with open('output-scrape.json', 'w') as outfile:
    json.dump(records, outfile, indent=2, ensure_ascii=False)

with open('output-tweets.json', 'w') as outfile:
    json.dump(allTweetThreads, outfile, indent=2, ensure_ascii=False)

# CHANGE HEADING always on first line with old heading; record never (?) includes by ADD/DELETE FIELD; record sometimes (rarely) includes ADD/DELETE GEOG (on second with new heading)
# CANCEL HEADING always brief
# ADD/DELETE FIELD sometimes record also includes ADD/REMOVE GEOG
# ADD/DELETE GEOG usually first line (unless first line contains CHANGE HEADING); sometimes (rarely) on second line if first line includes CHANGE HEADING; sometimes (rarely) record includes only ADD/DELETE GEOG with no other field updates
# CHANGE GEOG only one of these observed? was supposed to be ADD GEOG? see https://classweb.org/approved-subjects/2101.html
# total records = new headings + changed headings (includes some ADD/DELETE GEOG) + cancelled headings + updated fields (includes all ADD/DELETE fields and some ADD/DELETE GEOG)
