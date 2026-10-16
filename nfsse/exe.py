"""Generate a hi-res NFS SE executable (1024x768 layout scaled to W x H)."""
import struct,os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import le, stackfix
from layout import L
def relocate_target(d,old_off,new_off,obj=4):
    le_=0x2c80; U=lambda o:struct.unpack_from('<I',d,le_+o)[0]
    npages=U(0x14); fpt=le_+U(0x68); frt=le_+U(0x6c); n=0
    for p in range(1,npages+1):
        s=struct.unpack_from('<I',d,fpt+(p-1)*4)[0]; e=struct.unpack_from('<I',d,fpt+p*4)[0]
        o=frt+s; end=frt+e
        while o<end:
            src=d[o]; flg=d[o+1]; o+=2
            if src&0x20: k=d[o]; o+=1+2*k
            else: o+=2
            if flg&0x40: tobj=struct.unpack_from('<H',d,o)[0]; o+=2
            else: tobj=d[o]; o+=1
            if (src&0xf)==2: continue
            if flg&0x10:
                if tobj==obj and struct.unpack_from('<I',d,o)[0]==old_off: struct.pack_into('<I',d,o,new_off); n+=1
                o+=4
            else:
                assert not (tobj==obj and struct.unpack_from('<H',d,o)[0]==old_off); o+=2
    return n
def grow_obj4_and_move_column_table(d,extra_stack=0x8000,table=0x2000):
    le_=0x2c80; ot=le_+struct.unpack_from('<I',d,le_+0x40)[0]+24*3
    vsize=struct.unpack_from('<I',d,ot)[0]; assert vsize==0x89a10
    assert struct.unpack_from('<II',d,le_+0x20)==(4,0x89a10)
    top=(vsize+15)&~15; new_esp=top+extra_stack; tbase=new_esp+0x10
    struct.pack_into('<I',d,ot,tbase+table); struct.pack_into('<I',d,le_+0x24,new_esp)
    assert (relocate_target(d,0x4df40,tbase),relocate_target(d,0x4df44,tbase+4))==(6,1)
    return tbase
def add_obj4_block(d,size):
    """append a zero-initialised block to obj4 (above the initial stack top); returns its obj4 offset"""
    le_=0x2c80; ot=le_+struct.unpack_from('<I',d,le_+0x40)[0]+24*3
    base=(struct.unpack_from('<I',d,ot)[0]+15)&~15; struct.pack_into('<I',d,ot,base+size); return base
def car_draw_segments(d,segs,depth=None):
    """cars ahead are only considered within 35 track segments (flag table 0x6e5d0[35], followed by another
    table). Move the flag table to a new block and raise the segment limit; scale the depth cull 0x5a00 too."""
    if segs==35: return
    nb=add_obj4_block(d,0x80); assert segs<=0x7f
    assert relocate_target(d,0x6e5d0,nb)==3
    fo=le.cfo(0x678ab); assert struct.unpack_from('<I',d,fo)[0]==0x23; struct.pack_into('<I',d,fo,segs)
    for v in (0x67916,0x6792a,0x683a1):
        fo=le.cfo(v); assert d[fo]==0x23,hex(v); d[fo]=segs
    fo=le.cfo(0x66d26); o=struct.unpack_from('<i',d,fo)[0]; assert o==0x5a00; struct.pack_into('<i',d,fo,depth if depth else round(o*segs/35))
def grow_track_vertex_buffers(d,cap=2060):
    """track vertices live in three fixed 515-entry arrays (0x57434 world 12B, 0x58c58 view 12B, 0x5a47c
    screen 8B) without overflow checks. Move them to a new block with room for cap vertices each."""
    nb=add_obj4_block(d,cap*32); A,B,C=nb,nb+cap*12,nb+cap*24
    for old,new,n in ((0x57434,A,3),(0x58c58,B,7),(0x58c5c,B+4,2),(0x58c60,B+8,2),(0x5a47c,C,5)):
        got=relocate_target(d,old,new); assert got==n,(hex(old),got)
    return nb
CAVE=0xbaa00   # zero slack at the end of the code object (0xba9fd..0xbb000)
CAVE_CODE='60e8000000005b8bb3d93df9ff83c6088dbe4433221189bb3f4df9ff89bb534ef9ff31c931d289d083f81b7e05b81b00000089cdc1e50501c58b04ae89cdc1e50601d58904af4283fa407cda4183f9087cd261ba88776655c3'
def extend_detail_table(d,draw):
    """detail table 0xd284 has 32 entries per track type -> draw distance > ~30 indexes the next row.
    New 8x64 table in a fresh obj4 block, filled at track load by a code cave (hooked at 0x4f04d, where the
    draw distance is set): new[t][i] = old[t][min(i,27)]. The two readers use 16-bit-offset fixups that cannot
    be retargeted, so the cave rewrites their disp32 (0x4f745/0x4f859) at runtime; they switch to stride 256."""
    le_=0x2c80; ot=le_+struct.unpack_from('<I',d,le_+0x40)[0]
    assert struct.unpack_from('<I',d,ot)[0]==0xaa9fd; struct.pack_into('<I',d,ot,0xab000)
    nb=add_obj4_block(d,0x800)
    code=bytes.fromhex(CAVE_CODE).replace(bytes.fromhex('44332211'),struct.pack('<i',nb-0xd284)).replace(bytes.fromhex('88776655'),struct.pack('<I',draw))
    fo=le.cfo(CAVE); assert d[fo:fo+len(code)]==bytes(len(code)); d[fo:fo+len(code)]=code
    fo=le.cfo(0x4f04d); assert d[fo]==0xba; d[fo]=0xe8; struct.pack_into('<i',d,fo+1,CAVE-(0x4f04d+5))
    for v,b in ((0x4f73f,'c1e007'),(0x4f851,'c1e207')):
        fo=le.cfo(v); assert d[fo:fo+3].hex()==b,hex(v); d[fo+2]=8
def fix_polygon_fillers(d,rows,SRC):
    n=0
    for v,b in stackfix.patches(lambda v:bytes(d[le.cfo(v):le.cfo(v)+4]),rows):
        assert not any(v+i in SRC for i in range(len(b))),hex(v)
        fo=le.cfo(v); d[fo:fo+len(b)]=b; n+=1
    # the edge-table builders called by these fillers refuse heights > 768
    for v in (0xa7814,0xa7964,0xa797a,0xa7a24):
        fo=le.cfo(v); assert d[fo-2:fo]==b'\x81\xfb' and int.from_bytes(d[fo:fo+4],'little')==0x300,hex(v)
        assert not any(v+i in SRC for i in range(4)); d[fo:fo+4]=rows.to_bytes(4,'little'); n+=1
    return n
def build(orig_path,out_path,W=1280,H=960,tag='K',vesa=0x22B,steer=1,lod=1,segs=35,cardepth=None,draw=28,near=4,detail=None,force_detail=False,traffic=None,title=True):
    g=L(W,H); d=bytearray(open(orig_path,'rb').read()) if isinstance(orig_path,str) else bytearray(orig_path)
    SRC=le.sources(le.parse_fixups(bytes(d))); log=[]
    cfo,dfo=le.cfo,le.dfo
    def code(v,fn,n=4):
        fo=cfo(v); assert not any(v+i in SRC for i in range(n)),hex(v)
        old=int.from_bytes(d[fo:fo+n],'little',signed=True); new=int(round(fn(old)))
        d[fo:fo+n]=new.to_bytes(n,'little',signed=True); log.append((hex(v),old,new))
    def raw(v,old,new):
        fo=cfo(v); o=bytes.fromhex(old); nn=bytes.fromhex(new)
        assert d[fo:fo+len(o)]==o,hex(v); assert not any(v+i in SRC for i in range(len(o))),hex(v); d[fo:fo+len(nn)]=nn
    D=g.DXR; DY=g.DY
    for v in (0x5b9c1,0x2e9bc,0x2f619): code(v,lambda o:W)
    for v in (0x5b9c6,0x2e9c1,0x2d37a): code(v,lambda o:H)
    raw(0x5ba5a,'754a','9090')
    for v,k in ((0x2d913,1),(0x2d948,2),(0x2d98e,2),(0x2d9e5,4),(0x2da3e,3)): code(v,lambda o,k=k:o+k*D//4)
    for v in (0x2dd47,0x2dd99): code(v,lambda o:o*g.SX)
    code(0x2f8ef,lambda o:o+(H-416)); code(0x2f90b,lambda o:-62,1)
    for v in (0x2f905,0x31619,0x31bc5,0x300e6): code(v,lambda o:o+D)
    for v in (0x2fa19,0x3160e,0x31bbb,0x300dc): code(v,lambda o:o+DY)
    for v in (0x2fdd9,0x2fdde,0x2fdee,0x2fdf3): code(v,lambda o:o*g.SX)
    for v in (0x2fde3,0x2fdf8,0x2d345): code(v,lambda o:g.my(o))
    grp={0x30ea3:D//2,0x30eb4:D-32,0x30eca:D,0x30eeb:16,0x30f06:D-16,0x30f29:16,0x30f4d:D-16,0x30f7b:D-16,0x30f80:D-16,0x30fa7:D-16}
    for v,dd in grp.items(): code(v,lambda o,dd=dd:o+dd)
    for v in (0x3194b,0x31967): code(v,lambda o:H)
    for v in (0x31950,0x3196c): code(v,lambda o:W)
    raw(0x2f9b0,'83c308','83f308'); raw(0x2fac6,'83c608','83f608'); raw(0x308d2,'83c608','83f608')
    raw(0x49bd0,'7e','7c')
    for v,o in ((0x1af80,'7435'),(0x1bfb4,'7435'),(0x3cf7a,'742f'),(0x3e2cc,'7435')): raw(v,o,'9090')
    raw(0x56ced,'85db7554','31db9090'); raw(0x56d63,'74','eb')
    raw(0x5806d,'85db7527','31db9090'); raw(0x580af,'85f67554','31f69090')
    for v in (0x58082,0x580d6): code(v,lambda o:H)
    for v in (0x58087,0x580db): code(v,lambda o:W)
    for v in (0x5e505,0x7f483,0x5fd37,0x5fe84): code(v,lambda o:H)
    for v in (0x5e50a,0x7f488,0x5fd41,0x5fe8e): code(v,lambda o:W)
    for v in (0x5e50f,0x7f48d,0x5fd3c,0x5fe89,0x5fd50,0x5fe9c,0x5fd95,0x5fdb6,0x5fee7,0x5ff07): code(v,lambda o:o+DY)
    raw(0x5fd11,'0f854c010000','e94d01000090')
    # opponent markers above cars
    code(0x67018,lambda o:o*g.SX); code(0x67044,lambda o:o*g.SX,1)
    for v in (0x66ba9,0x66bb4,0x66be6,0x66beb,0x66bfa,0x66bff): code(v,lambda o:o*g.SX)
    # memory pool: request 48MB instead of 16MB (capped by what DOS4GW provides)
    code(0x92ed3,lambda o:0x3000000)
    # optional faster keyboard steering: 0x483e4 takes its base step from the car's PBS at +0x300 (=4 in every car).
    # Replace the load with a constant 4*steer (mov edi,imm32 + nop) -> steer x faster build-up (and return to centre)
    if steer!=1:
        imm=round(4*steer)
        for v in (0x4840b,0x4841d,0x48425): raw(v,'8bb900030000','bf'+imm.to_bytes(4,'little').hex()+'90')
    # car level of detail (0x66d08): view depth [car+0x399] decides hi/lo model.
    #   cars ahead:  lo-poly beyond 0x1900;  cars behind: lo-poly beyond 0xa00, culled beyond 0x2100
    #   (global cull 0x5a00 unchanged). lod scales these distances.
    if lod!=1:
        for v in (0x66d5e,0x66d6a,0x66d82): code(v,lambda o:round(o*lod))
    # track draw distance: [0x56618]=28 blocks (set at track load, 0x4f04d); textured near zone = 4 blocks (0x5a500)
    if draw!=28:
        fo=cfo(0x4f04e); assert struct.unpack_from('<I',d,fo)[0]==0x1c; struct.pack_into('<I',d,fo,draw)
    if near!=4:
        assert d[cfo(0x5a502)]==4 and struct.unpack_from('<I',d,cfo(0x5a506))[0]==4
        d[cfo(0x5a502)]=near; struct.pack_into('<I',d,cfo(0x5a506),near)
    # per-distance track detail table 0xd284: 8 track types x 32 block distances -> chunk variant
    # (orig: 3 blocks high, 1 medium, rest low; entries 28..31 = 0). Walls/scenery objects only exist in
    # the high/medium variants. detail = number of blocks with high/medium detail (last one medium).
    # Tested: detail=6 OK (incl. Transtropolis); 8 -> stray polygons; 12 -> crash at race start.
    if detail or draw>28:
        assert not detail or detail<=6 or force_detail, 'detail>6 breaks the renderer (vertex indexing limit)'
        assert draw<=32, 'detail table has 32 entries per track type (extend_detail_table() crashed in testing)'
        for t in range(8):
            fo=dfo(0xE0000+0xd284+t*128); row=list(struct.unpack_from('<32i',d,fo))
            hi,med,lo=row[0],row[3],row[4]; n=detail or 4
            new=[hi]*(n-1)+[med]+[lo]*(28-n)+row[28:]   # entries 28..31 must stay 0 (crash otherwise)
            struct.pack_into('<32i',d,fo,*new)
        # scenery-object window: the engine drops ALL objects once more than 180 are active; the object
        # vertex buffers (0x4f540 / 0x51f70) hold 900 vertices = 450 objects -> allow 440
        fo=cfo(0x597ee); assert struct.unpack_from('<I',d,fo)[0]==0xb4; struct.pack_into('<I',d,fo,440)
        grow_vbuf=True
    # traffic window (0x77f98): per player, from his segment s: spawn at s+front+rand(0..10), recycled outside
    # [s-rear_in-rear_out, s+front+11]. orig front=43, rear_in=12, rear_out=8. traffic=(front,rear_in,rear_out)
    if traffic:
        fr,ri,ro=traffic
        for v,old,new in ((0x77fb9,0x2b,fr),(0x77fbc,0x0c,ri),(0x7809f,0x08,ro)):
            assert d[cfo(v)]==old,hex(v); d[cfo(v)]=new
    # cockpit-view horizon: quads with any vertex x outside +-1280 are dropped (2x the 640 width); scale to 2*W
    for v in (0x4b0ec,0x4b0f8,0x4b104,0x4b11b,0x4b127,0x4b133,0x4b1a7,0x4b1b3,0x4b1bf,0x4b1d6,0x4b1e2,0x4b1ee): code(v+2,lambda o:o*W//640)
    for v in (0x4b110,0x4b1cb,0x4b1fa): code(v+1,lambda o:o*W//640)
    def put(base,vals):
        for i,v in enumerate(vals): struct.pack_into('<i',d,dfo(base+4*i),v)
    put(0xe8868+8,[0,0,W,H,0,0,W,round(320*H/480)])
    put(0xe88e0+8,[0,0,W,H-32,0,32,W,H-32])
    put(0xe8c80+16,[0,0,W,H,0,32,W,round(320*(H-32)/448)])
    put(0xe8cb4+16,[0,0,W,H-32,0,32,W,H-32])
    for i in range(12):
        fo=dfo(0xe8edc+12*i); o=struct.unpack_from('<i',d,fo)[0]; struct.pack_into('<i',d,fo,round(g.my(o)))
    def ch(v,old,new):
        fo=dfo(v); assert d[fo]==ord(old),(hex(v),chr(d[fo])); d[fo]=ord(new)
    for v in (0xe0d75,0xe0dd9,0xe0e43,0xe0e4f,0xe0e5b,0xe0e67,0xe0ea2,0xe0eaa,0xe0eb1,0xe0eb9): ch(v,'H',tag)
    for v in (0xe3651,0xe3669,0xe36ab): ch(v,'i',tag.lower())
    ch(0xe368b,'I',tag)
    if (W,H)!=(1024,768):
        mt=dfo(0xf7d68)+16*10; assert struct.unpack_from('<4i',d,mt)==(1280,1024,15,281)
        struct.pack_into('<4i',d,mt,W,H,8,vesa)
    if W>1024 or H>768:
        log.append(('coltable',hex(grow_obj4_and_move_column_table(d)),fix_polygon_fillers(d,max(1024,(H+255)//256*256),SRC)))
    car_draw_segments(d,segs,cardepth)
    if detail or draw>28 or near>4: grow_track_vertex_buffers(d)
    if title:   # title screen with the patch credit line (FRONTEND/(G)ART/TITLEE.QFS)
        for v in (0xe2974,0xe4454):
            fo=dfo(v); assert d[fo:fo+12]==b'title.qfs\0\0\0',hex(v); d[fo:fo+11]=b'titlee.qfs\0'
    if out_path: open(out_path,'wb').write(d)
    return (bytes(d),log) if not out_path else log
if __name__=='__main__':
    W,H,tag,out=int(sys.argv[1]),int(sys.argv[2]),sys.argv[3],sys.argv[4]
    build(le.ORIG,os.path.join(le.GAME,out),W,H,tag); print('built',out)
