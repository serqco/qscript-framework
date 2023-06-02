"""
Services that hide knowledge about codebook.md syntax structure and about annotations.
Terminology for annotations:
- annotation:  {{abc, defg:i1}}  on a line by itself
- annotationish: ditto, with perhaps broken braces or not alone on the line
- codings:     abc, defg:i1  as a string or list of coding-s
- coding:      defg:i1
- code:        defg
- csuffix:     :i1  ("colon-ed suffix")
- suffix:      i1  (or i1u1 or u1)
- suffixish:   CSuffix content not yet checked for structure
"""
import dataclasses
import re
import typing as tg

import qscript.icc as icc


OStr = tg.Optional[str]
AnnotationishMatches = tg.Tuple[OStr, OStr, OStr, OStr]
IUIUcount = tg.Tuple[int, int, int, int]


class Codebook:
    CODEBOOK_PATH = 'codebook.md'  # in project rootdir
    CODEDEF_REGEXP = r"code `([\w-]+(?::i?u)?)`"  # what code definitions look like in codebook
    IGNORECODE = '-ignorediff'  # code that indicates not to report coding differences
    GARBAGE_CODES = ['cruft']
    NONETOPIC = 'none'  # pseudo-topic for codes that have no topic

    def __init__(self):
        self.codes = self._allowed_codes(self.CODEBOOK_PATH)

    def exists_bare(self, code: str) -> bool:
        """Whether this code can never have a UI suffix."""
        return code in self.codes

    def exists_with_iu_suffix(self, coding: str) -> bool:
        """Whether this coding with no IU suffix could have had one."""
        return f"{coding}:iu" in self.codes

    def exists_with_u_suffix(self, coding: str) -> bool:
        """Whether this coding with no U suffix could have had one."""
        return f"{coding}:u" in self.codes

    def exists_with_suffix(self, coding: str) -> bool:
        return self.exists_with_iu_suffix(coding) or self.exists_with_u_suffix(coding)

    @staticmethod
    def is_extra_code(code: str) -> bool:
        return code.startswith('-')

    @staticmethod
    def is_heading_code(code: str) -> bool:
        return code.startswith('h-')

    @classmethod
    def topic(cls, code: str) -> str:
        """Code group, for a coarser analysis. Result words should have a unique first letter."""
        the_topic = dict(
                background='background', gap='gap', need='gap',
                objective='objective',
                design='design', method='method', result='result', claim='result', summary='summary',
                conclusion='conclusion',
                fposs='future', fneed='future', fgap='future', fwork='future',
                limitation='other', resourcepointer='other', X='other',
                )
        if code.startswith('-'):
            return cls.NONETOPIC  # auxiliary codes have no topic
        if code.startswith('a-'):
            return cls.topic(code[2:])
        if code.startswith('h-'):
            return cls.topic(code[2:])
        return the_topic[code]

    def _allowed_codes(self, codebookfile: str) -> tg.Set[str]:
        with open(codebookfile, 'rt', encoding='utf8') as cb:
            codebook = cb.read()
        codes = re.findall(self.CODEDEF_REGEXP, codebook, flags=re.IGNORECASE)
        return set(codes)


@dataclasses.dataclass
class AnnotatedSentence:
    sentence_idx: int
    sentence: str
    annotation: str


class Annotations:
    ALLOWED_IU_SUFFIX_REGEXP = r"i\d+|u\d+|i\d+u\d+"
    ALLOWED_U_SUFFIX_REGEXP = r"u\d+"
    ANNOTATIONISH_REGEXP = r"\n(\{\{[^}]*\})\n|\n(\{[^{]*\}\})\n|\n(.+\{\{.*\}\})|\n(\{\{.*\}\})\n"  # 4 cases
    ANNOTATION_CONTENT_REGEXP = r"([\w-]+)(:[\w\d]*)?"  # ignore commas and blanks and any non-word garbage symbols
    BARE_CODENAME_REGEXP = r"-?([\w-]+)(:[\w\d]*)?"
    EMPTY_ANNOTATION_REGEXP = r"\{\{\s*\}\}"
    LINE_AND_ANNOTATION_PAIR_REGEXP = r"(.*)\n(\{\{.*\}\})"
    SENTENCE_AND_ANNOTATION_PAIR_REGEXP = r"(?<=.\n\n|\}\}\n)(.*?)\n(\{\{.*?\}\})"
    SPLIT_SUFFIX_REGEXP = r":?(?:i(\d+))?(?:u(\d+))?"  # works for suffix or csuffix

    def __init__(self):
        self.codebook = icc.init(Codebook)

    def find_all_annotationish(self, content: str) -> tg.Sequence[AnnotationishMatches]:
        return re.findall(self.ANNOTATIONISH_REGEXP, content)

    def find_all_line_and_annotation_pairs(self, content: str) -> tg.Sequence[tg.Tuple[str, str]]:
        return re.findall(self.LINE_AND_ANNOTATION_PAIR_REGEXP, content)

    def find_all_sentence_and_annotation_pairs(self, content: str) -> tg.Sequence[AnnotatedSentence]:
        result = []
        i = 1
        for sentence, annotation in re.findall(self.SENTENCE_AND_ANNOTATION_PAIR_REGEXP, 
                                               content, flags=re.DOTALL):
            result.append(AnnotatedSentence(i, sentence, annotation))
            i += 1
        return result

    def bare_codename(self, coding: str) -> str:
        """Strips off leading dashes and trailing IU suffixes where present"""
        mm = re.match(self.BARE_CODENAME_REGEXP, coding)
        return mm.group(1)

    @staticmethod
    def check_annotationish(matches: AnnotationishMatches) -> tg.Tuple[OStr, OStr]:
        """Return (message, None) if annotationish is ill-formatted or (None, annotation) otherwise"""
        closing1, opening1, other, valid = matches
        if closing1:
            return f"second closing brace appears to be missing: '{closing1}'\n", None
        elif opening1:
            return f"second opening brace appears to be missing: '{opening1}'\n", None
        elif other:
            return "{{}}" f" annotation must be alone on a line: '{other}'\n", None
        return None, valid

    def codes_with_suffixes(self, annotation1: str, annotation2: str) -> tg.Mapping[str, IUIUcount]:
        """
        Map codes to tuples of (icount1, ucount1, icount2, ucount2) for 
        those codes in the annotations that can have IU suffixes or U suffixes.
        Counts are forced to 0 for codes that happen not to have a suffix.
        """
        result = dict()
        annotation_regexp = r"([\w-]+):(\d+)"
        for code, csuffix in re.findall(self.ANNOTATION_CONTENT_REGEXP, annotation1):
            if self.codebook.exists_with_suffix(code):
                result[code] = self.split_suffix(csuffix)
        for code, csuffix in re.findall(self.ANNOTATION_CONTENT_REGEXP, annotation2):
            if self.codebook.exists_with_suffix(code):
                icount1, ucount1 = result[code]
                icount2, ucount2 = self.split_suffix(csuffix)
                result[code] = (icount1, ucount1, icount2, ucount2)
        for code, count in re.findall(annotation_regexp, annotation2):
            assert False
            result[code] = (result[code], count)  # turn single count into a pair of counts
        # counts are never optional, so all values are pairs now
        return result

    def codings_of(self, annotation: str, strip_suffixes=False) -> tg.Set[str]:
        """Return set of codings from annotation."""
        result = set()
        for code, csuffix in re.findall(self.ANNOTATION_CONTENT_REGEXP, annotation):
            result.add(code + ("" if strip_suffixes else csuffix))
        return result

    def is_empty_annotation(self, annotation: str) -> bool:
        return re.match(self.EMPTY_ANNOTATION_REGEXP, annotation) is not None

    def split_into_codings(self, annotation: str) -> tg.Sequence[tg.Tuple[str, OStr]]:
        """E.g. "{{a,b:i1}} --> [("a", None), ("b", ":i1")]"""
        annotation = annotation[2:-2]  # strip off the braces front and back
        allcodes = re.findall(self.ANNOTATION_CONTENT_REGEXP, annotation)
        return allcodes

    def split_suffix(self, suffix: str) -> tg.Tuple[int, int]:
        """
        Return a pair (icount, ucount) from 
        an IU suffix (or csuffix) in i form, u form, iu form or even a missing one.
        """
        if not suffix:
            return 0, 0
        mm = re.fullmatch(self.SPLIT_SUFFIX_REGEXP, suffix)
        # if not mm:  # force malformed suffixes to (0, 0)
        #     return (0, 0)
        return (int(mm.group(1)) if mm.group(1) else 0,
                int(mm.group(2)) if mm.group(2) else 0,)

    def wrong_coding_msg(self, code: str, csuffix: tg.Optional[str]) -> tg.Optional[str]:
        """Check a single consisting coding of code and perhaps iu_suffix. Return error msg or None."""
        # ----- prepare suffix and base code:
        suffix = csuffix[1:] if csuffix else None  # strip off initial ':'
        if not suffix and code[-1] == '?':
            code = code[:-1]  # strip off trailing question mark
        # ----- report non-existing codes:
        if not suffix:
            if not self.codebook.exists_bare(code) and not self.codebook.exists_with_suffix(code):
                return f"unknown code: '{code}'"
            else:
                return None  # known code without suffix: done
        # ----- handle case with suffix:
        if self.codebook.exists_with_iu_suffix(code):
            mm = re.fullmatch(self.ALLOWED_IU_SUFFIX_REGEXP, suffix)
            if not mm:
                return f"IU suffix does not match one of the patterns :i1, :u2, :i3u4 : '{code}:{suffix}'"
        elif self.codebook.exists_with_u_suffix(code):
            mm = re.fullmatch(self.ALLOWED_U_SUFFIX_REGEXP, suffix)
            if not mm:
                return f"IU suffix does not match the only allowed pattern :u1 : '{code}:{suffix}'"
        else:
            return (f"%s: '{code}:{suffix}'" % ("should not have an IU suffix" if self.codebook.exists_bare(code)
                                                else "unknown code"))
        return None  # no problem found
