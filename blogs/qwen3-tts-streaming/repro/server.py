import asyncio
import os
import threading
import time
import traceback
import numpy as np
import torch
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from qwen_tts import Qwen3TTSModel
from streaming import LiveSession, install_adapter, Cancelled

app = FastAPI()
model = None
busy = threading.Lock()

@app.on_event('startup')
def load():
    global model
    torch.set_num_threads(1)
    model = Qwen3TTSModel.from_pretrained(os.environ['MODEL'], device_map='cuda:0',
                                       dtype=torch.bfloat16, attn_implementation='sdpa')
    install_adapter(model.model.talker)
    if os.getenv('FAST_INFERENCE', '0') == '1':
        from fast_inference import install_mtp, CodecGraph
        install_mtp(model.model.talker, verify=True)
        model.fast_codec = CodecGraph(model.model.speech_tokenizer)
        model.stream_do_sample = os.getenv('TALKER_SAMPLE', '1') == '1'
        model.trim_leading_silence = os.getenv('TRIM_LEADING_SILENCE', '1') == '1'
        # Warm graphs and verify real hidden states before accepting any requests.
        warm = LiveSession(model, lambda *args: None, 4, seed=42)
        warm.feed('你好，欢迎测试。今天我们测试首字朗读和持续音频生成的速度。')
        warm.end()
        warm.run()

@app.get('/health')
def health():
    return {'ready': model is not None, 'busy': busy.locked(), 'model': os.environ['MODEL'],
            'fast_inference': os.getenv('FAST_INFERENCE','0') == '1',
            'trim_leading_silence': getattr(model,'trim_leading_silence',False)}

@app.websocket('/ws')
async def ws(socket: WebSocket):
    await socket.accept()
    if not busy.acquire(blocking=False):
        await socket.send_json({'type': 'error', 'message': 'single-session experiment busy'})
        await socket.close(code=1013)
        return
    loop = asyncio.get_running_loop()
    outgoing = asyncio.Queue()
    session = None
    worker = None
    def emit(kind, data):
        loop.call_soon_threadsafe(outgoing.put_nowait, (kind, data))
    def generate():
        try:
            session.run()
        except Cancelled:
            emit('cancelled', {})
        except Exception as exc:
            traceback.print_exc()
            emit('error', {'message': str(exc)})
    async def receive():
        while True:
            msg = await socket.receive_json()
            if msg['type'] == 'text':
                session.feed(msg['text'])
            elif msg['type'] == 'end':
                session.end()
            elif msg['type'] == 'cancel':
                session.cancel()
                return
    async def send():
        while True:
            kind, data = await outgoing.get()
            if kind == 'audio':
                pcm = (np.clip(data.pop('pcm'), -1, 1) * 32767).astype('<i2').tobytes()
                await socket.send_json({'type': 'audio_meta', **data, 'bytes': len(pcm)})
                await socket.send_bytes(pcm)
            else:
                await socket.send_json({'type': kind, **data})
            if kind in ('done', 'error', 'cancelled'):
                return
    try:
        setup = await socket.receive_json()
        if setup.get('type') != 'start':
            raise ValueError('start expected')
        policy = setup.get('starvation', 'segment')
        if policy not in ('pad', 'wait', 'segment'):
            raise ValueError('starvation must be pad, wait, or segment')
        session = LiveSession(model, emit, int(setup.get('chunk_frames', 4)),
                              starvation=policy, seed=setup.get('seed'))
        if not 1 <= session.chunk_frames <= 32:
            raise ValueError('chunk_frames must be 1..32')
        worker = threading.Thread(target=generate, daemon=True)
        worker.start()
        reader = asyncio.create_task(receive())
        sender = asyncio.create_task(send())
        done, pending = await asyncio.wait([reader, sender], return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*done, *pending, return_exceptions=True)
    except WebSocketDisconnect:
        pass
    finally:
        if session:
            session.cancel()
        if worker:
            await asyncio.to_thread(worker.join)
        busy.release()


from web_chat import install_web
install_web(app, lambda: model, busy, LiveSession, Cancelled)
