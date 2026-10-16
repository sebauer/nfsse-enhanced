"""Ticket / warning full-screen images (TICKET*/WARN* ..H.QFS -> ..<tag>.QFS), Lanczos-scaled to W x H."""
import sys,os,struct,numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import qfs
from PIL import Image
NAMES=['TICKETDH','TICKETRH','TICKEGDH','TICKEGRH','WARNDH','WARNRH','GWARNDH','GWARNRH']
def load(path): return qfs.decode(open(path,'rb').read())
def info(u):
    cnt=struct.unpack_from('<I',u,8)[0]
    return {u[16+8*i:20+8*i]:struct.unpack_from('<I',u,20+8*i)[0] for i in range(cnt)}
def build(u,W,H):
    dr=info(u); so=dr[b'scrn']; po=dr[b'!pal']
    assert u[so]==0x7b
    w,h=struct.unpack_from('<2H',u,so+4)
    px=np.frombuffer(u,np.uint8,w*h,so+16).reshape(h,w)
    pal=np.frombuffer(u,np.uint8,768,po+16).reshape(256,3).astype(float)*255/63
    img=Image.fromarray(pal[px].astype(np.uint8)).resize((W,H),Image.LANCZOS)
    rgb=np.asarray(img).reshape(-1,3).astype(float)
    P=pal[:254]; out=np.empty(len(rgb),np.uint8)
    for i in range(0,len(rgb),32768):
        ch=rgb[i:i+32768]; out[i:i+32768]=((ch[:,None,:]-P[None])**2).sum(2).argmin(1)
    hdr=bytearray(u[so:so+16])
    nxt=struct.unpack_from('<I',hdr,0)[0]>>8
    struct.pack_into('<I',hdr,0,0x7b|(((16+W*H) if nxt else 0)<<8))
    cx,cy=struct.unpack_from('<2H',hdr,8)
    struct.pack_into('<2H',hdr,4,W,H); struct.pack_into('<2H',hdr,8,round(cx*1.6),round(cy*1.6))
    sblk=bytes(hdr)+out.tobytes()
    pblk=u[po:po+16+768] if po<so else u[po:]
    first=min(so,po)
    d=bytearray(u[:first]); offs={}
    for nm,blk in sorted([(b'scrn',sblk),(b'!pal',pblk)],key=lambda t:dr[t[0]]):
        offs[nm]=len(d); d+=blk
    struct.pack_into('<I',d,4,len(d))
    for i in range(struct.unpack_from('<I',u,8)[0]):
        struct.pack_into('<I',d,20+8*i,offs[bytes(d[16+8*i:20+8*i])])
    return bytes(d)
def build_all(misc,tag,W,H,out=None,names=NAMES):
    out=out or misc
    for f in names:
        d=build(load(misc+f+'.QFS'),W,H); p=qfs.pack(d); assert qfs.unpack(p)==d
        open(out+f[:-1]+tag+'.QFS','wb').write(p)
