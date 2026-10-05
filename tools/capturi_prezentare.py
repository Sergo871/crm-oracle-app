"""Capturile de ecran pentru /prezentare (tema luminoasă), făcute cu Playwright.

    pip install playwright && python -m playwright install chromium
    python tools/capturi_prezentare.py [URL_BAZA]

Se autentifică cu contul DEMO și salvează imaginile în static/prezentare/.
Nu modifică date: tragerea cardului Kanban se anulează (pointercancel) înainte de eliberare.
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://flask-hello-oracle.duckdns.org/crm").rstrip("/")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "prezentare")
W, H = 1440, 900

# (nume, cale, pagina întreagă)
PAGES = [
    ("panou", "/", False),
    ("lista-clienti", "/clients/", False),
    ("lista-oferte", "/deals/?sort=amount&dir=desc", False),
    ("formular-client", "/clients/4/edit", True),
    ("kanban-oferte", "/deals/kanban", False),
    ("kanban-sarcini", "/tasks/kanban", False),
    ("calendar", "/calendar?m=2026-09", False),
    ("cautare", "/search?q=moldtehnica", False),
    ("companii", "/companies/", False),
    ("companie", "/companies/1003600060378/edit", True),
]


def shot(page, name, full=False):
    page.wait_for_load_state("networkidle")
    if full:  # fereastră cât toată pagina (full_page ar tăia meniul lateral fix)
        vp = page.viewport_size
        page.set_viewport_size({"width": vp["width"],
                                "height": page.evaluate("document.documentElement.scrollHeight")})
    page.screenshot(path=os.path.join(OUT, name + ".png"))
    if full:
        page.set_viewport_size(vp)
    print("ok", name)


def main():
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--lang=ro-RO"])  # datele în format zz.ll.aaaa
        ctx = browser.new_context(viewport={"width": W, "height": H}, color_scheme="light",
                                  locale="ro-RO", device_scale_factor=1)
        page = ctx.new_page()

        page.goto(BASE + "/login")
        shot(page, "logare")
        page.click("button[type=submit]")
        page.wait_for_url(BASE + "/")
        page.evaluate("localStorage.setItem('crm-theme', 'light')")

        for name, path, full in PAGES:
            page.goto(BASE + path)
            shot(page, name, full)

        # comanda cu antetul și pozițiile ei
        page.goto(BASE + "/orders/2")
        shot(page, "comanda", full=True)

        # Kanban: cardul în timpul tragerii, deasupra coloanei următoare
        page.goto(BASE + "/deals/kanban")
        page.wait_for_load_state("networkidle")
        card = page.locator(".kb-col").nth(1).locator(".kb-card").first
        target = page.locator(".kb-col").nth(2).locator(".kb-cards")
        cb, tb = card.bounding_box(), target.bounding_box()
        x0, y0 = cb["x"] + cb["width"] / 2, cb["y"] + 20
        page.mouse.move(x0, y0)
        page.mouse.down()
        page.mouse.move(x0 + 20, y0 + 10, steps=3)
        page.mouse.move(tb["x"] + tb["width"] / 2, tb["y"] + 120, steps=12)
        page.wait_for_timeout(200)
        page.screenshot(path=os.path.join(OUT, "kanban-tragere.png"))
        print("ok kanban-tragere")
        page.evaluate("document.dispatchEvent(new PointerEvent('pointercancel'))")
        page.mouse.up()

        # meniul ⋯ de pe card (alternativa fără tragere)
        page.locator(".kb-col").nth(0).locator(".kb-card .kb-menu").first.click()
        page.wait_for_timeout(150)
        page.screenshot(path=os.path.join(OUT, "kanban-meniu.png"))
        print("ok kanban-meniu")

        # telefon
        mob = browser.new_context(viewport={"width": 390, "height": 844}, color_scheme="light",
                                  device_scale_factor=2, is_mobile=True, has_touch=True,
                                  storage_state=ctx.storage_state())
        mp = mob.new_page()
        mp.goto(BASE + "/tasks/kanban")
        shot(mp, "telefon-kanban")
        mp.goto(BASE + "/calendar?m=2026-09")
        shot(mp, "telefon-calendar")
        browser.close()


if __name__ == "__main__":
    main()
