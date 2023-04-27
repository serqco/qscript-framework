import sys
import typing as tg

import qscript.annotations as annot
import qscript.color as color
import qscript.metadata
import qscript

IGNORE = annot.Codebook.IGNORECODE
meaning = """Compares annotations between coders and flags discrepancies.
  Knows about allowed and non-allowed discrepancies and
  about codes for silencing discrepancies.
  Reports problems on stdout.
"""
aliases = ["compare", "comp"]


def add_arguments(subparser: qscript.ArgumentParser):
    subparser.add_argument('workdir',
                           help="Directory where sample-who-what.txt and abstracts.?/* live")
    subparser.add_argument('--maxcountdiff', type=int, default=2, metavar="N",
                           help="how much the smaller IU count may be smaller without a message")
    subparser.add_argument('--onlyfor', type=str, metavar="codername",
                           help="Only messages for this coder will be displayed.")


def execute(args: qscript.Namespace):
    msgcount = 0
    what = qscript.metadata.WhoWhat(args.workdir)
    annots = annot.Annotations()
    print("=========================================================================================")
    print("=== check pairs of files (consult with your fellow coder except for obvious mistakes) ===")
    print("=========================================================================================")
    for coder in sorted(what.coders):
        if args.onlyfor and args.onlyfor != coder:
            continue  # suppress this block of messages
        print(f"\n\n#################### {coder}'s: ####################\n")
        for file1, coder1, file2, coder2 in what.pairs:
            if coder in (coder1, coder2):
                msgcount += compare_files(file1, coder1, file2, coder2, 
                                          what.blockname(file1), args.maxcountdiff, annots)
    msgcount = msgcount // 2      # we counted unordered pairs, so we have to undo the double counting
    msgcount = min(msgcount, 255) # avoid overflow
    sys.exit(msgcount)  # 0 if no errors, number of errors otherwise


def compare_files(file1: str, name1: str, file2: str, name2: str, 
                  block: str, maxcountdiff: int, annots: annot.Annotations) -> int:
    with open(file1, 'r', encoding='utf8') as f1:
        content1 = f1.read()
    with open(file2, 'r', encoding='utf8') as f2:
        content2 = f2.read()
    sa_pairs1 = annots.find_all_sentence_and_annotation_pairs(content1)  # list of pairs (previous sentence, annotation)
    sa_pairs2 = annots.find_all_sentence_and_annotation_pairs(content2)  # list of pairs (previous sentence, annotation)
    return compare_codings2(file1, name1, sa_pairs1, file2, name2, sa_pairs2, 
                            block, maxcountdiff, annots)


def compare_codings2(file1: str, name1: str, annotated_sentences1: tg.Sequence[annot.AnnotatedSentence],
                     file2: str, name2: str, annotated_sentences2: tg.Sequence[annot.AnnotatedSentence],
                     block: str, maxcountdiff: int, annots: annot.Annotations):
    msgcount = 0
    lastmsg = ""  # message type in last header
    extra_line_done = True  # whether one more sentence after previous problem has been shown already

    def printmsg(msg: str, *items: tg.Sequence[str]):
        """Show sentence with a problem. Suppress header if same as previous."""
        nonlocal lastmsg, extra_line_done
        if msg != lastmsg:
            print(f"\n{color.YELLOW}##### {msg}{color.RESET}")
            print(f"{color.BLUE}{file1}{color.RESET}  ({name1}, Block {block})")
            print(f"{color.BLUE}{file2}{color.RESET}  ({name2}, Block {block})")
            lastmsg = msg
        for item in items:
            print(item)
        extra_line_done = False
        return 1

    def printextra(*items: tg.Sequence[str]):
        nonlocal lastmsg, extra_line_done
        if extra_line_done:
            return  # do printextra only once between any two problems
        for item in items:
            print(item)
        extra_line_done = True

    def numbered_sentence(ann_sent: annot.AnnotatedSentence) -> str:
        return f"[{ann_sent.sentence_idx}] {color.BOLD}{ann_sent.sentence}{color.RESET}"

    def of_1(msg: str) -> str:
        return f"{color.RED}{msg}{color.RESET}  ({name1})"

    def of_2(msg: str) -> str:
        return f"{color.RED}{msg}{color.RESET}  ({name2})"

    def of_1_ok(msg: str) -> str:
        return f"{color.GREEN}{msg}{color.RESET}  -OK- ({name1})"

    def of_2_ok(msg: str) -> str:
        return f"{color.GREEN}{msg}{color.RESET}  -OK- ({name2})"

    for as1, as2 in zip(annotated_sentences1, annotated_sentences2):
        # ----- check for non-parallel codings:
        if as1.sentence != as2.sentence:
            msgcount += printmsg("Annotations should be at parallel points in the files, but are at different points here:",
                                 of_1(f"\"{as1.sentence}\""), of_2(f"\"{as2.sentence}\""))
            break
        # ----- check for incomplete annotation:
        if annots.is_empty_annotation(as1.annotation) or annots.is_empty_annotation(as2.annotation):
            msgcount += printmsg("Incomplete annotation found, skipping rest of this file pair:",
                                 numbered_sentence(as1), of_1(as1.annotation), of_2(as2.annotation))
            break
        # ----- check for double IGNORE:
        set1 = annots.codings_of(as1.annotation, strip_suffixes=True)
        set2 = annots.codings_of(as2.annotation, strip_suffixes=True)
        if IGNORE in set1 and IGNORE in set2:
            msgcount += printmsg(f"Code '{IGNORE}' should only appear in one coding, never in both as it does here:",
                                 numbered_sentence(as1), of_1(as1.annotation), of_2(as2.annotation))
            continue
        # ----- check for IGNORE:
        if IGNORE in (set1 | set2):
            continue  # do not report possible discrepancies
            # we do not check for superfluous IGNORE, because that does not scale for 
            # more than 2 columns as in prestudy2
        # ----- check for code discrepancies:
        if set1 != set2:  # code sets are different
            msgcount += printmsg(f"The sets of codes applied are different, please check:",
                                 numbered_sentence(as1), of_1(as1.annotation), of_2(as2.annotation))
            continue
        # ----- check for count discrepancies:
        countdiffs_count = 0
        for code, counts in annots.codes_with_suffixes(as1.annotation, as2.annotation).items():
            icount1, ucount1, icount2, ucount2 = counts
            idiff = abs(icount1 - icount2) > maxcountdiff
            udiff = abs(ucount1 - ucount2) > maxcountdiff
            if idiff and udiff:
                msgcount += printmsg(f"{code}: Very different numbers of i&u gaps, please reconsider:",
                                     numbered_sentence(as1), of_1(as1.annotation), of_2(as2.annotation))
                countdiffs_count += 1
            elif idiff:
                msgcount += printmsg(f"{code}: Very different numbers of informativeness gaps, please reconsider:",
                                     numbered_sentence(as1), of_1(as1.annotation), of_2(as2.annotation))
                countdiffs_count += 1
            elif udiff:
                msgcount += printmsg(f"{code}: Very different numbers of understandability gaps, please reconsider:",
                                     numbered_sentence(as1), of_1(as1.annotation), of_2(as2.annotation))
                countdiffs_count += 1
        if countdiffs_count > 0:
            continue
        printextra(numbered_sentence(as1), of_1_ok(as1.annotation), of_2_ok(as2.annotation))
    return msgcount
