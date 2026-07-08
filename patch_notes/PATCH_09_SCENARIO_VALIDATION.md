# Patch 09 — Scenario Validation, Monte Carlo and Presentation Reel

## هدف
اعتبارسنجی عملکرد حلقه‌بستهٔ Phase 08 در چهار سناریوی نام‌دار و بیست آزمایش Monte Carlo بازتولیدپذیر.

## اضافه‌شده
- `config/phase09_scenarios.yaml`
- `src/aquaskim/phase09.py`
- `tests/test_phase09.py`
- `scripts/run_patch_09.bat`
- مستندات کامل Phase 09
- به‌روزرسانی CLI، automation، paths، رجیستری و build-all

## قرارداد مدل
- جریان در هر Trial ثابت و یکنواخت است.
- محیط شامل مانع‌های ثابت است.
- Monte Carlo در بازهٔ سرعت جریان 0 تا 0.02 m/s و SOC اولیهٔ 0.31 تا 0.48 اجرا می‌شود.
- خروجی‌ها گواهی ایمنی یا اعتبارسنجی میدان واقعی نیستند.

## فرمان اصلی
```bat
scripts\run_patch_09.bat
```
