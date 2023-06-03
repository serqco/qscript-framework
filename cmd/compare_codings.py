import dataclasses
import sys
import typing as tg

import qscript.annotations as annot
import qscript.color as color
import qscript.icc as icc
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
                           help="Directory where sample-who-what.txt and extracts subdirectories live")
    subparser.add_argument('--maxcountdiff', type=int, default=2, metavar="N",
                           help="how much the smaller IU count may be smaller without a message")
    subparser.add_argument('--onlyfor', type=str, metavar="codername",
                           help="Only messages for this coder will be displayed.")


def execute(args: qscript.Namespace):
    what = qscript.metadata.WhoWhat(args.workdir)
    annots = icc.init(annot.Annotations)
    comparator = icc.init(CodingsComparator)
    print("=========================================================================================")
    print("=== check pairs of files (consult with your fellow coder except for obvious mistakes) ===")
    print("=========================================================================================")
    for coder in sorted(what.coders):
        if args.onlyfor and args.onlyfor != coder:
            continue  # suppress this block of messages
        print(f"\n\n#################### {coder}'s: ####################\n")
        for file1, coder1, file2, coder2 in what.pairs:
            if coder in (coder1, coder2):
                ctx = ComparatorContext(file1, coder1, file2, coder2, what.blockname(file1))
                comparator.compare_files(ctx, args.maxcountdiff, annots)
    sys.exit(comparator.get_exitcode())  # 0 if no errors, number of errors otherwise


@dataclasses.dataclass
class ComparatorContext:
    file1: str
    name1: str
    file2: str
    name2: str
    block: str


class CodingsComparator:
    def __init__(self):
        self.msgcount = 0
        self.lastmsg = ""   # message type in last header
        self.extra_line_done = True  # whether one more sentence after previous problem has been shown already

    def get_exitcode(self) -> int:
        msgcount = self.msgcount // 2  # we counted unordered pairs, so we have to undo the double counting
        return min(msgcount, 255)  # avoid overflow
        
    def compare_files(self, ctx: ComparatorContext, 
                      maxcountdiff: int, annots: annot.Annotations):
        with open(ctx.file1, 'r', encoding='utf8') as f1:
            content1 = f1.read()
        with open(ctx.file2, 'r', encoding='utf8') as f2:
            content2 = f2.read()
        sa_pairs1 = annots.find_all_sentence_and_annotation_pairs(content1)  # list of (previous sentence, annotation)
        sa_pairs2 = annots.find_all_sentence_and_annotation_pairs(content2)  # list of (previous sentence, annotation)
        self.compare_codings2(ctx, sa_pairs1, sa_pairs2, maxcountdiff, annots)
    
    def compare_codings2(self, ctx: ComparatorContext, 
                         annotated_sentences1: tg.Sequence[annot.AnnotatedSentence],
                         annotated_sentences2: tg.Sequence[annot.AnnotatedSentence],
                         maxcountdiff: int, annots: annot.Annotations):
        self.lastmsg = ""  # message type in last header
        self.extra_line_done = True  # whether one more sentence after previous problem has been shown already
    
        for as1, as2 in zip(annotated_sentences1, annotated_sentences2):
            # ----- check for non-parallel codings:
            if as1.sentence != as2.sentence:
                should_msg = "Annotations should be at parallel points in the files"
                self._printmsg(ctx, f"{should_msg}, but are at different points here:",
                               self._of_1(ctx, f"\"{as1.sentence}\""), self._of_2(ctx, f"\"{as2.sentence}\""))
                break
            # ----- check for incomplete annotation:
            if annots.is_empty_annotation(as1.annotation) or annots.is_empty_annotation(as2.annotation):
                self._printmsg(ctx, "Incomplete annotation found, skipping rest of this file pair:",
                               self._numbered_sentence(as1), 
                               self._of_1(ctx, as1.annotation), self._of_2(ctx, as2.annotation))
                break
            # ----- check for double IGNORE:
            set1 = annots.codings_of(as1.annotation, strip_suffixes=True, strip_subjective=True)
            set2 = annots.codings_of(as2.annotation, strip_suffixes=True, strip_subjective=True)
            if IGNORE in set1 and IGNORE in set2:
                self._printmsg(ctx, f"Code '{IGNORE}' should only appear in one coding, never in both as it does here:",
                               self._numbered_sentence(as1), 
                               self._of_1(ctx, as1.annotation), self._of_2(ctx, as2.annotation))
                continue
            # ----- check for IGNORE:
            if IGNORE in (set1 | set2):
                continue  # do not report possible discrepancies
                # we do not check for superfluous IGNORE, because that does not scale for 
                # more than 2 columns as in prestudy2
            # ----- check for code discrepancies:
            if set1 != set2:  # code sets are different
                self._printmsg(ctx, f"The sets of codes applied are different, please check:",
                               self._numbered_sentence(as1), 
                               self._of_1(ctx, as1.annotation), self._of_2(ctx, as2.annotation))
                continue
            # ----- check for count discrepancies:
            old_msgcount = self.msgcount
            self.check_suffixes(annots, as1, as2, ctx, maxcountdiff)
            if self.msgcount - old_msgcount > 0:
                continue
            self._printextra(self._numbered_sentence(as1), 
                             self._of_1_ok(ctx, as1.annotation), self._of_2_ok(ctx, as2.annotation))

    def check_suffixes(self, annots, as1, as2, ctx, maxcountdiff):
        for code, counts in annots.codes_with_iucounts(as1.annotation, as2.annotation).items():
            icount1, ucount1, icount2, ucount2 = counts
            idiff = abs(icount1 - icount2) > maxcountdiff
            udiff = abs(ucount1 - ucount2) > maxcountdiff
            if idiff and udiff:
                self._printmsg(ctx, f"{code}: Very different numbers of i&u gaps, please reconsider:",
                               self._numbered_sentence(as1),
                               self._of_1(ctx, as1.annotation), self._of_2(ctx, as2.annotation))
            elif idiff:
                self._printmsg(ctx, f"{code}: Very different numbers of informativeness gaps, please reconsider:",
                               self._numbered_sentence(as1),
                               self._of_1(ctx, as1.annotation), self._of_2(ctx, as2.annotation))
            elif udiff:
                self._printmsg(ctx, f"{code}: Very different numbers of understandability gaps, please reconsider:",
                               self._numbered_sentence(as1),
                               self._of_1(ctx, as1.annotation), self._of_2(ctx, as2.annotation))

    def _printmsg(self, ctx: ComparatorContext, msg: str, *items: tg.Sequence[str]):
        """Show sentence with a problem. Suppress header if same as previous."""
        if msg != self.lastmsg:
            print(f"\n{color.YELLOW}##### {msg}{color.RESET}")
            print(f"{color.BLUE}{ctx.file1}{color.RESET}  ({ctx.name1}, Block {ctx.block})")
            print(f"{color.BLUE}{ctx.file2}{color.RESET}  ({ctx.name2}, Block {ctx.block})")
            self.lastmsg = msg
        for item in items:
            print(item)
        self.extra_line_done = False
        self.msgcount += 1

    def _printextra(self, *items: tg.Sequence[str]):
        if self.extra_line_done:
            return  # do _printextra only once between any two problems
        for item in items:
            print(item)
        self.extra_line_done = True

    def _numbered_sentence(self, ann_sent: annot.AnnotatedSentence) -> str:
        return f"[{ann_sent.sentence_idx}] {color.BOLD}{ann_sent.sentence}{color.RESET}"

    def _of_1(self, ctx: ComparatorContext, msg: str) -> str:
        return f"{color.RED}{msg}{color.RESET}  ({ctx.name1})"

    def _of_2(self, ctx: ComparatorContext, msg: str) -> str:
        return f"{color.RED}{msg}{color.RESET}  ({ctx.name2})"

    def _of_1_ok(self, ctx: ComparatorContext, msg: str) -> str:
        return f"{color.GREEN}{msg}{color.RESET}  -OK- ({ctx.name1})"

    def _of_2_ok(self, ctx: ComparatorContext, msg: str) -> str:
        return f"{color.GREEN}{msg}{color.RESET}  -OK- ({ctx.name2})"
