import argparse
import datetime
import uuid
from parseQDPX import read_qdpx_file
from zipfile import ZipFile, ZipInfo
from bs4 import BeautifulSoup
import time


user_guid = "DB54F35C-F8C7-4A3F-906C-074FFE27CD0F"
# We need to create a general header
header = '''GO TO
TARGET DOMAIN
SOURCE DOMAIN
METAPHOR TYPE
------------------------

'''

header_length = len(header)
# Those are start and end idices of "GO TO" string in the header, they were entered manually here
goto_start = 0
goto_end = 5

document_template = '''
<TextSource guid="{textSourceGUID}" name="{name}" creatingUser="{user_guid}" 
  plainTextPath="internal://{textSourceGUID}.txt">
<PlainTextSelection endPosition="{end_pos}" guid="{textSelectionGUID}" startPosition="{start_pos}" name="{start_pos},{end_pos}"/>
</TextSource>'''

link_template = '''
<Link originGUID="{originGUID}" name="Link" guid="{linkGUID}" targetGUID="{targetGUID}" color="#000000" direction="Associative"/>'''

users_template = '''
 <Users>
  <User name="{user}" guid="DB54F35C-F8C7-4A3F-906C-074FFE27CD0F"/>
 </Users>'''

def create_document(fragment, name):
    now = datetime.datetime.now().replace(microsecond=0).isoformat()
    userGUID = user_guid
    textSourceGUID = str(uuid.uuid4()).upper()
    textSelectionGUID = str(uuid.uuid4()).upper()
    start_pos = goto_start
    end_pos = goto_end
    name = name

    document_xml = document_template.format(
        now=now,
        userGUID=userGUID,
        textSourceGUID=textSourceGUID,
        textSelectionGUID=textSelectionGUID,
        start_pos=goto_start,
        end_pos=goto_end,
        name=name,
        user_guid = user_guid
    )
    linkGUID = str(uuid.uuid4()).upper()
    link_xml = link_template.format(
        linkGUID=linkGUID,
        originGUID=fragment["GUID"],
        targetGUID=textSelectionGUID
    )

    file = {"filename": textSourceGUID + ".txt",
            "full_text": header + fragment["full_text"]}

    return document_xml, link_xml, file


class Code:
    def __init__(self, name, guid, parent):
        self.name = name
        self.guid = guid
        self.parent = parent
        self.children = []

    def isChildOf(self, code):
        """Checks whether a code is a descendant of another code.
        """
        if self.parent:
            if code == self.parent:
                return True
            else:
                return (self.parent.isChildOf(code))
        else:
            return False

def extract_codes(project):
    codes_list = []
    all_codes = project.find("Codes")

    def search_for_codes(parent_xml, parent_code, codes_list):
        codes = parent_xml.find_all("Code", recursive=False)
        if len(codes) == 0:
            return
        for code in codes:
            c = Code(code['name'], code['guid'], parent_code)
            codes_list.append(c)
            if parent_code:
                parent_code.children.append(c)
            search_for_codes(code, c, codes_list)

    search_for_codes(all_codes, None, codes_list)
    return codes_list

def extract_fragments(project, sources, fragment_code, filename):
    codes_list = extract_codes(project)
    extraction_code = None
    for code in codes_list:
        if code.name == fragment_code:
            extraction_code = code
            break
    frags = []
    for code in extraction_code.children:
        frags.append((code.name, project.find_all(name="CodeRef", attrs={
                                 "targetGUID": code.guid})))
    extracted = []
    documents = []
    links = []
    files = []
    guids_map = {}
    for name, fragments in frags:
        for fragment in fragments:
            parent_name = fragment.parent.parent.parent["name"]
            start_position = int(fragment.parent.parent["startPosition"])
            end_position = int(fragment.parent.parent["endPosition"])
            path = fragment.parent.parent.parent["plainTextPath"].split("://")[1]
            with ZipFile(filename) as qdpx_archive:
                with qdpx_archive.open(f'sources/{path}') as text:
                    full_text  = text.read().decode()
                    if not path.split(".")[0] in guids_map:
                        new_guid = str(uuid.uuid4()).upper()
                        guids_map[path.split(".")[0]] = new_guid 
                        files.append({"filename": new_guid + ".txt", "full_text": full_text})
            extracted.append({"parent_name" : parent_name,
                            "start_position" : start_position,
                            "end_position" : end_position,
                            "GUID" : fragment.parent.parent["guid"],
                            "path" : path,
                            "full_text" : full_text[start_position:end_position],
                            "code_name" : name,
                            "source_doc_guid" : guids_map[path.split(".")[0]]
                            }
                            )
            print(full_text[start_position:end_position])
            print(fragment.parent.parent["guid"])
            print("---")


    for n, fragment in enumerate(extracted):
        document_xml, link_xml, file = create_document(
            fragment, fragment["code_name"])
        documents.append(document_xml)
        links.append(link_xml)
        files.append(file)
    project_docs = project.find_all("TextSource")
    for doc in project_docs:
        doc["creatingUser"] = user_guid
        doc["guid"] = guids_map[doc["guid"]]
        doc["plainTextPath"] = "internal://" + doc["guid"] + ".txt"
        doc["name"] = doc["name"] + " linked"
        for selection in doc.find_all("PlainTextSelection"):
            selection.clear()
            del selection["creatingUser"]
            del selection["creationDateTime"]
            del selection["modifiedDateTime"]
            del selection["modifyingUser"]
            # del selection["name"]
    documents = documents + [str(d) for d in project_docs] 
    files = [dict(t) for t in {tuple(d.items()) for d in files}]
    return documents, links, files


def make_qdpx_project(documents, links, files, output, project, user):
    documents_xml = "\n<Sources>\n" + "".join(documents) + "\n</Sources>"
    links.reverse()
    links_xml = "\n<Links>" + "".join(links) + "\n</Links>"

    project_xml = f'''<?xml version="1.0" encoding="utf-8"?>\n<Project xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:QDA-XML:project:1.0 http://schema.qdasoftware.org/versions/Project/v1.0/Project.xsd" name="imported" origin="MAXQDA 2022 (Release 22.4.0)" xmlns="urn:QDA-XML:project:1.0">''' + users_template.format(user = user) + documents_xml + links_xml + '\n</Project>'

    files.reverse()
    with ZipFile(output, "w") as qdpx_archive:
        with qdpx_archive.open('project.qde', "w") as project:
            soup = BeautifulSoup(project_xml, features="xml")
            project.write(project_xml.encode())
            print(project_xml)
        #qdpx_archive.getinfo("project.qde").external_attr = 0666 << 16
        for file in files:
            with qdpx_archive.open('sources/' + file['filename'], "w") as f:
                f.write(file["full_text"].encode())
            #qdpx_archive.getinfo("sources/" + file["filename"]).external_attr = 0666 << 16
    #f = open("fragments.qdxp", 'r')
    return qdpx_archive

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='QDPX parser',
        description='Reads and parses QPDX archive')
    parser.add_argument('--path', '-p')
    parser.add_argument('--unit-code', '-u')
    parser.add_argument('--output', '-o')

    args = parser.parse_args()

    project, sources = read_qdpx_file(args.path)

    documents, links, files, = extract_fragments(
        project, sources, args.unit_code, args.path)
    qdpx_archive = make_qdpx_project(documents, links, files, args.output, project)
