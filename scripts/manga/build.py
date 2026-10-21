"""Generate the manga-style SVG panels used by the profile README.

Static panels (hero, intro, chapter headers, arsenal, footer) are pure
drawing; the POWER LEVEL stats panel and QUEST cards pull live numbers
from the GitHub GraphQL API. Runs daily from .github/workflows/manga.yml.

    GH_TOKEN=... python scripts/manga/build.py
"""
import base64
import json
import math
import os
import random
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

LOGIN = "imjustneko"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "manga"
FONTS = Path(__file__).parent / "fonts"

INK = "#0D0D0D"
PAPER = "#F5F1E8"
WHITE = "#FFFFFF"
RED = "#E63946"
TONE = "#BDB8AD"
MID = "#6E6A62"

CHAPTERS = [
    ("01", "ORIGIN STORY", "第1話「はじまり」"),
    ("02", "ARSENAL", "第2話「武器」"),
    ("03", "POWER LEVEL", "第3話「戦闘力」"),
    ("04", "QUEST LOG", "第4話「冒険」"),
    ("05", "TRAINING ARC", "第5話「修行」"),
    ("06", "NEXT EPISODE", "次回予告"),
]

ARSENAL = [
    ("LANGUAGES", ["JavaScript", "TypeScript", "Python", "Java", "C#", "C++", "Dart"]),
    ("FRONTEND", ["React", "Next.js", "Tailwind CSS", "Vite", "React Query", "Zustand", "Flutter"]),
    ("BACKEND", ["Node.js", "Express", "NestJS", "Spring Boot", "ASP.NET Core", "Socket.IO", "REST / JWT"]),
    ("DATA", ["PostgreSQL", "MySQL", "MongoDB", "Prisma", "Redis", "Supabase", "Firebase"]),
    ("OPS & TOOLS", ["Docker", "Linux", "Nginx", "Vercel", "Railway", "Git", "Postman"]),
]

# Blurbs are hand-written because most repos have no description.
QUESTS = [
    ("QuitSmokeWeb", "SMOKE-FREE", "Quit-smoking companion with relapse analytics, milestones, a live leaderboard and an SOS button over WebSockets.",
     ["React", "TypeScript", "Spring Boot", "WebSocket"]),
    ("TaskProject", "TASK PROJECT", "Collaborative task platform with Google OAuth, email verification, file uploads and real-time updates.",
     ["Next.js", "NestJS", "Prisma", "Redis"]),
    ("School-Calendar-System", "SCHOOLCAL", "School event calendar with role-based access, RSVPs and reviews. JWT + refresh-token auth.",
     ["React", "Express", "PostgreSQL", "Prisma"]),
    ("Travel-web", "TRAVEL APP", "Discover destinations, book stays, write reviews and find events - with a full admin dashboard.",
     ["React", "Vite", "Node.js", "Tailwind"]),
    ("ForMeow", "PEONIA", "Generative-art digital garden: upload a photo and watch it bloom in ASCII, dot and pixel render modes.",
     ["React", "TypeScript", "p5.js", "Canvas"]),
    ("Game-Design-Document-Web", "GDD STUDIO", "Game design document platform: team goals, task tracker, daily dev logs and weekly reviews.",
     ["React", "Spring Boot", "MySQL", "Java"]),
]

JP_TEXT = "".join(c[2] for c in CHAPTERS) + "ゴ第1巻ニャッ戦闘力完つづく次回予告―"


# ---------------------------------------------------------------- helpers

def font_face(*names: str) -> str:
    families = {"bangers": "Bangers", "comic": "Comic", "jp": "JP"}
    out = []
    for n in names:
        b64 = base64.b64encode((FONTS / f"{n}.woff2").read_bytes()).decode()
        out.append(f"@font-face{{font-family:'{families[n]}';src:url(data:font/woff2;base64,{b64}) format('woff2');}}")
    return "".join(out)


BASE_CSS = (
    ".b{font-family:'Bangers',Impact,sans-serif;letter-spacing:1px}"
    ".c{font-family:'Comic','Comic Sans MS',sans-serif;font-weight:700}"
    ".j{font-family:'JP','Noto Sans CJK JP',sans-serif;font-weight:900}"
    ".pop{paint-order:stroke;stroke-linejoin:round}"
)

PATTERNS = f"""
<pattern id="dots" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
  <circle cx="4.5" cy="4.5" r="2" fill="{INK}"/></pattern>
<pattern id="dotsS" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
  <circle cx="3" cy="3" r="1.2" fill="{INK}"/></pattern>
<pattern id="dotsR" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
  <circle cx="4" cy="4" r="2" fill="{RED}"/></pattern>
<pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
  <rect width="8" height="8" fill="{PAPER}"/><line x1="0" y1="0" x2="0" y2="8" stroke="{INK}" stroke-width="3"/></pattern>
<pattern id="cross" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
  <rect width="8" height="8" fill="{PAPER}"/><path d="M0 0V8M0 0H8" stroke="{INK}" stroke-width="2"/></pattern>
<radialGradient id="fadeTL" cx="0" cy="0" r="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#000"/></radialGradient>
<radialGradient id="fadeBR" cx="1" cy="1" r="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#000"/></radialGradient>
<radialGradient id="fadeR" cx="1" cy="0.5" r="0.9"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#000"/></radialGradient>
"""


def svg(w: int, h: int, title: str, body: str, fonts=("bangers",), css: str = "", defs: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{escape(title)}">'
        f"<title>{escape(title)}</title><defs><style>{font_face(*fonts)}{BASE_CSS}{css}</style>{PATTERNS}{defs}</defs>"
        f"{body}</svg>\n"
    )


def text(x, y, s, cls, size, fill=INK, anchor="start", extra=""):
    return f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" {extra}>{escape(s)}</text>'


def tone(id_: str, x, y, w, h, pattern="dots", fade="fadeTL", opacity=1.0) -> str:
    """Screentone block that fades out like a gradient tone sheet."""
    return (
        f'<mask id="{id_}"><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{fade})"/></mask>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{pattern})" mask="url(#{id_})" opacity="{opacity}"/>'
    )


def focus_lines(cx, cy, rx, ry, n, seed, color=INK, reach=1600, wmin=1.5, wmax=9.0) -> str:
    """Manga 集中線: tapered wedges converging on an empty oval."""
    rnd = random.Random(seed)
    polys = []
    for _ in range(n):
        a = rnd.uniform(0, 2 * math.pi)
        k = rnd.uniform(1.0, 1.45)
        ix, iy = cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)
        ox, oy = cx + reach * math.cos(a), cy + reach * math.sin(a)
        hw = rnd.uniform(wmin, wmax) / 2
        px, py = -math.sin(a) * hw, math.cos(a) * hw
        polys.append(f"M{ix:.1f} {iy:.1f}L{ox + px:.1f} {oy + py:.1f}L{ox - px:.1f} {oy - py:.1f}Z")
    return f'<path d="{"".join(polys)}" fill="{color}"/>'


def wrap(s: str, width: int) -> list[str]:
    lines, cur = [], ""
    for word in s.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + [cur] if cur else lines


def burst(cx, cy, r1, r2, n, seed, fill, stroke=INK, sw=5, sx=1.6) -> str:
    rnd = random.Random(seed)
    pts = []
    for i in range(n * 2):
        a = math.pi * i / n
        r = (r2 if i % 2 == 0 else r1) * rnd.uniform(0.9, 1.1)
        pts.append(f"{cx + r * math.cos(a) * sx:.1f},{cy + r * math.sin(a):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>'


# ---------------------------------------------------------------- static panels

def hero() -> str:
    w, h = 1200, 520
    css = """
    .flick{animation:flick 1.6s steps(1) infinite}
    .flick2{animation:flick 1.6s steps(1) infinite;animation-delay:.8s;opacity:0}
    @keyframes flick{0%{opacity:1}50%{opacity:0}}
    .title{transform-box:fill-box;transform-origin:center;animation:slam .7s cubic-bezier(.2,1.6,.4,1) both}
    @keyframes slam{0%{transform:scale(1.6);opacity:0}100%{transform:scale(1);opacity:1}}
    .go{animation:bob 2.4s ease-in-out infinite}
    @keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
    """
    clip = '<clipPath id="panel"><rect x="14" y="14" width="1172" height="492"/></clipPath>'
    gos = ""
    for i, (x, y, s, r) in enumerate([(1035, 150, 66, -14), (1090, 250, 84, -8), (1030, 360, 72, -16),
                                      (125, 250, 58, 12), (175, 405, 66, 10)]):
        gos += (f'<g class="go" style="animation-delay:{i * .35:.2f}s"><text x="{x}" y="{y}" class="j pop" font-size="{s}" '
                f'fill="{INK}" stroke="{PAPER}" stroke-width="10" text-anchor="middle" transform="rotate({r} {x} {y})">ゴ</text></g>')
    body = f"""
<rect x="14" y="14" width="1172" height="492" fill="{PAPER}"/>
<g clip-path="url(#panel)">
  {tone("t1", 14, 14, 520, 300)}
  {tone("t2", 666, 206, 520, 300, fade="fadeBR")}
  <g class="flick">{focus_lines(600, 280, 430, 165, 230, 7)}</g>
  <g class="flick2">{focus_lines(600, 280, 430, 165, 230, 8)}</g>
</g>
<rect x="14" y="14" width="1172" height="492" fill="none" stroke="{INK}" stroke-width="8"/>
<polygon points="40,40 210,40 196,88 40,88" fill="{INK}"/>
{text(58, 76, "VOL. 01", "b", 36, PAPER)}
<rect x="932" y="40" width="228" height="48" fill="{WHITE}" stroke="{INK}" stroke-width="4"/>
{text(1046, 75, "@IMJUSTNEKO", "b", 30, INK, "middle")}
<polygon points="378,118 834,118 822,166 366,166" fill="{INK}"/>
{text(600, 154, "THE DEVELOPER FROM MONGOLIA", "b", 34, PAPER, "middle", 'letter-spacing="3"')}
<g class="title">
  {text(612, 362, "ANKO", "b pop", 218, RED, "middle", f'stroke="{RED}" stroke-width="16"')}
  {text(600, 350, "ANKO", "b pop", 218, INK, "middle", f'stroke="{PAPER}" stroke-width="18"')}
</g>
<polygon points="250,392 958,392 946,446 238,446" fill="{RED}" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/>
{text(598, 432, "FULL-STACK DEVELOPER  //  AI PRODUCT BUILDER", "b", 36, PAPER, "middle", 'letter-spacing="2"')}
{gos}
<rect x="40" y="462" width="326" height="30" fill="{WHITE}" stroke="{INK}" stroke-width="3"/>
{text(203, 483, "A tale of code, coffee & cats…", "c", 18, INK, "middle")}
{text(1160, 490, "第1巻", "j", 22, INK, "end")}
"""
    return svg(w, h, "ANKO - Full-stack developer and AI product builder from Mongolia", body,
               ("bangers", "comic", "jp"), css, clip)


def cat(cx: int, cy: int) -> str:
    """Original chibi cat mascot (Neko) in ink-and-screentone style."""
    s = INK
    return f"""
<g class="catbob">
  <ellipse cx="{cx}" cy="{cy + 250}" rx="150" ry="115" fill="{PAPER}" stroke="{s}" stroke-width="6"/>
  <path d="M{cx - 150} {cy + 250} Q{cx} {cy + 300} {cx + 150} {cy + 250}" fill="none" stroke="{s}" stroke-width="3" opacity=".25"/>
  <path d="M{cx - 120} {cy - 40} L{cx - 108} {cy - 165} L{cx - 30} {cy - 95} Z" fill="{PAPER}" stroke="{s}" stroke-width="6" stroke-linejoin="round"/>
  <path d="M{cx - 104} {cy - 60} L{cx - 98} {cy - 132} L{cx - 50} {cy - 92} Z" fill="url(#dots)"/>
  <path d="M{cx + 120} {cy - 40} L{cx + 108} {cy - 165} L{cx + 30} {cy - 95} Z" fill="{PAPER}" stroke="{s}" stroke-width="6" stroke-linejoin="round"/>
  <path d="M{cx + 104} {cy - 60} L{cx + 98} {cy - 132} L{cx + 50} {cy - 92} Z" fill="url(#dots)"/>
  <ellipse cx="{cx}" cy="{cy}" rx="140" ry="118" fill="{PAPER}" stroke="{s}" stroke-width="6"/>
  <path d="M{cx - 30} {cy - 112} l8 26 M{cx} {cy - 118} v28 M{cx + 30} {cy - 112} l-8 26" stroke="{s}" stroke-width="5" stroke-linecap="round"/>
  <g class="blink">
    <ellipse cx="{cx - 52}" cy="{cy + 5}" rx="30" ry="40" fill="{s}"/>
    <ellipse cx="{cx + 52}" cy="{cy + 5}" rx="30" ry="40" fill="{s}"/>
    <circle cx="{cx - 62}" cy="{cy - 12}" r="11" fill="{WHITE}"/><circle cx="{cx - 42}" cy="{cy + 22}" r="5" fill="{WHITE}"/>
    <circle cx="{cx + 42}" cy="{cy - 12}" r="11" fill="{WHITE}"/><circle cx="{cx + 62}" cy="{cy + 22}" r="5" fill="{WHITE}"/>
  </g>
  <path d="M{cx - 8} {cy + 46} h16 l-8 9 z" fill="{s}" stroke="{s}" stroke-width="3" stroke-linejoin="round"/>
  <path d="M{cx - 20} {cy + 60} q10 14 20 0 q10 14 20 0" fill="none" stroke="{s}" stroke-width="4" stroke-linecap="round"/>
  <path d="M{cx - 112} {cy + 40} l12 -16 M{cx - 98} {cy + 44} l12 -16 M{cx - 84} {cy + 48} l12 -16
           M{cx + 72} {cy + 40} l12 -16 M{cx + 86} {cy + 44} l12 -16 M{cx + 100} {cy + 48} l12 -16" stroke="{RED}" stroke-width="4" stroke-linecap="round"/>
  <path d="M{cx - 130} {cy + 52} l-50 -6 M{cx - 130} {cy + 66} l-48 10 M{cx + 130} {cy + 52} l50 -6 M{cx + 130} {cy + 66} l48 10" stroke="{s}" stroke-width="3" stroke-linecap="round"/>
  <path d="M{cx - 95} {cy + 128} Q{cx} {cy + 165} {cx + 95} {cy + 128} L{cx + 90} {cy + 150} Q{cx} {cy + 188} {cx - 90} {cy + 150} Z" fill="{RED}" stroke="{s}" stroke-width="5" stroke-linejoin="round"/>
  <circle cx="{cx}" cy="{cy + 182}" r="17" fill="#F2C94C" stroke="{s}" stroke-width="5"/>
  <path d="M{cx - 15} {cy + 180} h30 M{cx} {cy + 186} v10" stroke="{s}" stroke-width="3"/>
</g>"""


def sparkle(x, y, r) -> str:
    return (f'<path d="M{x} {y - r} Q{x} {y} {x + r} {y} Q{x} {y} {x} {y + r} Q{x} {y} {x - r} {y} Q{x} {y} {x} {y - r}Z" '
            f'fill="{WHITE}" stroke="{INK}" stroke-width="3" stroke-linejoin="round"/>')


def intro() -> str:
    w, h = 1200, 560
    css = """
    .catbob{animation:catbob 3s ease-in-out infinite}
    @keyframes catbob{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
    .blink{transform-box:fill-box;transform-origin:center;animation:blink 4s infinite}
    @keyframes blink{0%,92%,100%{transform:scaleY(1)}95%{transform:scaleY(.08)}}
    .tw{animation:tw 1.8s ease-in-out infinite;transform-box:fill-box;transform-origin:center}
    @keyframes tw{0%,100%{transform:scale(1)}50%{transform:scale(.55)}}
    """
    left = "10,10 452,10 402,550 10,550"
    right = "472,10 1190,10 1190,550 422,550"
    defs = f'<clipPath id="lp"><polygon points="{left}"/></clipPath><clipPath id="rp"><polygon points="{right}"/></clipPath>'
    bubble_tail = f'<path d="M560 205 L395 300 L615 222" fill="{WHITE}" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/>'
    who = wrap("Full-stack developer from Mongolia. I build modern web apps, automation tools and AI-powered "
               "products - thoughtful UI/UX on top of scalable, maintainable backends.", 56)
    who_txt = "".join(text(512, 322 + i * 28, ln, "c", 22) for i, ln in enumerate(who))
    def box(x, label, fill, items):
        out = (f'<rect x="{x}" y="440" width="315" height="96" fill="{WHITE}" stroke="{INK}" stroke-width="4"/>'
               f'<rect x="{x}" y="440" width="315" height="30" fill="{fill}"/>' + text(x + 12, 464, label, "b", 24, PAPER))
        for i, it in enumerate(items):
            out += f'<rect x="{x + 14}" y="{485 + i * 27}" width="10" height="10" fill="{fill}"/>' + text(x + 32, 496 + i * 27, it, "c", 20)
        return out
    body = f"""
<polygon points="{left}" fill="{PAPER}"/>
<g clip-path="url(#lp)">{tone("ta", 10, 300, 450, 260, fade="fadeBR")}{focus_lines(215, 270, 150, 140, 150, 3)}{cat(215, 250)}</g>
<polygon points="{left}" fill="none" stroke="{INK}" stroke-width="7" stroke-linejoin="round"/>
<g class="tw">{sparkle(60, 70, 18)}</g><g class="tw" style="animation-delay:.6s">{sparkle(372, 95, 14)}</g>
{text(330, 64, "ニャッ!", "j pop", 40, INK, "middle", f'stroke="{PAPER}" stroke-width="8" transform="rotate(12 330 64)"')}
<polygon points="{right}" fill="{PAPER}"/>
<g clip-path="url(#rp)">{tone("tb", 690, 10, 500, 300, fade="fadeR", opacity=.5)}</g>
<polygon points="{right}" fill="none" stroke="{INK}" stroke-width="7" stroke-linejoin="round"/>
<ellipse cx="830" cy="140" rx="330" ry="100" fill="{WHITE}" stroke="{INK}" stroke-width="5"/>
{bubble_tail}
<ellipse cx="830" cy="140" rx="326" ry="96" fill="{WHITE}"/>
{text(830, 118, "HELLO! MY NAME IS NEKO -", "c", 34, INK, "middle")}
<text x="830" y="172" class="c" font-size="34" fill="{INK}" text-anchor="middle">BUT YOU CAN CALL ME <tspan class="b" font-size="46" fill="{RED}">ANKO!</tspan></text>
<rect x="492" y="280" width="672" height="146" fill="{WHITE}" stroke="{INK}" stroke-width="4"/>
<rect x="492" y="262" width="96" height="30" fill="{INK}"/>{text(540, 285, "WHO?", "b", 26, PAPER, "middle")}
{who_txt}
{box(492, "NOW TRAINING", INK, ["Backend architecture", "AI engineering"])}
{box(849, "OPEN TO", RED, ["Full-stack & remote roles", "Collaboration"])}
"""
    return svg(w, h, "Hello! My name is Neko, but you can call me Anko. Full-stack developer from Mongolia building "
                     "modern web apps, automation tools and AI-powered products.", body, ("bangers", "comic", "jp"), css, defs)


def chapter(num: str, title: str, jp: str) -> str:
    w, h = 1200, 128
    css = ".slide{animation:slide .6s cubic-bezier(.2,1.4,.4,1) both}@keyframes slide{0%{transform:translateX(-60px);opacity:0}100%{transform:none;opacity:1}}"
    body = f"""
<rect x="4" y="14" width="1192" height="100" fill="{PAPER}" stroke="{INK}" stroke-width="5"/>
<g clip-path="url(#cp)">{tone("tc", 600, 14, 596, 100, fade="fadeR")}</g>
<polygon points="4,14 262,14 236,114 4,114" fill="{INK}"/>
{text(26, 61, "CHAPTER", "b", 28, TONE)}
{text(26, 102, num, "b", 48, PAPER)}
{text(120, 102, "///", "b", 48, RED)}
<g class="slide">
  {text(285, 96, title, "b pop", 70, RED, extra=f'stroke="{RED}" stroke-width="6" transform="translate(5 5)"')}
  {text(285, 96, title, "b pop", 70, INK, extra=f'stroke="{PAPER}" stroke-width="6"')}
</g>
<rect x="{1176 - 34 * len(jp)}" y="44" width="{34 * len(jp) + 4}" height="44" fill="{PAPER}"/>
{text(1176, 78, jp, "j", 30, INK, "end")}
"""
    return svg(w, h, f"Chapter {num}: {title}", body, ("bangers", "jp"), css,
               '<clipPath id="cp"><rect x="4" y="14" width="1192" height="100"/></clipPath>')


def arsenal() -> str:
    w, h = 1200, 392
    cw, gap = 226, 12
    body = ""
    for i, (cat_, items) in enumerate(ARSENAL):
        x = 10 + i * (cw + gap)
        body += f'<rect x="{x + 7}" y="17" width="{cw}" height="360" fill="{INK}"/>'
        body += f'<rect x="{x}" y="10" width="{cw}" height="360" fill="{PAPER}" stroke="{INK}" stroke-width="5"/>'
        body += f'<rect x="{x}" y="10" width="{cw}" height="56" fill="{RED if i % 2 else INK}"/>'
        body += text(x + cw / 2, 50, cat_, "b", 32, PAPER, "middle")
        for j, it in enumerate(items):
            y = 104 + j * 40
            body += f'<polygon points="{x + 18},{y - 14} {x + 30},{y - 8} {x + 18},{y - 2}" fill="{RED if i % 2 == 0 else INK}"/>'
            body += text(x + 40, y, it, "c", 22)
        body += f'<line x1="{x + 14}" y1="{y + 18}" x2="{x + cw - 14}" y2="{y + 18}" stroke="{INK}" stroke-width="2" stroke-dasharray="2 6"/>'
    alt = "Tech stack: " + "; ".join(f"{c}: {', '.join(i)}" for c, i in ARSENAL)
    return svg(w, h, alt, body, ("bangers", "comic"))


def footer() -> str:
    w, h = 1200, 210
    css = ".arrow{animation:arr .9s cubic-bezier(.2,1.3,.4,1) both}@keyframes arr{0%{transform:translateX(420px);opacity:0}100%{transform:none;opacity:1}}"
    arrow = "M40 105 L150 30 L150 62 L640 62 L640 148 L150 148 L150 180 Z"
    body = f"""
<rect x="4" y="4" width="1192" height="202" fill="{PAPER}" stroke="{INK}" stroke-width="5"/>
<g clip-path="url(#fp)">{focus_lines(1000, 105, 200, 60, 90, 11, reach=900)}</g>
<g class="arrow">
  <path d="{arrow}" fill="{RED}" transform="translate(8 8)"/>
  <path d="{arrow}" fill="{INK}" stroke="{PAPER}" stroke-width="4" stroke-linejoin="round"/>
  {text(395, 124, "TO BE CONTINUED", "b", 58, PAPER, "middle", 'letter-spacing="3"')}
</g>
<rect x="700" y="46" width="456" height="118" fill="{WHITE}" stroke="{INK}" stroke-width="4"/>
{text(722, 92, "次回予告 ― つづく", "j", 26, RED)}
{text(722, 126, "Next episode: we build something", "c", 22)}
{text(722, 152, "together. Say hi below!", "c", 22)}
"""
    return svg(w, h, "To be continued - next episode: we build something together.", body, ("bangers", "comic", "jp"), css,
               '<clipPath id="fp"><rect x="4" y="4" width="1192" height="202"/></clipPath>')


# ---------------------------------------------------------------- live panels

def gql(query: str, variables: dict) -> dict:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "manga-profile"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]


def fetch() -> dict:
    repos = "".join(
        f'q{i}: repository(owner: $login, name: "{name}") {{ name url homepageUrl stargazerCount pushedAt primaryLanguage {{ name }} }}'
        for i, (name, *_rest) in enumerate(QUESTS)
    )
    query = f"""query($login: String!) {{
      user(login: $login) {{
        repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {{
          totalCount
          nodes {{ stargazerCount languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{ edges {{ size node {{ name }} }} }} }}
        }}
        contributionsCollection {{
          totalCommitContributions totalPullRequestContributions totalIssueContributions
          contributionCalendar {{ totalContributions weeks {{ contributionDays {{ date contributionCount }} }} }}
        }}
      }}
      {repos}
    }}"""
    return gql(query, {"login": LOGIN})


def streaks(days: list[dict]) -> tuple[int, int, int, int]:
    counts = [d["contributionCount"] for d in sorted(days, key=lambda d: d["date"])]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current = 0
    tail = counts[:-1] if counts and counts[-1] == 0 else counts  # today isn't over yet
    for c in reversed(tail):
        if not c:
            break
        current += 1
    return current, longest, sum(1 for c in counts if c), max(counts, default=0)


LANG_FILLS = [INK, RED, "url(#dots)", "url(#hatch)", "url(#cross)", "url(#dotsR)"]


def stats(data: dict) -> str:
    w, h = 1200, 560
    user = data["user"]
    cc = user["contributionsCollection"]
    cal = cc["contributionCalendar"]
    days = [d for wk in cal["weeks"] for d in wk["contributionDays"]]
    cur, longest, active, best = streaks(days)
    total = cal["totalContributions"]
    rows = [
        ("COMMITS", cc["totalCommitContributions"]),
        ("PULL REQUESTS", cc["totalPullRequestContributions"]),
        ("ISSUES", cc["totalIssueContributions"]),
        ("ACTIVE DAYS", active),
        ("BEST DAY", best),
        ("CURRENT STREAK", f"{cur} D"),
        ("LONGEST STREAK", f"{longest} D"),
        ("PUBLIC REPOS", user["repositories"]["totalCount"]),
    ]
    langs: dict[str, int] = {}
    for node in user["repositories"]["nodes"]:
        for e in node["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:6]
    lang_total = sum(v for _, v in top) or 1

    css = ".rise{animation:rise .8s cubic-bezier(.2,1.5,.4,1) both}@keyframes rise{0%{transform:translateY(40px);opacity:0}100%{transform:none;opacity:1}}"
    over = total > 9000
    shout = "IT'S OVER 9000!!" if over else f"NEXT: {((total // 1000) + 1) * 1000:,}!"
    body = f"""
<rect x="10" y="10" width="1180" height="540" fill="{PAPER}"/>
<g clip-path="url(#sp)">{tone("ts", 10, 10, 560, 420)}{focus_lines(290, 255, 230, 95, 170, 21, reach=700)}</g>
<line x1="575" y1="10" x2="545" y2="430" stroke="{INK}" stroke-width="7"/>
<rect x="10" y="10" width="1180" height="540" fill="none" stroke="{INK}" stroke-width="8"/>
<rect x="40" y="40" width="150" height="50" fill="{INK}"/>{text(115, 78, "戦闘力", "j", 32, PAPER, "middle")}
{text(205, 76, "POWER LEVEL", "b", 38)}
<g class="rise">
  {text(296, 276, f"{total:,}", "b pop", 150, RED, "middle", f'stroke="{RED}" stroke-width="10"')}
  {text(290, 270, f"{total:,}", "b pop", 150, INK, "middle", f'stroke="{PAPER}" stroke-width="14"')}
</g>
<rect x="110" y="298" width="360" height="34" fill="{WHITE}" stroke="{INK}" stroke-width="3"/>
{text(290, 322, "contributions in the last 365 days", "c", 19, INK, "middle")}
<g transform="rotate(-6 290 378)">{burst(290, 380, 30, 44, 16, 5, RED, sx=2.4)}{text(290, 390, shout, "b", 28, PAPER, "middle")}</g>
"""
    for i, (label, val) in enumerate(rows):
        y = 70 + i * 44
        body += text(600, y + 14, label, "b", 30)
        body += f'<line x1="{620 + len(label) * 15}" y1="{y + 8}" x2="1060" y2="{y + 8}" stroke="{INK}" stroke-width="3" stroke-dasharray="2 7" stroke-linecap="round"/>'
        body += text(1160, y + 16, f"{val:,}" if isinstance(val, int) else val, "b", 36, RED, "end")
    body += f'<line x1="10" y1="430" x2="1190" y2="430" stroke="{INK}" stroke-width="7"/>'
    body += text(40, 468, "MASTERY", "b", 30) + text(160, 468, "(public repos, by code size)", "c", 16, MID)
    x = 40.0
    for i, (name, size) in enumerate(top):
        bw = 1120 * size / lang_total
        body += f'<rect x="{x:.1f}" y="482" width="{bw:.1f}" height="22" fill="{LANG_FILLS[i]}" stroke="{INK}" stroke-width="3"/>'
        x += bw
    lx = 420
    for i, (name, size) in enumerate(top):
        label = f"{name} {100 * size / lang_total:.0f}%"
        body += f'<rect x="{lx}" y="452" width="16" height="16" fill="{LANG_FILLS[i]}" stroke="{INK}" stroke-width="2"/>'
        body += text(lx + 22, 467, label, "c", 15)
        lx += 22 + len(label) * 8 + 18
    body += text(1160, 535, "auto-updated daily", "c", 14, MID, "end")
    return svg(w, h, f"Power level: {total} contributions in the last year. Current streak {cur} days, longest {longest} days.",
               body, ("bangers", "comic", "jp"), css,
               '<clipPath id="sp"><polygon points="10,10 575,10 545,430 10,430"/></clipPath>')


def quest(i: int, name: str, title: str, blurb: str, tags: list[str], repo: dict) -> str:
    w, h = 600, 318
    live = bool(repo and repo.get("homepageUrl"))
    lang = (repo or {}).get("primaryLanguage") or {}
    pushed = (repo or {}).get("pushedAt", "")[:7]
    stamp = (text(0, 9, "LIVE", "b", 28, RED, "middle") if live else text(0, 12, "完", "j", 34, RED, "middle"))
    body = f"""
<rect x="16" y="16" width="574" height="292" fill="{INK}"/>
<rect x="8" y="8" width="574" height="292" fill="{PAPER}" stroke="{INK}" stroke-width="6"/>
<g clip-path="url(#qp)">{tone("tq", 300, 150, 290, 160, fade="fadeBR", opacity=.6)}</g>
<polygon points="8,8 170,8 156,50 8,50" fill="{INK}"/>
{text(24, 41, f"QUEST {i + 1:02d}", "b", 30, PAPER)}
<g transform="translate(520 62) rotate(-14)"><circle r="40" fill="{PAPER}" stroke="{RED}" stroke-width="5"/>
<circle r="33" fill="none" stroke="{RED}" stroke-width="2"/>{stamp}</g>
{text(28, 108, title, "b pop", 52, INK, extra=f'stroke="{PAPER}" stroke-width="6"')}
"""
    for j, ln in enumerate(wrap(blurb, 50)[:3]):
        body += text(30, 146 + j * 27, ln, "c", 20)
    x = 30
    for t in tags:
        tw = len(t) * 9 + 22
        body += f'<rect x="{x}" y="232" width="{tw}" height="28" fill="{WHITE}" stroke="{INK}" stroke-width="3"/>'
        body += text(x + tw / 2, 252, t, "c", 15, INK, "middle")
        x += tw + 8
    meta = " · ".join(filter(None, [lang.get("name"), f"updated {pushed}" if pushed else None]))
    body += f'<line x1="8" y1="272" x2="582" y2="272" stroke="{INK}" stroke-width="3"/>'
    body += text(30, 294, meta, "c", 15, MID)
    body += text(560, 294, "▶ CODE + LIVE DEMO" if live else "▶ VIEW CODE", "c", 15, RED, "end")
    return svg(w, h, f"Quest {i + 1}: {title} - {blurb}", body, ("bangers", "comic", "jp"),
               defs='<clipPath id="qp"><rect x="8" y="8" width="574" height="292"/></clipPath>')


# ---------------------------------------------------------------- main

def write(name: str, content: str) -> None:
    path = OUT / name
    if not path.exists() or path.read_text() != content:
        path.write_text(content)
        print("wrote", path.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write("hero.svg", hero())
    write("intro.svg", intro())
    write("arsenal.svg", arsenal())
    write("footer.svg", footer())
    for num, title, jp in CHAPTERS:
        write(f"chapter-{num}.svg", chapter(num, title, jp))
    data = fetch()
    write("stats.svg", stats(data))
    for i, (name, title, blurb, tags) in enumerate(QUESTS):
        write(f"quest-{i + 1:02d}.svg", quest(i, name, title, blurb, tags, data.get(f"q{i}")))


if __name__ == "__main__":
    main()
