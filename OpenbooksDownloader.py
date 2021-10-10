###
#
#   IMPORTS SECTION
#
###

import requests, json, textwrap, html, os, isbnlib, statistics, subprocess, time, ebooklib
from difflib import SequenceMatcher
from ebooklib import epub 
from sys import platform

if platform == "win32":
    executable = "openbooks.exe"
else:
    executable = "./openbooks_linux"
    
lang = "en"

###
#
#   FUNCTION DEFINITIONS SECTION
#
###

def convertToISBN13(isbn):
    if(isbnlib.is_isbn10(isbn)):
        return isbnlib.to_isbn13(isbn)
    else:
        return isbn

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def clearScreen():
    os.system('cls' if os.name == 'nt' else 'clear')

def generateOverallMatch(fuzzyMatches):
    titleWeight = 1.2
    authorWeight = 1
    descWeight = 0.7
    
    totalWeights = titleWeight + authorWeight + descWeight
    
    confidence = (((fuzzyMatches[0] * titleWeight) + (fuzzyMatches[1] * authorWeight) + (fuzzyMatches[2] * descWeight)) / totalWeights)
    
    return "{:.2%}".format(confidence)

def search(targetTitle, targetAuthors):
    global executable
    print("\n\nRequesting", targetTitle, "from IRCHighway.")
    openbooksSearchReturn = subprocess.Popen([executable, "cli", "search", '"' + targetTitle + " " + targetAuthors + '"'], stdout=subprocess.PIPE)
    return openbooksSearchReturn.stdout.read().decode().split("Results location: ",1)[1].strip()

def scrapeSearchResults(openbooksSearchFile):
    validBooks = []
    for line in open(openbooksSearchFile, "r").read().split("\n"):
        if ".epub" in line:
            validBooks.append(line)
    os.remove(openbooksSearchFile)
    return validBooks

def downloadEbook(downloadCommand):
    global executable
    openbooksDownloadReturn = subprocess.Popen([executable, "cli", "download", downloadCommand], stdout=subprocess.PIPE)
    return openbooksDownloadReturn.stdout.read().decode().split("File location: ",1)[1].strip()

def fallBackToNextBook():
    global epubFileName, validBooks, downloadCommand
    if epubFileName.strip() != "":
        os.remove(epubFileName)
    validBooks.remove(downloadCommand)
    downloadCommand = min(validBooks, key=len)
    time.sleep(1)
    clearScreen()

def checkEmbeddedLanguage(book):
    if "en" in book.get_metadata('DC', 'language')[0][0] or book.get_metadata('DC', 'language')[0][0].startswith("en-"):
        return True
    else:
        return False

def prepareAndRunFuzzyMatching(targetTitle, bookTitle, targetAuthors, bookAuthors, targetDesc, bookDesc):
    fuzzyMatches = []
    fuzzyMatches.append(similar(targetTitle, bookTitle))
    fuzzyMatches.append(similar(targetAuthors, bookAuthors))
    fuzzyMatches.append(similar(targetDesc, bookDesc))
    return generateOverallMatch(fuzzyMatches)

def getTitle(data):
    return data["volumeInfo"]["title"]
    
def getDesc(data):
    return html.unescape(data["searchInfo"]["textSnippet"])
    
def getAuthors(data, separator=", "):
    return separator.join(data["volumeInfo"]["authors"])

def getPageCount(data):
    return data["volumeInfo"]["pageCount"]
    
def getLanguage(data):
    return data["volumeInfo"]["language"]
    
def getISBN(data):
    return convertToISBN13(data["volumeInfo"]["industryIdentifiers"][0]['identifier'])
 

 
###
#
#   START OF MAIN PROGRAM
#
###

searchInput = input("Enter search: ")
targetISBN = -1
response = requests.get("https://www.googleapis.com/books/v1/volumes?q=" + searchInput)
info = json.loads(response.content.decode())
clearScreen()

for volume_info in info['items']:
    try:
        print("\nTitle:", getTitle(volume_info))
        print("\nSummary:\n")
        print(textwrap.fill(getDesc(volume_info), width=65))
        print("\nAuthor(s):", getAuthors(volume_info))
        print("\nPage count:", getPageCount(volume_info))
        print("\nLanguage:", getLanguage(volume_info))
        print("\n***")
    except:
        pass  
    else:
        isCorrectBook = input("\n\nIs this your book? (y/n):")
        if isCorrectBook.lower().startswith("y"):
            targetISBN = getISBN(volume_info)
            targetTitle = getTitle(volume_info)
            targetAuthors = getAuthors(volume_info)
            targetDesc = getDesc(volume_info)
            break
        else:
            clearScreen()
    
openbooksSearchFile = search(targetTitle, targetAuthors)
clearScreen()
validBooks = scrapeSearchResults(openbooksSearchFile)
downloadCommand = min(validBooks, key=len)

while True:
    try:
        epubFileName = downloadEbook(downloadCommand)
        book = epub.read_epub(epubFileName)
    except:
        print("\n\nFAILED TO DOWNLOAD, FALLING BACK TO NEXT BOOK.")
        fallBackToNextBook()
    else:
        try:
            isbn = convertToISBN13(isbnlib.canonical(isbnlib.get_isbnlike(str(book.get_metadata('DC', 'identifier')))[0]))
            if isbn.strip() == "":
                raise 
        except:
            print("\n\nEXTRACTING METADATA FAILED, FALLING BACK TO NEXT BOOK.")
            fallBackToNextBook()
        else:
            if checkEmbeddedLanguage(book):
                if(isbn == targetISBN):
                    print("\n\n100% MATCH!")
                    break
                else:
                    response = requests.get("https://www.googleapis.com/books/v1/volumes?q=isbn:" + isbn)
                    info = json.loads(response.content.decode())
                    if info['totalItems'] != 0:
                        volume_info = info["items"][0]
                        if getLanguage(volume_info) == lang:
                            print("\n\n" + prepareAndRunFuzzyMatching(targetTitle, getTitle(volume_info), targetAuthors, getAuthors(volume_info, " "), targetDesc, getDesc(volume_info)), "MATCH!")
                            break
                        else:
                            print("\n\nBOOK DOES NOT MEET REQUIRED LANGUAGE, FALLING BACK TO NEXT BOOK.")
                            fallBackToNextBook()
                    else:
                        print("\n\nMETADATA QUERY FAILED, FALLING BACK TO NEXT BOOK.")
                        fallBackToNextBook()
            else:
                print("\n\nBOOK DOES NOT MEET REQUIRED LANGUAGE, FALLING BACK TO NEXT BOOK.")
                fallBackToNextBook()
            
            
            
            
print("\n\n***")
print("\nTitle:", getTitle(volume_info))
print("\nSummary:\n")
print(textwrap.fill(getDesc(volume_info), width=65))
print("\nAuthor(s):", getAuthors(volume_info))
print("\nPage count:", getPageCount(volume_info))
print("\nLanguage:", getLanguage(volume_info))
print("\n***")
            
            
addToCalibre = input("\n\nAdd this book to calibre? (y/n):")
if addToCalibre.lower().startswith("y"):
    subprocess.run(["calibredb", "add", epubFileName])