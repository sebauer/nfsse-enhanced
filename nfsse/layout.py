"""Resolution-independent version of the 1024x768 layout (HUD at 1x spread over the width,
cockpit scaled to fill rows 32..H-1)."""
class L:
    def __init__(s,W,H):
        s.W,s.H=W,H; s.SX=W/640; s.SY=(H-32)/448; s.DXR=W-640; s.DY=H-480
    def my(s,y): return 32+(y-32)*s.SY
    def hx(s,d1024):
        D=s.DXR
        return {0:0,16:16,96:D//4,192:D//2,288:3*D//4,352:D-32,368:D-16,384:D}[d1024]
    def hy(s,d1024): return {0:0,288:s.DY}[d1024]
