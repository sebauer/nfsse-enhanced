"""HUD archive generator (MASKHI.FSH / MASKHIG.FSH -> MASKH<tag>.FSH / MASKH<tag>G.FSH).
HUD shapes stay at 1x and are spread over the wider screen using the 1024x768 layout,
scaled to W x H via layout.L. Uses only the user's original archives."""
import struct,sys,os,numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import fsh
from layout import L
# position delta of each shape in the 1024x768 reference layout (dx,dy); unlisted = (0,0)
DELTA1024={
    (0, 288): ['00d ', '0a  ', '0b  ', '0d  ', '0e  ', '0f  ', '0h  ', '0i  ', '0j  ', '0k  ', '0l  ', '0m  ', '0n  ', '0o  ', '0p  ', '0q  ', '0r  ', '0s  ', '0t  ', '0u  ', '0v  ', '0w  ', '0x  ', '0y  ', '0z  ', '1/2d', '1/2l', '1/4d', '1/4l', '1d  ', 'dond', 'doni', 'donl', 'ford', 'fori', 'forl', 'fted', 'ftei', 'ftel', 'fuld', 'full', 'paud', 'paui', 'paul', 'plad', 'plai', 'plal', 'rewd', 'rewi', 'rewl', 'rtsd', 'rtsi', 'rtsl', 'tach', '0c  ', '7d  ', '9d  ', 'repl', 'donm', '0<d ', '0<ld', '0<lu', '0>d ', '0>ld', '0>lu', 'namd', 'naml', '3d  ', '6d  ', '8d  ', '0g  ', '2d  ', '4d  ', '5d  ', 'bard', '02d ', '03d ', '04d ', '05d ', '06d ', '07d ', '08d ', '01lu', '02lu', '03lu', '04lu', '05lu', '06lu', '07lu', '08lu', '01d ', '01ld', '02ld', '03ld', '04ld', '05ld', '06ld', '07ld', '08ld'],
    (192, 0): ['lost', 'wait'],
    (207, 162): ['paus'],
    (368, 0): ['lap#', 'mile', 'mnus', 'plus', 'splt'],
    (384, 0): ['head', 'sing'],
    (384, 288): ['bumd', 'buml', 'card', 'carl', 'chad', 'chal', 'copd', 'held', 'hell', 'mpbd', 'oppd', 'oppl', 'skyd', 'skyl', 'taid', 'tail', 'camd', 'caml', 'cami', 'copl'],
}
D1024={nm.encode('latin1'):k for k,v in DELTA1024.items() for nm in v}
def blocks(u):
    de=fsh.parse(u); offs=sorted(o for _,o in de)+[len(u)]
    return de,{nm:u[o:offs[offs.index(o)+1]] for nm,o in de}
def reblock(blk,npix,W,H,x,y,cx,cy):
    w,h=struct.unpack_from('<hh',blk,4); att=blk[16+w*h:]
    nxt=blk[1]|blk[2]<<8|blk[3]<<16
    ch=fsh.chain(att) if nxt else []
    natt=b''.join(cb for _,_,cb in ch) if ch else att
    hdr=bytearray(blk[:16]); hdr[1:4]=((16+W*H) if nxt else 0).to_bytes(3,'little')
    struct.pack_into('<6h',hdr,4,W,H,cx,cy,x,y)
    return bytes(hdr)+npix.astype(np.uint8).tobytes()+bytes(natt)
def regroup(src,cuts,d_new,W):
    """Place column groups [cuts[i],cuts[i+1]) at +d_new[i]; gaps repeat the last column."""
    h=src.shape[0]; out=np.zeros((h,W),np.uint8)
    for i in range(len(d_new)):
        a,b=cuts[i],cuts[i+1]; out[:,a+d_new[i]:b+d_new[i]]=src[:,a:b]
        if i+1<len(d_new):
            g0,g1=b+d_new[i],cuts[i+1]+d_new[i+1]
            if g1>g0: out[:,g0:g1]=src[:,b-1:b]
    return out
def build(orig,dst,W,H):
    g=L(W,H); u=open(orig,'rb').read(); de,bl=blocks(u); rep={}; D=g.DXR
    for nm,o in de:
        b=bl[nm]
        if b[0]!=0x7b: continue
        w,h,cx,cy,x,y=struct.unpack_from('<6h',b,4)
        px=np.frombuffer(b,np.uint8,w*h,16).reshape(h,w)
        dx,dy=D1024.get(nm,(0,0))
        if nm==b'paus':
            rep[nm]=reblock(b,px,w,h,(W-w)//2,(H-h)//2,cx,cy); continue
        if nm==b'stat':
            npx=regroup(px,[0,113,258,349,405,542,640],[0,16,D//2,D-32,D-16,D],W)
            rep[nm]=reblock(b,npx,W,h,x,y,cx,cy); continue
        if nm==b'acct':
            npx=regroup(px,[0,104,208,430,534,639],[0,D//4,D//2,3*D//4,D],W-1)
            rep[nm]=reblock(b,npx,W-1,h,x,y,cx,cy); continue
        if nm in (b'rtet',b'segt'):     # widen the label field by 16 px
            npx=np.hstack([px[:,:113],np.repeat(px[:,112:113],16,1),px[:,113:]])
            rep[nm]=reblock(b,npx,w+16,h,x,y,cx,cy); continue
        if nm==b'repl':
            L_,R_,M_=px[:,392:396],px[:,447:451],px[:,397:411]
            fill=np.hstack([L_,np.tile(M_,(1,D//14+1))[:,:D-8],R_])
            npx=np.hstack([px[:,:453],fill,px[:,453:]])
            rep[nm]=reblock(b,npx,W,h,0,y+g.DY,cx,cy); continue
        if nm in (b'sgrn',b'srdd',b'srdl',b'syld',b'syll'):   # start lights: stretch middle
            NW=round(w*g.SX); mid=px[:,3:w-3]; idx=(np.arange(NW-6)*(w-6))//(NW-6)
            npx=np.hstack([px[:,:3],mid[:,idx],px[:,w-3:]])
            rep[nm]=reblock(b,npx,NW,h,x,y,cx,cy); continue
        if y>=445 and dy==288 and nm not in (b'tach',b'mpbd'):   # replay bar group
            rep[nm]=reblock(b,px,w,h,x+(D if dx==384 else 0),y+g.DY,cx,cy); continue
        nx=x+(g.hx(dx) if dx else 0); ny=y+(g.hy(dy) if dy else 0)
        if dx==207: nx=(W-w)//2
        rep[nm]=reblock(b,px,w,h,nx,ny,cx,cy)
    open(dst,'wb').write(fsh.rebuild(u,rep))
def build_all(misc,tag,W,H,out=None):
    out=out or misc
    build(misc+'MASKHI.FSH',out+f'MASKH{tag}.FSH',W,H); build(misc+'MASKHIG.FSH',out+f'MASKH{tag}G.FSH',W,H)
