"""Resolution-independent version of the 1024x768 layout (HUD at 1x spread over the width,
cockpit below the 32-row HUD bar, scaled uniformly by W/640)."""
class L:
    def __init__(s,W,H,uniform=True):
        s.W,s.H=W,H; s.SX=W/640; s.SY=(H-32)/448; s.DXR=W-640; s.DY=H-480
        # cockpit = rows 32..479 of the 640x480 art. Default (uniform): scaled by SX in both directions and anchored at
        # the bottom; cockpit.fill_top fills the rows above (32 at 1280x960). uniform=False: stretched to fill rows
        # 32..H-1 (vertical scale SY, up to v0.9).
        s.CSY=s.SX if uniform else s.SY; s.CY0=H-448*s.SX if uniform else 32
    def my(s,y): return s.CY0+(y-32)*s.CSY
    def hx(s,d1024):
        D=s.DXR
        return {0:0,16:16,96:D//4,192:D//2,288:3*D//4,352:D-32,368:D-16,384:D}[d1024]
    def hy(s,d1024): return {0:0,288:s.DY}[d1024]
