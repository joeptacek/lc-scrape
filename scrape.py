# built-in modules
import codecs
import json
import re

# installed packages
import requests
from bs4 import BeautifulSoup

# optionally retrieve HTML via network request
# targetURL = "https://classweb.org/approved-subjects/2109.html"
# htmlText = requests.get(targetURL).text

# just grabbing HTML from local files for now
htmlText = codecs.open("lcsh-html/2109.html", "r", "utf-8").read()
soup = BeautifulSoup(htmlText, 'html.parser')

def initNewRec(recordType):
    return {
        "recordType": recordType,
        "heading": None,
        "headingOld": None,
        "recordIdProposed": None,
        "recordIdApproved": None,
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
        "allFields": []
    }

def squashSpaces(s):
    return " ".join(s.split())

def extractRecordId(fc):
    outputString = fc
    outputRecordId = None
    pattern = r"\[(sp|gp|dp|pp).+]"
    found = re.search(pattern, fc)
    if not found: raise Exception("Expected field content to contain a record ID: ", fc)
    outputString = re.sub(pattern, "", fc).strip()
    # remove stray spaces, opening and closing bracket
    outputRecordId = found.group().replace(" ", "")[1:-1]
    return outputString, outputRecordId

def getIdAndURI(recordIdProposed, currentRecordType):
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
    return recordIdApproved, linkedDataURI

records = []
currentRecordType = "mainSubjectHeadings" # LOC always starts with this?
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

    if addingRecord == False:
        if tr.select_one("table"): # beginning new record, first line (1xx)
            addingRecord = True
            newRecord = initNewRec(currentRecordType)
            fn = tr.select_one("td > table > tr > td:first-child").get_text()
            fc = squashSpaces(tr.select_one("td > table > tr > td:last-child").get_text())
            if fn[0] != "1": raise Exception("Expected record to start with 1xx, instead: ", fn)
            if changeHeadingLine: # 1xx for changed heading; represents old heading
                newRecord["statusChangedHeading"] = True
                newRecord["headingOld"] = fc
                newRecord["allFields"].append({"fieldNumber": fn, "fieldContent": fc, "lineLength": len(fn + fc)})
            else: # 1xx for non-changed heading
                if cancelHeadingLine: newRecord["statusCancelledHeading"] = True
                if addGeogLine or deleteGeogLine:
                    newRecord["statusUpdatedGeog"] = True
                    if addGeogLine: newRecord["statusAddedGeog"] = True
                    if deleteGeogLine: newRecord["statusDeletedGeog"] = True
                heading, recordIdProposed = extractRecordId(fc)
                recordIdApproved, linkedDataURI = getIdAndURI(recordIdProposed, currentRecordType)
                newRecord["heading"] = heading
                newRecord["recordIdProposed"] = recordIdProposed
                newRecord["recordIdApproved"] = recordIdApproved
                newRecord["linkedDataURI"] = linkedDataURI
                newRecord["allFields"].append({"fieldNumber": fn, "fieldContent": heading, "lineLength": len(fn + heading)})
        else: # blank rows
            continue
    else:
        if tr.select_one("table"): # adding record lines
            fn = tr.select_one("td > table > tr > td:first-child").get_text()
            fc = squashSpaces(tr.select_one("td > table > tr > td:last-child").get_text())
            if fn[0] == "1": # 1xx after changed heading; represents new heading
                if addGeogLine or deleteGeogLine:
                    newRecord["statusUpdatedGeog"] = True
                    if addGeogLine: newRecord["statusAddedGeog"] = True
                    if deleteGeogLine: newRecord["statusDeletedGeog"] = True
                heading, recordIdProposed = extractRecordId(fc)
                recordIdApproved, linkedDataURI = getIdAndURI(recordIdProposed, currentRecordType)
                newRecord["heading"] = heading
                newRecord["recordIdProposed"] = recordIdProposed
                newRecord["recordIdApproved"] = recordIdApproved
                newRecord["linkedDataURI"] = linkedDataURI
                newRecord["allFields"].append({"fieldNumber": fn, "fieldContent": heading, "lineLength": len(fn + heading)})
            else: # non-1xx lines
                if addFieldLine or deleteFieldLine:
                    newRecord["statusUpdatedField"] = True
                    if addFieldLine: newRecord["statusAddedField"] = True
                    if deleteFieldLine: newRecord["statusDeletedField"] = True
                newRecord["allFields"].append({"fieldNumber": fn, "fieldContent": fc, "lineLength": len(fn + fc)})
        else:
            addingRecord = False # done adding record
            if not (newRecord["statusChangedHeading"] or newRecord["statusCancelledHeading"] or newRecord["statusUpdatedField"] or newRecord["statusUpdatedGeog"]): newRecord["statusNewHeading"] = True
            records.append(newRecord)

# print(json.dumps(records, indent=2, ensure_ascii=False))
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
    "Cancelled headings:           " + str(len([rec for rec in records if rec["statusCancelledHeading"]])),
    "├──With added geog:           " + str(len([rec for rec in records if (rec["statusAddedGeog"] and rec["statusChangedHeading"])])),
    "└──With deleted geog:         " + str(len([rec for rec in records if (rec["statusDeletedGeog"] and rec["statusChangedHeading"])])),
    "With other changes:           " + str(len([rec for rec in records if (rec["statusUpdatedField"] or rec["statusUpdatedGeog"] and not rec["statusChangedHeading"])])),
    "├──With added field(s):       " + str(len([rec for rec in records if rec["statusAddedField"]])),
    "├──With deleted field(s):     " + str(len([rec for rec in records if rec["statusDeletedField"]])),
    "├──With added geog:           " + str(len([rec for rec in records if (rec["statusAddedGeog"] and not rec["statusChangedHeading"])])),
    "└──With deleted geog:         " + str(len([rec for rec in records if (rec["statusDeletedGeog"] and not rec["statusChangedHeading"])])),
    "----------------------------------",
    sep="\n"
)

with open('output.json', 'w') as outfile:
    json.dump(records, outfile, indent=2, ensure_ascii=False)

# CHANGE HEADING always on first line with old heading; record never (?) includes by ADD/DELETE FIELD; record sometimes (rarely) includes ADD/DELETE GEOG (on second with new heading)
# CANCEL HEADING always brief
# ADD/DELETE FIELD sometimes record also includes ADD/REMOVE GEOG
# ADD/DELETE GEOG usually first line (unless first line contains CHANGE HEADING); sometimes (rarely) on second line if first line includes CHANGE HEADING; sometimes (rarely) record includes only ADD/DELETE GEOG with no other field updates
# CHANGE GEOG only one of these observed? was supposed to be ADD GEOG? see https://classweb.org/approved-subjects/2101.html
# total records = new headings + changed headings (includes some ADD/DELETE GEOG) + cancelled headings + updated fields (includes all ADD/DELETE fields and some ADD/DELETE GEOG)
