import os,re,json,time,base64,logging,shutil
from pathlib import Path
from dataclasses import dataclass,asdict
from typing import List,Tuple
import numpy as np
try:
    import cv2
except ImportError:
    cv2=None
try:
    import whisper
except ImportError:
    whisper=None
try:
    from google import genai
    from google.genai import types as gtypes
except ImportError:
    genai=None;gtypes=None
try:
    import easyocr
except ImportError:
    easyocr=None
from src.utils import run_ffmpeg,get_video_resolution,get_video_duration
logger=logging.getLogger(__name__)
FI=0.1
@dataclass
class SubtitleEntry:
    start:float;end:float;text:str;speaker:str;style:str;confidence:float=1.0
    def to_dict(self):return asdict(self)
class SubtitleRecognizer:
    DIFF_TH=15.0;BRIGHT_TH=150
    def __init__(s,config):
        tc=config["transcription"];s.wm=tc["whisper_model"];s.lang=tc["language"]
        s.ocr_engine=tc.get("ocr_engine","gemini");s.srr=tc["subtitle_region_ratio"]
        s.bs=tc.get("batch_size",4);s.mr=tc.get("max_retries",3)
        s.td=config["paths"]["temp_dir"];s._g=None;s._gm=tc.get("gemini_model","gemini-2.0-flash")
        gk=tc.get("gemini_api_key","") or os.environ.get("GEMINI_API_KEY","")
        if gk and genai:s._g=genai.Client(api_key=gk)
        s._wm=None;s._or=None
    def recognize(s,vp):
        logger.info(f"OCR 0.1s: {vp}");ws=s._whisper(vp);logger.info(f"Whisper:{len(ws)}")
        os_=s._smart_ocr(vp) if s.ocr_engine=="gemini" and s._g else s._easyocr(vp)
        logger.info(f"OCR:{len(os_)}");return s._merge(ws,os_)
    def _smart_ocr(s,vp):
        w,h=get_video_resolution(vp);sy=int(h*(1-s.srr));sh=h-sy
        fd=os.path.join(s.td,"f01");os.makedirs(fd,exist_ok=True)
        try:
            run_ffmpeg(["-i",str(vp),"-vf",f"fps=10,crop=iw:{sh}:0:{sy}","-q:v","3",os.path.join(fd,"f_%07d.jpg")],timeout=1800)
            ff=sorted(Path(fd).glob("f_*.jpg"))
            if not ff:return []
            logger.info(f"{len(ff)} frames");cp=s._detect(ff);logger.info(f"{len(cp)} changes")
            if not cp:return []
            oc=s._ocr_cp(cp,ff);return s._build(oc)
        finally:shutil.rmtree(fd,ignore_errors=True)
    def _detect(s,ff):
        ch=[];pg=None;pt=False
        for i,fp in enumerate(ff):
            f=cv2.imread(str(fp))
            if f is None:continue
            g=cv2.cvtColor(f,cv2.COLOR_BGR2GRAY);br=np.sum(g>s.BRIGHT_TH)/g.size;ht=0.005<br<0.40
            if pg is not None:
                d=np.mean(cv2.absdiff(g,pg))
                if d>s.DIFF_TH:ch.append((i,str(fp)))
                elif ht!=pt:ch.append((i,str(fp)))
            elif ht:ch.append((i,str(fp)))
            pg=g;pt=ht
        return ch
    def _ocr_cp(s,cp,af):
        res=[]
        for bi in range(0,len(cp),s.bs):
            b=cp[bi:bi+s.bs];ps=[c[1] for c in b];ix=[c[0] for c in b];ts=[i*FI for i in ix]
            oc=s._gbr(ps,ts);res.extend([(ix[j],ts[j],oc[j][1],oc[j][2],oc[j][3]) for j in range(len(oc))])
            if bi+s.bs<len(cp):time.sleep(4.5)
        return res
    def _build(s,oc):
        if not oc:return []
        ent=[]
        for i,(idx,ts,tx,sp,sy) in enumerate(oc):
            if not tx:continue
            st=ts;en=oc[i+1][1] if i+1<len(oc) else ts+2.0
            if ent and ent[-1].text==tx:ent[-1].end=round(en,1);continue
            ent.append(SubtitleEntry(start=round(st,1),end=round(en,1),text=tx,speaker=sp,style=sy,confidence=0.95))
        return ent
    def _gbr(s,ps,ts):
        for a in range(s.mr):
            try:return s._gb(ps,ts)
            except Exception as e:
                logger.warning(f"OCR err({a+1}):{e}")
                if a<s.mr-1:time.sleep(2**(a+1))
                else:return [(ts_,"","unknown","normal") for ts_ in ts]
    def _gb(s,ps,ts):
        pa=[gtypes.Part.from_text("以下の画像はYouTube動画の字幕部分です。各画像についてJSON配列で答えてください。テキストなしも含め全画像分返してください。1文字も間違えず正確に読んでください。\n[{\"text\":\"表示テキスト\",\"color\":\"pink/cyan/other\",\"style\":\"normal/emphasis\"},...]\nJSONのみ出力。")]
        for fp in ps:
            with open(fp,"rb") as f:pa.append(gtypes.Part.from_bytes(data=f.read(),mime_type="image/jpeg"))
        r=s._g.models.generate_content(model=s._gm,contents=gtypes.Content(parts=pa,role="user"),config=gtypes.GenerateContentConfig(temperature=0,max_output_tokens=1000))
        m=re.search(r'\[.*\]',r.text.strip(),re.DOTALL)
        if not m:return [(t,"","unknown","normal") for t in ts]
        it=json.loads(m.group());res=[]
        for i,t in enumerate(ts):
            if i<len(it):
                x=it[i];tx=x.get("text","").strip();co=x.get("color","other").lower();sy=x.get("style","normal").lower()
                sp="aya" if "pink" in co else("junpei" if "cyan" in co else "unknown");res.append((t,tx,sp,sy))
            else:res.append((t,"","unknown","normal"))
        return res
    def _easyocr(s,vp):
        if not cv2 or not easyocr:return []
        w,h=get_video_resolution(vp);sy=int(h*(1-s.srr));fd=os.path.join(s.td,"foc");os.makedirs(fd,exist_ok=True)
        try:
            run_ffmpeg(["-i",str(vp),"-vf",f"fps=10,crop=iw:{h-sy}:0:{sy}","-q:v","3",os.path.join(fd,"f_%07d.jpg")],timeout=1800)
            if s._or is None:s._or=easyocr.Reader(["ja","en"],gpu=False)
            pg=None;raw=[]
            for i,fp in enumerate(sorted(Path(fd).glob("f_*.jpg"))):
                ts=i*FI;f=cv2.imread(str(fp))
                if f is None:continue
                g=cv2.cvtColor(f,cv2.COLOR_BGR2GRAY)
                if pg is not None and np.mean(cv2.absdiff(g,pg))<15:pg=g;continue
                pg=g
                if not(0.005<np.sum(g>150)/g.size<0.40):raw.append((ts,"","unknown","normal"));continue
                r=s._or.readtext(str(fp),detail=1,paragraph=True);tx="".join(d[1] for d in r if len(d)>=2).strip() if r else ""
                hsv=cv2.cvtColor(f,cv2.COLOR_BGR2HSV);pk=np.sum(cv2.inRange(hsv,np.array([140,50,150]),np.array([175,255,255]))>0)
                cy=np.sum(cv2.inRange(hsv,np.array([80,50,150]),np.array([100,255,255]))>0)
                sp="aya" if pk>cy and pk>100 else("junpei" if cy>100 else "unknown");raw.append((ts,tx,sp,"normal"))
            return s._grp(raw)
        finally:shutil.rmtree(fd,ignore_errors=True)
    def _whisper(s,vp):
        au=os.path.join(s.td,"a.wav");run_ffmpeg(["-i",str(vp),"-vn","-acodec","pcm_s16le","-ar","16000","-ac","1",au])
        try:
            if s._wm is None:s._wm=whisper.load_model(s.wm)
            r=s._wm.transcribe(au,language=s.lang,word_timestamps=True,verbose=False)
            return[SubtitleEntry(start=x["start"],end=x["end"],text=x["text"].strip(),speaker="unknown",style="normal")for x in r.get("segments",[])if x["text"].strip()]
        finally:
            if os.path.exists(au):os.remove(au)
    def _grp(s,raw):
        ent=[];ct,cs,cy,st,en="","unknown","normal",0.0,0.0
        for ts,tx,sp,sy in raw:
            if tx==ct and tx:en=ts+FI
            else:
                if ct:ent.append(SubtitleEntry(start=round(st,1),end=round(en,1),text=ct,speaker=cs,style=cy,confidence=0.95))
                ct,cs,cy,st,en=tx,sp,sy,ts,ts+FI
        if ct:ent.append(SubtitleEntry(start=round(st,1),end=round(en,1),text=ct,speaker=cs,style=cy,confidence=0.95))
        return ent
    def _merge(s,ws,os_):
        if not os_:return ws
        if not ws:return os_
        mg=list(os_)
        for w in ws:
            if not any(min(w.end,o.end)-max(w.start,o.start)>0.3 for o in os_):mg.append(w)
        mg.sort(key=lambda e:e.start);cl=[]
        for e in mg:
            if not e.text.strip()or e.end-e.start<0.2:continue
            e.text=re.sub(r'\s+',' ',e.text).strip()
            if cl and cl[-1].text==e.text and abs(cl[-1].start-e.start)<0.3:
                if(e.end-e.start)>(cl[-1].end-cl[-1].start):cl[-1]=e
                continue
            cl.append(e)
        return cl
