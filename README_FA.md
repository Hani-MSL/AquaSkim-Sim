# AquaSkim-Sim

**AquaSkim-Sim** یک پروژهٔ شبیه‌سازی مهندسی برای طراحی و ارزیابی یک ربات سطحی خودگردان از نوع کاتاماران است که در محیط آب آرام، زباله‌های شناور را جمع‌آوری می‌کند. تمرکز پروژه روی طراحی مکانیکی، محاسبات شناوری و پایداری، مدل دینامیکی کم‌سرعت، کنترل، مأموریت خودگردان و تولید خروجی‌های بصری قابل ارائه است.

> **مرز اعتبار:** خروجی‌های این repository حاصل مدل عددی و شبیه‌سازی‌شده هستند. این پروژه ادعای تست واقعی در دریا، گواهی عملکرد دریایی، اعتبارسنجی پاسخ موج، اعتبارسنجی تخمین‌گر جریان روی سخت‌افزار یا راه‌اندازی سخت‌افزاری ندارد.

<p align="center">
  <img src="assets/aquaskim_system_overview.svg" width="31%" alt="AquaSkim system overview" />
  <img src="assets/aquaskim_mission_evidence.svg" width="31%" alt="Reference mission evidence" />
  <img src="assets/aquaskim_validation_summary.svg" width="31%" alt="Validation summary" />
</p>

## خروجی اجرای کامل

با اجرای کامل پروژه، فولدر `outputs/` به‌صورت محلی ساخته می‌شود و شامل این موارد خواهد بود:

- گزارش‌ها و جدول‌های CSV مأموریت مرجع،
- شکل‌های مهندسی و نمودارهای طراحی،
- GIF و MP4 تولیدشده از replay داده‌های شبیه‌سازی،
- contact sheetهای شواهد بصری،
- گزارش Word نهایی به زبان انگلیسی،
- بستهٔ نهایی تحویل همراه با Manifest و SHA-256.

خروجی‌ها در Git ذخیره نمی‌شوند، چون با اجرای پروژه از روی سورس قابل بازتولید هستند.

## پیش‌نیازها

قبل از اجرا فقط این ابزارها باید روی سیستم نصب باشند:

1. **Git** برای clone کردن repository،
2. **Miniconda** یا **Mambaforge** برای ساخت محیط Python،
3. ویندوز 10/11 برای مسیر اصلی پیشنهادی با فایل `.bat`.

اسکریپت پروژه محیط Conda، نصب کتابخانه‌ها، نصب editable package، پاک‌سازی خروجی‌های قبلی و تولید خروجی‌های جدید را انجام می‌دهد. خودِ Git و Conda را نصب نمی‌کند؛ این دو ابزار باید قبلاً روی سیستم نصب باشند و دستور `conda` در Command Prompt شناخته شود.

## اجرای سریع از صفر تا صد در ویندوز

یک Command Prompt تازه باز کنید و این دستورها را اجرا کنید:

```bat
git clone https://github.com/Hani-MSL/AquaSkim-Sim.git
cd AquaSkim-Sim
scripts\run_from_zero_to_delivery.bat
```

اسکریپت به‌ترتیب:

1. محیط Conda با نام `aquaskim-sim` را می‌سازد یا فعال می‌کند،
2. اگر محیط از قبل وجود داشته باشد آن را با `environment.yml` به‌روزرسانی می‌کند،
3. package را به‌صورت editable نصب می‌کند،
4. خروجی‌های قبلی `outputs/` و `records/` را پاک می‌کند،
5. تمام مراحل شبیه‌سازی و تولید evidence را اجرا می‌کند،
6. گزارش Word انگلیسی را تولید می‌کند،
7. بستهٔ نهایی تحویل را می‌سازد.

خروجی نهایی مورد انتظار:

```text
outputs\deliverables\AquaSkim-Sim_Final_Delivery_v1.6.21.zip
```

## اجرای Linux/macOS

در سیستم‌های Linux یا macOS نیز اسکریپت shell وجود دارد:

```bash
git clone https://github.com/Hani-MSL/AquaSkim-Sim.git
cd AquaSkim-Sim
bash scripts/run_from_zero_to_delivery.sh
```

مسیر اصلی ارزیابی‌شده پروژه ویندوز است، اما اسکریپت shell نیز محیط Conda را می‌سازد یا update می‌کند و همان rebuild کامل را اجرا می‌کند.

## ساختار repository

```text
src/aquaskim/      کدهای اصلی مدل، شبیه‌سازی، کنترل، گزارش‌سازی و بسته‌بندی
config/           تنظیمات نسخه‌دار مدل مرجع و visualization
tests/            تست‌های regression و contract
scripts/          entrypointهای اجرایی نهایی
docs/             مستندات طراحی، فرضیات و بازتولیدپذیری
assets/           تصویرهای سبک برای معرفی پروژه در README
outputs/          خروجی تولیدشدهٔ محلی؛ در Git ذخیره نمی‌شود
records/          رکوردهای اجرای محلی؛ در Git ذخیره نمی‌شود
```

## گزارش Word

گزارش Word نهایی به زبان انگلیسی ساخته می‌شود. اگر کاربر بخواهد اطلاعات شخصی/درسی خود را وارد گزارش کند، می‌تواند فایل template را کپی کند:

```bat
copy config\report_metadata.template.json config\report_metadata.json
```

سپس `config\report_metadata.json` را ویرایش کند. این فایل محلی در Git ذخیره نمی‌شود.

## اجرای تست‌ها

```bat
conda activate aquaskim-sim
python -m pytest -q
```

در clone تمیز، تست‌هایی که به خروجی‌های تولیدشده نیاز دارند تا قبل از اجرای کامل skip می‌شوند. بعد از rebuild کامل، تست‌های delivery package نیز باید pass شوند.

## ادعاهای خارج از محدوده

این پروژه ادعاهای زیر را ندارد:

- گواهی sea-trial،
- اعتبارسنجی پاسخ موج،
- اعتبارسنجی تخمین‌گر جریان روی سخت‌افزار،
- راه‌اندازی سخت‌افزاری.

## مجوز

MIT License. فایل `LICENSE` را ببینید.
