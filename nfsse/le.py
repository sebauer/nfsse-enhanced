"""LE executable helpers for NFS.EXE: fixups, address mapping, disassembly."""
import struct,os,pickle
ROOT=os.path.dirname(os.path.abspath(__file__))
# default game folder for the dev helpers; override with the NFSSE_GAME environment variable
GAME=os.environ.get('NFSSE_GAME',os.path.join(os.path.dirname(ROOT),'NFSSE'))
ORIG=os.path.join(GAME,'NFS.EXE')
B=0x10000
def cfo(v): return 0x3c600+v-0x10000
def dfo(v): return 0xE9600+v-0xE0000
def parse_fixups(d):
    le=0x2c80; U=lambda o:struct.unpack_from('<I',d,le+o)[0]
    npages=U(0x14); fpt=le+U(0x68); frt=le+U(0x6c)
    objtab=le+U(0x40); nobj=U(0x44)
    objs=[struct.unpack_from('<IIIIII',d,objtab+i*24) for i in range(nobj)]
    bases={i+1:o[1] for i,o in enumerate(objs)}; pg={}
    for i,o in enumerate(objs):
        for k in range(o[4]): pg[o[3]+k]=(i+1,o[1]+k*4096)
    fix=[]
    for p in range(1,npages+1):
        s=struct.unpack_from('<I',d,fpt+(p-1)*4)[0]; e=struct.unpack_from('<I',d,fpt+p*4)[0]
        o=frt+s; end=frt+e
        while o<end:
            src=d[o]; flg=d[o+1]; o+=2
            if src&0x20: n=d[o]; o+=1; offs=[struct.unpack_from('<h',d,o+2*j)[0] for j in range(n)]; o+=2*n
            else: offs=[struct.unpack_from('<h',d,o)[0]]; o+=2
            if flg&0x40: tobj=struct.unpack_from('<H',d,o)[0]; o+=2
            else: tobj=d[o]; o+=1
            if (src&0xf)==2: toff=0
            elif flg&0x10: toff=struct.unpack_from('<I',d,o)[0]; o+=4
            else: toff=struct.unpack_from('<H',d,o)[0]; o+=2
            for so in offs: fix.append((pg[p][1]+so, bases[tobj]+toff, src&0xf))
    return fix
_cache=os.path.join(ROOT,'fix.pkl')
def fixups():
    if not os.path.exists(_cache):
        pickle.dump(parse_fixups(open(ORIG,'rb').read()),open(_cache,'wb'))
    return pickle.load(open(_cache,'rb'))
def sources(fix):
    out=set()
    for s,t,_ in fix:
        for k in range(4): out.add(s+k)
    return out
_src=None
def fix_sources():
    global _src
    if _src is None:
        _src=set()
        for s,t,_ in fixups():
            for k in range(4): _src.add(s+k)
    return _src
def code():
    d=open(ORIG,'rb').read(); return d[0x3c600:0x3c600+0xab000]
def dis(a,b,data=None):
    import capstone; md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    c=data if data is not None else code()
    out=[]
    for i in md.disasm(c[a-B:b-B],a):
        if i.mnemonic=='add' and i.op_str=='byte ptr [eax], al': continue
        out.append(f"{i.address:06x} {i.bytes.hex():16s} {i.mnemonic} {i.op_str}")
    return '\n'.join(out)
def callers(t,c=None):
    c=c or code(); r=[]
    for i in range(len(c)-5):
        if c[i]==0xe8 and B+i+5+struct.unpack_from('<i',c,i+1)[0]==t: r.append(B+i)
    return r
def refs(vaddr_lo,vaddr_hi=None):
    vaddr_hi=vaddr_hi or vaddr_lo+1
    return [(s,t) for s,t,_ in fixups() if vaddr_lo<=t<vaddr_hi and s<0xC0000]
if __name__=='__main__':
    import sys
    a,b=(int(x,16) for x in sys.argv[1].split(':')); print(dis(a,b))
