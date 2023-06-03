"""
Services that hide knowledge about codebook.md syntax structure and about annotations.
Terminology for annotations:
- annotation:  {{abc, defg:i1}}  on a line by itself
- annotationish: ditto, with perhaps broken braces or not alone on the line
- codings:     abc, defg:i1  as a string or list of coding-s
- coding:      defg:i1
- code:        defg
- cfullsuffix: :flag:i1  ("coloned")
- fullsuffix:  flag:i1
- suffix:      i1  (or i1u1 or u1)
"""
import dataclasses
import re
import typing as tg

import qscript.icc as icc


OStr = tg.Optional[str]
AnnotationishMatches = tg.Tuple[OStr, OStr, OStr, OStr]
IUIUcount = tg.Tuple[int, int, int, int]


@dataclasses.dataclass
class CodeDef:
    code: str
    suffixdef: str
    suffix_regexp: str


class Codebook:
    CODEBOOK_PATH = 'codebook.md'  # in project rootdir
    CODEDEF_REGEXP = r"code `([\w-]+)((?::[^:`]+)+)?`"  # e.g. mycode:flag:i\d
    SUFFIX_SEPARATOR = ":"  # hardcoded in CODEDEF_REGEXP!
    IGNORECODE = '-ignorediff'  # code that indicates not to report coding differences
    GARBAGE_CODES = ['cruft']
    NONETOPIC = 'none'  # pseudo-topic for codes that have no topic
    codedefs: tg.Mapping[str, CodeDef]  # maps code to CodeDef

    def __init__(self):
        self.codedefs = self.codebook_contents(self.CODEBOOK_PATH)

    class CodingError(KeyError):
        """Code or suffix do not conform to codebook."""
        pass

    def exists(self, code: str) -> bool:
        return code in self.codedefs

    def check_suffix(self, code: str, fullsuffixish: str) -> None:
        """Raises SuffixError(msg, code, suffix"""
        if not fullsuffixish:
            return  # null suffixes are always OK
        if fullsuffixish.startswith(self.SUFFIX_SEPARATOR):
            fullsuffixish = fullsuffixish[1:]  # remove initial separator
        for suffix in fullsuffixish.split(self.SUFFIX_SEPARATOR):
            allowed_pattern = self.codedefs[code].suffix_regexp
            if not re.fullmatch(allowed_pattern, suffix):
                msg = (f"suffix '{suffix}' not allowed for code '{code}': "
                       f"{code}{self.SUFFIX_SEPARATOR}{self.codedefs[code].suffixdef}")
                raise self.CodingError(msg)
            # else all is fine and nothing happens

    @staticmethod
    def is_extra_code(code: str) -> bool:
        return code.startswith('-')

    @classmethod
    def is_subjective_code(cls, code: str) -> bool:
        return code.startswith('-') and code != cls.IGNORECODE

    @staticmethod
    def is_heading_code(code: str) -> bool:
        return code.startswith('h-')

    @classmethod
    def topic(cls, code: str) -> str:
        """Code group, for a coarser analysis. Result words should have a unique first letter."""
        if code.startswith('-'):
            return cls.NONETOPIC  # auxiliary codes have no topic
        if code.startswith('a-'):
            return cls.topic(code[2:])
        if code.startswith('h-'):
            return cls.topic(code[2:])
        return cls._rawtopicdict()[code]

    def codebook_contents(self, codebookfile: str) -> tg.Mapping[str, CodeDef]:
        with open(codebookfile, 'rt', encoding='utf8') as cb:
            codebook = cb.read()
        matches = re.findall(self.CODEDEF_REGEXP, codebook, flags=re.IGNORECASE)
        result = dict()
        for code, suffixdef in matches:
            if suffixdef:
                suffixdef = suffixdef[1:]  # remove initial separator
            suffix_regexp = suffixdef.replace(self.SUFFIX_SEPARATOR, '|')  
            codedef = CodeDef(code, suffixdef, suffix_regexp)
            result[code] = codedef
        return result


@dataclasses.dataclass
class AnnotatedSentence:
    sentence_idx: int
    sentence: str
    annotation: str


class Annotations:
    ANNOTATIONISH_REGEXP = r"\n(\{\{[^}]*\})\n|\n(\{[^{]*\}\})\n|\n(.+\{\{.*\}\})|\n(\{\{.*\}\})\n"  # 4 cases
    ANNOTATION_CONTENT_REGEXP = r"([\w-]+)((?::[\w\d]+)*)"  # ignore commas and blanks and any non-word garbage symbols
    BARE_CODENAME_REGEXP = r"-?([\w-]+)(:[\w\d]*)?"
    EMPTY_ANNOTATION_REGEXP = r"\{\{\s*\}\}"
    LINE_AND_ANNOTATION_PAIR_REGEXP = r"(.*)\n(\{\{.*\}\})"
    SENTENCE_AND_ANNOTATION_PAIR_REGEXP = r"(?<=.\n\n|\}\}\n)(.*?)\n(\{\{.*?\}\})"

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
        """Strips off leading dashes and trailing suffixes where present"""
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

    def codings_of(self, annotation: str, strip_suffixes=False, strip_subjective=False) -> tg.Set[str]:
        """Return set of codings from annotation."""
        result = set()
        for code, csuffix in re.findall(self.ANNOTATION_CONTENT_REGEXP, annotation):
            if strip_subjective and self.codebook.is_subjective_code(code):
                continue  # do not include the subjective code
            result.add(code + ("" if strip_suffixes else csuffix))
        return result

    def is_empty_annotation(self, annotation: str) -> bool:
        return re.match(self.EMPTY_ANNOTATION_REGEXP, annotation) is not None

    def split_into_codings(self, annotation: str) -> tg.Sequence[tg.Tuple[str, str]]:
        """E.g. "{{a,b:i1}} --> [("a", ""), ("b", ":i1")]"""
        annotation = annotation[2:-2]  # strip off the braces front and back
        allcodes = re.findall(self.ANNOTATION_CONTENT_REGEXP, annotation)
        return allcodes

    def check_coding(self, code: str, cfullsuffix: tg.Optional[str]):
        """Check a single coding of code and perhaps cfullsuffix. Perhaps raise CodingError."""
        if not self.codebook.exists(code):
            raise self.codebook.CodingError(f"unknown code: '{code}'")
        self.codebook.check_suffix(code, cfullsuffix)
