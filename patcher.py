#!/usr/bin/env python3
"""NFS SE Enhanced patcher: checks a DOS installation of Need for Speed SE and generates the
hi-res executables and data files next to the originals (which stay untouched).

    python3 patcher.py <game folder> [--res 1024 1280] [--steer 2] [--view extended|original]
"""
import argparse,hashlib,os,sys
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'nfsse'))
VERSION='0.9'

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

def generate(game,out,res,steer,view,exe_bytes,langs,log=print):
    made=[]
    def done(*p): made.append(os.path.join(*p))
    misc_in=os.path.join(game,'SIMDATA','MISC')+os.sep; misc_out=os.path.join(out,'SIMDATA','MISC')+os.sep
    os.makedirs(misc_out,exist_ok=True)
    for sub in title.build_all(game,out,VERSION): done('FRONTEND',sub,title.OUTNAME)
    log('title screen: '+', '.join(made))
    for r in res:
        tag,W,H=RES[r]; name=f'NFS{r}.EXE'
        log(f'--- {W}x{H} ---')
        exe.build(exe_bytes,os.path.join(out,name),W,H,tag,steer=steer,**VIEW[view]); done(name); log(name)
        hud.build_all(misc_in,tag,W,H,misc_out); done('SIMDATA','MISC',f'MASKH{tag}.FSH'); done('SIMDATA','MISC',f'MASKH{tag}G.FSH')
        masks.build_all(misc_in,tag,W,H,misc_out)
        for v in range(3):
            for p in range(4): done('SIMDATA','MISC',f'MASKH{tag}.B{v}{p}')
        done('SIMDATA','MISC',f'MASKH{tag}.MMB'); log('HUD and blit masks')
        tickets.build_all(misc_in,tag,W,H,misc_out)
        for n in tickets.NAMES: done('SIMDATA','MISC',n[:-1]+tag+'.QFS')
        log('ticket / warning screens')
        for l in langs:
            dash=LANG[l][1]; src=os.path.join(game,'SIMDATA',dash)+os.sep; dst=os.path.join(out,'SIMDATA',dash)+os.sep
            os.makedirs(dst,exist_ok=True)
            for car in cockpit.CARS:
                cockpit.build_all(tag,W,H,[car],src,dst)
                done('SIMDATA',dash,car+'D'+tag+'.FSH'); done('SIMDATA',dash,car+'D'+tag+'.FMM')
            log(f'cockpits ({dash})')
    return made

def dosbox_notes(res):
    s=['','DOSBox-X configuration:','  [dosbox]','  machine = svga_s3',
       '  memsize = 64' if 1280 in res else '  memsize = 32        (64 if you also want 1280x960)']
    if 1280 in res:
        s+=['  [video]','  allow unusual vesa modes   = true','  vesa modelist width limit  = 1280','  vesa modelist height limit = 1024']
    s+=['  [cpu]','  cycles = max','',
        'In the game: Options > Graphic Details > Resolution must be 640x480.',
        'Start the race with '+' or '.join(f'NFS{r}.EXE' for r in res)+' instead of NFS.EXE.']
    return '\n'.join(s)

def main(argv=None):
    ap=argparse.ArgumentParser(description=f'NFS SE Enhanced v{VERSION} - hi-res patch for Need for Speed SE (DOS)')
    ap.add_argument('game',help='game folder (contains NFS.EXE)')
    ap.add_argument('--res',type=int,nargs='+',choices=sorted(RES),default=sorted(RES),help='resolution(s) to build (default: both)')
    ap.add_argument('--steer',type=int,choices=(1,2,3,4),default=2,help='keyboard steering speed factor, 1 = original (default: 2)')
    ap.add_argument('--view',choices=sorted(VIEW),default='extended',help='extended view distance, car visibility and traffic window, or original (default: extended)')
    ap.add_argument('--check',action='store_true',help='only check the installation, write nothing')
    ap.add_argument('--out',help='write the generated files to this folder instead of the game folder (testing)')
    ap.add_argument('--keep-video-mode',action='store_true',help=argparse.SUPPRESS)   # do not normalise the CD EXE to 86f8
    a=ap.parse_args(argv)
    game=os.path.abspath(a.game); out=os.path.abspath(a.out) if a.out else game; res=sorted(set(a.res))
    try:
        load_deps()
        exe_bytes,variant=read_exe(game,a.keep_video_mode)
        langs,cl=languages(game); check_install(game,langs)
    except Refuse as e:
        print('ERROR:',e,file=sys.stderr); return 1
    print(f'NFS SE Enhanced v{VERSION}')
    print(f'game folder : {game}')
    print(f'NFS.EXE     : {variant}')
    print(f'language    : {cl or "?"} (NFS.CFG); generating for: {", ".join(langs)}')
    print('installation: complete')
    if a.check: return 0
    print(f'options     : {", ".join(f"{r}" for r in res)}; steering x{a.steer}; view {a.view}')
    if out!=game: print(f'output      : {out}')
    made=generate(game,out,res,a.steer,a.view,exe_bytes,langs)
    print(f'\ndone: {len(made)} files written, original files unchanged.')
    print(dosbox_notes(res))
    return 0

if __name__=='__main__': sys.exit(main())
