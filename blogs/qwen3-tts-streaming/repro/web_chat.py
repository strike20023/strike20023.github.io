"""Single WebSocket, server-side LLM → streaming TTS experiment."""
import asyncio
import json
import os
import threading
from pathlib import Path

import httpx
import numpy as np
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse


def install_web(app, get_model, busy, session_class, cancelled_class):
    @app.get('/')
    async def index():
        return FileResponse(Path(__file__).with_name('web.html'))

    @app.get('/voices')
    async def voices():
        return {'voices': list(get_model().model.talker.config.spk_id), 'default': 'vivian'}

    async def turn(socket, request):
        request_id = request['id']
        if not busy.acquire(blocking=False):
            await socket.send_json({'type': 'error', 'id': request_id, 'message': '实验服务正在使用，请稍后重试。'})
            return
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()
        def emit(kind, data):
            loop.call_soon_threadsafe(queue.put_nowait, (kind, data))
        session = session_class(get_model(), emit, 4, starvation='segment', speaker=request['speaker'])
        def generate():
            try:
                session.run()
            except cancelled_class:
                pass
            except Exception as exc:
                emit('error', {'message': str(exc)})
        worker = threading.Thread(target=generate, daemon=True)
        async def llm():
            try:
                async with httpx.AsyncClient(timeout=90) as client:
                    async with client.stream('POST', os.getenv('LLM_URL', 'http://127.0.0.1:8001/v1/chat/completions'),
                        headers={'Authorization': 'Bearer '+os.environ['LLM_API_KEY']} if os.getenv('LLM_API_KEY') else {}, json={
                        'model': os.getenv('LLM_MODEL', 'your-model-name'), 'stream': True, 'max_tokens': 180,
                        'temperature': 0, 'chat_template_kwargs': {'enable_thinking': False},
                        'messages': [{'role': 'system', 'content': '用简洁中文直接回答，适合朗读，不使用Markdown。回答不超过一百字。'},
                                     {'role': 'user', 'content': request['text']}]
                    }) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.startswith('data:'):
                                continue
                            payload = line[5:].strip()
                            if payload == '[DONE]':
                                break
                            choices = json.loads(payload).get('choices', [])
                            piece = choices[0].get('delta', {}).get('content') if choices else None
                            if piece:
                                session.feed(piece)
                                queue.put_nowait(('text', {'text': piece}))
                session.end()
                queue.put_nowait(('text_done', {}))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                queue.put_nowait(('error', {'message': str(exc)}))
        worker.start()
        producer = asyncio.create_task(llm())
        terminal = None
        try:
            while True:
                kind, data = await asyncio.wait_for(queue.get(), 120)
                if kind in ('done', 'error'):
                    terminal = {'type': kind, 'id': request_id, **data}
                    break
                if kind == 'audio':
                    pcm = (np.clip(data['pcm'], -1, 1) * 32767).astype('<i2').tobytes()
                    await socket.send_json({'type': 'audio_meta', 'id': request_id, 'sample_rate': data['sample_rate'], 'bytes': len(pcm), 'speaker': session.speaker})
                    await socket.send_bytes(pcm)
                elif kind in ('text', 'text_done', 'segment_done', 'leading_silence'):
                    await socket.send_json({'type': kind, 'id': request_id, **data})
        except asyncio.TimeoutError:
            terminal = {'type': 'error', 'id': request_id, 'message': '生成超时'}
        finally:
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)
            session.cancel()
            await asyncio.to_thread(worker.join)
            busy.release()
        if terminal:
            await socket.send_json(terminal)

    @app.websocket('/chat')
    async def chat(socket: WebSocket):
        await socket.accept()
        task = None
        request_id = None
        try:
            while True:
                msg = await socket.receive_json()
                if msg.get('type') == 'cancel':
                    if task:
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
                        task = None
                    await socket.send_json({'type': 'cancelled', 'id': request_id})
                elif msg.get('type') == 'prompt':
                    if task and not task.done():
                        continue
                    if task:
                        await asyncio.gather(task, return_exceptions=True)
                    if not isinstance(msg.get('text'), str) or not 1 <= len(msg['text'].strip()) <= 2000:
                        await socket.send_json({'type': 'error', 'id': msg.get('id'), 'message': '请输入 1–2000 字文本。'})
                        continue
                    speaker = msg.get('speaker', 'vivian')
                    if not isinstance(speaker, str) or speaker not in get_model().model.talker.config.spk_id:
                        await socket.send_json({'type': 'error', 'id': msg.get('id'), 'message': '不支持的音色，请重新选择。'})
                        continue
                    msg['speaker'] = speaker
                    request_id = str(msg.get('id', ''))[:80]
                    task = asyncio.create_task(turn(socket, {**msg, 'id': request_id}))
        except (WebSocketDisconnect, ValueError):
            pass
        finally:
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
