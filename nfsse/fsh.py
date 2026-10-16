"""FSH archive helpers: parse, palettes, images, quantisation, rebuild."""
import struct,numpy as np
from PIL import Image
def parse(d,base=0):
    n=struct.unpack_from('<I',d,base+8)[0]
    return [(d[base+16+8*i:base+20+8*i],base+struct.unpack_from('<I',d,base+20+8*i)[0]) for i in range(n)]
def shapes(d,base=0): return {nm.decode('latin1'):o for nm,o in parse(d,base)}
def palblock(u,o):
    if u[o]==0x22: return np.frombuffer(u,np.uint8,768,o+16).reshape(256,3).astype(np.float32)*255/63
    if u[o]==0x24: return np.frombuffer(u,np.uint8,768,o+16).reshape(256,3).astype(np.float32)
    return None
def gpal(u,base=0):
    sh=shapes(u,base)
    for k in ('!pal','!PAL','!paL','!Pal'):
        if k in sh: return palblock(u,sh[k])
def chain(att):
    out=[];p=0
    while p<len(att):
        t=att[p]; nx=att[p+1]|att[p+2]<<8|att[p+3]<<16
        out.append((t,nx,att[p:p+nx] if nx else att[p:]))
        if not nx: break
        p+=nx
    return out
def image(u,o,base=0):
    w,h=struct.unpack_from('<2H',u,o+4)
    px=np.frombuffer(u,np.uint8,w*h,o+16).reshape(h,w)
    pal=None; nxt=struct.unpack_from('<I',u,o)[0]>>8; a=o
    while nxt:
        a+=nxt; p=palblock(u,a)
        if p is not None: pal=p;break
        nxt=struct.unpack_from('<I',u,a)[0]>>8
    if pal is None: pal=gpal(u,base)
    rgba=np.zeros((h,w,4),np.uint8); rgba[...,:3]=pal[px]; rgba[...,3]=np.where(px==255,0,255)
    return Image.fromarray(rgba,'RGBA'),px,pal
def quant(rgb,P):
    out=np.empty(len(rgb),np.uint8); P=P[:255]
    for i in range(0,len(rgb),32768):
        ch=rgb[i:i+32768]; out[i:i+32768]=((ch[:,None,:]-P[None])**2).sum(2).argmin(1)
    return out
def rebuild(d,replace):
    de=parse(d); n=len(de)
    order=sorted(range(n),key=lambda i:de[i][1]); first=de[order[0]][1]
    out=bytearray(d[:first]); newoff={}
    for k,i in enumerate(order):
        nm,o=de[i]; end=de[order[k+1]][1] if k+1<n else len(d)
        newoff[i]=len(out); out+=replace.get(nm,d[o:end])
    for i in range(n): struct.pack_into('<I',out,20+8*i,newoff[i])
    struct.pack_into('<I',out,4,len(out)); return bytes(out)
