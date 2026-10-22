# Reface fluxul Node-RED (flows/opcom-home-assistant.json) și cardul (card/card_opcom_preturi.yaml) din sursele din src/ și card/
import json, secrets, os
D = os.path.dirname(os.path.abspath(__file__))
R = lambda f: open(os.path.join(D, f), encoding='utf-8').read().strip()
i = lambda: secrets.token_hex(8)
T, IN1, F1, H1, F2, IN2, F3, H2, F4, CM = [i() for _ in range(10)]
fn = lambda id, name, f, x, y, w: {"id": id, "type": "function", "z": T, "name": name, "func": R(f), "outputs": 1, "timeout": 0, "noerr": 0, "initialize": "", "finalize": "", "libs": [], "x": x, "y": y, "wires": w}
hr = lambda id, name, ret, x, y, w: {"id": id, "type": "http request", "z": T, "name": name, "method": "use", "ret": ret, "paytoqs": "ignore", "url": "", "tls": "", "persist": False, "proxy": "", "insecureHTTPParser": False, "authType": "", "senderr": False, "headers": [], "x": x, "y": y, "wires": w}
nodes = [
    {"id": T, "type": "tab", "label": "OPCOM → Home Assistant", "disabled": False, "info": "Prețurile PZU de la OPCOM (15/30/60 min, azi și mâine) trimise în Home Assistant ca sensor.opcom_pret_acum.\n\nSetări: doar în nodul „Publică în HA” (HA_URL și HA_TOKEN).", "env": []},
    {"id": CM, "type": "comment", "z": T, "name": "⚙ Completează HA_URL și HA_TOKEN în nodul „Publică în HA”, apoi Deploy", "info": "", "x": 330, "y": 40, "wires": []},
    {"id": IN1, "type": "inject", "z": T, "name": "pornire + la 10 min", "props": [], "repeat": "600", "crontab": "", "once": True, "onceDelay": "5", "topic": "", "x": 150, "y": 100, "wires": [[F1]]},
    fn(F1, "Cerere OPCOM", "src/cerere.js", 350, 100, [[H1]]),
    hr(H1, "OPCOM CSV", "txt", 540, 100, [[F2]]),
    fn(F2, "Salvează prețuri", "src/salveaza.js", 730, 100, [[F3]]),
    {"id": IN2, "type": "inject", "z": T, "name": "la fiecare minut", "props": [], "repeat": "60", "crontab": "", "once": True, "onceDelay": "20", "topic": "", "x": 150, "y": 180, "wires": [[F3]]},
    fn(F3, "Publică în HA", "src/publica.js", 350, 180, [[H2]]),
    hr(H2, "HA API", "obj", 540, 180, [[F4]]),
    fn(F4, "Rezultat HA", "src/rezultat.js", 730, 180, []),
]
os.makedirs(os.path.join(D, 'flows'), exist_ok=True)
open(os.path.join(D, 'flows', 'opcom-home-assistant.json'), 'w', encoding='utf-8').write(json.dumps(nodes, indent=4, ensure_ascii=False) + "\n")
js = R('card/card_opcom.js'); css = R('card/card_opcom.css').replace('\n', '')
ind = lambda t, n: '\n'.join((' ' * n + l) if l else '' for l in t.split('\n'))
y = f"""type: custom:button-card
entity: sensor.opcom_pret_acum
show_name: false
show_icon: false
show_state: false
show_label: false
tap_action:
  action: none
hold_action:
  action: more-info
styles:
  card:
    - padding: 0px
    - background: none
    - border: none
    - box-shadow: none
    - overflow: visible
  grid:
    - grid-template-areas: '"f"'
    - grid-template-columns: 1fr
  custom_fields:
    f:
      - width: 100%
extra_styles: {json.dumps(css, ensure_ascii=False)}
custom_fields:
  f: |
    [[[
{ind(js, 6)}
    ]]]
"""
open(os.path.join(D, 'card', 'card_opcom_preturi.yaml'), 'w', encoding='utf-8').write(y)
print('ok')
