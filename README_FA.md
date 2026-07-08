# AquaSkim-Sim

AquaSkim-Sim یک پروژهٔ آموزشی/مهندسی برای شبیه‌سازی ربات خودگردان کاتامارانِ جمع‌آوری زبالهٔ سطح آب است. پروژه یک روند کامل از مدل عددی کم‌سرعت 3-DOF در محیط حوضچهٔ آرام/سرپوشیده می‌سازد، شواهد مأموریت مرجع را تولید می‌کند، شکل‌ها و انیمیشن‌ها را انتخاب و کنترل کیفیت می‌کند، گزارش Word نهایی را می‌سازد و در پایان یک بستهٔ تحویل قابل ممیزی تولید می‌کند.

> **مرز اعتبار:** این پروژه فقط شواهد عددی و شبیه‌سازی‌شده تولید می‌کند. این پروژه گواهی دریایی، تست واقعی در دریا، اعتبارسنجی موج، اعتبارسنجی تخمین‌گر جریان روی سخت‌افزار یا راه‌اندازی سخت‌افزاری نیست.

## خروجی پروژه چیست؟

با اجرای کامل، فولدر جدید `outputs/` ساخته می‌شود و شامل این موارد خواهد بود:

- گزارش‌ها و جدول‌های CSV مأموریت مرجع،
- شکل‌های باکیفیت،
- GIF و MP4 تولیدشده از اجرای محلی،
- شواهد curated برای ارائه،
- Engineering Release Gate،
- گزارش Word نهایی،
- ZIP نهایی تحویل همراه با Manifest و SHA-256.

فایل‌های خروجی در Git قرار نمی‌گیرند، چون از روی سورس قابل بازتولید هستند.

## اجرای سریع با یک دستور در ویندوز

ابتدا Miniconda یا Mambaforge را نصب کنید. سپس repo را clone کنید و فقط این دستور را بزنید:

```bat
scripts\run_from_zero_to_delivery.bat
```

این اسکریپت به‌ترتیب:

1. محیط Conda با نام `aquaskim-sim` را می‌سازد یا فعال می‌کند،
2. package را به‌صورت editable نصب می‌کند،
3. خروجی‌های قبلی `outputs/` و `records/` را پاک می‌کند،
4. همهٔ evidenceها را از صفر تولید می‌کند،
5. گزارش Word را می‌سازد،
6. ZIP نهایی تحویل را می‌سازد.

خروجی نهایی مورد انتظار:

```text
outputs\deliverables\AquaSkim-Sim_Final_Delivery_v1.6.21.zip

> نکته: README و راهنمای اصلی فارسی است، اما گزارش Word نهایی که با اجرای پروژه ساخته می‌شود عمداً انگلیسی تولید می‌شود تا برای انتشار عمومی و ارزیابی بین‌المللی خواناتر باشد.
```

اجرای کامل ممکن است زمان‌بر باشد، چون شکل، GIF، MP4، جدول، گزارش Word و ZIP نهایی تولید می‌شود.

## نصب دستی محیط

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

سپس `config\report_metadata.json` را ویرایش کنید. این فایل توسط Git ignore می‌شود.

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

## عدم ادعاها

این repo صراحتاً ادعاهای زیر را ندارد:

- گواهی sea-trial،
- اعتبارسنجی پاسخ موج،
- اعتبارسنجی تخمین‌گر جریان روی سخت‌افزار،
- راه‌اندازی سخت‌افزاری.

## مجوز

MIT License. فایل `LICENSE` را ببینید.
