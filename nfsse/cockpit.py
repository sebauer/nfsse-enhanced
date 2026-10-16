"""Cockpit builder: scale DH dash archives to the W x H layout (rows 32..H-1 filled),
build the window blit masks."""
import struct,sys,os,shutil,numpy as np
from PIL import Image
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import fsh, le
from layout import L
from scipy import ndimage as nd
SRC=OUT=os.path.join(le.GAME,'SIMDATA','DASH')+os.sep   # SRC: original *DH files, OUT: generated files
PAINT=np.arange(129,144)
def resample(pix,nw,nh,pal):
    h,w=pix.shape
    if w<8 or h<8: return np.array(Image.fromarray(pix,'L').resize((nw,nh),Image.NEAREST),np.uint8)
    rgba=np.zeros((h,w,4),np.uint8); rgba[...,:3]=pal[pix].round().astype(np.uint8); rgba[...,3]=np.where(pix==255,0,255)
    a=np.array(Image.fromarray(rgba,'RGBA').convert('RGBa').resize((nw,nh),Image.LANCZOS).convert('RGBA'))
    idx=fsh.quant(a[...,:3].reshape(-1,3).astype(np.float32),pal).reshape(nh,nw)
    return np.where(a[...,3]>=128,idx,255).astype(np.uint8)
def scale_shape(blk,pal,name,g):
    w,h,cx,cy,x,y=struct.unpack_from('<6h',blk,4)
    pix=np.frombuffer(blk,np.uint8,w*h,16).reshape(h,w); att=blk[16+w*h:]
    ch=fsh.chain(att) if (blk[1]|blk[2]<<8|blk[3]<<16) else []
    for ct,cnx,cb in ch:
        if ct==0x22 and len(cb)>=16+768: pal=np.frombuffer(cb,np.uint8,768,16).reshape(256,3).astype(np.float32)*255/63
    if name==b'dash' and y==0 and h==480:
        body=resample(pix[32:],round(w*g.SX),g.H-32,pal)
        npix=np.vstack([np.full((32,body.shape[1]),255,np.uint8),body]); nx,ny=0,0
    else:
        npix=resample(pix,max(1,round(w*g.SX)),max(1,round(h*g.SY)),pal); nx,ny=round(x*g.SX),round(g.my(y))
    nh,nw=npix.shape
    hdr=bytearray(16); hdr[0]=blk[0]
    struct.pack_into('<6h',hdr,4,nw,nh,round(cx*g.SX),round(cy*g.SY),nx,ny)
    natt=bytearray()
    for ct,cnx,cb in ch:
        cb=bytearray(cb)
        if ct==0x7c:
            cnt=struct.unpack_from('<I',cb,4)[0]
            if 8+8*cnt>len(cb) or cnt>4096: cnt=0
            for k in range(cnt):
                px,py=struct.unpack_from('<ii',cb,8+8*k)
                if abs(px)<100000 and abs(py)<100000:
                    struct.pack_into('<ii',cb,8+8*k,round(px*g.SX),round(g.my(py)) if name==b'dash' else round(py*g.SY))
        natt+=cb
    if not ch: natt=bytearray(att)
    hdr[1:4]=((16+nw*nh) if ch else 0).to_bytes(3,'little')
    return bytes(hdr)+npix.tobytes()+bytes(natt)
def scale_archive(src,dst,g):
    d=open(src,'rb').read(); de=fsh.parse(d); n=len(de)
    pal=fsh.gpal(d)
    if pal is None: pal=np.zeros((256,3),np.float32)
    order=sorted(range(n),key=lambda i:de[i][1]); first=de[order[0]][1]
    out=bytearray(d[:first]); newoff={}
    for k,i in enumerate(order):
        nm,o=de[i]; end=de[order[k+1]][1] if k+1<n else len(d)
        blk=d[o:end]; newoff[i]=len(out)
        out+= scale_shape(blk,pal,nm,g) if blk[0]==0x7b else blk
    for i in range(n): struct.pack_into('<I',out,20+8*i,newoff[i])
    struct.pack_into('<I',out,4,len(out)); open(dst,'wb').write(out)
def parse_bamf(d,base=0):
    nb=struct.unpack_from('<H',d,base+8)[0]; o=base+20; ents=[]
    for b in range(nb):
        n=struct.unpack_from('<H',d,o)[0]; o+=2
        for i in range(n):
            s,dd,l=struct.unpack_from('<IHH',d,o+8*i); ents.append((s,b*65536+dd,l))
        o+=8*n
    return ents
def bamf(ents):
    nb=(max(a+l for _,a,l in ents)+0xffff)>>16; banks=[[] for _ in range(nb)]
    for s0,a,l in ents: banks[a>>16].append((s0,a&0xffff,l))
    body=b''.join(struct.pack('<H',len(x))+b''.join(struct.pack('<IHH',*y) for y in x) for x in banks)
    hh=struct.pack('<HHII',nb,max(l for *_,l in ents),0x10000,0x10000)
    return b'BAMF'+struct.pack('<I',8+len(hh)+len(body))+hh+body
def window_mask(car,tag,g):
    m=open(SRC+car+'DH.FMM','rb').read(); Cm=np.zeros(640*480+70000,bool)
    for s,a,l in parse_bamf(m,struct.unpack_from('<I',m,8)[0]): Cm[a:a+l]=True
    rows=np.where(Cm[:640*480].reshape(480,640).any(1))[0]; r0,r1=rows.min(),rows.max()
    d=open(OUT+car+'D'+tag+'.FSH','rb').read(); o=fsh.shapes(d)['dash']
    w,h=struct.unpack_from('<hh',d,o+4); pix=np.frombuffer(d,np.uint8,w*h,o+16).reshape(h,w)
    pts=[]
    for ct,cnx,cb in fsh.chain(d[o+16+w*h:]):
        if ct==0x7c:
            cnt=struct.unpack_from('<I',cb,4)[0]; pts=[struct.unpack_from('<ii',cb,8+8*k) for k in range(cnt)]
    T=(pix==255).copy(); R0=round(g.my(r0)); R1=round(g.my(r1+1))-1
    T[:R0]=False; T[R1+1:]=False
    (mx0,my0),(mx1,my1)=pts[0],pts[1]; T[my0:my1+1,mx0:mx1+1]=False
    ents=[]
    for r in range(h):
        row=T[r]; c=0
        while c<g.W:
            if row[c]:
                s0=c
                while c<g.W and row[c]: c+=1
                a=r*g.W+s0; l=c-s0
                while l>0:
                    lim=((a>>16)+1)<<16; p=min(l,lim-a); ents.append((a,a,p)); a+=p; l-=p
            else: c+=1
    L_=bamf(ents); oo=24; table=[]; blob=b''
    for i in range(4):
        table.append(oo+len(blob)); blob+=L_
        while (oo+len(blob))%4: blob+=b'\0'
    open(OUT+car+'D'+tag+'.FMM','wb').write(b'wwww'+struct.pack('<I',4)+b''.join(struct.pack('<I',t) for t in table)+blob)
def defringe(car,tag):
    """the 1995 artwork has light anti-aliasing pixels at the window edge (drawn against
    white). At high resolution they show as a white dotted line: make them transparent."""
    p=OUT+car+'D'+tag+'.FSH'; d=bytearray(open(p,'rb').read()); o=fsh.shapes(bytes(d))['dash']
    _,px,pal=fsh.image(bytes(d),o); px=px.copy(); h,w=px.shape; lum=pal.mean(1); n=0
    for _ in range(3):
        tr=px==255; edge=nd.binary_dilation(tr,iterations=1)&~tr
        L=np.where(tr,np.nan,lum[px])
        K=np.ones((5,5))   # 5x5 neighbourhood sums (mode 'reflect')
        inner=nd.correlate(np.nan_to_num(L,nan=0.0),K)/np.maximum(nd.correlate((~tr).astype(float),K),1)
        bad=edge&(lum[px]>150)&(lum[px]>inner+35)
        if not bad.any(): break
        px[bad]=255; n+=int(bad.sum())
    d[o+16:o+16+w*h]=px.tobytes(); open(p,'wb').write(d); return n
def lanczos(car,tag,W,H):
    g=L(W,H); scale_archive(SRC+car+'DH.FSH',OUT+car+'D'+tag+'.FSH',g); defringe(car,tag); window_mask(car,tag,g)
CARS={'ANSX':'ansx','CZR1':'czr1','DVIPER':'dviper','F512TR':'f512tr','LDIABL':'diablo','MRX7':'mrx7','P911':'p911','TRAFFC':'traffc','TSUPRA':'tsupra'}
def build_all(tag,W,H,cars=None,src=None,out=None):
    global SRC,OUT
    if src: SRC=src
    if out: OUT=out
    for car in (cars or CARS):
        lanczos(car,tag,W,H); print(car,'lanczos',flush=True)
if __name__=='__main__':
    tag,W,H=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]); build_all(tag,W,H,sys.argv[4:] or None)
