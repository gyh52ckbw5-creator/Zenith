"""Zenith yetenekleri (skills): anahtarsiz, ucretsiz servislerle calisan
arac katmani. Her yetenek bir komut onekiyle tetiklenir ve dogrudan bir cevap
ya da modele verilecek zengin baglam uretir.

Servisler:
  - Wikipedia (ozet)                      -> "wiki: <konu>"
  - Hava durumu (open-meteo)              -> "hava: <sehir>"
  - Doviz kuru (frankfurter)              -> "kur: <miktar> <FROM> <TO>"
  - Haber basliklari (Google News RSS)    -> "haber: <konu?>"
  - Ingilizce sozluk (dictionaryapi.dev)  -> "sozluk: <kelime>"
  - Sifre uretici (yerel, secrets)        -> "sifre: <uzunluk?>"
  - Sherlock tarzi kullanici adi aramasi  -> "kullanici: <ad>"
  - Web sayfasi getirme (ozetleme icin)   -> "ozetle: <url>"

Ag gerektirenler httpx ile async yapilir ve serverless butcesini korumak icin
kisa zaman asimlariyla calisir.
"""

from __future__ import annotations

import asyncio
import re
import secrets
import string
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser

import httpx

HTTP_TIMEOUT = 10.0
# Wikimedia API'leri politika geregi tanimlayici bir User-Agent (iletisim/proje
# baglantisi) ister; genel/bos UA'lar 403 alabilir.
USER_AGENT = "ZenithAssistant/1.0 (https://github.com/gyh52ckbw5-creator/Zenith)"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=HTTP_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )


# --------------------------------------------------------------------------- #
# Wikipedia
# --------------------------------------------------------------------------- #
async def wikipedia(query: str, lang: str = "tr") -> str:
    async with _client() as client:
        try:
            # 1) Bulanik baslik aramasi (REST): "kuantum fizigi" -> "Kuantum_mekaniği"
            search = await client.get(
                f"https://{lang}.wikipedia.org/w/rest.php/v1/search/title",
                params={"q": query, "limit": 1},
            )
            pages = search.json().get("pages", [])
            if not pages:
                return f"Wikipedia'da '{query}' icin bir sey bulunamadi."
            title = pages[0]["title"]

            # 2) Giris ozetini action API'den al (politika-dostu, kararli).
            extract_resp = await client.get(
                f"https://{lang}.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "format": "json",
                    "prop": "extracts",
                    "exintro": 1,
                    "explaintext": 1,
                    "redirects": 1,
                    "titles": title,
                },
            )
            page_data = next(
                iter(extract_resp.json().get("query", {}).get("pages", {}).values()), {}
            )
        except (httpx.HTTPError, ValueError, StopIteration) as exc:
            return f"[wiki hatasi] {exc}"

    extract = page_data.get("extract", "").strip()
    page_title = page_data.get("title", title)
    if not extract:
        return f"Wikipedia'da '{query}' icin ozet bulunamadi."
    url = f"https://{lang}.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
    return f"**{page_title}**\n\n{extract}\n\n{url}"


# --------------------------------------------------------------------------- #
# Hava durumu (open-meteo, anahtarsiz)
# --------------------------------------------------------------------------- #
_WEATHER_CODES = {
    0: "acik",
    1: "az bulutlu",
    2: "parcali bulutlu",
    3: "kapali",
    45: "sisli",
    48: "kirci sis",
    51: "hafif ciseleme",
    53: "ciseleme",
    55: "yogun ciseleme",
    61: "hafif yagmur",
    63: "yagmur",
    65: "kuvvetli yagmur",
    71: "hafif kar",
    73: "kar",
    75: "yogun kar",
    80: "saganak",
    81: "saganak",
    82: "siddetli saganak",
    95: "gok gurultulu firtina",
    96: "dolu ile firtina",
    99: "siddetli dolu firtina",
}


async def weather(city: str) -> str:
    async with _client() as client:
        try:
            geo = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "language": "tr"},
            )
            results = geo.json().get("results")
            if not results:
                return f"'{city}' adinda bir yer bulunamadi."
            place = results[0]
            forecast = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m",
                    "timezone": "auto",
                },
            )
            cur = forecast.json()["current"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            return f"[hava hatasi] {exc}"

    desc = _WEATHER_CODES.get(cur.get("weather_code"), "bilinmiyor")
    name = f"{place['name']}, {place.get('country', '')}".strip(", ")
    return (
        f"**{name}** hava durumu:\n"
        f"- Durum: {desc}\n"
        f"- Sicaklik: {cur['temperature_2m']}C (hissedilen {cur['apparent_temperature']}C)\n"
        f"- Nem: %{cur['relative_humidity_2m']}\n"
        f"- Ruzgar: {cur['wind_speed_10m']} km/s"
    )


# --------------------------------------------------------------------------- #
# Doviz kuru (frankfurter, anahtarsiz)
# --------------------------------------------------------------------------- #
_CURRENCY_ALIASES = {
    "DOLAR": "USD",
    "USD": "USD",
    "EURO": "EUR",
    "AVRO": "EUR",
    "EUR": "EUR",
    "STERLIN": "GBP",
    "POUND": "GBP",
    "GBP": "GBP",
    "TL": "TRY",
    "LIRA": "TRY",
    "TRY": "TRY",
    "FRANK": "CHF",
    "CHF": "CHF",
    "YEN": "JPY",
    "JPY": "JPY",
}


def _normalize_currency(token: str) -> str | None:
    return _CURRENCY_ALIASES.get(token.upper().strip())


async def currency(spec: str) -> str:
    """spec ornekleri: '100 USD TRY', 'dolar tl', 'EUR USD'."""
    tokens = spec.replace(",", " ").split()
    amount = 1.0
    codes: list[str] = []
    for tok in tokens:
        try:
            amount = float(tok)
            continue
        except ValueError:
            pass
        code = _normalize_currency(tok)
        if code:
            codes.append(code)

    if len(codes) < 2:
        frm, to = "USD", "TRY"  # varsayilan: dolar/TL
        if len(codes) == 1:
            frm = codes[0]
            to = "TRY" if frm != "TRY" else "USD"
    else:
        frm, to = codes[0], codes[1]

    async with _client() as client:
        try:
            resp = await client.get(
                "https://api.frankfurter.dev/v1/latest",
                params={"base": frm, "symbols": to},
            )
            data = resp.json()
            rate = data["rates"][to]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            return f"[kur hatasi] {exc}"

    total = amount * rate
    return f"{amount:g} {frm} = {total:,.2f} {to} (1 {frm} = {rate:g} {to}, {data.get('date', '')})"


# --------------------------------------------------------------------------- #
# Haber basliklari (Google News RSS, anahtarsiz)
# --------------------------------------------------------------------------- #
async def news(topic: str = "", limit: int = 6) -> str:
    topic = topic.strip()
    if topic and topic.lower() not in {"gundem", "genel", "manset"}:
        url = "https://news.google.com/rss/search"
        params = {"q": topic, "hl": "tr", "gl": "TR", "ceid": "TR:tr"}
    else:
        url = "https://news.google.com/rss"
        params = {"hl": "tr", "gl": "TR", "ceid": "TR:tr"}

    async with _client() as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
        except (httpx.HTTPError, ET.ParseError) as exc:
            return f"[haber hatasi] {exc}"

    items = root.findall(".//item")[:limit]
    if not items:
        return f"'{topic}' icin haber bulunamadi." if topic else "Haber bulunamadi."

    baslik = f"Son haberler ({topic})" if topic else "Son haberler"
    lines = []
    for it in items:
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        lines.append(f"- [{title}]({link})")
    return f"**{baslik}:**\n" + "\n".join(lines)


# --------------------------------------------------------------------------- #
# Ingilizce sozluk (dictionaryapi.dev, anahtarsiz)
# --------------------------------------------------------------------------- #
async def dictionary(word: str) -> str:
    word = word.strip().split()[0] if word.strip() else ""
    if not word:
        return "Bir kelime yazin, orn: sozluk: serendipity"

    async with _client() as client:
        try:
            resp = await client.get(
                f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
            )
            if resp.status_code == 404:
                return f"'{word}' icin (Ingilizce) tanim bulunamadi."
            resp.raise_for_status()
            entries = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            return f"[sozluk hatasi] {exc}"

    lines = [f"**{word}**"]
    for meaning in entries[0].get("meanings", [])[:3]:
        pos = meaning.get("partOfSpeech", "")
        definition = meaning.get("definitions", [{}])[0].get("definition", "")
        if definition:
            lines.append(f"- _{pos}_: {definition}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Sifre uretici (yerel, kriptografik olarak guvenli)
# --------------------------------------------------------------------------- #
async def password(spec: str = "") -> str:
    length = 16
    match = re.search(r"\d+", spec or "")
    if match:
        length = max(8, min(64, int(match.group())))

    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        # En az bir kucuk, buyuk, rakam ve simge iceren bir sifre garanti et.
        if (
            any(c.islower() for c in pw)
            and any(c.isupper() for c in pw)
            and any(c.isdigit() for c in pw)
            and any(c in "!@#$%^&*-_=+" for c in pw)
        ):
            break
    return f"Uretilen sifre ({length} karakter):\n`{pw}`"


# --------------------------------------------------------------------------- #
# Sherlock tarzi kullanici adi aramasi
# --------------------------------------------------------------------------- #
# Popular sitelerde bir kullanici adinin var olup olmadigini paralel kontrol
# eder. Tam Sherlock (~400 site) yerine hizli, guvenilir bir alt kume kullanir.
_SITES: dict[str, str] = {
    "GitHub": "https://github.com/{}",
    "GitLab": "https://gitlab.com/{}",
    "Instagram": "https://www.instagram.com/{}",
    "X (Twitter)": "https://x.com/{}",
    "Reddit": "https://www.reddit.com/user/{}",
    "Telegram": "https://t.me/{}",
    "TikTok": "https://www.tiktok.com/@{}",
    "YouTube": "https://www.youtube.com/@{}",
    "Twitch": "https://www.twitch.tv/{}",
    "Pinterest": "https://www.pinterest.com/{}",
    "Medium": "https://medium.com/@{}",
    "Steam": "https://steamcommunity.com/id/{}",
    "SoundCloud": "https://soundcloud.com/{}",
    "Dev.to": "https://dev.to/{}",
    "Replit": "https://replit.com/@{}",
}

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{2,40}$")


@dataclass
class SiteHit:
    site: str
    url: str
    found: bool


async def _check_site(client: httpx.AsyncClient, site: str, template: str, username: str) -> SiteHit:
    url = template.format(username)
    try:
        resp = await client.get(url)
        found = resp.status_code == 200
    except httpx.HTTPError:
        found = False
    return SiteHit(site=site, url=url, found=found)


async def username_search(username: str) -> str:
    username = username.strip().lstrip("@")
    if not _USERNAME_RE.match(username):
        return "Gecersiz kullanici adi. Yalnizca harf, rakam, '_', '.', '-' kullanin."

    async with _client() as client:
        hits = await asyncio.gather(
            *(_check_site(client, s, t, username) for s, t in _SITES.items())
        )

    found = [h for h in hits if h.found]
    if not found:
        return (
            f"**@{username}** icin kontrol edilen {len(_SITES)} sitede acik profil "
            f"bulunamadi. (Bazi siteler botlari engelleyip yanlis negatif verebilir.)"
        )

    lines = [f"- {h.site}: {h.url}" for h in found]
    return (
        f"**@{username}** su sitelerde bulundu ({len(found)}/{len(_SITES)}):\n"
        + "\n".join(lines)
        + "\n\nNot: Ayni kullanici adi farkli kisilere ait olabilir; kesin degildir."
    )


# --------------------------------------------------------------------------- #
# Web sayfasi getirme (ozetleme icin metin cikarma)
# --------------------------------------------------------------------------- #
class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip == 0:
            text = data.strip()
            if text:
                self.parts.append(text)


async def fetch_page_text(url: str, max_chars: int = 6000) -> str:
    if not re.match(r"^https?://", url):
        url = "https://" + url
    async with _client() as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise SkillError(f"Sayfa getirilemedi: {exc}") from exc

    parser = _TextExtractor()
    parser.feed(resp.text)
    text = " ".join(parser.parts)
    return text[:max_chars]


class SkillError(RuntimeError):
    """Bir yetenek servisine ulasilamadiginda firlatilir."""
