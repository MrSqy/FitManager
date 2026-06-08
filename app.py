import calendar
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

import psycopg
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from db import fetch_all, fetch_one, get_conn, transaction


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("yonetici_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


@app.context_processor
def inject_layout_data():
    return {
        "aktif_yonetici": session.get("yonetici_ad"),
        "current_year": datetime.now().year,
    }


@app.template_filter("money")
def money(value):
    if value is None:
        value = 0
    return f"{Decimal(value):,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


@app.template_filter("datefmt")
def datefmt(value):
    if not value:
        return "-"
    if isinstance(value, str):
        return value
    return value.strftime("%d.%m.%Y")


@app.template_filter("datetimefmt")
def datetimefmt(value):
    if not value:
        return "-"
    if isinstance(value, str):
        return value
    return value.strftime("%d.%m.%Y %H:%M")


def parse_date(value, field_name):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} geçerli bir tarih olmalı.")


def parse_decimal(value, field_name):
    try:
        amount = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError):
        raise ValueError(f"{field_name} geçerli bir sayı olmalı.")
    if amount <= 0:
        raise ValueError(f"{field_name} sıfırdan büyük olmalı.")
    return amount


def parse_optional_int(value):
    if value in (None, "", "None"):
        return None
    return int(value)


def add_months(start_date, months):
    target_month = start_date.month - 1 + months
    year = start_date.year + target_month // 12
    month = target_month % 12 + 1
    day = min(start_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def log_event(event_type, detail=None, yonetici_id=None, conn=None):
    admin_id = yonetici_id if yonetici_id is not None else session.get("yonetici_id")
    ip_addr = request.remote_addr if request else None
    user_agent = request.headers.get("User-Agent") if request else None
    sql = """
        INSERT INTO yonetici_log (yonetici_id, olay_tipi, detay, ip_adresi, user_agent)
        VALUES (%s, %s, %s, %s, %s)
    """
    params = (admin_id, event_type, detail, ip_addr, user_agent)

    try:
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute(sql, params)
        else:
            with get_conn() as new_conn:
                with new_conn.cursor() as cur:
                    cur.execute(sql, params)
                new_conn.commit()
    except Exception:
        app.logger.exception("Log kaydı yazılamadı")


def safe_flash_db_error(error):
    message = str(error).splitlines()[0]
    flash(message, "error")


def expire_old_memberships():
    try:
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE uyelik SET durum = 'BITTI' "
                    "WHERE durum = 'AKTIF' AND bitis_tarihi < CURRENT_DATE"
                )
    except psycopg.Error:
        app.logger.exception("Süresi dolan üyelikler güncellenemedi")


@app.before_request
def auto_expire_memberships():
    if request.endpoint and request.endpoint != "static" and session.get("yonetici_id"):
        expire_old_memberships()


def reference_data():
    return {
        "planlar": fetch_all("SELECT * FROM plan ORDER BY plan_id"),
        "sureler": fetch_all("SELECT * FROM uyelik_suresi ORDER BY ay"),
        "sporcular": fetch_all(
            """
            SELECT sporcu_id, ad, soyad, telefon
              FROM sporcu
             WHERE aktif_mi = TRUE
             ORDER BY ad, soyad
            """
        ),
        "diyetisyenler": fetch_all(
            """
            SELECT calisan_id, ad, soyad
              FROM calisan
             WHERE rol = 'DIYETISYEN'
             ORDER BY ad, soyad
            """
        ),
        "ptler": fetch_all(
            """
            SELECT calisan_id, ad, soyad
              FROM calisan
             WHERE rol = 'PT'
             ORDER BY ad, soyad
            """
        ),
    }


@app.route("/")
def index():
    if session.get("yonetici_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        admin = fetch_one(
            """
            SELECT yonetici_id, ad_soyad, email, sifre_hash
              FROM yonetici
             WHERE email = %s AND aktif_mi = TRUE
            """,
            (email,),
        )

        if admin and check_password_hash(admin["sifre_hash"], password):
            session.clear()
            session["yonetici_id"] = admin["yonetici_id"]
            session["yonetici_ad"] = admin["ad_soyad"]
            with transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE yonetici
                           SET son_giris_tarihi = CURRENT_TIMESTAMP
                         WHERE yonetici_id = %s
                        """,
                        (admin["yonetici_id"],),
                    )
                log_event("LOGIN_SUCCESS", f"{email} giriş yaptı.", admin["yonetici_id"], conn)
            return redirect(url_for("dashboard"))

        log_event(
            "LOGIN_FAIL",
            f"Başarısız giriş denemesi: {email or 'boş email'}",
            admin["yonetici_id"] if admin else None,
        )
        flash("Email veya şifre hatalı.", "error")

    return render_template("login.html")


@app.post("/logout")
@login_required
def logout():
    log_event("LOGOUT", "Yönetici çıkış yaptı.")
    session.clear()
    return redirect(url_for("login"))


@app.get("/dashboard")
@login_required
def dashboard():
    stats = fetch_one(
        """
        SELECT
            (SELECT COUNT(*)
               FROM sporcu s
               JOIN uyelik u ON u.sporcu_id = s.sporcu_id
              WHERE s.aktif_mi = TRUE AND u.durum = 'AKTIF') AS aktif_sporcu,
            (SELECT COALESCE(SUM(tutar), 0)
               FROM odeme
              WHERE date_trunc('month', odeme_tarihi) = date_trunc('month', CURRENT_DATE)) AS aylik_gelir,
            (SELECT COUNT(*)
               FROM uyelik
              WHERE durum = 'AKTIF'
                AND bitis_tarihi BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days') AS yaklasan_bitis,
            (SELECT COUNT(*) FROM calisan) AS calisan_sayisi
        """
    )
    ending_memberships = fetch_all(
        """
        SELECT s.ad, s.soyad, s.telefon, p.plan_adi, u.bitis_tarihi,
               (u.bitis_tarihi - CURRENT_DATE) AS kalan_gun
          FROM uyelik u
          JOIN sporcu s ON s.sporcu_id = u.sporcu_id
          JOIN plan p ON p.plan_id = u.plan_id
         WHERE u.durum = 'AKTIF'
           AND u.bitis_tarihi BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
         ORDER BY u.bitis_tarihi ASC
        """
    )
    return render_template("dashboard.html", stats=stats, ending_memberships=ending_memberships)


@app.get("/api/dashboard/plan-dagilimi")
@login_required
def api_plan_distribution():
    rows = fetch_all(
        """
        SELECT p.plan_adi, COUNT(*) AS adet
          FROM uyelik u
          JOIN plan p ON p.plan_id = u.plan_id
         WHERE u.durum = 'AKTIF'
         GROUP BY p.plan_adi
         ORDER BY p.plan_adi
        """
    )
    return jsonify(
        {
            "labels": [row["plan_adi"] for row in rows],
            "values": [int(row["adet"]) for row in rows],
        }
    )


@app.get("/api/dashboard/aylik-gelir")
@login_required
def api_monthly_income():
    rows = fetch_all(
        """
        WITH aylar AS (
            SELECT date_trunc('month', CURRENT_DATE)::date - (n || ' months')::interval AS ay_baslangic
              FROM generate_series(5, 0, -1) AS n
        )
        SELECT to_char(a.ay_baslangic, 'YYYY-MM') AS ay,
               COALESCE(SUM(o.tutar), 0) AS gelir
          FROM aylar a
          LEFT JOIN odeme o
            ON date_trunc('month', o.odeme_tarihi) = a.ay_baslangic
         GROUP BY a.ay_baslangic
         ORDER BY a.ay_baslangic
        """
    )
    return jsonify(
        {
            "labels": [row["ay"] for row in rows],
            "values": [float(row["gelir"]) for row in rows],
        }
    )


@app.get("/sporcular")
@login_required
def sporcular():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "aktif")
    filters = []
    params = []

    if q:
        filters.append("(s.ad ILIKE %s OR s.soyad ILIKE %s OR s.telefon ILIKE %s)")
        like = f"%{q}%"
        params.extend([like, like, like])

    if status == "aktif":
        filters.append("s.aktif_mi = TRUE")
    elif status == "pasif":
        filters.append("s.aktif_mi = FALSE")

    where_sql = "WHERE " + " AND ".join(filters) if filters else ""
    rows = fetch_all(
        f"""
        SELECT s.*,
               u.uyelik_id,
               p.plan_adi,
               u.durum AS uyelik_durum,
               u.bitis_tarihi,
               (u.bitis_tarihi >= CURRENT_DATE) AS uye_yenilenebilir,
               CASE WHEN u.durum = 'AKTIF' AND u.bitis_tarihi IS NOT NULL
                    THEN u.bitis_tarihi - CURRENT_DATE END AS kalan_gun
          FROM sporcu s
          LEFT JOIN LATERAL (
              SELECT *
                FROM uyelik
               WHERE sporcu_id = s.sporcu_id
               ORDER BY (durum = 'AKTIF') DESC, baslangic_tarihi DESC
               LIMIT 1
          ) u ON TRUE
          LEFT JOIN plan p ON p.plan_id = u.plan_id
          {where_sql}
         ORDER BY s.aktif_mi DESC, s.ad, s.soyad
        """,
        tuple(params),
    )
    return render_template("sporcular.html", sporcular=rows, q=q, status=status)


@app.route("/sporcular/yeni", methods=["GET", "POST"])
@login_required
def sporcu_yeni():
    if request.method == "POST":
        try:
            with transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO sporcu (ad, soyad, telefon, kayit_tarihi, aktif_mi)
                        VALUES (%s, %s, %s, %s, TRUE)
                        RETURNING sporcu_id
                        """,
                        (
                            request.form["ad"].strip(),
                            request.form["soyad"].strip(),
                            request.form["telefon"].strip(),
                            parse_date(request.form["kayit_tarihi"], "Kayıt tarihi"),
                        ),
                    )
                    sporcu_id = cur.fetchone()["sporcu_id"]
                log_event("CREATE_SPORCU", f"Sporcu #{sporcu_id} oluşturuldu.", conn=conn)
            flash("Sporcu oluşturuldu.", "success")
            return redirect(url_for("sporcular"))
        except (ValueError, psycopg.Error) as exc:
            safe_flash_db_error(exc)

    return render_template("sporcu_form.html", sporcu=None, today=date.today())


@app.route("/sporcular/<int:sporcu_id>/duzenle", methods=["GET", "POST"])
@login_required
def sporcu_duzenle(sporcu_id):
    sporcu = fetch_one("SELECT * FROM sporcu WHERE sporcu_id = %s", (sporcu_id,))
    if not sporcu:
        flash("Sporcu bulunamadı.", "error")
        return redirect(url_for("sporcular"))

    if request.method == "POST":
        try:
            with transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE sporcu
                           SET ad = %s,
                               soyad = %s,
                               telefon = %s,
                               kayit_tarihi = %s,
                               aktif_mi = %s
                         WHERE sporcu_id = %s
                        """,
                        (
                            request.form["ad"].strip(),
                            request.form["soyad"].strip(),
                            request.form["telefon"].strip(),
                            parse_date(request.form["kayit_tarihi"], "Kayıt tarihi"),
                            request.form.get("aktif_mi") == "on",
                            sporcu_id,
                        ),
                    )
                log_event("UPDATE_SPORCU", f"Sporcu #{sporcu_id} güncellendi.", conn=conn)
            flash("Sporcu güncellendi.", "success")
            return redirect(url_for("sporcular"))
        except (ValueError, psycopg.Error) as exc:
            safe_flash_db_error(exc)

    return render_template("sporcu_form.html", sporcu=sporcu, today=date.today())


@app.post("/sporcular/<int:sporcu_id>/pasife-al")
@login_required
def sporcu_pasife_al(sporcu_id):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE sporcu SET aktif_mi = FALSE WHERE sporcu_id = %s", (sporcu_id,))
        log_event("DEACTIVATE_SPORCU", f"Sporcu #{sporcu_id} pasife alındı.", conn=conn)
    flash("Sporcu pasife alındı.", "success")
    return redirect(url_for("sporcular"))


@app.post("/sporcular/<int:sporcu_id>/aktif")
@login_required
def sporcu_aktif(sporcu_id):
    try:
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE sporcu SET aktif_mi = TRUE WHERE sporcu_id = %s AND aktif_mi = FALSE",
                    (sporcu_id,),
                )
                uye_guncellendi = cur.rowcount
                cur.execute(
                    """
                    UPDATE uyelik SET durum = 'AKTIF'
                     WHERE uyelik_id = (
                         SELECT uyelik_id FROM uyelik
                          WHERE sporcu_id = %s AND bitis_tarihi >= CURRENT_DATE
                          ORDER BY (durum = 'AKTIF') DESC, baslangic_tarihi DESC
                          LIMIT 1
                     )
                       AND durum <> 'AKTIF'
                    """,
                    (sporcu_id,),
                )
                uyelik_guncellendi = cur.rowcount
            if uye_guncellendi or uyelik_guncellendi:
                log_event("REACTIVATE_SPORCU", f"Sporcu #{sporcu_id} aktife alındı.", conn=conn)
        if uye_guncellendi or uyelik_guncellendi:
            flash("Üye aktife alındı.", "success")
        else:
            flash("Bu üye aktife alınamaz (zaten aktif veya günü kalan üyeliği yok).", "error")
    except psycopg.errors.UniqueViolation:
        flash("Bu üyenin zaten aktif bir üyeliği var; ikinci aktif üyelik açılamaz.", "error")
    except psycopg.Error as exc:
        safe_flash_db_error(exc)
    return redirect(url_for("sporcular"))


@app.post("/sporcular/<int:sporcu_id>/sil")
@login_required
def sporcu_sil(sporcu_id):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ad || ' ' || soyad AS ad_soyad, aktif_mi FROM sporcu WHERE sporcu_id = %s",
                (sporcu_id,),
            )
            row = cur.fetchone()
            if not row:
                flash("Üye bulunamadı.", "error")
                return redirect(url_for("sporcular"))
            if row["aktif_mi"]:
                flash("Aktif üye silinemez; önce pasife alın.", "error")
                return redirect(url_for("sporcular"))

            ad_soyad = row["ad_soyad"]
            cur.execute(
                """
                UPDATE odeme SET silinen_uye_ad = %s
                 WHERE uyelik_id IN (SELECT uyelik_id FROM uyelik WHERE sporcu_id = %s)
                """,
                (ad_soyad, sporcu_id),
            )
            cur.execute("DELETE FROM uyelik WHERE sporcu_id = %s", (sporcu_id,))
            cur.execute("DELETE FROM sporcu WHERE sporcu_id = %s", (sporcu_id,))
        log_event(
            "DELETE_SPORCU",
            f"Pasif üye #{sporcu_id} ({ad_soyad}) silindi; ödeme kayıtları korundu.",
            conn=conn,
        )
    flash(f"{ad_soyad} silindi; ödeme kayıtları korundu.", "success")
    return redirect(url_for("sporcular"))


@app.get("/calisanlar")
@login_required
def calisanlar():
    rol = request.args.get("rol", "TUM")
    if rol in ("PT", "DIYETISYEN", "DIGER"):
        rows = fetch_all("SELECT * FROM calisan WHERE rol = %s ORDER BY ad, soyad", (rol,))
    else:
        rows = fetch_all("SELECT * FROM calisan ORDER BY rol, ad, soyad")
        rol = "TUM"
    return render_template("calisanlar.html", calisanlar=rows, rol=rol)


@app.route("/calisanlar/yeni", methods=["GET", "POST"])
@login_required
def calisan_yeni():
    if request.method == "POST":
        try:
            with transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO calisan (ad, soyad, telefon, maas, mesai_baslangic, mesai_bitis, rol)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING calisan_id
                        """,
                        (
                            request.form["ad"].strip(),
                            request.form["soyad"].strip(),
                            request.form["telefon"].strip(),
                            parse_decimal(request.form["maas"], "Maaş"),
                            request.form["mesai_baslangic"],
                            request.form["mesai_bitis"],
                            request.form["rol"],
                        ),
                    )
                    calisan_id = cur.fetchone()["calisan_id"]
                log_event("CREATE_CALISAN", f"Çalışan #{calisan_id} oluşturuldu.", conn=conn)
            flash("Çalışan oluşturuldu.", "success")
            return redirect(url_for("calisanlar"))
        except (ValueError, psycopg.Error) as exc:
            safe_flash_db_error(exc)

    return render_template("calisan_form.html", calisan=None)


@app.route("/calisanlar/<int:calisan_id>/duzenle", methods=["GET", "POST"])
@login_required
def calisan_duzenle(calisan_id):
    calisan = fetch_one("SELECT * FROM calisan WHERE calisan_id = %s", (calisan_id,))
    if not calisan:
        flash("Çalışan bulunamadı.", "error")
        return redirect(url_for("calisanlar"))

    if request.method == "POST":
        try:
            with transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE calisan
                           SET ad = %s,
                               soyad = %s,
                               telefon = %s,
                               maas = %s,
                               mesai_baslangic = %s,
                               mesai_bitis = %s,
                               rol = %s
                         WHERE calisan_id = %s
                        """,
                        (
                            request.form["ad"].strip(),
                            request.form["soyad"].strip(),
                            request.form["telefon"].strip(),
                            parse_decimal(request.form["maas"], "Maaş"),
                            request.form["mesai_baslangic"],
                            request.form["mesai_bitis"],
                            request.form["rol"],
                            calisan_id,
                        ),
                    )
                log_event("UPDATE_CALISAN", f"Çalışan #{calisan_id} güncellendi.", conn=conn)
            flash("Çalışan güncellendi.", "success")
            return redirect(url_for("calisanlar"))
        except (ValueError, psycopg.Error) as exc:
            safe_flash_db_error(exc)

    return render_template("calisan_form.html", calisan=calisan)


@app.route("/uyelikler/yeni", methods=["GET", "POST"])
@login_required
def uyelik_yeni():
    refs = reference_data()
    preview = None

    if request.method == "POST":
        try:
            sporcu_id = int(request.form["sporcu_id"])
            plan_id = int(request.form["plan_id"])
            sure_id = int(request.form["sure_id"])
            baslangic_tarihi = parse_date(request.form["baslangic_tarihi"], "Başlangıç tarihi")
            diyetisyen_id = parse_optional_int(request.form.get("diyetisyen_id"))
            pt_id = parse_optional_int(request.form.get("pt_id"))

            plan = fetch_one("SELECT * FROM plan WHERE plan_id = %s", (plan_id,))
            sure = fetch_one("SELECT * FROM uyelik_suresi WHERE sure_id = %s", (sure_id,))
            if not plan or not sure:
                raise ValueError("Plan veya süre bulunamadı.")

            if plan["plan_adi"] in ("Profesyonel", "VIP") and not diyetisyen_id:
                raise ValueError(f"{plan['plan_adi']} plan için diyetisyen seçilmelidir.")
            if plan["plan_adi"] == "VIP" and not pt_id:
                raise ValueError("VIP plan için PT seçilmelidir.")

            bitis_tarihi = add_months(baslangic_tarihi, int(sure["ay"]))
            tutar = Decimal(plan["aylik_ucret"]) * Decimal(sure["katsayi"])
            preview = {
                "plan_adi": plan["plan_adi"],
                "bitis_tarihi": bitis_tarihi,
                "tutar": tutar,
            }

            with transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM uyelik WHERE sporcu_id = %s AND durum = 'AKTIF'",
                        (sporcu_id,),
                    )
                    if cur.fetchone():
                        raise ValueError("Bu sporcunun zaten aktif bir üyeliği var.")

                    cur.execute(
                        """
                        INSERT INTO uyelik
                            (sporcu_id, plan_id, sure_id, baslangic_tarihi, bitis_tarihi, tutar, durum)
                        VALUES (%s, %s, %s, %s, %s, %s, 'AKTIF')
                        RETURNING uyelik_id
                        """,
                        (sporcu_id, plan_id, sure_id, baslangic_tarihi, bitis_tarihi, tutar),
                    )
                    uyelik_id = cur.fetchone()["uyelik_id"]

                    if diyetisyen_id or pt_id:
                        cur.execute(
                            """
                            INSERT INTO sporcu_atama (uyelik_id, diyetisyen_id, pt_id, atama_tarihi)
                            VALUES (%s, %s, %s, CURRENT_DATE)
                            """,
                            (uyelik_id, diyetisyen_id, pt_id),
                        )
                log_event("CREATE_UYELIK", f"Üyelik #{uyelik_id} oluşturuldu.", conn=conn)

            flash("Üyelik oluşturuldu.", "success")
            return redirect(url_for("uyelik_detay", uyelik_id=uyelik_id))
        except (ValueError, psycopg.Error) as exc:
            safe_flash_db_error(exc)

    return render_template("uyelik_form.html", refs=refs, today=date.today(), preview=preview)


@app.get("/uyelikler/<int:uyelik_id>")
@login_required
def uyelik_detay(uyelik_id):
    uyelik = fetch_one(
        """
        SELECT u.*, s.ad, s.soyad, s.telefon, p.plan_adi, us.ay, us.katsayi,
               d.ad || ' ' || d.soyad AS diyetisyen_ad,
               pt.ad || ' ' || pt.soyad AS pt_ad,
               (u.bitis_tarihi >= CURRENT_DATE) AS yenilenebilir,
               COALESCE(SUM(o.tutar), 0) AS odenen,
               u.tutar - COALESCE(SUM(o.tutar), 0) AS kalan
          FROM uyelik u
          JOIN sporcu s ON s.sporcu_id = u.sporcu_id
          JOIN plan p ON p.plan_id = u.plan_id
          JOIN uyelik_suresi us ON us.sure_id = u.sure_id
          LEFT JOIN sporcu_atama sa ON sa.uyelik_id = u.uyelik_id
          LEFT JOIN calisan d ON d.calisan_id = sa.diyetisyen_id
          LEFT JOIN calisan pt ON pt.calisan_id = sa.pt_id
          LEFT JOIN odeme o ON o.uyelik_id = u.uyelik_id
         WHERE u.uyelik_id = %s
         GROUP BY u.uyelik_id, s.ad, s.soyad, s.telefon, p.plan_adi, us.ay, us.katsayi,
                  d.ad, d.soyad, pt.ad, pt.soyad
        """,
        (uyelik_id,),
    )
    if not uyelik:
        flash("Üyelik bulunamadı.", "error")
        return redirect(url_for("sporcular"))

    odemeler = fetch_all(
        "SELECT * FROM odeme WHERE uyelik_id = %s ORDER BY odeme_tarihi DESC, odeme_id DESC",
        (uyelik_id,),
    )
    return render_template("uyelik_detay.html", uyelik=uyelik, odemeler=odemeler)


@app.post("/uyelikler/<int:uyelik_id>/aktif")
@login_required
def uyelik_aktif(uyelik_id):
    try:
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE uyelik SET durum = 'AKTIF' "
                    "WHERE uyelik_id = %s AND durum <> 'AKTIF' AND bitis_tarihi >= CURRENT_DATE",
                    (uyelik_id,),
                )
                guncellenen = cur.rowcount
            if guncellenen:
                log_event("REACTIVATE_UYELIK", f"Üyelik #{uyelik_id} tekrar aktife alındı.", conn=conn)
        if guncellenen:
            flash(f"Üyelik #{uyelik_id} tekrar aktife alındı.", "success")
        else:
            flash("Bu üyelik aktife alınamaz (süresi dolmuş veya zaten aktif).", "error")
    except psycopg.errors.UniqueViolation:
        flash("Bu sporcunun zaten aktif bir üyeliği var; ikinci aktif üyelik açılamaz.", "error")
    except psycopg.Error as exc:
        safe_flash_db_error(exc)
    return redirect(url_for("uyelik_detay", uyelik_id=uyelik_id))


@app.post("/uyelikler/<int:uyelik_id>/sil")
@login_required
def uyelik_sil(uyelik_id):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.durum, s.ad || ' ' || s.soyad AS ad_soyad
                  FROM uyelik u
                  JOIN sporcu s ON s.sporcu_id = u.sporcu_id
                 WHERE u.uyelik_id = %s
                """,
                (uyelik_id,),
            )
            row = cur.fetchone()
            silinen = 0
            if row and row["durum"] != "AKTIF":
                cur.execute(
                    "UPDATE odeme SET silinen_uye_ad = %s WHERE uyelik_id = %s",
                    (row["ad_soyad"], uyelik_id),
                )
                cur.execute("DELETE FROM uyelik WHERE uyelik_id = %s", (uyelik_id,))
                silinen = cur.rowcount
        if silinen:
            log_event("DELETE_UYELIK", f"Üyelik #{uyelik_id} silindi; ödeme kayıtları korundu.", conn=conn)

    if silinen:
        flash(f"Üyelik #{uyelik_id} silindi; ödeme kayıtları korundu.", "success")
    else:
        flash("Aktif üyelik silinemez; yalnızca süresi dolmuş/iptal üyelikler silinebilir.", "error")
    return redirect(url_for("sporcular"))


def active_memberships_with_debt():
    return fetch_all(
        """
        SELECT u.uyelik_id,
               s.ad || ' ' || s.soyad AS sporcu_ad,
               p.plan_adi,
               u.tutar,
               COALESCE(SUM(o.tutar), 0) AS odenen,
               u.tutar - COALESCE(SUM(o.tutar), 0) AS kalan
          FROM uyelik u
          JOIN sporcu s ON s.sporcu_id = u.sporcu_id
          JOIN plan p ON p.plan_id = u.plan_id
          LEFT JOIN odeme o ON o.uyelik_id = u.uyelik_id
         WHERE u.durum = 'AKTIF'
         GROUP BY u.uyelik_id, s.ad, s.soyad, p.plan_adi
         ORDER BY s.ad, s.soyad
        """
    )


@app.get("/odemeler")
@login_required
def odemeler():
    payments = fetch_all(
        """
        SELECT o.*,
               COALESCE(s.ad || ' ' || s.soyad, o.silinen_uye_ad) AS sporcu_ad,
               (o.uyelik_id IS NULL) AS silinmis,
               p.plan_adi
          FROM odeme o
          LEFT JOIN uyelik u ON u.uyelik_id = o.uyelik_id
          LEFT JOIN sporcu s ON s.sporcu_id = u.sporcu_id
          LEFT JOIN plan p ON p.plan_id = u.plan_id
         ORDER BY o.odeme_tarihi DESC, o.odeme_id DESC
         LIMIT 100
        """
    )
    memberships = active_memberships_with_debt()
    return render_template("odemeler.html", odemeler=payments, memberships=memberships)


@app.route("/odemeler/yeni", methods=["GET", "POST"])
@login_required
def odeme_yeni():
    memberships = active_memberships_with_debt()

    if request.method == "POST":
        try:
            uyelik_id = int(request.form["uyelik_id"])
            tutar = parse_decimal(request.form["tutar"], "Ödeme tutarı")
            odeme_tarihi = parse_date(request.form["odeme_tarihi"], "Ödeme tarihi")
            odeme_yontemi = request.form["odeme_yontemi"]
            membership = fetch_one(
                """
                SELECT u.tutar - COALESCE(SUM(o.tutar), 0) AS kalan
                  FROM uyelik u
                  LEFT JOIN odeme o ON o.uyelik_id = u.uyelik_id
                 WHERE u.uyelik_id = %s
                 GROUP BY u.uyelik_id
                """,
                (uyelik_id,),
            )
            if not membership:
                raise ValueError("Üyelik bulunamadı.")
            if Decimal(membership["kalan"]) <= 0:
                raise ValueError("Bu üyeliğin kalan borcu yok.")
            if tutar > Decimal(membership["kalan"]):
                raise ValueError("Ödeme tutarı kalan borçtan büyük olamaz.")

            kart_faizi = (
                (tutar * Decimal("0.05")).quantize(Decimal("0.01"))
                if odeme_yontemi == "KART"
                else Decimal("0")
            )
            tahsil_edilen = tutar + kart_faizi

            with transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO odeme (uyelik_id, tutar, odeme_tarihi, odeme_yontemi)
                        VALUES (%s, %s, %s, %s)
                        RETURNING odeme_id
                        """,
                        (uyelik_id, tutar, odeme_tarihi, odeme_yontemi),
                    )
                    odeme_id = cur.fetchone()["odeme_id"]
                log_detay = f"Ödeme #{odeme_id} oluşturuldu."
                if kart_faizi > 0:
                    log_detay += (
                        f" Kart faizi %5 = {money(kart_faizi)}, "
                        f"toplam tahsilat = {money(tahsil_edilen)}."
                    )
                log_event("CREATE_ODEME", log_detay, conn=conn)
            if kart_faizi > 0:
                flash(
                    f"Ödeme eklendi. Kart faizi (%5): {money(kart_faizi)} — "
                    f"müşteriden tahsil edilen toplam: {money(tahsil_edilen)}.",
                    "success",
                )
            else:
                flash("Ödeme eklendi.", "success")
            return redirect(url_for("odemeler"))
        except (ValueError, psycopg.Error) as exc:
            safe_flash_db_error(exc)

    return render_template("odeme_form.html", memberships=memberships, today=date.today())


@app.get("/sorgular")
@login_required
def sorgular():
    reports = {
        "yaklasan": fetch_all(
            """
            SELECT s.ad || ' ' || s.soyad AS sporcu, p.plan_adi, u.bitis_tarihi,
                   u.bitis_tarihi - CURRENT_DATE AS kalan_gun
              FROM uyelik u
              JOIN sporcu s ON s.sporcu_id = u.sporcu_id
              JOIN plan p ON p.plan_id = u.plan_id
             WHERE u.durum = 'AKTIF'
               AND u.bitis_tarihi BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
             ORDER BY u.bitis_tarihi
            """
        ),
        "pt_yuku": fetch_all(
            """
            SELECT c.ad || ' ' || c.soyad AS pt, COUNT(u.uyelik_id) AS aktif_sporcu
              FROM calisan c
              LEFT JOIN sporcu_atama sa ON sa.pt_id = c.calisan_id
              LEFT JOIN uyelik u ON u.uyelik_id = sa.uyelik_id AND u.durum = 'AKTIF'
             WHERE c.rol = 'PT'
             GROUP BY c.calisan_id
             ORDER BY aktif_sporcu DESC, pt
            """
        ),
        "diyetisyen_yuku": fetch_all(
            """
            SELECT c.ad || ' ' || c.soyad AS diyetisyen, COUNT(u.uyelik_id) AS aktif_sporcu
              FROM calisan c
              LEFT JOIN sporcu_atama sa ON sa.diyetisyen_id = c.calisan_id
              LEFT JOIN uyelik u ON u.uyelik_id = sa.uyelik_id AND u.durum = 'AKTIF'
             WHERE c.rol = 'DIYETISYEN'
             GROUP BY c.calisan_id
             ORDER BY aktif_sporcu DESC, diyetisyen
            """
        ),
        "aylik_gelir": fetch_all(
            """
            SELECT to_char(date_trunc('month', odeme_tarihi), 'YYYY-MM') AS ay,
                   SUM(tutar) AS toplam_gelir
              FROM odeme
             GROUP BY date_trunc('month', odeme_tarihi)
             ORDER BY ay DESC
            """
        ),
        "plan_dagilimi": fetch_all(
            """
            SELECT p.plan_adi, COUNT(*) AS aktif_sporcu
              FROM uyelik u
              JOIN plan p ON p.plan_id = u.plan_id
             WHERE u.durum = 'AKTIF'
             GROUP BY p.plan_adi
             ORDER BY aktif_sporcu DESC
            """
        ),
        "aktif_kalan": fetch_all(
            """
            SELECT s.ad || ' ' || s.soyad AS sporcu, p.plan_adi,
                   u.baslangic_tarihi, u.bitis_tarihi,
                   u.bitis_tarihi - CURRENT_DATE AS kalan_gun
              FROM uyelik u
              JOIN sporcu s ON s.sporcu_id = u.sporcu_id
              JOIN plan p ON p.plan_id = u.plan_id
             WHERE u.durum = 'AKTIF'
             ORDER BY kalan_gun ASC
            """
        ),
    }
    return render_template("sorgular.html", reports=reports)


@app.get("/loglar")
@login_required
def loglar():
    rows = fetch_all(
        """
        SELECT yl.*, y.ad_soyad
          FROM yonetici_log yl
          LEFT JOIN yonetici y ON y.yonetici_id = yl.yonetici_id
         ORDER BY yl.olay_zamani DESC
         LIMIT 200
        """
    )
    return render_template("loglar.html", loglar=rows)


if __name__ == "__main__":
    app.run(debug=True)
