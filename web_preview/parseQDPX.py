from zipfile import ZipFile
from bs4 import BeautifulSoup
import uuid
import datetime
import os.path
from pprint import pprint, pp, pformat
from textwrap import indent

class Project:
    def extract_sources(self):
        sources = self.xml.find_all("TextSource")
        sources_list = []
        for source in sources:
            name = source['name']
            guid = source['guid']
            full_text = self.sources_raw[guid + '.txt']
            sources_list.append(Source(name, guid, source, full_text, self))
        return sources_list

    def extract_codes(self):
        codes_list = []
        all_codes = self.xml.find("Codes")
        def search_for_codes(parent_xml, parent_code, codes_list):
            codes = parent_xml.find_all("Code", recursive = False)
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

    def __init__(self, project_xml, source_files):
        self.xml = project_xml
        self.sources_raw = source_files
        self.codes = self.extract_codes()
        # We need to extract metaphors by one specific code
        for code in self.codes:
            if code.name == "Unit":
                self.unit_code = code
        self.codes_by_name = {}
        self.codes_by_guid = {}
        for code in self.codes:
            self.codes_by_name[code.name] = code
            self.codes_by_guid[code.guid] = code
        self.sources = self.extract_sources()
    def __repr__(self):
        return indent(f'Project(Codes={self.codes}, \nSources={self.sources})\n', "\t")


class Code:
    def __init__(self, name, guid, parent):
        self.name = name
        self.guid = guid
        self.parent = parent
        self.children = []

    def isChildOf(self, code):
        if self.parent:
            if code == self.parent:
                return True
            else:
                return(self.parent.isChildOf(code))
        else:
            return False

    def __repr__(self):
        return indent(f'Code(name={self.name})', "")

class Source:
    def extract_metaphors(self, unit_code):
        metaphors = []
        selections = self.xml.find_all("PlainTextSelection")
        for selection in selections:
            span = (int(selection['startPosition']), int(selection['endPosition']))
            coderef = selection.find_all("CodeRef")
            if len(coderef) == 0:
                continue
            if coderef[0]['targetGUID'] == unit_code.guid:
                print(f"Unit identified in {self.name}")
                metaphors.append(Metaphor(self, span))
        return metaphors

    def __init__(self, name, guid, xml, full_text, project):
        self.name = name
        self.guid = guid
        self.xml = xml
        self.full_text = full_text.decode()
        self.project = project
        self.metaphors = self.extract_metaphors(self.project.unit_code)

    def __repr__(self):
        return indent(f'Source(name={self.name}, \nmetaphors={self.metaphors})\n', "\t")


class LexicalUnit:
    def __init__(self, code, s_pos, e_pos, full_text):
        self.code = code
        self.start_pos = s_pos
        self.end_pos = e_pos
        self.full_text = full_text
        self.Elements = []
        self.Grammar = []

    def __repr__(self):
        return f'LexicalUnit(text={self.full_text}, \ncode={self.code.name}, \nelements={self.Elements}, \ngrammar={self.Grammar})\n'

class Metaphor:
    def get_selection_data(self, coderef):
            selection = coderef.parent.parent
            start_pos = int(selection['startPosition'])
            end_pos = int(selection['endPosition'])
            full_text = self.source.full_text[start_pos:end_pos]
            return selection, start_pos, end_pos, full_text

    def extract_info(self):
        info = {}
        coderefs = self.source.xml.find_all("CodeRef")
        if len(coderefs) == 0:
            print("ERROR")
        for coderef in coderefs:
            selection, start_pos, end_pos, full_text = self.get_selection_data(coderef)
            if not ((start_pos >= self.span[0]) and (end_pos <= self.span[1])):
                continue
            code = self.source.project.codes_by_guid[coderef['targetGUID']]
            if code.parent == self.source.project.codes_by_name["Lexical Unit"]:
                self.extract_lu(code, start_pos, end_pos, full_text)
            if full_text == "TYPE":
               info["Type"] = code
            if full_text == "TARGET":
                info["Target"] = code
            if full_text == "SOURCE":
                info["Source"] = code
        return info


    def extract_lu(self, code, s_pos, e_pos, full_text):
        coderefs = self.source.xml.find_all("CodeRef")
        lu = LexicalUnit(code, s_pos, e_pos, full_text)
        if len(coderefs) == 0:
            print("ERROR")
        for coderef in coderefs:
            selection, start_pos, end_pos, full_text = self.get_selection_data(coderef)
            if full_text != lu.full_text:
                continue
            code = self.source.project.codes_by_guid[coderef['targetGUID']]
            if code.isChildOf(self.source.project.codes_by_name['Grammar']):
                lu.Grammar.append(code)
            if code.isChildOf(self.source.project.codes_by_name['Frame']):
                lu.Elements.append(code)
        self.lus.append(lu)

    def __init__(self, source, span):
        self.source = source
        self.span = span
        self.lus = []
        self.info = self.extract_info()

    def __repr__(self):
        return indent(f'Metaphor(info={self.info}, \nlus={self.lus})\n', "\t")

def read_qdpx_file(path):
    with ZipFile(path) as qdpx_archive:
        with qdpx_archive.open('project.qde') as project:
            project_file = project.read()
            project = BeautifulSoup(project_file, features="xml")
        sources = {}
        for f in qdpx_archive.infolist():
            if f.filename.startswith("sources"):
                fpath = f.filename
                basename = os.path.basename(fpath)
                with qdpx_archive.open(fpath) as source:
                    sources[basename] = source.read()
        return Project(project, sources)

#project = read_qdpx_file("DeCuriositate 3-4_Orestis.qdpx")