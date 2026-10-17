# Decoder for EA's Huffman compression format (types 0x30fb..0x35fb), pure Python.
# Output is byte-compatible with the game's own decoder
class _Bits:
    def __init__(s,b,p): s.b=b; s.p=p*8
    def get(s,n):
        v=0
        for _ in range(n):
            v=(v<<1)|((s.b[s.p>>3]>>(7-(s.p&7)))&1 if (s.p>>3)<len(s.b) else 0); s.p+=1
        return v
    def peek(s,n):
        p=s.p; v=s.get(n); s.p=p; return v
    def getnum(s):
        if s.peek(1): return s.get(3)-4
        if s.peek(16):
            k=0
            while not s.get(1): k+=1
            n=k+2
        else:
            n=2
            while True:
                n+=1
                if s.get(1): break
        return s.get(n)+(1<<n)-4
def decode(b):
    typ=(b[0]<<8)|b[1]; p=2
    assert b[1]==0xfb and (typ>>8)&0xf0==0x30, hex(typ)
    if typ&0x100: p+=3
    ulen=(b[p]<<16)|(b[p+1]<<8)|b[p+2]; p+=3
    r=_Bits(b,p); clue=r.get(8)
    base={}; count={}; limit={}; numchars=0; cmp=0; bn=1
    while True:
        cmp*=2; base[bn]=cmp-numchars
        n=r.getnum(); count[bn]=n; numchars+=n; cmp+=n
        lim=((cmp<<(16-bn))&0xffff) if n else 0
        limit[bn]=lim; bn+=1
        if n and not lim: break
    maxbits=bn-1; limit[maxbits]=0xffffffff
    used=[0]*256; leaf=[]; c=0xff
    for _ in range(numchars):
        d=r.getnum()+1
        while True:
            c=(c+1)&255
            if not used[c]: d-=1
            if not d: break
        used[c]=1; leaf.append(c)
    qb=[0x40]*256; qc=[0]*256; k=0; i=0; cluebits=0
    for L in range(1,min(maxbits,8)+1):
        span=1<<(8-L)
        for _ in range(count[L]):
            s=leaf[i]; i+=1; bits=L
            if s==clue: cluebits=L; bits=0x60
            for _ in range(span):
                if k<256: qb[k]=bits; qc[k]=s; k+=1
    out=bytearray()
    while True:
        t=r.peek(8); bits=qb[t]
        if bits<=8:
            r.p+=bits; out.append(qc[t]); continue
        if bits==0x60: L=cluebits
        else:
            v=r.peek(16); L=9
            while v>=limit[L]: L+=1
        s=leaf[r.get(L)-base[L]]
        if s!=clue: out.append(s); continue
        run=r.getnum()
        if run: out+=bytes([out[-1]])*run; continue
        if r.get(1): break
        out.append(r.get(8))
    if typ==0x32fb:
        a=0
        for j in range(len(out)): a=(a+out[j])&255; out[j]=a
    elif typ==0x34fb:
        a=0; d=0
        for j in range(len(out)): a=(a+out[j])&255; d=(d+a)&255; out[j]=d
    return bytes(out[:ulen])
