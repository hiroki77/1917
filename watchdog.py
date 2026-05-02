#!/usr/bin/env python3
import os,sys,time,subprocess,logging
PD=os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(PD,"logs"),exist_ok=True)
logging.basicConfig(level=logging.INFO,format="%(asctime)s [WD] %(message)s",
    handlers=[logging.FileHandler(os.path.join(PD,"logs/watchdog.log"),encoding="utf-8"),logging.StreamHandler()])
log=logging.getLogger()
def run():
    r,w=0,10
    while r<50:
        log.info(f"main.py start (#{r})")
        try:
            res=subprocess.run([sys.executable,"main.py"],cwd=PD)
            if res.returncode==0:log.info("done");break
            else:log.warning(f"exit {res.returncode}")
        except KeyboardInterrupt:log.info("stopped");break
        except Exception as e:log.error(f"crash:{e}")
        r+=1;log.info(f"restart in {w}s");time.sleep(w);w=min(w*2,300)
    if r>=50:log.error("max restarts")
if __name__=="__main__":run()
