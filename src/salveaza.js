// Citește CSV-ul OPCOM și salvează în flow "opcom_preturi" = { "AAAA-LL-ZZ" (ziua OPCOM): [ {interval, ora_cet, ts_utc, pret_lei_mwh} ] }
// Intervalele OPCOM sunt în CET/CEST: ts_utc = începutul slotului în UTC (00:00 CET/CEST al zilei + (interval-1)*15 min).
//@@CORE@@
const preturi = ocParseCsv(msg.payload, msg.opcomZi);
if (msg.statusCode !== 200 || preturi.length === 0) {
    node.status({ fill: "yellow", shape: "ring", text: msg.opcomZi + ": încă fără prețuri (cod " + msg.statusCode + ")" });
    return null;
}
const toate = flow.get("opcom_preturi") || {};
toate[msg.opcomZi] = preturi;
Object.keys(toate).sort().slice(0, -5).forEach(k => delete toate[k]);   // păstrăm ultimele 5 zile (inclusiv ieri)
flow.set("opcom_preturi", toate);
const v = preturi.map(p => p.pret_lei_mwh);
node.status({ fill: "green", shape: "dot", text: msg.opcomZi + ": " + preturi.length + " intervale, " + Math.min(...v) + "–" + Math.max(...v) + " lei/MWh" });
return { topic: "publica" };   // publică imediat în HA
