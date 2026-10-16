"""Terminal output for the patcher: brew-style headings and a live progress block (bar, running jobs
with their elapsed time). Without a terminal it falls back to plain lines; NO_COLOR disables colour."""
import os,sys,time,shutil
# title logo (ASCII only): rows 0-3 THE NEED, 4-7 FOR SPEED (+ SE from column 41), 8 SPECIAL EDITION, 9-12 ENHANCED
LOGO=r"""
       ________ ______  _  _____________        __________    ___________
      /_  __/ // / __/ / |/ / __/ __/ _ \      / ________/   / _________/
       / / / _  / _/  /    / _// _// // /     / /           / /
      /_/ /_//_/___/ /_/|_/___/___/____/     / /________   / /______
   ________  ___    _______  ___________    /________/ /  / _______/
  / __/ __ \/ _ \  / __/ _ \/ __/ __/ _ \           / /  / /
 / _// /_/ / , _/ _\ \/ ___/ _// _// // /    ______/ /  / /_________
/_/  \____/_/|_| /___/_/  /___/___/____/    /_______/  /____________/
         S  P  E  C  I  A  L    E  D  I  T  I  O  N
                                   _____  ____ _____   _  ______________
                                  / __/ |/ / // / _ | / |/ / ___/ __/ _ \
                                 / _//    / _  / __ |/    / /__/ _// // /
                                /___/_/|_/_//_/_/ |_/_/|_/\___/___/____/""".split('\n')[1:]
class UI:
    def __init__(s,out=sys.stdout):
        s.o=out; s.live=out.isatty() and os.environ.get('TERM')!='dumb'
        s.color=s.live and 'NO_COLOR' not in os.environ
        if s.live and os.name=='nt': os.system('')   # switches the Windows console to ANSI mode
        try: '█░✔✘⠋'.encode(getattr(out,'encoding',None) or 'ascii'); s.uni=True
        except (UnicodeError,LookupError): s.uni=False
    def c(s,code,t): return f'\x1b[{code}m{t}\x1b[0m' if s.color else t
    def p(s,t=''): print(t,file=s.o,flush=True)
    def logo(s,sub):
        if shutil.get_terminal_size((80,24)).columns<max(map(len,LOGO))+1: s.head('NFS SE Enhanced'); s.p('    '+sub); return
        s.p()
        for i,l in enumerate(LOGO):
            if i<8: s.p(s.c('1;31' if i<4 else '1;33',l[:41])+s.c('1;97',l[41:]))
            else: s.p(s.c('37' if i==8 else '1;36',l))
        s.p(); s.p(s.c('2',f'{sub:>{max(map(len,LOGO))}}'))
    def head(s,t): s.p(s.c('1;34','==>')+' '+s.c('1',t))
    def info(s,k,v): s.p(f'    {k:<13}{v}')
    def ok(s,t): s.p(s.c('1;32','✔' if s.uni else 'OK')+' '+t)
    def error(s,t): print(s.c('1;31','Error:')+' '+t,file=sys.stderr,flush=True)
    def progress(s,labels): return Progress(s,labels)
def clock(t): t=int(t); return f'{t//60}:{t%60:02d}'
class Progress:
    SPIN='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    def __init__(s,ui,labels):
        s.ui=ui; s.labels=labels; s.n=len(labels); s.done=0; s.running={}; s.finished=set()
        s.t0=time.time(); s.tick=0; s.drawn=0; s.wl=max(len(l) for l in labels)
    def start(s,i,t=None):
        if i not in s.finished: s.running[i]=t or time.time()
        s.draw()
    def finish(s,i,dt):
        s.running.pop(i,None); s.finished.add(i); s.done+=1; s.clear(); ui=s.ui
        mark=ui.c('32','✔' if ui.uni else 'OK') if ui.live else f'[{s.done:{len(str(s.n))}}/{s.n}]'
        ui.p(f'  {mark} {s.labels[i]:<{s.wl}}  {ui.c("2",f"{dt:5.1f}s")}'); s.draw()
    def clear(s):
        if s.drawn: s.ui.o.write(f'\x1b[{s.drawn}A\r\x1b[J'); s.drawn=0
    def draw(s):
        ui=s.ui
        if not ui.live: return
        s.clear(); now=time.time(); s.tick+=1
        w=shutil.get_terminal_size((80,24)).columns; bw=max(10,min(40,w-24))
        f=round(bw*s.done/s.n); full,empty=('█','░') if ui.uni else ('#','-')
        lines=[]; spin=(s.SPIN if ui.uni else '|/-\\')
        for k,(i,t) in enumerate(sorted(s.running.items(),key=lambda x:x[1])):
            lab=f'{s.labels[i]:<{s.wl}}'[:max(10,w-12)]   # keep every line shorter than the terminal
            lines.append(f'  {ui.c("36",spin[(s.tick+k)%len(spin)])} {lab}  {ui.c("2",f"{now-t:5.1f}s")}')
        lines.append(f'  {ui.c("32",full*f)}{ui.c("2",empty*(bw-f))} {s.done:>{len(str(s.n))}}/{s.n}  {clock(now-s.t0)}')   # bar stays the bottom line
        ui.o.write('\n'.join(lines)+'\n'); ui.o.flush(); s.drawn=len(lines)
    def end(s): s.clear(); s.ui.o.flush()
