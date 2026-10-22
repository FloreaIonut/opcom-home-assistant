// Arată dacă HA a primit senzorul (200 = actualizat, 201 = creat)
if (msg.statusCode === 200 || msg.statusCode === 201) {
    node.status({ fill: "green", shape: "dot", text: "HA OK la " + new Date().toLocaleTimeString("ro-RO", { timeZone: "Europe/Bucharest" }) });
} else {
    node.status({ fill: "red", shape: "ring", text: "HA a răspuns " + msg.statusCode + (msg.statusCode === 401 ? " — token greșit" : "") });
    node.warn("Eroare HA " + msg.statusCode + ": " + JSON.stringify(msg.payload).slice(0, 200));
}
return null;
