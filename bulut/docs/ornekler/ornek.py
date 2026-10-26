# Python 3 ornegi (ek paket gerekmez)
import json, time, urllib.request, urllib.error

BASE = "https://alanadiniz.com/api/v1"
KEY = "API_ANAHTARI"

def bildir(kayit, deneme=3):
    istek = urllib.request.Request(BASE + "/is-emirleri", data=json.dumps(kayit).encode("utf-8"), method="POST",
                                   headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json", "User-Agent": "MuhasebeYazilimi/1.0"})
    for n in range(deneme):
        try:
            with urllib.request.urlopen(istek, timeout=20) as r:
                return r.status, json.loads(r.read().decode())          # 200 eslesti/tekrar, 202 incelemeye alindi
        except urllib.error.HTTPError as e:
            govde = json.loads(e.read().decode() or "{}")
            if e.code == 429: time.sleep(int(e.headers.get("Retry-After", "300"))); continue
            if e.code >= 500 or (e.code == 409 and govde.get("kod") == "CONFLICT"): time.sleep(2 ** n); continue   # gecici: ayni kayit_no ile tekrar
            return e.code, govde                                           # 401/422/409(IDEMPOTENCY_CONFLICT): duzeltmeden tekrar denemeyin
        except OSError: time.sleep(2 ** n)
    return 0, {"hata": "ulasilamadi"}

if __name__ == "__main__":
    print(bildir({"kayit_no": "K-10425", "plaka": "35 ABC 123", "km": 120010, "yapilan_islem": ["Yağ değişimi"], "durum": "Tamamlandı"}))
