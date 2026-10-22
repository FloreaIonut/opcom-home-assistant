// ===================== SETĂRI (aici modifici) =====================
const HA_URL   = "http://homeassistant.local:8123";   // adresa Home Assistant (ex. http://192.168.1.10:8123)
const HA_TOKEN = "PUNE_AICI_TOKEN_HA";                  // Profil HA → Securitate → Long-lived access token
const ENTITATE = "sensor.opcom_pret_acum";              // NU schimba: cardul citește acest senzor
// ==================================================================
// Ziua „azi/mâine” = ziua locală Europe/Bucharest; intervalele OPCOM (CET/CEST) sunt mutate cu +1 h (docs/corectie-fus-orar.md).
// Trimite în HA prețul curent + listele pe 15/30/60 min pentru azi și mâine.
if (HA_TOKEN.startsWith("PUNE_AICI")) { node.status({ fill: "red", shape: "ring", text: "completează HA_URL și HA_TOKEN în acest nod" }); return null; }
//@@CORE@@
const rez = ocConstruieste(flow.get("opcom_preturi") || {}, Date.now());
const pretAcum = rez.pretAcum;
msg.url = HA_URL.replace(/\/+$/, "") + "/api/states/" + ENTITATE;
msg.method = "POST";
msg.headers = { "Authorization": "Bearer " + HA_TOKEN, "Content-Type": "application/json" };
msg.payload = {
    state: pretAcum !== undefined ? String(pretAcum) : "unknown",
    attributes: Object.assign({}, rez.atribute, { unit_of_measurement: "lei/MWh", friendly_name: "OPCOM Pret acum", icon: "mdi:flash" })
};
node.status({ fill: pretAcum !== undefined ? "blue" : "yellow", shape: "dot",
    text: (pretAcum !== undefined ? pretAcum + " lei/MWh (interval " + rez.intervalAcum + ")" : "fără preț acum") + " · mâine " + (rez.maineDisponibil ? "da" : "nu") });
return msg;
