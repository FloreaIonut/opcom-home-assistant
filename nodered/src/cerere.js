// Cere prețurile OPCOM PZU (15 min) pentru IERI, AZI și, după ora 13:00 ora României, pentru MÂINE, doar dacă lipsesc.
// Ieri e necesar: sloturile 93-96 ale zilei OPCOM de ieri (23:00-24:00 CET) sunt ora 00:00-01:00 locală de azi.
// Rulează la pornire și la fiecare 10 minute (vezi nodul inject).
//@@CORE@@
const preturi = flow.get("opcom_preturi") || {};
const zile = ocZileDeCerut(Date.now());
const cereri = zile.filter(z => !preturi[z.key] || preturi[z.key].length === 0).map(z => ({
    url: "https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv/" + z.opcom + "/ro?resolution=15",
    method: "GET", opcomZi: z.key
}));
if (cereri.length === 0) { node.status({ fill: "green", shape: "dot", text: "prețuri deja descărcate: " + zile.map(z => z.key).join(", ") }); return null; }
node.status({ fill: "blue", shape: "dot", text: "cer: " + cereri.map(c => c.opcomZi).join(", ") });
return [cereri];
