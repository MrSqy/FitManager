# Spor Salonu Yönetim Sistemi

Flask + PostgreSQL + HTML/CSS + Chart.js ile hazırlanmış spor salonu üyelik, ödeme ve personel yönetim paneli.

## Demo Bilgileri

- Email: `demo@example.com`
- Şifre: `change-me`

## PostgreSQL Kurulumu

Ubuntu için:

```bash
sudo apt install postgresql postgresql-contrib
```

Veritabanı ve uygulama kullanıcısı:

```bash
sudo -u postgres psql
```

```sql
CREATE USER spor_app WITH PASSWORD '<DB_PASSWORD>';
CREATE DATABASE spor_salonu_db OWNER spor_app;
GRANT ALL PRIVILEGES ON DATABASE spor_salonu_db TO spor_app;
\c spor_salonu_db
GRANT ALL ON SCHEMA public TO spor_app;
\q
```

Şema ve demo veri:

```bash
psql "postgresql://spor_app:<DB_PASSWORD>@localhost:5432/spor_salonu_db" -f schema.sql
psql "postgresql://spor_app:<DB_PASSWORD>@localhost:5432/spor_salonu_db" -f seed.sql
```

## Uygulama Çalıştırma

```bash
source .venv/bin/activate
pip install -r requirements.txt
flask --app app run --debug
```

Tarayıcı:

```text
http://127.0.0.1:5000
```

## Sunum Akışı

1. ER tasarımından gelen tabloları ve ilişkileri göster.
2. Dashboard metrikleri ve Chart.js grafiklerini aç.
3. Yeni sporcu ekle.
4. Profesyonel/VIP üyelik oluştururken zorunlu atama kuralını göster.
5. Ödeme ekleyip kalan borç değişimini göster.
6. Sorgular ekranında 7 gün içinde bitecek üyelikler, PT yükü ve aylık geliri göster.
7. Loglar ekranında login ve kritik işlem kayıtlarını göster.
