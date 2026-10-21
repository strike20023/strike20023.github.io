"""Fixed-step cached MTP graph. Single-session only; keeps upstream sampling."""
from types import SimpleNamespace
import torch
from transformers.cache_utils import DynamicCache

@torch.inference_mode()
def install_mtp(talker, verify=False):
    p=talker.code_predictor
    original=p.generate
    n=talker.config.num_code_groups-1
    x=torch.zeros(1,2,talker.config.hidden_size,device=talker.device,dtype=talker.dtype)
    positions=[torch.arange(2,device=x.device)]+[torch.tensor([i+1],device=x.device) for i in range(1,n)]
    def run(sample):
        cache=DynamicCache()
        ids=[]
        for i in range(n):
            args={'inputs_embeds':x} if i==0 else {'input_ids':ids[-1]}
            out=p(**args,past_key_values=cache,use_cache=True,generation_steps=i,
                  cache_position=positions[i],position_ids=positions[i][None],
                  attention_mask={'full_attention':None},output_hidden_states=False,return_dict=True)
            logits=out.logits[:,-1].float()
            if sample:
                logits=logits/.9
                cutoff=torch.topk(logits,50,dim=-1).values[:,-1,None]
                logits=logits.masked_fill(logits<cutoff,-float('inf'))
                token=torch.multinomial(logits.softmax(-1),1)
            else:
                token=logits.argmax(-1,keepdim=True)
            ids.append(token)
        return torch.cat(ids,-1)
    graphs={}
    stream=torch.cuda.Stream()
    stream.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(stream):
        for mode in (False,True):
            for _ in range(3):run(mode)
    torch.cuda.current_stream().wait_stream(stream)
    for mode in (False,True):
        graph=torch.cuda.CUDAGraph()
        with torch.cuda.graph(graph):result=run(mode)
        graphs[mode]=(graph,result)
    checks=0
    def generate(*,inputs_embeds,**kw):
        nonlocal checks
        assert inputs_embeds.shape==x.shape
        assert kw['max_new_tokens']==n
        assert kw.get('top_k',50)==50 and kw.get('top_p',1)==1 and kw.get('temperature',.9)==.9
        x.copy_(inputs_embeds)
        if verify and checks<32:
            expected=original(inputs_embeds=inputs_embeds,max_new_tokens=n,do_sample=False,return_dict_in_generate=True).sequences
            graphs[False][0].replay()
            actual=graphs[False][1].clone()
            eager=run(False)
            if not torch.equal(eager, actual):
                raise RuntimeError('MTP captured/eager mismatch')
            if not torch.equal(expected,actual):
                raise RuntimeError(f'MTP live greedy mismatch: {expected.tolist()} != {actual.tolist()}')
            checks+=1
            if checks==32:print('MTP: 32 real Talker inputs matched upstream greedy',flush=True)
        mode=bool(kw.get('do_sample',True))
        graphs[mode][0].replay()
        return SimpleNamespace(sequences=graphs[mode][1].clone())
    p.generate=generate
    return {'original':original,'graphs':graphs}

class CodecGraph:
    """Causal 25-frame left context, following upstream chunked_decode policy.

    Right-padding is discarded, never emitted. No future text/audio is required.
    Separate graph buffers are retained for their entire lifetime.
    """
    @torch.inference_mode()
    def __init__(self, tokenizer):
        self.decoder=tokenizer.model.decoder.float()
        self.samples=int(self.decoder.total_upsample)
        self.rate=tokenizer.get_output_sample_rate()
        self.graphs={}
        self.checked=0
        for size in (8,16,32):
            codes=torch.zeros(1,self.decoder.config.num_quantizers,size,dtype=torch.long,device=tokenizer.device)
            stream=torch.cuda.Stream();stream.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(stream):
                for _ in range(3):self.decoder(codes)
            torch.cuda.current_stream().wait_stream(stream)
            graph=torch.cuda.CUDAGraph()
            with torch.cuda.graph(graph):out=self.decoder(codes)
            self.graphs[size]=(codes,graph,out)
    @torch.inference_mode()
    def decode_new(self,codes,samples_sent):
        sent=samples_sent//self.samples
        assert samples_sent%self.samples==0
        start=max(0,sent-25)
        selected=torch.stack(codes[start:]).T[None]
        count=selected.shape[-1]
        if count==0:return None
        size=next((s for s in self.graphs if s>=count),None)
        if size is None:
            out=self.decoder(selected)
            return out[0,0,(sent-start)*self.samples:].float().cpu().numpy(),self.rate
        inputs,graph,out=self.graphs[size]
        inputs.zero_();inputs[...,:count].copy_(selected)
        graph.replay()
        pcm=out[0,0,(sent-start)*self.samples:count*self.samples].float().cpu().numpy().copy()
        if self.checked < 8:
            reference=self.decoder(selected)[0,0,(sent-start)*self.samples:].float().cpu().numpy()
            error=float(abs(pcm-reference).max())
            if error > .003:
                raise RuntimeError(f'Codec graph/causal reference mismatch: {error}')
            self.checked+=1
            print(f'Codec real-frame check {self.checked}: max error {error:.8f}',flush=True)
        return pcm,self.rate
