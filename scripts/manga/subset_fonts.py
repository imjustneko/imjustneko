"""One-off helper: subset the source fonts into the small WOFF2 files that
build.py embeds into every SVG. Re-run only when new Japanese text is added.

    pip install fonttools brotli
    python scripts/manga/subset_fonts.py Bangers-Regular.ttf ComicNeue-Bold.ttf NotoSansCJK-Bold.ttc
"""
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTCollection, TTFont

sys.path.insert(0, str(Path(__file__).parent))
from build import JP_TEXT  # noqa: E402

OUT = Path(__file__).parent / "fonts"
ASCII = "".join(chr(c) for c in range(0x20, 0x7F))


def save(font: TTFont, text: str, name: str) -> None:
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    sub = subset.Subsetter(opts)
    sub.populate(text=text)
    sub.subset(font)
    font.flavor = "woff2"
    font.save(OUT / name)
    print(name, (OUT / name).stat().st_size, "bytes")


def main(bangers: str, comic: str, noto_ttc: str) -> None:
    OUT.mkdir(exist_ok=True)
    save(TTFont(bangers), ASCII, "bangers.woff2")
    save(TTFont(comic), ASCII + "—–’‘“”…•·×", "comic.woff2")
    jp = next(f for f in TTCollection(noto_ttc).fonts if f["name"].getDebugName(1) == "Noto Sans CJK JP")
    save(jp, "".join(sorted(set(JP_TEXT))) + "!?", "jp.woff2")


if __name__ == "__main__":
    main(*sys.argv[1:4])
