import re
import os
import html
import hashlib
import datetime
import sqlite3
import streamlit as st
import streamlit.components.v1 as components

# ---------------------------------------------------------
# 1. SAYFA YAPILANDIRMASI VE TEMA AYARLARI
# ---------------------------------------------------------
st.set_page_config(
    page_title="Bilgi ve Hikmet Köşesi",
    page_icon="⏳",
    layout="wide",
    initial_sidebar_state="collapsed"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "icerik_arsivi.db")

# ---------------------------------------------------------
# 2. GÜVENLİK: ŞİFRE YÖNETİMİ VE VERİTABANI (SQLITE)
# ---------------------------------------------------------
def get_author_password() -> str:
    try:
        if "AUTHOR_PASSWORD" in st.secrets:
            return str(st.secrets["AUTHOR_PASSWORD"])
    except Exception:
        pass
    return "lebis9791."


DEFAULT_PASSWORD = get_author_password()


def make_hash(password: str) -> str:
    return hashlib.sha256(str.encode(password)).hexdigest()


AUTHOR_PASSWORD_HASH = make_hash(DEFAULT_PASSWORD)


def temizle_eski_html_kalintisi(metin: str) -> str:
    """Eski kayıtlardan kalmış wrapper etiketleri ve satır başı girintilerini temizler."""
    if not metin:
        return ""
    temiz = metin.replace("\r\n", "\n").replace("\r", "\n")
    temiz = re.sub(
        r'^\s*<div\s+class=["\'](?:wisdom-title|wisdom-body|wisdom-card)["\']>\s*',
        '',
        temiz,
        flags=re.IGNORECASE | re.MULTILINE
    )
    temiz = re.sub(r'^\s*</div>\s*$', '', temiz, flags=re.IGNORECASE | re.MULTILINE)
    temiz = re.sub(r'\s*</div>\s*$', '', temiz, flags=re.IGNORECASE)
    satirlar = [s.lstrip(" \t") for s in temiz.split("\n")]
    return "\n".join(satirlar).strip()


def temizle_veritabani_kalintilari(conn: sqlite3.Connection):
    """Mevcut SQLite kayıtlarındaki kalıntı HTML etiketlerini kalıcı olarak temizler."""
    c = conn.cursor()

    c.execute("SELECT id, baslik_tr, icerik_tr, yonlendirme_etiket_tr FROM yazilar")
    for row in c.fetchall():
        y_id, b_tr, i_tr, et_tr = row
        nb_tr = temizle_eski_html_kalintisi(b_tr or "") or "Bilgi Notu"
        ni_tr = temizle_eski_html_kalintisi(i_tr or "")
        net_tr = temizle_eski_html_kalintisi(et_tr or "")

        if (nb_tr, ni_tr, net_tr) != (b_tr or "", i_tr or "", et_tr or ""):
            c.execute('''
                UPDATE yazilar
                SET baslik_tr = ?, icerik_tr = ?, yonlendirme_etiket_tr = ?
                WHERE id = ?
            ''', (nb_tr, ni_tr, net_tr, y_id))

    c.execute("SELECT id, metin_tr FROM kayan_sozler")
    for s_id, m_tr in c.fetchall():
        nm_tr = temizle_eski_html_kalintisi(m_tr or "")
        if nm_tr != (m_tr or ""):
            c.execute('''
                UPDATE kayan_sozler
                SET metin_tr = ?
                WHERE id = ?
            ''', (nm_tr, s_id))

    conn.commit()


def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS kayan_sozler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kategori TEXT,
            metin_tr TEXT,
            kaynak TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS yazilar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baslik_tr TEXT,
            icerik_tr TEXT,
            kaynak TEXT,
            yonlendirme_url TEXT,
            yonlendirme_etiket_tr TEXT,
            tarih TEXT
        )
    ''')
    conn.commit()

    c.execute("SELECT COUNT(*) FROM kayan_sozler")
    if c.fetchone()[0] == 0:
        ornek_sozler = [
            (
                "Ayet / Hadis / Hikmet",
                "İnsan için ancak çalıştığının karşılığı vardır.",
                "Necm Suresi, 39. Ayet"
            ),
            (
                "Vatan, Millet ve Bayrak",
                "Birlik ve beraberlik; ölümden başka her şeyi yener.",
                "Tarihi Devlet Hikmeti"
            ),
            (
                "Osmanlı Padişahları",
                "Halk içinde muteber bir nesne yok devlet gibi; olmaya devlet cihanda bir nefes sıhhat gibi.",
                "Kanuni Sultan Süleyman (Muhibbi)"
            ),
            (
                "Veli Kulların Görüşleri",
                "İlim ilim bilmektir, ilim kendin bilmektir; sen kendini bilmezsin, ya nice okumaktır.",
                "Yunus Emre"
            ),
            (
                "Osmanlı Padişahları",
                "İnsanı yaşat ki devlet yaşasın.",
                "Şeyh Edebali'nin Osman Gazi'ye Nasihati"
            )
        ]
        c.executemany(
            "INSERT INTO kayan_sozler (kategori, metin_tr, kaynak) VALUES (?, ?, ?)",
            ornek_sozler
        )
        conn.commit()

    c.execute("SELECT COUNT(*) FROM yazilar")
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO yazilar (
                baslik_tr, icerik_tr, kaynak,
                yonlendirme_url, yonlendirme_etiket_tr, tarih
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            "Zamanın Kıymeti, Birlik Ruhu ve İlim Paylaşımı",
            "Ömür, akıp giden bir kum saati gibidir. Her bir tanesi geri döndürülemez bir nefesi temsil eder. Vatanımıza, bayrağımıza, birlik ve beraberliğimize sahip çıkmak; ilmi, hikmeti ve güzel ahlakı yaymak en yüce vazifemizdir. Geçmişten aldığımız manevi mirası, doğruluk ve adalet ekseninde geleceğe taşımalıyız.",
            "Kültür ve Hikmet Derlemeleri",
            "",
            "",
            datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        ))
        conn.commit()

    temizle_veritabani_kalintilari(conn)
    return conn


conn = init_db()

# ---------------------------------------------------------
# 3. OTURUM DURUMLARI (YAZAR GİRİŞİ VE DÜZENLEME)
# ---------------------------------------------------------
if "is_author" not in st.session_state:
    st.session_state.is_author = False
if "edit_post_id" not in st.session_state:
    st.session_state.edit_post_id = None
if "edit_ticker_id" not in st.session_state:
    st.session_state.edit_ticker_id = None

# ---------------------------------------------------------
# 4. ARAYÜZ METİNLERİ (TEK DİL: TÜRKÇE)
# ---------------------------------------------------------
T = {
    "site_title": "MİLLİ VE MANEVİ HİKMET KÖŞESİ",
    "site_subtitle": "Vatan, Millet, Bayrak, Birlik ve İlim Paylaşım Platformu",
    "hourglass_caption": "Ömür sermayesi hızla akıyor; her anı hayırla ve ilimle değerlendirelim.",
    "author_login_btn": "🔐 Misafir Yazar Girişi",
    "author_logout_btn": "🚪 Yazar Çıkışı Yap",
    "login_header": "Yetkili Misafir Yazar Girişi",
    "password_label": "Yazar Erişim Şifresi:",
    "login_submit": "Giriş Yap",
    "login_success": "Yazar yetkisi doğrulandı. Kopyalama/yapıştırma ve içerik düzenleme aktif.",
    "login_error": "Hatalı şifre! Yetkisiz erişim engellendi.",
    "author_panel_title": "✍️ Yazar İçerik Yönetim Paneli (Serbest Kopyala / Yapıştır Aktif)",
    "tab_new_post": "📝 Yeni Bilgi Notu / Makale Paylaş",
    "tab_new_ticker": "📢 Üst Kayan Şeride Yeni Söz Ekle",
    "tab_manage": "🗂️ Mevcut İçerikleri Güncelle / Sil",
    "post_title_label": "Yazı Başlığı:",
    "post_content_label": "Bilgi Notu / Hikmetli Yazı (Büyük Kapasiteli Alan - İstediğiniz kadar metin yapıştırabilirsiniz):",
    "post_source_label": "Kaynak Belirtiniz (Zorunlu - Ayet, Hadis, Padişah, Eser veya Yazar):",
    "post_url_label": "Harici Site Yönlendirme Bağlantısı (İsteğe Bağlı - Örn: https://...):",
    "post_url_text_label": "Yönlendirme Butonu Açıklaması (İsteğe Bağlı - Örn: İlgili Kaynak Siteye Git):",
    "publish_btn": "🚀 Yayına Al",
    "publish_success": "Bilgi notu başarıyla yayınlandı!",
    "source_warning": "Lütfen kaynak belirtiniz. Kaynaksız paylaşım yapılamaz.",
    "ticker_cat_label": "Konu Kategorisi:",
    "ticker_cats": [
        "Vatan, Millet ve Bayrak",
        "Birlik ve Beraberlik",
        "Ayet / Hadis / Hikmet",
        "Veli Kulların Görüşleri",
        "Osmanlı Padişahları"
    ],
    "ticker_text_label": "Kayan Şerit Sözü:",
    "ticker_source_label": "Sözün Kaynağı (Zorunlu):",
    "ticker_add_btn": "➕ Kayan Şeride Ekle",
    "ticker_success": "Söz üst kayan şeride eklendi!",
    "posts_section_header": "📜 PAYLAŞILAN BİLGİ NOTLARI VE HİKMETLER",
    "source_prefix": "Kaynak:",
    "date_prefix": "Yayın Tarihi:",
    "visit_link_default": "🔗 Yazarın Önerdiği Bağlantıya Git",
    "no_posts": "Henüz paylaşılmış bir bilgi notu bulunmamaktadır.",
    "edit_btn": "✏️ Güncelle",
    "delete_btn": "🗑️ Sil",
    "delete_all_posts_btn": "💣 Tüm Bilgi Notlarını Veritabanından Sil",
    "delete_all_tickers_btn": "💣 Tüm Kayan Sözleri Veritabanından Sil",
    "confirm_delete_all": "Tüm kayıtların veritabanından kalıcı olarak silineceğini onaylıyorum",
    "confirm_warning": "Önce yukarıdaki kalıcı silme onay kutusunu işaretleyin.",
    "all_deleted_msg": "Seçili tüm veriler veritabanından kalıcı olarak silindi.",
    "updated_msg": "Kayıt güncellendi.",
    "deleted_msg": "Kayıt veritabanından silindi.",
    "legal_title": "⚖️ HUKUKİ KORUMA VE YASAL UYARI",
    "legal_text": (
        "1. Bu platform yalnızca bilgi paylaşımı yapmak, milli ve manevi duyguları geliştirmek amacıyla oluşturulmuştur.\n"
        "2. Sitede yer alan tüm bilgi notları, derlemeler ve tasarımlar Fikir ve Sanat Eserleri Kanunu kapsamında hukuki koruma altındadır.\n"
        "3. İçeriklerin izinsiz kopyalanması, çoğaltılması, başka mecralarda yayınlanması ve ticari amaçla kullanılması kesinlikle yasaktır. Ticareti yapılamaz.\n"
        "4. Her hakkı saklıdır. Kaynak gösterilmeden alıntı yapılamaz.\n"
        "5. Yazılımda yer alan ayet, hadis ve âlim görüşlerine ilişkin çeviriler (otomatik veya yapay zekâ destekli çeviriler dahil) kolaylık ve genel bilgilendirme amacıyla sunulmaktadır. Kavram incelikleri, bağlam ve yorum farkları nedeniyle çevirilerde anlam kayması oluşabilir; bu çeviriler tek başına kesin veya bağlayıcı kaynak yerine geçmez ve asıl metinlerin, muteber meallerin ile ilgili kaynak eserlerin esas alınması gerekir.\n"
        "6. Yazılımdaki metin ve kaynak atıfları yapay zekâ desteğiyle oluşturulmuş olabilir; yalnızca bilgilendirme amaçlıdır ve resmî, teknik, idari, mali veya hukuki görüş/onay yerine geçmez. Yapay zekâ sistemleri eksik, güncel olmayan veya hatalı bilgi ve kaynak üretebileceğinden, tüm içerik ve atıfların kullanılmadan önce birincil kaynaklardan teyit edilmesi kullanıcının sorumluluğundadır.\n"
        "7. Yazılım \"olduğu gibi\" (AS-IS) sunulur; doğrulanmamış içeriklerin kullanımından doğabilecek zararlardan geliştirici ve dağıtıcı sorumlu tutulamaz."
    ),
    "protection_badge": "🛡️ Kopyalama Koruması Aktif (Salt Okunur Ziyaretçi Modu)"
}
# ---------------------------------------------------------
# 5. KENAR ÇUBUĞU (SIDEBAR): UYKU MODU BİLGİSİ VE YENİLEME
# ---------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.info(
    "💡 **Bilgi Notu:** Bu uygulama ücretsiz sunucularda barındırılmaktadır. "
    "Belirli bir süre işlem yapılmadığında kaynak tasarrufu için uyku moduna geçebilir "
    "ve ekranda **'Zzzz'** simgesi görünebilir.\n\n"
    "💤 **Uygulamayı Yeniden Başlatma:**\n"
    "1. Uyku ekranı geldiğinde mavi **'Yes, get this app back up!'** butonuna tıklayın.\n"
    "2. Uygulamanın açılması için ortalama **15–30 saniye** bekleyin.\n"
    "3. Süre dolmasına rağmen ekran güncellenmezse tarayıcı sayfasını yenileyin (F5 / Ctrl+R)."
)
st.sidebar.caption("Uygulama yavaşladıysa veya takıldıysa aşağıdaki butonu kullanabilirsiniz:")
if st.sidebar.button("🔄 Sayfayı Yenile", use_container_width=True):
    st.rerun()

# ---------------------------------------------------------
# 6. TASARIM, KUM SAATİ VE KOPYALAMA KORUMASI (CSS + JS)
# ---------------------------------------------------------
if not st.session_state.is_author:
    anti_copy_css = """
    body, .stApp, p, h1, h2, h3, h4, span, div, article {
        -webkit-user-select: none !important;
        -moz-user-select: none !important;
        -ms-user-select: none !important;
        user-select: none !important;
    }
    """
else:
    anti_copy_css = """
    input, textarea, [contenteditable="true"] {
        -webkit-user-select: text !important;
        -moz-user-select: text !important;
        -ms-user-select: text !important;
        user-select: text !important;
    }
    """

st.markdown(
    "<style>"
    ".stApp { background-color: #F6F4EE; color: #1E242B; font-family: 'Georgia', 'Segoe UI', serif; }"
    ".ticker-wrapper { width: 100%; overflow: hidden; background: linear-gradient(90deg, #EAE4D3 0%, #F2EFE6 50%, #EAE4D3 100%); border-top: 3px solid #2C3E50; border-bottom: 3px solid #2C3E50; padding: 16px 0; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); white-space: nowrap; position: relative; }"
    ".ticker-content { display: inline-block; padding-left: 100%; animation: marquee-fast 28s linear infinite; font-size: 26px; font-weight: 900; color: #000000 !important; letter-spacing: 0.4px; }"
    ".ticker-wrapper:hover .ticker-content { animation-play-state: paused; }"
    ".ticker-source { font-size: 19px; font-weight: 700; color: #7B241C; margin-right: 65px; }"
    "@keyframes marquee-fast { 0% { transform: translate(0, 0); } 100% { transform: translate(-100%, 0); } }"
    ".hourglass-box { display: flex; flex-direction: column; align-items: center; justify-content: center; background-color: #EFECE2; border: 1px solid #D5CEBC; border-radius: 14px; padding: 14px 18px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }"
    ".hourglass-icon { font-size: 46px; display: inline-block; animation: flip-hourglass 4s ease-in-out infinite; }"
    "@keyframes flip-hourglass { 0% { transform: rotate(0deg); } 45% { transform: rotate(0deg); } 50% { transform: rotate(180deg); } 95% { transform: rotate(180deg); } 100% { transform: rotate(360deg); } }"
    ".hourglass-text { font-size: 13.5px; font-style: italic; color: #4A4437; margin-top: 6px; font-weight: 600; }"
    ".wisdom-card { background-color: #FCFBF7; border-left: 6px solid #2C3E50; border-top: 1px solid #E2DDD0; border-right: 1px solid #E2DDD0; border-bottom: 1px solid #E2DDD0; border-radius: 10px; padding: 26px 30px; margin-bottom: 14px; box-shadow: 0 3px 10px rgba(0,0,0,0.04); }"
    ".wisdom-title { font-size: 23px; font-weight: 800; color: #1A252F; margin-bottom: 14px; border-bottom: 1px dashed #D5CEBC; padding-bottom: 8px; }"
    ".wisdom-body { font-size: 18px; line-height: 1.8; color: #212529; white-space: pre-wrap; margin-bottom: 18px; }"
    ".wisdom-meta { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; background-color: #F2EFE6; padding: 10px 16px; border-radius: 6px; font-size: 15px; color: #3E3A32; font-weight: 700; }"
    ".redirect-btn { display: inline-block; margin-top: 14px; padding: 10px 20px; background-color: #1E3A5F; color: #FFFFFF !important; text-decoration: none; border-radius: 6px; font-weight: 700; font-size: 15px; transition: background-color 0.2s ease; }"
    ".redirect-btn:hover { background-color: #142842; }"
    ".legal-footer { background-color: #EAE5D9; border: 2px solid #8C7A5B; border-radius: 10px; padding: 20px 24px; margin-top: 40px; color: #2C271E; font-size: 14.5px; line-height: 1.7; }"
    ".legal-footer h4 { margin-top: 0; color: #5C1A1B; font-weight: 800; }"
    + anti_copy_css +
    "</style>",
    unsafe_allow_html=True
)

if not st.session_state.is_author:
    components.html(
        """
        <script>
        const doc = window.parent.document;
        doc.addEventListener('contextmenu', function(e) {
            e.preventDefault();
        });
        doc.addEventListener('copy', function(e) {
            e.preventDefault();
        });
        doc.addEventListener('cut', function(e) {
            e.preventDefault();
        });
        doc.addEventListener('selectstart', function(e) {
            if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
                e.preventDefault();
            }
        });
        doc.addEventListener('keydown', function(e) {
            if (
                (e.ctrlKey && ['c', 'C', 'x', 'X', 'u', 'U', 's', 'S', 'a', 'A', 'p', 'P'].includes(e.key)) ||
                e.key === 'F12'
            ) {
                if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
                    e.preventDefault();
                }
            }
        });
        </script>
        """,
        height=0,
        width=0
    )

# ---------------------------------------------------------
# 7. ÜST KONTROL ÇUBUĞU (YAZAR GİRİŞİ)
# ---------------------------------------------------------
top_col1, top_col2 = st.columns([7, 2])

with top_col1:
    st.caption(
        T["protection_badge"]
        if not st.session_state.is_author
        else "🔓 Yazar Modu Aktif (Kopyala/Yapıştır ve Yönetim Açık)"
    )

with top_col2:
    if not st.session_state.is_author:
        with st.popover(T["author_login_btn"], use_container_width=True):
            st.subheader(T["login_header"])
            pwd_input = st.text_input(T["password_label"], type="password", key="author_pwd_input")
            if st.button(T["login_submit"], use_container_width=True):
                if make_hash(pwd_input) == AUTHOR_PASSWORD_HASH:
                    st.session_state.is_author = True
                    st.success(T["login_success"])
                    st.rerun()
                else:
                    st.error(T["login_error"])
    else:
        if st.button(T["author_logout_btn"], use_container_width=True):
            st.session_state.is_author = False
            st.session_state.edit_post_id = None
            st.session_state.edit_ticker_id = None
            st.rerun()

# ---------------------------------------------------------
# 8. EN ÜSTTE BÜYÜK SİYAH PUNTOLU HIZLI KAYAN SÖZLER ŞERİDİ
# ---------------------------------------------------------
c = conn.cursor()
c.execute("SELECT kategori, metin_tr, kaynak FROM kayan_sozler ORDER BY id DESC")
ticker_rows = c.fetchall()

ticker_items_html = ""
for row in ticker_rows:
    kat, m_tr, kynk = row
    soz_e = html.escape(temizle_eski_html_kalintisi(m_tr or ""))
    kynk_e = html.escape(temizle_eski_html_kalintisi(kynk or ""))
    ticker_items_html += f'<span>“{soz_e}” </span><span class="ticker-source">[{kynk_e}] &nbsp;&nbsp;✦&nbsp;&nbsp; </span>'

st.markdown(
    f'<div class="ticker-wrapper"><div class="ticker-content">{ticker_items_html}</div></div>',
    unsafe_allow_html=True
)

# ---------------------------------------------------------
# 9. BAŞLIK VE KUM SAATİ BÖLÜMÜ
# ---------------------------------------------------------
head_col1, head_col2 = st.columns([4, 1.3])

with head_col1:
    st.markdown(
        f"<h1 style='color:#1A252F; margin-bottom:4px; font-weight:900;'>{html.escape(T['site_title'])}</h1>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"<p style='font-size:18px; color:#4A4437; font-weight:600;'>{html.escape(T['site_subtitle'])}</p>",
        unsafe_allow_html=True
    )

with head_col2:
    st.markdown(
        f'<div class="hourglass-box"><div class="hourglass-icon">⏳</div>'
        f'<div class="hourglass-text">{html.escape(T["hourglass_caption"])}</div></div>',
        unsafe_allow_html=True
    )

st.markdown("---")
# ---------------------------------------------------------
# 10. YAZAR YÖNETİM PANELİ (EKLEME, GÜNCELLEME VE KALICI SİLME)
# ---------------------------------------------------------
if st.session_state.is_author:
    st.markdown(f"### {T['author_panel_title']}")
    tab1, tab2, tab3 = st.tabs([T["tab_new_post"], T["tab_new_ticker"], T["tab_manage"]])

    # SEKME 1: BÜYÜK KAPASİTELİ BİLGİ NOTU EKLEME
    with tab1:
        with st.form("yeni_yazi_formu", clear_on_submit=True):
            baslik_tr = st.text_input(T["post_title_label"])
            icerik_tr = st.text_area(
                T["post_content_label"],
                height=320,
                placeholder="Buraya istediğiniz uzunlukta bilgi notu, makale veya hikmetli söz kopyalayıp yapıştırabilirsiniz..."
            )
            kaynak_yazi = st.text_input(T["post_source_label"])

            col_url1, col_url2 = st.columns(2)
            with col_url1:
                yonlendirme_url = st.text_input(T["post_url_label"], placeholder="https://ornek-site.com")
            with col_url2:
                yonlendirme_etiket_tr = st.text_input(
                    T["post_url_text_label"],
                    placeholder="İlgili Siteye Gitmek İçin Tıklayınız"
                )

            submitted = st.form_submit_button(T["publish_btn"], type="primary")
            if submitted:
                if not kaynak_yazi.strip():
                    st.warning(T["source_warning"])
                elif not icerik_tr.strip():
                    st.warning("Lütfen içerik metnini giriniz.")
                else:
                    with st.spinner("İçerik kaydediliyor..."):
                        clean_b_tr = temizle_eski_html_kalintisi(baslik_tr)
                        clean_i_tr = temizle_eski_html_kalintisi(icerik_tr)
                        final_baslik_tr = clean_b_tr if clean_b_tr else "Bilgi Notu"
                        etiket_tr = temizle_eski_html_kalintisi(yonlendirme_etiket_tr)
                        tarih_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

                        c.execute('''
                            INSERT INTO yazilar (
                                baslik_tr, icerik_tr, kaynak,
                                yonlendirme_url, yonlendirme_etiket_tr, tarih
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            final_baslik_tr, clean_i_tr,
                            kaynak_yazi.strip(), yonlendirme_url.strip(), etiket_tr, tarih_str
                        ))
                        conn.commit()
                    st.toast(T["publish_success"])
                    st.rerun()

    # SEKME 2: ÜST KAYAN ŞERİDE SÖZ EKLEME
    with tab2:
        with st.form("yeni_kayan_soz_formu", clear_on_submit=True):
            kat_secim = st.selectbox(T["ticker_cat_label"], T["ticker_cats"])
            soz_tr = st.text_area(T["ticker_text_label"], height=120)
            soz_kaynak = st.text_input(T["ticker_source_label"])
            soz_ekle_btn = st.form_submit_button(T["ticker_add_btn"], type="primary")

            if soz_ekle_btn:
                if not soz_kaynak.strip() or not soz_tr.strip():
                    st.warning(T["source_warning"])
                else:
                    with st.spinner("Kayan şeride ekleniyor..."):
                        clean_soz_tr = temizle_eski_html_kalintisi(soz_tr)
                        c.execute(
                            "INSERT INTO kayan_sozler (kategori, metin_tr, kaynak) VALUES (?, ?, ?)",
                            (kat_secim, clean_soz_tr, soz_kaynak.strip())
                        )
                        conn.commit()
                    st.toast(T["ticker_success"])
                    st.rerun()

    # SEKME 3: MEVCUT İÇERİKLERİ GÜNCELLEME / KALICI SİLME
    with tab3:
        st.subheader("Paylaşılan Bilgi Notları")
        c.execute("""
            SELECT id, baslik_tr, icerik_tr, kaynak,
                   yonlendirme_url, yonlendirme_etiket_tr, tarih
            FROM yazilar ORDER BY id DESC
        """)
        for y_id, y_b_tr, y_i_tr, y_kaynak, y_url, y_et_tr, y_tarih in c.fetchall():
            col_m1, col_m2, col_m3 = st.columns([5, 1, 1])
            gosterim_baslik = temizle_eski_html_kalintisi(y_b_tr)
            col_m1.write(f"**{gosterim_baslik}** — *{y_kaynak}* ({y_tarih})")
            if col_m2.button(T["edit_btn"], key=f"tab_edit_post_{y_id}"):
                st.session_state.edit_post_id = y_id
                st.rerun()
            if col_m3.button(T["delete_btn"], key=f"tab_del_post_{y_id}"):
                c.execute("DELETE FROM yazilar WHERE id = ?", (y_id,))
                conn.commit()
                if st.session_state.edit_post_id == y_id:
                    st.session_state.edit_post_id = None
                st.toast(T["deleted_msg"])
                st.rerun()

        if st.session_state.edit_post_id is not None:
            c.execute("""
                SELECT id, baslik_tr, icerik_tr, kaynak,
                       yonlendirme_url, yonlendirme_etiket_tr
                FROM yazilar WHERE id = ?
            """, (st.session_state.edit_post_id,))
            target_post = c.fetchone()
            if target_post:
                _, eb_tr, ei_tr, ekynk, eurl, eet_tr = target_post
                st.markdown("#### ✏️ Bilgi Notunu Güncelle")
                with st.form(f"guncelle_yazi_formu_{st.session_state.edit_post_id}"):
                    new_b_tr = st.text_input("Başlık", value=temizle_eski_html_kalintisi(eb_tr or ""))
                    new_i_tr = st.text_area("İçerik", value=temizle_eski_html_kalintisi(ei_tr or ""), height=240)
                    new_kynk = st.text_input("Kaynak", value=ekynk or "")
                    new_url = st.text_input("Yönlendirme URL", value=eurl or "")
                    new_et_tr = st.text_input("Buton Etiketi", value=temizle_eski_html_kalintisi(eet_tr or ""))

                    c_save, c_cancel = st.columns(2)
                    save_upd = c_save.form_submit_button("💾 Değişiklikleri Kaydet", type="primary")
                    cancel_upd = c_cancel.form_submit_button("❌ Vazgeç")

                    if save_upd:
                        if not new_kynk.strip() or not new_i_tr.strip():
                            st.warning(T["source_warning"])
                        else:
                            with st.spinner("Güncelleniyor..."):
                                clean_nb_tr = temizle_eski_html_kalintisi(new_b_tr)
                                clean_ni_tr = temizle_eski_html_kalintisi(new_i_tr)
                                final_b_tr = clean_nb_tr or "Bilgi Notu"
                                final_i_tr = clean_ni_tr
                                final_et_tr = temizle_eski_html_kalintisi(new_et_tr)

                                c.execute('''
                                    UPDATE yazilar
                                    SET baslik_tr = ?, icerik_tr = ?, kaynak = ?,
                                        yonlendirme_url = ?, yonlendirme_etiket_tr = ?
                                    WHERE id = ?
                                ''', (
                                    final_b_tr, final_i_tr,
                                    new_kynk.strip(), new_url.strip(), final_et_tr,
                                    st.session_state.edit_post_id
                                ))
                                conn.commit()
                            st.session_state.edit_post_id = None
                            st.toast(T["updated_msg"])
                            st.rerun()

                    if cancel_upd:
                        st.session_state.edit_post_id = None
                        st.rerun()

        st.markdown("---")
        st.subheader("Kayan Şerit Sözleri")
        c.execute("SELECT id, kategori, metin_tr, kaynak FROM kayan_sozler ORDER BY id DESC")
        for s_id, s_kat, s_metin, s_kaynak in c.fetchall():
            col_s1, col_s2, col_s3 = st.columns([5, 1, 1])
            clean_s_tr = temizle_eski_html_kalintisi(s_metin or "")
            col_s1.write(f"“{clean_s_tr[:90]}...” — *{s_kaynak}*")
            if col_s2.button(T["edit_btn"], key=f"tab_edit_ticker_{s_id}"):
                st.session_state.edit_ticker_id = s_id
                st.rerun()
            if col_s3.button(T["delete_btn"], key=f"tab_del_ticker_{s_id}"):
                c.execute("DELETE FROM kayan_sozler WHERE id = ?", (s_id,))
                conn.commit()
                if st.session_state.edit_ticker_id == s_id:
                    st.session_state.edit_ticker_id = None
                st.toast(T["deleted_msg"])
                st.rerun()

        if st.session_state.edit_ticker_id is not None:
            c.execute("SELECT id, kategori, metin_tr, kaynak FROM kayan_sozler WHERE id = ?", (st.session_state.edit_ticker_id,))
            target_ticker = c.fetchone()
            if target_ticker:
                _, tk_kat, tk_tr, tk_kynk = target_ticker
                st.markdown("#### ✏️ Kayan Şerit Sözünü Güncelle")
                with st.form(f"guncelle_soz_formu_{st.session_state.edit_ticker_id}"):
                    kat_idx = T["ticker_cats"].index(tk_kat) if tk_kat in T["ticker_cats"] else 0
                    new_tk_kat = st.selectbox(T["ticker_cat_label"], T["ticker_cats"], index=kat_idx)
                    new_tk_tr = st.text_area(T["ticker_text_label"], value=temizle_eski_html_kalintisi(tk_tr or ""), height=110)
                    new_tk_kynk = st.text_input(T["ticker_source_label"], value=tk_kynk or "")

                    sc1, sc2 = st.columns(2)
                    save_tk = sc1.form_submit_button("💾 Sözü Güncelle", type="primary")
                    cancel_tk = sc2.form_submit_button("❌ Vazgeç")

                    if save_tk:
                        if not new_tk_tr.strip() or not new_tk_kynk.strip():
                            st.warning(T["source_warning"])
                        else:
                            final_tk_tr = temizle_eski_html_kalintisi(new_tk_tr)
                            c.execute('''
                                UPDATE kayan_sozler
                                SET kategori = ?, metin_tr = ?, kaynak = ?
                                WHERE id = ?
                            ''', (new_tk_kat, final_tk_tr, new_tk_kynk.strip(), st.session_state.edit_ticker_id))
                            conn.commit()
                            st.session_state.edit_ticker_id = None
                            st.toast(T["updated_msg"])
                            st.rerun()

                    if cancel_tk:
                        st.session_state.edit_ticker_id = None
                        st.rerun()

        st.markdown("---")
        st.markdown("#### 🧹 Bilgi Kirliliği Temizliği (Veritabanından Toplu Kalıcı Silme)")
        confirm_wipe = st.checkbox(T["confirm_delete_all"], key="confirm_db_wipe_chk")
        wipe_c1, wipe_c2 = st.columns(2)
        if wipe_c1.button(T["delete_all_posts_btn"], key="wipe_all_posts_btn"):
            if not confirm_wipe:
                st.warning(T["confirm_warning"])
            else:
                c.execute("DELETE FROM yazilar")
                conn.commit()
                st.session_state.edit_post_id = None
                st.toast(T["all_deleted_msg"])
                st.rerun()

        if wipe_c2.button(T["delete_all_tickers_btn"], key="wipe_all_tickers_btn"):
            if not confirm_wipe:
                st.warning(T["confirm_warning"])
            else:
                c.execute("DELETE FROM kayan_sozler")
                conn.commit()
                st.session_state.edit_ticker_id = None
                st.toast(T["all_deleted_msg"])
                st.rerun()

    st.markdown("---")

# ---------------------------------------------------------
# 11. ANA İÇERİK AKIŞI (BİLGİ NOTLARI)
# ---------------------------------------------------------
st.markdown(f"### {T['posts_section_header']}")

c.execute("""
    SELECT id, baslik_tr, icerik_tr, kaynak,
           yonlendirme_url, yonlendirme_etiket_tr, tarih
    FROM yazilar ORDER BY id DESC
""")
posts = c.fetchall()

if not posts:
    st.info(T["no_posts"])
else:
    for post in posts:
        p_id, b_tr, i_tr, kynk, url, et_tr, trh = post
        b_tr_clean = temizle_eski_html_kalintisi(b_tr or "")
        i_tr_clean = temizle_eski_html_kalintisi(i_tr or "")
        et_tr_clean = temizle_eski_html_kalintisi(et_tr or "")
        g_etiket = et_tr_clean if et_tr_clean else T["visit_link_default"]

        link_html = ""
        if url and url.strip():
            raw_url = url.strip()
            tam_url = raw_url if raw_url.startswith(("http://", "https://")) else f"https://{raw_url}"
            if tam_url.startswith(("http://", "https://")):
                link_html = (
                    f'<a href="{html.escape(tam_url)}" target="_blank" rel="noopener noreferrer" '
                    f'class="redirect-btn">{html.escape(g_etiket)} ↗️</a>'
                )

        card_html = (
            f'<div class="wisdom-card">'
            f'<div class="wisdom-title">{html.escape(b_tr_clean)}</div>'
            f'<div class="wisdom-body">{html.escape(i_tr_clean)}</div>'
            f'<div class="wisdom-meta">'
            f'<span>📚 {html.escape(T["source_prefix"])} {html.escape(kynk or "")}</span>'
            f'<span>🗓️ {html.escape(T["date_prefix"])} {html.escape(trh or "")}</span>'
            f'</div>'
            f'{link_html}'
            f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

        if st.session_state.is_author:
            btn_cols = st.columns([1.3, 1.3, 7.4])
            if btn_cols[0].button(T["edit_btn"], key=f"card_edit_{p_id}"):
                st.session_state.edit_post_id = p_id
                st.rerun()
            if btn_cols[1].button(T["delete_btn"], key=f"card_del_{p_id}"):
                c.execute("DELETE FROM yazilar WHERE id = ?", (p_id,))
                conn.commit()
                if st.session_state.edit_post_id == p_id:
                    st.session_state.edit_post_id = None
                st.toast(T["deleted_msg"])
                st.rerun()

# ---------------------------------------------------------
# 12. HUKUKİ KORUMA VE YASAL UYARI ALT BİLGİSİ
# ---------------------------------------------------------
legal_lines = html.escape(T["legal_text"]).replace("\n", "<br>")
st.markdown(
    f'<div class="legal-footer"><h4>{html.escape(T["legal_title"])}</h4><p>{legal_lines}</p></div>',
    unsafe_allow_html=True
)