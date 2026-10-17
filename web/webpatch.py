"""Browser glue (runs in Pyodide inside a web worker): the CLI patcher's checks and jobs, driven from
JavaScript. The worker copies the needed game files to GAME (in-memory file system), the jobs write to
OUT, and the worker hands the results back to the page."""
import os,sys,time
sys.path[:0]=['/py','/py/nfsse']
import patcher
from version import VERSION
GAME='/game'; OUT='/out'
_state={}

def candidates():
    """every file the patcher may read (both languages); the page copies those that exist"""
    patcher.load_deps()
    req=['NFS.EXE','NFS.CFG']+['/'.join(r) for r in patcher.required(list(patcher.LANG))]
    dirs=['FRONTEND/'+art for art,_ in patcher.LANG.values()]+['SIMDATA/'+dash for _,dash in patcher.LANG.values()]
    return {'files':sorted(set(req)),'dirs':dirs}

def check():
    """verify NFS.EXE and the installation in GAME; {'ok':..., 'error'|'variant','language','langs'}"""
    try:
        patcher.load_deps()
        exe_bytes,variant=patcher.read_exe(GAME,False)
        langs,cl=patcher.languages(GAME); patcher.check_install(GAME,langs)
    except patcher.Refuse as e:
        return {'ok':False,'error':str(e).replace(GAME+'/','').replace(GAME,'the game folder')}
    _state.update(exe=exe_bytes,langs=langs)
    return {'ok':True,'variant':variant,'language':(cl or '?').title(),'langs':[l.title() for l in langs],'version':VERSION}

def plan(res,steer,view):
    """build the job list; [{'label','files'}] (paths relative to the game folder)"""
    J=patcher.jobs(GAME,OUT,sorted(res),steer,view,_state['exe'],_state['langs'])
    for d in {os.path.dirname(os.path.join(OUT,f)) for *_,files in J for f in files}: os.makedirs(d,exist_ok=True)
    _state['jobs']=J
    return [{'label':lab,'files':files} for lab,_,_,files in J]

def notes(res):
    """the DOSBox-X / in-game notes, as the CLI prints them (plain text)"""
    import io
    from ui import UI
    buf=io.StringIO(); patcher.notes(UI(buf),sorted(res)); return buf.getvalue()

def run(i):
    """run job i; returns its time in seconds"""
    lab,fn,args,files=_state['jobs'][i]
    t=time.time(); fn(*args); return time.time()-t
