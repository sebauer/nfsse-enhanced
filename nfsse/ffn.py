"""EA FNTF font (*.FFN): glyph table + 4bpp atlas (FSH shape type 0x7a)."""
import struct,numpy as np
def load(path):
    d=open(path,'rb').read(); assert d[:4]==b'FNTF'
    n=struct.unpack_from('<H',d,10)[0]; ao=struct.unpack_from('<I',d,0x1c)[0]
    assert d[ao]==0x7a; w,h=struct.unpack_from('<2h',d,ao+4)
    raw=np.frombuffer(d,np.uint8,w*h//2,ao+16)
    atlas=np.empty(w*h,np.uint8); atlas[0::2]=raw>>4; atlas[1::2]=raw&15; atlas=atlas.reshape(h,w)
    g={}
    for i in range(n):
        c,gw,gh,x,y,adv,xo,yo=struct.unpack_from('<HBBHHBbB',d,0x20+11*i)
        g[c]=(atlas[y:y+gh,x:x+gw],adv,xo,yo)
    return g
def render(g,text,track=0):
    """returns alpha (0..1) image"""
    W=sum(g[ord(ch)][1]+track for ch in text)+8; H=max(gl[0].shape[0]+gl[3] for gl in g.values())+2
    a=np.zeros((H,W),np.float32); x=0
    for ch in text:
        gl,adv,xo,yo=g[ord(ch)]; h,w=gl.shape
        X=x+xo+1; a[yo:yo+h,X:X+w]=np.maximum(a[yo:yo+h,X:X+w],gl/15); x+=adv+track
    return a[:,:x+2]
