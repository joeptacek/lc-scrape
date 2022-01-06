# approved subject lists here: https://classweb.org/approved-subjects/
#
# example use:
# python scrape.py https://classweb.org/approved-subjects/2111b.html 2021-11-12
#
# TODO
# save requested html as output/source.html
# automate saving output to archive
# write script for pushing tweets.json to s3 bucket
# write script for running batches from input list

import sys
from datetime import date
from pathlib import Path
import json
import re
import textwrap
import requests
from bs4 import BeautifulSoup

listSourceURL = sys.argv[1]
dateISO = sys.argv[2]
saveId = sys.argv[3] if len(sys.argv) > 3 else ""

def newUpdateObj(headingType, dateISO, listSourceURL):
    return {
        "headingType": headingType,
        "listDate": dateISO,
        "listSource": listSourceURL,
        "LCLinkedDataURI": None,
        "LCCNPermalink": None,
        "approvedBeforeMeeting": False,
        "submittedByCoopLib": False,
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

def getRecordIdApproved(recordIdProposed, currentHeadingType):
    if currentHeadingType == "mainSubjectHeadings":
        return recordIdProposed.replace("sp", "sh")
    elif currentHeadingType == "genreFormTerms":
        return recordIdProposed.replace("gp", "gf")
    elif currentHeadingType == "childrensSubjectHeadings":
        return recordIdProposed.replace("sp", "sj")
    elif currentHeadingType == "mediumOfPerformanceTerms":
        return recordIdProposed.replace("pp", "mp")
    elif currentHeadingType == "demographicGroupTerms":
        return recordIdProposed.replace("dp", "dg")

def getLCLinkedDataURI(recordIdProposed, currentHeadingType):
    recordIdApproved = getRecordIdApproved(recordIdProposed, currentHeadingType)
    if currentHeadingType == "mainSubjectHeadings":
        return "http://id.loc.gov/authorities/subjects/" + recordIdApproved
    elif currentHeadingType == "genreFormTerms":
        return "http://id.loc.gov/authorities/genreForms/" + recordIdApproved
    elif currentHeadingType == "childrensSubjectHeadings":
        return "http://id.loc.gov/authorities/childrensSubjects/" + recordIdApproved
    elif currentHeadingType == "mediumOfPerformanceTerms":
        return "http://id.loc.gov/authorities/performanceMediums/" + recordIdApproved
    elif currentHeadingType == "demographicGroupTerms":
        return "http://id.loc.gov/authorities/demographicTerms" + recordIdApproved

# LCCN Permalink not available for demographic group terms or medium of performance terms
def getLCCNPermalink(recordIdProposed, currentHeadingType):
    recordIdApproved = getRecordIdApproved(recordIdProposed, currentHeadingType)
    return "https://lccn.loc.gov/" + recordIdApproved

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

def countSpecialCharacters(string):
    return len([chr for chr in string if isSpecial(chr)])

# scrape updates from html source
def scrapeList(listSourceURL, dateISO, saveId):
    htmlText = requests.get(listSourceURL).text
    # can use local html for testing instead
    # import codecs
    # htmlText = codecs.open("./archive/html/0001--2021-11-12--2111b.html", "r", "utf-8").read()

    htmlSoup = BeautifulSoup(htmlText, 'html.parser')

    updates = []
    currentHeadingType = "mainSubjectHeadings" # LC always starts with this?
    addingUpdate = False
    for tr in htmlSoup.select("body > table > tr"):
        # detect subject heading type based on page section titles
        if "GENRE/FORM TERMS" in tr.text: currentHeadingType = "genreFormTerms"
        if "CHILDREN'S SUBJECT HEADINGS" in tr.text: currentHeadingType = "childrensSubjectHeadings"
        if "MEDIUM OF PERFORMANCE TERMS" in tr.text: currentHeadingType = "mediumOfPerformanceTerms"
        if "DEMOGRAPHIC GROUP TERMS" in tr.text: currentHeadingType = "demographicGroupTerms"

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

        if addingUpdate == False:
            if tr.select_one("table"): # beginning new update, first line (1xx)
                addingUpdate = True
                newUpdate = newUpdateObj(currentHeadingType, dateISO, listSourceURL)

                # set (A) and (C)
                if approvedBeforeMeetingLine: newUpdate["approvedBeforeMeeting"] = True
                if submittedByCoopLibLine: newUpdate["submittedByCoopLib"] = True

                fn = squashSpaces(tr.select_one("td > table > tr > td:first-child").get_text())
                fc = squashSpaces(tr.select_one("td > table > tr > td:last-child").get_text())
                if fn[0] != "1": raise Exception("Expected update to start with 1xx, instead: ", fn)
                if changeHeadingLine: # 1xx for changed heading; represents old heading
                    newUpdate["statusChangedHeading"] = True
                    newUpdate["lines"].append(fn + " " + fc)
                else: # 1xx for non-changed heading
                    if cancelHeadingLine: newUpdate["statusCancelledHeading"] = True
                    if addGeogLine or deleteGeogLine or changeGeogLine:
                        newUpdate["statusUpdatedGeog"] = True
                        if addGeogLine: newUpdate["statusAddedGeog"] = True
                        if deleteGeogLine: newUpdate["statusDeletedGeog"] = True
                        if changeGeogLine: newUpdate["statusChangedGeog"] = True
                    fcNew, recordIdProposed = extractRecordId(fc)
                    newUpdate["LCLinkedDataURI"] = getLCLinkedDataURI(recordIdProposed, currentHeadingType)
                    if currentHeadingType not in ["demographicGroupTerms", "mediumOfPerformanceTerms"]:
                        newUpdate["LCCNPermalink"] = getLCCNPermalink(recordIdProposed, currentHeadingType)
                    newUpdate["lines"].append(fn + " " + fcNew)
            else: # blank rows
                continue
        else:
            if tr.select_one("table"): # adding update lines
                fn = squashSpaces(tr.select_one("td > table > tr > td:first-child").get_text())
                fc = squashSpaces(tr.select_one("td > table > tr > td:last-child").get_text())
                if fn[0] == "1": # 1xx after changed heading; represents new heading
                    if addGeogLine or deleteGeogLine or changeGeogLine:
                        newUpdate["statusUpdatedGeog"] = True
                        if addGeogLine: newUpdate["statusAddedGeog"] = True
                        if deleteGeogLine: newUpdate["statusDeletedGeog"] = True
                        if changeGeogLine: newUpdate["statusChangedGeog"] = True
                    fcNew, recordIdProposed = extractRecordId(fc)
                    newUpdate["LCLinkedDataURI"] = getLCLinkedDataURI(recordIdProposed, currentHeadingType)
                    if currentHeadingType not in ["demographicGroupTerms", "mediumOfPerformanceTerms"]:
                        newUpdate["LCCNPermalink"] = getLCCNPermalink(recordIdProposed, currentHeadingType)
                    newUpdate["lines"].append(fn + " " + fcNew)
                else: # non-1xx update lines
                    if addFieldLine or deleteFieldLine:
                        newUpdate["statusUpdatedField"] = True
                        if addFieldLine: newUpdate["statusAddedField"] = True
                        if deleteFieldLine: newUpdate["statusDeletedField"] = True
                    newUpdate["lines"].append(fn + " " + fc)
            else:
                addingUpdate = False # done adding update
                if not (newUpdate["statusChangedHeading"] or newUpdate["statusCancelledHeading"] or newUpdate["statusUpdatedField"] or newUpdate["statusUpdatedGeog"]): newUpdate["statusNewHeading"] = True
                updates.append(newUpdate)

    if saveId:
        htmlFilename = Path(listSourceURL).stem # kind of misusing Path module, maybe

        if not Path("./archive/html/").exists(): Path("./archive/html/").mkdir(parents=True)
        with open(f"./archive/html/{saveId}--{dateISO}--{htmlFilename}.html", "w") as outfile:
            outfile.write(htmlText)

        if not Path("./archive/json/").exists(): Path("./archive/json/").mkdir(parents=True)
        with open(f"./archive/json/{saveId}--{dateISO}--{htmlFilename}.json", "w") as outfile:
            json.dump(updates, outfile, indent=2, ensure_ascii=False)
            outfile.write("\n")
    else:
        if not Path("./output/").exists(): Path("./output/").mkdir()
        with open("./output/source.html", "w") as outfile:
            outfile.write(htmlText)

        with open("./output/scrape.json", "w") as outfile:
            json.dump(updates, outfile, indent=2, ensure_ascii=False)
            outfile.write("\n")

        with open("./output/tweets.json", "w") as outfile:
            json.dump(allTweetThreads, outfile, indent=2, ensure_ascii=False)
            outfile.write("\n")


    return updates

    # NOTES RE: OBSERVED LC CONVENTIONS
    # CHANGE HEADING always on first line with old heading; update never (?) includes by ADD/DELETE FIELD; update sometimes (rarely) includes ADD/DELETE GEOG (on second with new heading)
    # CANCEL HEADING always brief
    # ADD/DELETE FIELD sometimes update also includes ADD/REMOVE GEOG
    # ADD/DELETE GEOG usually first line (unless first line contains CHANGE HEADING); sometimes (rarely) on second line if first line includes CHANGE HEADING; sometimes (rarely) update includes only ADD/DELETE GEOG with no other field updates
    # CHANGE GEOG only one of these observed? was supposed to be ADD GEOG? see https://classweb.org/approved-subjects/2101.html
    # total updates = new headings + changed headings (includes some ADD/DELETE GEOG) + cancelled headings + updated fields (includes all ADD/DELETE fields and some ADD/DELETE GEOG)

def toTwitterJSON(allUpdates):
    # generate tweet threads from updates
    allTweetThreads = []
    for update in allUpdates:
        if update["headingType"] == "mainSubjectHeadings": hashtags = "#newLCSH"
        if update["headingType"] == "genreFormTerms": hashtags = "#newLCGFT"
        if update["headingType"] == "childrensSubjectHeadings": hashtags = "#newLCSHAC"
        if update["headingType"] == "mediumOfPerformanceTerms": hashtags = "#newLCMPT"
        if update["headingType"] == "demographicGroupTerms": hashtags = "#newLCDGT"
        if update["statusNewHeading"]: hashtags += " #newHeading"
        if update["statusChangedHeading"]: hashtags += " #changedHeading"
        if update["statusCancelledHeading"]: hashtags += " #cancelledHeading"
        if update["statusUpdatedField"]: hashtags += " #updatedField"
        if update["statusUpdatedGeog"]: hashtags += " #updatedGeog"

        tweetThread = []
        tweetBody = ""
        for index, line in enumerate(update["lines"]):
            # first 1-2 heading-related lines = stanalone tweets
            if index == 0:
                tweetThread.append(f"{line}\n\n{hashtags}")
            elif index == 1 and update["statusChangedHeading"]:
                tweetThread.append(f"NEW HEADING →\n{line}")
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

        listSourceURL = update["listSource"]
        datePretty = date.fromisoformat(update["listDate"]).strftime("%b. %d, %Y").replace(" 0", " ")
        # TODO: warn re: inactive links for cancelled headings?
        if update["headingType"] not in ["demographicGroupTerms", "mediumOfPerformanceTerms"]:
            tweetThread.append(f"🗓️ Approved {datePretty} →\n{listSourceURL}\n\n🌐 LC Linked Data Service URI →\n{update['LCLinkedDataURI']}\n\n🔗 LCCN Permalink →\n{update['LCCNPermalink']}\n\n*Links might not be active for very recently approved subject headings")
        else:
            tweetThread.append(f"🗓️ Approved {datePretty} →\n{listSourceURL}\n\n🌐 LC Linked Data Service URI →\n{update['LCLinkedDataURI']}\n\n*Links might not be active for very recently approved subject headings")

        allTweetThreads.append(tweetThread)
    return allTweetThreads

def printSummary(allUpdates):
    print(
        "----------------------------------",
        "TOTAL UPDATES:                " + str(len(allUpdates)),
        "----------------------------------",
        "Approved before meeting (A):  " + str(len([update for update in allUpdates if update["approvedBeforeMeeting"]])),
        "Submitted by coop. lib. (C):  " + str(len([update for update in allUpdates if update["submittedByCoopLib"]])),
        "----------------------------------",
        "Main subject headings:        " + str(len([update for update in allUpdates if update["headingType"] == "mainSubjectHeadings"])),
        "Genre/form terms:             " + str(len([update for update in allUpdates if update["headingType"] == "genreFormTerms"])),
        "Children's subject headings:  " + str(len([update for update in allUpdates if update["headingType"] == "childrensSubjectHeadings"])),
        "Medium of performance terms:  " + str(len([update for update in allUpdates if update["headingType"] == "mediumOfPerformanceTerms"])),
        "Demographic group terms:      " + str(len([update for update in allUpdates if update["headingType"] == "demographicGroupTerms"])),
        "----------------------------------",
        "New headings:                 " + str(len([update for update in allUpdates if update["statusNewHeading"]])),
        "Changed headings:             " + str(len([update for update in allUpdates if update["statusChangedHeading"]])),
        "├──With added geog:           " + str(len([update for update in allUpdates if (update["statusAddedGeog"] and update["statusChangedHeading"])])),
        "├──With deleted geog:         " + str(len([update for update in allUpdates if (update["statusDeletedGeog"] and update["statusChangedHeading"])])),
        "└──With changed geog:         " + str(len([update for update in allUpdates if (update["statusChangedGeog"] and update["statusChangedHeading"])])),
        "Cancelled headings:           " + str(len([update for update in allUpdates if update["statusCancelledHeading"]])),
        "With other changes:           " + str(len([update for update in allUpdates if (update["statusUpdatedField"] or update["statusUpdatedGeog"] and not update["statusChangedHeading"])])),
        "├──With added field(s):       " + str(len([update for update in allUpdates if update["statusAddedField"]])),
        "├──With deleted field(s):     " + str(len([update for update in allUpdates if update["statusDeletedField"]])),
        "├──With added geog:           " + str(len([update for update in allUpdates if (update["statusAddedGeog"] and not update["statusChangedHeading"])])),
        "├──With deleted geog:         " + str(len([update for update in allUpdates if (update["statusDeletedGeog"] and not update["statusChangedHeading"])])),
        "└──With changed geog:         " + str(len([update for update in allUpdates if (update["statusChangedGeog"] and not update["statusChangedHeading"])])),
        "----------------------------------",
        sep="\n"
    )

allUpdates = scrapeList(listSourceURL, dateISO, saveId)
allTweetThreads = toTwitterJSON(allUpdates)
printSummary(allUpdates)
