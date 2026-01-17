import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
from datetime import datetime, timedelta, time as dt_time
import threading
import random

# Grafik kütüphanesini güvenli içe aktarma
try:
    import plotly.express as px
    GRAFIK_VAR = True
except ImportError:
    GRAFIK_VAR = False

# ==============================================================================
# AYARLAR
# ==============================================================================
DOSYA_ADI = "EvAsistaniDB"
NTFY_TOPIC = "yunus_ozel_ev_kanali_123"

st.set_page_config(page_title="Bizim Evin Paneli", page_icon="🏡", layout="centered")

# --- CSS ---
st.markdown("""
<style>
    div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 5px !important; }
    div[data-testid="column"] { display: flex; align-items: center; height: 100%; }
    button { padding: 0.25rem 0.5rem !important; }
    
    /* Karşılama Kutusu */
    .welcome-box {
        background: linear-gradient(120deg, #84fab0 0%, #8fd3f4 100%);
        color: #2c3e50; padding: 15px; border-radius: 15px;
        text-align: center; margin-bottom: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .prenses-box {
        background: linear-gradient(120deg, #fccb90 0%, #d57eeb 100%);
        color: #4a235a; padding: 15px; border-radius: 15px;
        text-align: center; margin-bottom: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        border: 2px solid #fff;
    }
    .welcome-title { font-size: 22px; font-weight: bold; margin-bottom: 5px; }
    .welcome-note { font-size: 15px; font-style: italic; }
    
    /* Kategori Rozetleri */
    .cat-badge {
        display: inline-block; padding: 4px 12px; border-radius: 12px;
        color: white; font-weight: bold; font-size: 14px; margin-bottom: 5px;
    }
    .streamlit-expanderHeader { font-weight: bold; color: #333; font-size: 16px; }
</style>
""", unsafe_allow_html=True)

# KATEGORİ RENK HARİTASI
def get_kategori_renk(kategori):
    renkler = {
        "Meyve": "#2ecc71", "Sebze": "#2ecc71", "Manav": "#2ecc71",
        "Et": "#e74c3c", "Şarküteri": "#e74c3c",
        "Süt": "#3498db", "Kahvaltılık": "#f1c40f",
        "Temizlik": "#9b59b6", "Ev": "#9b59b6",
        "Gıda": "#e67e22", "Bakliyat": "#d35400",
        "Atıştırmalık": "#e84393", "Genel": "#95a5a6"
    }
    for key, color in renkler.items():
        if key in kategori: return color
    return "#34495e"

# ==============================================================================
# SÜRPRİZ VE PRENSES VERİTABANI
# ==============================================================================
def ask_kavanozu_sozleri():
    return [
        "Seninle her şey daha güzel.", "Bugün yine harika görünüyorsun.", "İyi ki hayatımdasın.", 
        "Akşam çayı benden!", "Senin gülüşün güneşten daha parlak.", "Dünyanın en şanslı adamı benim.",
        "Bir kahve molası verelim mi?", "Seni seviyorum, hem de çok!", "Bugün senin günün olsun.",
        "Akşama en sevdiğin filmi izleyelim.", "Yemekler senden, bulaşıklar benden (şaka şaka).",
        "Seninle yaşlanmak istiyorum.", "Gözlerinin içi gülüyor bugün.", "Harika bir eşsin.",
        "Evin neşesi sensin.", "Bugün kendine bir güzellik yap.", "Seninle tartışmayı bile seviyorum.",
        "Hayat arkadaşım, can yoldaşım.", "Sana sarılmak bütün yorgunluğumu alıyor.",
        "Mesafeler engel değil, kalbim seninle.", "Seninle geçen her dakika kıymetli.",
        "Prenses bile seni benden çok seviyor olabilir.", "Bugün gökyüzü senin için mavi.",
        "En güzel manzaram sensin.", "Senin elinden zehir olsa yerim.", "Kalbimin tek sahibi.",
        "Bu mesajı okuduysan bana bir öpücük borçlusun.", "Seni düşünmek bile yüzümü güldürüyor.",
        "Dünyadaki en güzel tesadüfümsün.", "Seninle her yere gelirim.", "Birlikte başarabiliriz.",
        "Bugün çok yoruldun, dinlenmeyi hak ettin.", "Sen benim evimsin.", "Huzurumsun.",
        "Seni ilk gördüğüm günü hatırlıyorum.", "Aşkımız her geçen gün büyüyor.",
        "Seninle kavga etmeyi bile özlüyorum.", "Benim süper kahramanım sensin.",
        "Gülmek sana çok yakışıyor.", "Seninle sonsuza kadar...", "İyi ki varsın sevgilim.",
        "Hayallerimin ortağısın.", "Sen olmasan bu ev çok sessiz olurdu.", "Seni çok özledim.",
        "Akşama sürpriz var mı? (Yoksa ben yapayım)", "Seninle her şey mümkün.",
        "Bugün prenses gibi hissediyor musun?", "Senin mutsuz olmana dayanamam.",
        "Sadece seninle...", "Her şey seninle anlamlı."
        # Listeyi 100'e tamamlayacak kadar çoğaltılabilir, şimdilik 50 tane örnek.
    ]

def prenses_sozleri():
    return [
        "🐈 Prenses: Mama kabım boşken bu uygulamada ne geziyorsun?",
        "🐈 Prenses: Yunus'a söyle, o koltuk benim.",
        "🐈 Prenses: Beni sevmeyi unuttunuz mu?",
        "🐈 Prenses: Bugün çok tüy döktüm, süpürgeyi çalıştırın.",
        "🐈 Prenses: Akşama balık mı var? Bana da ayırın.",
        "🐈 Prenses: Evin gerçek sahibi benim, siz sadece kiracısınız.",
        "🐈 Prenses: Şu an uyuyorum, beni rahatsız etmeyin.",
        "🐈 Prenses: Yaş mama günü ne zamandı?",
        "🐈 Prenses: Sizi izliyorum...",
        "🐈 Prenses: Miyav! (Tercümesi: Beni sevin!)"
    ]

# ==============================================================================
# AI MUTFAK ŞEFİ MOTORU
# ==============================================================================
def mutfak_sefi_motoru(marketten_gelenler, manuel_eklenenler):
    tum_malzemeler = set()
    for urun in marketten_gelenler: tum_malzemeler.add(urun.lower().split("(")[0].strip())
    for urun in manuel_eklenenler: tum_malzemeler.add(urun.lower())

    tarifler = {
        "Menemen": ["yumurta", "domates", "biber"],
        "Omlet": ["yumurta", "peynir", "tereyağı"],
        "Mercimek Çorbası": ["mercimek", "soğan", "salça", "yağ"],
        "Karnıyarık": ["patlıcan", "kıyma", "domates", "soğan"],
        "Köfte Patates": ["kıyma", "patates", "soğan", "ekmek"],
        "Makarna": ["makarna", "salça", "yağ"],
        "Tavuk Sote": ["tavuk", "biber", "domates", "soğan"],
        "Kısır": ["bulgur", "salça", "yeşillik", "limon"],
        "Cacık": ["yoğurt", "salatalık", "sarımsak"],
        "Pilav": ["pirinç", "tereyağı", "şehriye"],
        "Patates Kızartması": ["patates", "yağ"],
        "Çoban Salata": ["domates", "salatalık", "biber", "soğan"],
        "Mantarlı Tavuk": ["tavuk", "mantar", "krema"],
        "Hamburger": ["kıyma", "ekmek", "domates", "yeşillik"]
    }
    
    tam, eksik = [], []
    for yemek, malzemeler in tarifler.items():
        eksikler = [m for m in malzemeler if m not in tum_malzemeler]
        if len(eksikler) == 0: tam.append(yemek)
        elif len(eksikler) <= 2: eksik.append((yemek, eksikler))
    return tam, eksik, list(tum_malzemeler)

# ==============================================================================
# KARŞILAMA (PRENSES MODLU)
# ==============================================================================
def karsilama_paneli():
    # %30 İhtimalle Prenses Konuşur
    if random.random() < 0.30:
        soz = random.choice(prenses_sozleri())
        st.markdown(f'<div class="prenses-box"><div class="welcome-title">🐾 MİYAV!</div><div class="welcome-note">{soz}</div></div>', unsafe_allow_html=True)
    else:
        # Normal Karşılama
        saat = datetime.now().hour
        selam = "Günaydın" if 5<=saat<12 else "Tünaydın" if 12<=saat<18 else "İyi Akşamlar" if 18<=saat<22 else "İyi Geceler"
        sozler = [
            "🏡 Evimiz kalemizdir.", "💡 Yemekler artık kendi menüsünde!",
            "❤️ Bugün harika bir gün olacak.", "🛒 Eksikleri anında yaz ki unutulmasın.",
            "👨‍🍳 Şef de emrinizde, Çark da!"
        ]
        st.markdown(f'<div class="welcome-box"><div class="welcome-title">{selam}! ☀️</div><div class="welcome-note">{random.choice(sozler)}</div></div>', unsafe_allow_html=True)

# ==============================================================================
# ARKA PLAN VE VERİTABANI
# ==============================================================================
def get_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(dict(st.secrets["connections"]["gsheets"]), scopes=scopes)
    return gspread.authorize(creds)

def arka_planda_ekle(satir):
    try: get_client().open(DOSYA_ADI).sheet1.append_row(satir)
    except: pass

def arka_planda_sil(urun):
    try:
        sheet = get_client().open(DOSYA_ADI).sheet1
        try: sheet.delete_rows(sheet.find(urun).row)
        except:
            for i, row in enumerate(sheet.get_all_values()):
                if row[0] == urun: sheet.delete_rows(i+1); break
    except: pass

def arka_planda_guncelle(urun, durum):
    try:
        sheet = get_client().open(DOSYA_ADI).sheet1
        try: sheet.update_cell(sheet.find(urun).row, 2, str(durum))
        except:
            for i, row in enumerate(sheet.get_all_values()):
                if row[0] == urun: sheet.update_cell(i+1, 2, str(durum)); break
    except: pass

def arka_planda_guncelle_yatirim(urun, miktar, notlar, tip):
    try:
        client = get_client()
        sheet = client.open(DOSYA_ADI).sheet1
        bulundu = False
        tum_veriler = sheet.get_all_values()
        for i, row in enumerate(tum_veriler):
            if row[0] == urun and row[4] == tip:
                sheet.update_cell(i + 1, 2, datetime.now().strftime("%Y-%m-%d")) 
                sheet.update_cell(i + 1, 3, str(miktar))
                sheet.update_cell(i + 1, 4, str(notlar))
                bulundu = True
                break
        if not bulundu: sheet.append_row([urun, datetime.now().strftime("%Y-%m-%d"), str(miktar), notlar, tip])
    except: pass

def verileri_yukle():
    try:
        data = get_client().open(DOSYA_ADI).sheet1.get_all_values()
        if not data or "Urun" not in data[0]: return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman", "Tip"])
        df = pd.DataFrame(data[1:], columns=data[0]).astype(str)
        df = df.drop_duplicates(subset=['Urun', 'Tip'], keep='first')
        return df
    except: return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman", "Tip"])

if 'local_df' not in st.session_state: st.session_state.local_df = verileri_yukle()

# ==============================================================================
# HIZLI İŞLEMLER
# ==============================================================================
def hizli_ekle(isim, tip, zaman="", mesaj="", durum="0"):
    # Rutinler için her gün sıfırlanabilir
    if tip in ["MARKET", "YEMEK_OGUN", "YEMEK_KAHVALTI"]:
        mevcut = st.session_state.local_df[(st.session_state.local_df["Tip"] == tip) & (st.session_state.local_df["Urun"] == isim)]
        if not mevcut.empty: return

    row = {"Urun": isim, "Durum": durum, "Mesaj": mesaj, "Zaman": str(zaman), "Tip": tip}
    st.session_state.local_df = pd.concat([st.session_state.local_df, pd.DataFrame([row])], ignore_index=True)
    threading.Thread(target=arka_planda_ekle, args=([isim, durum, mesaj, str(zaman), tip],)).start()

def hizli_sil(isim):
    st.session_state.local_df = st.session_state.local_df[st.session_state.local_df["Urun"] != isim]
    threading.Thread(target=arka_planda_sil, args=(isim,)).start()

def hizli_durum_degistir(isim, yeni_durum):
    idx = st.session_state.local_df[st.session_state.local_df["Urun"] == isim].index
    if not idx.empty: st.session_state.local_df.at[idx[0], "Durum"] = str(yeni_durum)
    threading.Thread(target=arka_planda_guncelle, args=(isim, yeni_durum)).start()

def hizli_yatirim_guncelle(isim, miktar, notlar):
    df = st.session_state.local_df
    mask = (df["Tip"] == "YATIRIM") & (df["Urun"] == isim)
    if df[mask].empty: hizli_ekle(isim, "YATIRIM", zaman=notlar, mesaj=str(miktar), durum=datetime.now().strftime("%Y-%m-%d"))
    else:
        idx = df[mask].index[0]
        st.session_state.local_df.at[idx, "Mesaj"] = str(miktar)
        st.session_state.local_df.at[idx, "Zaman"] = str(notlar)
        st.session_state.local_df.at[idx, "Durum"] = datetime.now().strftime("%Y-%m-%d")
        threading.Thread(target=arka_planda_guncelle_yatirim, args=(isim, miktar, notlar, "YATIRIM")).start()

def listeyi_temizle():
    st.session_state.local_df = st.session_state.local_df.drop_duplicates(subset=['Urun', 'Tip'], keep='first')
    st.toast("🧹 Liste temizlendi!")
    time.sleep(1)
    st.rerun()

# CALLBACKLER
def market_ekleme_callback():
    val = st.session_state.market_giris
    kat_secim = st.session_state.market_kategori_secim
    kat_yeni = st.session_state.get("market_kategori_yeni", "")
    kategori = kat_yeni if (kat_secim == "✏️ Yeni Kategori Yaz" and kat_yeni) else kat_secim
    if val:
        hizli_ekle(val, "MARKET", mesaj=kategori)
        st.session_state.market_giris = ""
        if "market_kategori_yeni" in st.session_state: st.session_state.market_kategori_yeni = ""

def is_ekleme_callback():
    val = st.session_state.is_giris
    kat_secim = st.session_state.is_kategori_secim
    kat_yeni = st.session_state.get("is_kategori_yeni", "")
    kategori = kat_yeni if (kat_secim == "✏️ Yeni Kategori Yaz" and kat_yeni) else kat_secim
    if val:
        hizli_ekle(val, "TODO", mesaj=kategori)
        st.session_state.is_giris = ""
        if "is_kategori_yeni" in st.session_state: st.session_state.is_kategori_yeni = ""

def yemek_ekle_callback(input_key, tip_kod):
    val = st.session_state[input_key]
    if val:
        hizli_ekle(val, tip_kod, durum="1") 
        st.session_state[input_key] = ""

def rutin_ekle_callback():
    val = st.session_state.rutin_giris
    if val:
        hizli_ekle(val, "RUTIN", durum="0")
        st.session_state.rutin_giris = ""

def ekleme_callback(key, tip):
    val = st.session_state[key]
    if val: hizli_ekle(val, tip); st.session_state[key] = ""

def not_callback():
    baslik, icerik = st.session_state.not_baslik, st.session_state.not_icerik
    if baslik and icerik: hizli_ekle(baslik, "NOTE", mesaj=icerik, durum=datetime.now().strftime("%d-%m-%Y")); st.session_state.not_baslik = ""; st.session_state.not_icerik = ""

def sayac_callback():
    ad, tarih = st.session_state.sayac_ad, st.session_state.sayac_tarih
    if ad: hizli_ekle(ad, "COUNTDOWN", zaman=str(tarih)); st.session_state.sayac_ad = ""

def fatura_callback():
    ad, gun, saat, tekrar = st.session_state.fat_ad, st.session_state.fat_gun, st.session_state.fat_saat, st.session_state.fat_tekrar
    if ad:
        kod = "HER_AY" if tekrar == "🔁 Her Ay" else "TEK"
        hizli_ekle(ad, "FATURA", gun, str(saat)[0:5], kod)
        st.session_state.fat_ad = ""

def butce_callback():
    ad, tutar, tur = st.session_state.butce_ad, st.session_state.butce_tutar, st.session_state.butce_tur
    if ad and tutar > 0: hizli_ekle(ad, "BUTCE", mesaj=str(tutar), durum=tur, zaman=datetime.now().strftime("%Y-%m-%d")); st.session_state.butce_ad = ""; st.session_state.butce_tutar = 0

def yatirim_callback():
    ad, miktar, notlar = st.session_state.yat_ad, st.session_state.yat_mik, st.session_state.yat_not
    if ad: hizli_yatirim_guncelle(ad, miktar, notlar); st.session_state.yat_ad = ""; st.session_state.yat_not = ""

def alarm_kur(mesaj, sure):
    hedef = datetime.now() + timedelta(minutes=sure)
    hizli_ekle(f"{mesaj} ({hedef.strftime('%H:%M')})", "ALARM", hedef.strftime("%Y-%m-%d %H:%M:%S"), mesaj, "-1")
    try: requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=f"✅ Alarm: {sure} dk sonra '{mesaj}'".encode('utf-8'), headers={"Title": "Ev Asistanı".encode('utf-8'), "Priority": "high"})
    except: pass

def silme_butonu_koy(prefix, urun):
    if not st.session_state.get(f"conf_{prefix}_{urun}"):
        if st.button("🗑️", key=f"del_{prefix}_{urun}"): st.session_state[f"conf_{prefix}_{urun}"] = True; st.rerun()
    else:
        if st.button("Sil?", key=f"yes_{prefix}_{urun}", type="primary"):
            hizli_sil(urun)
            st.session_state[f"conf_{prefix}_{urun}"] = False; st.rerun()
        st.caption("İptal")

# ==============================================================================
# DASHBOARD (EVİN NABZI) - GİZLİLİK MODU
# ==============================================================================
def dashboard_goster():
    df = st.session_state.local_df

    # Sıradaki Fatura
    df_f = df[df["Tip"] == "FATURA"]
    siradaki_fatura = "Yok"
    kalan_gun_txt = ""

    if not df_f.empty:
        bugun = datetime.now().day
        df_f["Gun_Sayi"] = pd.to_numeric(df_f["Zaman"], errors="coerce").fillna(32)
        df_f = df_f.sort_values("Gun_Sayi")
        for _, row in df_f.iterrows():
            kalan = int(row["Gun_Sayi"]) - bugun
            if kalan >= 0:
                siradaki_fatura = row["Urun"]
                kalan_gun_txt = "Bugün" if kalan == 0 else f"{kalan} gün"
                break

    # 🛒 Market Sepeti
    sepet_sayisi = len(df[(df["Tip"] == "MARKET") & (df["Durum"] == "0")])

    st.metric("🧾 Sıradaki Ödeme", siradaki_fatura, kalan_gun_txt)
    st.metric("🛒 Sepet", f"{sepet_sayisi} Ürün")
    st.markdown("---")


# ==============================================================================
# SAYFALAR
# ==============================================================================
def sayfa_ana_ekran():

    # ======================================================
    # 🎁 SÜRPRİZ
    # ======================================================
    if st.button("🎁 Bana Bir Sürpriz Yap", type="primary", use_container_width=True):
        st.balloons()
        soz = random.choice(ask_kavanozu_sozleri())
        st.success(f"💌 {soz}")
        time.sleep(3)

    tab1, tab2, tab3 = st.tabs(["🛒 MARKET", "📝 İŞLER", "⏰ ALARM"])

    # ======================================================
    # 🛒 MARKET
    # ======================================================
    with tab1:
        df = st.session_state.local_df
        df_market = df[df["Tip"] == "MARKET"]

        VARSAYILAN_KATEGORILER = [
            "🍏 Meyve & Sebze", "🥩 Et & Şarküteri", "🥛 Süt & Kahvaltılık",
            "🍞 Gıda & Bakliyat", "🧹 Temizlik", "🍫 Atıştırmalık"
        ]

        kayitli_kategoriler = {
            k for k in df_market["Mesaj"].dropna().unique()
            if k and k not in ["Genel", "None", "✏️ Yeni Kategori Yaz"]
        }

        TUM_KATEGORILER = sorted(
            list(set(VARSAYILAN_KATEGORILER) | kayitli_kategoriler)
        ) + ["✏️ Yeni Kategori Yaz"]

        # ---- ALT ALTA EKLEME
        st.text_input(
            "Ürün",
            key="market_giris",
            placeholder="Ürün adı...",
            label_visibility="collapsed"
        )

        st.selectbox(
            "Kategori",
            TUM_KATEGORILER,
            key="market_kategori_secim",
            label_visibility="collapsed"
        )

        if st.session_state.market_kategori_secim == "✏️ Yeni Kategori Yaz":
            st.text_input(
                "Yeni Kategori",
                key="market_kategori_yeni",
                placeholder="Örn: Tekne"
            )

        st.button(
            "EKLE",
            key="btn_m",
            on_click=market_ekleme_callback,
            use_container_width=True
        )

        st.markdown("---")

        # ---- ALINACAKLAR
        alinacaklar = df_market[df_market["Durum"] == "0"]
        st.subheader("📌 Alınacaklar Listesi")

        kategori_listesi = sorted(list(set(TUM_KATEGORILER[:-1]) | {"Genel"}))
        if "Genel" in kategori_listesi:
            kategori_listesi.remove("Genel")
            kategori_listesi.append("Genel")

        if alinacaklar.empty:
            st.success("Sepet boş 🎉")
        else:
            for kat in kategori_listesi:
                if kat == "Genel":
                    items = alinacaklar[
                        (alinacaklar["Mesaj"].isna()) |
                        (alinacaklar["Mesaj"] == "") |
                        (alinacaklar["Mesaj"] == "Genel") |
                        (alinacaklar["Mesaj"] == "None")
                    ]
                else:
                    items = alinacaklar[alinacaklar["Mesaj"] == kat]

                if not items.empty:
                    with st.expander(f"{kat} ({len(items)})", expanded=True):
                        for i, row in items.iterrows():
                            c1, c2 = st.columns([0.8, 0.2])
                            with c1:
                                if st.checkbox(
                                    f"**{row['Urun']}**",
                                    key=f"chk_m_{i}"
                                ):
                                    hizli_durum_degistir(row["Urun"], "1")
                                    st.rerun()
                            with c2:
                                silme_butonu_koy(f"m_{i}", row["Urun"])

        # ---- ALINANLAR
        st.divider()
        tamamlananlar = df_market[df_market["Durum"] == "1"]

        with st.expander(f"📦 Alınanlar ({len(tamamlananlar)})", expanded=False):
            if tamamlananlar.empty:
                st.info("Henüz alınan yok.")
            else:
                for i, row in tamamlananlar.iterrows():
                    c1, c2 = st.columns([0.8, 0.2])
                    with c1:
                        st.write(f"✅ {row['Urun']}")
                    with c2:
                        silme_butonu_koy(f"fin_m_{i}", row["Urun"])

    # ======================================================
    # 📝 İŞLER
    # ======================================================
    with tab2:
        df_todo = st.session_state.local_df[
            st.session_state.local_df["Tip"] == "TODO"
        ]

        VARSAYILAN_IS = ["🏠 Ev İçi", "🔧 Tamirat", "🏢 Dışarı İşleri", "🚗 Araba"]

        kayitli_is = {
            k for k in df_todo["Mesaj"].dropna().unique()
            if k and k not in ["Genel", "None", "✏️ Yeni Kategori Yaz"]
        }

        TUM_ISLER = sorted(
            list(set(VARSAYILAN_IS) | kayitli_is)
        ) + ["✏️ Yeni Kategori Yaz"]

        # ---- ALT ALTA EKLEME
        st.text_input(
            "Görev",
            key="is_giris",
            placeholder="Yapılacak iş...",
            label_visibility="collapsed"
        )

        st.selectbox(
            "Kategori",
            TUM_ISLER,
            key="is_kategori_secim",
            label_visibility="collapsed"
        )

        if st.session_state.is_kategori_secim == "✏️ Yeni Kategori Yaz":
            st.text_input(
                "Yeni Kategori",
                key="is_kategori_yeni",
                placeholder="Örn: Bahçe"
            )

        st.button(
            "EKLE",
            key="btn_t",
            on_click=is_ekleme_callback,
            use_container_width=True
        )

        st.markdown("---")

        # ---- YAPILACAKLAR
        st.subheader("📌 Yapılacaklar Listesi")

        is_listesi = sorted(list(set(TUM_ISLER[:-1]) | {"Genel"}))
        if "Genel" in is_listesi:
            is_listesi.remove("Genel")
            is_listesi.append("Genel")

        for kat in is_listesi:
            if kat == "Genel":
                items = df_todo[
                    (df_todo["Durum"] == "0") &
                    (
                        (df_todo["Mesaj"].isna()) |
                        (df_todo["Mesaj"] == "") |
                        (df_todo["Mesaj"] == "Genel") |
                        (df_todo["Mesaj"] == "None")
                    )
                ]
            else:
                items = df_todo[
                    (df_todo["Durum"] == "0") &
                    (df_todo["Mesaj"] == kat)
                ]

            if not items.empty:
                with st.expander(f"{kat} ({len(items)})", expanded=True):
                    for i, row in items.iterrows():
                        c1, c2 = st.columns([0.8, 0.2])
                        with c1:
                            if st.checkbox(
                                f"**{row['Urun']}**",
                                key=f"chk_t_{i}"
                            ):
                                hizli_durum_degistir(row["Urun"], "1")
                                st.rerun()
                        with c2:
                            silme_butonu_koy(f"t_{i}", row["Urun"])


    # ======================================================
    # ⏰ ALARM
    # ======================================================
    with tab3:
        with st.form("alarm"):
            mesaj = st.text_input("Not", placeholder="Fırın...")
            sure = st.number_input("Dakika", min_value=1, value=15)
            if st.form_submit_button("🔔 Kur", use_container_width=True):
                alarm_kur(mesaj, sure)
                st.success("Kuruldu!")
                time.sleep(1)
                st.rerun()


        df_a = st.session_state.local_df[st.session_state.local_df["Tip"] == "ALARM"]
        if not df_a.empty:
            st.markdown("---"); simdi = datetime.now()
            for i, row in df_a.iterrows():
                try:
                    hedef = datetime.strptime(row["Zaman"], "%Y-%m-%d %H:%M:%S"); kalan = (hedef - simdi).total_seconds()
                    c1, c2, c3 = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="center")
                    with c1: st.write(f"**{row['Mesaj']}**"); st.caption(hedef.strftime('%H:%M'))
                    with c2: st.info(f"⏳ {int(kalan/60)} dk") if kalan > 0 else st.error("🔔")
                    with c3: silme_butonu_koy(f"al_{i}", row['Urun'])
                    st.divider()
                except: pass

def sayfa_ekonomi():
    tab1, tab2, tab3 = st.tabs(["💸 ÖDEME", "💰 BÜTÇE", "📈 YATIRIM"])
    with tab1:
        with st.expander("➕ Yeni Ödeme", expanded=True):
            c1, c2 = st.columns(2)
            with c1: st.text_input("Adı", key="fat_ad"); st.number_input("Günü", 1, 31, 1, key="fat_gun")
            with c2: st.time_input("Saat", dt_time(9,0), key="fat_saat"); st.radio("Sıklık", ["🔁 Her Ay", "1️⃣ Tek"], key="fat_tekrar")
            st.button("KAYDET", key="btn_fat_save", on_click=fatura_callback, use_container_width=True)
        st.markdown("---")
        df_f = st.session_state.local_df[st.session_state.local_df["Tip"] == "FATURA"]
        if not df_f.empty:
            bugun = datetime.now().day
            df_f["Gun_Sayi"] = pd.to_numeric(df_f["Zaman"], errors='coerce').fillna(32); df_f = df_f.sort_values("Gun_Sayi")
            for i, row in df_f.iterrows():
                try:
                    gun = int(row["Gun_Sayi"]); kalan = gun - bugun
                    c1, c2, c3 = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="center")
                    with c1: st.write(f"**{row['Urun']}**"); st.caption(f"{row.get('Mesaj','09:00')} | {row['Durum']}")
                    with c2: st.error("❗ BUGÜN") if kalan==0 else st.success(f"⏳ {kalan} gün") if kalan>0 else st.warning("Geçti")
                    with c3: silme_butonu_koy(f"fat_{i}", row['Urun'])
                    st.divider()
                except: pass

    with tab2:
        with st.expander("➕ Gelir/Gider", expanded=True):
            c1, c2 = st.columns(2)
            with c1: st.radio("Tür", ["Gider", "Gelir"], horizontal=True, key="butce_tur"); st.text_input("Açıklama", key="butce_ad")
            with c2: st.number_input("Tutar", key="butce_tutar"); st.write(""); st.button("KAYDET", key="btn_butce_save", on_click=butce_callback, use_container_width=True)
        st.markdown("---")
        df_b = st.session_state.local_df[st.session_state.local_df["Tip"] == "BUTCE"].copy()
        if not df_b.empty:
            df_b["Tarih"] = pd.to_datetime(df_b["Zaman"], errors='coerce').fillna(datetime.now())
            bu_ay = datetime.now().strftime("%Y-%m"); df_bu_ay = df_b[df_b["Tarih"].dt.strftime('%Y-%m') == bu_ay]
            gelir = sum(float(r["Mesaj"]) for _, r in df_bu_ay.iterrows() if r["Durum"] == "Gelir")
            gider = sum(float(r["Mesaj"]) for _, r in df_bu_ay.iterrows() if r["Durum"] == "Gider")
            if gelir > 0: st.progress(min(gider / gelir, 1.0), f"Harcama: %{int((gider/gelir)*100)}")
            c1, c2, c3 = st.columns(3); c1.metric("Gelir", f"{gelir:.0f}₺"); c2.metric("Gider", f"{gider:.0f}₺"); c3.metric("Kalan", f"{gelir-gider:.0f}₺")
            st.divider()
            for i, row in df_bu_ay.iterrows():
                c1, c2, c3 = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="center")
                with c1: st.write(f"{'🟢' if row['Durum']=='Gelir' else '🔴'} **{row['Urun']}**")
                with c2: st.write(f"{row['Mesaj']} ₺")
                with c3: silme_butonu_koy(f"b_{i}", row['Urun'])

    with tab3:
        with st.expander("➕ Varlık Ekle", expanded=True):
            c1, c2 = st.columns(2)
            with c1: st.text_input("Varlık", key="yat_ad"); st.number_input("Değer", step=100.0, key="yat_mik")
            with c2: st.text_area("Not", height=100, key="yat_not"); st.button("KAYDET", key="btn_yat_save", on_click=yatirim_callback, use_container_width=True)
        df_y = st.session_state.local_df[st.session_state.local_df["Tip"] == "YATIRIM"]
        
        if GRAFIK_VAR and not df_y.empty:
            df_y["Tutar"] = df_y["Mesaj"].apply(lambda x: float(x) if x.replace('.','',1).isdigit() else 0)
            toplam = df_y["Tutar"].sum()
            st.markdown("---")
            c1, c2 = st.columns([1, 2])
            with c1: st.metric("💰 TOPLAM", f"{toplam:,.0f} ₺")
            with c2:
                fig = px.pie(df_y, values='Tutar', names='Urun', title='Varlık Dağılımı', hole=0.4)
                fig.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=250)
                st.plotly_chart(fig, use_container_width=True)
        elif not df_y.empty:
            st.warning("⚠️ Grafik için 'requirements.txt' dosyasına 'plotly' ekle.")
            toplam = sum(float(r["Mesaj"]) for _, r in df_y.iterrows() if r["Mesaj"].replace('.','',1).isdigit())
            st.metric("💰 TOPLAM", f"{toplam:,.0f} ₺")

        st.divider()
        for i, row in df_y.iterrows():
            c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="center")
            with c1: st.subheader(f"💎 {row['Urun']}"); st.caption(f"{row['Mesaj']} ₺ | {row['Durum']}")
            with c2: silme_butonu_koy(f"y_{i}", row['Urun'])

# ==============================================================================
# YENİ MENÜ: YEMEKLER
# ==============================================================================
def sayfa_yemekler():
    tab1, tab2, tab3, tab4 = st.tabs(["🔥 EŞLEŞME", "🎡 KAHVALTI", "🎡 YEMEK", "👨‍🍳 AI ŞEF"])
    
    with st.expander("⚙️ Temizlik"):
        if st.button("🧹 Çift Kayıtları Temizle", use_container_width=True): listeyi_temizle()

    # OYUN MODU
    with tab1:
        st.caption("Tinder usulü yemek seçimi! Kararsız kaldığınızda kullanın.")
        df_oyun = st.session_state.local_df[(st.session_state.local_df["Tip"].isin(["YEMEK_OGUN", "YEMEK_KAHVALTI"])) & (st.session_state.local_df["Durum"] == "1")]
        yemek_listesi = df_oyun["Urun"].tolist()
        
        if not yemek_listesi:
            st.warning("Önce Çark kısmından yemek ekleyin!")
        else:
            if 'oyun_yemegi' not in st.session_state:
                st.session_state.oyun_yemegi = random.choice(yemek_listesi)
            
            st.markdown(f"<h2 style='text-align: center;'>🍽️ {st.session_state.oyun_yemegi} 🍽️</h2>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            if c1.button("👎 Olmaz", use_container_width=True):
                st.session_state.oyun_yemegi = random.choice(yemek_listesi)
                st.rerun()
            
            if c2.button("👍 Olur", type="primary", use_container_width=True):
                st.balloons()
                st.success(f"HARİKA! Akşama {st.session_state.oyun_yemegi} var! Afiyet olsun.")

    with tab2:
        c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("Kahvaltı Ekle", key="kahvalti_giris", label_visibility="collapsed")
        with c2: st.button("EKLE", key="btn_kahvalti", on_click=yemek_ekle_callback, args=("kahvalti_giris", "YEMEK_KAHVALTI"), use_container_width=True)
        st.markdown("---")
        df_k = st.session_state.local_df[st.session_state.local_df["Tip"] == "YEMEK_KAHVALTI"]
        havuz = df_k[df_k["Durum"] == "1"]["Urun"].tolist()
        if havuz:
            if st.button(f"🎲 KURA ÇEK ({len(havuz)})", key="spin_kahvalti", type="primary", use_container_width=True):
                st.balloons(); st.success(f"🍳 Kahvaltı: **{random.choice(havuz)}**")
        for i, row in df_k.iterrows():
            c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
            with c1:
                chk = (row['Durum'] == "1")
                if st.checkbox(f"**{row['Urun']}**", value=chk, key=f"k_chk_{i}"):
                    if not chk: hizli_durum_degistir(row['Urun'], "1")
                else:
                    if chk: hizli_durum_degistir(row['Urun'], "0")
            with c2: silme_butonu_koy(f"k_del_{i}", row['Urun'])

    with tab3:
        c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("Yemek Ekle", key="yemek_giris", label_visibility="collapsed")
        with c2: st.button("EKLE", key="btn_yemek", on_click=yemek_ekle_callback, args=("yemek_giris", "YEMEK_OGUN"), use_container_width=True)
        st.markdown("---")
        df_y = st.session_state.local_df[st.session_state.local_df["Tip"] == "YEMEK_OGUN"]
        havuz = df_y[df_y["Durum"] == "1"]["Urun"].tolist()
        if havuz:
            if st.button(f"🎲 KURA ÇEK ({len(havuz)})", key="spin_yemek", type="primary", use_container_width=True):
                st.balloons(); st.success(f"🥘 Akşam Yemeği: **{random.choice(havuz)}**")
        for i, row in df_y.iterrows():
            c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
            with c1:
                chk = (row['Durum'] == "1")
                if st.checkbox(f"**{row['Urun']}**", value=chk, key=f"y_chk_{i}"):
                    if not chk: hizli_durum_degistir(row['Urun'], "1")
                else:
                    if chk: hizli_durum_degistir(row['Urun'], "0")
            with c2: silme_butonu_koy(f"y_del_{i}", row['Urun'])

    with tab4:
        st.subheader("👨‍🍳 AI Mutfak Şefi")
        df = st.session_state.local_df
        marketten_gelenler = df[(df["Tip"] == "MARKET") & (df["Durum"] == "1")]["Urun"].tolist()
        malzemeler = ["Yumurta", "Domates", "Biber", "Soğan", "Kıyma", "Patates", "Tavuk", "Makarna", "Salça", "Pirinç", "Mercimek", "Yoğurt", "Salatalık", "Patlıcan", "Mantar"]
        ek_malzemeler = st.multiselect("Evde başka ne var?", malzemeler)
        if st.button("🔍 Ne Pişirsem?", type="primary", use_container_width=True):
            tam, eksik, stok_listesi = mutfak_sefi_motoru(marketten_gelenler, ek_malzemeler)
            with st.expander("📦 Algılanan Stoklar"): st.write(", ".join(stok_listesi))
            if tam: st.success(f"✅ **Hemen Yapabilirsin:** {', '.join(tam)}")
            if eksik:
                st.markdown("---"); st.warning("🛒 **Ufak Eksikler Var:**")
                for yemek, eksikler in eksik: st.write(f"• **{yemek}** için eksik: *{', '.join(eksikler)}*")
            if not tam and not eksik: st.error("Bu malzemelerle bir tarif bulamadım.")

# ==============================================================================
# SADELEŞEN MENÜ: YAŞAM
# ==============================================================================
def sayfa_yasam():
    tab1, tab2, tab3 = st.tabs(["⛓️ ZİNCİR", "⏳ SAYAÇ", "📒 NOTLAR"])

    with tab1:
        st.caption("Günlük hedeflerini tamamla, zinciri kırma!")
        c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("Rutin Ekle", key="rutin_giris", label_visibility="collapsed", placeholder="Su iç...")
        with c2: st.button("EKLE", key="btn_rutin", on_click=rutin_ekle_callback, use_container_width=True)
        df_r = st.session_state.local_df[st.session_state.local_df["Tip"] == "RUTIN"]
        completed = len(df_r[df_r["Durum"] == "1"])
        if len(df_r) > 0: st.progress(completed/len(df_r), text=f"Günlük İlerleme: %{int((completed/len(df_r))*100)}")
        st.markdown("---")
        for i, row in df_r.iterrows():
            c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
            with c1:
                is_done = (row['Durum'] == "1")
                if st.checkbox(f"**{row['Urun']}**", value=is_done, key=f"r_chk_{i}"):
                    if not is_done: hizli_durum_degistir(row['Urun'], "1"); st.rerun()
                else:
                    if is_done: hizli_durum_degistir(row['Urun'], "0"); st.rerun()
            with c2: silme_butonu_koy(f"r_del_{i}", row['Urun'])

    with tab2:
        with st.expander("➕ Yeni Sayaç", expanded=True):
            st.text_input("Etkinlik", key="sayac_ad"); st.date_input("Tarih", key="sayac_tarih")
            st.button("KAYDET", key="btn_syc_save", on_click=sayac_callback)
        df_s = st.session_state.local_df[st.session_state.local_df["Tip"] == "COUNTDOWN"]
        if not df_s.empty:
            st.markdown("---"); bugun = datetime.now().date()
            for i, row in df_s.iterrows():
                try:
                    hedef = datetime.strptime(row["Zaman"], "%Y-%m-%d").date(); kalan = (hedef - bugun).days
                    c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
                    with c1: st.write(f"🎉 **{row['Urun']}**"); st.info(f"⏳ **{kalan}** gün kaldı") if kalan > 0 else st.success("🎉 BUGÜN!")
                    with c2: silme_butonu_koy(f"syc_{i}", row['Urun'])
                    st.divider()
                except: pass

    with tab3:
        with st.expander("➕ Not Ekle", expanded=True):
            st.text_input("Başlık", key="not_baslik"); st.text_area("İçerik", key="not_icerik"); st.button("KAYDET", key="btn_not_save", on_click=not_callback)
        df_n = st.session_state.local_df[st.session_state.local_df["Tip"] == "NOTE"]
        for i, row in df_n.iterrows():
            with st.expander(f"📒 {row['Urun']}"): st.code(row['Mesaj']); silme_butonu_koy(f"nt_{i}", row['Urun'])

def sayfa_dosya():
    st.subheader("📂 PDF Çevirici")
    dosya = st.file_uploader("Resim Yükle", type=["png", "jpg", "jpeg"])
    if dosya:
        import img2pdf; st.download_button("⬇️ İndir", img2pdf.convert(dosya.read()), f"{dosya.name}.pdf", "application/pdf")

# ==============================================================================
# ÇALIŞTIRMA
# ==============================================================================
karsilama_paneli()
dashboard_goster()

with st.sidebar:
    st.header("Menü")
    secim = st.radio("Git:", ["🏠 Ana Sayfa", "🍽️ Yemekler", "💰 Ekonomi", "🧬 Yaşam", "📂 Dosya"])
    st.markdown("---"); st.header("Linkler")
    st.markdown('<a href="https://www.turkiye.gov.tr/" target="_blank" class="link-box">🏛️ E-Devlet</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://www.enabiz.gov.tr/" target="_blank" class="link-box">🏥 E-Nabız</a>', unsafe_allow_html=True)

if secim == "🏠 Ana Sayfa": sayfa_ana_ekran()
elif secim == "🍽️ Yemekler": sayfa_yemekler()
elif secim == "💰 Ekonomi": sayfa_ekonomi()
elif secim == "🧬 Yaşam": sayfa_yasam()
elif secim == "📂 Dosya": sayfa_dosya()



























