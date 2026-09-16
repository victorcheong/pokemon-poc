"""Records a captioned walkthrough of the app as a video (team select, battle with Fight /
Ask Coach / Bag, results, Swagger). Requires the stack running on http://localhost:8080.

    uv venv .venv-demo && uv pip install --python .venv-demo/bin/python playwright imageio-ffmpeg
    .venv-demo/bin/python -m playwright install chromium
    .venv-demo/bin/python scripts/record_demo.py      # writes video/*.webm

Convert to MP4 with the bundled ffmpeg:
    FF=$(.venv-demo/bin/python -c "import imageio_ffmpeg as f; print(f.get_ffmpeg_exe())")
    $FF -i video/<file>.webm -c:v libx264 -crf 22 -pix_fmt yuv420p demo.mp4
"""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8080"
OUT = Path("video"); OUT.mkdir(exist_ok=True)
W, H = 1280, 1060

CAPTION_CSS = """
#demo-cap{position:fixed;left:0;right:0;bottom:0;z-index:99999;background:rgba(10,12,30,.92);color:#fff;
font:700 18px/1.4 Nunito,system-ui,sans-serif;padding:12px 20px;border-top:4px solid #ffcc00;box-shadow:0 -6px 20px rgba(0,0,0,.5)}
#demo-cap .api{display:inline-block;margin-left:10px;padding:2px 8px;border-radius:6px;background:#3b6fd6;font-family:'Courier New',monospace;font-size:15px}
#demo-cap .step{color:#ffcc00;font-family:'Press Start 2P',monospace;font-size:11px;margin-right:12px}
.api-log{font-size:.85rem!important}
.panel:has(.api-log){outline:3px solid #ffcc00;outline-offset:2px}
"""

def cap(page, step, text, api=None):
    page.evaluate("""([step,text,api,css]) => {
      if(!document.getElementById('demo-css')){const s=document.createElement('style');s.id='demo-css';s.textContent=css;document.head.appendChild(s);}
      let d=document.getElementById('demo-cap'); if(!d){d=document.createElement('div');d.id='demo-cap';document.body.appendChild(d);}
      d.innerHTML=`<span class="step">${step}</span>${text}`+(api?`<span class="api">${api}</span>`:'');
    }""", [step, text, api, CAPTION_CSS])

def pause(page, s): page.wait_for_timeout(int(s*1000))

def wait_idle(page, timeout=180000):
    """Wait until the player can act again, must switch, or the battle finished."""
    page.wait_for_function("""() => {
      const fight=document.querySelector('.menu-btn.fight'); const res=[...document.querySelectorAll('button')].find(b=>b.textContent.includes('See results'));
      const sw=document.querySelector('.switch-panel .switch-btn:not([disabled])');
      return (fight && !fight.disabled) || res || sw; }""", timeout=timeout)

def battle_state(page):
    if page.locator("button", has_text="See results").count(): return "finished"
    if page.locator(".menu-btn.fight").count() and page.locator(".menu-btn.fight").is_enabled(): return "menu"
    return "switch"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(OUT), record_video_size={"width": W, "height": H})
    page = ctx.new_page()
    page.goto(BASE); page.wait_for_selector(".poke-card")
    cap(page, "1 / TEAM", "The Pokédex loads all 801 Pokémon from the FastAPI backend", "GET /api/pokemon"); pause(page, 3)

    for name in ("Charizard", "Mewtwo"):
        page.fill("input[placeholder*='Search']", name)
        page.locator(".poke-card", has_text=name).first.click()
        cap(page, "1 / TEAM", f"Picked {name}. Hovering a card fetches its stats and moves", f"GET /api/pokemon/{'6' if name=='Charizard' else '150'}")
        pause(page, 2)
    page.fill("input[placeholder*='Search']", "")
    page.click("text=Single 1v1"); cap(page, "1 / TEAM", "Single 1v1 format selected (Double 2v2 also available)"); pause(page, 1.5)
    page.click("text=Pick opponent")

    page.wait_for_selector(".trainer-card"); cap(page, "2 / OPPONENT", "Trainer roster served by the API", "GET /api/trainers"); pause(page, 2.5)
    page.locator(".trainer-card", has_text="BROCK").click(); pause(page, 1)
    cap(page, "2 / OPPONENT", "Starting the battle: the server builds Brock's team to match ours", "POST /api/battles")
    page.click("text=Battle!")
    page.wait_for_selector(".arena", timeout=60000); wait_idle(page)
    cap(page, "3 / BATTLE", "Battle created. Sidebar (right) logs every API call live", "201 Created"); pause(page, 3)

    turn, used_coach, used_bag = 0, False, False
    while turn < 12:
        st = battle_state(page)
        if st == "finished": break
        if st == "switch":
            cap(page, "3 / BATTLE", "Our Pokémon fainted: choosing a replacement", "POST /api/battles/{id}/turn  {kind: switch}")
            page.locator(".switch-panel .switch-btn:not([disabled])").first.click(); wait_idle(page); continue
        turn += 1
        if not used_coach:
            cap(page, "3 / BATTLE", "ASK COACH: an AI agent recommends our move", "POST /api/battles/{id}/advice")
            page.click(".menu-btn.coach"); page.wait_for_selector(".coach, .error", timeout=180000); pause(page, 5)
            used_coach = True
            if page.locator(".coach button", has_text="Do it").count():
                cap(page, "3 / BATTLE", "Following the coach. The opposing trainer's agent now picks its move", "POST /api/battles/{id}/turn")
                page.click(".coach button:has-text('Do it')"); wait_idle(page); pause(page, 1.5); continue
        hp = page.locator(".hud.me .hpnum").first.inner_text() if page.locator(".hud.me .hpnum").count() else "0 / 1"
        cur, mx = [int(x) for x in re.findall(r"\d+", hp)[:2]]
        bag_ok = page.locator(".menu-btn.bag").is_enabled()
        if not used_bag and bag_ok and cur < mx * 0.75:
            cap(page, "3 / BATTLE", "BAG: healing with a Potion costs the turn", "POST /api/battles/{id}/turn  {kind: item}")
            page.click(".menu-btn.bag"); pause(page, 1.5)
            page.locator(".switch-panel .switch-btn:not([disabled])").first.click(); used_bag = True; wait_idle(page); pause(page, 1); continue
        cap(page, "3 / BATTLE", "FIGHT opens the move list; nothing fires until a move is chosen"); page.click(".menu-btn.fight"); pause(page, 1.8)
        moves = page.locator(".move-btn:not([disabled])")
        best = 0
        for i in range(moves.count()):
            t = moves.nth(i).inner_text()
            if "×2" in t: best = i; break
        cap(page, "3 / BATTLE", "Move chosen: server resolves both sides' actions and returns the events", "POST /api/battles/{id}/turn")
        moves.nth(best).click(); wait_idle(page); pause(page, 1.5)

    if battle_state(page) == "finished":
        cap(page, "3 / BATTLE", "Battle over"); pause(page, 2); page.click("text=See results"); page.wait_for_selector(".result")
        cap(page, "4 / RESULT", "Result screen"); pause(page, 4)

    page.goto(f"{BASE}/api/docs"); page.wait_for_selector(".swagger-ui .opblock", timeout=30000)
    page.evaluate("document.querySelectorAll('.opblock-tag').forEach(t=>{})")
    cap(page, "API", "Every endpoint used above is documented in the FastAPI Swagger UI at /api/docs"); pause(page, 6)
    page.evaluate("window.scrollBy(0, 600)"); pause(page, 4)
    ctx.close(); browser.close()

vids = sorted(OUT.glob("*.webm"), key=lambda f: f.stat().st_mtime)
print("VIDEO:", vids[-1] if vids else "none", "turns:", turn)
