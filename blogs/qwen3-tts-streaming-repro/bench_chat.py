"""Exercise the same /chat WebSocket as the Web UI; record PCM and text."""
import argparse,asyncio,array,json,time,wave
from pathlib import Path
import websockets

async def main(args):
 root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
 async with websockets.connect(args.ws,max_size=16*1024*1024) as ws:
  for i in range(args.runs):
   start=time.perf_counter();events=[];chunks=[];text='';metadata=None
   await ws.send(json.dumps({'type':'prompt','id':str(i),'text':args.prompt}))
   while True:
    m=await asyncio.wait_for(ws.recv(),120);elapsed=(time.perf_counter()-start)*1000
    if isinstance(m,bytes):
     assert metadata and len(m)==metadata['bytes'];metadata=None
     chunks.append(m);v=array.array('h',m)
     events.append({'event':'pcm','ms':elapsed,'samples':len(v),'first_loud_sample':next((j for j,a in enumerate(v) if abs(a)>327),None)})
    else:
     d=json.loads(m);assert d['id']==str(i),d
     kind=d.pop('type');events.append({'event':kind,'ms':elapsed,**d})
     if kind=='text':text+=d['text']
     if kind=='audio_meta':metadata=d
     if kind=='error':raise RuntimeError(d)
     if kind=='done':break
   first=lambda kind:next((e['ms'] for e in events if e['event']==kind),None)
   pcm=[e for e in events if e['event']=='pcm'];cursor=0;gaps=0;onset=None
   for e in pcm:
    if cursor:gaps+=max(0,e['ms']-cursor)
    when=max(cursor,e['ms'])
    if onset is None and e['first_loud_sample'] is not None:onset=when+e['first_loud_sample']/24
    cursor=when+e['samples']/24
   summary={'text':text,'ttft_ms':first('text'),'first_pcm_ms':first('pcm'),'first_nonquiet_ms':next(e['ms'] for e in pcm if e['first_loud_sample'] is not None),'simulated_onset_ms':onset,'underrun_ms':gaps,'total_ms':first('done'),'audio_s':sum(len(x) for x in chunks)/48000}
   with wave.open(str(root/f'chat-{i}.wav'),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000);f.writeframes(b''.join(chunks))
   (root/f'chat-{i}.json').write_text(json.dumps({'summary':summary,'events':events},ensure_ascii=False,indent=2))
   print(json.dumps(summary,ensure_ascii=False),flush=True)
   await asyncio.sleep(.5)
p=argparse.ArgumentParser();p.add_argument('--ws',default='ws://127.0.0.1:8092/chat');p.add_argument('--runs',type=int,default=2);p.add_argument('--prompt',default='请用两句话介绍一下杭州适合散步的地方。');p.add_argument('--output',default='outputs/chat-fast');asyncio.run(main(p.parse_args()))
