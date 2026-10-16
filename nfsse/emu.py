"""Unicorn harness: flat-load NFS.EXE (code+data objects, fixups applied) to call pure routines."""
import struct,unicorn as U
from unicorn.x86_const import *
import le
def load(path=le.ORIG):
    d=open(path,'rb').read(); L=0x2c80; u=lambda o:struct.unpack_from('<I',d,L+o)[0]
    objtab=L+u(0x40); nobj=u(0x44); pgsz=u(0x28); dpg=u(0x80)
    objs=[struct.unpack_from('<IIIIII',d,objtab+i*24) for i in range(nobj)]
    mu=U.Uc(U.UC_ARCH_X86,U.UC_MODE_32); mu.mem_map(0,0x400000)
    for vsize,base,flags,pidx,pcnt,_ in objs:
        off=dpg+(pidx-1)*pgsz; mu.mem_write(base,d[off:off+pcnt*pgsz])
    fx=le.fixups() if path==le.ORIG else le.parse_fixups(d)
    for s,t,typ in fx:
        if typ==7: mu.mem_write(s,struct.pack('<I',t))
    return mu,objs
STOP=0x3f0000
def call(mu,addr,regs={},stack=(),esp=0x3e0000):
    mu.mem_write(STOP,b'\xf4'); sp=esp
    for v in reversed(list(stack)): sp-=4; mu.mem_write(sp,struct.pack('<i',v))
    sp-=4; mu.mem_write(sp,struct.pack('<I',STOP)); mu.reg_write(UC_X86_REG_ESP,sp)
    for r,v in regs.items(): mu.reg_write(r,v&0xffffffff)
    mu.emu_start(addr,STOP,count=50_000_000)
    return mu.reg_read(UC_X86_REG_EAX)
def huff_decode(data,mu=None):
    """EA 0x30fb/0x32fb Huffman (+RLE) via the game's own decoder 0xaf440(src,dst)."""
    if mu is None: mu,_=load()
    n=int.from_bytes(data[2:5],'big'); SRC=0x300000; DST=0x340000
    mu.mem_write(SRC,bytes(data)); call(mu,0xaf440,stack=(SRC,DST,1))
    return bytes(mu.mem_read(DST,n))
