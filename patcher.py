#!/usr/bin/env python3
"""NFS SE Enhanced patcher: checks a DOS installation of Need for Speed SE and generates the
hi-res executables and data files next to the originals (which stay untouched).

    python3 patcher.py <game folder> [--res 1024 1280] [--steer 2] [--view extended|original]
"""
import argparse,hashlib,os,shlex,sys,time
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'nfsse'))
from ui import UI,clock
from version import VERSION
REPO='https://github.com/sebauer/nfsse-enhanced'
COFFEE='https://buymeacoffee.com/sebauer'

SHA_CD='7d2104a9eae01ca7b74807ab66334e3ce806d7a9ca3057a9f886932533c6f815'    # CD NFS_DOS.EXE = clean install
SHA_86='86f80829727fd311387a69c55613a3332de4a2df27a350502d9bce1d1011df6a'    # variant all in-game tests used
VIDEO_BPP=0x607e6   # code 0x341e6: video player mode set 320x200, bpp 0 (=16, hicolor) in the CD EXE, 8 in 86f8

RES={1024:('J',1024,768),1280:('K',1280,960)}   # tag, W, H (1280: VESA mode 0x22B, exe.build default)
VIEW={'extended':dict(lod=2,segs=80,cardepth=0x7fff0000,draw=32,near=12,detail=6,traffic=(50,6,13)),
      'original':dict(lod=1,segs=35,cardepth=None,draw=28,near=4,detail=None,traffic=None)}
LANG={'ENGLISH':('ART','DASH'),'GERMAN':('GART','GDASH')}   # (FRONTEND/<art>, SIMDATA/<dash>)

class Refuse(Exception): pass

def load_deps():
    missing=[]
    for mod,pkg in (('numpy','numpy'),('scipy','scipy'),('PIL','Pillow')):
        try: __import__(mod)
        except ImportError: missing.append(pkg)
    if missing: raise Refuse('missing Python packages: '+' '.join(missing)+'\n  install with: python3 -m pip install '+' '.join(missing))
    global exe,hud,masks,cockpit,tickets,title
    import exe,hud,masks,cockpit,tickets,title

def read_exe(game,keep_video):
    p=os.path.join(game,'NFS.EXE')
    if not os.path.isfile(p): raise Refuse(f'{p} not found - is this the NFS SE game folder?')
    d=bytearray(open(p,'rb').read()); h=hashlib.sha256(d).hexdigest()
    if h==SHA_86: return bytes(d),'86f8 variant'
    if h!=SHA_CD:
        raise Refuse('NFS.EXE is not a supported version (sha256 '+h+').\n'
                     '  Supported: the DOS executable of the 1996 CD release (English/German). The Windows 95\n'
                     '  version (NFS_WIN.EXE) and other releases are not supported.')
    if keep_video: return bytes(d),'CD original'
    assert d[VIDEO_BPP-1:VIDEO_BPP+1]==b'\x6a\x00'; d[VIDEO_BPP]=8
    assert hashlib.sha256(d).hexdigest()==SHA_86
    return bytes(d),'CD original (video mode byte normalised to the tested 86f8 variant)'

def cfg_language(game):
    try: words=open(os.path.join(game,'NFS.CFG'),'rb').read().decode('latin1').upper().split()
    except OSError: return None
    return next((w for w in words if w in LANG),None)

def languages(game):
    """the NFS.CFG language plus every other language whose folders exist"""
    langs=[l for l,(art,dash) in LANG.items() if os.path.isdir(os.path.join(game,'FRONTEND',art)) or os.path.isdir(os.path.join(game,'SIMDATA',dash))]
    cl=cfg_language(game)
    if cl and cl not in langs: langs.insert(0,cl)
    if not langs: raise Refuse('no English (FRONTEND/ART) or German (FRONTEND/GART) installation found')
    return langs,cl

def required(langs):
    req=[('SIMDATA','MISC','MASKHI.FSH'),('SIMDATA','MISC','MASKHIG.FSH'),('SIMDATA','MISC','MASKHI.MMB')]
    req+=[('SIMDATA','MISC',f'MASKHI.B{v}{p}') for v in range(3) for p in range(4)]
    req+=[('SIMDATA','MISC',n+'.QFS') for n in tickets.NAMES]
    for l in langs:
        art,dash=LANG[l]
        req+=[('SIMDATA',dash,car+'DH.'+ext) for car in cockpit.CARS for ext in ('FSH','FMM')]
        req+=[('FRONTEND',art,'TITLE.QFS'),('FRONTEND',art,'FONTS','GRAVER18.FFN')]
    return req

def check_install(game,langs):
    missing=[os.path.join(*r) for r in required(langs) if not os.path.isfile(os.path.join(game,*r))]
    if missing:
        raise Refuse(f'{len(missing)} required file(s) missing, e.g.\n    '+'\n    '.join(missing[:8])+'\n'
                     '  The patch needs a FULL installation: run the game setup again, choose "Custom" and\n'
                     '  select ALL components.')

# --- jobs: module-level functions so worker processes can run them (spawn on Windows/macOS) ---
def job_title(game,out): import title; title.build_all(game,out,VERSION)
def job_exe(exe_bytes,path,W,H,tag,steer,view): import exe; exe.build(exe_bytes,path,W,H,tag,steer=steer,**VIEW[view])
def job_hud(misc_in,tag,W,H,misc_out): import hud; hud.build_all(misc_in,tag,W,H,misc_out)
def job_masks(misc_in,tag,W,H,misc_out): import masks; masks.build_all(misc_in,tag,W,H,misc_out)
def job_ticket(misc_in,tag,W,H,misc_out,name): import tickets; tickets.build_all(misc_in,tag,W,H,misc_out,[name])
def job_cockpit(tag,W,H,car,src,dst):
    import cockpit; cockpit.SRC,cockpit.OUT=src,dst; cockpit.lanczos(car,tag,W,H)
_Q=None   # worker -> main queue: (job index, start time), for the live display
def _init(q):
    global _Q; _Q=q
def timed(fn,args,i=None):
    t=time.time()
    if _Q is not None: _Q.put((i,t))
    fn(*args); return time.time()-t

def jobs(game,out,res,steer,view,exe_bytes,langs):
    """independent jobs (label, function, args, files written), slowest first; each writes only its own files"""
    misc_in=os.path.join(game,'SIMDATA','MISC')+os.sep; misc_out=os.path.join(out,'SIMDATA','MISC')+os.sep
    J=[]; P=os.path.join
    for r in sorted(res,reverse=True):
        tag,W,H=RES[r]
        for l in langs:
            dash=LANG[l][1]; src=P(game,'SIMDATA',dash)+os.sep; dst=P(out,'SIMDATA',dash)+os.sep
            for car in cockpit.CARS:
                J.append((f'cockpit {car} {W}x{H} ({dash})',job_cockpit,(tag,W,H,car,src,dst),[P('SIMDATA',dash,car+'D'+tag+e) for e in ('.FSH','.FMM')]))
    for r in sorted(res,reverse=True):
        tag,W,H=RES[r]
        for n in tickets.NAMES:
            J.append((f'screen {n[:-1]+tag} {W}x{H}',job_ticket,(misc_in,tag,W,H,misc_out,n),[P('SIMDATA','MISC',n[:-1]+tag+'.QFS')]))
    for r in sorted(res,reverse=True):
        tag,W,H=RES[r]; name=f'NFS{r}.EXE'
        J.append((f'{name}',job_exe,(exe_bytes,P(out,name),W,H,tag,steer,view),[name]))
        J.append((f'HUD {W}x{H}',job_hud,(misc_in,tag,W,H,misc_out),[P('SIMDATA','MISC',f'MASKH{tag}{g}.FSH') for g in ('','G')]))
        J.append((f'blit masks {W}x{H}',job_masks,(misc_in,tag,W,H,misc_out),
                  [P('SIMDATA','MISC',f'MASKH{tag}.B{v}{p}') for v in range(3) for p in range(4)]+[P('SIMDATA','MISC',f'MASKH{tag}.MMB')]))
    J.append(('title screen',job_title,(game,out),[P('FRONTEND',LANG[l][0],title.OUTNAME) for l in langs]))
    return J

def default_workers(): return max(1,(os.cpu_count() or 2)//2)   # half the cores: parallel, but leave the machine usable

def generate(J,workers,ui):
    """run the jobs (in a process pool if workers>1); returns the files written"""
    made=[]; pr=ui.progress([lab for lab,*_ in J])
    if workers<=1:
        for i,(lab,fn,args,files) in enumerate(J):
            pr.start(i); dt=timed(fn,args); made+=files; pr.finish(i,dt)
        pr.end(); return made
    import multiprocessing,queue
    from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
    ctx=multiprocessing.get_context(); q=ctx.Queue()
    with ProcessPoolExecutor(workers,mp_context=ctx,initializer=_init,initargs=(q,)) as ex:
        fut={ex.submit(timed,fn,args,i):i for i,(lab,fn,args,files) in enumerate(J)}; pending=set(fut)
        try:
            while pending:
                fin,pending=wait(pending,timeout=0.1,return_when=FIRST_COMPLETED)
                while True:
                    try: pr.start(*q.get_nowait())
                    except queue.Empty: break
                for f in fin:
                    i=fut[f]; dt=f.result(); made+=J[i][3]; pr.finish(i,dt)
                pr.draw()
        except BaseException:
            for f in fut: f.cancel()
            pr.end(); raise
    pr.end(); return made

def notes(ui,res):
    ui.head('DOSBox-X configuration (dosbox-x.conf)')
    ui.p(ui.c('2','    Tested mainly with DOSBox-X; other DOSBox versions may work but are untested.'))
    ui.p('    [dosbox]'); ui.p('    machine = svga_s3')
    ui.p('    memsize = 64' if 1280 in res else '    memsize = 32       (64 if you also want 1280x960)')
    if 1280 in res:
        for l in ('[video]','allow unusual vesa modes   = true','vesa modelist width limit  = 1280','vesa modelist height limit = 1024'): ui.p('    '+l)
    ui.p('    [cpu]'); ui.p('    cycles = max')
    ui.p(); ui.head('In the game')
    ui.p('    Options > Graphic Details > Resolution must be 640x480.')
    ui.p('    Start the race with '+' or '.join(f'NFS{r}.EXE' for r in res)+' instead of NFS.EXE.')

def ask_options(ui,a):
    """ask for the build options not given on the command line"""
    ui.p(); ui.head('Build options')
    if a.res is None:
        a.res=ui.choose('Resolution',[([1024],'1024x768'),([1280],'1280x960   (DOSBox-X: memsize = 64 and VESA settings, shown at the end)'),
                                      ([1024,1280],'both (recommended)')],3)
    if a.steer is None:
        a.steer=ui.choose('Keyboard steering (joystick/wheel are not affected)',[(1,'original'),(2,'2x faster (recommended)'),
                                      (3,'3x faster (not recommended: scrubs off too much speed in corners)'),
                                      (4,'4x faster (not recommended: scrubs off too much speed in corners)')],2)
    if a.view is None:
        a.view=ui.choose('View distance, car visibility and traffic',[('extended','extended (recommended)'),('original','original')],1)

def clean_path(s):
    """a folder typed or dragged into the terminal: macOS escapes spaces (mac\\ data), Windows adds quotes"""
    s=s.strip()
    if os.name!='nt':
        try: t=shlex.split(s)
        except ValueError: t=[]
        if len(t)==1: s=t[0]
    return os.path.expanduser(s.strip().strip('"\''))

def ask_game(ui):
    ui.p('  Which folder is the game installed in? (type the path or drag the folder into this window)')
    while True:
        g=clean_path(ui.ask('Game folder:') or '')
        if g and os.path.isfile(os.path.join(g,'NFS.EXE')): return g
        ui.p(f'    {"no NFS.EXE in " + g if g else "please enter a folder"}')

def main(argv=None):
    ap=argparse.ArgumentParser(description=f'NFS SE Enhanced v{VERSION} - hi-res patch for Need for Speed SE (DOS)')
    ap.add_argument('game',nargs='?',help='game folder (contains NFS.EXE); asked for if missing')
    ap.add_argument('--res',type=int,nargs='+',choices=sorted(RES),help='resolution(s) to build (default: both)')
    ap.add_argument('--steer',type=int,choices=(1,2,3,4),help='keyboard steering speed factor, 1 = original (default: 2)')
    ap.add_argument('--view',choices=sorted(VIEW),help='extended view distance, car visibility and traffic window, or original (default: extended)')
    ap.add_argument('-y','--yes',action='store_true',help='do not ask: use the defaults for options not given')
    ap.add_argument('--check',action='store_true',help='only check the installation, write nothing')
    ap.add_argument('--jobs',type=int,default=default_workers(),help=f'parallel jobs (default: half the CPU cores, here {default_workers()})')
    ap.add_argument('--out',help='write the generated files to this folder instead of the game folder (testing)')
    ap.add_argument('--keep-video-mode',action='store_true',help=argparse.SUPPRESS)   # do not normalise the CD EXE to 86f8
    a=ap.parse_args(argv)
    if a.game is None and not sys.stdin.isatty(): ap.error('the game folder is required')
    ui=UI()
    ui.logo(f'v{VERSION} - hi-res patch for Need for Speed SE (DOS)'); ui.p()
    ui.head('Checking your installation')
    if a.game is None:
        try: a.game=ask_game(ui)
        except (KeyboardInterrupt,EOFError): ui.p(); ui.error('aborted, nothing written'); return 130
    game=os.path.abspath(a.game); out=os.path.abspath(a.out) if a.out else game
    ui.p('    Verifying installation ...')
    try:
        load_deps()
        exe_bytes,variant=read_exe(game,a.keep_video_mode)
        langs,cl=languages(game); check_install(game,langs)
    except Refuse as e:
        ui.error(str(e)); return 1
    ui.info('Game folder',game)
    ui.info('NFS.EXE',variant)
    ui.info('Language',f'{(cl or "?").title()} (NFS.CFG); generating for: {", ".join(l.title() for l in langs)}')
    ui.ok('Game installation verified')
    if a.check: return 0
    interactive=not a.yes and sys.stdin.isatty(); asked=interactive and None in (a.res,a.steer,a.view)
    try:
        if asked: ask_options(ui,a)
        res=sorted(set(a.res or RES)); a.steer=a.steer or 2; a.view=a.view or 'extended'
        J=jobs(game,out,res,a.steer,a.view,exe_bytes,langs); w=max(1,min(a.jobs,len(J)))
        existing=[f for *_,files in J for f in files if os.path.exists(os.path.join(out,f))]
        if existing:
            if not asked: ui.p()
            ui.warn(f'{len(existing)} of the {sum(len(j[3]) for j in J)} patch files already exist (earlier run) and will be replaced.')
        if interactive and (asked or existing) and not ui.confirm('Replace them and start patching?' if existing else 'Start patching?'):
            ui.p('  Nothing written.'); return 0
    except (KeyboardInterrupt,EOFError):
        ui.p(); ui.error('aborted, nothing written'); return 130
    ui.p(); ui.head('Building '+' and '.join(f'{RES[r][1]}x{RES[r][2]}' for r in res)+f' ({len(J)} jobs, {w} in parallel)')
    ui.info('Options',f'keyboard steering x{a.steer}, view {a.view}')
    if out!=game: ui.info('Output',out)
    for d in {os.path.dirname(os.path.join(out,f)) for *_,files in J for f in files}: os.makedirs(d,exist_ok=True)
    t=time.time(); made=generate(J,w,ui)
    ui.ok(f'{len(made)} files written in {clock(time.time()-t)}, original files unchanged')
    ui.p(); ui.p(ui.c('1;32','  Success! Your game is patched. Start your engines - let\'s race!')); ui.p()
    notes(ui,res)
    ui.p(); ui.p(f'  Questions, problems or feedback? Visit {ui.c("1;4",REPO)}')
    ui.p(f'  {"☕ " if ui.uni else ""}Enjoying the patch? Buy me a coffee: {ui.c("1;4",COFFEE)}  {ui.c("2","(entirely optional)")}'); ui.p()
    return 0

if __name__=='__main__': sys.exit(main())
