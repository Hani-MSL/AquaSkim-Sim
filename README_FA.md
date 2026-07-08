# AquaSkim-Sim

AquaSkim-Sim یک پروژهٔ آموزشی/مهندسی برای شبیه‌سازی ربات خودگردان کاتامارانِ جمع‌آوری زبالهٔ سطح آب است. پروژه یک روند کامل از مدل عددی کم‌سرعت 3-DOF در محیط حوضچهٔ آرام/سرپوشیده می‌سازد، شواهد مأموریت مرجع را تولید می‌کند، شکل‌ها و انیمیشن‌ها را انتخاب و کنترل کیفیت می‌کند، گزارش Word نهایی را می‌سازد و در پایان یک بستهٔ تحویل قابل ممیزی تولید می‌کند.

> **مرز اعتبار:** این پروژه فقط شواهد عددی و شبیه‌سازی‌شده تولید می‌کند. این پروژه گواهی دریایی، تست واقعی در دریا، اعتبارسنجی موج، اعتبارسنجی تخمین‌گر جریان روی سخت‌افزار یا راه‌اندازی سخت‌افزاری نیست.

## نتیجهٔ اجرای پروژه چیست؟

با اجرای کامل، فولدر جدید `outputs/` ساخته می‌شود و شامل این موارد خواهد بود:

- گزارش‌ها و جدول‌های CSV مأموریت مرجع،
- شکل‌های باکیفیت،
- GIF و MP4 تولیدشده از اجرای محلی،
- شواهد curated برای ارائه،
- Engineering Release Gate،
- گزارش Word نهایی به زبان انگلیسی،
- ZIP نهایی تحویل همراه با Manifest و SHA-256.

فایل‌های خروجی در Git قرار نمی‌گیرند، چون از روی سورس قابل بازتولید هستند.

## پیش‌نیازها

قبل از اجرای پروژه فقط این‌ها باید روی سیستم نصب باشند:

1. **Git** برای clone کردن repo،
2. **Miniconda** یا **Mambaforge** برای ساخت محیط Python،
3. ویندوز 10/11 برای مسیر اصلی پیشنهادی با فایل `.bat`.

اسکریپت پروژه خودش محیط Conda، کتابخانه‌های Python، نصب editable package، پاک‌سازی خروجی‌های قبلی و تولید خروجی‌های جدید را انجام می‌دهد. خودِ Miniconda/Git را نصب نمی‌کند؛ این دو ابزار باید قبلاً روی سیستم نصب باشند و `conda` باید در Command Prompt شناخته شود.

## اجرای سریع از صفر تا صد در ویندوز

یک Command Prompt تازه باز کنید و این دستورها را بزنید:

```bat
git clone https://github.com/Hani-MSL/AquaSkim-Sim.git
cd AquaSkim-Sim
scripts\run_from_zero_to_delivery.bat
```

این همان مسیر اصلی و پیشنهادی پروژه است. اسکریپت به‌ترتیب:

1. محیط Conda با نام `aquaskim-sim` را می‌سازد یا فعال می‌کند،
2. اگر محیط از قبل وجود داشته باشد، آن را از روی `environment.yml` به‌روزرسانی می‌کند،
3. همهٔ کتابخانه‌های لازم مثل `numpy`، `scipy`، `pandas`، `matplotlib`، `python-docx`، `imageio` و `ffmpeg` را از طریق Conda نصب/همگام می‌کند،
4. package را به‌صورت editable نصب می‌کند،
5. خروجی‌های قبلی `outputs/` و `records/` را پاک می‌کند،
6. همهٔ evidenceها را از صفر تولید می‌کند،
7. گزارش Word انگلیسی را می‌سازد،
8. ZIP نهایی تحویل را می‌سازد.

خروجی نهایی مورد انتظار:

```text
outputs\deliverables\AquaSkim-Sim_Final_Delivery_v1.6.21.zip
```

گزارش Word نهایی عمداً انگلیسی تولید می‌شود تا برای انتشار عمومی و ارزیابی بین‌المللی خواناتر باشد. README و راهنمای اصلی پروژه فارسی است.

اجرای کامل ممکن است زمان‌بر باشد، چون شکل، GIF، MP4، جدول، گزارش Word، QA manifest و ZIP نهایی تولید می‌شود.

## اجرای سریع در Linux/macOS

مسیر اصلی پروژه ویندوز است، اما یک اسکریپت shell هم برای کاربران Linux/macOS وجود دارد:

```bash
git clone https://github.com/Hani-MSL/AquaSkim-Sim.git
cd AquaSkim-Sim
bash scripts/run_from_zero_to_delivery.sh
```

این اسکریپت نیز Conda environment را می‌سازد یا به‌روزرسانی می‌کند و سپس rebuild کامل را اجرا می‌کند.

## نصب دستی محیط

اگر نخواستید از اسکریپت یک‌فرمانی استفاده کنید:

```bat
conda env create -f environment.yml
conda activate aquaskim-sim
python -m pip install --editable . --no-build-isolation --no-deps
```

سپس یکی از این دو دستور را اجرا کنید:

```bat
python -m aquaskim.rebuild_from_zero
```

یا:

```bat
python -m aquaskim rebuild-from-zero
```

## دیدن مراحل بدون تولید خروجی

```bat
python -m aquaskim.rebuild_from_zero --list-steps
```

## ساختار repo

```text
src/aquaskim/      کدهای اصلی شبیه‌سازی و گزارش‌سازی
config/           تنظیمات مدل مرجع و visualization
tests/            تست‌های regression و contract
scripts/          اسکریپت‌های اجرای ویندوز و shell
docs/             مستندات فازها، incidentها و راهنمای GitHub
outputs/          خروجی تولیدشدهٔ محلی؛ در Git ذخیره نمی‌شود
records/          رکوردهای اجرای محلی؛ در Git ذخیره نمی‌شود
```

## اجرای تست‌ها

```bat
conda activate aquaskim-sim
python -m pytest -q
```

در clone تمیز، تست‌هایی که به خروجی‌های تولیدشده نیاز دارند تا قبل از اجرای کامل skip می‌شوند. بعد از rebuild کامل، تست‌های delivery package هم باید pass شوند.

## metadata گزارش Word

در repo عمومی فقط فایل template وجود دارد:

```text
config/report_metadata.template.json
```

برای قرار دادن اطلاعات شخصی/درسی در Word محلی، این فایل را کپی کنید:

```bat
copy config\report_metadata.template.json config\report_metadata.json
```

سپس `config\report_metadata.json` را ویرایش کنید. این فایل توسط Git ignore می‌شود و به repo عمومی اضافه نمی‌شود.

## کنترل بستهٔ نهایی

پس از اجرای موفق، این فایل‌ها را بررسی کنید:

```text
outputs\deliverables\FINAL_DELIVERY_PACKAGE_MANIFEST.json
outputs\deliverables\FINAL_DELIVERY_SHA256SUMS.txt
outputs\deliverables\final_delivery_package_audit.md
```

وضعیت نهایی معتبر باید این باشد:

```text
DELIVERY_PACKAGE_READY
```

## نکته‌های مهم اجرا

- اگر `conda` در Command Prompt شناخته نشد، Miniconda/Mambaforge را نصب کنید و یک Command Prompt جدید باز کنید.
- اگر اینترنت قطع باشد، ساخت محیط برای اولین بار ممکن است انجام نشود، چون Conda باید packageها را دانلود کند.
- خروجی‌ها عمداً commit نشده‌اند و با اجرای پروژه دوباره ساخته می‌شوند.
- اگر محیط `aquaskim-sim` از قبل وجود داشته باشد، اسکریپت آن را از روی `environment.yml` همگام می‌کند.

## عدم ادعاها

این repo صراحتاً ادعاهای زیر را ندارد:

- گواهی sea-trial،
- اعتبارسنجی پاسخ موج،
- اعتبارسنجی تخمین‌گر جریان روی سخت‌افزار،
- راه‌اندازی سخت‌افزاری.

## مجوز

MIT License. فایل `LICENSE` را ببینید.
