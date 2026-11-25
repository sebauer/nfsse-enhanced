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
# detail reader 0x4f83e..0x4f855 (between two fixup'd instructions): same result, but the distance index is
# clamped to 27, the last own-type low-detail entry (entries 28..31 select structure 0 = the 36-vertex
# high-detail variant of types 3/6)
DETAIL_ORIG=bytes.fromhex('c1e202'+'8a440207'+'89c2'+'81e2ff000000'+'8b442420'+'c1e207'+'29f0')
DETAIL_CLAMP=bytes.fromhex('0fb6549007'+'c1e207'+'8b442420'+'29f0'+'83f81b'+'7e02'+'b01b'+'909090')
# texture level by block distance: table 0x14708 has 32 entries (+4 zero bytes); `ebp/4` -> min(ebp>>2,31)
MIP_ORIG=bytes.fromhex('89ea'+'89e8'+'c1fa1f'+'c1e202'+'1bc2'+'c1f802')
MIP_CLAMP=bytes.fromhex('89e8'+'c1f802'+'83f81f'+'7e02'+'b01f'+'909090')
# limits: scenery-object vertex buffers (0x4f540/0x51f70/0x549a0, 900 entries; measured over all 17 tracks:
# 847 at 44 blocks, 919 at 48); on open roads the finish line is 45 blocks before the end of the data; the block
# ring has 64 slots (window = 5 behind + draw + 2 ahead -> 57) and the block offset table 600 entries
DRAW_MAX=44
def far_track(d,draw,SRC,cap=2060):
    """really raise the track draw distance (blocks). Needs, besides the distance itself:
    - the streaming window (0x4f0f5: blocks loaded ahead of the car, 30) -> draw+2, otherwise blocks >= car+30 are
      stale ring slots; the ring has 64 slots
    - every block from the textured near zone up to draw-1 must be a low-detail one (11 vertices): 0x5a52e and
      0x5a0b7 compute the vertex base of the near blocks as total-11-(draw-near)*11
    - the view vertex copy 0x62578 (515 entries, followed by the camera globals) moved to a bigger block
    - a loader that skips an unreadable block (past the end of an open road) instead of waiting for a key"""
    assert 28<draw<=DRAW_MAX
    def put(v,old,new):
        fo=le.cfo(v); assert d[fo:fo+len(old)]==old,hex(v); assert not any(v+i in SRC for i in range(len(old))),hex(v)
        d[fo:fo+len(new)]=new
    I=lambda n:struct.pack('<I',n)
    # the distance: track load, race start, F key, 0x63304 (each: setting 0 = far), limits
    for v in (0x4f04e,0x5bbe9,0x48121,0x633e2,0x5b0dd,0x5b1a6,0x5b1c5): put(v,I(28),I(draw))
    for v in (0x5b0d9,0x5b19e,0x5b1bd): put(v-2,b'\x83\xf8\x1c',bytes((0x83,0xf8,draw)))
    # the setting [0x4d9d5] has three stages (F key, options menu, saved config): far / medium / near. Make them
    # draw / 28 (the original far) / the original medium; the original near is dropped
    for v,old,new in ((0x4812d,14,28),(0x48139,9,14),(0x633f8,14,28),(0x63412,9,14),(0x5bbfa,18,28),(0x5bc0b,13,18)): put(v,I(old),I(new))
    put(0x4f0f4,b'\xba'+I(30),b'\xba'+I(draw+2))                 # blocks loaded ahead; behind = this + 5
    put(0x4edf2,bytes.fromhex('e855550300ebc5'),bytes.fromhex('eb129090909090'))   # no 'TRKD' -> return 0
    put(0x4f83e,DETAIL_ORIG,DETAIL_CLAMP)
    for v in (0x59d67,0x5a055): put(v,MIP_ORIG,MIP_CLAMP)
    nb=add_obj4_block(d,cap*12); assert relocate_target(d,0x62578,nb)==4
    return nb
def relocate_range(d,lo,hi,new):
    """move every fixup target in [lo,hi) (obj4 offsets) to new+(target-lo); returns {old target: fixup count}"""
    T=sorted({t-0xE0000 for s,t,k in le.parse_fixups(bytes(d)) if lo<=t-0xE0000<hi})
    return {t:relocate_target(d,t,new+t-lo) for t in T}
# the engine is laid out for 10 cars at most (palette ranges 0x16ea0/0x16ec8/0x16ef0, shapes 0x693a4, the two
# 10-entry tables read by 0x80ab0/0x80ad4, 20 list slots in a replay key frame): 7 traffic cars + player +
# opponent + police. Tested in game, see docs/EXE.md "Car slots".
TRAFFIC_MAX=7
AI_ARGS_ORIG=bytes.fromhex('8d44245c'+'50'+'8d442454'+'8d4c2478'+'50'+'8d44244c'+'8d542408'+'50'+'89fb'+'89f0')
AI_ARGS_NEW=bytes.fromhex('8d442444'+'8d4818'+'51'+'8d480c'+'51'+'50'+'8d4830'+'8d5058'+'89fb'+'89f0'+'90909090')
def more_traffic(d,cars,SRC):
    """raise the number of traffic cars on open roads from 6 to `cars` (total 9 -> cars+3). Everything indexed by
    car number or list position that has only 9 slots is moved or grown:
    - lists 0x5c224 (drawn), 0x5c274 (rank), 0x5c298 (order) and the variable 0x5c270 (which is also the base of
      the rank list - 4) go to a new block, so the car pointers 0x5c24c can grow in place over 0x5c270
    - the variable 0x4dd08 behind the model list 0x4dce4, the byte lists 0x6e5bc and 0x4bd33
    - the per-car records (9 x 0x1d2 bytes from 0x6ea80, with the three dwords in front of them, which are
      also used as biased bases)
    - replay key frame: the rank list moves 4 bytes up inside the frame (order 10 + rank 10 slots); the cars
      that are not human get cars+2 instead of 8 slots of 0x172 bytes per key frame (16 key frames)
    - 0x7a040 keeps one lane mask per car in a stack array of 9 dwords at [esp], directly below 8 counters:
      frame 0x9c -> 0xc4, masks at [esp+0x9c] (the loop offset edx starts at 0x9c; the pointer for 0x78c88)"""
    assert 6<cars<=TRAFFIC_MAX
    def put(v,old,new):
        fo=le.cfo(v); assert d[fo:fo+len(old)]==old,hex(v); assert not any(v+i in SRC for i in range(len(old))),hex(v)
        assert len(new)==len(old); d[fo:fo+len(new)]=new
    I=lambda n:struct.pack('<I',n)
    put(0x36dd8,b'\xb9'+I(6),b'\xb9'+I(cars))
    nb=add_obj4_block(d,0x100); D,R,O,S=nb,nb+0x48,nb+0x8c,nb+0xd0     # 16 slots per list; R-8..R-1: biased bases
    moved=[(0x5c224,D,3),(0x5c26c,R-8,1),(0x5c270,R-4,6),(0x5c274,R,8),(0x5c278,R+4,3),(0x5c290,R+0x1c,1),
           (0x5c294,O-4,1),(0x5c298,O,16),(0x5c29c,O+4,3),(0x4dd08,S,14),(0x6e5bc,S+0x10,10),(0x4bd33,S+0x20,2),
           (0x63f10,0x63f14,1),(0x63f0c,0x63f10,1)]      # key frame rank list: reader first, then the writer (base - 4)
    for old,new,n in moved:
        got=relocate_target(d,old,new); assert got==n,(hex(old),got)
    recs=add_obj4_block(d,0xc+(cars+3)*0x1d2)
    got=relocate_range(d,0x6ea74,0x6fae0,recs)       # 0x6fae0 itself is `word ptr 0x6fae2` read as a dword
    assert len(got)==22 and sum(got.values())==99,got
    slots=cars+2; size=0xa500+16*slots*0x172
    for v in (0x5d07c,0x5d28a): put(v,b'\x69\xd2'+I(0xb90),b'\x69\xd2'+I(slots*0x172))
    put(0x5ddcb,b'\x68'+I(0x15e00),b'\x68'+I(size))
    for v in (0x5c443,0x5c562): put(v,b'\xba'+I(0x15e00),b'\xba'+I(size))
    put(0x7a046,bytes.fromhex('81ec9c000000'),bytes.fromhex('81ecc4000000'))
    put(0x7aea9,bytes.fromhex('81c49c000000'),bytes.fromhex('81c4c4000000'))
    put(0x7a0bb,b'\x31\xff',b'\x31\xd2')                                       # xor edi,edi -> xor edx,edx
    put(0x7a0c3,bytes.fromhex('89bc2490000000'),bytes.fromhex('89942490000000'))   # mov [esp+0x90],edi -> ,edx
    put(0x7a0d4,b'\x31\xd2',b'\xb2\x9c')                                       # xor edx,edx -> mov dl,0x9c
    put(0x7abda,AI_ARGS_ORIG,AI_ARGS_NEW)
    return nb,recs,moved,got
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
def build(orig_path,out_path,W=1280,H=960,tag='K',vesa=0x22B,steer=1,lod=1,segs=35,cardepth=None,draw=28,near=4,detail=None,force_detail=False,traffic=None,title=True,uniform=True,traffic_cars=6,traffic_active=4):
    g=L(W,H,uniform); d=bytearray(open(orig_path,'rb').read()) if isinstance(orig_path,str) else bytearray(orig_path)
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
    if draw<28:   # only the track-load value (overwritten at race start: no effect)
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
        for t in range(8):
            fo=dfo(0xE0000+0xd284+t*128); row=list(struct.unpack_from('<32i',d,fo))
            hi,med,lo=row[0],row[3],row[4]; n=detail or 4
            new=[hi]*(n-1)+[med]+[lo]*(28-n)+row[28:]   # entries 28..31 must stay 0 (crash otherwise)
            struct.pack_into('<32i',d,fo,*new)
        # scenery-object window: the engine drops ALL objects once more than 180 are active; the object
        # vertex buffers (0x4f540 / 0x51f70) hold 900 vertices; 440 was chosen assuming 2 per object (emulation: about 4, see docs/EXE.md)
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
    put(0xe8c80+16,[0,0,W,H,0,32,W,round(g.my(352))-32])   # 3D view height in the cockpit view (orig 320)
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
    if draw>28: log.append(('far_track',draw,hex(far_track(d,draw,SRC))))
    # more traffic cars / more of them active at the same time (docs/EXE.md "Car slots")
    if traffic_cars!=6: log.append(('more_traffic',traffic_cars)+tuple(hex(x) for x in more_traffic(d,traffic_cars,SRC)[:2]))
    if traffic_active!=4:
        assert 1<=traffic_active<=traffic_cars
        raw(0x63fae,'c7403404000000','c74034%02x000000'%traffic_active)   # [0x7d2f0], see docs/EXE.md
    if title:   # title screen with the patch credit line (FRONTEND/(G)ART/TITLEE.QFS)
        for v in (0xe2974,0xe4454):
            fo=dfo(v); assert d[fo:fo+12]==b'title.qfs\0\0\0',hex(v); d[fo:fo+11]=b'titlee.qfs\0'
    if out_path: open(out_path,'wb').write(d)
    return (bytes(d),log) if not out_path else log
if __name__=='__main__':
    W,H,tag,out=int(sys.argv[1]),int(sys.argv[2]),sys.argv[3],sys.argv[4]
    build(le.ORIG,os.path.join(le.GAME,out),W,H,tag); print('built',out)
