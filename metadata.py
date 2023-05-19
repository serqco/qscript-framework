"""Reading and a little writing the various metadata files."""
import glob
import re
import typing as tg

Entry = str  # Pseudo type for strings of form "mypath/EMSE-2021/AbuDab21.pdf"
Filepair = tg.Tuple[str, str, str, str]  # (file1, coder1, file2, coder2)


def citekey(list_line: Entry) -> str:
    """From a line like EMSE-2021/AbuDab21.pdf return AbuDab21"""
    return split_entry(list_line)[1]


def split_entry(list_line: Entry) -> tg.Tuple[str, str]:
    """From a line like volumes/EMSE-2021/AbuDab21.pdf return its semantic parts EMSE-2021 and AbuDab21"""
    mm = re.search(r"([^/]+)/([^/]+)\.pdf$", list_line)
    assert mm
    return mm.group(1), mm.group(2)


def volume(list_line: Entry) -> str:
    """From a line like EMSE-2021/AbuDab21.pdf return EMSE-2021"""
    return split_entry(list_line)[0]


def read_list(filename: str) -> tg.List[Entry]:
    with open(filename, 'rt', encoding='utf-8') as lst:
        mylist = lst.read().split('\n')
        mylist.pop()  # file ends with \n, so last item is empty
    return mylist


def write_list(to: str, entries: tg.Iterator[Entry]):
    with open(to, 'w', encoding='utf8') as lst:
        for elem in entries:
            lst.write(f"{elem}\n")


class Venue:
    """Understands sample.list and can determine which venue or volume a citekey belongs to."""
    FILENAME = "sample.list"
    ENTRY_REGEXP = r"(\w+)-(\d+)/([\w-]+)\."  # e.g. TSE-2021/LiuKimBis21.pdf

    def __init__(self, workdir: str):
        self.workdir = workdir
        self.venue = dict()  # citekey -> venue name (e.g. TSE)
        self.volume = dict()  # citekey -> volume name (e.g. TSE22 for TSE-2022 or TSE48 for TSE-48)
        with open(f"{workdir}/{self.FILENAME}", 'r', encoding='utf8') as f:
            lines = f.readlines()
        for line in lines:
            mm = re.match(self.ENTRY_REGEXP, line)
            venue, number, citekey_ = (mm.group(1), mm.group(2), mm.group(3))
            if re.fullmatch(r"20\d\d", number):
                number = number[2:]  # remove century, leaving only a two-digit year
            self.venue[citekey_] = venue
            self.volume[citekey_] = f"{venue}{number}"

    def venue_of(self, citekey_: str) -> str:
        return self.venue[citekey_]

    def volume_of(self, citekey_: str) -> str:
        return self.volume[citekey_]


class WhoWhat:
    """
    Can tell which coder annotated which file and which pairs of files to compare.
    Hides the following secrets :
    1. The filename of the who/what file.
    2. The format of that file (for reading only)
    3. The meaning of the entries in that file (blocks, reservations, implied filenames, coder_letters)
    4. Which pairs of annotated files should be compared
    Secret 3 is non-fixed wrt the A/B subdirectories, the names of which may involve a variable prefix.
    This makes _subdir_prefix() necessary and makes citekey() and coderletter() a bit ugly.
    """
    WHOWHAT_FILE = "sample-who-what.txt"  # in workdir
    FILENAMEPATTERN = r"/(.*)?([A-Z])/(\w+)\.txt$"
    BLOCKHEADER_REGEXP = r"^#---+ [Bb]lock (\d+)"

    def __init__(self, workdir: str):
        self.workdir = workdir
        self.subdir_prefix = self._subdir_prefix()
        self.coders = set()
        self._coder_of = dict()  # filename -> codername
        self._block_of = dict()  # filename -> blockname
        self._pairs: tg.List[Filepair] = [] 
        with open(f"{workdir}/{self.WHOWHAT_FILE}", 'r', encoding='utf8') as f:
            lines = f.readlines()
        currentblock = ""  # block number as a string
        for line in lines:
            if line.startswith("#"):
                mm = re.match(self.BLOCKHEADER_REGEXP, line)
                if mm:
                    currentblock = mm.group(1)
                continue
            parts = line.strip().split()  # splits on single or multiple whitespace after removing trailing \n
            citekey_ = parts[0]
            columns = parts[1:]  # list of coder names or reservations
            # --- collect coders and single-file entries:
            for index, coder in enumerate(columns):
                if self.is_reservation(coder):
                    continue  # reservations are non-entries
                self.coders.add(coder)
                filename = self._implied_filename(citekey_, index)
                self._coder_of[filename] = coder
                self._block_of[filename] = currentblock
            # --- collect filepair entries, using either _build_pairs_with_A oder _build_neighboring_pairs:
            for next_pair in self._build_pairs_with_A(citekey_, columns):
                self._pairs.append(next_pair)

    def blockname(self, filename: str) -> str:
        """Which block does this file belong to?"""
        return self._block_of[filename]

    def citekey(self, filename: str) -> str:
        return self._filenamepart(filename, 3)

    def coder_letter(self, filename: str) -> str:
        return self._filenamepart(filename, 2)

    def files_of(self, coder: str) -> tg.Generator[str, None, None]:
        for myfile, mycoder in self._coder_of.items():
            if mycoder == coder:
                yield myfile

    @staticmethod
    def is_reservation(codername: str) -> bool:
        return codername.startswith('-')

    @property
    def pairs(self) -> tg.Generator[str, None, None]:
        for file1, coder1, file2, coder2 in self._pairs:
            if not self.is_reservation(coder1) and not self.is_reservation(coder2):
                yield file1, coder1, file2, coder2

    def _implied_filename(self, citekey_: str, columnindex: int) -> str:
        """Knows the abstracts.A, abstracts.B dirname convention. First such column has index 0."""
        char = chr(ord('A') + columnindex)  # 26 columns maximum (we'll never need more than 10)
        return f"{self.workdir}/{self.subdir_prefix}{char}/{citekey_}.txt"

    def _filenamepart(self, filename: str, which: int) -> str:
        """Partial inverse of _implied_filename()"""
        mm = re.search(self.FILENAMEPATTERN, filename)
        return mm.group(which)


    def _subdir_prefix(self) -> str:
        """
        Determine which, if any, prefix is used for the names of the extracts-holding subdirectories.
        For workdir/abstracts.A would yield "abstracts.",
        for workdir/A would yield "".
        """
        results = glob.glob(f"{self.workdir}/*A")
        assert len(results) == 1, f"surprising glob result: {results}"
        mm = re.search(r"/(.*)A$", results[0])  # find prefix in last part of path
        return mm.group(1)

    def _build_neighboring_pairs(self, citekey_: str, columns: tg.Sequence[str]) -> tg.Generator[Filepair, None, None]:
        """
        Generator for pairs of neighboring entries A/B, C/D etc. (whether reservation or not).
        """
        firstentry = None  # we return a pair whenever we have a first and find another entry
        for index, coder in enumerate(columns):
            if firstentry:
                mypair = (firstentry[0], firstentry[1], self._implied_filename(citekey_, index), coder)
                firstentry = None
                yield mypair
            else:
                firstentry = (self._implied_filename(citekey_, index), coder)
        # firstentry may be set when the loop finishes, leaving an unpaired entry. C'est la vie!

    def _build_pairs_with_A(self, citekey_: str, columns: tg.Sequence[str]) -> tg.Generator[Filepair, None, None]:
        """
        Generator for pairs A/B, A/C, A/D etc. (whether reservation or not).
        """
        if len(columns) == 0:
            return  # there are zero pairs
        coder_A = columns[0]
        file_of_A = self._implied_filename(citekey_, 0)
        for index, coder in enumerate(columns[1:]):
            yield file_of_A, coder_A, self._implied_filename(citekey_, index+1), coder
