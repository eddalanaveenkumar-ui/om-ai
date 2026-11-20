"""Draw using the actual capture-to-desktop scale, including Retina screenshots."""
from PIL import ImageDraw, ImageFont


def pixels(point, image_size, logical_size):
    return tuple(round(p * n / d) for p, n, d in zip(point, image_size, logical_size))


def annotate(image, elements, logical_size):
    out = image.convert('RGB').copy()
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default(size=15)
    labels = []
    for key, el in elements.items():
        l, t, r, b = el['bbox']
        x, y = pixels((l, t), out.size, logical_size)
        right, bottom = pixels((r, b), out.size, logical_size)
        draw.rectangle((x,y,max(x,right-1),max(y,bottom-1)), outline='#ffda26', width=2)
        labels.append((str(key), x, y, right, bottom))
    occupied = []
    for text, x, y, right, bottom in labels:
        l, t, r, b = draw.textbbox((0,0), text, font=font)
        w, h = r-l+6, b-t+6
        # Prefer top-left. Nested controls can share that corner, so try the
        # other corners before obscuring an earlier mark.
        positions = [(x,y), (right-w,y), (x,bottom-h), (right-w,bottom-h)]
        options = [(max(0,min(a,out.width-w)), max(0,min(b,out.height-h))) for a,b in positions]
        def overlap(pos):
            a,b = pos
            return sum(max(0,min(a+w,r)-max(a,l))*max(0,min(b+h,d)-max(b,t))
                       for l,t,r,d in occupied)
        x,y = min(options, key=overlap)
        occupied.append((x,y,x+w,y+h))
        draw.rectangle((x,y,x+w-1,y+h-1), fill='#15102d', outline='#ffda26')
        draw.text((x+3-l,y+3-t), text, font=font, fill='white')
    return out
