import os.path
import re
import typing as tg

usage = """Prepares files for annotation.
  Reads and converts text files such as 'abc.txt' one-by-one and writes their
  converted version to path 'outputdir/abc.txt'.
  Breaks lines after each sentence (using simple heuristics to determine
  the end of sentences) and inserts empty annotation braces {{}}
  on the next line.
"""


def configure_argparser(p_prepare_ann):
    p_prepare_ann.add_argument('outputdir',
                               help="Directory where prepared files will be placed")
    p_prepare_ann.add_argument('textfile', nargs='+',
                               help="*.txt file into which to line-split by sentence and insert empty {{}}")


def prepare_annotations(outputdir: str, inputfiles: tg.Sequence[str]):
    for inputfile in inputfiles:
        prepare_one_file(inputfile, outputdir)


def prepare_one_file(inputfile: str, outputdir: str):
    with open(inputfile, mode='rt', encoding="utf8") as f:
        inputstring = f.read()
    inputfilename = os.path.basename(inputfile)
    outputpathname = f"{outputdir}/{inputfilename}"
    if os.path.exists(outputpathname):
        print(f"#### '{outputpathname}' exists!. SKIPPED.")
        return
    print(f"---- writing '{outputpathname}'")
    with open(outputpathname, mode='wt', encoding="utf8") as f:
        f.write(prepared(inputstring))


def prepared(txt: str) -> str:
    """
    Splits into sentences and inserts '{{}}' pairs.
    Possible sentence ends are . : ? ! followed by a blank,
    but instead of a blank there can be '\n' or end-of-file.
    Replacements enforce '\n' there and another after the '{{}}'.
    """
    possible_end = r'[.:?!]\s*[ \n$]'
    result = ""
    # ----- process abstract text:
    while len(txt) > 0:
        end_match = re.search(possible_end, txt)
        if end_match:
            # print(f"## match ")  #'{end_match.group()}'")
            endpos = end_match.end()
            candidate = txt[0:endpos]
            txt = txt[endpos:]
            result += replacement_for(candidate)
        else:  # no further sentence end at all
            # print("## remainder ")
            result += replacement_for(txt)
            txt = ""
    return result


def replacement_for(candidate: str) -> str:
    result = re.sub(r"\s*$", r"", candidate)  # remove trailing whitespace
    non_sentenceends = r"e\.g\.$|i\.e\.$"
    nonend_match = re.search(non_sentenceends, result, flags=re.IGNORECASE)
    if nonend_match:
        result = candidate  # this candidate has no sentence end 
    else:
        result += "\n{{}}\n"
    # print(f"replacement_for(({candidate}))  {nonend_match and 1 or 0}==>  {result}")
    return result
