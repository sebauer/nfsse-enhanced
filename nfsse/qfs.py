"""RefPack (QFS) codec."""
import struct
def unpack(b):
    hdr=struct.unpack('>H',b[0:2])[0]
    p=5 if hdr&0x100 else 2
    assert (hdr&0xfeff)==0x10fb, hex(hdr)
    size=(b[p]<<16)|(b[p+1]<<8)|b[p+2]; p+=3
    o=bytearray()
    while p<len(b):
        c0=b[p]
        if c0<0x80:
            c1=b[p+1]; p+=2
            n=c0&3; o+=b[p:p+n]; p+=n
            l=((c0&0x1c)>>2)+3; off=((c0&0x60)<<3)+c1+1
        elif c0<0xc0:
            c1,c2=b[p+1],b[p+2]; p+=3
            n=c1>>6; o+=b[p:p+n]; p+=n
            l=(c0&0x3f)+4; off=((c1&0x3f)<<8)+c2+1
        elif c0<0xe0:
            c1,c2,c3=b[p+1],b[p+2],b[p+3]; p+=4
            n=c0&3; o+=b[p:p+n]; p+=n
            l=((c0&0x0c)<<6)+c3+5; off=((c0&0x10)<<12)+(c1<<8)+c2+1
        elif c0<0xfc:
            n=((c0&0x1f)<<2)+4; p+=1; o+=b[p:p+n]; p+=n; continue
        else:
            n=c0&3; p+=1; o+=b[p:p+n]; p+=n; break
        for _ in range(l): o.append(o[-off])
    return bytes(o)
def pack(d):
    n=len(d); out=bytearray(b'\x10\xfb'+bytes([(n>>16)&255,(n>>8)&255,n&255]))
    head={}; prev=[-1]*n
    i=0; lit=0
    def flush_lits(upto, keep):
        nonlocal lit
        while upto-lit-keep>=4:
            k=min(112,(upto-lit-keep)&~3)
            out.append(0xe0+(k>>2)-1); out.extend(d[lit:lit+k]); lit+=k
    def ins(j):
        if j+3<=n:
            h=d[j:j+3]; prev[j]=head.get(h,-1); head[h]=j
    while i<n:
        best=0;boff=0
        if i+3<=n:
            j=head.get(d[i:i+3],-1); tries=0
            while j>=0 and i-j<=131072 and tries<64:
                l=0; m=min(1028,n-i)
                while l<m and d[j+l]==d[i+l]: l+=1
                if l>best: best=l;boff=i-j
                if best>=m: break
                j=prev[j]; tries+=1
        ok = best>=3 and boff<=1024 or best>=4 and boff<=16384 or best>=5
        if not ok:
            ins(i); i+=1; continue
        L=best
        if boff>16384: L=min(L,1028)
        elif boff>1024: L=min(L,67)
        else: L=min(L,10)
        flush_lits(i,0) if (i-lit)%4==0 else flush_lits(i,(i-lit)%4)
        nl=i-lit; assert nl<=3
        o=boff-1
        if L<=10 and boff<=1024:
            out+=bytes([((o>>3)&0x60)|((L-3)<<2)|nl, o&255])
        elif L<=67 and boff<=16384:
            out+=bytes([0x80|(L-4), (nl<<6)|(o>>8), o&255])
        else:
            out+=bytes([0xc0|((o>>12)&0x10)|(((L-5)>>6)&0x0c)|nl,(o>>8)&255,o&255,(L-5)&255])
        out.extend(d[lit:i])
        for k in range(L): ins(i+k)
        i+=L; lit=i
    flush_lits(n,(n-lit)%4)
    nl=n-lit; out.append(0xfc+nl); out.extend(d[lit:n])
    return bytes(out)
def decode(b):
    """any EA compressed file: RefPack (0x10fb/0x11fb) or Huffman (0x30fb..0x35fb)"""
    if (b[0]&0xf0)==0x30:
        import huff; return huff.decode(b)
    return unpack(b)
