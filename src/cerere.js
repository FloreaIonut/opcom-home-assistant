// Cere prețurile OPCOM PZU (15 min) pentru AZI și, după ora 13, pentru MÂINE, doar dacă lipsesc.
// Rulează la pornire și la fiecare 10 minute (vezi nodul inject).
const preturi = flow.get("opcom_preturi") || {};
const local = new Date(new Date().toLocaleString("en-US", { timeZone: "Europe/Bucharest" }));
function zi(offset) {
    const d = new Date(local); d.setDate(d.getDate() + offset);
    const p = x => String(x).padStart(2, "0");
    return { key: d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()),
             opcom: p(d.getDate()) + "/" + p(d.getMonth() + 1) + "/" + d.getFullYear() };
}
const zile = [zi(0)];
if (local.getHours() >= 13) zile.push(zi(1));   // OPCOM publică ziua de mâine în jur de 13:00–14:30
const cereri = zile.filter(z => !preturi[z.key] || preturi[z.key].length === 0).map(z => ({
    url: "https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv/" + z.opcom + "/ro?resolution=15",
    method: "GET", opcomZi: z.key
}));
if (cereri.length === 0) { node.status({ fill: "green", shape: "dot", text: "prețuri deja descărcate: " + zile.map(z => z.key).join(", ") }); return null; }
node.status({ fill: "blue", shape: "dot", text: "cer: " + cereri.map(c => c.opcomZi).join(", ") });
return [cereri];
