import json
import os.path
import typing as tg

import qabs.extract_abs as ea
import qabs.extract_concl as ec
import qscript.cmd.extract_part as ep
import qscript.cmd.prepare_ann
import qscript.metadata as metadata
import qscript

WHAT_ABSTRACT = "abstract"
WHAT_CONCLUSION = "conclusion"
meaning = "Get and prepare abstracts (after select-sample)"


def add_arguments(subparser: qscript.ArgumentParser):
    subparser.add_argument('whatpart', type=str, choices=(WHAT_ABSTRACT, WHAT_CONCLUSION),
                           help="what to extract from articles")
    subparser.add_argument('workdir', type=str,
                           help="directory where to find sample* files and where to place the 'raw' result dir")
    subparser.add_argument('--volumedir', metavar="dir", type=str, required=True,
                           help="target directory where to to find the volumes directories mentioned in 'sample.list'")
    subparser.add_argument('--remainder', action='store_true', default=False,
                           help="Silently skip existing abstracts and create any missing ones.")


def execute(args: qscript.Namespace):
    targetdir = f"{args.workdir}/raw"
    # ----- prepare directories:
    if args.remainder:
        if not os.path.exists(targetdir):
            raise ValueError(f"'{targetdir}' does not exist. Exiting.")
    else:
        if os.path.exists(targetdir):
            raise ValueError(f"'{targetdir}' already exists. I will not overwrite it. Exiting.")
        os.mkdir(targetdir)
    # ----- obtain data:
    sample = metadata.read_list(f'{args.workdir}/sample.list')
    with open(f"{args.workdir}/sample-titles.json", encoding='utf8') as f:
        titles = json.load(f)
    # ----- create abstracts files:
    for article in sample:
        prepare_article(args.whatpart, targetdir, args.volumedir, article, titles)


def prepare_article(whatpart: str, targetdir: str, volumedir: str, article: metadata.Entry,
                    titles: tg.Mapping[str, str]):
    """Extracts abstract, splits by sentence, inserts {{}}, writes to abstract file"""
    citekey = metadata.citekey(article)
    targetfile = f"{targetdir}/{citekey}.txt"
    if os.path.exists(targetfile):
        return  # we are in remaindermode: skip pre-existing file
    # ----- obtain abstract:
    print(f"{article}  \t-> {targetfile}")
    if whatpart == WHAT_ABSTRACT:
        layouttype = ep.decide_layouttype(ea.layouttypes, article)
        txt = ea.abstract_from_pdf(layouttype, f"{volumedir}/{article}")  # may not be pure
    elif whatpart == WHAT_CONCLUSION:
        layouttype = ep.decide_layouttype(ec.layouttypes, article)
        txt = ec.conclusion_from_pdf(layouttype, f"{volumedir}/{article}")  # may not be pure
    else:
        assert False
    # ----- annotate abstract and write abstract file:
    title = titles[citekey]
    annotated_txt = qscript.cmd.prepare_ann.prepared(txt)
    with open(targetfile, 'wt', encoding='utf8') as out:
        out.write(f"{title}\n\n{annotated_txt}")
        out.write("---\n")
