#!/usr/bin/env python3
#
# Command Line Interface to fetch ICANN documents and open them
# from the local directories.  The Mac "open" command is used
# so that user preferences for .pdf and .htm files are honored.
# The associated .config file determines which directories are
# used to store the files.
#
# Copyright (c) 2021-2023, Vigil Security, LLC
# License: https://github.com/russhousley/icann-cli/blob/main/LICENSE
#

import os
import sys
import fnmatch
import datetime
import platform
import requests
import tempfile
import textwrap
from bs4 import BeautifulSoup

"""
Program for command-line users to access ICANN documents.
"""

__version__ = "1.02"
__license__ = "https://github.com/russhousley/icann-cli/blob/main/LICENSE"

# Version history:
#  1.00 = Initial release
#  1.01 = After cleaning up the SSAC document mirror, one routine can now
#         be used to open SSAC, RSSAC, or OCTO documents from the local
#         directories.
#  1.02 = Use python3, and adjust the use of some strings to bytes.
#         Use mode="w+" with TempFile.

def clean_html(pathname, html):
    """
    Clear away all of ICANN website decorations, leaving just the document
    """
    fout = open(pathname, mode="w")
    fout.write('<!DOCTYPE html>\n')
    fout.write('<html lang="en">\n')
    fout.write('<head>\n')
    fout.write('<meta charset="utf-8"/>\n')

    page = BeautifulSoup(html, features="lxml")
    title = page.find("title")
    titlestr = title.contents[0]
    if titlestr.endswith(" - ICANN"):
        titlestr = title.contents[0].replace(" - ICANN", "")
    fout.write('<title>' + titlestr + '</title>\n')
    fout.write('</head>\n')
    fout.write('<body>\n')
    fout.write('<div><h1>' + titlestr + '</h1></div>\n')

    date = page.find("iti-date-tag")
    if date: fout.write('<div><p>' + date.contents[0] + '</p></div>\n')
  
    for a in page.find_all("a", href=True):
        if a['href'].startswith('//'):
            a['href'] = 'https:' + a['href']
        if a['href'].startswith('/'):
            a['href'] = 'https://www.icann.org' + a['href']

    embeddedpage = page.find("div", class_="EmbeddedHTML")
    fout.write(str(embeddedpage).replace(' class="EmbeddedHTML"', '') + '\n')

    fout.write('</body>\n')
    fout.write('</html>\n')
    fout.close()


def mirror_ssac_documents():
    """
    Fetch SSAC documents from https://www.icann.org/groups/ssac/documents
    """
    # Get a temporary file to hold the index; it might be saved later
    TempFile = tempfile.TemporaryFile(mode="w+")
    TempFile.write("ICANN SSAC document index as of %s\n\n" % 
        datetime.date.today().strftime("%d-%b-%Y"))

    # Fetch the web page, then parse the table building the index as we go
    print("Starting SSAC Documents")
    response = requests.get("https://www.icann.org/groups/ssac/documents")
    if response.status_code != 200:
        sys.exit("Unable to fetch ICANN SSAC documents web page.")

    # Fix the mistakes in the table formatting
    fixup = response.content.replace(b"<td>[SAC030]", b"<tr><td>[SAC030]")
    fixup = fixup.replace(b"</a>- Executive Summary", b"- Executive Summary</a>")

    # Parse the table building the index as we go
    WriteIndexFile = False
    page = BeautifulSoup(fixup, features="lxml")
    table = page.find("table")
    for row in table.findAll("tr"):
        tds = row.findAll('td')
        if "SAC" in str(tds[0]):
            docname = str(tds[0]).split("[", 1)[1].split("]", 1)[0]
            doctitle = str(tds[1])[4:].split("<br/>")[0]
            ilines = textwrap.wrap(docname.ljust(8) + doctitle.lstrip(),
                width=73, initial_indent="", subsequent_indent="        ",
                break_long_words=False)
            for l in ilines:  TempFile.write(l + "\n")
            refs = row.find_all("a", href=True)
            onlyHTML = all([a['href'].endswith(".htm") for a in refs])
            for a in refs:
                if "Executive Summary" in a.contents[0]:
                    continue
                if a['href'].endswith("-en.pdf") or \
                    (onlyHTML and a['href'].endswith("-en.htm")) or \
                    (docname == "SAC013" and a['href'].endswith(".htm")) or \
                    (docname == "SAC007" and a['href'].endswith(".pdf")):
                    TempFile.write("        " + a['href'] + "\n")
                    filename = os.path.basename(a['href'])
                    pathname = os.path.join(SSACDir, filename)
                    url = "https://www.icann.org" + a['href']
                    if not os.path.exists(pathname):
                        response = requests.get(url)
                        if response.status_code != 200:
                            sys.stderr.write("Unable to fetch " + url + ".\n")
                        else:
                            WriteIndexFile = True
                            if a['href'].endswith(".htm"):
                                clean_html(pathname, response.content)
                            else:
                                open(pathname, mode="wb").write(response.content)
                            print(url)
                            if not filename.startswith("sac-"):
                                linkfilename = "sac-" + docname[3:]
                                if a['href'].endswith(".pdf"):
                                    linkfilename = linkfilename + "-en.pdf"
                                if a['href'].endswith(".htm"):
                                    linkfilename = linkfilename + "-en.htm"
                                linkpathname = os.path.join(SSACDir, linkfilename)
                                os.symlink(pathname, linkpathname)
                                print("  With symlink " + linkfilename)
            TempFile.write("\n")

    # If any files were fetched, save the index; also close the temporary file
    if WriteIndexFile:
        TempFile.seek(0)
        IndexFile = os.path.join(SSACDir, "sac-index.txt")
        open(IndexFile, mode="w").write(TempFile.read())

    TempFile.close()


def mirror_rssac_documents():
    """
    Fetch RSSAC documents from https://www.icann.org/groups/rssac/documents
    """
    # Get a temporary file to hold the index; it might be saved later
    TempFile = tempfile.TemporaryFile(mode="w+")
    TempFile.write("ICANN RSSAC document index as of %s\n\n" % 
        datetime.date.today().strftime("%d-%b-%Y"))

    # Fetch the web page, then parse the table building the index as we go
    print("Starting RSSAC Documents")
    response = requests.get("https://www.icann.org/groups/rssac/documents")
    if response.status_code != 200:
        sys.exit("Unable to fetch ICANN RSSAC documents web page.")

    WriteIndexFile = False
    page = BeautifulSoup(response.content, features="lxml")
    table = page.find("table")
    for row in table.findAll("tr")[1:]:
        tds = row.findAll('td')
        a = tds[0].find("a", href=True, string=True)
        filename = os.path.basename(a['href'])
        pathname = os.path.join(RSSACDir, filename)
        url = "https://www.icann.org" + a['href']
        docname = a.contents[0]
        try:
             doctitle = str(tds[1].contents[0])
        except:
             doctitle = str(tds[1].contents[0])[4:].split("<br/>")[0]
        docdate = str(tds[2].contents[0])
        ilines = textwrap.wrap(docname.ljust(11) + doctitle + " (" + docdate + ")",  
            width=73, initial_indent="", subsequent_indent="           ",
            break_long_words=False)
        for l in ilines:  TempFile.write(l + "\n")
        TempFile.write("           " + a['href'] + "\n")
        if not os.path.exists(pathname):
            response = requests.get(url)
            if response.status_code != 200:
                sys.stderr.write("Unable to fetch " + url + ".\n")
            else:
                WriteIndexFile = True
                open(pathname, mode="wb").write(response.content)
                print(url)
                if not filename.startswith("rssac-" + docname[5:].lower()):
                    linkfilename = "rssac-" + docname[5:].lower() + "-en.pdf"
                    linkpathname = os.path.join(RSSACDir, linkfilename)
                    os.symlink(pathname, linkpathname)
                    print("  With symlink " + linkfilename)
            TempFile.write("\n")

    # If any files were fetched, save the index; also close the temporary file
    if WriteIndexFile:
        TempFile.seek(0)
        IndexFile = os.path.join(RSSACDir, "rssac-index.txt")
        open(IndexFile, mode="w").write(TempFile.read())

    TempFile.close()


def mirror_octo_documents():
    """
    Fetch OCTO documents from https://www.icann.org/resources/pages/octo-publications-2019-05-24-en
    """
    # Get a temporary file to hold the index; it might be saved later
    TempFile = tempfile.TemporaryFile(mode="w+")
    TempFile.write("ICANN OCTO document index as of %s\n\n" % 
        datetime.date.today().strftime("%d-%b-%Y"))

    # Fetch the web page, then parse the table building the index as we go
    print("Starting OCTO Documents")
    response = requests.get("https://www.icann.org/resources/pages/octo-publications-2019-05-24-en")
    if response.status_code != 200:
        sys.exit("Unable to fetch ICANN OCTO documents web page.")

    WriteIndexFile = False
    page = BeautifulSoup(response.content, features="lxml")
    table = page.find("table")
    for row in table.findAll("tr")[1:]:
        tds = row.findAll('td')
        a = tds[0].find("a", href=True, string=True)
        filename = os.path.basename(a['href'])
        pathname = os.path.join(OCTODir, filename)
        url = "https://www.icann.org" + a['href']
        docname = a.contents[0]
        try:
             doctitle = str(tds[1].contents[0])
        except:
             doctitle = str(tds[1].contents[0])[4:].split("<br/>")[0]
        docdate = str(tds[2].contents[0])
        ilines = textwrap.wrap(docname.ljust(9) + doctitle + " (" + docdate + ")",  
            width=73, initial_indent="", subsequent_indent="         ",
            break_long_words=False)
        for l in ilines:  TempFile.write(l + "\n")
        TempFile.write("         " + url + "\n")
        if not os.path.exists(pathname):
            response = requests.get(url)
            if response.status_code != 200:
                sys.stderr.write("Unable to fetch " + url + ".\n")
            else:
                WriteIndexFile = True
                open(pathname, mode="wb").write(response.content)
                print(url)
        TempFile.write("\n")

    # If any files were fetched, save the index; also close the temporary file
    if WriteIndexFile:
        TempFile.seek(0)
        IndexFile = os.path.join(OCTODir, "octo-index.txt")
        open(IndexFile, mode="w").write(TempFile.read())

    TempFile.close()


def cmd_mirror():
    """
    Fetch SSAC and RSSAC and OCTO documents
    """
    mirror_ssac_documents()
    print("")
    mirror_rssac_documents()
    print("")
    mirror_octo_documents()
    print("")


def cmd_open_doc(docdir, fnprefix, num):
    """
    Open SSAC, RSSAC, or OCTO document from the local directory.
    """
    if num == 'index':
        os.system("open " + os.path.join(docdir, fnprefix + "-index.txt"))
        return

    # Check for an exact match to allow for opening a particular version
    # (like rssac-002v4-en.pdf) or multi-part documents (like sac-036b-en.pdf)
    if len(num) > 3:
        matchstr = fnprefix + "-" + num + "*.*"
        fnlist = [fn for fn in os.listdir(docdir) if fnmatch.fnmatch(fn, matchstr)]
        if len(fnlist) == 1:
            pathname = os.path.join(docdir, fnlist[0])
            os.system("open " + pathname)
        else:
            sys.exit("No published document matches %s-%s." % (fnprefix, num))

    # otherwise, assume a document number was provided
    else:
        try:
            matchstr = fnprefix + "-" + "%03d" % int(num) + "*-en.*"
        except:
            sys.exit("error: must provide a document number or 'index'")

        fnlist = [fn for fn in os.listdir(docdir) if fnmatch.fnmatch(fn, matchstr)]
        if len(fnlist) == 0:
            print("No published document for %s-%03d." % (fnprefix, int(num)))
        #  open all of the matches
        else:
            for fn in fnlist:
                pathname = os.path.join(docdir, fn)
                print("Opening " + fn)
                os.system("open " + pathname)


def usage(name):
    """
    Display usage information and then exit.
    """
    cmd_name = os.path.basename(name)
    print("commands:")
    print(cmd_name + " mirror")
    print("   fetch SSAC, RSSAC, and OCTO documents")
    print(" ")
    print(cmd_name + " ssac <num|index>")
    print("   open SSAC documents associated with num")
    print(" ")
    print(cmd_name + " rssac <num|index>")
    print("   open RSSAC documents associated with num")
    print(" ")
    print(cmd_name + " octo <num|index>")
    print("   open OCTO documents associated with num")
    print(" ")
    print("optional command arguments:")
    print("   -h, --help")
    print("                           Provides this information")
    print("   -v, --version")
    print("                           Provides the program version")


#### -------------------------------------------------------------------
#### The command line interface
#### -------------------------------------------------------------------

cmds = ['mirror', 'ssac', 'rssac', 'octo']

# Stop immediately if this is not being run on a Mac
if platform.system() != "Darwin":
    sys.exit("This program only works on a Mac. Sorry.")

# Provide help
if sys.argv[1] == 'help' or '--help' in sys.argv or '-h' in sys.argv:
    usage(sys.argv[0])
    sys.exit(1)

# Provide version
if sys.argv[1] == 'version' or '--version' in sys.argv or '-v' in sys.argv:
    print(os.path.basename(sys.argv[0]) + " " + __version__)
    sys.exit(1)

# Simple command line checks
if len(sys.argv) < 2 or sys.argv[1] not in cmds:
    print("error: first argument must be a command")
    usage(sys.argv[0])
    sys.exit(1)

# Find the config file, then execute it to set the directory names
ConfigPlaces = ("~/bin/icann.config",
                "/usr/local/bin/icann.config",
                "~/.icann/icann.config")

ConfigFile = ""
for place in ConfigPlaces:
    if os.path.exists(os.path.expanduser(place)):
        ConfigFile = os.path.expanduser(place)
        break

if ConfigFile == "":
    sys.exit("Could not find a icann.config file.")

try:
    Configs = open(ConfigFile, mode="r").read()
except:
    sys.exit("Could not open %s config file" % ConfigFile)

SSACDir = ""
RSSACDir = ""
OCTODir = ""
try:
    exec(Configs)
except:
    sys.exit("Failed during exec of %s." % ConfigFile)

if SSACDir == "":
    sys.exit("SSACDir not set by %s." % ConfigFile)

if RSSACDir == "":
    sys.exit("RSSACDir not set by %s." % ConfigFile)

if OCTODir == "":
    sys.exit("OCTODir not set by %s." % ConfigFile)

# Parse mirror arguments; then execute the command
if sys.argv[1] == 'mirror':
    if len(sys.argv) > 2:
        print("error: the mirror command does not accept arguments")
        usage(sys.argv[0])
        sys.exit(1)

    cmd_mirror()

# Parse arguments for ssac, rssac, and octo commands, then execute the command
if sys.argv[1] in ['ssac', 'rssac', 'octo']:
    if len(sys.argv) < 3:
        print("error: no document number provided")
        usage(sys.argv[0])
        sys.exit(1)

    if len(sys.argv) > 3:
        print("error: too many arguments provided")
        usage(sys.argv[0])
        sys.exit(1)

    if sys.argv[1] == 'ssac':   cmd_open_doc(SSACDir, "sac", sys.argv[2])
    if sys.argv[1] == 'rssac':  cmd_open_doc(RSSACDir, "rssac", sys.argv[2])
    if sys.argv[1] == 'octo':   cmd_open_doc(OCTODir, "octo", sys.argv[2])
