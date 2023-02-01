from zipfile import ZipFile
from bs4 import BeautifulSoup
import uuid
import datetime
import os.path
from pprint import pprint, pp, pformat
from textwrap import indent
import argparse

class Project:
    """Object containing the project read from QDPX file.

    It stores both codebook with associated codes as well as source texts and codings.

    Attributes:
        xml: xml of the project.qdp file as a BeautifulSoup objectect
        sources_raw: files associated with project sources as raw data
        sources: project sources as a list of Source objects
        codes: project codes as a list of Code objects
        codes_by_name: dictionary of codes with their names as keys
        codes_by_guid: dictionary of codes with their GUIDs as keys
    """
    def extract_sources(self):
        """Extract sources from the raw files and project data.

        Returns:
            A list containing Source objects.
        """
        sources = self.xml.find_all("TextSource")
        sources_list = []
        for source in sources:
            name = source['name']
            guid = source['guid']
            full_text = self.sources_raw[guid + '.txt']
            sources_list.append(Source(name, guid, source, full_text, self))
        return sources_list

    def extract_codes(self):
        """Extract codes from the raw files and project data. In addition to that this function also reads hierarchical structure of codes.
        Returns:
            A list containing Code objects.
        """
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

    def __init__(self, project_xml, source_files, lu_code_name = "LexicalUnit", f_code_name = "Frame", g_code_name = "Grammar"):
        """Inits Project with project_xml read from `project.qde` file and a dictionary of source files.

        Args:
            project_xml: a project.qde file compliant with REFI-QDA standard in a form of BeautifulSoup object
            source_files: dictionary with base names of the sources fils as keys and binary data as values (read from `sources` directory in a QDPX archive)
            lu_code_name = name of the code used for lexical units
            g_code_name = name of the code used for grammatical categories
            f_code_name = name of the code used for elements of scenes
        """
        self.xml = project_xml
        self.sources_raw = source_files
        self.codes = self.extract_codes()
        self.LU_CODE_NAME = lu_code_name
        self.GRAMMAR_CODE_NAME = g_code_name
        self.FRAME_CODE_NAME = f_code_name
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
    """Lexical Unit (word phrase) extracted from the source 

    Attributes:
        code: Code object assigned to the LexicalUnit
        full_text = full text of the LexicalUnit (word/pgrase)
        start_pos: start position of the lexical unit in the source file
        end_pos: end position of the lexical unit in the source file
        Elements: a list of frame elements (Code objects) associated with LexicalUnit with `Frame` as a parent node
        Grammar: a list of frame elements (Code objects) associated with LexicalUnit with `Grammar` as a parent node
    """
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
    """Representation of a metaphor found in the text.
    
    This object contains info on the metaphor (source and target scenes and metaphor typ) 
    as well as LexicalUnit(s) associated with the meraphor.
    Caution: for this to work some requirements must be met:
    - `Frame`, `Grammar` and `Lexical Unit` codes must be present in the project
    - each document must have header with TYPE, TARGET and SOURCE keywords

    Attributes:
        source: a Source document in which document was found
        span: start and end position of the unit of analysis
        lus: a list of LexicalUnit(s) associated with the metaphor
        info: a dictionary containing info on metaphor type, source and target scenes and potentially other things
    """
    def get_selection_data(self, coderef):
            selection = coderef.parent.parent
            start_pos = int(selection['startPosition'])
            end_pos = int(selection['endPosition'])
            full_text = self.source.full_text[start_pos:end_pos]
            return selection, start_pos, end_pos, full_text

    def extract_info(self):
        """Extracts general info on the metaphor. 
        
        If this function encounters a lexical unit while parsing the text, it extracts it too

        Returns:
        A dictionary with info on the metaphor. _Does not_ return LexicalUnit(s), but it extracts it and saves it in Metaphor.lus

        """
        info = {}
        coderefs = self.source.xml.find_all("CodeRef")
        if len(coderefs) == 0:
            print("ERROR")
        for coderef in coderefs:
            selection, start_pos, end_pos, full_text = self.get_selection_data(coderef)
            if not ((start_pos >= self.span[0]) and (end_pos <= self.span[1])):
                continue
            code = self.source.project.codes_by_guid[coderef['targetGUID']]
            if code.parent == self.source.project.codes_by_name[self.source.project.LU_CODE_NAME]:
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
            if code.isChildOf(self.source.project.codes_by_name[self.source.project.GRAMMAR_CODE_NAME]):
                lu.Grammar.append(code)
            if code.isChildOf(self.source.project.codes_by_name[self.source.project.FRAME_CODE_NAME]):
                lu.Elements.append(code)
        self.lus.append(lu)

    def __init__(self, source, span):
        self.source = source
        self.span = span
        self.lus = []
        self.info = self.extract_info()

    def __repr__(self):
        return indent(f'Metaphor(info={self.info}, \nlus={self.lus})\n', "\t")

def read_qdpx_file(path, lu_code_name, f_code_name, g_code_name):
    """Reads QDPX archive and return a Project object.

    Args:
        path: relative or absolute path to the QDPX archive
    Returns:
        A Project object containing parsed data from project.qde file and sources from sources directory
    """
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
        return Project(project, sources, lu_code_name, f_code_name, g_code_name)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
                    prog = 'QDPX parser',
                    description = 'Reads and parses QPDX archive into structured Python object, then prints its representation')
    parser.add_argument('--path', '-p')
    parser.add_argument('--lu_code_name', '-l')
    parser.add_argument('--f_code_name', '-f')
    parser.add_argument('--g_code_name', '-g')
    args = parser.parse_args()

    project = read_qdpx_file(args.path, args.lu_code_name, args.f_code_name, args.g_code_name)
    print(project)