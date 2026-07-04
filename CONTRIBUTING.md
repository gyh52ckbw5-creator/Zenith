# Zenith'e Katkı Sağlama

Zenith'i iyileştirmeye yardımcı olmak istiyorsan, bu kılavuzu takip et.

## Geliştirme Ortamı

```bash
cd Zenith
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Kod Yazma

- **Python 3.10+** kullan
- **Type hints** ekle (`from __future__ import annotations`)
- **Black** ile formatla: `black zenith/`
- **isort** ile import'ları sırala: `isort zenith/`
- **mypy** ile türleri kontrol et: `mypy zenith/`

## Testler

```bash
pytest               # Tüm testleri çalıştır
pytest tests/test_*.py -v  # Belirli testleri çalıştır
pytest --cov        # Coverage raporu ile
```

## Pull Request

1. Konu başlı bir branch aç: `git checkout -b feature/description`
2. Değişiklikleri commit et: `git commit -m "feat: açıklama"`
3. Branch'i push et: `git push origin feature/description`
4. GitHub'da pull request aç, değişiklikleri açıkla

## Commit Mesajları

[Conventional Commits](https://www.conventionalcommits.org/) kullan:

- `feat:` Yeni özellik
- `fix:` Hata düzeltmesi
- `docs:` Belgeleme
- `style:` Kod biçimi (siyah, isort)
- `refactor:` Kod yeniden yapılandırması
- `perf:` Performans iyileştirmesi
- `test:` Test ekleme/düzeltme

Örnek:
```
feat: council mode synthesis algorithm iyileştirmesi

- Çok model cevaplarında daha iyi birleştirme
- Tutarsızlık tespiti ve uzlaştırma
- Katkıları daha açık belirtme
```

## Dökümantasyon

- Kod yorumlarında Türkçe ve İngilizce kullan
- Docstring'ler yazı (Google stilinde)
- README'yi güncelle (büyük değişikliklerse)

## Yeni Bir Yetenek (Skill) Ekleme

1. `zenith/skills.py` içinde fonksiyon yaz
2. HTTP client'i `_client()` ile oluştur
3. Hata ayıklamayı `try-except` ile yap
4. Test ekle (`tests/test_skills.py`)
5. README'de documenter

## Yeni Bir Model Ekleme

`config/models.yaml` dosyasını düzenle:

```yaml
- name: awesome-model
  litellm_id: provider/model-id
  provider: provider_name
  requires_key: PROVIDER_API_KEY
  tags: [chat, code]
  priority: 50
```

## Sorular & Destek

- GitHub Issues'de soru aç
- Discussions kısmını kullan fikir ve önerileri için

Teşekkür ederiz! 🚀
