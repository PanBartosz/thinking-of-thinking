from parseQDPX import Project, Metaphor, read_qdpx_file
import argparse
from pprint import pprint, pp, pformat
import datetime
from textwrap import indent


class MetaphorComparison:
    def __init__(self, aligned_metaphor):
        self.metaphor_first = aligned_metaphor[0]
        self.metaphor_second = aligned_metaphor[1]
        self.offset_first = aligned_metaphor[2]
        self.offset_second = aligned_metaphor[3]

        self.source_domain = {"first": self.metaphor_first.info["Source"],
                              "second": self.metaphor_second.info["Source"]}

        self.target_domain = {"first": self.metaphor_first.info["Target"],
                              "second": self.metaphor_second.info["Target"]}

        self.metaphor_type = {"first": self.metaphor_first.info["Type"],
                              "second": self.metaphor_second.info["Type"]}

        self.source_domain["common"] = self.source_domain["first"] if self.source_domain[
            "first"].name == self.source_domain["second"].name else None
        self.target_domain["common"] = self.target_domain["first"] if self.target_domain[
            "first"].name == self.target_domain["second"].name else None
        self.metaphor_type["common"] = self.metaphor_type["first"] if self.metaphor_type[
            "first"].name == self.metaphor_type["second"].name else None

        self.lu_names_first = [lu.code.name for lu in self.metaphor_first.lus]
        self.lu_names_second = [
            lu.code.name for lu in self.metaphor_second.lus]
        self.lu_names_common = [
            name for name in self.lu_names_first if name in self.lu_names_second]
        aligned_lus = []
        lus_only_first = []
        lus_only_second = []

        for lu_first in self.metaphor_first.lus:
            for lu_second in self.metaphor_second.lus:
                if (lu_first.code.name == lu_second.code.name and
                    lu_first.start_pos - self.offset_first == lu_second.start_pos - self.offset_second and
                        lu_first.end_pos - self.offset_first == lu_second.end_pos - self.offset_second):
                    aligned_lus.append((lu_first, lu_second))
                    break
            else:
                print("Unmatched LU found")
                lus_only_first.append(lu_first)
        for lu_second in self.metaphor_second.lus:
            for lu_first in self.metaphor_first.lus:
                if (lu_first.code.name == lu_second.code.name and
                    lu_first.start_pos - self.offset_first == lu_second.start_pos - self.offset_second and
                        lu_first.end_pos - self.offset_first == lu_second.end_pos - self.offset_second):
                    break
            else:
                print("Unmatched LU found")
                lus_only_second.append(lu_second)

        aligned_elements = {}
        for lu_pair in aligned_lus:
            aligned_elements[lu_pair] = {
                "first": [], "second": [], "common": [], "common_names": []}
            for element_first in lu_pair[0].Elements:
                for element_second in lu_pair[1].Elements:
                    if element_first.name == element_second.name:
                        aligned_elements[lu_pair]["common"].append(
                            element_first)
                        aligned_elements[lu_pair]["common_names"].append(
                            element_first.name)
            for element_first in lu_pair[0].Elements:
                if element_first.name not in aligned_elements[lu_pair]["common_names"]:
                    aligned_elements[lu_pair]["first"].append(element_first)
            for element_second in lu_pair[1].Elements:
                if element_second.name not in aligned_elements[lu_pair]["common_names"]:
                    aligned_elements[lu_pair]["second"].append(element_second)
        self.aligned_elements = aligned_elements
        self.lus_only_first = lus_only_first
        self.lus_only_second = lus_only_second

    def __repr__(self):
        return indent(f'MetaphorComparison(source_domain={self.source_domain}, \ntarget_domain = {self.target_domain}, \nmetaphor_type = {self.metaphor_type}, \nelements = {self.aligned_elements})', "\t")


class ProjectPair:
    def __init__(self, project_first, project_second):
        self.project_first = project_first
        self.project_second = project_second
        self.sources = {}
        self.align_projects()
        self.align_sources()

    def align_projects(self):
        srcs_names_first = [
            source.name for source in self.project_first.sources]
        srcs_names_second = [
            source.name for source in self.project_second.sources]
        self.srcs_common = [
            name for name in srcs_names_first if name in srcs_names_second]
        srcs_only_first = [
            name for name in srcs_names_first if name not in srcs_names_second]
        srcs_only_second = [
            name for name in srcs_names_second if name not in srcs_names_first]
        if len(srcs_only_first) != 0 or len(srcs_only_second) != 0:
            raise Exception("Some documents are present only in one file!")

    def align_sources(self):
        for name in self.srcs_common:
            src_first = [
                source for source in self.project_first.sources if source.name == name][0]
            src_second = [
                source for source in self.project_second.sources if source.name == name][0]
            aligned_metaphors, metaphors_first, metaphors_second = self.find_matching_metaphors(
                src_first, src_second)
            self.sources[src_first] = {
                "common": [], "first": [],  "second": []}
            for aligned_metaphor in aligned_metaphors:
                self.sources[src_first]["common"].append(
                    MetaphorComparison(aligned_metaphor))
            for metaphor in metaphors_first:
                self.sources[src_first]["first"].append(metaphor)
            for metaphor in metaphors_second:
                self.sources[src_first]["second"].append(metaphor)

    def find_matching_metaphors(self, src_first, src_second):
        aligned_metaphors = []
        metaphors_first = []
        metaphors_second = []
        for metaphor_first in src_first.metaphors:
            for metaphor_second in src_second.metaphors:
                if (metaphor_first.info["Target"].name == metaphor_second.info["Target"].name or
                        metaphor_first.info["Source"].name == metaphor_second.info["Source"].name):
                    offset_first, offset_second = self.get_offsets(
                        metaphor_first, metaphor_second)
                    aligned_metaphors.append(
                        (metaphor_first, metaphor_second, offset_first, offset_second))
                    print("Found matching pair of metaphors!")
                    break
            else:
                metaphors_first.append(metaphor_first)

        for metaphor_second in src_second.metaphors:
            for metaphor_first in src_first.metaphors:
                if (metaphor_first.info["Target"].name == metaphor_second.info["Target"].name or
                        metaphor_first.info["Source"].name == metaphor_second.info["Source"].name):
                    print("Found matching pair of metaphors!")
                    break
            else:
                metaphors_second.append(metaphor_second)

        return aligned_metaphors, metaphors_first, metaphors_second

    def get_offsets(self, metaphor_first, metaphor_second):
        return (metaphor_first.span[0], metaphor_second.span[0])

    def __repr__(self):
        return indent(f'ProjectPair(Sources={self.sources})\n', "\t")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='QDPX comparator',
        description='Reads and parses two QPDX archives into structured Python object,\
             then prints its comparison')
    parser.add_argument('--path_first', '-pf')
    parser.add_argument('--path_second', '-ps')
    parser.add_argument('--lu_code_name', '-l')
    parser.add_argument('--f_code_name', '-f')
    parser.add_argument('--g_code_name', '-g')
    parser.add_argument('--table', '-t')
    parser.add_argument('--prefix', '-x')
    args = parser.parse_args()

    project_first, sources_first = read_qdpx_file(args.path_first)
    project_second, sources_second = read_qdpx_file(args.path_first)
    project_first = Project(project_first, sources_first, args.lu_code_name,
                            args.f_code_name, args.g_code_name)
    project_second = Project(project_second, sources_second, args.lu_code_name,
                             args.f_code_name, args.g_code_name)
    project_pair = ProjectPair(project_first, project_second)
    print(project_pair)
