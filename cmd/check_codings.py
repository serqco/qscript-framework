import sys
import typing as tg

import qscript.annotations as annot
import qscript.color as color
import qscript.icc as icc
import qscript.metadata
import qscript

meaning = """Checks annotated (and unannotated) extracts files for errors.
  Knows about annotation syntax. 
  Reads all extracts files and checks for syntax errors and undefined codes.
  Reports problems on stdout.
"""
aliases = ["check"]


def add_arguments(subparser: qscript.ArgumentParser):
    subparser.add_argument('workdir',
                           help="Directory where metadata and extracts subdirectories live")


def execute(args: qscript.Namespace):
    print("===============================================================================")
    print("=== check individual files (correct mistakes even if they are not your own) ===")
    print("===============================================================================")
    annots = icc.init(annot.Annotations)
    what = qscript.metadata.WhoWhat(args.workdir)
    errors: int = 0
    for coder in sorted(what.coders):
        print(f"\n#################### {coder}'s: ####################\n")
        for file in what.files_of(coder):
            errors += report_errors(file, coder, what.blockname(file), annots)
    errors = min(errors, 255) # avoid overflow
    sys.exit(errors)  # 0 if no errors, number of errors otherwise


def report_errors(file: str, coder: str, block: str, annots: annot.Annotations) -> int:
    def report():
        if errors:
            print(f"---- {color.BLUE}{file}{color.RESET}  ({coder}, Block {block}):\n" + '\n'.join(errors))
    with open(file, 'rt', encoding='utf8') as f:
        content = f.read()
    # ----- check annotation-ish stuff:
    errors = []
    for matches in annots.find_all_annotationish(content):
        msg, annotation = annots.check_annotationish(matches)
        if msg and not annotation:
            errors.append(f"{color.RED}{msg}{color.RESET}")
        elif annotation and not msg:
            errors.extend(report_errors_within_braces(annotation, annots))
        else:
            assert False, "WTF? This was supposed to never happen!"
        if len(errors) > 3:  # don't overwhelm with too many messages
            errors.append("too many problems in this file, stopping.\n")
            report()
            return len(errors)
    # ----- finish:
    report()
    return len(errors)


def report_errors_within_braces(annotation: str, annots: annot.Annotations) -> tg.Sequence[str]:
    errors = []
    for code, fullsuffix in annots.split_into_codings(annotation):
        try:
            annots.check_coding(code, fullsuffix)
        except annots.codebook.CodingError as exc:
            errors.append(f"{annotation}\n{color.RED}{exc.args[0]}{color.RESET}")
    return errors