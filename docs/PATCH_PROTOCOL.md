# پروتکل اعمال Patch

## اصل اصلی
هر Patch جدید یک ZIP است که داخل آن از پوشهٔ `AquaSkim-Sim` شروع می‌شود. بنابراین با Extract کردن آن در `C:\Projects`، فایل‌ها دقیقاً در مسیر درست قرار می‌گیرند.

## روش پیشنهادی با Explorer
1. پروژه را ببندید یا اجرای Python را متوقف کنید.
2. از `C:\Projects\AquaSkim-Sim` یک نسخهٔ پشتیبان بسازید.
3. فایل Patch ZIP را در `C:\Projects` Extract کنید.
4. اگر Windows پرسید فایل‌های هم‌نام جایگزین شوند، گزینهٔ Replace را انتخاب کنید.
5. در CMD، `python -m pytest -q` را اجرا کنید.

## روش پیشنهادی با CMD
فرض کنید ZIP در Downloads قرار دارد:

```bat
cd /d C:\Projects
tar -xf "%USERPROFILE%\Downloads\AquaSkim-Sim_PATCH_NAME.zip" -C C:\Projects
```

اگر ابزار `tar` روی Windows در دسترس نبود، از Explorer استفاده کنید.

## نکته
Patchها به‌صورت افزایشی هستند؛ بنابراین هر Patch فقط فایل‌های جدید یا تغییرکرده را دارد، نه لزوماً همهٔ فایل‌های قبلی را.
