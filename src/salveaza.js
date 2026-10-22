// Citește CSV-ul OPCOM și salvează în flow "opcom_preturi" = { "AAAA-LL-ZZ": [ {interval, ora, pret_lei_mwh} ] }
const text = typeof msg.payload === "string" ? msg.payload : "";
const preturi = [];
text.split("\n").forEach(linie => {
    linie = linie.trim();
    if (!linie.startsWith('"Romania"')) return;
    const col = linie.split(",").map(c => c.replace(/"/g, "").trim());
    const interval = parseInt(col[1]), pret = parseFloat(col[2]);
    if (isNaN(interval) || isNaN(pret)) return;
    const min = (interval - 1) * 15;
    preturi.push({ interval: interval, ora: String(Math.floor(min / 60)).padStart(2, "0") + ":" + String(min % 60).padStart(2, "0"), pret_lei_mwh: pret });
});
if (msg.statusCode !== 200 || preturi.length === 0) {
    node.status({ fill: "yellow", shape: "ring", text: msg.opcomZi + ": încă fără prețuri (cod " + msg.statusCode + ")" });
    return null;
}
const toate = flow.get("opcom_preturi") || {};
toate[msg.opcomZi] = preturi;
Object.keys(toate).sort().slice(0, -3).forEach(k => delete toate[k]);   // păstrăm ultimele 3 zile
flow.set("opcom_preturi", toate);
const v = preturi.map(p => p.pret_lei_mwh);
node.status({ fill: "green", shape: "dot", text: msg.opcomZi + ": " + preturi.length + " intervale, " + Math.min(...v) + "–" + Math.max(...v) + " lei/MWh" });
return { topic: "publica" };   // publică imediat în HA
