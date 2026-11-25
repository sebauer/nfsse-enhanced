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
def _link(items,base):
    """tiny linker for cave code: bytes | ('L',label) | ('j',opcode,label) rel8 | ('c',opcode,label or vaddr) rel32"""
    pos={}; o=0
    for it in items:
        if isinstance(it,bytes): o+=len(it)
        elif it[0]=='L': pos[it[1]]=o
        else: o+=len(it[1])+(1 if it[0]=='j' else 4)
    out=bytearray()
    for it in items:
        if isinstance(it,bytes): out+=it
        elif it[0]=='j':
            r=pos[it[2]]-(len(out)+len(it[1])+1); assert -128<=r<128,it; out+=it[1]+struct.pack('b',r)
        elif it[0]=='c':
            t=pos[it[2]]+base if isinstance(it[2],str) else it[2]; out+=it[1]+struct.pack('<i',t-(base+len(out)+len(it[1])+4))
    return bytes(out),{k:v+base for k,v in pos.items()}
ANALOG_CAVE=CAVE+0x80   # behind the 89 bytes of CAVE_CODE (extend_detail_table, disabled)
def analog_steering(d,SRC):
    """high-resolution joystick steering, live and in replays (option analog, docs/EXE.md).
    The joystick reader 0x4e0b8 scales raw X to a step j = -32..31 (about 45 raw counts per step; 35 steps from
    the centre to the calibrated end, 3 of them dead zone) and 0x4853c maps the step to an angle through the
    table 0xc538 (T): orig(j) = T[j+1] for j >= 1, +T[0] for j = 0, -T[-j] for j < 0. Here the position inside
    the step travels next to the control word and 0x4853c interpolates between two neighbouring orig() values:
      right: w = (x*gain >> 16) - 4 (0 at the edge of the dead zone, 30 where the original reaches full lock),
             w' = w*31/30, k = int(w')+1:  angle = orig(k-1) + frac(w') * (orig(k) - orig(k-1))
      left:  m = 0..31 likewise, m' = m*32/31, between orig(-(k-1)) and orig(-k)
    So the curve starts at the original centre value at the edge of the dead zone, reaches full lock exactly
    where the original does, is continuous and monotone in between and never more than one step away from the
    original stair. The dead zone and everything beyond full lock carry no fraction and are bit-identical.
    The stretch by 31/30 (32/31) is needed because the original jumps at both ends of that range (to T[2] at
    the dead zone, to T[32] at step 31): without it either the dead-zone edge keeps its jump or full lock moves
    one step further out, behind the calibrated end of the stick.
    orig() of the two neighbours is taken through the game's own packing rules (inverted axis 0x4dd28 with its
    +1 adjustments), so the inverted curve is continuous too.
    Fraction entry (dword): bit 31 valid, bits 16..21 key = the 6 steering bits of the word it belongs to, and
    the packed 16 bits that also go into a replay: 14..15 = lower neighbour's field - key + 2 (1..3, never 0),
    12..13 = upper neighbour's field - lower + 2 (0..3), 0..11 the weight F = 0..0xfff (4096 positions per step).
    The packed value is complete without the inversion flag or any other state. An entry is only used when the
    key equals the steering bits of the word 0x4853c gets, for the local player with steering device 1
    (joystick); live it is produced only on the single-machine path (0x49035, mode 0x7d136 = 0).
    Replays (stage 2): the replay buffer 0xf6b98 has control word streams for two humans (low bytes at p*0x1c20,
    high bytes at 0x3840+p*0x1c20, index 0x64ba4/4) and human key frames at 0x7080+p*0x1a40. With one human,
    player 1's streams and key frames are never written or read. The recorder (calls 0x5da42/0x5dab1) then
    stores the packed value of the entry in use for that step (0 if none or if its key is not the recorded
    word's) in player 1's streams and the magic at 0x8ac0 (player 1's key frame 0), if the human is player 0
    with a joystick. The reader (call 0x5dc7d) takes it back as the current entry, key = the steering bits of
    the word just read, only with the magic and one human; the device gate in 0x4853c then sees the recorded
    device (0x37561 copies it from the race description, which a replay file restores). The magic is cleared
    when the buffer is allocated (0x5dde4; heap memory is not initialised and a file read may be short).
    New obj4 block: +0 pending entry, +4 captured product, +8 captured flag, +0x10 current entry per player (8),
    +0x40 one ring of 64 entries per player (stride 0x18c like the control word structs 0x4cccc, same index).
    The caves have no fixups: the block address comes from the relocated operand at 0x4855b (address of T)."""
    def put(v,old,new):
        fo=le.cfo(v); old=bytes.fromhex(old); assert d[fo:fo+len(old)]==old,hex(v)
        assert not any(v+i in SRC for i in range(len(old))),hex(v); assert len(new)==len(old); d[fo:fo+len(new)]=new
    le_=0x2c80; ot=le_+struct.unpack_from('<I',d,le_+0x40)[0]
    assert struct.unpack_from('<I',d,ot)[0] in (0xaa9fd,0xab000); struct.pack_into('<I',d,ot,0xab000)   # obj1 size: whole last page
    assert 0x4855b in SRC and struct.unpack_from('<I',d,le.cfo(0x4855b))[0]==0xc538     # the anchor: mov edi,[edx*4+T]
    nb=add_obj4_block(d,0x40+8*0x18c); A=ANALOG_CAVE
    H=bytes.fromhex; I=lambda n:struct.pack('<i',n); G=lambda raw:I(raw-nb)   # obj4 variable relative to the block
    RING=I(nb+0x40-0x4cccc); CUR=I(nb+0x10-0x4d954)                         # relative to a struct / a word slot
    MAG=0x8ac0; M1,M2=(H(x) for x in ('4e465345','414e4131'))               # 'NFSEANA1' in the replay buffer
    P1L,P1H=I(0x1c20),I(0x5460)                                             # player 1's word streams
    code,lab=_link([
        ('L','gb'),H('e8000000005b'),H('8b9b')+I(0x4855b-(A+5)),H('8d9b')+I(nb-0xc538),H('c3'),   # ebx = block
        # 0x4e174/0x4e1a4: keep the product raw X * gain (eax) before the game shifts it down
        ('L','cap'),H('53'),('c',H('e8'),'gb'),H('894304'),H('c7430801000000'),H('5b'),H('c1f810'),H('89442410'),H('c3'),
        # 0x48c10 (the call of the joystick reader): build the pending entry from the product and the result
        ('L','wrap'),H('53'),('c',H('e8'),'gb'),H('c70300000000'),H('c7430800000000'),H('5b'),('c',H('e8'),0x4e0b8),
        H('60'),('c',H('e8'),'gb'),H('837b0800'),('j',H('75'),'go'),('L','done'),H('61'),H('c3'),
        ('L','go'),H('8b4304'),H('89c1'),H('c1f910'),H('85c0'),('j',H('7c'),'neg'),
        H('83e903'),H('83f901'),('j',H('7c'),'done'),H('83f91e'),('j',H('7f'),'done'),      # right: step 1..30
        H('3b8b')+G(0x4f260),('j',H('75'),'done'),H('89cf'),
        H('2d00000400'),H('6bc01f'),H('31d2'),H('b91e000000'),H('f7f1'),                    # w' = w*31/30 (16.16)
        H('89c6'),H('c1ee10'),H('25ffff0000'),H('c1e804'),H('89c5'),H('8d4e01'),('j',H('eb'),'com'),
        ('L','neg'),H('83c103'),H('83f9ff'),('j',H('7f'),'done'),H('83f9e1'),('j',H('7c'),'done'),   # left: -1..-31
        H('3b8b')+G(0x4f260),('j',H('75'),'done'),H('89cf'),
        H('f7d8'),H('2d00000300'),H('c1e005'),H('31d2'),H('b91f000000'),H('f7f1'),H('48'),  # m' = m*32/31, - 1 unit
        H('89c6'),H('c1ee10'),H('25ffff0000'),H('c1e804'),H('89c5'),H('8d4e01'),H('f7d9'),H('f7de'),
        ('L','com'),H('89f8'),('c',H('e8'),'fld'),H('89c7'),H('89f0'),('c',H('e8'),'fld'),H('89c6'),H('89c8'),('c',H('e8'),'fld'),
        H('29f0'),H('83c002'),H('83f803'),('j',H('77'),'done2'),                            # upper - lower + 2: 0..3
        H('29fe'),H('83c602'),H('8d56ff'),H('83fa02'),('j',H('77'),'done2'),                # lower - key + 2: 1..3
        H('c1e60e'),H('c1e00c'),H('c1e710'),H('09f0'),H('09f8'),H('09e8'),H('0d00000080'),H('8903'),
        ('L','done2'),H('61'),H('c3'),
        # steering value eax -> control word field, as 0x48c88..0x48cc2 does
        ('L','fld'),H('83bb')+G(0x4dd28)+H('00'),('j',H('74'),'fn'),H('83f81f'),('j',H('74'),'fi'),H('83f8e0'),('j',H('75'),'fs'),
        ('L','fi'),H('40'),('L','fs'),H('f7d8'),('L','fn'),H('83c020'),H('c3'),
        # 0x49035 (single machine: the word goes into the local player's ring): entry -> same ring index
        ('L','sto'),H('535156'),('c',H('e8'),'gb'),H('31c9'),H('870b'),H('833800'),('j',H('74'),'sout'),
        H('6683bb')+G(0x7d136)+H('00'),('j',H('75'),'sinv'),
        H('8bb3')+G(0x4dd58),H('8d3476'),H('83bcb3')+G(0x4d974)+H('01'),('j',H('75'),'sinv'),
        H('85c9'),('j',H('79'),'sinv'),H('89ce'),H('c1ee10'),H('31d6'),H('83e63f'),('j',H('74'),'sst'),
        ('L','sinv'),H('31c9'),
        ('L','sst'),H('8b7008'),H('89f3'),H('c1fb1f'),H('29de'),H('d1fe'),H('83e63f'),H('898cb0')+RING,
        ('L','sout'),H('5e595b'),('c',H('e9'),0x4918c),
        # 0x49554 (a word is taken from a ring): take the entry with it, empty the ring slot
        ('L','con'),H('51'),H('31c9'),H('878c98')+RING,H('898a')+CUR,H('59'),H('01db01d88b580a'),H('c3'),
        # 0x494d0 entry: no current entry unless a word is really taken
        ('L','ent'),H('873424'),H('55'),H('c782')+CUR+I(0),H('833800'),H('ffe6'),
        # 0x47c6d/0x6388e (control struct init): empty this player's ring, the pending and the current entries
        ('L','ini'),H('5351'),H('31c9'),('L','il'),H('c78488')+RING+I(0),H('41'),H('83f940'),('j',H('72'),'il'),
        ('c',H('e8'),'gb'),('c',H('e8'),'clr'),H('595b'),('c',H('e9'),0x48ec0),
        ('L','clr'),H('31c9'),H('890b'),H('b108'),('L','cl'),H('83648b0c00'),H('49'),('j',H('75'),'cl'),H('c3'),
        # 0x5dc7d (replay playback refills the words): the current entry comes from the replay or there is none
        ('L','rep'),H('5351'),('c',H('e8'),'gb'),('c',H('e8'),'clr'),H('595b'),('c',H('e8'),0x5cb58),
        H('60'),('c',H('e8'),'gb'),H('83bb')+G(0x4da30)+H('01'),('j',H('75'),'px'),
        H('8bbb')+G(0x16b98),H('85ff'),('j',H('74'),'px'),
        H('81bf')+I(MAG)+M1,('j',H('75'),'px'),H('81bf')+I(MAG+4)+M2,('j',H('75'),'px'),
        H('8b8b')+G(0x64ba4),H('c1e902'),H('81f9201c0000'),('j',H('73'),'px'),
        H('0fb6840f')+P1H,H('c1e008'),H('8a840f')+P1L,H('f6c4c0'),('j',H('74'),'px'),
        H('8b93')+G(0x4d954),H('83e23f'),H('c1e210'),H('09d0'),H('0d00000080'),H('894310'),
        ('L','px'),H('61'),H('c3'),
        # 0x5da42/0x5dab1 (the recorder 0x5cac4 is called): one human, player 0, joystick -> packed entry + magic
        ('L','rec'),H('60'),('c',H('e8'),'gb'),H('83bb')+G(0x4dd5c)+H('00'),('j',H('74'),'rx'),
        H('6683bb')+G(0x7d136)+H('01'),('j',H('74'),'rx'),H('83bb')+G(0x4da30)+H('01'),('j',H('75'),'rx'),
        H('83bb')+G(0x4dd58)+H('00'),('j',H('75'),'rx'),H('83bb')+G(0x4d974)+H('01'),('j',H('75'),'rx'),
        H('8bbb')+G(0x16b98),H('85ff'),('j',H('74'),'rx'),
        H('8b8b')+G(0x64ba4),H('c1e902'),H('81f9201c0000'),('j',H('73'),'rx'),
        H('31d2'),H('8b4310'),H('85c0'),('j',H('79'),'rw'),
        H('89c6'),H('c1ee10'),H('33b3')+G(0x4d954),H('83e63f'),('j',H('75'),'rw'),H('89c2'),
        ('L','rw'),H('88940f')+P1L,H('88b40f')+P1H,H('c787')+I(MAG)+M1,H('c787')+I(MAG+4)+M2,
        ('L','rx'),H('61'),('c',H('e9'),0x5cac4),
        # 0x5dde4 (replay buffer allocated, eax): no magic
        ('L','alc'),('c',H('e8'),0x828a8),H('85c0'),('j',H('74'),'ax'),H('83a0')+I(MAG)+H('00'),H('83a0')+I(MAG+4)+H('00'),
        ('L','ax'),('c',H('e9'),0x5dde9),
        # 0x48544 (analog steering): edi = target angle, continue at 0x4856e
        ('L','ana'),H('83e23f'),H('52'),('c',H('e8'),'gb'),H('89d0'),('c',H('e8'),'org'),
        H('8b817d040000'),H('83f807'),('j',H('77'),'ad'),H('3b83')+G(0x4dd58),('j',H('75'),'ad'),
        H('8d2c40'),H('83bcab')+G(0x4d974)+H('01'),('j',H('75'),'ad'),
        H('8b448310'),H('85c0'),('j',H('79'),'ad'),H('89c5'),H('c1ed10'),H('83e53f'),H('39d5'),('j',H('75'),'ad'),
        H('89c5'),H('c1e80e'),H('83e003'),H('8d4402fe'),H('83e03f'),H('50'),('c',H('e8'),'org'),H('58'),H('57'),   # lower field
        H('89ea'),H('c1ea0c'),H('83e203'),H('8d4410fe'),H('83e03f'),('c',H('e8'),'org'),                     # upper field
        H('58'),H('29c7'),H('97'),H('81e5ff0f0000'),H('f7ed'),H('0facd00c'),H('01c7'),      # lo + (hi-lo)*F >> 12
        ('L','ad'),H('5a'),('c',H('e9'),0x4856e),
        # the original lookup 0x48547..0x4856c: field eax -> edi
        ('L','org'),H('83e820'),H('83f801'),('j',H('7c'),'oa'),H('40'),('L','oa'),H('85c0'),('j',H('7c'),'on'),
        H('8bbc83')+G(0xc538),H('c3'),('L','on'),H('f7d8'),H('8bbc83')+G(0xc538),H('f7df'),H('c3')],A)
    assert A+len(code)<=0xbb000
    fo=le.cfo(A); assert d[fo:fo+len(code)]==bytes(len(code)) and not any(A+i in SRC for i in range(len(code)))
    d[fo:fo+len(code)]=code
    rel=lambda op,v,t:bytes((op,))+I(lab[t]-(v+5))
    put(0x48c10,'e8a3540000',rel(0xe8,0x48c10,'wrap'))
    for v in (0x4e174,0x4e1a4): put(v,'c1f8108944240c',rel(0xe8,v,'cap')+b'\x90\x90')
    put(0x49035,'e852010000',rel(0xe8,0x49035,'sto'))
    put(0x49554,'01db01d88b580a',rel(0xe8,0x49554,'con')+b'\x90\x90')
    put(0x494d0,'5655833800',rel(0xe8,0x494d0,'ent'))
    put(0x47c6d,'e84e120000',rel(0xe8,0x47c6d,'ini')); put(0x6388e,'e82d56feff',rel(0xe8,0x6388e,'ini'))
    put(0x5dc7d,'e8d6eeffff',rel(0xe8,0x5dc7d,'rep'))
    put(0x5da42,'e87df0ffff',rel(0xe8,0x5da42,'rec')); put(0x5dab1,'e80ef0ffff',rel(0xe8,0x5dab1,'rec'))
    put(0x5dde4,'e8bf4a0200',rel(0xe9,0x5dde4,'alc'))
    put(0x48544,'83e23f83ea20',rel(0xe9,0x48544,'ana')+b'\x90')
    return nb,lab,len(code)
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
def build(orig_path,out_path,W=1280,H=960,tag='K',vesa=0x22B,steer=1,lod=1,segs=35,cardepth=None,draw=28,near=4,detail=None,force_detail=False,traffic=None,title=True,uniform=True,traffic_cars=6,traffic_active=4,analog=False):
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
    # optional high-resolution joystick steering (stage 1: not stored in replays)
    if analog:
        nb,lab,n=analog_steering(d,SRC); log.append(('analog',hex(nb),hex(ANALOG_CAVE),n))
    if title:   # title screen with the patch credit line (FRONTEND/(G)ART/TITLEE.QFS)
        for v in (0xe2974,0xe4454):
            fo=dfo(v); assert d[fo:fo+12]==b'title.qfs\0\0\0',hex(v); d[fo:fo+11]=b'titlee.qfs\0'
    if out_path: open(out_path,'wb').write(d)
    return (bytes(d),log) if not out_path else log
if __name__=='__main__':
    W,H,tag,out=int(sys.argv[1]),int(sys.argv[2]),sys.argv[3],sys.argv[4]
    build(le.ORIG,os.path.join(le.GAME,out),W,H,tag); print('built',out)
