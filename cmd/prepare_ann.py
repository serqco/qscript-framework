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
    txt2 = with_protection(txt)  # save non-sentence-ends from being treated like sentence ends
    result = ""
    # ----- process abstract text:
    while len(txt2) > 0:
        end_match = re.search(possible_end, txt2)
        if end_match:
            # print(f"## match ")  #'{end_match.group()}'")
            endpos = end_match.end()
            candidate = txt2[0:endpos]
            txt2 = txt2[endpos:]
            result += replacement_for(candidate)
        else:  # no further sentence end at all
            # print("## remainder ")
            result += replacement_for(txt2)
            txt2 = ""
    return unprotect(result)  # put back protected possible_ends 


protection_replacements = [('.', '\u2059'), (':', '\u205a'), ('?', '\u2056'), ('!', '\u205e'), ]


def protect(txt: str) -> str:
    """Replace characters that could indicate a sentence end by super-rare ones."""
    for char, rplcmnt in protection_replacements:
        txt = txt.replace(char, rplcmnt)
    return txt


def unprotect(txt: str) -> str:
    """Replace the replacement characters back by the original characters."""
    for char, rplcmnt in protection_replacements:
        txt = txt.replace(rplcmnt, char)
    return txt


def with_protection(txt: str) -> str:
    """
    Knows some kinds of sentence-end-lookalikes that are not really sentence ends
    and protects them by replacing the sentence-end-indicator characters by dummies.
    """
    non_sentenceends = (r"e\.g\.\s",
                        r"et ?al.\s",
                        r"https?:\s",
                        r"i\.e\.\s",
                        r"vs\.\s",
                        r"\n# \d\d?\.?\s.+(?=\n)",  # heading with dotted number or pseudo-end in title
                        )
    mark_as_sentence = (r"\n(\d\d?\.){0,3}\d\d?\.?\s.+(?=\n)",  # e.g. "2.3.4. Acro: The Design Phase!"
                        )
    result = txt
    for non_end in non_sentenceends:
        result = re.sub(non_end, lambda mm: protect(mm.group()), result)
    for sentence_structure in mark_as_sentence:
        result = re.sub(sentence_structure, lambda mm: protect(mm.group()) + ".", result)
    return result


def replacement_for(candidate: str) -> str:
    """
    Replaces a sentence by what should appear in the coding file for it:
    replaces the trailing whitespace by "\n{{}}\n".
    """
    result = re.sub(r"\s*$", r"", candidate)  # remove trailing whitespace
    return result + "\n{{}}\n"
