import os,re,json,time,logging
from dataclasses import dataclass
logger=logging.getLogger(__name__)
try:
    from google import genai
    from google.genai import types as gtypes
except ImportError:
    genai=None;gtypes=None
@dataclass
class ClipSegment:
    start:float;end:float;subtitles:list;score:float=0.0;topic_summary:str="";reason:str=""
    @property
    def duration(s):return s.end-s.start
class TopicSegmenter:
    TB=["で","でさ","というわけで","次","じゃあ","ところで","ちなみに","あと","それで","最後に"]
    VW=["やばい","マジ","笑","可愛い","無理","神","最高","おもろい","怖い","泣く","エモい"]
    def __init__(s,config):
        s.mn=config["clips"]["min_duration"];s.mx=config["clips"]["max_duration"];s.cc=config["clips"]["count"]
        tc=config["transcription"];s._g=None;s._gm=tc.get("gemini_model","gemini-2.0-flash")
        gk=tc.get("gemini_api_key","")or os.environ.get("GEMINI_API_KEY","")
        if gk and genai:s._g=genai.Client(api_key=gk)
    def select_clips(s,subs,vp,pref=None):
        if not subs:return[]
        if s._g:
            c=s._gem(subs,pref)
            if c:return c
            logger.warning("Gemini失敗,fallback")
        return s._rules(subs,pref)
    def _gem(s,subs,pref=None):
        ln=[f"[{x.start:.1f}-{x.end:.1f}] {{\"aya\":\"綾\",\"junpei\":\"純平\"}.get(x.speaker,'?')}: {x.text}" for x in subs]
        tr="\n".join(ln)
        bo=""
        if pref:
            kw=pref.get("boost_keywords",[])
            if kw:bo+=f"\n過去バズキーワード:{",".join(kw)}"
            pd=pref.get("preferred_duration",0)
            if pd:bo+=f"\n過去バズ平均:{pd}s"
        pr=(f"あなたはプロの切り抜き動画クリエイターです。以下は中町兄妹(YouTube)の全字幕です。\n\n{tr}\n\n"
            f"「それだけ見ても面白い」切り抜きを3本作ります。\n"
            f"【絶対条件】\n- {s.mn}-{s.mx}秒\n- 話の途中で絶対に切らない\n- 3本重複なし\n\n"
            "【オチの定義-最重要】\n切り抜き動画はオチが全てです。以下のいずれかで終わるクリップを選んでください:\n"
            "- 笑いのオチ:ツッコミ,ボケ,予想外の展開で笑える\n- 感動のオチ:良い話,兄妹愛\n"
            "- 驚きのオチ:衡撃の告白,予想外の事実\n- 共感のオチ:「わかる～」な日常話\n"
            "オチなしはNG。\n\n【構成】各1クリップ:フリ(導入)→展開→オチ\n"
            f"【優先】兄妹の掛け合い,リアクション大,SNSシェアされそう{bo}\n\n"
            "【出力】JSON配列のみ。\n"
            '[{"start":秒,"end":秒,"topic":"","punchline":"オチ内容","reason":"","score":1-10},...]')
        for a in range(3):
            try:
                r=s._g.models.generate_content(model=s._gm,contents=gtypes.Content(parts=[gtypes.Part.from_text(pr)],role="user"),config=gtypes.GenerateContentConfig(temperature=0.3,max_output_tokens=2000))
                m_=re.search(r'\[.*\]',r.text.strip(),re.DOTALL)
                if not m_:continue
                it=json.loads(m_.group());cl=[]
                for x in it[:s.cc]:
                    st,en=float(x["start"]),float(x["end"])
                    if en-st<s.mn:en=st+s.mn
                    if en-st>s.mx:en=st+s.mx
                    cs=[sub for sub in subs if sub.start>=st and sub.end<=en]
                    cl.append(ClipSegment(start=st,end=en,subtitles=cs,score=float(x.get("score",5)),topic_summary=x.get("topic",""),reason=x.get("reason","")))
                if cl:
                    for i,c in enumerate(cl):logger.info(f"  Clip{i+1}:{c.start:.0f}-{c.end:.0f}s({c.duration:.0f}s) 「{c.topic_summary}」")
                    return cl
            except Exception as e:
                logger.warning(f"Gemini err({a+1}):{e}")
                if a<2:time.sleep(2**a)
        return[]
    def _rules(s,subs,pref=None):
        b=[0]
        for i in range(1,len(subs)):
            if subs[i].start-subs[i-1].end>2.0:b.append(i);continue
            for w in s.TB:
                if subs[i].text.startswith(w):b.append(i);break
        b.append(len(subs));b=sorted(set(b));ca=[]
        for i in range(len(b)-1):
            for j in range(i+1,len(b)):
                sl=subs[b[i]:b[j]]
                if not sl:continue
                d=sl[-1].end-sl[0].start
                if s.mn<=d<=s.mx:ca.append(ClipSegment(start=sl[0].start,end=sl[-1].end,subtitles=sl))
                if d>s.mx:break
        for c in ca:
            tx=" ".join(x.text for x in c.subtitles);sc=sum(3.0 for w in s.VW if w in tx)
            sc+=sum(2.0 for i in range(1,len(c.subtitles))if c.subtitles[i].speaker!=c.subtitles[i-1].speaker and c.subtitles[i].speaker!="unknown")
            if 30<=c.duration<=45:sc+=5.0
            c.score=sc;c.topic_summary=tx[:50]
        ca.sort(key=lambda c:c.score,reverse=True);se=[]
        for c in ca:
            if not any(not(c.end<=x.start or c.start>=x.end)for x in se):se.append(c)
            if len(se)>=s.cc:break
        return se
