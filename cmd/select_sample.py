import json
import os.path
import random
import typing as tg

import qscript.metadata
import qscript

meaning = "Get block-randomized articles list of given size"


def add_arguments(subparser: qscript.ArgumentParser):
    subparser.add_argument('--size', metavar="N", type=int, required=True,
                           help="Total number of abstracts in the sample")
    subparser.add_argument('--blocksize', metavar="k", type=int, required=True,
                           help="Size of subsamples that are stratified over volumes and randomized")
    subparser.add_argument('--to', metavar="targetdir", type=str, required=True,
                           help="target directory where to place result")
    subparser.add_argument('volume', nargs='+',
                           help="dirname of a retrievelit result (subpopulation)")


def execute(args: qscript.Namespace):
    pop = Population(args.volumes)
    sample = Sample(args.blocksize)
    for i in range(args.size):
        sample.add(pop.draw1())
    if os.path.exists(f"{args.to}/sample.list"):
        print(f"{args.to}/sample.list already exists. I will not overwrite it. Exiting.")
        return
    qscript.metadata.write_list(f"{args.to}/sample.list", sample.entries)
    print(f"wrote '{args.to}/sample.list'")
    write_who_what(args.to, sample, args.blocksize)
    write_titles(args.to, sample, args.volumes)


class Population:
    def __init__(self, volumes: tg.Sequence[str]):
        self.subpopulations = []  # type: tg.List[tg.List[str]]
        for volume in volumes:
            my_subpopulation = self.subpopulation(volume)
            random.shuffle(my_subpopulation)
            self.subpopulations.append(my_subpopulation)
        self.next_subpopI = 0  # where to attempt to draw from next time

    def draw1(self) -> str:
        anything_left = sum(map(len, self.subpopulations)) > 0
        if not anything_left:
            raise ValueError("All subpopulations have run dry. Nothing left to draw from.")
        next = self.next_subpopI  # remember where we are and
        self.next_subpopI = (next + 1) % len(self.subpopulations)  # move on by 1
        if len(self.subpopulations[next]) > 0:
            return self.subpopulations[next].pop()  # return last element and remove it
        else:
            return self.draw1()  # return from next subpopulaation, because the current one is empty

    @staticmethod
    def subpopulation(volumedir: str) -> tg.List[str]:
        return qscript.metadata.read_list(f"{volumedir}/metadata/{volumename(volumedir)}.list")


class Sample:
    """
    A list that performs blockwise shuffling while built and 
    knows about its entries' structure a la 'EMSE-2021/AbuDab21.pdf' and can extract basenames from them.
    """
    def __init__(self, blocksize: int):
        self.blocksize = blocksize
        self._elems = []

    def add(self, elem: str):
        self._elems.append(elem)
        if len(self._elems) % self.blocksize == 0:
            self.shuffle_last(self.blocksize)
            # an incomplete last block will not be shuffled automatically, a negligible problem.

    def shuffle_last(self, n: int):
        """randomize order of the last n elems"""
        N = len(self._elems)
        lastblock = self._elems[(N - n):N]
        lastblock = random.sample(lastblock, n)
        self._elems[(N - n):N] = lastblock

    @property
    def entries(self) -> tg.Generator[str, None, None]:
        for elem in self._elems:
            yield elem

    @property
    def citekeys(self):
        for elem in self._elems:
            yield qscript.metadata.citekey(elem)


def volumename(volumedir: str) -> str:
    return os.path.basename(volumedir)


def write_who_what(to: str, sample: Sample, blocksize: int):
    filename = f"{to}/sample-who-what.txt"
    with open(filename, 'w', encoding='utf8') as who:
        who.write("# what      abstracts.A   abstracts.B\n")
        for i, citekey in enumerate(sample.citekeys):
            if i % blocksize == 0:
                who.write("#----- Block %d\n" % (int(i/blocksize)+1))
            who.write(f"{citekey}   \n")
        print(f"wrote '{filename}'")


def write_titles(to: str, sample: Sample, volumedirs: tg.Sequence[str]):
    """Knows about structure of metadata; writes mapping citekey->articletitle into file."""
    alltitles = dict()
    for volumedir in volumedirs:
        metadatafile = f"{volumedir}/metadata/{volumename(volumedir)}-dblp.json"
        with open(metadatafile, 'rt', encoding='utf8') as md:
            for entry in json.load(md)['corpus_metadata']:
                alltitles[entry['identifier']] = entry['title']  # make titles accessible by citekey
    titles = dict()
    for entry in sample.entries:
        volumedir, citekey = qscript.metadata.split_entry(entry)
        titles[citekey] = alltitles[citekey]
    filename = f"{to}/sample-titles.json"
    with open(filename, 'w', encoding='utf8') as j:
        json.dump(titles, j, indent=2)
        print(f"wrote '{filename}'")
