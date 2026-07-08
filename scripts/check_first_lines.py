import glob
bad=[]
for p in glob.glob('**/*.py'):
    try:
        with open(p,'r',encoding='utf-8') as f:
            first=f.readline()
            if not first:
                continue
            s=first.strip()
            if s and not (s.startswith('#') or s.startswith('from') or s.startswith('import') or s.startswith('"') or s.startswith("'") or s.startswith('def') or s.startswith('class') or s.startswith('"""')):
                bad.append((p,first))
    except Exception as e:
        print('ERR',p,e)

for p,first in bad:
    print(p,repr(first[:120]))

if not bad:
    print('No suspicious first lines found')
