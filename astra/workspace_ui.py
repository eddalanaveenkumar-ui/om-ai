"""Desktop workspace presentation; automation is owned by AstraApp."""
import math
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext

BG, PANEL, FIELD = '#151321', '#201e31', '#191727'
INK, MUTED, LILAC, MINT = '#f5f3ff', '#b8b3ce', '#c3afff', '#8be1d1'
MONO = ('Consolas', 10)


def label(parent, text, size=10, color=INK, bold=False, mono=False, **kw):
    return tk.Label(parent, text=text, bg=parent['bg'], fg=color, anchor='w',
                    font=('Consolas' if mono else 'Segoe UI', size, 'bold' if bold else 'normal'), **kw)


def star(canvas, x, y, radius, color):
    points = []
    for i in range(8):
        r = radius if i % 2 == 0 else radius / 4
        points.extend((x + r*math.cos(i*math.pi/4), y + r*math.sin(i*math.pi/4)))
    canvas.create_polygon(points, fill=color)


def build(app):
    root = app.root
    root.configure(bg=BG)
    if sys.platform == 'win32':
        try:
            root.configure(cursor=('@' + str(Path(__file__).with_name('astra.cur')),))
        except tk.TclError:
            root.configure(cursor='arrow')  # Older Tk builds may not load .cur files.
    style = ttk.Style(root)
    style.theme_use('clam')
    for name, base, fg, hover in [('Launch', LILAC, BG, '#dbceff'), ('Utility', '#353149', INK, '#47415e')]:
        key = name + '.TButton'
        style.configure(key, background=base, foreground=fg, borderwidth=0, padding=(16,9), font=('Segoe UI',10,'bold'))
        style.map(key, background=[('disabled','#393647'),('active',hover)], foreground=[('disabled',MUTED)])
    outer = tk.Frame(root, bg=BG, padx=26, pady=18)
    outer.pack(fill='both', expand=True)
    top = tk.Frame(outer,bg=BG); top.pack(fill='x')
    logo = tk.Canvas(top,width=32,height=32,bg=BG,highlightthickness=0); logo.pack(side='left')
    star(logo,16,16,15,LILAC)
    label(top,'Astra',17,bold=True).pack(side='left',padx=(6,18))
    label(top,'/   COMPUTER WORKSPACE',9,MUTED,mono=True).pack(side='left')
    label(top,'LOCAL DESKTOP',9,MINT,mono=True).pack(side='right')
    hero = tk.Frame(outer,bg=PANEL,padx=18,pady=12); hero.pack(fill='x',pady=(14,12))
    orbit = tk.Canvas(hero,width=152,height=75,bg=PANEL,highlightthickness=0); orbit.pack(side='right')
    for radius in (19,31,43):
        orbit.create_oval(84-radius*1.45,38-radius,84+radius*1.45,38+radius,outline='#48415f')
    star(orbit,84,38,18,LILAC); star(orbit,123,15,5,MINT); star(orbit,35,58,4,'#f2ba8b')
    label(hero,'MISSION CONTROL',9,LILAC,bold=True,mono=True).pack(anchor='w')
    label(hero,'Agent workspace',22,bold=True).pack(anchor='w')
    label(hero,'Give Astra a task and follow each action as it happens.',10,MUTED).pack(anchor='w')
    label(outer,'01   TASK BRIEF',10,LILAC,bold=True,mono=True).pack(anchor='w')
    def editor(lines, font):
        return scrolledtext.ScrolledText(outer,height=lines,wrap='word',font=font,bg=FIELD,fg=INK,
            insertbackground=INK,selectbackground='#5e5385',selectforeground=INK,padx=12,pady=9,
            relief='flat',highlightthickness=1,highlightbackground='#413b55',highlightcolor=LILAC)
    app.task = editor(3,('Segoe UI',11)); app.task.pack(fill='x',pady=(6,8))
    app.task.insert('1.0','Open my browser from the taskbar and search for NVIDIA')
    controls = tk.Frame(outer,bg=BG); controls.pack(fill='x')
    app.approval = tk.BooleanVar(value=True)
    tk.Checkbutton(controls,text='Approve each action',variable=app.approval,bg=BG,fg=INK,
                   selectcolor=FIELD,activebackground=BG,activeforeground=LILAC,font=('Segoe UI',10)).pack(side='left')
    app.run_btn = ttk.Button(controls,text='Run Astra  →',style='Launch.TButton',command=app.start); app.run_btn.pack(side='right')
    ttk.Button(controls,text='Inspect screen',style='Utility.TButton',command=app.inspect_only).pack(side='right',padx=8)
    head = tk.Frame(outer,bg=BG); head.pack(fill='x',pady=(17,6))
    label(head,'02   ACTIVITY LOG',10,LILAC,bold=True,mono=True).pack(side='left')
    app.status = tk.StringVar(value='Ready')
    label(head,'',10,MINT,textvariable=app.status).pack(side='right')
    app.log = editor(5,MONO); app.log.pack(fill='both',expand=True)
    app.log.tag_configure('idle',foreground=MUTED)
    app.log.insert('1.0','Waiting for a task. Execution details will appear here.','idle')
    app.log.configure(state='disabled')
    foot = tk.Frame(outer,bg=BG); foot.pack(fill='x',pady=(8,0))
    label(foot,'FAIL-SAFE  /  Move the pointer to the top-left corner to interrupt input.',9,MUTED).pack(side='left')
    ttk.Button(foot,text='Stop instructions',style='Utility.TButton',command=app.stop_notice).pack(side='right')
