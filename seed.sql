BEGIN;

INSERT INTO plan (plan_id, plan_adi, aylik_ucret) VALUES
    (1, 'Temel', 500.00),
    (2, 'Profesyonel', 1500.00),
    (3, 'VIP', 2500.00);

INSERT INTO uyelik_suresi (sure_id, ay, katsayi) VALUES
    (1, 1, 1.00),
    (2, 3, 2.50),
    (3, 6, 5.00),
    (4, 12, 9.00);

INSERT INTO calisan (calisan_id, ad, soyad, telefon, maas, mesai_baslangic, mesai_bitis, rol) VALUES
    (1, 'Mert', 'Kaya', '05000000001', 32000.00, '09:00', '18:00', 'PT'),
    (2, 'Ece', 'Arslan', '05000000002', 34000.00, '10:00', '19:00', 'PT'),
    (3, 'Can', 'Yilmaz', '05000000003', 30000.00, '08:00', '17:00', 'PT'),
    (4, 'Derya', 'Aydin', '05000000004', 36000.00, '09:00', '18:00', 'DIYETISYEN'),
    (5, 'Selin', 'Demir', '05000000005', 35500.00, '10:00', '19:00', 'DIYETISYEN'),
    (6, 'Burak', 'Celik', '05000000006', 34500.00, '08:00', '17:00', 'DIYETISYEN'),
    (7, 'Ayse', 'Kurt', '05000000007', 25000.00, '09:00', '18:00', 'DIGER'),
    (8, 'Emre', 'Sahin', '05000000008', 24500.00, '12:00', '21:00', 'DIGER');

INSERT INTO sporcu (sporcu_id, ad, soyad, telefon, kayit_tarihi, aktif_mi) VALUES
    (1, 'Ali', 'Yildiz', '05320000001', CURRENT_DATE - INTERVAL '80 days', TRUE),
    (2, 'Zeynep', 'Koc', '05320000002', CURRENT_DATE - INTERVAL '45 days', TRUE),
    (3, 'Deniz', 'Aksoy', '05320000003', CURRENT_DATE - INTERVAL '18 days', TRUE),
    (4, 'Elif', 'Gunes', '05320000004', CURRENT_DATE - INTERVAL '200 days', TRUE),
    (5, 'Kerem', 'Oz', '05320000005', CURRENT_DATE - INTERVAL '390 days', TRUE),
    (6, 'Mina', 'Tas', '05320000006', CURRENT_DATE - INTERVAL '20 days', TRUE),
    (7, 'Baris', 'Ucar', '05320000007', CURRENT_DATE - INTERVAL '5 days', TRUE);

INSERT INTO uyelik (uyelik_id, sporcu_id, plan_id, sure_id, baslangic_tarihi, bitis_tarihi, tutar, durum) VALUES
    (1, 1, 1, 2, CURRENT_DATE - INTERVAL '80 days', CURRENT_DATE + INTERVAL '10 days', 1, 'AKTIF'),
    (2, 2, 2, 1, CURRENT_DATE - INTERVAL '24 days', CURRENT_DATE + INTERVAL '6 days', 1, 'AKTIF'),
    (3, 3, 3, 3, CURRENT_DATE - INTERVAL '18 days', CURRENT_DATE + INTERVAL '162 days', 1, 'AKTIF'),
    (4, 4, 2, 2, CURRENT_DATE - INTERVAL '84 days', CURRENT_DATE + INTERVAL '6 days', 1, 'AKTIF'),
    (5, 5, 3, 4, CURRENT_DATE - INTERVAL '360 days', CURRENT_DATE + INTERVAL '5 days', 1, 'AKTIF'),
    (6, 6, 1, 1, CURRENT_DATE - INTERVAL '45 days', CURRENT_DATE - INTERVAL '15 days', 1, 'BITTI'),
    (7, 7, 1, 1, CURRENT_DATE - INTERVAL '5 days', CURRENT_DATE + INTERVAL '25 days', 1, 'AKTIF'),
    (8, 6, 1, 1, CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days', 1, 'AKTIF');

INSERT INTO sporcu_atama (uyelik_id, diyetisyen_id, pt_id, atama_tarihi) VALUES
    (2, 4, NULL, CURRENT_DATE - INTERVAL '24 days'),
    (3, 5, 1, CURRENT_DATE - INTERVAL '18 days'),
    (4, 6, NULL, CURRENT_DATE - INTERVAL '84 days'),
    (5, 4, 2, CURRENT_DATE - INTERVAL '360 days');

INSERT INTO odeme (uyelik_id, tutar, odeme_tarihi, odeme_yontemi) VALUES
    (1, 750.00, CURRENT_DATE - INTERVAL '75 days', 'KART'),
    (1, 500.00, CURRENT_DATE - INTERVAL '45 days', 'NAKIT'),
    (2, 1000.00, CURRENT_DATE - INTERVAL '24 days', 'KART'),
    (3, 7500.00, CURRENT_DATE - INTERVAL '18 days', 'HAVALE'),
    (3, 2500.00, CURRENT_DATE - INTERVAL '3 days', 'KART'),
    (4, 3750.00, CURRENT_DATE - INTERVAL '80 days', 'KART'),
    (5, 15000.00, CURRENT_DATE - INTERVAL '350 days', 'HAVALE'),
    (7, 500.00, CURRENT_DATE - INTERVAL '5 days', 'NAKIT');

INSERT INTO yonetici (yonetici_id, ad_soyad, email, sifre_hash, aktif_mi, olusturma_tarihi) VALUES
    (1, 'Baran Demir', 'admin@spor.local', 'scrypt:32768:8:1$eQ7F1LNvxn6AcXxF$9fee270e7eea77cadafd4043b1e9b2deb1e36aa6d2961bb16c5037585052e30377d52b2433429598b1f126ea1639799fe6698e48e1c3681de55a06726aab8065', TRUE, CURRENT_TIMESTAMP);

INSERT INTO yonetici_log (yonetici_id, olay_tipi, detay, ip_adresi, user_agent, olay_zamani) VALUES
    (1, 'SEED', 'Demo verisi yüklendi', '127.0.0.1', 'seed.sql', CURRENT_TIMESTAMP);

-- Ek demo verisi (grafikleri doldurmak için)
INSERT INTO calisan (calisan_id, ad, soyad, telefon, maas, mesai_baslangic, mesai_bitis, rol) VALUES
    (9, 'Onur', 'Sen', '05000000009', 33000.00, '09:00', '18:00', 'PT'),
    (10, 'Pelin', 'Ak', '05000000010', 35000.00, '10:00', '19:00', 'DIYETISYEN');

INSERT INTO sporcu (sporcu_id, ad, soyad, telefon, kayit_tarihi, aktif_mi) VALUES
    (8, 'Ahmet', 'Demir', '05320000008', CURRENT_DATE - INTERVAL '30 days', TRUE),
    (9, 'Buse', 'Sahin', '05320000009', CURRENT_DATE - INTERVAL '20 days', TRUE),
    (10, 'Cem', 'Yildirim', '05320000010', CURRENT_DATE - INTERVAL '10 days', TRUE),
    (11, 'Dilara', 'Kaya', '05320000011', CURRENT_DATE - INTERVAL '40 days', TRUE),
    (12, 'Efe', 'Aslan', '05320000012', CURRENT_DATE - INTERVAL '60 days', TRUE),
    (13, 'Gizem', 'Polat', '05320000013', CURRENT_DATE - INTERVAL '15 days', TRUE),
    (14, 'Hakan', 'Eren', '05320000014', CURRENT_DATE - INTERVAL '25 days', TRUE),
    (15, 'Irem', 'Coban', '05320000015', CURRENT_DATE - INTERVAL '35 days', TRUE),
    (16, 'Kaan', 'Ozturk', '05320000016', CURRENT_DATE - INTERVAL '12 days', TRUE);

INSERT INTO uyelik (uyelik_id, sporcu_id, plan_id, sure_id, baslangic_tarihi, bitis_tarihi, tutar, durum) VALUES
    (9, 8, 2, 2, CURRENT_DATE - INTERVAL '30 days', CURRENT_DATE + INTERVAL '60 days', 1, 'AKTIF'),
    (10, 9, 3, 3, CURRENT_DATE - INTERVAL '20 days', CURRENT_DATE + INTERVAL '160 days', 1, 'AKTIF'),
    (11, 10, 1, 1, CURRENT_DATE - INTERVAL '10 days', CURRENT_DATE + INTERVAL '20 days', 1, 'AKTIF'),
    (12, 11, 2, 3, CURRENT_DATE - INTERVAL '40 days', CURRENT_DATE + INTERVAL '140 days', 1, 'AKTIF'),
    (13, 12, 3, 4, CURRENT_DATE - INTERVAL '60 days', CURRENT_DATE + INTERVAL '300 days', 1, 'AKTIF'),
    (14, 13, 1, 2, CURRENT_DATE - INTERVAL '15 days', CURRENT_DATE + INTERVAL '75 days', 1, 'AKTIF'),
    (15, 14, 2, 2, CURRENT_DATE - INTERVAL '25 days', CURRENT_DATE + INTERVAL '65 days', 1, 'AKTIF'),
    (16, 15, 3, 3, CURRENT_DATE - INTERVAL '35 days', CURRENT_DATE + INTERVAL '145 days', 1, 'AKTIF'),
    (17, 16, 1, 2, CURRENT_DATE - INTERVAL '12 days', CURRENT_DATE + INTERVAL '50 days', 1, 'IPTAL');

INSERT INTO sporcu_atama (uyelik_id, diyetisyen_id, pt_id, atama_tarihi) VALUES
    (9, 4, NULL, CURRENT_DATE - INTERVAL '30 days'),
    (10, 5, 1, CURRENT_DATE - INTERVAL '20 days'),
    (12, 6, NULL, CURRENT_DATE - INTERVAL '40 days'),
    (13, 10, 2, CURRENT_DATE - INTERVAL '60 days'),
    (15, 10, NULL, CURRENT_DATE - INTERVAL '25 days'),
    (16, 6, 9, CURRENT_DATE - INTERVAL '35 days');

INSERT INTO odeme (uyelik_id, tutar, odeme_tarihi, odeme_yontemi) VALUES
    (13, 13500.00, CURRENT_DATE - INTERVAL '150 days', 'HAVALE'),
    (9, 2250.00, CURRENT_DATE - INTERVAL '140 days', 'HAVALE'),
    (10, 7500.00, CURRENT_DATE - INTERVAL '110 days', 'KART'),
    (12, 4500.00, CURRENT_DATE - INTERVAL '80 days', 'HAVALE'),
    (14, 750.00, CURRENT_DATE - INTERVAL '50 days', 'KART'),
    (16, 7500.00, CURRENT_DATE - INTERVAL '35 days', 'HAVALE'),
    (15, 4500.00, CURRENT_DATE - INTERVAL '25 days', 'KART'),
    (9, 2250.00, CURRENT_DATE - INTERVAL '20 days', 'KART'),
    (10, 7500.00, CURRENT_DATE - INTERVAL '15 days', 'HAVALE'),
    (12, 4500.00, CURRENT_DATE - INTERVAL '10 days', 'KART'),
    (11, 500.00, CURRENT_DATE - INTERVAL '2 days', 'NAKIT');

SELECT setval('calisan_calisan_id_seq', (SELECT MAX(calisan_id) FROM calisan));
SELECT setval('sporcu_sporcu_id_seq', (SELECT MAX(sporcu_id) FROM sporcu));
SELECT setval('uyelik_uyelik_id_seq', (SELECT MAX(uyelik_id) FROM uyelik));
SELECT setval('yonetici_yonetici_id_seq', (SELECT MAX(yonetici_id) FROM yonetici));

COMMIT;
