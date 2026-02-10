from __future__ import annotations

import argparse
from pathlib import Path

import pdfplumber


def _print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def _render_first_pages(pdf_path: Path, out_dir: Path, max_pages: int) -> None:
    try:
        import pypdfium2 as pdfium  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - optional dependency
        print(f"[render] skip: pypdfium2 unavailable: {exc}")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(pdf_path))
    page_count = len(doc)
    for page_index in range(min(page_count, max_pages)):
        page = doc.get_page(page_index)
        pil_image = page.render(scale=2).to_pil()
        out_path = out_dir / f"{pdf_path.stem}.page{page_index + 1}.png"
        pil_image.save(out_path)
        print(f"[render] wrote {out_path}")
        page.close()
    doc.close()


def probe_pdf(pdf_path: Path, max_pages: int, render_pages: int) -> None:
    _print_header(str(pdf_path))
    with pdfplumber.open(pdf_path) as pdf:
        print("pages:", len(pdf.pages))
        for page_index in range(min(len(pdf.pages), max_pages)):
            page = pdf.pages[page_index]
            text = page.extract_text() or ""
            lines = text.splitlines()
            print(f"\n--- page {page_index + 1}: text lines={len(lines)} ---")
            for line in lines[:60]:
                print(line)
            try:
                tables = page.extract_tables() or []
            except Exception as exc:
                print(f"[tables] error: {exc}")
                tables = []
            print(f"[tables] count={len(tables)}")
            if tables:
                t = tables[0]
                print(f"[tables] first rows={len(t)} sample:")
                for row in t[:10]:
                    print(row)

    if render_pages > 0:
        _render_first_pages(pdf_path, Path("tmp/pdfs"), max_pages=render_pages)


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe PDF structure via text/table extraction.")
    parser.add_argument("pdf", type=Path, nargs="+")
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--render-pages", type=int, default=1)
    args = parser.parse_args()

    for pdf_path in args.pdf:
        probe_pdf(pdf_path, max_pages=args.max_pages, render_pages=args.render_pages)


if __name__ == "__main__":
    main()
