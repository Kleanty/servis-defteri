// C# (.NET 6+ / .NET Framework 4.7.2+) ornegi
using System;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Threading.Tasks;

class Program
{
    const string Base = "https://alanadiniz.com/api/v1";
    const string Key = "API_ANAHTARI";

    static async Task Main()
    {
        using var http = new HttpClient();
        http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", Key);
        http.DefaultRequestHeaders.UserAgent.ParseAdd("MuhasebeYazilimi/1.0");   // User-Agent gonderin; bos/varsayilan kimlikler guvenlik duvarinca engellenebilir
        var json = "{\"kayit_no\":\"K-10425\",\"plaka\":\"35 ABC 123\",\"km\":120010,\"yapilan_islem\":[\"Yağ değişimi\"],\"durum\":\"Tamamlandı\"}";
        var yanit = await http.PostAsync(Base + "/is-emirleri", new StringContent(json, Encoding.UTF8, "application/json"));
        Console.WriteLine((int)yanit.StatusCode + " " + await yanit.Content.ReadAsStringAsync());
        // 200 eslesti/tekrar, 202 incelemeye alindi -> basarili sayin. 5xx ve 429 (Retry-After) tekrar denenir.
    }
}
