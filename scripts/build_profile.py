"""Generates the profile README and its SVG tiles in the Codematically theme.

Every section of codematically.com is redrawn as SVG with the site's exact tokens
(colors, Inter, radii, spacing x1.3 so text stays legible at README width). Inter
and every image are embedded, because GitHub blocks external resources inside
SVGs served through <img>.

Tiles are inline images with align="top" (vertical-align: top), so they pack edge to
edge with no baseline gap; align="left" would pick up GitHub's 20px padding-right.
Tiles that sit side by side always share the same height.

    python scripts/build_profile.py      # writes assets/*.svg and README.md
"""

import base64
import io
import os
import urllib.request
from html import escape

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
CACHE = os.path.join(ROOT, ".cache")

# ---------------------------------------------------------------- design tokens
BG, SOFT, SURFACE, BORDER = "#05060c", "#0a0d1a", "#101426", "#1e2439"
TEXT, DIM, HEAD = "#c7cede", "#7a8299", "#f4f6fb"
ACCENT, ACCENT2, VIOLET = "#38bdf8", "#6366f1", "#a78bfa"
PROCESS_BG = "#070911"  # bg-soft/40 composited over bg

K = 1.3  # site px -> tile px
W = 1200
PAD = 56
CW = W - 2 * PAD  # content width
GAP = 20 * K

SITE = "https://www.codematically.com"
EMAIL = "umerqureshi40116@gmail.com"
WHATSAPP = "https://wa.me/923455040529"
LINKEDIN = "https://www.linkedin.com/in/muhammad-umer-qureshi-376286199"
GH = "https://github.com/umerqureshi40116"
CLD = "https://res.cloudinary.com/dh2tiiokr/image/upload"
INTER = "https://fonts.gstatic.com/s/inter/v20/UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7.woff2"

# lucide icons (24x24, stroke 2), taken from the site's lucide-react build
ICONS = {
    "code": '<path d="m18 16 4-4-4-4"/><path d="m6 8-4 4 4 4"/><path d="m14.5 4-5 16"/>',
    "workflow": '<rect width="8" height="8" x="3" y="3" rx="2"/><path d="M7 11v4a2 2 0 0 0 2 2h4"/><rect width="8" height="8" x="13" y="13" rx="2"/>',
    "bot": '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>',
    "plug": '<path d="M12 22v-5"/><path d="M15 8V2"/><path d="M17 8a1 1 0 0 1 1 1v4a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1z"/><path d="M9 8V2"/>',
    "rocket": '<path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09"/><path d="M9 12a22 22 0 0 1 2-3.950A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.4 22.4 0 0 1-4 2z"/><path d="M9 12H4s.55-3.030 2-4c1.62-1.08 5 .05 5 .05"/>',
    "chart": '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="m19 9-5 5-4-4-3 3"/>',
    "sparkles": '<path d="M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z"/><path d="M20 2v4"/><path d="M22 4h-4"/><circle cx="4" cy="20" r="2"/>',
    "arrow": '<path d="M7 7h10v10"/><path d="M7 17 17 7"/>',
    "play": '<path d="M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z"/>',
    "award": '<path d="m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526"/><circle cx="12" cy="8" r="6"/>',
    "mail": '<path d="m22 7-8.991 5.727a2 2 0 0 1-2.009 0L2 7"/><rect x="2" y="4" width="20" height="16" rx="2"/>',
    "message": '<path d="M2.992 16.342a2 2 0 0 1 .094 1.167l-1.065 3.29a1 1 0 0 0 1.236 1.168l3.413-.998a2 2 0 0 1 1.099.092 10 10 0 1 0-4.777-4.719"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    "linkedin": '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect width="4" height="12" x="2" y="9"/><circle cx="4" cy="4" r="2"/>',
    "pin": '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
    "briefcase": '<path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/><rect width="20" height="14" x="2" y="6" rx="2"/>',
}


def icon(name, x, y, size, color, fill="none", sw=2, cls=""):
    s = size / 24
    c = f' class="{cls}"' if cls else ""
    return (
        f'<g transform="translate({x:.1f} {y:.1f})"><g{c}><g transform="scale({s:.4f})" fill="{fill}" '
        f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">'
        f"{ICONS[name]}</g></g></g>"
    )


# ---------------------------------------------------------------- data (from the site)
PROJECTS = [
    ("LLM · RAG", "ANF Chatbot", "RAG chatbot using LangGraph + Groq LLaMA 70B. 96% retrieval precision.",
     "1ADYD4-VLENIl5wpVcwQCjj3JnWEkcZ8u", "ANF_HQ_VERSION", "v1781295200/ANF_Chatbot_m6jcno.png"),
    ("Full Stack", "Inventory Management", "FastAPI stack with JWT + RBAC, PDF/CSV reporting, 90% effort reduction.",
     "12ThjJ4lltkZ713NRziuk2WTrP_Vsc0dS", "waze_enterprises_water_project", "v1781281847/IMS_Thumbnail_hywe1g.png"),
    ("Deep Learning", "MRI Brain Tumor Detection", "VGG16 transfer learning achieving 95% accuracy on brain MRI scans.",
     "1UNe8ilI9XRjxcTQmocBqi1wA1jUGTqH_", "Brain_Tumor_Detection_DL",
     "v1781281256/ChatGPT_Image_Jun_12_2026_09_19_39_PM_1_vy6e0b.png"),
    ("ML · Classification", "Heart Disease Prediction", "Ensemble model (Random Forest + XGBoost) with 88% accuracy.",
     "1HyLwy8-XnjR05BhAOPoh0omCDKFYkSyK", "Heart_Disease_Prediction", "v1781295200/HDP_Thumbnail_vwfiwc.png"),
    ("NLP · Compliance", "ComplianceGuard",
     "Call-centre compliance detector: TF-IDF + LinearSVC flags whether agents completed data-capture "
     "verification. 99.97% on 5-fold CV vs 81.3% keyword baseline.",
     "1oil1LGhQBNGLCdxIA9NjxiA-PdM6tLaR", "call_center_supervision",
     "v1788712595/Compliance_Guard_Thumbnail_xawxpu.png"),
    ("ML · Analytics", "Student Class Estimator",
     "Teachers upload a class CSV and get grade-distribution and difficulty-tolerance charts. "
     "Aggregate class predictions land 88-95% accurate.",
     "1YjrUK0bEge-1vks2XXU4U1NcXEu-KhB_", "student_class_estimator",
     "v1788712749/Student_Performance_Project_Thumbnail_zp2qzo.png"),
    ("Computer Vision", "Virtual Try-On System", "Cat-VTON garment segmentation at 95% accuracy, GPU batching.",
     "16GL-KCXMQi7sjEXfRL6LpyvVGHMPqnRY", "CLOTHING_VIRTUAL_TRYON_WEB_APPLICATION",
     "v1781282492/VTON_Thumbnail_levdeb.png"),
    ("Full Stack AI", "AI Assisted Hospital MS", "3-hour rapid prototyping for job application.",
     "17AdWAg5lq-rl8NKwfFUR9UU0q0Y2BSL1", "IMERA_AI_AI_POWERED_FULL_STACK_APPLICATION",
     "v1781295583/Hospital_Thumbnail_lr931h.png"),
    ("Classification", "Diabetes Prediction", "Logistic Regression & ANN with 92% accuracy, PIMA dataset.",
     "1KZJoEwzb5ZG3J2yc3cKlH-Va0H_lggVm", "Diabetes_Risk_Prediction", "v1781295200/DDP_Thumbnail_pj8je8.png"),
    # No public repo for this one, so the code link falls back to the demo.
    ("Unsupervised", "Customer Segmentation", "K-Means clustering & PCA on retail data for targeted marketing.",
     "152FC1E_fZE-vGveqrK__TQ2Q6JxbNQKp", None, "v1781282179/CSP_Thumbnail_caajbp.png"),
]

CERTS = [
    ("v1778962745/IMG_20260517_010828_410_thprwg.jpg", "Anti-Narcotics Force (ANF)", "Junior AI Engineer",
     "Sep 2025 – Apr 2026", True),
    ("v1778971885/Muahammad_Umer_Qureshi_page-0001_ezmhy6.jpg", "Kartoa Technologies (USA)", "AI Intern",
     "Aug 2025 – Nov 2026", True),
    ("v1778962620/IBM_Python_Certificate_ryfoeu.jpg", "IBM", "Python for Data Science, AI and Development",
     "Completed 2025", False),
    ("v1778962621/Cisco_Python_1_Course_tqq5cl.jpg", "CISCO", "Python Essentials 1", "Completed 2025", False),
    ("v1778962770/IMG_20260517_010932_433_n6joud.jpg", "NUTECH", "ASP .NET Core", "Completed 2024", False),
    ("v1778962621/WhatsApp_Image_2025-08-29_at_11.38.01_PM_1_d2rigj.jpg", "CISCO", "Advance Python Essentials",
     "Completed 2025", False),
    ("v1778962621/WhatsApp_Image_2025-08-29_at_11.38.00_PM_curxhh.jpg", "HP Life", "AI for Beginners",
     "Completed 2025", False),
]

SERVICES = [
    ("code", "Web Development",
     "Marketing sites, product dashboards and e-commerce storefronts — built with React and shipped fast, "
     "on a stack that scales.", ["Custom design & build", "Blazing performance", "SEO-ready foundations"]),
    ("workflow", "Business Automations",
     "I connect your tools and remove manual work — from lead intake to invoicing — so your team runs on "
     "autopilot.", ["Zapier / n8n / Make", "CRM & email workflows", "Custom internal tools"]),
    ("bot", "AI & RAG Systems",
     "Retrieval-augmented assistants, agents and vision models that answer from your own data instead of "
     "guessing.", ["LangChain & LangGraph", "Vector search & RAG", "Custom AI agents"]),
    ("plug", "API & Integrations",
     "Stitch your stack together. I build reliable integrations between the tools you already use and love.",
     ["Third-party API integration", "Webhooks & sync jobs", "Payment & billing setup"]),
    ("rocket", "Launch & Hosting",
     "From domain to deploy — shipped on modern infrastructure with CI/CD, so updates go live in minutes, "
     "not weeks.", ["Vercel / cloud deploys", "CI/CD pipelines", "Monitoring & uptime"]),
    ("chart", "Growth & Optimization",
     "Post-launch, I keep tuning — performance, conversion, and analytics — so the site keeps earning its "
     "keep.", ["Core Web Vitals tuning", "Conversion-focused UX", "Analytics & reporting"]),
]

STEPS = [
    ("01", "Discover", "A short call to understand your goals, workflows, and where time or revenue is leaking."),
    ("02", "Design & Plan", "You get a clear scope, timeline, and a design direction before a single line of "
                            "code is written."),
    ("03", "Build", "Built in the open — regular check-ins and a staging link so you can watch it take shape."),
    ("04", "Launch & Automate", "Shipped to production, with the automations wired up that keep things "
                                "running without manual upkeep."),
]

MARQUEE = ["React & Next.js", "FastAPI", "LangChain & LangGraph", "n8n & Zapier", "PostgreSQL", "Docker",
           "PyTorch & TensorFlow", "Custom APIs", "AI Workflows", "Pinecone & ChromaDB"]

STATS = [("", "10", "", "Projects shipped"), ("", "96", "%", "RAG retrieval precision"),
         ("", "95", "%", "MRI detection accuracy"), ("", "7", "", "Certifications & roles")]


# ---------------------------------------------------------------- assets
def fetch(url, name):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r, open(path, "wb") as f:
            f.write(r.read())
    return path


def image_uri(public_id, width):
    """Cloudinary resizes on the fly; the JPEG is inlined so GitHub will render it."""
    url = f"{CLD}/f_jpg,q_72,w_{width},c_limit/{public_id}"
    path = fetch(url, public_id.replace("/", "_").rsplit(".", 1)[0] + f"_{width}.jpg")
    with open(path, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


FONT_PATH = fetch(INTER, "inter.woff2")
_METRICS = {}


def _metrics(weight):
    if weight not in _METRICS:
        inst = instancer.instantiateVariableFont(TTFont(FONT_PATH), {"wght": weight})
        _METRICS[weight] = (inst.getBestCmap(), inst["hmtx"].metrics, inst["head"].unitsPerEm)
    return _METRICS[weight]


def measure(s, size, weight=400, ls=0.0):
    cmap, hmtx, upm = _metrics(weight)
    adv = sum(hmtx[cmap.get(ord(ch), "space")][0] for ch in s)
    return adv * size / upm + ls * len(s)


def wrap(s, size, maxw, weight=400):
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if cur and measure(trial, size, weight) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur] if cur else lines


def font_face(chars):
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga", "calt", "tnum"]
    sub = subset.Subsetter(opts)
    sub.populate(text="".join(sorted(chars | set(" "))))
    font = TTFont(FONT_PATH)
    sub.subset(font)
    buf = io.BytesIO()
    font.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return (f"@font-face{{font-family:'Inter';font-weight:100 900;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")


# ---------------------------------------------------------------- tile builder
class Tile:
    def __init__(self, name, w, h, label, bg=BG):
        self.name, self.w, self.h, self.label, self.bg = name, w, h, label, bg
        self.parts, self.defs, self.css, self.chars = [], [], [], set()

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, size, weight=400, fill=TEXT, anchor="start", ls=0.0, extra=""):
        self.chars |= set(s)
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        l = f' letter-spacing="{ls:.2f}"' if ls else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:.1f}" font-weight="{weight}" '
                 f'fill="{fill}"{a}{l}{extra}>{escape(s)}</text>')

    def raw_text(self, chars):
        self.chars |= set(chars)

    def write(self):
        css = (f"{font_face(self.chars)}"
               "text{font-family:Inter,-apple-system,'Segoe UI',Roboto,sans-serif}" + "".join(self.css) +
               "@media (prefers-reduced-motion:reduce){*{animation:none!important}}")
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h:.0f}" '
               f'width="{self.w}" height="{self.h:.0f}" role="img" aria-label="{escape(self.label)}">'
               f"<defs>{''.join(self.defs)}</defs><style>{css}</style>"
               f'<rect width="{self.w}" height="{self.h:.0f}" fill="{self.bg}"/>{"".join(self.parts)}</svg>')
        with open(os.path.join(ASSETS, self.name + ".svg"), "w", encoding="utf-8") as f:
            f.write(svg)


def hline(t, y, x1=0, x2=None):
    t.add(f'<rect x="{x1}" y="{y}" width="{(x2 or t.w) - x1}" height="1" fill="{BORDER}"/>')


def pill_button(t, x, y, label, primary, icon_name=None, size=18.2, h=None, w=None, anchor="start"):
    """rounded-full CTA: primary is bg-text-h/text-bg, secondary is outlined."""
    px = 20.8 if h is None or h < 50 else 31.2
    h = h or 46.8
    iw = size * 1.07 if icon_name else 0
    tw = measure(label, size, 500)
    w = w or px * 2 + tw + (iw + 6.5 if icon_name else 0)
    if anchor == "middle":
        x -= w / 2
    fill, fg, stroke = (HEAD, BG, "none") if primary else ("none", TEXT, BORDER)
    t.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{h / 2:.1f}" '
          f'fill="{fill}" stroke="{stroke}"/>')
    cx = x + w / 2 - (iw + 6.5) / 2 if icon_name else x + w / 2
    t.text(cx, y + h / 2 + size * 0.36, label, size, 500, fg, "middle")
    if icon_name:
        t.add(icon(icon_name, cx + tw / 2 + 6.5, y + (h - iw) / 2, iw, fg))
    return w


def logo_mark(t, x, y, size):
    t.defs.append('<linearGradient id="cm" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#38bdf8"/>'
                  '<stop offset=".5" stop-color="#6366f1"/><stop offset="1" stop-color="#a78bfa"/></linearGradient>')
    s = size / 64
    t.add(f'<g transform="translate({x} {y}) scale({s:.4f})"><rect width="64" height="64" rx="16" fill="{SOFT}" '
          f'stroke="{BORDER}" stroke-width="1.5"/><path d="M36 20L22 32L36 44" stroke="url(#cm)" stroke-width="5.5" '
          f'stroke-linecap="round" stroke-linejoin="round" fill="none"/><circle cx="45" cy="32" r="4" '
          f'fill="url(#cm)"/></g>')


def section_head(t, y, label, title, body=None, body_w=None):
    """The site's section header: accent eyebrow, h2, dim lede."""
    t.text(PAD, y + 12, label.upper(), 15.6, 500, ACCENT, ls=0.78)
    y += 20.8 + 15.6
    t.text(PAD, y + 41.6, title, 46.8, 600, HEAD, ls=-1.17)
    y += 52
    if body:
        y += 20.8
        for line in wrap(body, 20.8, body_w or 874):
            t.text(PAD, y + 22, line, 20.8, 400, DIM)
            y += 31.2
    return y


def glow(t, gid, cx, cy, rx, ry, opacity=0.2):
    t.defs.append(f'<radialGradient id="{gid}"><stop offset="0" stop-color="{ACCENT}" stop-opacity="{opacity}"/>'
                  f'<stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></radialGradient>')
    t.add(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#{gid})"/>')


def grid_fade(t, h, cy=0, rx=0.7, ry=0.6):
    """.grid-fade: 56px indigo grid under a radial mask anchored at the top centre."""
    t.defs.append(
        f'<pattern id="grid" width="72.8" height="72.8" patternUnits="userSpaceOnUse" x="{(t.w / 2) % 72.8:.1f}">'
        f'<path d="M72.8 0H0v72.8" fill="none" stroke="{ACCENT2}" stroke-opacity=".09" stroke-width="1.3"/></pattern>'
        f'<radialGradient id="gm" cx=".5" cy="{cy}" r="1" gradientTransform="translate(.5 {cy}) scale({rx} {ry}) '
        f'translate(-.5 {-cy})"><stop offset=".4" stop-color="#fff"/><stop offset="1" stop-color="#000"/>'
        f'</radialGradient><mask id="gmask"><rect width="{t.w}" height="{h}" fill="url(#gm)"/></mask>')
    t.add(f'<rect width="{t.w}" height="{h}" fill="url(#grid)" mask="url(#gmask)"/>')


# ---------------------------------------------------------------- sections
def hero():
    H = 900
    t = Tile("hero", W, H, "Umer Qureshi — I build fast websites that run themselves. AI engineer and founder of "
                           "Codematically: web, AI and automation.")
    grid_fade(t, H)
    glow(t, "hglow", 600, 42, 416, 250)
    t.defs.append('<filter id="blur" x="-100%" y="-100%" width="300%" height="300%">'
                  '<feGaussianBlur stdDeviation="62"/></filter>')
    t.css.append(
        "@keyframes dA{0%,100%{transform:translate(0,0) scale(1)}33%{transform:translate(52px,-39px) scale(1.12)}"
        "66%{transform:translate(-26px,26px) scale(.95)}}"
        "@keyframes dB{0%,100%{transform:translate(0,0) scale(1)}33%{transform:translate(-65px,32px) scale(.92)}"
        "66%{transform:translate(32px,-26px) scale(1.1)}}"
        ".dA{animation:dA 18s ease-in-out infinite;transform-box:fill-box;transform-origin:center}"
        ".dB{animation:dB 22s ease-in-out infinite;transform-box:fill-box;transform-origin:center}"
        "@keyframes wig{0%,100%{transform:rotate(0)}25%{transform:rotate(15deg)}75%{transform:rotate(-15deg)}}"
        ".wig{animation:wig 4s ease-in-out infinite;transform-box:fill-box;transform-origin:center}"
        "@keyframes up{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:none}}"
        ".up{animation:up .6s cubic-bezier(.22,1,.36,1) both}"
        "@keyframes nav{from{transform:translateY(-84px)}to{transform:none}}"
        ".nav{animation:nav .6s cubic-bezier(.22,1,.36,1) both}")
    t.add(f'<circle class="dA" cx="67" cy="237" r="187" fill="{ACCENT2}" fill-opacity=".10" filter="url(#blur)"/>')
    t.add(f'<circle class="dB" cx="1150" cy="365" r="208" fill="{VIOLET}" fill-opacity=".10" filter="url(#blur)"/>')

    # navbar
    t.add('<g class="nav">')
    logo_mark(t, PAD, 24, 36.4)
    t.text(PAD + 36.4 + 13, 49, "Umer Qureshi", 20.8, 600, HEAD, ls=-0.52)
    links = ["Portfolio", "Services", "Process", "Contact"]
    widths = [measure(l, 18.2) for l in links]
    x = W / 2 - (sum(widths) + 41.6 * (len(links) - 1)) / 2 + 60
    for l, lw in zip(links, widths):
        t.text(x, 48.5, l, 18.2, 400, DIM)
        x += lw + 41.6
    bw = 20.8 * 2 + measure("Start a project", 18.2, 500) + 19.5 + 6.5
    pill_button(t, W - PAD - bw, 18.6, "Start a project", True, "arrow")
    t.add("</g>")

    y = 176
    # eyebrow pill
    label = "AI engineer · Websites, AI & automations"
    tw = measure(label, 15.6)
    pw = 20.8 * 2 + 17 + 10.4 + tw
    px = W / 2 - pw / 2
    t.add(f'<g class="up" style="animation-delay:0s"><rect x="{px:.1f}" y="{y}" width="{pw:.1f}" height="38" '
          f'rx="19" fill="{SURFACE}" stroke="{BORDER}"/>')
    t.add(icon("sparkles", px + 20.8, y + 10.5, 17, ACCENT, cls="wig"))
    t.text(px + 20.8 + 17 + 10.4, y + 24.5, label, 15.6, 400, DIM)
    t.add("</g>")
    y += 38 + 41.6

    # headline — "I build fast websites / that run themselves."
    fs = 90
    words = ["I", "build", "fast", "websites"]
    b1 = y + 0.889 * fs
    ls = -0.025 * fs
    total = measure(" ".join(words), fs, 600, ls)
    x = W / 2 - total / 2
    for i, wd in enumerate(words):
        t.add(f'<g class="up" style="animation-delay:{0.08 + i * 0.08:.2f}s">')
        t.text(x, b1, wd, fs, 600, HEAD, ls=ls)
        t.add("</g>")
        x += measure(wd + " ", fs, 600, ls)
    b2 = b1 + 1.05 * fs
    w_that = measure("that ", fs, 600, ls)
    w_run = measure("run themselves.", fs, 600, ls)
    x0 = W / 2 - (w_that + w_run) / 2
    gx = x0 + w_that
    # .animate-gradient: 220% wide gradient panned back and forth over 8s
    span = w_run * 2.2
    t.defs.append(
        f'<linearGradient id="hl" gradientUnits="userSpaceOnUse" x1="{gx:.1f}" y1="0" x2="{gx + span:.1f}" y2="0" '
        f'spreadMethod="reflect"><stop offset="0" stop-color="{ACCENT}"/><stop offset=".25" stop-color="{ACCENT2}"/>'
        f'<stop offset=".5" stop-color="{VIOLET}"/><stop offset=".75" stop-color="{ACCENT2}"/>'
        f'<stop offset="1" stop-color="{ACCENT}"/>'
        f'<animateTransform attributeName="gradientTransform" type="translate" values="0 0;{-(span - w_run):.1f} 0;0 0" '
        f'dur="8s" calcMode="spline" keySplines=".42 0 .58 1;.42 0 .58 1" repeatCount="indefinite"/>'
        f'</linearGradient>')
    t.add('<g class="up" style="animation-delay:.44s">')
    t.text(x0, b2, "that", fs, 600, HEAD, ls=ls)
    t.text(gx, b2, "run themselves.", fs, 600, "url(#hl)", ls=ls)
    t.add("</g>")
    y = b2 + (1.05 - 0.889) * fs + 31.2

    lede = ("I'm Umer — an AI engineer and founder of Codematically, a small studio building high-performance "
            "web experiences, AI systems and business automations, so you spend less time on busywork and more "
            "time growing.")
    t.add('<g class="up" style="animation-delay:.55s">')
    for line in wrap(lede, 23.4, 874):
        t.text(W / 2, y + 25, line, 23.4, 400, DIM, "middle")
        y += 36.4
    t.add("</g>")
    y += 52

    t.add('<g class="up" style="animation-delay:.65s">')
    w1 = 31.2 * 2 + measure("Start a project", 18.2, 500) + 26
    w2 = 31.2 * 2 + measure("See my work", 18.2, 500)
    bx = W / 2 - (w1 + w2 + 20.8) / 2
    pill_button(t, bx, y, "Start a project", True, "arrow", h=57.2, w=w1)
    pill_button(t, bx + w1 + 20.8, y, "See my work", False, h=57.2, w=w2)
    t.add("</g>")
    y += 57.2 + 83

    # marquee, doubled and panned by exactly one copy for a seamless loop
    items = [m.upper() for m in MARQUEE]
    fsm, lsm, gap = 15.6, 0.78, 52
    seq, x = [], 0.0
    for it in items:
        # item, gap-10, dot, gap-10 — the site's span-with-trailing-dot inside a gap-10 flex row
        seq.append((x, it))
        x += measure(it, fsm, 400, lsm) + gap
        seq.append((x + 2.6, None))
        x += 5.2 + gap
    loop = x
    t.css.append(f"@keyframes mq{{to{{transform:translateX(-{loop:.1f}px)}}}}"
                 ".mq{animation:mq 28s linear infinite}")
    t.defs.append('<linearGradient id="fxg"><stop offset="0" stop-color="#000"/><stop offset=".12" stop-color="#fff"/>'
                  '<stop offset=".88" stop-color="#fff"/><stop offset="1" stop-color="#000"/></linearGradient>'
                  f'<mask id="fx"><rect y="{y - 30}" width="{W}" height="60" fill="url(#fxg)"/></mask>')
    t.add(f'<g mask="url(#fx)"><g class="mq">')
    for copy in (0, loop, 2 * loop):
        for sx, it in seq:
            if it is None:
                t.add(f'<circle cx="{copy + sx:.1f}" cy="{y - 5.5:.1f}" r="2.6" fill="{ACCENT}" fill-opacity=".5"/>')
            else:
                t.text(copy + sx, y, it, fsm, 400, DIM, ls=lsm)
    t.add("</g></g>")
    t.h = y + 104
    t.write()


def stats():
    t = Tile("stats", W, 0, "10 projects shipped. 96% RAG retrieval precision. 95% MRI detection accuracy. "
                            "7 certifications and roles.")
    hline(t, 0)
    colw = (CW - 3 * 41.6) / 4
    for i, (pre, val, suf, label) in enumerate(STATS):
        x = PAD + i * (colw + 41.6)
        t.text(x, 83 + 44, pre + val + suf, 46.8, 600, HEAD, ls=-1.17)
        t.text(x, 83 + 52 + 5 + 20, label, 18.2, 400, DIM)
    t.h = 83 + 52 + 5 + 26 + 83
    t.write()


def portfolio_head():
    t = Tile("portfolio", W, 0, "Portfolio — projects and certifications.")
    hline(t, 0)
    y = section_head(t, 146, "Portfolio", "Projects & certifications")
    body = "Shipped work with recorded walkthroughs and source code, alongside the certifications behind it."
    lines = wrap(body, 18.2, 499)
    for i, line in enumerate(reversed(lines)):
        t.text(W - PAD, y - 12 - i * 28, line, 18.2, 400, DIM, "end")
    t.h = y + 62.4
    t.write()


CARD_W = (CW - GAP) / 2
THUMB_H = round(CARD_W * 9 / 16)
R = 20.8  # rounded-2xl


def card_x(col):
    """Left edge of a two-column card inside its own 600px tile."""
    return PAD if col == 0 else PAD + CARD_W + GAP - W / 2


def project_thumb(i, p):
    tag, title, _, demo, _, img = p
    col = i % 2
    t = Tile(f"p{i + 1:02d}a", W // 2, THUMB_H + 1, f"{title} — watch the demo video.")
    x = card_x(col)
    cid = "c"
    t.defs.append(f'<clipPath id="{cid}"><rect x="{x + 1:.1f}" y="1" width="{CARD_W - 2:.1f}" '
                  f'height="{THUMB_H + 40}" rx="{R - 1}"/></clipPath>')
    t.add(f'<rect x="{x + .5:.1f}" y=".5" width="{CARD_W - 1:.1f}" height="{THUMB_H + 60}" rx="{R}" '
          f'fill="{SURFACE}" stroke="{BORDER}"/>')
    t.add(f'<g clip-path="url(#{cid})"><rect x="{x}" y="0" width="{CARD_W}" height="{THUMB_H + 2}" fill="{SOFT}"/>'
          f'<image href="{image_uri(img, 640)}" x="{x + 1:.1f}" y="1" width="{CARD_W - 2:.1f}" height="{THUMB_H}" '
          f'preserveAspectRatio="xMidYMid slice"/></g>')
    # the site's hover play button, parked in the corner with a soft pulse so the demo is discoverable
    cx, cy, r = x + CARD_W - 50, THUMB_H - 44, 27
    t.css.append("@keyframes pulse{0%{transform:scale(1);opacity:.55}100%{transform:scale(1.7);opacity:0}}"
                 ".pulse{animation:pulse 2.2s cubic-bezier(.22,1,.36,1) infinite;transform-box:fill-box;"
                 f"transform-origin:center;animation-delay:{(i % 4) * .35:.2f}s}}")
    t.add(f'<circle class="pulse" cx="{cx:.1f}" cy="{cy}" r="{r}" fill="{ACCENT}"/>'
          f'<circle cx="{cx:.1f}" cy="{cy}" r="{r}" fill="{ACCENT}"/>')
    t.add(icon("play", cx - 10.5, cy - 11.5, 23, BG, fill=BG))
    t.write()


def project_body(i, p, lines_max):
    tag, title, desc, _, repo, _ = p
    col = i % 2
    body_h = 26 + 32 + 15.6 + 31.2 + 10.4 + lines_max * 29.6 + 20.8 + 43.6 + 26
    t = Tile(f"p{i + 1:02d}b", W // 2, body_h + GAP, f"{tag}. {title}: {desc}")
    x = card_x(col)
    t.add(f'<rect x="{x + .5:.1f}" y="-60" width="{CARD_W - 1:.1f}" height="{body_h + 59.5:.1f}" rx="{R}" '
          f'fill="{SURFACE}" stroke="{BORDER}"/>')
    ix, y = x + 26, 26
    tw = measure(tag, 14.3, 500)
    t.add(f'<rect x="{ix}" y="{y}" width="{tw + 26:.1f}" height="30" rx="15" fill="{ACCENT}" fill-opacity=".1" '
          f'stroke="{ACCENT}" stroke-opacity=".25"/>')
    t.text(ix + 13, y + 20, tag, 14.3, 500, ACCENT)
    y += 32 + 15.6
    t.text(ix, y + 22, title, 20.8, 500, HEAD)
    y += 31.2 + 10.4
    for line in wrap(desc, 18.2, CARD_W - 52):
        t.text(ix, y + 20, line, 18.2, 400, DIM)
        y += 29.6
    by = body_h - 26 - 43.6
    label = "View code" if repo else "Watch demo"
    t.add(f'<rect x="{ix}" y="{by:.1f}" width="{CARD_W - 52:.1f}" height="43.6" rx="10.4" fill="{SOFT}" '
          f'stroke="{BORDER}"/>')
    lw = measure(label, 15.6, 500)
    cx = ix + (CARD_W - 52) / 2
    t.add(icon("code" if repo else "play", cx - (lw + 23) / 2, by + 13.3, 17, TEXT))
    t.text(cx - (lw + 23) / 2 + 23, by + 27.5, label, 15.6, 500, TEXT)
    t.write()


def certs_head():
    t = Tile("certificates", W, 0, "Certificates and achievements.")
    y = 104 - GAP
    t.text(PAD, y + 26, "Certificates & achievements", 31.2, 600, HEAD, ls=-0.78)
    lx = PAD + measure("Certificates & achievements", 31.2, 600, -0.78) + 20.8
    t.defs.append(f'<linearGradient id="ln"><stop offset="0" stop-color="{ACCENT}" stop-opacity=".4"/>'
                  f'<stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></linearGradient>')
    t.add(f'<rect x="{lx:.1f}" y="{y + 16}" width="{W - PAD - lx:.1f}" height="1.3" fill="url(#ln)"/>')
    t.h = y + 36 + 41.6
    t.write()


C3_W = (CW - 2 * GAP) / 3
CERT_IMG_H = 250
CERT_BODY_H = 26 + 20 + 10.4 + 2 * 31.2 + 5.2 + 21 + 26


def cert_x(col):
    return PAD + col * (C3_W + GAP) - col * (W / 3)


def cert(i, c):
    img, issuer, title, date, featured = c
    col = i % 3
    t = Tile(f"cert{i + 1}", 400, CERT_IMG_H + CERT_BODY_H + GAP, f"{issuer} — {title}, {date}.")
    x = cert_x(col)
    h = CERT_IMG_H + CERT_BODY_H
    t.defs.append(f'<clipPath id="c"><rect x="{x + 1:.1f}" y="1" width="{C3_W - 2:.1f}" height="{h}" '
                  f'rx="{R - 1}"/></clipPath>')
    t.add(f'<rect x="{x + .5:.1f}" y=".5" width="{C3_W - 1:.1f}" height="{h - 1}" rx="{R}" fill="{SURFACE}" '
          f'stroke="{BORDER}"/>')
    t.add(f'<g clip-path="url(#c)"><rect x="{x}" width="{C3_W}" height="{CERT_IMG_H}" fill="{SOFT}"/>'
          f'<image href="{image_uri(img, 520)}" x="{x + 1:.1f}" y="1" width="{C3_W - 2:.1f}" '
          f'height="{CERT_IMG_H - 1}" preserveAspectRatio="xMidYMin slice"/></g>')
    if featured:
        fw = measure("Featured", 14.3, 600) + 26
        fx = x + C3_W - 15.6 - fw
        t.add(f'<rect x="{fx:.1f}" y="15.6" width="{fw:.1f}" height="30" rx="15" fill="{ACCENT}"/>')
        t.text(fx + fw / 2, 35.6, "Featured", 14.3, 600, BG, "middle")
    ix, y = x + 26, CERT_IMG_H + 26
    t.add(icon("award", ix, y + 1.5, 17, ACCENT))
    t.text(ix + 23.4, y + 15, issuer.upper(), 14.3, 600, ACCENT, ls=0.36)
    y += 20 + 10.4
    for line in wrap(title, 20.8, C3_W - 52, 500)[:2]:
        t.text(ix, y + 22, line, 20.8, 500, HEAD)
        y += 31.2
    t.text(ix, y + 5.2 + 16, date, 15.6, 400, DIM)
    t.write()


def cert_cta(col):
    """Fills the last row of the certificate grid with a card pointing at the full site."""
    w = 800
    t = Tile("cert-more", w, CERT_IMG_H + CERT_BODY_H + GAP,
             "Watch every demo on codematically.com — walkthrough videos, services and how to start a project.")
    x = cert_x(col)
    cw = 2 * C3_W + GAP
    h = CERT_IMG_H + CERT_BODY_H
    t.defs.append(f'<clipPath id="c"><rect x="{x + 1:.1f}" y="1" width="{cw - 2:.1f}" height="{h - 2}" '
                  f'rx="{R - 1}"/></clipPath>'
                  f'<pattern id="grid" width="72.8" height="72.8" patternUnits="userSpaceOnUse">'
                  f'<path d="M72.8 0H0v72.8" fill="none" stroke="{ACCENT2}" stroke-opacity=".09" stroke-width="1.3"/>'
                  f'</pattern><radialGradient id="gm" cx=".5" cy="0" r="1" gradientTransform="translate(.5 0) '
                  f'scale(.7 .9) translate(-.5 0)"><stop offset=".3" stop-color="#fff"/><stop offset="1" '
                  f'stop-color="#000"/></radialGradient><mask id="gmask"><rect x="{x}" width="{cw}" height="{h}" '
                  f'fill="url(#gm)"/></mask>')
    t.add(f'<rect x="{x + .5:.1f}" y=".5" width="{cw - 1:.1f}" height="{h - 1}" rx="{R}" fill="{SURFACE}" '
          f'stroke="{BORDER}"/>')
    t.add(f'<g clip-path="url(#c)"><rect x="{x}" width="{cw}" height="{h}" fill="url(#grid)" mask="url(#gmask)"/>')
    glow(t, "g2", x + cw / 2, 0, 300, 180, 0.22)
    t.add("</g>")
    cx = x + cw / 2
    logo_mark(t, cx - 36.4, 70, 72.8)
    t.text(cx, 206, "Watch every demo on the studio site", 31.2, 600, HEAD, "middle", ls=-0.78)
    lines = wrap("Recorded walkthroughs for each project, the full services list and a quick way to start a "
                 "project — all on codematically.com.", 18.2, 620)
    for k, line in enumerate(lines):
        t.text(cx, 246 + k * 29.6, line, 18.2, 400, DIM, "middle")
    pill_button(t, cx, 246 + len(lines) * 29.6 + 10, "Visit codematically.com", True, "arrow", anchor="middle")
    t.write()


def services():
    t = Tile("services", W, 0, "Services — web development, business automations, AI and RAG systems, API and "
                               "integrations, launch and hosting, growth and optimization.")
    hline(t, 0)
    y = section_head(t, 146, "Services", "Everything you need to launch and scale online",
                     "Three disciplines, working together: sharp web development, applied AI, and smart automation "
                     "— so your site looks great and your operations run without you.", 874)
    y += 72.8
    cw = C3_W
    rows = []
    for icon_name, title, desc, points in SERVICES:
        rows.append(wrap(desc, 18.2, cw - 62.4))
    max_lines = max(len(r) for r in rows)
    ch = 31.2 + 52 + 26 + 29 + 10.4 + max_lines * 29.6 + 20.8 + 3 * 27 + 31.2
    t.css.append("@keyframes lit{0%,100%{stroke:#1e2439}8%,22%{stroke:rgba(56,189,248,.45)}30%{stroke:#1e2439}}"
                 ".lit{animation:lit 12s ease-in-out infinite}")
    for i, (icon_name, title, desc, points) in enumerate(SERVICES):
        x = PAD + (i % 3) * (cw + GAP)
        cy = y + (i // 3) * (ch + GAP)
        t.add(f'<rect class="lit" style="animation-delay:{i * 2}s" x="{x + .5:.1f}" y="{cy + .5:.1f}" '
              f'width="{cw - 1:.1f}" height="{ch - 1:.1f}" rx="{R}" fill="{SURFACE}" stroke="{BORDER}"/>')
        ix, iy = x + 31.2, cy + 31.2
        t.add(f'<rect x="{ix + .5}" y="{iy + .5:.1f}" width="51" height="51" rx="10.4" fill="{SOFT}" '
              f'stroke="{BORDER}"/>')
        t.add(icon(icon_name, ix + 14.3, iy + 14.3, 23.4, ACCENT))
        ty = iy + 52 + 26
        t.text(ix, ty + 20, title, 23.4, 500, HEAD)
        ty += 29 + 10.4
        for line in rows[i]:
            t.text(ix, ty + 20, line, 18.2, 400, DIM)
            ty += 29.6
        ty = cy + ch - 31.2 - 3 * 27
        for p in points:
            t.add(f'<circle cx="{ix + 2.6}" cy="{ty + 13:.1f}" r="2.6" fill="{ACCENT}"/>')
            t.text(ix + 15.6, ty + 18.5, p, 15.6, 400, DIM)
            ty += 27
    t.h = y + 2 * ch + GAP + 146
    t.write()


def process():
    t = Tile("process", W, 0, "Process — discover, design and plan, build, launch and automate.", bg=PROCESS_BG)
    hline(t, 0)
    y = section_head(t, 146, "Process", "A simple, transparent way of working",
                     "No black boxes. You know what's happening at every stage, from first call to launch day.", 980)
    y += 72.8
    colw = (CW - 3 * 41.6) / 4
    t.defs.append(f'<linearGradient id="cn"><stop offset="0" stop-color="{ACCENT}" stop-opacity=".5"/>'
                  f'<stop offset="1" stop-color="{BORDER}"/></linearGradient>')
    t.css.append("@keyframes step{0%,100%{fill:rgba(122,130,153,.4)}6%,22%{fill:#38bdf8}28%{fill:rgba(122,130,153,.4)}}"
                 ".step{animation:step 10s ease-in-out infinite;fill:rgba(122,130,153,.4)}")
    bottom = y
    for i, (num, title, desc) in enumerate(STEPS):
        x = PAD + i * (colw + 41.6)
        t.chars |= set(num)
        t.add(f'<text class="step" style="animation-delay:{i * 2.5}s" x="{x:.1f}" y="{y + 30:.1f}" '
              f'font-size="31.2" font-weight="600">{num}</text>')
        if i < len(STEPS) - 1:
            nx = x + measure(num, 31.2, 600) + 15.6
            t.add(f'<rect x="{nx:.1f}" y="{y + 19:.1f}" width="{x + colw + 41.6 - 15.6 - nx:.1f}" height="1.3" '
                  f'fill="url(#cn)"/>')
        ty = y + 41.6 + 20.8
        t.text(x, ty + 20, title, 23.4, 500, HEAD)
        ty += 29 + 10.4
        for line in wrap(desc, 18.2, colw):
            t.text(x, ty + 20, line, 18.2, 400, DIM)
            ty += 29.6
        bottom = max(bottom, ty)
    t.h = bottom + 146
    t.write()


CARD_L, CARD_R = PAD, W - PAD
CR = 31.2  # rounded-3xl


def card_sides(t, top=None, bottom=None):
    """Draws the contact card's frame for one horizontal slice of it."""
    y0 = top if top is not None else -60
    y1 = bottom if bottom is not None else t.h + 60
    t.add(f'<rect x="{CARD_L + .5}" y="{y0 + .5}" width="{CARD_R - CARD_L - 1}" height="{y1 - y0 - 1}" rx="{CR}" '
          f'fill="{SURFACE}" stroke="{BORDER}"/>')


def contact():
    top = Tile("contact", W, 0, "Get in touch. Let's build something that works while you sleep.")
    hline(top, 0)
    ctop = 110
    x, y = CARD_L + 62.4, ctop + 62.4
    top.text(x, y + 12, "GET IN TOUCH", 15.6, 500, ACCENT, ls=0.78)
    y += 36.4
    for line in ["Let's build something that", "works while you sleep."]:
        top.text(x, y + 41.6, line, 46.8, 600, HEAD, ls=-1.17)
        y += 52
    y += 20.8
    for line in wrap("Tell me about your project or the manual work you're ready to automate away. I reply within "
                     "one business day.", 20.8, 874):
        top.text(x, y + 22, line, 20.8, 400, DIM)
        y += 31.2
    y += 20.8
    fx = x
    for ic, s in [("pin", "Islamabad, Pakistan"), ("briefcase", "Open to freelance work & full-time roles")]:
        top.add(icon(ic, fx, y + 3, 20.8, ACCENT))
        top.text(fx + 31.2, y + 19, s, 18.2, 400, DIM)
        fx += 31.2 + measure(s, 18.2) + 41.6
    top.h = y + 36.4 + 36.4
    # the card frame goes under the copy that was laid out before its height was known
    top.parts.insert(0, f'<rect x="{CARD_L + .5}" y="{ctop + .5}" width="{CARD_R - CARD_L - 1}" '
                        f'height="{top.h + 60}" rx="{CR}" fill="{SURFACE}" stroke="{BORDER}"/>')
    top.write()

    rows = [("mail", "Email", EMAIL, "c-email"),
            ("message", "WhatsApp", "+92 345 5040529", "c-whatsapp"),
            ("linkedin", "LinkedIn", "muhammad-umer-qureshi", "c-linkedin"),
            ("globe", "Studio", "codematically.com", "c-site")]
    rh = 72.8
    for ic, label, value, name in rows:
        t = Tile(name, W, rh + 15.6, f"{label}: {value}")
        card_sides(t)
        bx, bw = CARD_L + 62.4, CARD_R - CARD_L - 124.8
        t.add(f'<rect x="{bx + .5}" y=".5" width="{bw - 1}" height="{rh - 1}" rx="10.4" fill="{SOFT}" '
              f'stroke="{BORDER}"/>')
        t.add(icon(ic, bx + 26, rh / 2 - 11.7, 23.4, ACCENT))
        t.text(bx + 70, rh / 2 + 6.5, label, 15.6, 400, DIM)
        t.text(bx + 190, rh / 2 + 7.5, value, 20.8, 500, HEAD)
        t.add(icon("arrow", bx + bw - 26 - 20.8, rh / 2 - 10.4, 20.8, DIM))
        t.write()

    t = Tile("c-start", W, 0, "Send a message on WhatsApp to start a project.")
    bh = 62.4
    y = 15.6
    t.h = y + bh + 20.8 + 20 + 62.4 + 146
    glow(t, "bg2", W / 2, t.h + 60, 520, 250, 0.2)
    card_sides(t, bottom=t.h - 146)
    bx, bw = CARD_L + 62.4, CARD_R - CARD_L - 124.8
    t.add(f'<rect x="{bx}" y="{y}" width="{bw}" height="{bh}" rx="10.4" fill="{HEAD}"/>')
    lw = measure("Start a project on WhatsApp", 18.2, 500)
    cx = W / 2 - (lw + 29) / 2
    t.add(icon("message", cx, y + bh / 2 - 10.4, 20.8, BG))
    t.text(cx + 29, y + bh / 2 + 6.5, "Start a project on WhatsApp", 18.2, 500, BG)
    t.text(W / 2, y + bh + 20.8 + 15, "Opens WhatsApp with a new chat — or email me any time.", 15.6, 400, DIM,
           "middle")
    t.write()


def footer():
    t = Tile("footer", W, 0, "Umer Qureshi — Codematically. Web development, applied AI and automation.")
    hline(t, 0)
    y = 72.8
    logo_mark(t, PAD, y, 36.4)
    t.text(PAD + 49.4, y + 25, "Umer Qureshi", 20.8, 600, HEAD, ls=-0.52)
    for k, line in enumerate(wrap("Web development, applied AI and automation for businesses that want to move "
                                  "faster online.", 18.2, 400)):
        t.text(PAD, y + 36.4 + 20.8 + 20 + k * 28, line, 18.2, 400, DIM)
    cols = [("Studio", ["Portfolio", "Services", "Process", "codematically.com"]),
            ("Contact", [EMAIL, "+92 345 5040529", "Start a project"])]
    for c, (title, items) in enumerate(cols):
        x = PAD + (540, 800)[c]
        t.text(x, y + 20, title, 18.2, 500, HEAD)
        for k, it in enumerate(items):
            t.text(x, y + 20 + 52 + k * 39, it, 18.2, 400, DIM)
    y += 20 + 52 + 3 * 39 + 20 + 72.8
    hline(t, y)
    t.text(PAD, y + 50, "© 2026 Umer Qureshi · Codematically. All rights reserved.", 15.6, 400, DIM)
    t.text(W - PAD, y + 50, "Designed in the Codematically theme.", 15.6, 400, DIM, "end")
    t.h = y + 80
    t.write()


# ---------------------------------------------------------------- README
def img(name, width, alt, href=None):
    tag = f'<img align="top" width="{width}" src="./assets/{name}.svg" alt="{escape(alt)}"/>'
    return f'<a href="{href}">{tag}</a>' if href else tag


def readme():
    drive = "https://drive.google.com/file/d/{}/view"
    out = ["<!-- Generated by scripts/build_profile.py in the Codematically theme. Edit the script, not this file. -->", ""]
    out.append(img("hero", "100%", "Umer Qureshi — I build fast websites that run themselves.", SITE))
    out.append(img("portfolio", "100%", "Portfolio — projects and certifications."))
    for r in range(0, len(PROJECTS), 2):
        pair = PROJECTS[r:r + 2]
        for k, p in enumerate(pair):
            out.append(img(f"p{r + k + 1:02d}a", "50%", f"{p[1]} — demo video", drive.format(p[3])))
        for k, p in enumerate(pair):
            code = f"{GH}/{p[4]}" if p[4] else drive.format(p[3])
            out.append(img(f"p{r + k + 1:02d}b", "50%", f"{p[0]} · {p[1]}: {p[2]}", code))
    out.append(img("certificates", "100%", "Certificates and achievements."))
    for i, c in enumerate(CERTS):
        out.append(img(f"cert{i + 1}", "33.33%", f"{c[1]} — {c[2]}, {c[3]}", f"{CLD}/{c[0]}"))
    out.append(img("cert-more", "66.66%", "Watch every demo on codematically.com", SITE))
    out.append(img("stats", "100%", "10 projects shipped · 96% RAG retrieval precision · 95% MRI detection accuracy "
                                    "· 7 certifications and roles"))
    out.append(img("services", "100%", "Services: web development, business automations, AI and RAG systems, API "
                                       "and integrations, launch and hosting, growth and optimization."))
    out.append(img("process", "100%", "Process: discover, design and plan, build, launch and automate."))
    out.append(img("contact", "100%", "Get in touch — let's build something that works while you sleep."))
    out.append(img("c-email", "100%", f"Email — {EMAIL}", f"mailto:{EMAIL}"))
    out.append(img("c-whatsapp", "100%", "WhatsApp — +92 345 5040529", WHATSAPP))
    out.append(img("c-linkedin", "100%", "LinkedIn — muhammad-umer-qureshi", LINKEDIN))
    out.append(img("c-site", "100%", "Studio — codematically.com", SITE))
    out.append(img("c-start", "100%", "Start a project on WhatsApp", WHATSAPP))
    out.append(img("footer", "100%", "Umer Qureshi · Codematically", SITE))
    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8") as f:
        # All tiles share one paragraph with no whitespace between them: a newline would render as
        # <br> and a space would push the second half-width tile onto its own line.
        f.write(out[0] + "\n\n" + "".join(out[2:]) + "\n")


def main():
    os.makedirs(ASSETS, exist_ok=True)
    for f in os.listdir(ASSETS):
        if f.endswith(".svg"):
            os.remove(os.path.join(ASSETS, f))
    hero()
    portfolio_head()
    for i, p in enumerate(PROJECTS):
        # the two cards in a row share a height; rows size to their own longest description
        pair = PROJECTS[i - i % 2:i - i % 2 + 2]
        project_thumb(i, p)
        project_body(i, p, max(len(wrap(q[2], 18.2, CARD_W - 52)) for q in pair))
    certs_head()
    for i, c in enumerate(CERTS):
        cert(i, c)
    cert_cta(len(CERTS) % 3)
    stats()
    services()
    process()
    contact()
    footer()
    readme()


if __name__ == "__main__":
    main()
