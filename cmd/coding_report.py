import sys
import typing as tg
from typing import Any

import qscript.annotations as annot
import qscript.color as color
import qscript.icc as icc
import qscript.metadata
import qscript

from collections import defaultdict

meaning = """Counts (reports on) coding progress.
  Reads sample-who-what.txt and creates a report of the progress.
  Reports problems on stdout.
"""

aliases = ["report"]


def add_arguments(subparser: qscript.ArgumentParser):
    subparser.add_argument('workdir',
                           help="Directory where sample-who-what.txt lives")


def execute(args: qscript.Namespace):
    print("=================================")
    print("=== Report of Coding Progress ===")
    print("=================================")
    # ----- gather report data:
    what = qscript.metadata.WhoWhat(args.workdir)
    report_data = {
        'total_abs': 0,
        'blocks': set(),
        'pairs': defaultdict(lambda: {'abs_count': 0, 'blocks': set()}),
    }
    for pair in what.pairs:
        coder_tuple = tuple(sorted([pair[1], pair[3]]))
        block_name = what.blockname(pair[0])
        # Count total abstracts
        report_data['total_abs'] += 1
        # Track unique blocks
        report_data['blocks'].add(block_name)
        # Count pairs
        report_data['pairs'][coder_tuple]['abs_count'] += 1
        report_data['pairs'][coder_tuple]['blocks'].add(block_name)

    # ----- display report data:
    print(f"\nCoded Abstracts: {report_data['total_abs']} ({len(report_data['blocks'])} blocks)")
    print('\nCoding Pairs:')
    name_pad = max([len(name) for name in what.coders])
    sorted_pairs = dict(sorted(report_data['pairs'].items(),
                               key=lambda item: item[1]['abs_count'],
                               reverse=True))
    for pair, data in sorted_pairs.items():
        print(f"{pair[0]: <{name_pad}} & {pair[1]: <{name_pad}} {data['abs_count']} ({len(data['blocks'])} blocks)")
    print('\nCoding Individuals:')
    coder_reports = defaultdict(lambda: {'abs_count': 0, 'blocks': set()})
    for coder in sorted(what.coders):
        for pair, data in sorted_pairs.items():
            if coder not in pair:
                continue
            coder_reports[coder]['abs_count'] += data['abs_count']
            coder_reports[coder]['blocks'].update(data['blocks'])
    sorted_coder_reports = dict(sorted(coder_reports.items(),
                                       key=lambda item: item[1]['abs_count'],
                                       reverse=True)).items()
    for coder, coder_report in sorted_coder_reports:
        print(f"{coder: <{name_pad}} {coder_report['abs_count']} ({len(coder_report['blocks'])} blocks)")
    print('')
