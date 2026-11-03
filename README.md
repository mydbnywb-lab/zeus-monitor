# ZEUS MONITOR

**ZEUS MONITOR** یک مینی‌اپ ربات تلگرام برای مانیتورینگ و مدیریت وضعیت کاربران و سرورهای متصل به پنل PasarGuard است.

## امکانات

- نمایش آمار کاربران
- نمایش وضعیت نودها
- نمایش مصرف ترافیک
- نمایش اطلاعات مانیتورینگ
- نمایش منابع سرور
- نمایش تاریخچه اختلالات ثبت‌شده
- رابط کاربری فارسی و انگلیسی
- پشتیبانی از تم روشن و تاریک
## پیش‌نیازها

- Ubuntu 22.04 یا جدیدتر
- دسترسی SSH با کاربر root
- دامنه متصل به IP سرور
- ربات تلگرام و توکن آن
- دسترسی API پنل PasarGuard

## نصب

ابتدا مخزن را دریافت کنید:

    apt update && apt install -y git
    git clone https://github.com/mydbnywb-lab/zeus-monitor.git
    cd zeus-monitor

سپس نصب‌کننده را اجرا کنید:

    chmod +x installer/zeus.sh
    bash installer/zeus.sh

## منوی نصب‌کننده

1. Install — نصب ZEUS MONITOR
2. Update — به‌روزرسانی پروژه
3. Uninstall (Full Remove) — حذف کامل ZEUS MONITOR
4. Edit Configuration — ویرایش تنظیمات
## تنظیمات

هنگام نصب، اطلاعات زیر از شما دریافت می‌شود:

| متغیر | توضیح |
|---|---|
| BOT_TOKEN | توکن ربات تلگرام |
| ADMIN_ID | شناسه عددی مدیر تلگرام |
| MINI_APP_DOMAIN | دامنه مینی‌اپ |
| PANEL_URL | آدرس پنل PasarGuard |
| PANEL_API_KEY | کلید API پنل |
| CHECK_INTERVAL | فاصله بررسی‌ها بر حسب ثانیه |

## ساخت ربات تلگرام

1. در تلگرام به @BotFather مراجعه کنید.
2. دستور `/newbot` را ارسال کنید.
3. ربات خود را بسازید و توکن آن را دریافت کنید.
4. شناسه عددی تلگرام مدیر را آماده کنید.

## دامنه و HTTPS

قبل از نصب، دامنه را به IP سرور متصل کنید و مطمئن شوید پورت‌های 80 و 443 باز هستند.

نصب‌کننده برای فعال‌سازی HTTPS از Certbot استفاده می‌کند.

## مدیریت سرویس‌ها

مشاهده وضعیت سرویس‌ها:

    systemctl status zeus-backend
    systemctl status zeus-bot

مشاهده گزارش Backend:

    journalctl -u zeus-backend -f

مشاهده گزارش Bot:

    journalctl -u zeus-bot -f

## امنیت

- فایل `.env` شامل اطلاعات محرمانه است و نباید منتشر شود.
- توکن ربات و کلید API را در اختیار دیگران قرار ندهید.
- قبل از تغییرات مهم، نسخه پشتیبان تهیه کنید.

## مخزن پروژه

https://github.com/mydbnywb-lab/zeus-monitor
