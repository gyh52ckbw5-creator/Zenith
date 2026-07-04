import httpx
import pytest

from zenith import skills


def _mock_client(handler):
    """skills._client yerine, istekleri handler ile karsilayan bir
    AsyncClient dondurur (gercek ag cagrisi yapmaz)."""
    transport = httpx.MockTransport(handler)

    def factory():
        return httpx.AsyncClient(transport=transport, base_url="https://test")

    return factory


@pytest.mark.asyncio
async def test_currency_parses_amount_and_aliases(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["base"] == "USD"
        assert request.url.params["symbols"] == "TRY"
        return httpx.Response(200, json={"date": "2026-07-03", "rates": {"TRY": 40.0}})

    monkeypatch.setattr(skills, "_client", _mock_client(handler))
    result = await skills.currency("100 dolar tl")
    assert "100 USD" in result
    assert "4,000.00 TRY" in result


@pytest.mark.asyncio
async def test_weather_formats_current_conditions(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if "geocoding" in request.url.host:
            return httpx.Response(
                200,
                json={"results": [{"name": "Izmir", "country": "Turkiye", "latitude": 38.4, "longitude": 27.1}]},
            )
        return httpx.Response(
            200,
            json={
                "current": {
                    "temperature_2m": 30.0,
                    "apparent_temperature": 33.0,
                    "weather_code": 0,
                    "wind_speed_10m": 5.0,
                    "relative_humidity_2m": 40,
                }
            },
        )

    monkeypatch.setattr(skills, "_client", _mock_client(handler))
    result = await skills.weather("Izmir")
    assert "Izmir" in result
    assert "acik" in result
    assert "30.0C" in result


@pytest.mark.asyncio
async def test_username_search_reports_found_sites(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        # GitHub ve GitLab "bulundu", digerleri 404.
        if request.url.host in {"github.com", "gitlab.com"}:
            return httpx.Response(200)
        return httpx.Response(404)

    monkeypatch.setattr(skills, "_client", _mock_client(handler))
    result = await skills.username_search("someone")
    assert "GitHub" in result
    assert "GitLab" in result


@pytest.mark.asyncio
async def test_username_search_rejects_invalid_input():
    result = await skills.username_search("has spaces!")
    assert "Gecersiz" in result


@pytest.mark.asyncio
async def test_username_search_none_found(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    monkeypatch.setattr(skills, "_client", _mock_client(handler))
    result = await skills.username_search("nobodyxyz")
    assert "bulunamadi" in result


@pytest.mark.asyncio
async def test_fetch_page_text_strips_html(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        html = "<html><head><style>x{}</style></head><body><p>Merhaba</p><script>evil()</script> dunya</body></html>"
        return httpx.Response(200, text=html)

    monkeypatch.setattr(skills, "_client", _mock_client(handler))
    text = await skills.fetch_page_text("https://x")
    assert "Merhaba" in text
    assert "dunya" in text
    assert "evil" not in text


@pytest.mark.asyncio
async def test_fetch_page_text_raises_on_http_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    monkeypatch.setattr(skills, "_client", _mock_client(handler))
    with pytest.raises(skills.SkillError):
        await skills.fetch_page_text("https://x")


@pytest.mark.asyncio
async def test_password_generates_requested_length():
    result = await skills.password("24")
    assert "24 karakter" in result
    pw = result.split("`")[1]
    assert len(pw) == 24
    assert any(c.isdigit() for c in pw)
    assert any(c.isupper() for c in pw)


@pytest.mark.asyncio
async def test_password_default_length():
    result = await skills.password("")
    pw = result.split("`")[1]
    assert len(pw) == 16


@pytest.mark.asyncio
async def test_news_parses_rss(monkeypatch):
    rss = """<?xml version="1.0"?><rss><channel>
      <item><title>Baslik 1</title><link>https://a</link></item>
      <item><title>Baslik 2</title><link>https://b</link></item>
    </channel></rss>"""

    def handler(request):
        return httpx.Response(200, text=rss)

    monkeypatch.setattr(skills, "_client", _mock_client(handler))
    result = await skills.news("teknoloji")
    assert "Baslik 1" in result
    assert "teknoloji" in result


@pytest.mark.asyncio
async def test_dictionary_returns_definition(monkeypatch):
    def handler(request):
        return httpx.Response(
            200,
            json=[{"meanings": [{"partOfSpeech": "noun", "definitions": [{"definition": "test tanimi"}]}]}],
        )

    monkeypatch.setattr(skills, "_client", _mock_client(handler))
    result = await skills.dictionary("word")
    assert "test tanimi" in result


@pytest.mark.asyncio
async def test_dictionary_handles_404(monkeypatch):
    def handler(request):
        return httpx.Response(404)

    monkeypatch.setattr(skills, "_client", _mock_client(handler))
    result = await skills.dictionary("qwzxq")
    assert "bulunamadi" in result


@pytest.mark.asyncio
async def test_wikipedia_returns_extract(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if "search/title" in request.url.path:
            return httpx.Response(200, json={"pages": [{"title": "Test Konu"}]})
        return httpx.Response(
            200,
            json={"query": {"pages": {"1": {"title": "Test Konu", "extract": "Bu bir ozet."}}}},
        )

    monkeypatch.setattr(skills, "_client", _mock_client(handler))
    result = await skills.wikipedia("test")
    assert "Test Konu" in result
    assert "Bu bir ozet." in result
