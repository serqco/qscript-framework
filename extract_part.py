"""framework for the concrete parts extractors extract_abs, extract_concl."""
import argparse
import os.path
import re
import typing as tg

import qscript.metadata

LayoutDescriptor = tg.Mapping[str, tg.Any]  # fixed structure per extraction task
Extractor = tg.Callable[[LayoutDescriptor, str, argparse.Namespace], str]  # returns text extracted from PDF


def is_icse_in_year(volume: str, years: tg.Set[int]) -> bool:
    """Knows which ICSE years use ACM layout (versus IEEE CS layout)."""
    path, name, year = volume_as_path_name_year(volume)
    if name != "ICSE":
        return False
    return year in years


def is_acmconf_icse(volume: str) -> bool:
    """Knows some ICSE years that use acmconf layout."""
    return is_icse_in_year(volume, {2022, 2020, 2018, 2016})


def is_ieeeconf_icse(volume: str) -> bool:
    """Knows some ICSE years that use ieeeconf layout."""
    return is_icse_in_year(volume, {2021, 2019, 2017})


def decide_layouttype(layouttypes: tg.Mapping[str, LayoutDescriptor], entry: qscript.metadata.Entry) -> LayoutDescriptor:
    volume = qscript.metadata.volume(entry)
    venue = volume_as_path_name_year(volume)[1]
    for key, descriptor in layouttypes.items():
        for candidate in descriptor['applies_to']:
            mentioned_by_name = (candidate == venue)
            matched_by_predicate = (callable(candidate) and candidate(volume))
            if mentioned_by_name or matched_by_predicate:
                return descriptor
    raise ValueError(f"cannot find layouttype for volume '{volume}'")


def extract_parts(extractor: Extractor, 
                  layouttypes: dict, layouttype: str, helper: argparse.Namespace,
                  outputdir: str, inputfile: str):
    if inputfile.endswith('.pdf'):
        layout = layouttypes[layouttype] if layouttype else decide_layouttype(layouttypes, inputfile)
        extract_part(extractor, layout, inputfile, helper, outputdir)
    elif inputfile.endswith('.list'):
        with open(inputfile, mode='rt', encoding="utf8") as f:
            inputstring = f.read()
        for inputfile in inputstring.split('\n'):
            extract_part(extractor, decide_layouttype(layouttypes, inputfile), inputfile, helper,
                         outputdir)
    else:
        print(f"'{inputfile}': unknown input file type; must be .pdf or .list")


def extract_part(extractor: Extractor, 
                 layouttype: LayoutDescriptor, pdffilepath: str, helper: argparse.Namespace,
                 outputdir: str):
    # ----- skip existing:
    pdffile = os.path.basename(pdffilepath)
    basename, suffix = os.path.splitext(pdffile)
    outputpathname = f"{outputdir}/{basename}.txt"
    if os.path.exists(outputpathname):
        print(f"#### '{outputpathname}' exists!. SKIPPED.")
        return
    # ----- obtain abstract:
    abstract = extractor(layouttype, pdffilepath, helper)
    # ----- write abstract:
    print(f"---- writing '{outputpathname}'")
    with open(outputpathname, mode='wt', encoding="utf8") as f:
        f.write(abstract)


def more_readable(txt: str) -> str:
    """Replace some special chars (such as ligatures) by more readable equivalents."""
    txt2 = txt
    txt2 = txt2.replace("ﬁ", "fi")
    txt2 = txt2.replace("ﬂ", "fl")
    return txt2


def remove_stuff(txt: str, removelist: tg.Sequence[str]) -> str:
    """Replace regexp matches (which are often whole paragraphs) by a single newline."""
    txt2 = txt
    for regexp in removelist:
        txt2 = re.sub(regexp, "\n", txt2)
    return txt2


def volume_as_path_name_year(volumepath: str) -> tg.Tuple[str, str, int]:
    volumename_regexp = r"(.+/)?([A-Za-z]+)-(\d\d\d\d)"  # {perhaps_path}/{name}-{year}
    mm = re.fullmatch(volumename_regexp, volumepath) 
    path, name, year = (mm.group(1), mm.group(2), int(mm.group(3)))
    return path, name, year