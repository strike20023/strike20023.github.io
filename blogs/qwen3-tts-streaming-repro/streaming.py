"""Experimental single-session true incremental text adapter for upstream qwen-tts.

Default policy closes a model segment on text starvation, drains its audio,
then starts the next segment in the same WebSocket session. KV state is retained
within a segment, not across starvation boundaries. Unread arrived text is
re-tokenized together; committed token boundaries cannot be retroactively changed.
Audio uses causal prefix decoding. Diagnostic pad policy can drop later speech
and is not suitable as the default. Installed model source is not modified.
"""
import inspect
import queue
import textwrap
import types
import time
import torch
import numpy as np


class Cancelled(Exception):
    pass


def install_adapter(talker):
    original = inspect.unwrap(type(talker).forward)
    source = textwrap.dedent(inspect.getsource(original))
    source = source[source.index('def forward('):]
    old = '''if generation_step < trailing_text_hidden.shape[1]:
            inputs_embeds = inputs_embeds + trailing_text_hidden[:, generation_step].unsqueeze(1)
        else:
            inputs_embeds = inputs_embeds + tts_pad_embed'''
    assert old in source, 'Upstream forward changed; review adapter'
    source = source.replace(old, '''if getattr(self, "live_session", None) is not None:
            self.live_session.on_codes(codec_ids)
            inputs_embeds = inputs_embeds + self.live_session.next_embedding()
        elif generation_step < trailing_text_hidden.shape[1]:
            inputs_embeds = inputs_embeds + trailing_text_hidden[:, generation_step].unsqueeze(1)
        else:
            inputs_embeds = inputs_embeds + tts_pad_embed''')
    anchor = 'logits = self.codec_head(hidden_states)'
    assert anchor in source
    source = source.replace(anchor, anchor + '''
    if getattr(self, "live_session", None) is not None and not self.live_session.ended:
        logits[..., self.config.codec_eos_token_id] = -float("inf")
''')
    namespace = dict(original.__globals__)
    exec(compile(source, '<qwen3-tts-live-forward>', 'exec'), namespace)
    talker.forward = types.MethodType(namespace['forward'], talker)


class LiveSession:
    def __init__(self, model, emit, chunk_frames=4, starvation="segment", seed=None, speaker="vivian"):
        self.speaker = speaker
        self.wrapper = model
        self.talker = model.model.talker
        self.emit = emit
        self.queue = queue.Queue()
        self.pending = []
        self.text_buffer = ""
        self.ended = False
        self.cancelled = False
        self.codes = []
        self.samples_sent = 0
        self.audible = False
        self.chunk_frames = chunk_frames
        self.text_consumed = 0
        self.starvation = starvation
        self.seed = seed
        self.pad_steps = 0
        self.session_ended = False
        self.segment_id = 0
        self.total_frames = 0
        self.leading_pending = np.empty(0,dtype=np.float32)
        self.leading_done = not getattr(model, "trim_leading_silence", False)
        self.leading_dropped = 0
        self.last_input = time.monotonic()

    def feed(self, text):
        if text:
            self.last_input = time.monotonic()
            self.queue.put(text)

    def end(self):
        self.queue.put(None)

    def cancel(self):
        self.cancelled = True
        self.queue.put(None)

    def get(self):
        item = self.queue.get(timeout=60)
        if self.cancelled:
            raise Cancelled()
        return item

    def embed(self, ids):
        ids = torch.tensor([ids], device=self.talker.device, dtype=torch.long)
        return self.talker.text_projection(self.talker.get_text_embeddings()(ids))

    def tokenize_offsets(self, text):
        encoded = self.wrapper.processor.tokenizer(text, add_special_tokens=False,
                                                    return_offsets_mapping=True)
        return encoded['input_ids'], encoded['offset_mapping']

    def take_group(self):
        # Re-tokenize only unread text. Commit all byte pieces covering the first
        # complete character together so a multibyte character is never dropped.
        ids, offsets = self.tokenize_offsets(self.text_buffer)
        if not ids:
            raise ValueError('Unread text has no tokens')
        end = offsets[0][1]
        if end <= 0:
            raise ValueError('Tokenizer returned an empty offset')
        count = 1
        while count < len(ids) and offsets[count][1] <= end:
            count += 1
        self.pending.extend(ids[:count])
        self.text_buffer = self.text_buffer[end:]

    def accept_text(self, text):
        if text is None:
            self.session_ended = True
        else:
            self.text_buffer += text

    def next_embedding(self):
        if self.cancelled:
            raise Cancelled()
        if self.ended:
            return self.embed([self.wrapper.model.config.tts_pad_token_id])
        while True:
            while not self.session_ended:
                try:
                    self.accept_text(self.queue.get_nowait())
                except queue.Empty:
                    break
            if not self.pending and self.text_buffer:
                self.take_group()
            if self.pending:
                self.text_consumed += 1
                return self.embed([self.pending.pop(0)])
            if self.session_ended:
                self.ended = True
                return self.embed([self.wrapper.model.config.tts_eos_token_id])
            if self.starvation == 'wait':
                self.accept_text(self.get())
                continue
            if self.starvation == 'segment':
                self.ended = True
                self.emit('segment_sealed', {'time': time.perf_counter(),
                          'segment': self.segment_id, 'reason': 'text_underflow'})
                return self.embed([self.wrapper.model.config.tts_eos_token_id])
            if time.monotonic() - self.last_input > 30:
                raise TimeoutError('Text input stalled for 30 seconds')
            self.pad_steps += 1
            self.emit('text_underflow', {'time': time.perf_counter(),
                      'frame': len(self.codes), 'pad_steps': self.pad_steps})
            return self.embed([self.wrapper.model.config.tts_pad_token_id])

    def on_codes(self, codes):
        if self.cancelled:
            raise Cancelled()
        self.codes.append(codes[0].detach())
        if not self.audible or (len(self.codes)-1) % self.chunk_frames == 0:
            self.decode()

    def decode(self):
        if not self.codes:
            return
        fast = getattr(self.wrapper, 'fast_codec', None)
        if self.samples_sent == len(self.codes) * 1920:
            return
        if fast is not None:
            chunk, sr = fast.decode_new(self.codes, self.samples_sent)
            self.samples_sent += len(chunk)
        else:
            audio, sr = self.wrapper.model.speech_tokenizer.decode(
                [{'audio_codes': torch.stack(self.codes)}])
            wav = audio[0]
            chunk = wav[self.samples_sent:]
            self.samples_sent = len(wav)
        if len(chunk):
            self.audible = self.audible or bool((abs(chunk) > .01).any())
            if not self.leading_done:
                combined = np.concatenate([self.leading_pending, chunk])
                audible = np.flatnonzero(np.abs(combined) > .001)
                if len(audible):
                    cut = max(0, int(audible[0]) - int(sr * .04))
                    self.leading_dropped += cut
                    chunk = combined[cut:]
                    self.leading_done = True
                    self.emit('leading_silence', {'trimmed_ms': self.leading_dropped / sr * 1000})
                    self.leading_pending = np.empty(0,dtype=np.float32)
                else:
                    keep = min(len(combined), int(sr * .04))
                    self.leading_dropped += len(combined) - keep
                    self.leading_pending = combined[-keep:]
                    return
            self.emit('audio', {'pcm': chunk, 'sample_rate': sr,
                                'frames': self.total_frames + len(self.codes),
                                'segment': self.segment_id, 'time': time.perf_counter()})

    @torch.inference_mode()
    def run(self):
        if self.seed is not None:
            torch.manual_seed(self.seed)
        first = self.get()
        if first is None:
            raise ValueError('No text supplied')
        self.talker.live_session = self
        try:
            while first is not None:
                self.ended = False
                self.codes = []
                self.samples_sent = 0
                self.audible = False
                prompt = self.wrapper._tokenize_texts([self.wrapper._build_assistant_text(first)])
                ids = prompt[0][0, 3:-5].tolist()
                if not ids:
                    raise ValueError('Text delta has no tokens')
                self.text_buffer = first
                self.take_group()
                if self.pending.pop(0) != ids[0]:
                    raise ValueError('Prompt/text tokenization mismatch')
                self.text_consumed += 1
                self.emit('generation_start', {'time': time.perf_counter(),
                          'first_text': first, 'segment': self.segment_id})
                self.wrapper.model.generate(input_ids=prompt, languages=['Chinese'],
                    speakers=[self.speaker], non_streaming_mode=False, max_new_tokens=512,
                    do_sample=getattr(self.wrapper, "stream_do_sample", True), subtalker_dosample=True,
                    top_k=50, top_p=1.0, temperature=0.9, repetition_penalty=1.05)
                self.decode()
                if len(self.codes) >= 511:
                    raise RuntimeError('Codec generation hit limit; audio is incomplete')
                if not self.ended or self.pending or self.text_buffer:
                    raise RuntimeError('Audio ended before text was fully consumed')
                self.total_frames += len(self.codes)
                self.emit('segment_done', {'time': time.perf_counter(),
                          'segment': self.segment_id, 'frames': len(self.codes)})
                self.segment_id += 1
                if self.session_ended:
                    break
                first = self.get()
            self.emit('done', {'time': time.perf_counter(), 'frames': self.total_frames,
                              'segments': self.segment_id,
                              'text_tokens_consumed': self.text_consumed, 'pad_steps': self.pad_steps})
        finally:
            self.talker.live_session = None
