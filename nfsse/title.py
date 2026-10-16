"""Title screen stamp: writes a credit line onto the user's own TITLE.QFS (font GRAVER18.FFN
from the same installation, white with black drop shadow like the original credits)."""
import sys,os,struct,numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import qfs,fsh,ffn
from version import VERSION
TEXT='Enhanced Patch v{v} \xa92026 by github.com/sebauer'
def stamp(title_qfs,font_ffn,text=None,y=None,shadow=2,scale=0.85):
    u=bytearray(qfs.decode(open(title_qfs,'rb').read())); o=fsh.shapes(bytes(u))['bgnd']
    _,px,pal=fsh.image(bytes(u),o); h,w=px.shape
    text=text or TEXT.format(v=VERSION)
    a=ffn.render(ffn.load(font_ffn),text)
    if scale!=1:
        from PIL import Image
        im=Image.fromarray((a*255).astype(np.uint8)); im=im.resize((round(a.shape[1]*scale),round(a.shape[0]*scale)),Image.LANCZOS)
        a=np.asarray(im).astype(np.float32)/255
    th,tw=a.shape
    x0=(w-tw)//2; y0=y if y is not None else 424
    rgb=pal[px].astype(np.float32)
    for dx,dy,col in ((shadow,shadow,0.0),(0,0,255.0)):
        sl=rgb[y0+dy:y0+dy+th,x0+dx:x0+dx+tw]; al=a[...,None]; sl[:]=sl*(1-al)+col*al
    P=pal[:255].astype(np.float32); touched=np.zeros((h,w),bool)
    touched[y0:y0+th+shadow,x0:x0+tw+shadow]=True
    sub=rgb[touched]; q=fsh.quant(sub,P)
    newpx=px.copy(); newpx[touched]=q
    u[o+16:o+16+w*h]=newpx.tobytes()
    return qfs.pack(bytes(u)),pal[newpx]
OUTNAME='TITLEE.QFS'   # loaded by the patched EXEs instead of TITLE.QFS
def build_all(game,out=None,version=None):
    """stamp FRONTEND/ART (English) and FRONTEND/GART (German), whichever is installed"""
    global VERSION
    if version: VERSION=version
    done=[]
    for sub in ('ART','GART'):
        src=os.path.join(game,'FRONTEND',sub)
        if os.path.exists(os.path.join(src,'TITLE.QFS')):
            q,_=stamp(os.path.join(src,'TITLE.QFS'),os.path.join(src,'FONTS','GRAVER18.FFN'))
            dst=os.path.join(out or game,'FRONTEND',sub); os.makedirs(dst,exist_ok=True)
            open(os.path.join(dst,OUTNAME),'wb').write(q); done.append(sub)
    return done
