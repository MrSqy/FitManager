DROP TABLE IF EXISTS yonetici_log CASCADE;
DROP TABLE IF EXISTS odeme CASCADE;
DROP TABLE IF EXISTS sporcu_atama CASCADE;
DROP TABLE IF EXISTS uyelik CASCADE;
DROP TABLE IF EXISTS uyelik_suresi CASCADE;
DROP TABLE IF EXISTS plan CASCADE;
DROP TABLE IF EXISTS calisan CASCADE;
DROP TABLE IF EXISTS sporcu CASCADE;
DROP TABLE IF EXISTS yonetici CASCADE;

CREATE TABLE sporcu (
    sporcu_id BIGSERIAL PRIMARY KEY,
    ad VARCHAR(50) NOT NULL,
    soyad VARCHAR(50) NOT NULL,
    telefon VARCHAR(20) NOT NULL UNIQUE,
    kayit_tarihi DATE NOT NULL DEFAULT CURRENT_DATE,
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE calisan (
    calisan_id BIGSERIAL PRIMARY KEY,
    ad VARCHAR(50) NOT NULL,
    soyad VARCHAR(50) NOT NULL,
    telefon VARCHAR(20) NOT NULL UNIQUE,
    maas NUMERIC(10,2) NOT NULL CHECK (maas >= 0),
    mesai_baslangic TIME NOT NULL,
    mesai_bitis TIME NOT NULL,
    rol VARCHAR(20) NOT NULL CHECK (rol IN ('PT', 'DIYETISYEN', 'DIGER')),
    CHECK (mesai_bitis > mesai_baslangic)
);

CREATE TABLE plan (
    plan_id SMALLINT PRIMARY KEY,
    plan_adi VARCHAR(20) NOT NULL UNIQUE CHECK (plan_adi IN ('Temel', 'Profesyonel', 'VIP')),
    aylik_ucret NUMERIC(10,2) NOT NULL CHECK (aylik_ucret > 0)
);

CREATE TABLE uyelik_suresi (
    sure_id SMALLINT PRIMARY KEY,
    ay SMALLINT NOT NULL UNIQUE CHECK (ay IN (1, 3, 6, 12)),
    katsayi NUMERIC(4,2) NOT NULL CHECK (katsayi > 0)
);

CREATE TABLE uyelik (
    uyelik_id BIGSERIAL PRIMARY KEY,
    sporcu_id BIGINT NOT NULL REFERENCES sporcu(sporcu_id) ON DELETE RESTRICT,
    plan_id SMALLINT NOT NULL REFERENCES plan(plan_id) ON DELETE RESTRICT,
    sure_id SMALLINT NOT NULL REFERENCES uyelik_suresi(sure_id) ON DELETE RESTRICT,
    baslangic_tarihi DATE NOT NULL,
    bitis_tarihi DATE NOT NULL,
    tutar NUMERIC(10,2) NOT NULL CHECK (tutar > 0),
    durum VARCHAR(10) NOT NULL CHECK (durum IN ('AKTIF', 'BITTI', 'IPTAL')),
    CHECK (bitis_tarihi > baslangic_tarihi)
);

CREATE UNIQUE INDEX uq_sporcu_tek_aktif_uyelik
    ON uyelik(sporcu_id)
    WHERE durum = 'AKTIF';

CREATE INDEX idx_uyelik_bitis_tarihi ON uyelik(bitis_tarihi);
CREATE INDEX idx_uyelik_durum ON uyelik(durum);

CREATE TABLE sporcu_atama (
    atama_id BIGSERIAL PRIMARY KEY,
    uyelik_id BIGINT NOT NULL UNIQUE REFERENCES uyelik(uyelik_id) ON DELETE CASCADE,
    diyetisyen_id BIGINT REFERENCES calisan(calisan_id) ON DELETE RESTRICT,
    pt_id BIGINT REFERENCES calisan(calisan_id) ON DELETE RESTRICT,
    atama_tarihi DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE odeme (
    odeme_id BIGSERIAL PRIMARY KEY,
    uyelik_id BIGINT REFERENCES uyelik(uyelik_id) ON DELETE SET NULL,
    silinen_uye_ad VARCHAR(120),
    tutar NUMERIC(10,2) NOT NULL CHECK (tutar > 0),
    odeme_tarihi DATE NOT NULL DEFAULT CURRENT_DATE,
    odeme_yontemi VARCHAR(15) NOT NULL CHECK (odeme_yontemi IN ('NAKIT', 'KART', 'HAVALE'))
);

CREATE INDEX idx_odeme_tarih ON odeme(odeme_tarihi);
CREATE INDEX idx_odeme_uyelik ON odeme(uyelik_id);

CREATE TABLE yonetici (
    yonetici_id BIGSERIAL PRIMARY KEY,
    ad_soyad VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    sifre_hash TEXT NOT NULL,
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,
    olusturma_tarihi TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    son_giris_tarihi TIMESTAMP
);

CREATE TABLE yonetici_log (
    log_id BIGSERIAL PRIMARY KEY,
    yonetici_id BIGINT REFERENCES yonetici(yonetici_id) ON DELETE SET NULL,
    olay_tipi VARCHAR(40) NOT NULL,
    detay TEXT,
    ip_adresi VARCHAR(45),
    user_agent TEXT,
    olay_zamani TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_yonetici_log_zaman ON yonetici_log(olay_zamani DESC);
CREATE INDEX idx_yonetici_log_tip ON yonetici_log(olay_tipi);

CREATE OR REPLACE FUNCTION trg_uyelik_tutari_hesapla()
RETURNS TRIGGER AS $$
DECLARE
    hesaplanan_tutar NUMERIC(10,2);
BEGIN
    SELECT p.aylik_ucret * us.katsayi
      INTO hesaplanan_tutar
      FROM plan p
      JOIN uyelik_suresi us ON us.sure_id = NEW.sure_id
     WHERE p.plan_id = NEW.plan_id;

    IF hesaplanan_tutar IS NULL THEN
        RAISE EXCEPTION 'Plan veya üyelik süresi bulunamadı.';
    END IF;

    NEW.tutar := hesaplanan_tutar;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER uyelik_tutari_hesapla
BEFORE INSERT OR UPDATE OF plan_id, sure_id, tutar ON uyelik
FOR EACH ROW
EXECUTE FUNCTION trg_uyelik_tutari_hesapla();

CREATE OR REPLACE FUNCTION trg_sporcu_atama_kontrol()
RETURNS TRIGGER AS $$
DECLARE
    secilen_plan VARCHAR(20);
    pt_rol VARCHAR(20);
    diyetisyen_rol VARCHAR(20);
BEGIN
    SELECT p.plan_adi
      INTO secilen_plan
      FROM uyelik u
      JOIN plan p ON p.plan_id = u.plan_id
     WHERE u.uyelik_id = NEW.uyelik_id;

    IF secilen_plan IS NULL THEN
        RAISE EXCEPTION 'Atama için üyelik bulunamadı.';
    END IF;

    IF secilen_plan IN ('Profesyonel', 'VIP') AND NEW.diyetisyen_id IS NULL THEN
        RAISE EXCEPTION '% plan için diyetisyen zorunludur.', secilen_plan;
    END IF;

    IF secilen_plan = 'VIP' AND NEW.pt_id IS NULL THEN
        RAISE EXCEPTION 'VIP plan için PT zorunludur.';
    END IF;

    IF NEW.diyetisyen_id IS NOT NULL THEN
        SELECT rol INTO diyetisyen_rol FROM calisan WHERE calisan_id = NEW.diyetisyen_id;
        IF diyetisyen_rol <> 'DIYETISYEN' THEN
            RAISE EXCEPTION 'Seçilen diyetisyen_id çalışanının rolü DIYETISYEN olmalıdır.';
        END IF;
    END IF;

    IF NEW.pt_id IS NOT NULL THEN
        SELECT rol INTO pt_rol FROM calisan WHERE calisan_id = NEW.pt_id;
        IF pt_rol <> 'PT' THEN
            RAISE EXCEPTION 'Seçilen pt_id çalışanının rolü PT olmalıdır.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER sporcu_atama_kontrol
BEFORE INSERT OR UPDATE ON sporcu_atama
FOR EACH ROW
EXECUTE FUNCTION trg_sporcu_atama_kontrol();

CREATE OR REPLACE FUNCTION trg_uyelik_zorunlu_atama_kontrol()
RETURNS TRIGGER AS $$
DECLARE
    secilen_plan VARCHAR(20);
    atama_sayisi INTEGER;
BEGIN
    SELECT plan_adi INTO secilen_plan FROM plan WHERE plan_id = NEW.plan_id;

    IF secilen_plan = 'Profesyonel' THEN
        SELECT COUNT(*) INTO atama_sayisi
          FROM sporcu_atama
         WHERE uyelik_id = NEW.uyelik_id
           AND diyetisyen_id IS NOT NULL;

        IF atama_sayisi = 0 THEN
            RAISE EXCEPTION 'Profesyonel plan için diyetisyen ataması zorunludur.';
        END IF;
    ELSIF secilen_plan = 'VIP' THEN
        SELECT COUNT(*) INTO atama_sayisi
          FROM sporcu_atama
         WHERE uyelik_id = NEW.uyelik_id
           AND diyetisyen_id IS NOT NULL
           AND pt_id IS NOT NULL;

        IF atama_sayisi = 0 THEN
            RAISE EXCEPTION 'VIP plan için diyetisyen ve PT ataması zorunludur.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER uyelik_zorunlu_atama_kontrol
AFTER INSERT OR UPDATE OF plan_id, durum ON uyelik
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION trg_uyelik_zorunlu_atama_kontrol();
