"""Client-clock latency measurement; PCM receipt is not physical speaker onset."""
import argparse
import os
import asyncio
import json
import time
import wave
import array
import random
from pathlib import Path
import httpx
import websockets

async def run(args, index):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    events, chunks = [], []
    origin = time.perf_counter()
    def event(kind, **data):
        row = {'event': kind, 'ms': (time.perf_counter()-origin)*1000, **data}
        events.append(row)
        return row
    text = ''
    async with websockets.connect(args.ws, max_size=16*1024*1024) as ws:
        await ws.send(json.dumps({'type':'start', 'chunk_frames':args.chunk_frames,
                                  'starvation':args.starvation, 'seed':args.seed}))
        async def producer():
            nonlocal text
            event('request_start')
            if args.mode != 'llm':
                pieces = (list(args.text) if args.mode == 'chars' else
                          [args.text[:1], args.text[1:]] if args.mode == 'hold' else [args.text])
                rng = random.Random(args.seed)
                if args.mode == 'jitter':
                    pieces = []
                    offset = 0
                    while offset < len(args.text):
                        size = rng.randint(1,4)
                        pieces.append(args.text[offset:offset+size])
                        offset += size
                for piece_index, piece in enumerate(pieces):
                    text += piece
                    event('text_delta', text=piece)
                    await ws.send(json.dumps({'type':'text', 'text':piece}))
                    if args.mode == 'jitter' and piece_index+1 < len(pieces):
                        await asyncio.sleep(rng.uniform(.02,args.delay))
                    if args.mode in ('chars', 'hold') and piece_index+1 < len(pieces):
                        await asyncio.sleep(args.delay)
            else:
                async with httpx.AsyncClient(timeout=120) as client:
                    async with client.stream('POST', args.llm+'/v1/chat/completions', headers={'Authorization':'Bearer '+os.environ['LLM_API_KEY']} if os.getenv('LLM_API_KEY') else {}, json={
                        'model':os.getenv('LLM_MODEL','your-model-name'), 'stream':True, 'temperature':0,
                        'max_tokens':180, 'chat_template_kwargs':{'enable_thinking':False},
                        'messages':[{'role':'system','content':'用简洁中文直接回答，不要思考过程，不使用Markdown。'},
                                    {'role':'user','content':args.prompt}]
                    }) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.startswith('data: '):
                                continue
                            if line[6:] == '[DONE]':
                                break
                            obj = json.loads(line[6:])
                            choices = obj.get('choices', [])
                            if not choices:
                                continue
                            delta = choices[0].get('delta', {})
                            piece = delta.get('content')
                            if piece:
                                text += piece
                                event('text_delta', text=piece)
                                await ws.send(json.dumps({'type':'text', 'text':piece}))
            event('text_end')
            await ws.send(json.dumps({'type':'end'}))
        async def consumer():
            async for message in ws:
                if isinstance(message, bytes):
                    chunks.append(message)
                    samples = array.array('h', message)
                    event('pcm', samples=len(message)//2, peak=max(map(abs, samples), default=0),
                          first_loud_sample=next((i for i,v in enumerate(samples) if abs(v)>327),None))
                else:
                    obj = json.loads(message)
                    event(obj.pop('type'), **obj)
                    if events[-1]['event'] in ('done','error','cancelled'):
                        break
        await asyncio.wait_for(asyncio.gather(producer(),consumer()), timeout=180)
    name = f'{args.mode}-{index}'
    with wave.open(str(out/(name+'.wav')), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
        wav.writeframes(b''.join(chunks))
    def first(kind):
        return next((e['ms'] for e in events if e['event']==kind), None)
    start = first('request_start')
    pcm = [e for e in events if e['event']=='pcm']
    # Simulated immediate playback, no startup buffering or hardware latency.
    cursor = pcm[0]['ms'] if pcm else 0
    underrun = 0
    simulated_onset = None
    for e in pcm:
        underrun += max(0, e['ms']-cursor)
        if simulated_onset is None and e['first_loud_sample'] is not None:
            simulated_onset = max(cursor,e['ms'])+e['first_loud_sample']/24-start
        cursor = max(cursor,e['ms'])+e['samples']/24
    summary = {'name':name, 'text':text, 'ttft_ms':first('text_delta')-start,
        'first_pcm_ms': None if not pcm else pcm[0]['ms']-start,
        'first_text_to_pcm_ms':None if not pcm else pcm[0]['ms']-first('text_delta'),
        'first_nonquiet_pcm_ms':next((e['ms']-start for e in pcm if e['peak']>327),None),
        'text_end_ms':first('text_end')-start,
        'total_ms':events[-1]['ms']-start,
        'audio_seconds':sum(len(c) for c in chunks)/48000,
        'simulated_underrun_ms':underrun,
        'simulated_first_nonquiet_play_ms':simulated_onset,
        'segments':sum(e['event']=='segment_done' for e in events),
        'underflow_frames':sum(e['event']=='text_underflow' for e in events),
        'audio_before_text_end':bool(pcm and pcm[0]['ms']<first('text_end')),
        'status':events[-1]['event'], 'chunk_frames':args.chunk_frames,
                                  'starvation':args.starvation, 'seed':args.seed}
    (out/(name+'.json')).write_text(json.dumps({'summary':summary,'events':events},ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False),flush=True)

async def main(args):
    for i in range(args.runs):
        await run(args, i)
        await asyncio.sleep(.5)

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--ws',default='ws://127.0.0.1:8092/ws')
    p.add_argument('--llm',default='http://127.0.0.1:8001')
    p.add_argument('--mode',choices=['llm','chars','full','hold','jitter'],default='llm')
    p.add_argument('--text',default='你好，今天我们测试实时语音合成。')
    p.add_argument('--prompt',default='用两句话解释为什么天空是蓝色的，限制在六十个汉字以内。')
    p.add_argument('--delay',type=float,default=.15)
    p.add_argument('--runs',type=int,default=1)
    p.add_argument('--chunk-frames',type=int,default=4)
    p.add_argument('--starvation', choices=['wait','pad','segment'], default='segment')
    p.add_argument('--seed',type=int,default=None)
    p.add_argument('--output',default='outputs/bench')
    asyncio.run(main(p.parse_args()))
