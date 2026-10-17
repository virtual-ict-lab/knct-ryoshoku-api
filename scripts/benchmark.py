# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Compare OCR to the 15 manually transcribed cells; --run repeats real inference."""
import argparse,json,sys,time,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
FIX=ROOT/'tests/fixtures/ocr'

def normalize(text):
    return ''.join(unicodedata.normalize('NFKC',text).split())

def distance(a,b):
    row=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        new=[i]
        for j,y in enumerate(b,1):
            new.append(min(new[-1]+1,row[j]+1,row[j-1]+(x!=y)))
        row=new
    return row[-1]

def score(rows):
    errors=total=exact=0
    for row in rows:
        expected=normalize(row['expected']); actual=normalize(row['actual'])
        errors+=distance(expected,actual);total+=len(expected);exact+=expected==actual
    return dict(exact=exact,cells=len(rows),errors=errors,characters=total,cer=errors/total)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--images-dir',type=Path,help='Directory containing local 00.png through 14.png cell images')
    parser.add_argument('--output',type=Path,default=ROOT/'data/benchmark/report.json')
    args=parser.parse_args()
    saved=ROOT/'docs/ocr-evaluation.json'
    if not args.run and saved.exists():
        for name,result in json.loads(saved.read_text())['summary'].items():
            print(f'{name}: {result["exact"]}/{result["cells"]}, CER {result["cer"]:.2%}')
        return
    truth=json.loads((FIX/'truth.json').read_text())
    reference={s['id']:s['expected'] for s in truth}
    summary={}
    for name in ['ndl-official','rapid-v5','rapid-v6-small','rapid-v6-medium']:
        rows=json.loads((FIX/f'{name}-results.json').read_text())
        for row in rows:row['expected']=reference[row['id']]
        summary[name]=score(rows)
    if args.run:
        if not args.images_dir:
            parser.error('--run requires --images-dir; reference images are not distributed')
        missing=[sample['id']+'.png' for sample in truth if not (args.images_dir/(sample['id']+'.png')).is_file()]
        if missing:
            parser.error('Missing local cell images: '+', '.join(missing))
        from PIL import Image
        from ryoshoku_ocr.engine import OcrEngine
        engine=OcrEngine('medium',ROOT/'.models');rows=[]
        for sample in truth:
            start=time.monotonic();lines=engine.read(Image.open(args.images_dir/(sample['id']+'.png')))
            rows.append({**sample,'actual':'\n'.join(l['text'] for l in lines),'lines':lines,'seconds':time.monotonic()-start})
        summary['production-medium-raw']=score(rows)
        display=[{**r,'actual':'\n'.join(l['text'] for l in r['lines'] if l['confidence']>=.5)} for r in rows]
        summary['production-medium-display']=score(display)
    else:
        rows=json.loads((FIX/'rapid-v6-medium-results.json').read_text())
        for row in rows:row['expected']=reference[row['id']]
    report={'normalization':'Unicode NFKC; ignore all whitespace; no dish corrections','baselineThreshold':.5,'productionThreshold':0.0,'summary':summary,'cells':rows}
    if args.run:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    for name,result in summary.items():print(f'{name}: {result["exact"]}/{result["cells"]}, CER {result["cer"]:.2%} ({result["errors"]}/{result["characters"]})')
if __name__=='__main__':main()
