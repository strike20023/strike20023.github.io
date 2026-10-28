"""Extract ONLY audio received before the second text delta; no future-text leak."""
import argparse,json,wave
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('directory');args=p.parse_args()
for path in sorted(Path(args.directory).glob('hold-*.json')):
    if '-prefix' in path.stem: continue
    d=json.loads(path.read_text()); ts=[e for e in d['events'] if e['event']=='text_delta']
    if len(ts)<2: continue
    count=sum(e['samples'] for e in d['events'] if e['event']=='pcm' and e['ms']<ts[1]['ms'])
    if not count: continue
    with wave.open(str(path.with_suffix('.wav')),'rb') as f:
        pcm=f.readframes(count);params=f.getparams()
    target=path.with_name(path.stem+'-prefix.wav')
    with wave.open(str(target),'wb') as f:
        f.setparams(params);f.writeframes(pcm)
    target.with_suffix('.json').write_text(json.dumps({'summary':{'text':ts[0]['text'],
        'audio_seconds':count/24000,'cutoff_ms':ts[1]['ms']}},ensure_ascii=False,indent=2))
    print(target,count/24000,flush=True)
