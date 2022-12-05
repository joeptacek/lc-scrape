# WORKFLOW
# run in venv
# source env/bin/activate

# save source.html, scrape.json, and tweets.json to output/ (confirm output looks OK)
# python scrape.py https://classweb.org/approved-subjects/2111b.html 2021-11-12

# save source and scrape to archive, push tweets to s3, save run parameters to archive/batch.json
# python scrape.py https://classweb.org/approved-subjects/2111b.html 2021-11-12 0001 --save-run

# OPTIONS
# save source and scrape to archive/, push tweets to s3 (skip batchfile update)
# python scrape.py https://classweb.org/approved-subjects/2111b.html 2021-11-12 0001

# save source and scrape to archive, skip everything related to tweets
# python scrape.py https://classweb.org/approved-subjects/2111b.html 2021-11-12 0001 --skip-tweets

# run batch job to update archive from archive/batch.json (or other batch file)
# python scrape.py --batch <optional: path/to/batch.json>

# NOTES
# approved subject lists here: https://classweb.org/approved-subjects/
# currently monitoring with Versionista
# scrape/save approved lists as they're released with IDs counting up from 0001
# ID numbering doesn't need to reflect approval date chronology, e.g., 0002--2021-11-23--2111y, 0003--2021-11-15--2111

# dates come from HTML file (manually check)
# for list dates with no day, use YYYY-MM
# python scrape.py https://classweb.org/approved-subjects/2123x.html 2022-01

# TODO
# import older lists, update numbering scheme for newer lists
# hashtags for (C) or (A)?

import sys
from datetime import date
from pathlib import Path
import json
import re
import textwrap
import requests
from bs4 import BeautifulSoup
import boto3

batchMode = True if sys.argv[1] == "--batch" else False
if batchMode:
    inputBatchPath = sys.argv[2] if len(sys.argv) > 2 else "archive/batch.json"
    inputListSourceURL = inputDateISO = inputSaveId = None
    skipTweetsMode = True
    saveRunMode = False
else:
    inputListSourceURL = sys.argv[1]
    inputDateISO = sys.argv[2]
    inputSaveId = sys.argv[3] if len(sys.argv) > 3 else None
    skipTweetsMode = True if "--skip-tweets" in sys.argv else False
    saveRunMode = True if "--save-run" in sys.argv else False

def newUpdateObj(headingType, dateISO, listSourceURL):
    return {
        "headingType": headingType,
        "listDate": dateISO,
        "listSource": listSourceURL,
        "LCLinkedDataURI": None,
        "LCCNPermalink": None,
        "statusApprovedBeforeMeeting": False,
        "statusSubmittedByCoopLib": False,
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

# removes extra spaces between words, also removes any trailing and leading spaces
def squashSpaces(s):
    return " ".join(s.split())

# strip proposal id from string, return stripped string and normalized proposal id
def stripRecordId(inputString):
    outputString = inputString # why
    outputRecordId = None
    pattern = r"\[(sp|gp|dp|pp).+]"
    found = re.search(pattern, inputString)
    if not found: raise Exception("Expected field content to contain a record ID: ", inputString)
    outputString = re.sub(pattern, "", inputString).strip()
    # remove stray spaces, opening and closing bracket
    outputRecordId = found.group().replace(" ", "")[1:-1]
    return outputString, outputRecordId

def getRecordIdApproved(recordIdProposed, currentHeadingType):
    if currentHeadingType == "mainSubjectHeading":
        return recordIdProposed.replace("sp", "sh")
    elif currentHeadingType == "genreFormTerm":
        return recordIdProposed.replace("gp", "gf")
    elif currentHeadingType == "childrensSubjectHeading":
        return recordIdProposed.replace("sp", "sj")
    elif currentHeadingType == "mediumOfPerformanceTerm":
        return recordIdProposed.replace("pp", "mp")
    elif currentHeadingType == "demographicGroupTerm":
        return recordIdProposed.replace("dp", "dg")

def getLCLinkedDataURI(recordIdProposed, currentHeadingType):
    recordIdApproved = getRecordIdApproved(recordIdProposed, currentHeadingType)
    if currentHeadingType == "mainSubjectHeading":
        return "http://id.loc.gov/authorities/subjects/" + recordIdApproved
    elif currentHeadingType == "genreFormTerm":
        return "http://id.loc.gov/authorities/genreForms/" + recordIdApproved
    elif currentHeadingType == "childrensSubjectHeading":
        return "http://id.loc.gov/authorities/childrensSubjects/" + recordIdApproved
    elif currentHeadingType == "mediumOfPerformanceTerm":
        return "http://id.loc.gov/authorities/performanceMediums/" + recordIdApproved
    elif currentHeadingType == "demographicGroupTerm":
        return "http://id.loc.gov/authorities/demographicTerms/" + recordIdApproved

# LCCN Permalink not available for demographic group terms or medium of performance terms
def getLCCNPermalink(recordIdProposed, currentHeadingType):
    recordIdApproved = getRecordIdApproved(recordIdProposed, currentHeadingType)
    return "https://lccn.loc.gov/" + recordIdApproved

def stripHeadingStatus(line):
    return line.replace("CANCEL HEADING", "").replace("CHANGE HEADING", "").strip()

def getPrettyDate(inputDate):
    if len(inputDate) == 10:
        # if YYYY-MM-DD
        return date.fromisoformat(inputDate).strftime("%b. %d, %Y").replace(" 0", " ")
    else:
        # if YYYY-MM
        dateTemp = inputDate + "-01" # python datetime can't handle YYYY-MM
        return date.fromisoformat(dateTemp).strftime("%b. %Y")

# twitter double-weights characters unless they fall in certain unicode ranges (see https://developer.twitter.com/en/docs/counting-characters)
def isSpecial(chr):
    chrVal = ord(chr)
    if (
        chrVal <= int(0x10FF)
        or (chrVal >= int(0x2000) and chrVal <= int(0x200D))
        or (chrVal >= int(0x2010) and chrVal <= int(0x201F))
        or (chrVal >= int(0x2032) and chrVal <= int(0x2037))
    ):
        # e.g., the é in café is single-weighted
        return False
    else:
        # e.g., the ṭ shṭraimels is double-weighted
        return True

def countSpecialCharacters(inputString):
    return len([chr for chr in inputString if isSpecial(chr)])

def getLongestHeading(scrapeJSON):
    maxLen, maxTxt = 0, ""
    for update in scrapeJSON:
        headerTxt = update["lines"][0]
        headerLen = len(headerTxt)
        if headerLen > maxLen:
            maxLen = headerLen
            maxTxt = headerTxt
    return maxLen, maxTxt

# scrape updates from html source
def scrapeList(listSourceURL, dateISO):
    sourceHTML = requests.get(listSourceURL).text

    # can use local html for testing instead
    # import codecs
    # sourceHTML = codecs.open("./source.html", "r", "utf-8").read()

    htmlSoup = BeautifulSoup(sourceHTML, 'html.parser')

    scrapeJSON = []
    currentHeadingType = "mainSubjectHeading" # LC always starts with this?
    addingUpdate = False

    # break html table into chunks based on blank rows
    for tr in htmlSoup.select("body > table > tr"):
        # detect subject heading type based on page section titles
        if "GENRE/FORM TERMS" in tr.text: currentHeadingType = "genreFormTerm"
        if "CHILDREN'S SUBJECT HEADINGS" in tr.text: currentHeadingType = "childrensSubjectHeading"
        if "MEDIUM OF PERFORMANCE TERMS" in tr.text: currentHeadingType = "mediumOfPerformanceTerm"
        if "DEMOGRAPHIC GROUP TERMS" in tr.text: currentHeadingType = "demographicGroupTerm"

        # detect heading, fields, geog updates
        changeHeadingLine = True if "CHANGE HEADING" in tr.text else False
        cancelHeadingLine = True if "CANCEL HEADING" in tr.text else False
        addFieldLine = True if "ADD FIELD" in tr.text else False
        deleteFieldLine = True if "DELETE FIELD" in tr.text else False
        addGeogLine = True if "ADD GEOG" in tr.text else False
        deleteGeogLine = True if "DELETE GEOG" in tr.text else False
        changeGeogLine = True if "CHANGE GEOG" in tr.text else False

        # detect (A) and (C)
        approvedBeforeMeetingLine = True if "(A)" in tr.text else False
        submittedByCoopLibLine = True if "(C)" in tr.text else False

        if not addingUpdate:
            if tr.select_one("table"): # beginning new update, first line (1xx)
                addingUpdate = True
                newUpdate = newUpdateObj(currentHeadingType, dateISO, listSourceURL)

                # set (A) and (C)
                if approvedBeforeMeetingLine: newUpdate["statusApprovedBeforeMeeting"] = True
                if submittedByCoopLibLine: newUpdate["statusSubmittedByCoopLib"] = True

                fieldNum = squashSpaces(tr.select_one("td > table > tr > td:first-child").get_text())
                fieldTxt = squashSpaces(tr.select_one("td > table > tr > td:last-child").get_text())
                if fieldNum[0] != "1": raise Exception("Expected update to start with 1xx, instead: ", fieldNum)
                if changeHeadingLine: # 1xx for changed heading; represents old heading
                    newUpdate["statusChangedHeading"] = True
                    newUpdate["lines"].append(fieldNum + " " + fieldTxt)
                else: # 1xx for non-changed heading
                    if cancelHeadingLine: newUpdate["statusCancelledHeading"] = True
                    if addGeogLine or deleteGeogLine or changeGeogLine:
                        newUpdate["statusUpdatedGeog"] = True
                        if addGeogLine: newUpdate["statusAddedGeog"] = True
                        if deleteGeogLine: newUpdate["statusDeletedGeog"] = True
                        if changeGeogLine: newUpdate["statusChangedGeog"] = True
                    fieldTxtStripped, recordIdProposed = stripRecordId(fieldTxt)
                    newUpdate["LCLinkedDataURI"] = getLCLinkedDataURI(recordIdProposed, currentHeadingType)
                    if currentHeadingType not in ["demographicGroupTerm", "mediumOfPerformanceTerm"]:
                        newUpdate["LCCNPermalink"] = getLCCNPermalink(recordIdProposed, currentHeadingType)
                    newUpdate["lines"].append(fieldNum + " " + fieldTxtStripped)
            else: # blank rows
                continue
        else:
            if tr.select_one("table"): # adding update lines
                fieldNum = squashSpaces(tr.select_one("td > table > tr > td:first-child").get_text())
                fieldTxt = squashSpaces(tr.select_one("td > table > tr > td:last-child").get_text())
                if fieldNum[0] == "1": # 1xx after changed heading; represents new heading
                    if addGeogLine or deleteGeogLine or changeGeogLine:
                        newUpdate["statusUpdatedGeog"] = True
                        if addGeogLine: newUpdate["statusAddedGeog"] = True
                        if deleteGeogLine: newUpdate["statusDeletedGeog"] = True
                        if changeGeogLine: newUpdate["statusChangedGeog"] = True
                    fieldTxtStripped, recordIdProposed = stripRecordId(fieldTxt)
                    newUpdate["LCLinkedDataURI"] = getLCLinkedDataURI(recordIdProposed, currentHeadingType)
                    if currentHeadingType not in ["demographicGroupTerm", "mediumOfPerformanceTerm"]:
                        newUpdate["LCCNPermalink"] = getLCCNPermalink(recordIdProposed, currentHeadingType)
                    newUpdate["lines"].append(fieldNum + " " + fieldTxtStripped)
                else: # non-1xx update lines
                    if addFieldLine or deleteFieldLine:
                        newUpdate["statusUpdatedField"] = True
                        if addFieldLine: newUpdate["statusAddedField"] = True
                        if deleteFieldLine: newUpdate["statusDeletedField"] = True
                    newUpdate["lines"].append(fieldNum + " " + fieldTxt)
            else: # first blank row after update
                addingUpdate = False
                if not (newUpdate["statusChangedHeading"] or newUpdate["statusCancelledHeading"] or newUpdate["statusUpdatedField"] or newUpdate["statusUpdatedGeog"]): newUpdate["statusNewHeading"] = True
                scrapeJSON.append(newUpdate)
    return scrapeJSON, sourceHTML

    # NOTES RE: OBSERVED LC CONVENTIONS
    # CHANGE HEADING always on first line with old heading; update never (?) includes by ADD/DELETE FIELD; update sometimes (rarely) includes ADD/DELETE GEOG (on second with new heading)
    # CANCEL HEADING always brief
    # ADD/DELETE FIELD sometimes update also includes ADD/REMOVE GEOG
    # ADD/DELETE/CHANGE GEOG usually first line; sometimes (rarely) on second line if first line includes CHANGE HEADING; sometimes (rarely) update includes only ADD/DELETECHANGE GEOG with no other field updates
    # total updates = new headings + changed headings (includes some ADD/DELETE/CHANGE GEOG) + cancelled headings + updated fields (includes all ADD/DELETE fields and some ADD/DELETE/CHANGE GEOG)

def toTwitterJSON(scrapeJSON):
    # generate tweet threads from updates
    tweetsJSON = []
    for update in scrapeJSON:
        if update["headingType"] == "mainSubjectHeading": hashtags = "-newLCSH"
        if update["headingType"] == "genreFormTerm": hashtags = "-newLCGFT"
        if update["headingType"] == "childrensSubjectHeading": hashtags = "-newLCSHAC"
        if update["headingType"] == "mediumOfPerformanceTerm": hashtags = "-newLCMPT"
        if update["headingType"] == "demographicGroupTerm": hashtags = "-newLCDGT"

        if update["statusNewHeading"]:
            intro = "NEW HEADING"
            hashtags += " -newHeading"

        if update["statusChangedHeading"]:
            intro = "CHANGE HEADING"
            hashtags += " -changedHeading"

        if update["statusCancelledHeading"]:
            intro = "CANCEL HEADING"
            hashtags += " -cancelledHeading"

        if update["statusUpdatedField"] or update["statusUpdatedGeog"]:
            intro = "UPDATE DETAILS" if not update["statusChangedHeading"] else "CHANGE HEADING"
            if update["statusUpdatedField"]: hashtags += " -updatedField"
            if update["statusUpdatedGeog"]: hashtags += " -updatedGeog"

        tweetThread = []
        tweetBody = ""
        for index, line in enumerate(update["lines"]):
            # first 1-2 heading-related lines = stanalone tweets
            if index == 0:
                lineStripped = stripHeadingStatus(line) if update["statusNewHeading"] or update["statusChangedHeading"] else line
                tweetThread.append(f"{intro} ⇨\n{lineStripped}\n\n{hashtags}")
            elif index == 1 and update["statusChangedHeading"]:
                tweetThread.append(f"NEW HEADING (CHANGED) →\n{line}")
            else:
                # concatenate any remaining lines as tweetBody
                if tweetBody == "":
                    tweetBody += line
                else:
                    tweetBody += "\n\n" + line

        # break tweetBody into 280-character chunks (occasionally no tweetBody due to single-line updates)
        if tweetBody:
            maxLen = 274 # 280 minus 6 for possible leading/trailing "..."

            # for Tweets containing special double-weighted characters, reduce max chunk size to accomodate
            numSpecials = countSpecialCharacters(tweetBody)
            maxLenAdjusted = maxLen - numSpecials
            tweetBodyChunks = textwrap.wrap(tweetBody, width=maxLenAdjusted, replace_whitespace=False, break_on_hyphens=False)

            if len(tweetBodyChunks) == 1:
                tweetThread.append(tweetBodyChunks[0])
            else:
                tweetThread.append(tweetBodyChunks[0] + "...")
                for chunk in tweetBodyChunks[1:-1]:
                    tweetThread.append("..." + chunk + "...")
                tweetThread.append("..." + tweetBodyChunks[-1])

        # TODO: warn re: inactive links for cancelled headings?
        datePretty = getPrettyDate(update["listDate"])
        listSourceURL = update["listSource"]
        if update["headingType"] not in ["demographicGroupTerm", "mediumOfPerformanceTerm"]:
            tweetThread.append(f"🗓️ Approved {datePretty} →\n{listSourceURL}\n\n🌐 LC Linked Data Service URI →\n{update['LCLinkedDataURI']}\n\n🔗 LCCN Permalink →\n{update['LCCNPermalink']}\n\n*Links might not be active for very recently approved subject headings")
        else:
            tweetThread.append(f"🗓️ Approved {datePretty} →\n{listSourceURL}\n\n🌐 LC Linked Data Service URI →\n{update['LCLinkedDataURI']}\n\n*Links might not be active for very recently approved subject headings")

        tweetsJSON.append(tweetThread)
    return tweetsJSON

def printSummary(scrapeJSON):
    maxLen, maxTxt = getLongestHeading(scrapeJSON)
    print(
        "",
        "-----------------------------------",
        f"TOTAL UPDATES:                {len(scrapeJSON):>5}",
        "-----------------------------------",
        f"Approved before meeting (A):  {len([update for update in scrapeJSON if update['statusApprovedBeforeMeeting']]):>5}",
        f"Submitted by coop. lib. (C):  {len([update for update in scrapeJSON if update['statusSubmittedByCoopLib']]):>5}",
        "-----------------------------------",
        f"Main subject headings:        {len([update for update in scrapeJSON if update['headingType'] == 'mainSubjectHeading']):>5}",
        f"Genre/form terms:             {len([update for update in scrapeJSON if update['headingType'] == 'genreFormTerm']):>5}",
        f"Children's subject headings:  {len([update for update in scrapeJSON if update['headingType'] == 'childrensSubjectHeading']):>5}",
        f"Medium of performance terms:  {len([update for update in scrapeJSON if update['headingType'] == 'mediumOfPerformanceTerm']):>5}",
        f"Demographic group terms:      {len([update for update in scrapeJSON if update['headingType'] == 'demographicGroupTerm']):>5}",
        "-----------------------------------",
        f"New headings:                 {len([update for update in scrapeJSON if update['statusNewHeading']]):>5}",
        f"Changed headings:             {len([update for update in scrapeJSON if update['statusChangedHeading']]):>5}",
        f"├──With added geog:           {len([update for update in scrapeJSON if (update['statusAddedGeog'] and update['statusChangedHeading'])]):>5}",
        f"├──With deleted geog:         {len([update for update in scrapeJSON if (update['statusDeletedGeog'] and update['statusChangedHeading'])]):>5}",
        f"└──With changed geog:         {len([update for update in scrapeJSON if (update['statusChangedGeog'] and update['statusChangedHeading'])]):>5}",
        f"Cancelled headings:           {len([update for update in scrapeJSON if update['statusCancelledHeading']]):>5}",
        f"Other changes:                {len([update for update in scrapeJSON if (update['statusUpdatedField'] or update['statusUpdatedGeog'] and not update['statusChangedHeading'])]):>5}",
        f"├──With added field(s):       {len([update for update in scrapeJSON if update['statusAddedField']]):>5}",
        f"├──With deleted field(s):     {len([update for update in scrapeJSON if update['statusDeletedField']]):>5}",
        f"├──With added geog:           {len([update for update in scrapeJSON if (update['statusAddedGeog'] and not update['statusChangedHeading'])]):>5}",
        f"├──With deleted geog:         {len([update for update in scrapeJSON if (update['statusDeletedGeog'] and not update['statusChangedHeading'])]):>5}",
        f"└──With changed geog:         {len([update for update in scrapeJSON if (update['statusChangedGeog'] and not update['statusChangedHeading'])]):>5}",
        "-----------------------------------",
        f"Longest heading ({maxLen} chr):",
        f"{maxTxt[:32]}...",
        "-----------------------------------",
        "",
        sep="\n"
    )

def saveFiles(listSourceURL, dateISO, saveId, scrapeJSON, sourceHTML, tweetsJSON=None):
    if saveId:
        listSourceFilename = Path(listSourceURL).stem # kind of misusing Path module, maybe
        outputFilenameHTML = f"{saveId}--{dateISO}--{listSourceFilename}" + ".html"
        outputFilenameJSON = f"{saveId}--{dateISO}--{listSourceFilename}" + ".json"

        if not Path("./archive/source/").exists(): Path("./archive/source/").mkdir(parents=True)
        with open("./archive/source/" + outputFilenameHTML, "w") as outfile:
            outfile.write(sourceHTML)

        if not Path("./archive/scrape/").exists(): Path("./archive/scrape/").mkdir(parents=True)
        with open("./archive/scrape/" + outputFilenameJSON, "w") as outfile:
            json.dump(scrapeJSON, outfile, indent=2, ensure_ascii=False)
            outfile.write("\n") # here and below: ensure newline at EOFfor POSIX compliance

        if saveRunMode:
            with open("./archive/batch.json", "r+") as batchFile:
                newRun = {
                    "id": saveId,
                    "date": dateISO,
                    "url": listSourceURL
                }

                archiveBatch = json.load(batchFile)
                archiveBatch.append(newRun)
                batchFile.seek(0)
                json.dump(archiveBatch, batchFile, indent=2)
                batchFile.write("\n")


        if not skipTweetsMode:
            s3 = boto3.resource("s3") # use AWS CLI to configure local security credentials
            tweetsObj = s3.Object("lc-new-subjects", "input/" + outputFilenameJSON)
            tweetsObj.put(Body=(json.dumps(tweetsJSON, indent=2, default=str, ensure_ascii=False)), ContentType="application/json")
            print(f"[Saved {outputFilenameJSON} to lc-new-subjects bucket]\n")
    else:
        if not Path("./output/").exists(): Path("./output/").mkdir()
        with open("./output/source.html", "w") as outfile:
            outfile.write(sourceHTML)

        with open("./output/scrape.json", "w") as outfile:
            json.dump(scrapeJSON, outfile, indent=2, ensure_ascii=False)
            outfile.write("\n")

        with open("./output/tweets.json", "w") as outfile:
            json.dump(tweetsJSON, outfile, indent=2, ensure_ascii=False)
            outfile.write("\n")

def runBatch():
    with open(inputBatchPath, "r") as infile:
        batchList = json.load(infile)

    for newRun in batchList:
        newListSourceURL = newRun["url"]
        newDateISO = newRun["date"]
        newSaveId = newRun["id"]

        scrapeJSON, sourceHTML = scrapeList(newListSourceURL, newDateISO)
        saveFiles(newListSourceURL, newDateISO, newSaveId, scrapeJSON, sourceHTML, tweetsJSON=None)
        # printSummary(scrapeJSON)

        listSourceFilename = Path(newListSourceURL).stem
        print(f"Done: {newSaveId}--{newDateISO}--{listSourceFilename}")

def runSingle():
    scrapeJSON, sourceHTML = scrapeList(inputListSourceURL, inputDateISO)
    printSummary(scrapeJSON)

    tweetsJSON = toTwitterJSON(scrapeJSON) if not skipTweetsMode else None
    saveFiles(inputListSourceURL, inputDateISO, inputSaveId, scrapeJSON, sourceHTML, tweetsJSON)

runBatch() if batchMode else runSingle()
