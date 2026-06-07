# Bağcıbaşı Logistics AI Platform - Son Kurulum

Bu klasör artık PostgreSQL + FastAPI + Next.js profesyonel sürümdür.

## 1. İlk Kez Kurulum

Önce şu dosyayı çalıştır:

```text
01_YONETICI_OLARAK_WSL_KUR.bat
```

Bu dosya Windows için gerekli WSL ve sanallaştırma özelliklerini açar. Windows UAC sorarsa `Evet` de.

İşlem sonunda bilgisayar yeniden başlatma isterse mutlaka yeniden başlat.

## 2. Platformu Başlatma

Yeniden başlattıktan sonra şu dosyayı çalıştır:

```text
02_PLATFORMU_BASLAT.bat
```

Bu dosya Docker Desktop'ı açar, Docker motorunu bekler ve ardından şu sistemi ayağa kaldırır:

- PostgreSQL
- FastAPI backend
- Next.js frontend

## 3. Kullanım Adresleri

Platform açılınca:

- Yönetici paneli: http://localhost:3000
- API dokümantasyonu: http://localhost:8000/docs

Adresleri hızlı açmak için:

```text
03_PLATFORM_ADRESLERI_AC.bat
```

## 4. İçerik

- Operasyon dashboard'u
- Akıllı sevkiyat oluşturma
- Otomatik araç seçimi
- Maliyet, fatura, kâr ve kâr marjı hesabı
- CO2 ve ESG özeti
- Finans ve 15 gün nakit akış tahmini
- AI operasyon asistanı
- PostgreSQL veri modeli
- FastAPI servis katmanı
- Next.js arayüz

