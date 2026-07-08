# Patch 10 Execution Runbook — Final Report and Delivery

## هدف
Patch 10 لایهٔ نهایی تحویل AquaSkim-Sim است. این Patch از خروجی‌ها و نتایج ثبت‌شدهٔ Phase 02 تا Phase 09 استفاده می‌کند تا یک گزارش Word قابل ویرایش و یک بستهٔ تحویل کامل و قابل بازتولید بسازد.

## ورودی‌های لازم

- خروجی موفق Phase 02 تا Phase 09
- محیط Conda با نام `aquaskim-sim`
- فایل `config/report_metadata.json`
- فایل‌های JSON/CSV/PNG/SVG تولیدشده در `outputs/`

## مسیر اجرایی

```text
config/report_metadata.json
+ outputs/logs/phase02...phase09 summary files
+ selected figures and tables
→ Phase 10 report generator
→ AquaSkim-Sim_Final_Report.docx
→ report manifest + quality inventory
→ AquaSkim-Sim_Submission.zip
→ checksum manifest
→ Phase 10 Evidence + Handoff
```

## فرمان استاندارد

```bat
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_10.bat
```

## اطلاعات جلد

پیش از اجرای نهایی، این فیلدها را در فایل زیر تکمیل کنید:

```text
config/report_metadata.json
```

فیلدها:

- `student_name`
- `student_id`
- `course`
- `instructor`
- `institution`
- `semester`

## کنترل‌های موفقیت

اجرای موفق باید موارد زیر را ایجاد کند:

```text
outputs/reports/AquaSkim-Sim_Final_Report.docx
outputs/reports/phase10_report_build_manifest.json
outputs/deliverables/AquaSkim-Sim_Submission.zip
outputs/deliverables/AquaSkim-Sim_SHA256SUMS.txt
outputs/deliverables/AquaSkim-Sim_Submission_manifest.json
records/handoffs/PHASE10_LATEST_HANDOFF.md
```

## محدودیت‌های علمی

Phase 10 هیچ مدل جدیدی اضافه نمی‌کند. تمام محدودیت‌های صریح Phase 02 تا Phase 09، از جمله دامنهٔ اعتبار جریان در آزمون کنترل، به گزارش نهایی منتقل می‌شوند.
