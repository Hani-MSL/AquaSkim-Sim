# فرمان‌های Windows CMD

## بررسی آماده‌بودن Miniconda

```bat
where conda
conda --version
```

## ساخت محیط

```bat
cd /d C:\Projects\AquaSkim-Sim
conda env create -f environment.yml
conda activate aquaskim-sim
python -m pip install -e .
```

## کنترل سلامت پروژه

```bat
python -m aquaskim.cli preflight
python -m pytest -q
```

## اجرای اسکریپت یک‌مرحله‌ای

```bat
cd /d C:\Projects\AquaSkim-Sim
scripts\create_environment.bat
```

## باز کردن پروژه در VS Code

```bat
code .
```

> در VS Code، Interpreter را روی محیط `aquaskim-sim` انتخاب کنید.
