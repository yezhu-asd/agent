import ast, glob, sys
errors = []
for path in glob.glob('**/*.py', recursive=True):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            src = f.read()
        ast.parse(src, filename=path)
    except Exception as e:
        print(f"SYNTAX ERROR in {path}: {e}")
        errors.append(path)

if errors:
    print(f"Found {len(errors)} file(s) with syntax errors")
    sys.exit(2)

print('All files syntactically valid')
