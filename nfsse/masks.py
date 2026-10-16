"""Blit-list generator (MASKHI.Bxy / MASKHI.MMB -> MASKH<tag>.*).
BAMF lists: per 64K bank, entries (src, dst&0xffff, len). Only the user's originals are read."""
import struct,sys,os,numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import fsh
from layout import L
def parse(d,base=0):
    nb=struct.unpack_from('<H',d,base+8)[0]; hdr=d[base+10:base+20]; o=base+20; ents=[]
    for b in range(nb):
        n=struct.unpack_from('<H',d,o)[0]; o+=2
        for i in range(n):
            s,dd,l=struct.unpack_from('<IHH',d,o+8*i); ents.append((s,b*65536+dd,l))
        o+=8*n
    return hdr,ents
def convert(hdr,ents,W,P=640):
    maxlen,xs,ys=struct.unpack('<HII',hdr)
    out=[]
    for s,a,l in ents:
        while l>0:
            dr,dc=divmod(a,P); seg=min(l,P-dc)
            sr,sc=divmod(s,P)
            na=dr*W+dc; ns=sr*W+sc
            rem=seg; ca=na; cs=ns
            while rem>0:
                lim=((ca>>16)+1)<<16; part=min(rem,lim-ca)
                out.append((cs,ca,part))
                cs+= (part*xs)>>16; ca+=part; rem-=part
            a+=seg; s+= (seg*xs)>>16 if xs!=0x10000 else seg; l-=seg
    nb=(max(a+l for s,a,l in out)+0xffff)>>16
    banks=[[] for _ in range(nb)]
    for s,a,l in out: banks[a>>16].append((s,a&0xffff,l))
    ml=max(l for _,_,l in out)
    body=b''.join(struct.pack('<H',len(e))+b''.join(struct.pack('<IHH',*x) for x in e) for e in banks)
    h=struct.pack('<HHII',nb,ml,xs,ys)
    return b'BAMF'+struct.pack('<I',8+len(h)+len(body))+h+body
def build_list(inside,W,rows):
    ents=[]
    for r in rows:
        c=0
        while c<W:
            if inside(r,c):
                s0=c
                while c<W and inside(r,c): c+=1
                a=r*W+s0; l=c-s0
                while l>0:
                    lim=((a>>16)+1)<<16; p=min(l,lim-a); ents.append((a,a,p)); a+=p; l-=p
            else: c+=1
    nb=(max(a+l for _,a,l in ents)+0xffff)>>16; banks=[[] for _ in range(nb)]
    for s,a,l in ents: banks[a>>16].append((s,a&0xffff,l))
    body=b''.join(struct.pack('<H',len(x))+b''.join(struct.pack('<IHH',*y) for y in x) for x in banks)
    hh=struct.pack('<HHII',nb,max(l for *_,l in ents),0x10000,0x10000)
    return b'BAMF'+struct.pack('<I',8+len(hh)+len(body))+hh+body
def mmb(lists):
    n=len(lists); o=8+4*n; table=[]; blob=b''
    for Lst in lists:
        table.append(o+len(blob)); blob+=Lst
        while (o+len(blob))%4: blob+=b'\0'
    return b'wwww'+struct.pack('<I',n)+b''.join(struct.pack('<I',t) for t in table)+blob
def tach_mask(misc,W,H):
    g=L(W,H); u=open(misc+'MASKHI.FSH','rb').read(); o=fsh.shapes(u)['tach']
    w,h,cx,cy,x,y=struct.unpack_from('<6h',u,o+4)
    px=np.frombuffer(u,np.uint8,w*h,o+16).reshape(h,w)
    m=np.zeros((H,W),bool); m[y+g.DY:y+g.DY+h,x:x+w]=px!=255; return m
def build_all(misc,tag,W,H,out=None):
    out=out or misc
    g=L(W,H); tm=tach_mask(misc,W,H)
    mapm=np.zeros((H,W),bool); mapm[304+g.DY:446+g.DY,518+g.DXR:634+g.DXR]=True
    full=lambda hole: build_list(lambda r,c: not hole[r,c],W,range(32,H))
    for v in range(3):
        for p in range(4):
            if v==0 and p==0: data=full(tm|mapm)
            else: data=convert(*parse(open(misc+f'MASKHI.B{v}{p}','rb').read()),W)
            open(out+f'MASKH{tag}.B{v}{p}','wb').write(data)
    d=open(misc+'MASKHI.MMB','rb').read(); n=struct.unpack_from('<I',d,4)[0]
    offs=[struct.unpack_from('<I',d,8+4*i)[0] for i in range(n)]
    open(out+f'MASKH{tag}.MMB','wb').write(mmb([full(tm) if i==0 else convert(*parse(d,o),W) for i,o in enumerate(offs)]))
