"""Isolated synchronized component timings; no production monkey patches."""
import json,os,time,threading
from pathlib import Path
import numpy as np
import torch
from qwen_tts import Qwen3TTSModel
from streaming import LiveSession,install_adapter

torch.set_num_threads(1)
model=Qwen3TTSModel.from_pretrained(os.environ['MODEL'],device_map='cuda:0',dtype=torch.bfloat16,attn_implementation='sdpa')
install_adapter(model.model.talker)
parts={}
def timed(obj,name,label):
    original=getattr(obj,name)
    def call(*args,**kwargs):
        torch.cuda.synchronize(); start=time.perf_counter()
        result=original(*args,**kwargs)
        torch.cuda.synchronize(); parts.setdefault(label,[]).append(time.perf_counter()-start)
        return result
    setattr(obj,name,call)
timed(model.model.talker.code_predictor,'generate','residual_predictor')
timed(model.model.speech_tokenizer,'decode','codec_decode')
root=Path('outputs/profile-strict');root.mkdir(parents=True,exist_ok=True)
for index,hold in enumerate([False,False,True]):
    parts.clear();events=[];chunks=[];origin=time.perf_counter()
    def emit(kind,data):
        elapsed=(time.perf_counter()-origin)*1000
        if kind=='audio':
            wav=data['pcm'];chunks.append(wav)
            events.append({'type':kind,'ms':elapsed,'peak':float(np.max(np.abs(wav))),'samples':len(wav)})
        else:events.append({'type':kind,'ms':elapsed})
    s=LiveSession(model,emit,4,starvation='segment',seed=42)
    text='你好，欢迎测试。今天我们测试首字朗读和持续音频生成的速度。'
    s.feed(text[:1] if hold else text)
    def later():
        time.sleep(3);s.feed(text[1:]);s.end()
    if hold:threading.Thread(target=later).start()
    else:s.end()
    s.run();total=time.perf_counter()-origin
    result={'index':index,'hold':hold,'total_s':total,'audio_s':sum(len(x) for x in chunks)/24000,'first_pcm_ms':next(e['ms'] for e in events if e['type']=='audio'),'first_nonquiet_ms':next(e['ms'] for e in events if e['type']=='audio' and e['peak']>.01),'parts':{k:{'count':len(v),'sum_s':sum(v),'median_ms':float(np.median(v))*1000} for k,v in parts.items()},'events':events}
    (root/f'{index}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='events'},ensure_ascii=False),flush=True)
