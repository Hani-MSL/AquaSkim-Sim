# Patch 10.8 — Dynamic Manoeuvre Verification

## هدف

اضافه‌کردن شواهد مستقل و قابل‌دفاع برای نیروها، دینامیک و حرکت ربات، پیش از ورود به تولید گزارش نهایی.

## اضافه‌شده‌ها

- `config/maneuver_protocol.yaml`
- `src/aquaskim/maneuver_validation.py`
- `src/aquaskim/phase10_8.py`
- نمودارهای دوبعدی، سه‌بعدی و انیمیشن‌های مانور
- آزمون‌های خودکار Step, Turn, Zig-Zag, Current و Convergence
- Evidence و Handoff مستقل

## اصلاح همراه

مسیر ثبت Evidence اجرای Phase 10.7 از `phase_10_6` به `phase_10_7` اصلاح شد. Evidence قبلی حذف یا دستکاری نمی‌شود؛ اجرای بعدی تنها در مسیر درست ثبت خواهد شد.
