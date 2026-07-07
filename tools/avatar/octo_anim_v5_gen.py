#!/usr/bin/env python3
"""
octo_anim_v5_gen.py — Animated sticker generator v5
Changes vs v4:
  - Tentacles: vertical stretch/contract (上下伸縮), NO left-right sway
  - Blink type-A (happy.png): erase smile arc → draw squinting arc → back
  - Blink type-B (wink.png left eye): erase circle eye → draw flat wink line → back
  - Base blink now correctly erases open eye before drawing closed line
"""

import sys, os, math, subprocess, shutil
from PIL import Image, ImageDraw

def generate_octopus_image(body_rgb=(150, 150, 150),
                            mood="base", eyewear="none",
                            headgear="none", item_r="none", item_l="none",
                            blush_style="oval", has_gold=False, size=64, scale=8, **_kw):
    """Standalone v2 octopus generator. Full replication of v1 component logic with targeted fixes:
    - chef hat: rectangle [28,14,36,18] (centered; was [24,14,32,18]); drawn before ellipse
    - love mood: blush_style is respected (v1 forced 'hearts')
    - all blush colors use alpha=255 (solid)
    """
    img  = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    px   = img.load()
    draw = ImageDraw.Draw(img)
    B      = ( 44,  44,  44, 255); GOLD   = (255, 215,   0, 255); W      = (255, 255, 255, 255)
    E      = (  0,   0,   0, 255); RED    = (255,  90,  90, 255); BLUE   = ( 52, 152, 219, 255)
    PINK   = (255, 182, 193, 255); SKY    = (135, 206, 235, 255); YELLOW = (255, 235,  59, 255)
    GREEN  = ( 46, 204, 113, 255); BROWN  = (121,  85,  72, 255); PURPLE = (155,  89, 182, 255)
    SILVER = (189, 195, 199, 255); TAN    = (210, 180, 140, 255); ORANGE = (255, 127,  80, 255)

    body_color = (*body_rgb, 255)
    for y in range(size):
        for x in range(size):
            if (x - 32)**2 + (y - 32)**2 < 14**2:
                px[x, y] = body_color

    lx, ly = 24, 30; rx, ry = 40, 30
    blush_y = ly + 6   # 36
    cur_blush_color = (255, 100, 150, 255)
    cur_blush_style = blush_style

    def draw_eye(ex, ey, eye_mood="standard"):
        if   eye_mood == "standard": draw.ellipse([ex-2,ey-2,ex+2,ey+2],fill=E); px[ex-1,ey-1]=W
        elif eye_mood == "smile":    draw.arc([ex-2,ey-2,ex+2,ey+2],start=200,end=340,fill=E,width=2)
        elif eye_mood == "closed":   draw.line([ex-2,ey+1,ex+2,ey+1],fill=E,width=2); draw.point([ex+2,ey],fill=E)
        elif eye_mood == "heart":    draw.polygon([(ex,ey+3),(ex-3,ey),(ex-1,ey-3),(ex,ey-1),(ex+1,ey-3),(ex+3,ey)],fill=RED); px[ex+1,ey-1]=W
        elif eye_mood == "star":     draw.ellipse([ex-2,ey-2,ex+2,ey+2],fill=E); draw.line([ex-2,ey,ex+2,ey],fill=W); draw.line([ex,ey-2,ex,ey+2],fill=W)
        elif eye_mood == "angry":    draw.polygon([(ex-2,ey-2),(ex+2,ey),(ex-2,ey+2)],fill=E)
        elif eye_mood == "smart":    draw.rectangle([ex-3,ey-2,ex+3,ey+2],fill=W,outline=GOLD)

    if   mood == "base":      draw_eye(lx,ly); draw_eye(rx,ry)
    elif mood == "happy":     draw_eye(lx,ly,"smile"); draw_eye(rx,ry,"smile")
    elif mood == "love":
        draw_eye(lx,ly,"heart"); draw_eye(rx,ry,"heart")
        draw.polygon([(32,12),(30,10),(31,8),(32,9),(33,8),(34,10)],fill=RED)
        # v2: do NOT force cur_blush_style="hearts" — caller's blush_style is used
    elif mood == "wink":
        draw_eye(lx,ly,"closed"); draw_eye(rx,ry,"standard")
        px[lx-3,ly-1]=YELLOW; px[lx-4,ly-2]=YELLOW
    elif mood == "surprised":
        draw.ellipse([lx-3,ly-3,lx+3,ly+3],fill=E); draw.ellipse([rx-3,ry-3,rx+3,ry+3],fill=E)
        px[lx-1,ly-1]=W; px[rx-1,ry-1]=W
    elif mood == "thinking":
        draw_eye(lx,ly); draw_eye(rx,ry)
        px[49,10]=YELLOW; px[50,10]=YELLOW; px[51,11]=YELLOW; px[50,12]=YELLOW; px[50,14]=YELLOW
    elif mood == "angry":
        draw_eye(lx,ly,"angry"); draw_eye(rx,ry,"angry")
        cur_blush_color = (200, 50, 50, 255)
        px[44,24]=RED; px[46,24]=RED; px[45,23]=RED; px[45,25]=RED
    elif mood == "sad":
        draw.line([lx-2,ly+1,lx+2,ly+1],fill=E); draw.line([rx-2,ry+1,rx+2,ry+1],fill=E)
        px[lx-1,ly+3]=BLUE; px[lx-1,ly+4]=BLUE
    elif mood == "excited":
        draw_eye(lx,ly,"star"); draw_eye(rx,ry,"star")
        px[lx-3,ly-3]=GOLD; px[rx+3,ry-3]=GOLD
    elif mood == "cool":
        draw.rectangle([lx-5,ly-2,rx+5,ry+2],fill=B,outline=SILVER); draw.line([lx-5,ly-1,rx+5,ly-1],fill=W)
    elif mood == "sleepy":
        draw.line([lx-2,ly,lx+2,ly],fill=E); draw.line([rx-2,ry,rx+2,ry],fill=E)
        px[48,12]=BLUE; px[50,10]=BLUE; px[52,8]=BLUE
    elif mood == "sleeping":
        draw.line([lx-2,ly,lx+2,ly],fill=E); draw.line([rx-2,ry,rx+2,ry],fill=E)
    elif mood in ("embarrassed","shy"):
        draw.line([(22,27),(26,30),(22,33)],fill=E,width=2); draw.line([(42,27),(38,30),(42,33)],fill=E,width=2)
        cur_blush_color=(255,100,150,255); px[20,24]=SKY
    elif mood == "smart":
        draw_eye(lx,ly,"smart"); draw_eye(rx,ry,"smart")
        draw.line([50,10,50,14],fill=YELLOW); px[50,16]=YELLOW; px[20,21]=GOLD

    for ox in [lx, rx]:
        if   cur_blush_style == "oval":      draw.ellipse([ox-2,blush_y,ox+2,blush_y+2],fill=cur_blush_color)
        elif cur_blush_style == "lightning": px[ox-2,blush_y]=cur_blush_color; px[ox-1,blush_y-1]=cur_blush_color; px[ox,blush_y]=cur_blush_color; px[ox+1,blush_y-1]=cur_blush_color; px[ox+2,blush_y]=cur_blush_color
        elif cur_blush_style == "stars":     px[ox,blush_y-1]=cur_blush_color; px[ox-1,blush_y]=cur_blush_color; px[ox,blush_y]=cur_blush_color; px[ox+1,blush_y]=cur_blush_color; px[ox,blush_y+1]=cur_blush_color
        elif cur_blush_style == "hearts":    px[ox-2,blush_y]=RED; px[ox-1,blush_y]=RED; px[ox+1,blush_y]=RED; px[ox+2,blush_y]=RED; px[ox-2,blush_y+1]=RED; px[ox-1,blush_y+1]=RED; px[ox,blush_y+1]=RED; px[ox+1,blush_y+1]=RED; px[ox+2,blush_y+1]=RED; px[ox-1,blush_y+2]=RED; px[ox,blush_y+2]=RED; px[ox+1,blush_y+2]=RED; px[ox,blush_y+3]=RED
        elif cur_blush_style == "dots":      px[ox-2,blush_y+1]=cur_blush_color; px[ox,blush_y+1]=cur_blush_color; px[ox+2,blush_y+1]=cur_blush_color
        elif cur_blush_style == "swirls":    draw.rectangle([ox-1,blush_y,ox+1,blush_y+2],fill=cur_blush_color)

    if   eyewear == "monocle":         draw.ellipse([rx-4,ry-4,rx+4,ry+4],outline=GOLD,width=1)
    elif eyewear == "monocle_left":    draw.ellipse([lx-4,ly-4,lx+4,ly+4],outline=GOLD,width=1)
    elif eyewear == "glasses":         draw.rectangle([lx-4,ly-4,lx+4,ly+4],outline=B); draw.rectangle([rx-4,ry-4,rx+4,ry+4],outline=B); draw.line([lx+4,ly,rx-4,ly],fill=B)
    elif eyewear == "round_glasses":   draw.ellipse([lx-4,ly-4,lx+4,ly+4],outline=B); draw.ellipse([rx-4,ry-4,rx+4,ry+4],outline=B); draw.line([lx+4,ly,rx-4,ly],fill=B)
    elif eyewear == "half_rim_glasses":
        for ex,ey in [(lx,ly),(rx,ry)]:
            draw.line([ex-4,ey-3,ex+4,ey-3],fill=B); draw.line([ex-4,ey-3,ex-4,ey+1],fill=B); draw.line([ex+4,ey-3,ex+4,ey+1],fill=B)
        draw.line([lx+4,ly-1,rx-4,ly-1],fill=B)

    if   headgear == "grad":         draw.polygon([(32,10),(42,15),(32,20),(22,15)],fill=B)
    elif headgear == "crown":        draw.polygon([(24,18),(24,12),(28,16),(32,10),(36,16),(40,12),(40,18)],fill=GOLD,outline=B); px[32,14]=RED
    elif headgear == "viking":       draw.ellipse([24,12,40,20],fill=SILVER,outline=B); draw.polygon([(24,16),(18,8),(26,14)],fill=W); draw.polygon([(40,16),(46,8),(38,14)],fill=W)
    elif headgear == "wizard":       draw.polygon([(22,18),(32,6),(42,18)],fill=PURPLE,outline=B); draw.rectangle([18,18,46,20],fill=PURPLE,outline=B)
    elif headgear == "ninja":        draw.rectangle([24,14,40,18],fill=B); draw.line([40,16,46,20],fill=B,width=2)
    elif headgear == "flower_crown":
        draw.ellipse([22,16,42,20],outline=GREEN,width=1)
        for _cx,_cy in [(26,17),(32,15),(38,17)]: draw.ellipse([_cx-2,_cy-2,_cx+2,_cy+2],fill=PINK); px[_cx,_cy]=YELLOW
    elif headgear == "fish":
        _fc=(255,127,80,255); draw.ellipse([22,12,42,20],fill=_fc); draw.polygon([(42,16),(48,12),(48,20)],fill=_fc); draw.polygon([(28,12),(33,10),(38,12)],fill=_fc); px[26,15]=W; draw.line([30,16,38,16],fill=B,width=1)
    elif headgear == "frog":
        draw.ellipse([24,14,40,20],fill=GREEN); draw.ellipse([25,10,31,16],fill=GREEN); draw.ellipse([33,10,39,16],fill=GREEN); draw.point([28,12],fill=E); draw.point([36,12],fill=E); draw.line([30,17,34,17],fill=B,width=1)
    elif headgear == "ribbon":       draw.polygon([(26,12),(32,15),(26,18)],fill=RED); draw.polygon([(38,12),(32,15),(38,18)],fill=RED)
    elif headgear == "tophat":       draw.rectangle([24,10,40,18],fill=B); draw.rectangle([20,18,44,20],fill=B); draw.line([24,16,40,16],fill=RED)
    elif headgear == "halo":         draw.ellipse([24,8,40,12],outline=GOLD,width=2)
    elif headgear == "chef":
        draw.rectangle([28, 14, 36, 18], fill=W, outline=B)   # v2: centered [28,14,36,18] (v1 was [24,14,32,18])
        draw.ellipse([24, 8, 40, 16], fill=W, outline=B)      # ellipse on top of rectangle
    elif headgear == "propeller":
        draw.chord([26,17,38,21],start=180,end=0,fill=RED)  # upper arc dome: top at y=17, flat base at y=19
        draw.line([32,17,32,13],fill=BROWN,width=1)          # spindle from dome peak to blade
        draw.line([24,13,40,13],fill=SILVER,width=2)         # blade
    elif headgear == "straw_hat":    draw.ellipse([16,16,48,20],fill=YELLOW,outline=B); draw.ellipse([24,10,40,18],fill=YELLOW,outline=B); draw.line([24,16,40,16],fill=RED)
    elif headgear == "cap":          draw.ellipse([26,12,38,20],fill=BLUE); draw.rectangle([34,16,44,18],fill=BLUE)
    elif headgear == "hard_hat":     draw.ellipse([24,12,40,20],fill=YELLOW); draw.rectangle([22,18,42,20],fill=YELLOW)
    elif headgear == "beret":        draw.ellipse([22,12,40,18],fill=RED); draw.line([32,12,34,10],fill=B)
    elif headgear == "pirate":       draw.polygon([(18,16),(32,8),(46,16),(32,20)],fill=B); draw.ellipse([30,12,34,16],fill=W)
    elif headgear == "nurse":        draw.ellipse([26,12,38,18],fill=W,outline=B); draw.line([32,14,32,16],fill=RED); draw.line([31,15,33,15],fill=RED)
    elif headgear == "police":       draw.ellipse([26,12,38,18],fill=BLUE); draw.rectangle([24,18,40,20],fill=B); draw.ellipse([31,14,33,16],fill=GOLD)
    elif headgear == "jester":       draw.polygon([(24,18),(20,10),(28,18)],fill=RED); draw.polygon([(32,18),(32,8),(36,18)],fill=BLUE); draw.polygon([(40,18),(44,10),(36,18)],fill=RED); draw.ellipse([19,9,21,11],fill=GOLD); draw.ellipse([31,7,33,9],fill=GOLD); draw.ellipse([43,9,45,11],fill=GOLD)
    elif headgear == "sombrero":     draw.ellipse([14,16,50,20],fill=GREEN); draw.polygon([(26,16),(32,6),(38,16)],fill=GREEN); draw.line([28,14,36,14],fill=RED)
    elif headgear == "santa":        draw.polygon([(24,18),(32,6),(40,18)],fill=RED); draw.ellipse([30,4,34,8],fill=W); draw.rectangle([22,16,42,20],fill=W)
    elif headgear == "elf":          draw.polygon([(26,18),(32,8),(38,18)],fill=GREEN); draw.rectangle([24,16,40,18],fill=RED); draw.ellipse([31,7,33,9],fill=GOLD)
    elif headgear == "traffic_cone": draw.polygon([(26,18),(32,6),(38,18)],fill=ORANGE); draw.line([28,14,36,14],fill=W); draw.line([29,10,35,10],fill=W)
    elif headgear == "apple":        draw.ellipse([26,10,38,20],fill=RED); draw.line([32,10,32,8],fill=BROWN); draw.ellipse([32,8,36,10],fill=GREEN)
    elif headgear == "cherry":       draw.ellipse([26,14,30,18],fill=RED); draw.ellipse([34,14,38,18],fill=RED); draw.line([24,14,28,10],fill=GREEN); draw.line([36,14,32,10],fill=GREEN)
    elif headgear == "mushroom":     draw.ellipse([22,10,42,20],fill=RED); draw.ellipse([26,12,30,16],fill=W); draw.ellipse([34,14,38,18],fill=W); draw.rectangle([28,18,36,22],fill=W)
    elif headgear == "earmuffs":     draw.arc([22,12,42,22],start=180,end=0,fill=RED,width=2); draw.ellipse([20,18,26,24],fill=PINK); draw.ellipse([38,18,44,24],fill=PINK)
    elif headgear == "ice_crown":    draw.polygon([(24,18),(24,10),(28,14),(32,8),(36,14),(40,10),(40,18)],fill=SKY)
    elif headgear == "paper_boat":   draw.polygon([(22,18),(32,8),(42,18)],fill=W); draw.polygon([(28,18),(32,8),(32,18)],fill=SILVER); draw.rectangle([20,18,44,20],fill=W)
    elif headgear == "magic_hat":    draw.polygon([(24,18),(32,6),(40,18)],fill=BROWN); draw.ellipse([20,16,44,20],fill=BROWN)
    elif headgear == "bowler_hat":   draw.ellipse([24,12,40,18],fill=B); draw.rectangle([20,16,44,18],fill=B)
    elif headgear == "headphones":   draw.arc([22,10,42,20],start=180,end=0,fill=B,width=2); draw.ellipse([20,16,26,22],fill=B); draw.ellipse([38,16,44,22],fill=B)
    elif headgear == "antenna":      draw.line([32,18,32,8],fill=SILVER,width=1); draw.ellipse([30,6,34,10],fill=RED)

    def draw_fleshy_tentacle(anchor_x, anchor_y, side, stretch, hook_w, hook_h):
        for i in range(11):
            t=i/10.0; _cx=anchor_x+(side*stretch)*t; _cy=anchor_y+4*t
            draw.ellipse([_cx-2,_cy-2,_cx+2,_cy+2],fill=body_color)
        mid_x=anchor_x+side*stretch; mid_y=anchor_y+4
        for i in range(11):
            t=i/10.0; _cx=mid_x+(side*hook_w)*t; _cy=mid_y-hook_h*t
            draw.ellipse([_cx-2,_cy-2,_cx+2,_cy+2],fill=body_color)
    draw_fleshy_tentacle(23,44,-1,4,4,5); draw_fleshy_tentacle(41,44,1,4,4,5)
    draw_fleshy_tentacle(29,46,-1,2,2,3); draw_fleshy_tentacle(35,46,1,2,2,3)

    def draw_handheld(item_type, side):
        _cx=52 if side=='r' else 12; _cy=38
        if   item_type=="flower":        draw.line([_cx,_cy+2,_cx,_cy+8],fill=GREEN); draw.point([_cx-1,_cy+5],fill=GREEN); draw.ellipse([_cx-3,_cy-3,_cx+3,_cy+3],fill=RED); px[_cx,_cy]=YELLOW; px[_cx-2,_cy-2]=PINK; px[_cx+2,_cy-2]=PINK
        elif item_type=="sword":         draw.rectangle([_cx-2,_cy-8,_cx+2,_cy+3],fill=SILVER,outline=B); draw.polygon([(_cx-2,_cy-8),(_cx,_cy-13),(_cx+2,_cy-8)],fill=SILVER,outline=B); draw.line([_cx,_cy-11,_cx,_cy+2],fill=W); draw.line([_cx-5,_cy+3,_cx+5,_cy+3],fill=GOLD,width=2); draw.rectangle([_cx-1,_cy+4,_cx+1,_cy+8],fill=BROWN,outline=B); draw.point([_cx,_cy+9],fill=GOLD)
        elif item_type=="shield":        draw.polygon([(_cx-5,_cy-5),(_cx+5,_cy-5),(_cx+5,_cy+2),(_cx,_cy+8),(_cx-5,_cy+2)],fill=SILVER,outline=B); draw.rectangle([_cx-2,_cy-5,_cx+2,_cy+3],fill=BLUE); draw.line([_cx,_cy-3,_cx,_cy+1],fill=W)
        elif item_type=="wand":          draw.line([_cx,_cy-10,_cx,_cy+8],fill=BROWN,width=1); draw.ellipse([_cx-2,_cy-12,_cx+2,_cy-8],fill=W,outline=B)
        elif item_type=="lantern":       draw.line([_cx,_cy-8,_cx,_cy-5],fill=B,width=1); draw.rectangle([_cx-3,_cy-5,_cx+3,_cy+5],fill=YELLOW,outline=B); draw.line([_cx-3,_cy-2,_cx+3,_cy-2],fill=ORANGE); draw.line([_cx-3,_cy+1,_cx+3,_cy+1],fill=ORANGE)
        elif item_type=="book":          draw.rectangle([_cx-4,_cy-5,_cx+4,_cy+5],fill=RED,outline=B); draw.line([_cx-1,_cy-5,_cx-1,_cy+5],fill=B)
        elif item_type=="scroll":        draw.ellipse([_cx-3,_cy-6,_cx+3,_cy-3],fill=TAN,outline=B); draw.rectangle([_cx-3,_cy-4,_cx+3,_cy+4],fill=TAN); draw.ellipse([_cx-3,_cy+3,_cx+3,_cy+6],fill=TAN,outline=B); draw.line([_cx-2,_cy-1,_cx+2,_cy-1],fill=B); draw.line([_cx-2,_cy+1,_cx+2,_cy+1],fill=B)
        elif item_type=="duck":          draw.ellipse([_cx-2,_cy-4,_cx+2,_cy],fill=YELLOW); draw.point([_cx-1,_cy-2],fill=E); draw.ellipse([_cx-5,_cy-1,_cx+5,_cy+5],fill=YELLOW); px[_cx+3 if side=='r' else _cx-3,_cy-2]=ORANGE
        elif item_type=="axe":           draw.line([_cx,_cy-6,_cx,_cy+8],fill=BROWN,width=2); draw.polygon([(_cx,_cy-6),(_cx+6 if side=='r' else _cx-6,_cy-10),(_cx+6 if side=='r' else _cx-6,_cy-2)],fill=SILVER,outline=B)
        elif item_type=="umbrella":      draw.chord([_cx-7,_cy-10,_cx+7,_cy-2],start=180,end=0,fill=BLUE,outline=B); draw.line([_cx,_cy-6,_cx,_cy+6],fill=B,width=1); draw.arc([_cx,_cy+4,_cx+3,_cy+7],start=0,end=180,fill=B)
        elif item_type=="balloon":       draw.ellipse([_cx-5,_cy-8,_cx+5,_cy+2],fill=RED); draw.polygon([(_cx-1,_cy+2),(_cx+1,_cy+2),(_cx,_cy+4)],fill=RED); draw.line([_cx,_cy+4,_cx,_cy+9],fill=B)
        elif item_type=="magnifier":     draw.line([_cx,_cy,_cx,_cy+6],fill=BROWN,width=2); draw.ellipse([_cx-4,_cy-8,_cx+4,_cy],outline=B,width=2); draw.ellipse([_cx-3,_cy-7,_cx+3,_cy-1],fill=SKY); px[_cx-1,_cy-5]=W
        elif item_type=="bow":           draw.arc([_cx-8,_cy-8,_cx+2,_cy+8],start=270,end=90,fill=BROWN,width=2); draw.line([_cx-3,_cy-8,_cx-3,_cy+8],fill=W); draw.line([_cx-8,_cy,_cx+3,_cy],fill=SILVER); draw.polygon([(_cx+3,_cy-2),(_cx+7,_cy),(_cx+3,_cy),(_cx+3,_cy+2)],fill=SILVER,outline=B)
        elif item_type=="spear":         draw.line([_cx,_cy-12,_cx,_cy+10],fill=BROWN,width=2); draw.polygon([(_cx-3,_cy-12),(_cx,_cy-22),(_cx+3,_cy-12)],fill=SILVER,outline=B); draw.point([(_cx-1,_cy-11),(_cx+1,_cy-11)],fill=RED)
        elif item_type=="crystal_ball":  draw.polygon([(_cx-4,_cy+6),(_cx+4,_cy+6),(_cx,_cy+2)],fill=GOLD,outline=B); draw.ellipse([_cx-4,_cy-6,_cx+4,_cy+2],fill=SKY,outline=W); px[_cx-1,_cy-4]=W
        elif item_type=="ice_cream":     draw.polygon([(_cx-3,_cy+2),(_cx+3,_cy+2),(_cx,_cy+8)],fill=BROWN,outline=B); draw.ellipse([_cx-3,_cy-2,_cx+3,_cy+3],fill=PINK,outline=B); draw.ellipse([_cx-3,_cy-6,_cx+3,_cy-1],fill=W,outline=B); px[_cx+1,_cy-7]=RED
        elif item_type=="key":           draw.ellipse([_cx-3,_cy-3,_cx+3,_cy+3],outline=GOLD,width=2); draw.line([_cx+3 if side=='r' else _cx-3,_cy,_cx+9 if side=='r' else _cx-9,_cy],fill=GOLD,width=2); draw.line([_cx+6 if side=='r' else _cx-6,_cy,_cx+6 if side=='r' else _cx-6,_cy+3],fill=GOLD); draw.line([_cx+8 if side=='r' else _cx-8,_cy,_cx+8 if side=='r' else _cx-8,_cy+3],fill=GOLD)
        elif item_type=="letter":        draw.rectangle([_cx-5,_cy-3,_cx+5,_cy+3],fill=W,outline=B); draw.line([_cx-5,_cy-3,_cx,_cy],fill=B); draw.line([_cx+5,_cy-3,_cx,_cy],fill=B); draw.ellipse([_cx-1,_cy-1,_cx+1,_cy+1],fill=RED)
        elif item_type=="laptop":        draw.polygon([(_cx-6,_cy+4),(_cx+6,_cy+4),(_cx+4,_cy+1),(_cx-4,_cy+1)],fill=SILVER,outline=B); draw.rectangle([_cx-4,_cy-5,_cx+4,_cy+1],fill=B,outline=SILVER); draw.rectangle([_cx-3,_cy-4,_cx+3,_cy],fill=SKY)
        elif item_type=="smartphone":    draw.rectangle([_cx-3,_cy-5,_cx+3,_cy+5],fill=B,outline=SILVER); draw.rectangle([_cx-2,_cy-4,_cx+2,_cy+3],fill=SKY); px[_cx,_cy+4]=W; px[_cx-1,_cy-4]=GREEN
        elif item_type=="battery":       draw.rectangle([_cx-3,_cy-4,_cx+3,_cy+6],fill=GREEN,outline=B); draw.rectangle([_cx-1,_cy-6,_cx+1,_cy-4],fill=SILVER,outline=B); draw.line([_cx-1,_cy+1,_cx+1,_cy+1],fill=W); draw.line([_cx,_cy,_cx,_cy+2],fill=W)
        elif item_type=="anchor":        draw.line([_cx,_cy-8,_cx,_cy+8],fill=GOLD,width=2); draw.line([_cx-4,_cy-6,_cx+4,_cy-6],fill=GOLD,width=2); draw.arc([_cx-6,_cy+2,_cx+6,_cy+10],start=0,end=180,fill=GOLD,width=2)
        elif item_type=="telescope":     draw.rectangle([_cx-3,_cy-6,_cx+3,_cy-2],fill=BROWN,outline=B); draw.rectangle([_cx-2,_cy-2,_cx+2,_cy+4],fill=BROWN,outline=B); draw.rectangle([_cx-1,_cy+4,_cx+1,_cy+8],fill=BROWN,outline=B); px[_cx,_cy-5]=SKY
        elif item_type=="burger":        draw.ellipse([_cx-4,_cy-4,_cx+4,_cy-1],fill=ORANGE); draw.rectangle([_cx-4,_cy-1,_cx+4,_cy+1],fill=BROWN); draw.line([_cx-4,_cy-1,_cx+4,_cy-1],fill=GREEN); draw.ellipse([_cx-4,_cy+1,_cx+4,_cy+4],fill=ORANGE)
        elif item_type=="compass":       draw.ellipse([_cx-5,_cy-5,_cx+5,_cy+5],outline=GOLD,width=2); draw.polygon([(_cx-2,_cy),(_cx+2,_cy),(_cx,_cy-4)],fill=RED); draw.polygon([(_cx-2,_cy),(_cx+2,_cy),(_cx,_cy+4)],fill=SILVER)
        elif item_type=="medal":         draw.line([_cx-2,_cy-6,_cx,_cy-2],fill=BLUE,width=2); draw.line([_cx+2,_cy-6,_cx,_cy-2],fill=BLUE,width=2); draw.ellipse([_cx-3,_cy-2,_cx+3,_cy+4],fill=GOLD,outline=B)
        elif item_type=="bell":          draw.line([_cx,_cy-2,_cx,_cy+2],fill=BROWN,width=2); draw.polygon([(_cx-4,_cy+8),(_cx+4,_cy+8),(_cx+2,_cy+2),(_cx-2,_cy+2)],fill=GOLD,outline=B); draw.point([_cx,_cy+9],fill=B)
        elif item_type=="baguette":      draw.ellipse([_cx-2,_cy-8,_cx+2,_cy+8],fill=TAN); draw.line([_cx-1,_cy-4,_cx+1,_cy-2],fill=BROWN); draw.line([_cx-1,_cy+2,_cx+1,_cy+4],fill=BROWN)
    draw_handheld(item_r, 'r')
    draw_handheld(item_l, 'l')

    return img.resize((size * scale, size * scale), Image.NEAREST)

SCALE   = 8
NFRAMES = 12
FPS     = 10

LX, LY = 24*SCALE, 30*SCALE   # 192, 240
RX, RY = 40*SCALE, 30*SCALE   # 320, 240

DARK   = (0,   0,   0,   255)
WHITE  = (255, 255, 255, 255)
GOLD   = (255, 215,   0,   255)
RED    = (255,  90,  90,   255)
BLUE   = ( 52, 152, 219,   255)
YELLOW = (255, 235,  59,   255)

def S(v): return v * SCALE

# ─── helpers ─────────────────────────────────────────────────────────────────

def draw_star(d, cx, cy, r, color):
    w = max(2, r // 3)
    d.line([cx-r, cy, cx+r, cy], fill=color, width=w)
    d.line([cx, cy-r, cx, cy+r], fill=color, width=w)
    d.ellipse([cx-r//3, cy-r//3, cx+r//3, cy+r//3], fill=color)

def draw_heart(d, cx, cy, r, color):
    d.ellipse([cx-r-1, cy-r, cx-1,   cy+2], fill=color)
    d.ellipse([cx+1,   cy-r, cx+r+1, cy+2], fill=color)
    d.polygon([(cx-r-2,cy+2),(cx+r+2,cy+2),(cx,cy+r+4)], fill=color)

def draw_smooth_heart(d, cx, cy, r, color):
    """Smooth heart via parametric equations: x=r·sin³t, y scaled from heart formula."""
    pts = []
    for i in range(60):
        t = -math.pi + 2 * math.pi * i / 60
        px = cx + int(r * math.sin(t)**3)
        py_val = 13*math.cos(t) - 5*math.cos(2*t) - 2*math.cos(3*t) - math.cos(4*t)
        py = cy - int(r * py_val * 0.65 / 13)
        pts.append((px, py))
    if len(pts) >= 3:
        d.polygon(pts, fill=color)

def draw_z(d, cx, cy, sz, color):
    d.line([cx,    cy,    cx+sz, cy],    fill=color, width=max(2,sz//5))
    d.line([cx+sz, cy,    cx,    cy+sz], fill=color, width=max(2,sz//5))
    d.line([cx,    cy+sz, cx+sz, cy+sz], fill=color, width=max(2,sz//5))

def blink_stars(d, ex, ey):
    draw_star(d, ex+34, ey-22, 9,  GOLD)
    draw_star(d, ex-34, ey-22, 7,  YELLOW)

def _draw_blush64(d, px64, ox, style, color, enlarged=False):
    """Draw one cheek blush on a 64×64 pixel-art canvas at cheek x=ox.
    enlarged=True → angry scale (9×7 at y=34-40); False → standard (5×3 at y=36-38)."""
    if enlarged:
        by, r, h = 34, 4, 6   # angry: 9px wide × 7px tall
    else:
        by, r, h = 36, 2, 2   # normal: 5px wide × 3px tall
    cy = by + h // 2

    if style == 'oval':
        # Explicit pixel rows to avoid PIL small-ellipse diamond artifact
        if enlarged:
            # 9×7 oval: rows narrow→wide→narrow
            for hx in (-1, 0, 1):
                if 0<=ox+hx<64: px64[ox+hx, by] = color; px64[ox+hx, by+6] = color
            for hx in range(-2, 3):
                if 0<=ox+hx<64: px64[ox+hx, by+1] = color; px64[ox+hx, by+5] = color
            for hx in range(-3, 4):
                if 0<=ox+hx<64: px64[ox+hx, by+2] = color; px64[ox+hx, by+4] = color
            for hx in range(-r, r+1):
                if 0<=ox+hx<64: px64[ox+hx, by+3] = color
        else:
            # 5×3 oval
            for hx in (-1, 0, 1):
                if 0<=ox+hx<64: px64[ox+hx, by] = color; px64[ox+hx, by+2] = color
            for hx in range(-r, r+1):
                if 0<=ox+hx<64: px64[ox+hx, by+1] = color

    elif style == 'stars':
        d.rectangle([ox-r, cy-1, ox+r, cy+1], fill=color)
        d.rectangle([ox-1, by,   ox+1, by+h], fill=color)

    elif style == 'dots':
        if enlarged:
            # Three 3×3 square blocks with 1px gap between each (spans ox-5 to ox+5)
            for tx in (ox-5, ox-1, ox+3):
                d.rectangle([tx, cy-1, tx+2, cy+1], fill=color)
        else:
            # Three 2×2 square blocks with 1px gap between each (spans ox-4 to ox+3)
            for tx in (ox-4, ox-1, ox+2):
                d.rectangle([tx, cy-1, tx+1, cy], fill=color)

    elif style == 'lightning':
        half = h // 2
        q = (r + 1) // 2   # r=4→q=2, r=2→q=1 (all segments 45°)
        pts = [ox-r, by, ox-q, by+half, ox, by, ox+q, by+half, ox+r, by]
        d.line(pts, fill=color, width=max(1, h//4))

    elif style == 'swirls':
        sq = h  # enlarged: 6×6 block, normal: 2×2 block
        d.rectangle([ox - sq//2, by, ox + sq//2, by + sq], fill=color)

    elif style == 'hearts':
        if enlarged:
            # Angry enlarged heart: 9px wide × 7 rows (bigger than embarrassed's 7×6)
            for hx, hy in [(-4,-2),(-3,-2),(+3,-2),(+4,-2),
                           (-4,-1),(-3,-1),(-2,-1),(-1,-1),(+1,-1),(+2,-1),(+3,-1),(+4,-1),
                           (-4, 0),(-3, 0),(-2, 0),(-1, 0),(0, 0),(+1, 0),(+2, 0),(+3, 0),(+4, 0),
                           (-3, 1),(-2, 1),(-1, 1),(0, 1),(+1, 1),(+2, 1),(+3, 1),
                           (-2, 2),(-1, 2),(0, 2),(+1, 2),(+2, 2),
                           (-1, 3),(0, 3),(+1, 3),
                           (0, 4)]:
                nx, ny = ox+hx, cy+hy
                if 0 <= nx < 64 and 0 <= ny < 64: px64[nx, ny] = color
        else:
            # Normal 5×4 heart
            for hx, hy in [(-2,0),(-1,0),(1,0),(2,0),
                           (-2,1),(-1,1),(0,1),(1,1),(2,1),
                           (-1,2),(0,2),(1,2),(0,3)]:
                nx, ny = ox+hx, by+hy
                if 0 <= nx < 64 and 0 <= ny < 64: px64[nx, ny] = color

# ─── motion config (vertical bob + tentacle stretch, no sway) ─────────────────
# (bob_amp, stretch_range, bob_freq)
# bob_amp      : vertical shift amplitude in scaled pixels (very gentle)
# stretch_range: tentacle vertical stretch ±range (e.g. 0.06 = ±6%)
# bob_freq     : cycles per 12-frame loop (2 = double-bounce for energetic moods)

_PI = math.pi
MOTION = {
    'base':      (5,  0.05, 1),
    'happy':     (7,  0.06, 1),
    'love':      (4,  0.04, 1),
    'wink':      (6,  0.05, 1),
    'surprised': (5,  0.07, 2),   # fast double-shake
    'thinking':  (4,  0.04, 1),
    'angry':     (4,  0.03, 1),   # tremor added in code
    'sad':       (5,  0.04, 1),
    'excited':   (9,  0.09, 2),   # big double-bounce
    'cool':      (5,  0.05, 1),
    'sleepy':    (3,  0.02, 1),
    'sleeping':  (2,  0.01, 1),
    'embarrassed':(3,  0.03, 1),
}

# ─── blink / alternation frames (at 64×64 logical scale, then ×8 resize) ────
#
# happy:   smile arc ↔ standard circle (原型眼), no stars
# base:    both eyes close (flat line), no stars
# wink:    left eye open (原型眼) ↔ left eye closed, stars on close
#
BLINK_FRAMES          = {4, 5}
SURPRISED_BIG_FRAMES  = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}   # big eye stays 10 frames (≈83% of cycle)

def make_blink_frame(mood, body_rgb, headgear, eyewear, item_r, item_l, blush_style='oval'):
    """Generate alternation frame at 64×64 then resize ×8."""
    img64 = generate_octopus_image(
        body_rgb=body_rgb, mood=mood,
        eyewear=eyewear, headgear=headgear,
        item_r=item_r, item_l=item_l,
        blush_style=blush_style,
        size=64, scale=1
    ).convert('RGBA')
    d  = ImageDraw.Draw(img64)
    px = img64.load()

    if mood == 'happy':
        # Alternate smile arcs → standard circles (原型眼), no blink-close, no stars
        for ex, ey in [(24, 30), (40, 30)]:
            d.ellipse([ex-3, ey-3, ex+3, ey+3], fill=(*body_rgb, 255))  # erase smile arc
            d.ellipse([ex-2, ey-2, ex+2, ey+2], fill=DARK)              # standard circle
            px[ex-1, ey-1] = (255, 255, 255, 255)                       # highlight

    else:  # base: both eyes close flat-line style, no stars
        for ex, ey in [(24, 30), (40, 30)]:
            d.ellipse([ex-3, ey-3, ex+3, ey+3], fill=(*body_rgb, 255))  # erase
            d.line([ex-2, ey+1, ex+2, ey+1], fill=DARK, width=2)
            d.point([ex+2, ey], fill=DARK)

    return img64.resize((512, 512), Image.NEAREST)


def make_wink_open_frame(body_rgb, headgear, eyewear, item_r, item_l, blush_style='oval'):
    """Wink open state: left eye shows as standard circle (原型眼), right stays standard."""
    img64 = generate_octopus_image(
        body_rgb=body_rgb, mood='wink', eyewear=eyewear, headgear=headgear,
        item_r=item_r, item_l=item_l, blush_style=blush_style, size=64, scale=1
    ).convert('RGBA')
    d  = ImageDraw.Draw(img64)
    px = img64.load()
    lx, ly = 24, 30  # left eye logical coords
    # Erase yellow sparkle pixels (lx-4,ly-2) and (lx-3,ly-1) from wink mood
    px[lx-4, ly-2] = (*body_rgb, 255)
    px[lx-3, ly-1] = (*body_rgb, 255)
    d.ellipse([lx-3, ly-3, lx+3, ly+3], fill=(*body_rgb, 255))  # erase closed-wink eye
    d.ellipse([lx-2, ly-2, lx+2, ly+2], fill=DARK)              # standard circle
    px[lx-1, ly-1] = (255, 255, 255, 255)                       # highlight
    return img64.resize((512, 512), Image.NEAREST)


def make_wink_closed_frame(body_rgb, headgear, eyewear, item_r, item_l, blush_style='oval'):
    """Wink closed state: left eye wink-closed with star sparkles (yellow sparkle pixels removed)."""
    img64 = generate_octopus_image(
        body_rgb=body_rgb, mood='wink', eyewear=eyewear, headgear=headgear,
        item_r=item_r, item_l=item_l, blush_style=blush_style, size=64, scale=1
    ).convert('RGBA')
    px = img64.load()
    lx, ly = 24, 30
    # Erase yellow sparkle pixels from wink mood
    px[lx-4, ly-2] = (*body_rgb, 255)
    px[lx-3, ly-1] = (*body_rgb, 255)
    img512 = img64.resize((512, 512), Image.NEAREST)
    ov  = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
    dov = ImageDraw.Draw(ov)
    blink_stars(dov, LX, LY)  # stars beside left (wink) eye
    return Image.alpha_composite(img512, ov)


def make_surprised_frame(fi, body_rgb, headgear, eyewear, item_r, item_l, blush_style='oval'):
    """Normal frames: standard eye (5×5); SURPRISED_BIG_FRAMES: big surprised eye (7×7)."""
    img64 = generate_octopus_image(
        body_rgb=body_rgb, mood='surprised', eyewear=eyewear, headgear=headgear,
        item_r=item_r, item_l=item_l, blush_style=blush_style, size=64, scale=1
    ).convert('RGBA')
    px = img64.load()
    d  = ImageDraw.Draw(img64)
    if fi not in SURPRISED_BIG_FRAMES:
        for ex, ey in [(24, 30), (40, 30)]:
            d.ellipse([ex-3, ey-3, ex+3, ey+3], fill=(*body_rgb, 255))  # erase big eye
            d.ellipse([ex-2, ey-2, ex+2, ey+2], fill=DARK)              # standard eye
            px[ex-1, ey-1] = (255, 255, 255, 255)                        # highlight center-left
    else:
        for ex, ey in [(24, 30), (40, 30)]:
            px[ex-1, ey-1] = DARK                   # fill old highlight with black (inside eye)
            px[ex-2, ey-2] = (255, 255, 255, 255)   # highlight upper-left corner of big eye
        # "!" near upper-left of face — 1px wide bar + dot, GOLD, synced with big eye
        for y in range(14, 19):        # bar: 5px tall, beside face
            px[12, y] = GOLD
        px[12, 21] = GOLD              # dot
    return img64.resize((512, 512), Image.NEAREST)


def make_love_base_img(fi, body_rgb, headgear, eyewear, item_r, item_l, blush_style='oval'):
    """Generate love base at 64×64, erase head heart, draw pixel-art eye hearts, resize.
    fi drives heart size variation: small ↔ large alternates every 6 frames."""

    # Small heart (5 wide × 5 tall) — blush + extra middle row for roundness
    HEART_SM = [
        (-2,-2),(-1,-2),(1,-2),(2,-2),              # two 2px humps, gap at x=0
        (-2,-1),(-1,-1),(0,-1),(1,-1),(2,-1),        # 5px
        (-2, 0),(-1, 0),(0, 0),(1, 0),(2, 0),        # 5px (extra row → rounder)
        (-1, 1),(0, 1),(1, 1),                        # 3px
        (0, 2),                                       # tip
    ]
    # Large heart (7 wide × 7 tall) — full 7×7 bounding box
    HEART_LG = [
        (-3,-3),(-2,-3),(-1,-3),(1,-3),(2,-3),(3,-3),          # 6px top (gap only at x=0)
        (-3,-2),(-2,-2),(-1,-2),(0,-2),(1,-2),(2,-2),(3,-2),   # 7px (y=-2)
        (-3,-1),(-2,-1),(-1,-1),(0,-1),(1,-1),(2,-1),(3,-1),   # 7px (y=-1)
        (-2, 0),(-1, 0),(0, 0),(1, 0),(2, 0),                  # 5px (y=0)
        (-2, 1),(-1, 1),(0, 1),(1, 1),(2, 1),                  # 5px (y=1)
        (-1, 2),(0, 2),(1, 2),                                  # 3px (y=2)
        (0, 3),                                                 # tip (y=3)
    ]
    heart_pts = HEART_LG if fi >= NFRAMES // 2 else HEART_SM
    erase_r   = 3 if fi < NFRAMES // 2 else 5

    img64 = generate_octopus_image(
        body_rgb=body_rgb, mood='love', eyewear=eyewear, headgear=headgear,
        item_r=item_r, item_l=item_l, blush_style=blush_style, size=64, scale=1
    ).convert('RGBA')
    px = img64.load()
    d  = ImageDraw.Draw(img64)

    # 1. Erase head heart → transparent (sits above body on transparent background)
    for x in range(28, 36):
        for y in range(6, 14):
            if px[x, y][:3] == (255, 90, 90):
                px[x, y] = (0, 0, 0, 0)

    # 2. Replace octo_generator heart eyes with pixel-art hearts (no white pixel — adds 8×8 block)
    RED_PX = (255, 90, 90, 255)
    for ex, ey in [(24, 30), (40, 30)]:
        d.ellipse([ex-erase_r, ey-erase_r, ex+erase_r, ey+erase_r], fill=(*body_rgb, 255))
        for dx, dy in heart_pts:
            nx, ny = ex+dx, ey+dy
            if 0 <= nx < 64 and 0 <= ny < 64:
                px[nx, ny] = RED_PX

    return img64.resize((512, 512), Image.NEAREST)


# ─── vertical float + tentacle stretch ───────────────────────────────────────

STRETCH_SPLIT = 340   # below body equator, above tentacle anchors

def apply_vertical_float(img, bob_px, stretch_ratio):
    """
    Shift whole image up/down by bob_px.
    Additionally stretch/compress the tentacle region vertically.
    stretch_ratio > 1 → tentacles extend; < 1 → tentacles contract.
    """
    # 1. Body bob: shift entire image
    shifted = Image.new('RGBA', (512, 512), (0,0,0,0))
    shifted.paste(img, (0, -bob_px))

    # 2. Tentacle vertical stretch
    if abs(stretch_ratio - 1.0) < 0.001:
        return shifted

    split_y = STRETCH_SPLIT - bob_px
    split_y = max(100, min(460, split_y))   # clamp to safe range

    top    = shifted.crop((0, 0,       512, split_y))
    bottom = shifted.crop((0, split_y, 512, 512))

    new_h  = max(1, int(bottom.height * stretch_ratio))
    stretched = bottom.resize((512, new_h), Image.BILINEAR)

    result = Image.new('RGBA', (512, 512), (0,0,0,0))
    result.paste(top,      (0, 0))
    result.paste(stretched, (0, split_y), stretched)
    return result


# ─── per-mood facial overlays ────────────────────────────────────────────────

def draw_overlay(img, mood, fi, nf, body_rgb, blush_style='oval', eyewear='none'):
    overlay = Image.new('RGBA', img.size, (0,0,0,0))
    d = ImageDraw.Draw(overlay)
    t     = fi / nf
    phase = t * 2 * _PI

    if mood == 'love':
        # Floating hearts: 2 hearts alternating between upper-left and upper-right corners
        # Eye hearts are drawn as pixel-art in make_love_base_img (8-bit style)
        corner_x = [S(16), S(48)]   # left x=128, right x=384 (near body sides)
        for i in range(2):
            ht = (t + i * 0.5) % 1.0
            hx = corner_x[i]
            hy = int(S(20) - ht * S(17))
            ha = int(255 * max(0, 1 - ht * 1.1))
            if ha > 0:
                draw_heart(d, hx, hy, int(7 + 2*math.sin(phase+i)), (*RED[:3], ha))

    elif mood == 'thinking':
        # Erase ? pixels precisely at exact logical positions (transparent bg — alpha=0, not body_rgb)
        px_src = img.load()
        for lx, ly in [(49,10),(50,10),(51,11),(50,12),(50,14)]:
            for ix in range(lx*8, lx*8+8):
                for iy in range(ly*8, ly*8+8):
                    px_src[ix, iy] = (0, 0, 0, 0)

        # 8-bit pixel-art thought bubbles + lightbulb (all drawn as 8×8 logical blocks)
        # fi 0:    nothing
        # fi 1:    bubble 1 (circle, near head)
        # fi 2:    bubble 1 + bubble 2 (same size circle, higher)
        # fi 3-11: both bubbles + lightbulb (9 frames)

        def lp(lx, ly, color):
            if 0 <= lx < 64 and 0 <= ly < 64:
                d.rectangle([lx*8, ly*8, lx*8+7, ly*8+7], fill=color)

        WCLOUD = (255, 255, 255, 220)
        YBULB  = (255, 220,   0, 255)
        GBULB  = (185, 150,   0, 255)
        SBULB  = (255, 255, 255, 255)
        FBULB  = (255, 248, 130, 220)

        # Two same-size 3×3 circles — cross shape (cut 4 corners for round look)
        BUBBLE_PX = [
                    (0,-1),
            (-1,0),(0,0),(1,0),
                    (0,1),
        ]

        B1_CX, B1_CY = 46, 18   # bubble 1: near head
        B2_CX, B2_CY = 50, 14   # bubble 2: above bubble 1

        # Lightbulb: bigger (3→5→7→7→7→5→3 + base), center logical (51, 4)
        BL_CX, BL_CY = 51, 4
        BL_GLASS = [
            (-1,-3),(0,-3),(1,-3),                                        # 3-wide rounded top
            (-2,-2),(-1,-2),(0,-2),(1,-2),(2,-2),                        # 5-wide
            (-3,-1),(-2,-1),(-1,-1),(0,-1),(1,-1),(2,-1),(3,-1),         # 7-wide
            (-3,0),(-2,0),(-1,0),(0,0),(1,0),(2,0),(3,0),                # 7-wide
            (-3,1),(-2,1),(-1,1),(0,1),(1,1),(2,1),(3,1),                # 7-wide
            (-2,2),(-1,2),(0,2),(1,2),(2,2),                             # 5-wide
            (-1,3),(0,3),(1,3),                                          # 3-wide neck
        ]
        BL_BASE = [
            (-1,4),(0,4),(1,4),   # 3-wide base (flush with neck, no side protrusion)
            (-1,5),(0,5),(1,5),   # 3-wide bottom
        ]
        BL_RAYS = [(-5,-3),(0,-3),(5,-3), (-6,0),(6,0), (-5,3),(5,3)]

        if fi >= 1:
            for dx, dy in BUBBLE_PX:
                lp(B1_CX+dx, B1_CY+dy, WCLOUD)
            lp(B1_CX, B1_CY-1, SBULB)          # bubble 1 shine (top pixel)

        if fi >= 2:
            for dx, dy in BUBBLE_PX:
                lp(B2_CX+dx, B2_CY+dy, WCLOUD)
            lp(B2_CX, B2_CY-1, SBULB)          # bubble 2 shine (top pixel)

        if fi >= 3:
            for dx, dy in BL_GLASS:
                lp(BL_CX+dx, BL_CY+dy, YBULB)
            for dx, dy in BL_BASE:
                lp(BL_CX+dx, BL_CY+dy, GBULB)
            lp(BL_CX-1, BL_CY-3, SBULB)        # bulb shine (near rounded top)
            if fi % 2 == 1:                     # twinkling rays on odd frames
                for dx, dy in BL_RAYS:
                    lp(BL_CX+dx, BL_CY+dy, FBULB)
            # Eyes → happy smile-arc when lightbulb is lit (exact match to happy.webm)
            # Erase circular eyes directly on img
            for ex, ey in [(24, 30), (40, 30)]:
                for ix in range((ex-3)*8, (ex+4)*8):
                    for iy in range((ey-3)*8, (ey+4)*8):
                        px_src[ix, iy] = (*body_rgb, 255)
            # Draw smile arc at 64×64 then NEAREST scale ×8 → composite onto img
            eye64 = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            ed = ImageDraw.Draw(eye64)
            for ex, ey in [(24, 30), (40, 30)]:
                ed.arc([ex-2, ey-2, ex+2, ey+2], start=200, end=340, fill=DARK, width=2)
            img.alpha_composite(eye64.resize((512, 512), Image.NEAREST))

    elif mood == 'angry':
        # fi=0-2 round eyes; fi=3-11 V-eyes (75% dwell, like thinking)
        angry_eyes = fi >= 3

        # 1. Erase base triangular angry eyes + vein pixels on img
        px_a = img.load()
        for ex, ey in [(24, 30), (40, 30)]:
            for ix in range((ex - 3) * 8, (ex + 4) * 8):
                for iy in range((ey - 3) * 8, (ey + 4) * 8):
                    px_a[ix, iy] = (*body_rgb, 255)
        for vx, vy in [(44, 24), (46, 24), (45, 23), (45, 25)]:
            for ix in range(vx * 8, vx * 8 + 8):
                for iy in range(vy * 8, vy * 8 + 8):
                    px_a[ix, iy] = (0, 0, 0, 0)   # 透明拔除

        # 2. Draw eyes (+ brows/blush if V-eye frame) at 64×64 → NEAREST ×8
        face64 = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        fd = ImageDraw.Draw(face64)
        if angry_eyes:
            # Filled circle eyes (brow inner tip dips into eye top → natural half-moon 向內)
            for ex, ey in [(24, 30), (40, 30)]:
                fd.ellipse([ex-2, ey-2, ex+2, ey+2], fill=DARK)
            # V-brows: inner tips press DOWN to eye upper edge → merge with inner-upper eye
            # Left brow \: outer (21,25) high → inner (26,29) dips to eye top
            fd.line([21, 25, 26, 29], fill=DARK, width=2)
            # Right brow /: inner (38,29) dips to eye top → outer (43,25) high
            fd.line([38, 29, 43, 25], fill=DARK, width=2)
            # Erase base small blush from img so it doesn't show through enlarged blush gaps
            # Only overwrite non-transparent pixels to avoid painting body_rgb outside octopus outline
            for ox_b in (24, 40):
                for ix in range((ox_b - 5) * 8, (ox_b + 6) * 8):
                    for iy in range(33 * 8, 42 * 8):
                        if 0 <= ix < 512 and 0 <= iy < 512 and px_a[ix, iy][3] > 0:
                            px_a[ix, iy] = (*body_rgb, 255)
            # Enlarged blush — style follows blush_style parameter
            BLUSH_C = (200, 50, 50, 255)
            px64_angry = face64.load()
            for ox in (24, 40):
                _draw_blush64(fd, px64_angry, ox, blush_style, BLUSH_C, enlarged=True)
        else:
            # Round eyes with highlight
            for ex, ey in [(24, 30), (40, 30)]:
                fd.ellipse([ex-2, ey-2, ex+2, ey+2], fill=DARK)
                face64.load()[ex-1, ey-1] = WHITE
        img.alpha_composite(face64.resize((512, 512), Image.NEAREST))

        # 3. Smoke from head top when V-eyes showing
        if angry_eyes:
            for i in range(3):
                st = (t + i * 0.33) % 1.0
                sx = S(26) + i * S(4)
                sy = int(S(11) - st * S(9))
                sr = int(5 + int(st * 5))
                sa = int(160 * (1 - st))
                d.ellipse([sx-sr, sy-sr, sx+sr, sy+sr], fill=(210, 210, 210, sa))

    elif mood == 'sad':
        # 1. Erase existing eye + brow region on base image
        px_s = img.load()
        for ex, ey in [(24, 30), (40, 30)]:
            for ix in range((ex-4)*8, (ex+5)*8):
                for iy in range((ey-6)*8, (ey+4)*8):
                    if px_s[ix, iy][3] > 0:   # only erase non-transparent pixels
                        px_s[ix, iy] = (*body_rgb, 255)

        # 2. Draw watery eyes at 64×64 → NEAREST ×8
        face64 = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        fd = ImageDraw.Draw(face64)
        px64 = face64.load()

        # Watery large eyes: radius 3 + v1 cross-style highlight
        for ex, ey in [(24, 30), (40, 30)]:
            fd.ellipse([ex-3, ey-3, ex+3, ey+3], fill=DARK)
            fd.ellipse([ex-2, ey-2, ex,   ey  ], fill=WHITE)   # main highlight
            if 0 <= ex+1 < 64 and 0 <= ey-2 < 64:
                px64[ex+1, ey-2] = WHITE                        # sparkle dot

        img.alpha_composite(face64.resize((512, 512), Image.NEAREST))

        # 3. 含淚: wide oval tear pools below each eye (first ref style)
        TEAR_C = (150, 190, 230, 200)
        for i, cx in enumerate([LX, RX]):
            ty = LY + S(3)   # just below eye
            tw = 20 + int(3 * math.sin(phase + i * _PI))   # gentle width pulse
            ta = int(185 + 55 * math.sin(phase * 1.5 + i * _PI))  # opacity trembling
            d.ellipse([cx - tw, ty, cx + tw, ty + 14],
                      fill=(*TEAR_C[:3], min(255, ta)))
            # Small white glint inside tear pool
            d.ellipse([cx - tw//2 + 2, ty + 2, cx - tw//4 + 2, ty + 6],
                      fill=(225, 242, 255, 130))

    elif mood == 'excited':
        for i in range(5):
            ang = phase + i*(2*_PI/5)
            sx  = int(S(32) + S(17)*math.cos(ang))
            sy  = int(S(32) + S(17)*math.sin(ang))
            sr  = int(7 + 3*math.sin(ang*2))
            draw_star(d, sx, sy, sr, (*GOLD[:3], 210))

    elif mood == 'cool':
        # Draw 8-bit oval sunglasses at 64×64 → NEAREST ×8 on base image
        sg64  = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        sgd   = ImageDraw.Draw(sg64)
        LENS  = (15, 15, 20, 230)        # dark tinted lens
        FRAME = (200, 200, 210, 255)     # silver frame
        lx64, rx64, ly64 = 24, 40, 30
        # Left lens: 10×6 square
        sgd.rectangle([lx64-5, ly64-3, lx64+5, ly64+3], fill=LENS, outline=FRAME)
        # Right lens: 10×6 square
        sgd.rectangle([rx64-5, ly64-3, rx64+5, ly64+3], fill=LENS, outline=FRAME)
        # Bridge between lenses
        sgd.line([lx64+5, ly64, rx64-5, ly64], fill=FRAME, width=1)
        img.alpha_composite(sg64.resize((512, 512), Image.NEAREST))

        # Animated glint sweep left→right across each lens
        for lx_gl in (LX, RX):
            gx = int(lx_gl - S(4) + (t * S(8)) % S(8))
            for j in range(2):
                d.point([gx + j*2, LY - S(1)], fill=(*WHITE[:3], 170))

        # 帥氣十字光 — flashes at top-right corner of right lens
        # Right lens top-right corner in 512px: (RX+S(5), LY-S(3)) = (360, 216)
        star_cx = RX + S(5)       # 360
        star_cy = LY - S(3)       # 216
        star_a  = int(max(0, math.sin(phase * 2)) * 235)   # 2 flashes per cycle
        if star_a > 20:
            sr   = 18 + int(6 * star_a / 235)   # ray length 18-24px
            STAR = (255, 255, 210)
            # Main cross (4 rays)
            d.line([star_cx - sr, star_cy, star_cx + sr, star_cy], fill=(*STAR, star_a), width=2)
            d.line([star_cx, star_cy - sr, star_cx, star_cy + sr], fill=(*STAR, star_a), width=2)
            # Diagonal rays (shorter)
            sd = sr * 2 // 3
            d.line([star_cx-sd, star_cy-sd, star_cx+sd, star_cy+sd], fill=(*STAR, star_a*2//3), width=1)
            d.line([star_cx-sd, star_cy+sd, star_cx+sd, star_cy-sd], fill=(*STAR, star_a*2//3), width=1)
            # Bright center
            d.ellipse([star_cx-5, star_cy-5, star_cx+5, star_cy+5],
                      fill=(255, 255, 255, min(255, star_a + 30)))

    elif mood == 'sleepy':
        # 8-bit pixel art eyes: down-arc (fi 0-6), pop (fi 6), shocked (fi 7-11)
        px_s = img.load()
        # Erase base eyes (all frames) — zone ±S(5) to fit shocked circle r=4+outline
        for ex in (LX, RX):
            for ix in range(ex - S(5), ex + S(5) + 1):
                for iy in range(LY - S(5), LY + S(5) + 1):
                    if 0 <= ix < 512 and 0 <= iy < 512 and px_s[ix, iy][3] > 0:
                        px_s[ix, iy] = (*body_rgb, 255)

        ARC_PX = [(-3,0),(-2,1),(-1,2),(0,2),(1,2),(2,1),(3,0)]
        bx, by = 256, LY + S(4)

        if fi <= 6:  # sleeping: 8-bit arc eyes + bubble
            for ex64, ey64 in [(24, 30), (40, 30)]:
                for dx, dy in ARC_PX:
                    d.rectangle([S(ex64+dx), S(ey64+dy),
                                 S(ex64+dx)+SCALE-1, S(ey64+dy)+SCALE-1],
                                fill=(*DARK[:3], 255))
            if fi <= 4:
                br = 6 + fi * 5
                d.ellipse([bx-br, by-br, bx+br, by+br],
                          outline=(*DARK[:3], 210), fill=(255,255,255,45), width=2)
                hl = max(2, br // 4)
                d.ellipse([bx-br//2-hl, by-br//2-hl, bx-br//2+hl, by-br//2+hl],
                          fill=(255,255,255,180))
            elif fi == 5:
                br = 32
                d.ellipse([bx-br, by-br, bx+br, by+br],
                          outline=(*DARK[:3], 210), fill=(255,255,255,45), width=2)
                d.ellipse([bx-19, by-19, bx-11, by-11], fill=(255,255,255,180))
            elif fi == 6:  # pop burst
                for ang in range(0, 360, 45):
                    rad = math.radians(ang)
                    d.line([int(bx+18*math.cos(rad)), int(by+18*math.sin(rad)),
                            int(bx+38*math.cos(rad)), int(by+38*math.sin(rad))],
                           fill=(*DARK[:3], 210), width=2)
                for ang in range(22, 360, 45):
                    rad = math.radians(ang)
                    d.ellipse([int(bx+28*math.cos(rad))-3, int(by+28*math.sin(rad))-3,
                               int(bx+28*math.cos(rad))+3, int(by+28*math.sin(rad))+3],
                              fill=(*DARK[:3], 180))

        else:  # fi 7-11: shocked awake (5 frames) — 8-bit round eyes (5×5 minus corners)
            for ex64, ey64 in [(24, 30), (40, 30)]:
                # Dark outer: 5×5 with 4 corners cut → proper 8-bit circle look
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        if abs(dx) == 2 and abs(dy) == 2:
                            continue  # cut corners to avoid diamond shape
                        d.rectangle([S(ex64+dx), S(ey64+dy),
                                     S(ex64+dx)+SCALE-1, S(ey64+dy)+SCALE-1],
                                    fill=(*DARK[:3], 255))
                # White inner: 3×3 solid
                for dy in range(-1, 2):
                    for dx in range(-1, 2):
                        d.rectangle([S(ex64+dx), S(ey64+dy),
                                     S(ex64+dx)+SCALE-1, S(ey64+dy)+SCALE-1],
                                    fill=(*WHITE[:3], 255))

    elif mood == 'sleeping':
        # 8-bit down-arc eyes (all frames) + Z-bubbles on right side of head
        px_s = img.load()
        for ex in (LX, RX):
            for ix in range(ex - S(4), ex + S(4) + 1):
                for iy in range(LY - S(4), LY + S(4) + 1):
                    if 0 <= ix < 512 and 0 <= iy < 512 and px_s[ix, iy][3] > 0:
                        px_s[ix, iy] = (*body_rgb, 255)

        ARC_PX = [(-3,0),(-2,1),(-1,2),(0,2),(1,2),(2,1),(3,0)]
        for ex64, ey64 in [(24, 30), (40, 30)]:
            for dx, dy in ARC_PX:
                d.rectangle([S(ex64+dx), S(ey64+dy),
                             S(ex64+dx)+SCALE-1, S(ey64+dy)+SCALE-1],
                            fill=(*DARK[:3], 255))

        # Z-bubbles: start from face right edge, float diagonally upper-right
        bx_orig, by_orig = 396, LY + S(2)
        for t_off, br, zsz in [(0.0, 8, 6), (0.33, 16, 12), (0.66, 24, 18)]:
            bt = (t + t_off) % 1.0
            bx   = int(bx_orig + bt * S(9))   # drift right +72px
            by_b = int(by_orig - bt * S(16))  # rise up  -128px
            ba   = int(210 * (1.0 - bt))
            if ba > 15:
                d.ellipse([bx-br, by_b-br, bx+br, by_b+br],
                          outline=(*DARK[:3], ba), fill=(255,255,255, ba//6), width=2)
                hl = max(2, br // 4)
                d.ellipse([bx-br//2-hl, by_b-br//2-hl,
                           bx-br//2+hl, by_b-br//2+hl],
                          fill=(255, 255, 255, min(255, ba+40)))
                hz = zsz // 2
                draw_z(d, bx - hz, by_b - hz, zsz, (*BLUE[:3], ba))

    elif mood == 'embarrassed':
        # Base image uses 'base' mood (no SKY pixel, clean base)
        px_s = img.load()
        # Erase base circle eyes (r=2 in 64-unit, erase ±5 to be safe)
        for ex in (LX, RX):
            for ix in range(ex - S(5), ex + S(5) + 1):
                for iy in range(LY - S(5), LY + S(5) + 1):
                    if 0 <= ix < 512 and 0 <= iy < 512 and px_s[ix, iy][3] > 0:
                        px_s[ix, iy] = (*body_rgb, 255)
        # Erase base blush (y=35~41 in 64-unit) so animated blush can fully fade to transparent
        for ox in (LX, RX):
            for ix in range(ox - S(5), ox + S(5) + 1):
                for iy in range(S(34), S(42)):
                    if 0 <= ix < 512 and 0 <= iy < 512 and px_s[ix, iy][3] > 0:
                        px_s[ix, iy] = (*body_rgb, 255)
        face64 = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        fd = ImageDraw.Draw(face64)
        # Upward arc eyes: explicit pixel list guarantees left-right symmetry
        # Peak at dy=-3 (more pronounced than happy's r=2 arc), 2-pixel thick toward baseline
        ARC_UP = [(-3,0),(-2,-1),(-1,-2),(0,-3),(1,-2),(2,-1),(3,0)]
        for ex64, ey64 in [(24, 30), (40, 30)]:
            for dx, dy in ARC_UP:
                fd.point([ex64+dx, ey64+dy], fill=(*DARK[:3], 255))
                if dy < 0:  # thicken inward (toward baseline)
                    fd.point([ex64+dx, ey64+dy+1], fill=(*DARK[:3], 255))
        # Blush: medium size, synced with sweat drop — both peak when drop reaches bottom
        sd_t  = (t * 0.9) % 1.0   # same timeline as sweat drop below
        ba = int(220 * (0.30 + 0.70 * sd_t))  # 66→193: lightest at top, darkest at bottom
        BLUSH_C = (255, 120, 160, min(255, ba))
        px64_emb = face64.load()
        by_m, r_m, h_m = 35, 3, 4   # medium: 6×4 in 64px (normal=4×2, angry=8×6)
        cy_m = by_m + h_m // 2       # 37
        for ox in (24, 40):
            if blush_style == 'oval':
                # Explicit pixel oval (PIL small ellipse renders as diamond artifact)
                for hx in (-1, 0, 1):
                    px64_emb[ox+hx, by_m] = BLUSH_C
                    px64_emb[ox+hx, by_m+h_m] = BLUSH_C
                for hx in range(-2, 3):
                    px64_emb[ox+hx, by_m+1] = BLUSH_C
                    px64_emb[ox+hx, by_m+h_m-1] = BLUSH_C
                for hx in range(-r_m, r_m+1):
                    px64_emb[ox+hx, by_m+2] = BLUSH_C
            elif blush_style == 'stars':
                fd.rectangle([ox-r_m, cy_m-1, ox+r_m, cy_m+1], fill=BLUSH_C)
                fd.rectangle([ox-1, by_m, ox+1, by_m+h_m], fill=BLUSH_C)
            elif blush_style == 'dots':
                # Three 2×2 square blocks, 1px gap between each
                for tx in (ox-4, ox-1, ox+2):
                    fd.rectangle([tx, cy_m-1, tx+1, cy_m], fill=BLUSH_C)
            elif blush_style == 'lightning':
                # r=4 (偶數) → q=2，所有線段均為 45°，完美對稱 W 形
                rl = 4; ql = 2; half = h_m // 2
                pts = [ox-rl, by_m, ox-ql, by_m+half, ox, by_m, ox+ql, by_m+half, ox+rl, by_m]
                fd.line(pts, fill=BLUSH_C, width=max(1, h_m//4))
            elif blush_style == 'swirls':
                fd.rectangle([ox-2, by_m, ox+2, by_m+h_m], fill=BLUSH_C)
            elif blush_style == 'hearts':
                # Enlarged heart: 7px wide × 6px tall (normal is 5×4)
                for hx, hy in [(-3,-2),(-2,-2),(+2,-2),(+3,-2),
                               (-3,-1),(-2,-1),(-1,-1),(+1,-1),(+2,-1),(+3,-1),
                               (-3, 0),(-2, 0),(-1, 0),(0, 0),(+1, 0),(+2, 0),(+3, 0),
                               (-2, 1),(-1, 1),(0, 1),(+1, 1),(+2, 1),
                               (-1, 2),(0, 2),(+1, 2),
                               (0, 3)]:
                    nx, ny = ox+hx, cy_m+hy
                    if 0 <= nx < 64 and 0 <= ny < 64:
                        px64_emb[nx, ny] = BLUSH_C
            else:
                fd.ellipse([ox-r_m, by_m, ox+r_m, by_m+h_m], fill=BLUSH_C)
        # 8-bit sweat drop: water-drop silhouette (pointed top, fat bottom = 1,3,5,5,3)
        SWEAT_PX = [
            (0,-2),
            (-1,-1),(0,-1),(1,-1),
            (-2,0),(-1,0),(0,0),(1,0),(2,0),
            (-2,1),(-1,1),(0,1),(1,1),(2,1),
            (-1,2),(0,2),(1,2),
        ]
        # sd_t already computed above (synced with blush)
        sd_y  = int(22 + sd_t * 5)       # slides y=22→27 in 64×64
        sd_a  = int(255 * sd_t)           # 先淡再深：透明→不透明，到底最深
        SWEAT = (*BLUE[:3], min(255, sd_a))
        if sd_a > 10:
            for dx, dy in SWEAT_PX:
                px_x, px_y = 47+dx, sd_y+dy
                if 0 <= px_x < 64 and 0 <= px_y < 64:
                    fd.point([px_x, px_y], fill=SWEAT)
            if sd_a > 60:   # 降低門檻：讓亮點在半途就出現
                hl_x, hl_y = 46, sd_y-1
                if 0 <= hl_x < 64 and 0 <= hl_y < 64:
                    face64.load()[hl_x, hl_y] = (220, 240, 255, min(255, sd_a))
        img.alpha_composite(face64.resize((512, 512), Image.NEAREST))

    # Redraw eyewear on top so it's never covered by face overlays
    # Skip for 'cool' — it has its own sunglasses overlay
    if eyewear != 'none' and mood != 'cool':
        ew64 = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        ew_d = ImageDraw.Draw(ew64)
        _B    = (44,  44,  44,  255)
        _GOLD = (255, 215,   0,  255)
        lx64, ly64, rx64 = 24, 30, 40
        if eyewear == 'glasses':
            ew_d.rectangle([lx64-4, ly64-4, lx64+4, ly64+4], outline=_B)
            ew_d.rectangle([rx64-4, ly64-4, rx64+4, ly64+4], outline=_B)
            ew_d.line([lx64+4, ly64, rx64-4, ly64], fill=_B)
        elif eyewear == 'round_glasses':
            ew_d.ellipse([lx64-4, ly64-4, lx64+4, ly64+4], outline=_B)
            ew_d.ellipse([rx64-4, ly64-4, rx64+4, ly64+4], outline=_B)
            ew_d.line([lx64+4, ly64, rx64-4, ly64], fill=_B)
        elif eyewear == 'monocle':
            ew_d.ellipse([rx64-4, ly64-4, rx64+4, ly64+4], outline=_GOLD, width=1)
        elif eyewear == 'monocle_left':
            ew_d.ellipse([lx64-4, ly64-4, lx64+4, ly64+4], outline=_GOLD, width=1)
        img.alpha_composite(ew64.resize((512, 512), Image.NEAREST))

    return Image.alpha_composite(img.convert('RGBA'), overlay)


# ─── main frame generator ────────────────────────────────────────────────────

BLINK_MOODS = {'base', 'happy'}

def generate_frame(fi, mood, body_rgb, headgear='crown', eyewear='none',
                   item_r='none', item_l='none', blush_style='oval'):
    t     = fi / NFRAMES
    phase = t * 2 * _PI
    bob_amp, stretch_range, bob_freq = MOTION[mood]

    # ── 1. Base image ──────────────────────────────────────────────────────
    if mood in BLINK_MOODS and fi in BLINK_FRAMES:
        img = make_blink_frame(mood, body_rgb, headgear, eyewear, item_r, item_l, blush_style)
    elif mood == 'wink':
        if fi in BLINK_FRAMES:
            img = make_wink_closed_frame(body_rgb, headgear, eyewear, item_r, item_l, blush_style)
        else:
            img = make_wink_open_frame(body_rgb, headgear, eyewear, item_r, item_l, blush_style)
    elif mood == 'love':
        img = make_love_base_img(fi, body_rgb, headgear, eyewear, item_r, item_l, blush_style)
        img = draw_overlay(img, mood, fi, NFRAMES, body_rgb, blush_style, eyewear)
    elif mood == 'surprised':
        img = make_surprised_frame(fi, body_rgb, headgear, eyewear, item_r, item_l, blush_style)
    elif mood in ('sleepy', 'sleeping'):
        # Use base mood so overlay can replace eyes with down-arc
        img = generate_octopus_image(
            body_rgb=body_rgb, mood='base',
            eyewear=eyewear, headgear=headgear,
            item_r=item_r, item_l=item_l,
            blush_style=blush_style,
            size=64, scale=SCALE
        ).convert('RGBA')
        img = draw_overlay(img, mood, fi, NFRAMES, body_rgb, blush_style, eyewear)
    elif mood == 'cool':
        # Use base mood (no visor); overlay draws its own sunglasses — eyewear is suppressed
        img = generate_octopus_image(
            body_rgb=body_rgb, mood='base',
            eyewear='none', headgear=headgear,
            item_r=item_r, item_l=item_l,
            blush_style=blush_style,
            size=64, scale=SCALE
        ).convert('RGBA')
        img = draw_overlay(img, mood, fi, NFRAMES, body_rgb, blush_style, 'none')
    elif mood == 'embarrassed':
        # Use base mood: embarrassed generator draws SKY blue pixel + fixed blush that break overlay
        img = generate_octopus_image(
            body_rgb=body_rgb, mood='base',
            eyewear=eyewear, headgear=headgear,
            item_r=item_r, item_l=item_l,
            blush_style=blush_style,
            size=64, scale=SCALE
        ).convert('RGBA')
        img = draw_overlay(img, mood, fi, NFRAMES, body_rgb, blush_style, eyewear)
    else:
        img = generate_octopus_image(
            body_rgb=body_rgb, mood=mood,
            eyewear=eyewear, headgear=headgear,
            item_r=item_r, item_l=item_l,
            blush_style=blush_style,
            size=64, scale=SCALE
        ).convert('RGBA')
        img = draw_overlay(img, mood, fi, NFRAMES, body_rgb, blush_style, eyewear)

    # ── 2. Vertical bob + tentacle stretch (上下伸縮, no horizontal sway) ──
    if mood == 'angry':
        bob_raw = math.sin(phase) + 0.35 * math.sin(phase * 5)
        bob_px  = round(bob_raw * bob_amp * 0.7)
    else:
        bob_px = round(math.sin(phase * bob_freq) * bob_amp)

    stretch_ratio = 1.0 + math.sin(phase * bob_freq) * stretch_range

    result = apply_vertical_float(img, bob_px, stretch_ratio)
    return result


# ─── sticker builder ─────────────────────────────────────────────────────────

ALL_MOODS = [
    'base','happy','love','wink','surprised','thinking',
    'angry','sad','excited','cool','sleepy','sleeping','embarrassed'
]

def generate_sticker(mood, body_rgb=(130,80,200), headgear='crown',
                     eyewear='none', item_r='none', item_l='none',
                     frame_dir='/tmp/octo_v5_frames', out_webm='/tmp/octo_v5.webm',
                     fps=None, blush_style='oval'):
    actual_fps = fps if fps is not None else FPS
    os.makedirs(frame_dir, exist_ok=True)
    for fi in range(NFRAMES):
        frame = generate_frame(fi, mood, body_rgb, headgear, eyewear, item_r, item_l, blush_style)
        frame.save(f'{frame_dir}/frame_{fi:03d}.png')

    subprocess.run([
        'ffmpeg', '-y',
        '-framerate', str(actual_fps),
        '-i', f'{frame_dir}/frame_%03d.png',
        '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p',
        '-auto-alt-ref', '0', '-b:v', '400k', '-crf', '28',
        '-loop', '0', '-an', out_webm
    ], check=True, capture_output=True)

    shutil.rmtree(frame_dir, ignore_errors=True)
    return out_webm


if __name__ == '__main__':
    BODY_RGB = (130, 80, 200)
    OUT_DIR  = '/home/kenzan/ai-project/services/OctoMatrix/agent_home/Solas/project/octo_animated_v5'
    os.makedirs(OUT_DIR, exist_ok=True)

    for mood in ALL_MOODS:
        print(f'  {mood}...', end='', flush=True)
        generate_sticker(
            mood=mood, body_rgb=BODY_RGB, headgear='crown',
            frame_dir=f'/tmp/octo_v5_{mood}',
            out_webm=f'{OUT_DIR}/{mood}.webm'
        )
        kb = os.path.getsize(f'{OUT_DIR}/{mood}.webm') / 1024
        print(f' {kb:.1f} KB')

    # Item test
    print('  excited+sword...', end='', flush=True)
    generate_sticker(
        mood='excited', body_rgb=BODY_RGB, headgear='crown', item_r='sword',
        frame_dir='/tmp/octo_v5_sword',
        out_webm=f'{OUT_DIR}/excited_sword.webm'
    )
    print(f' {os.path.getsize(f"{OUT_DIR}/excited_sword.webm")/1024:.1f} KB')

    print('Done.')
