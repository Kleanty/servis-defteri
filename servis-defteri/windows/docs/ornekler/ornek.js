// Node.js 18+ ornegi (fetch yerlesik)
const BASE = "https://alanadiniz.com/api/v1";
const KEY = "API_ANAHTARI";

async function bildir(kayit) {
  const r = await fetch(BASE + "/is-emirleri", {
    method: "POST",
    headers: { "Authorization": "Bearer " + KEY, "Content-Type": "application/json", "User-Agent": "MuhasebeYazilimi/1.0" },
    body: JSON.stringify(kayit),
  });
  return { durum: r.status, govde: await r.json() };   // 200 eslesti/tekrar, 202 incelemeye alindi
}

bildir({ kayit_no: "K-10425", plaka: "35 ABC 123", km: 120010, yapilan_islem: ["Yağ değişimi"], durum: "Tamamlandı" })
  .then(console.log).catch(console.error);
