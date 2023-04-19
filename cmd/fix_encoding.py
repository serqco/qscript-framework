import qscript

meaning = """Makes each file conform to UTF-8 encoding.
  Attempts to read it as UTF-8. 
  If that fails, reads it as Windows-1252 and writes it back to the same filename as UTF-8.
"""

def add_arguments(subparser: qscript.ArgumentParser):
    subparser.add_argument('files', nargs='+',
                           help="Files to check and perhaps convert")


def execute(args: qscript.Namespace):
    print("============================================================")
    print("=== Rewrite non-UTF8 files (interpreted as Windows-1252) ===")
    print("============================================================")
    for file in args.files:
        check_and_perhaps_rewrite(file)


def check_and_perhaps_rewrite(file: str):
    print(f"reading '{file}'")
    try:
        with open(file, 'rt', encoding='utf-8') as f:
            f.read()  # just read. The actual data is not needed.
    except UnicodeDecodeError as exc:
        print(f"==> rewriting '{file}' from assumed Windows-1252 to UTF-8")
        with open(file, 'rb') as f:
            content = f.read().decode(encoding='windows-1252', errors='replace')
        with open(file, 'wb') as f:
            f.write(content.encode(encoding='utf-8', errors='replace'))  # put '?' for unknown chars
