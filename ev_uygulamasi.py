import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import json
from datetime import datetime, timedelta, time as dt_time
import threading
import random
import streamlit.components.v1 as components

# Grafik kütüphanesi kontrolü
try:
    import plotly.express as px
    GRAFIK_VAR = True
except ImportError:
    GRAFIK_VAR = False

# ==============================================================================
# ⚙️ AYARLAR VE VERİTABANI
# ==============================================================================
DOSYA_ADI = "EvAsistaniDB"
NTFY_TOPIC = "yunus_ozel_ev_kanali_123"

st.set_page_config(page_title="Bizim Evin Paneli", page_icon="🏡", layout="centered")

# ==============================================================================
# 🖼️ CSS VE JAVASCRIPT (V52 - ZORLA YAN YANA TUTMA & FIXLER)
# ==============================================================================
APP_ICON_URL = "https://cdn-icons-png.flaticon.com/512/2942/2942789.png"

# 1. HTML HEAD (İkonlar için Meta Etiketleri)
st.markdown(f"""
    <head>
        <link rel="icon" href="{APP_ICON_URL}">
        <link rel="apple-touch-icon" href="{APP_ICON_URL}">
        <link rel="shortcut icon" href="{APP_ICON_URL}">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-title" content="Ev Asistanı">
    </head>
""", unsafe_allow_html=True)

# 2. CSS (ZORLA YAN YANA TUTMA)
st.markdown("""
    <style>
    /* 1. SÜTUNLARI ASLA ALT SATIRA İNDİRME (KRİTİK KOD) */
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important; /* Asla sarma */
        align-items: center !important;
        gap: 5px !important;
    }
    
    /* 2. BUTON BOYUTLARI VE HİZALAMA */
    button {
        padding: 0rem 0.5rem !important;
        min-height: 40px !important;
        height: 40px !important;
        line-height: 1 !important;
        white-space: nowrap !important;
    }
    
    /* 3. İSİM SÜTUNU ÇOK UZUNSA EKANDAN TAŞMASIN, ... KOYSUN */
    div[data-testid="column"]:nth-of-type(1) {
        min-width: 0; /* Flexbox taşmasını önler */
        flex-grow: 1;
        overflow: hidden;
    }
    
    /* GÖRSEL KUTULAR */
    .welcome-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; padding: 20px; border-radius: 15px;
        text-align: center; margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .prenses-box {
        background: linear-gradient(135deg, #f6d365 0%, #fda085 100%);
        color: #5e4a18; padding: 20px; border-radius: 15px;
        text-align: center; margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        border: 2px solid white;
    }
    .welcome-title { font-size: 24px; font-weight: bold; margin-bottom: 5px; }
    .welcome-note { font-size: 16px; font-style: italic; opacity: 0.9; }
    .category-line { height: 4px; border-radius: 2px; margin-bottom: 8px; }
    </style>
""", unsafe_allow_html=True)

# 3. JAVASCRIPT (YUKARI ÇIK BUTONU - PARENT WINDOW FIX)
components.html("""
<script>
    function topaGit() {
        // Iframe içinden ana pencereyi kaydır
        window.parent.scrollTo({top: 0, behavior: 'smooth'});
    }
</script>
<button onclick="topaGit()" style="
    position: fixed; bottom: 20px; left: 20px;
    background-color: #FF4B4B; color: white;
    border: none; padding: 15px; border-radius: 50%;
    font-size: 20px; cursor: pointer;
    box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
    z-index: 999999; display: flex; align-items: center; justify-content: center; width: 50px; height: 50px;">
    ⬆️
</button>
""", height=0)

# ==============================================================================
# 🧠 İÇERİK KÜTÜPHANESİ
# ==============================================================================
def get_kategori_renk(kategori):
    renkler = {
        "Meyve": "#2ecc71", "Sebze": "#27ae60", "Manav": "#2ecc71",
        "Et": "#c0392b", "Şarküteri": "#e74c3c", "Tavuk": "#d35400",
        "Süt": "#3498db", "Kahvaltılık": "#f1c40f", "Peynir": "#f39c12",
        "Temizlik": "#8e44ad", "Ev": "#9b59b6", "Deterjan": "#8e44ad",
        "Gıda": "#e67e22", "Bakliyat": "#d35400", "Makarna": "#e67e22",
        "Atıştırmalık": "#e84393", "Cips": "#ff7979", "Çikolata": "#e84393",
        "İçecek": "#00cec9", "Su": "#74b9ff", "Genel": "#95a5a6"
    }
    for key, color in renkler.items():
        if key in kategori: return color
    return "#34495e"

def ask_kavanozu_sozleri():
    return [
        "Seninle her şey daha güzel.", "Bugün yine harika görünüyorsun.", "İyi ki hayatımdasın.", 
        "Akşam çayı benden!", "Senin gülüşün güneşten daha parlak.", "Dünyanın en şanslı adamı benim.",
        "Bir kahve molası verelim mi?", "Seni seviyorum, hem de çok!", "Bugün senin günün olsun.",
        "Akşama en sevdiğin filmi izleyelim.", "Harika bir eşsin.", "Evin neşesi sensin.",
        "Seninle yaşlanmak istiyorum.", "Gözlerinin içine bakınca huzur buluyorum.", "Sen benim en güzel şansımsın."
    ]

def prenses_sozleri():
    return [
        "🐈 Prenses: Mama kabım boşken bu uygulamada ne geziyorsun?",
        "🐈 Prenses: Yunus'a söyle, o koltuk benim.",
        "🐈 Prenses: Beni sevmeyi unuttunuz mu?",
        "🐈 Prenses: Akşama balık mı var? Bana da ayırın.",
        "🐈 Prenses: Miyav! (Tercümesi: Beni sevin!)",
        "🐈 Prenses: Bugün çok tüy döktüm, evi süpürür müsün?",
        "🐈 Prenses: O lazeri bir gün yakalayacağım!",
        "🐈 Prenses: Uyuyorum, ses yapmayın.",
        "🐈 Prenses: Kutular neden bu kadar güzel?"
    ]

# ==============================================================================
# 🔄 VERİTABANI VE İŞLEMLER
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

def arka_planda_guncelle(eski_ad, yeni_ad=None, yeni_durum=None):
    try:
        sheet = get_client().open(DOSYA_ADI).sheet1
        cell = sheet.find(eski_ad)
        if yeni_durum is not None:
            sheet.update_cell(cell.row, 2, str(yeni_durum))
        if yeni_ad is not None:
            sheet.update_cell(cell.row, 1, str(yeni_ad))
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

@st.cache_data(ttl=60)
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
# ⚡ HIZLI İŞLEMLER
# ==============================================================================
def hizli_ekle(isim_veya_liste, tip, zaman="", mesaj="", durum="0"):
    if "," in isim_veya_liste:
        urunler = [u.strip() for u in isim_veya_liste.split(",")]
    else:
        urunler = [isim_veya_liste.strip()]

    for isim in urunler:
        if not isim: continue
        if tip in ["MARKET", "YEMEK_OGUN", "YEMEK_KAHVALTI"]:
            mevcut = st.session_state.local_df[(st.session_state.local_df["Tip"] == tip) & (st.session_state.local_df["Urun"] == isim)]
            if not mevcut.empty: continue

        row = {"Urun": isim, "Durum": durum, "Mesaj": mesaj, "Zaman": str(zaman), "Tip": tip}
        st.session_state.local_df = pd.concat([st.session_state.local_df, pd.DataFrame([row])], ignore_index=True)
        threading.Thread(target=arka_planda_ekle, args=([isim, durum, mesaj, str(zaman), tip],)).start()

def hizli_sil(isim):
    st.session_state.local_df = st.session_state.local_df[st.session_state.local_df["Urun"] != isim]
    threading.Thread(target=arka_planda_sil, args=(isim,)).start()

def hizli_duzenle(eski_isim, yeni_isim):
    if not yeni_isim or eski_isim == yeni_isim: return
    idx = st.session_state.local_df[st.session_state.local_df["Urun"] == eski_isim].index
    if not idx.empty:
        st.session_state.local_df.at[idx[0], "Urun"] = yeni_isim
        st.success(f"✅ '{eski_isim}' -> '{yeni_isim}' olarak değişti.")
    threading.Thread(target=arka_planda_guncelle, args=(eski_isim, yeni_isim, None)).start()

def hizli_durum_degistir(isim, yeni_durum):
    idx = st.session_state.local_df[st.session_state.local_df["Urun"] == isim].index
    if not idx.empty: st.session_state.local_df.at[idx[0], "Durum"] = str(yeni_durum)
    threading.Thread(target=arka_planda_guncelle, args=(isim, None, yeni_durum)).start()

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

# ==============================================================================
# UI CALLBACKLER
# ==============================================================================
def market_ekleme_callback():
    val = st.session_state.market_giris
    kat_secim = st.session_state.market_kategori_secim
    kat_yeni = st.session_state.get("market_kategori_yeni", "")
    kategori = kat_yeni if (kat_secim == "✏️ Yeni Kategori Yaz" and kat_yeni) else kat_secim
    if val:
        hizli_ekle(val, "MARKET", mesaj=kategori)
        st.session_state.market_giris = ""

def is_ekleme_callback():
    val = st.session_state.is_giris
    kat_secim = st.session_state.is_kategori_secim
    kategori = st.session_state.get("is_kategori_yeni", "") if kat_secim == "✏️ Yeni Kategori Yaz" else kat_secim
    if val:
        hizli_ekle(val, "TODO", mesaj=kategori)
        st.session_state.is_giris = ""

def yemek_ekle_callback(input_key, tip_kod):
    val = st.session_state[input_key]
    if val: hizli_ekle(val, tip_kod, durum="1"); st.session_state[input_key] = ""

def rutin_ekle_callback():
    val = st.session_state.rutin_giris
    if val: hizli_ekle(val, "RUTIN", durum="0"); st.session_state.rutin_giris = ""

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

def mutfak_sefi_motoru(marketten_gelenler, manuel_eklenenler):
    tum_malzemeler = set()
    for urun in marketten_gelenler: tum_malzemeler.add(urun.lower().split("(")[0].strip())
    for urun in manuel_eklenenler: tum_malzemeler.add(urun.lower())
    tarifler = {"Menemen": ["yumurta", "domates", "biber"], "Omlet": ["yumurta", "peynir", "tereyağı"], "Makarna": ["makarna", "salça", "yağ"], "Köfte": ["kıyma", "soğan", "ekmek"], "Kısır": ["bulgur", "salça", "yeşillik"], "Patates Kızartması": ["patates", "yağ"], "Tavuk Sote": ["tavuk", "biber", "domates"], "Mercimek Çorbası": ["mercimek", "soğan", "salça"]}
    tam, eksik = [], []
    for yemek, malzemeler in tarifler.items():
        eksikler = [m for m in malzemeler if m not in tum_malzemeler]
        if len(eksikler) == 0: tam.append(yemek)
        elif len(eksikler) <= 2: eksik.append((yemek, eksikler))
    return tam, eksik, list(tum_malzemeler)

def karsilama_paneli():
    saat = datetime.now().hour
    if 5 <= saat < 12: mesaj = "Günaydın! ☀️"
    elif 12 <= saat < 18: mesaj = "Tünaydın! 🌤️"
    elif 18 <= saat < 22: mesaj = "İyi Akşamlar! 🌙"
    else: mesaj = "İyi Geceler! 🦉"
    
    if random.random() < 0.25:
        soz = random.choice(prenses_sozleri())
        st.markdown(f'<div class="prenses-box"><div class="welcome-title">🐾 MİYAV!</div><div class="welcome-note">{soz}</div></div>', unsafe_allow_html=True)
    else:
        motivasyon = ["Bugün harika şeyler başarabilirsin.", "Evimiz, kalemiz.", "Listeler hazır, sen hazırsan başlayalım.", "Bir kahve al ve günün tadını çıkar.", "Planlı hayat, stressiz hayattır.", "Bugün senin günün!"]
        st.markdown(f'<div class="welcome-box"><div class="welcome-title">{mesaj}</div><div class="welcome-note">{random.choice(motivasyon)}</div></div>', unsafe_allow_html=True)

def dashboard_goster():
    df = st.session_state.local_df
    df_f = df[df["Tip"] == "FATURA"]
    siradaki_fatura = "Yok"; kalan_gun_txt = ""
    if not df_f.empty:
        bugun = datetime.now().day
        df_f["Gun_Sayi"] = pd.to_numeric(df_f["Zaman"], errors='coerce').fillna(32)
        df_f = df_f.sort_values("Gun_Sayi")
        for _, row in df_f.iterrows():
            kalan = int(row["Gun_Sayi"]) - bugun
            if kalan >= 0:
                siradaki_fatura = row["Urun"]
                kalan_gun_txt = "Bugün" if kalan == 0 else f"{kalan} gün"
                break
    sepet_sayisi = len(df[(df["Tip"] == "MARKET") & (df["Durum"] == "0")])
    c1, c2 = st.columns(2)
    c1.metric("🧾 Sıradaki Ödeme", siradaki_fatura, kalan_gun_txt)
    c2.metric("🛒 Sepet", f"{sepet_sayisi} Ürün")
    st.markdown("---")

# ==============================================================================
# V52: DÜZENLEME VE LİSTELEME MODÜLÜ (YAN YANA GARANTİ)
# ==============================================================================
def liste_satiri_olustur(prefix, i, row, checkbox_var=True):
    if st.session_state.get(f"editing_{prefix}") == row['Urun']:
        with st.form(key=f"edit_form_{prefix}_{i}"):
            yeni_ad = st.text_input("Düzenle:", value=row['Urun'])
            c_save, c_cancel = st.columns(2)
            if c_save.form_submit_button("💾 Kaydet"):
                hizli_duzenle(row['Urun'], yeni_ad)
                st.session_state[f"editing_{prefix}"] = None
                st.rerun()
            if c_cancel.form_submit_button("❌ İptal"):
                st.session_state[f"editing_{prefix}"] = None
                st.rerun()
    else:
        # SÜTUN ORANLARI (Mobilde yan yana sığması için)
        c1, c2, c3 = st.columns([0.65, 0.17, 0.18], gap="small", vertical_alignment="center")
        
        with c1:
            if checkbox_var:
                if st.checkbox(f"**{row['Urun']}**", key=f"chk_{prefix}_{i}"):
                    hizli_durum_degistir(row['Urun'], "1")
                    st.rerun()
            else:
                st.markdown(f"**{row['Urun']}**")

        with c2:
            if st.button("✏️", key=f"ed_{prefix}_{i}"):
                st.session_state[f"editing_{prefix}"] = row['Urun']
                st.rerun()

        with c3:
            if not st.session_state.get(f"conf_{prefix}_{i}"):
                if st.button("🗑️", key=f"del_{prefix}_{i}"): 
                    st.session_state[f"conf_{prefix}_{i}"] = True
                    st.rerun()
            else:
                if st.button("Sil?", key=f"yes_{prefix}_{i}", type="primary"):
                    hizli_sil(row['Urun'])
                    st.session_state[f"conf_{prefix}_{i}"] = False
                    st.rerun()

def liste_satiri_geri_al(prefix, i, row):
    c1, c2, c3 = st.columns([0.65, 0.17, 0.18], gap="small", vertical_alignment="center")
    with c1:
        if st.button(f"➕ {row['Urun']}", key=f"back_{prefix}_{i}", use_container_width=True):
            hizli_durum_degistir(row['Urun'], "0")
            st.rerun()
    with c2:
         if st.button("✏️", key=f"ed_fin_{prefix}_{i}"):
                st.session_state[f"editing_{prefix}"] = row['Urun']
                st.rerun()
    with c3:
        if st.button("🗑️", key=f"del_fin_{prefix}_{i}"):
            hizli_sil(row['Urun'])
            st.rerun()

# ==============================================================================
# SAYFALAR
# ==============================================================================
def sayfa_ana_ekran():
    if st.button("🎁 Sürpriz Kutusu", type="primary", use_container_width=True):
        st.balloons(); soz = random.choice(ask_kavanozu_sozleri()); st.success(f"💌 {soz}"); time.sleep(4)

    tab1, tab2, tab3 = st.tabs(["🛒 MARKET", "📝 İŞLER", "⏰ ALARM"])
    
    with tab1:
        df = st.session_state.local_df
        df_market = df[df["Tip"] == "MARKET"]
        VARSAYILAN_KATEGORILER = ["🍏 Meyve & Sebze", "🥩 Et & Şarküteri", "🥛 Süt & Kahvaltılık", "🍞 Gıda & Bakliyat", "🧹 Temizlik", "🍫 Atıştırmalık"]
        kayitli_kategoriler = {k for k in set(df_market["Mesaj"].dropna().unique()) if k and k not in ["Genel", "None", "✏️ Yeni Kategori Yaz"]}
        TUM_KATEGORILER = sorted(list(set(VARSAYILAN_KATEGORILER) | kayitli_kategoriler)) + ["✏️ Yeni Kategori Yaz"]
        
        c1, c2, c3 = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("Ürün (Virgülle çoklu ekle)", key="market_giris", label_visibility="collapsed", placeholder="Domates, Biber...")
        with c2: st.selectbox("Kategori", TUM_KATEGORILER, key="market_kategori_secim", label_visibility="collapsed")
        with c3: st.button("EKLE", key="btn_m", on_click=market_ekleme_callback, use_container_width=True)
        if st.session_state.market_kategori_secim == "✏️ Yeni Kategori Yaz": st.text_input("Yeni Kategori Adı:", key="market_kategori_yeni")
        st.markdown("---")
        
        alinacaklar = df_market[df_market["Durum"] == "0"]
        st.subheader("📌 Alınacaklar Listesi")
        if alinacaklar.empty: st.info("Sepetiniz boş.")
        
        kategori_listesi = sorted(list(set(TUM_KATEGORILER[:-1]) | {"Genel"}))
        if "Genel" in kategori_listesi: kategori_listesi.remove("Genel"); kategori_listesi.append("Genel")

        for kat in kategori_listesi:
            if kat == "Genel": items = alinacaklar[(alinacaklar["Mesaj"] == "") | (alinacaklar["Mesaj"] == "Genel") | (alinacaklar["Mesaj"] == "None")]
            else: items = alinacaklar[alinacaklar["Mesaj"] == kat]
            
            if not items.empty:
                renk = get_kategori_renk(kat)
                with st.expander(f"{kat} ({len(items)})", expanded=True):
                    st.markdown(f"<div class='category-line' style='background-color:{renk};'></div>", unsafe_allow_html=True)
                    for i, row in items.iterrows():
                        liste_satiri_olustur("m", i, row)

        st.divider()
        tamamlananlar = df_market[df_market["Durum"] == "1"]
        with st.expander(f"📦 Geçmiş / Alınanlar ({len(tamamlananlar)})", expanded=False):
            if not tamamlananlar.empty:
                for i, row in tamamlananlar.iterrows():
                    liste_satiri_geri_al("m", i, row)

    with tab2:
        df_todo = st.session_state.local_df[st.session_state.local_df["Tip"] == "TODO"]
        VARSAYILAN_IS = ["🏠 Ev İçi", "🔧 Tamirat", "🏢 Dışarı İşleri", "🚗 Araba"]
        kayitli_is = {k for k in set(df_todo["Mesaj"].dropna().unique()) if k and k not in ["Genel", "None", "✏️ Yeni Kategori Yaz"]}
        TUM_ISLER = sorted(list(set(VARSAYILAN_IS) | kayitli_is)) + ["✏️ Yeni Kategori Yaz"]
        c1, c2, c3 = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("Görev", key="is_giris", label_visibility="collapsed", placeholder="Yapılacak iş...")
        with c2: st.selectbox("Kategori", TUM_ISLER, key="is_kategori_secim", label_visibility="collapsed")
        with c3: st.button("EKLE", key="btn_t", on_click=is_ekleme_callback, use_container_width=True)
        if st.session_state.is_kategori_secim == "✏️ Yeni Kategori Yaz": st.text_input("Yeni Kategori Adı:", key="is_kategori_yeni")
        st.markdown("---")
        
        is_listesi = sorted(list(set(TUM_ISLER[:-1]) | {"Genel"}))
        if "Genel" in is_listesi: is_listesi.remove("Genel"); is_listesi.append("Genel")
        
        st.subheader("📌 Yapılacaklar Listesi")
        for kat in is_listesi:
            if kat == "Genel": items = df_todo[(df_todo["Durum"] == "0") & ((df_todo["Mesaj"] == "") | (df_todo["Mesaj"] == "Genel") | (df_todo["Mesaj"] == "None"))]
            else: items = df_todo[(df_todo["Durum"] == "0") & (df_todo["Mesaj"] == kat)]
            if not items.empty:
                renk = get_kategori_renk(kat)
                with st.expander(f"{kat} ({len(items)})", expanded=True):
                    st.markdown(f"<div class='category-line' style='background-color:{renk};'></div>", unsafe_allow_html=True)
                    for i, row in items.iterrows():
                        liste_satiri_olustur("t", i, row)

    with tab3:
        with st.form("alarm"):
            mesaj = st.text_input("Not", placeholder="Fırın...")
            sure = st.number_input("Dakika", min_value=1, value=15)
            if st.form_submit_button("🔔 Kur", use_container_width=True): alarm_kur(mesaj, sure); st.success("Kuruldu!"); time.sleep(1); st.rerun()
        df_a = st.session_state.local_df[st.session_state.local_df["Tip"] == "ALARM"]
        if not df_a.empty:
            st.markdown("---"); simdi = datetime.now()
            for i, row in df_a.iterrows():
                try:
                    hedef = datetime.strptime(row["Zaman"], "%Y-%m-%d %H:%M:%S"); kalan = (hedef - simdi).total_seconds()
                    c1, c2, c3 = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="center")
                    with c1: st.write(f"**{row['Mesaj']}**"); st.caption(hedef.strftime('%H:%M'))
                    with c2: st.info(f"⏳ {int(kalan/60)} dk") if kalan > 0 else st.error("🔔")
                    with c3: 
                        if st.button("🗑️", key=f"del_al_{i}"): hizli_sil(row['Urun']); st.rerun()
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
                    with c3: 
                        if st.button("🗑️", key=f"del_fat_{i}"): hizli_sil(row['Urun']); st.rerun()
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
                with c3: 
                    if st.button("🗑️", key=f"del_b_{i}"): hizli_sil(row['Urun']); st.rerun()
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
            toplam = sum(float(r["Mesaj"]) for _, r in df_y.iterrows() if r["Mesaj"].replace('.','',1).isdigit())
            st.metric("💰 TOPLAM", f"{toplam:,.0f} ₺")
        st.divider()
        for i, row in df_y.iterrows():
            c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="center")
            with c1: st.subheader(f"💎 {row['Urun']}"); st.caption(f"{row['Mesaj']} ₺ | {row['Durum']}")
            with c2: 
                if st.button("🗑️", key=f"del_y_{i}"): hizli_sil(row['Urun']); st.rerun()

def sayfa_yemekler():
    tab1, tab2, tab3, tab4 = st.tabs(["🔥 EŞLEŞME", "🎡 KAHVALTI", "🎡 YEMEK", "👨‍🍳 AI ŞEF"])
    with st.expander("⚙️ Temizlik"):
        if st.button("🧹 Çift Kayıtları Temizle", use_container_width=True): listeyi_temizle()
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
            liste_satiri_olustur("k", i, row)
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
            liste_satiri_olustur("y", i, row)
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
            liste_satiri_olustur("r", i, row)
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
                    with c2: 
                        if st.button("🗑️", key=f"del_syc_{i}"): hizli_sil(row['Urun']); st.rerun()
                    st.divider()
                except: pass
    with tab3:
        with st.expander("➕ Not Ekle", expanded=True):
            st.text_input("Başlık", key="not_baslik"); st.text_area("İçerik", key="not_icerik"); st.button("KAYDET", key="btn_not_save", on_click=not_callback)
        df_n = st.session_state.local_df[st.session_state.local_df["Tip"] == "NOTE"]
        for i, row in df_n.iterrows():
            with st.expander(f"📒 {row['Urun']}"): st.code(row['Mesaj']); 
            if st.button("🗑️", key=f"del_nt_{i}"): hizli_sil(row['Urun']); st.rerun()

def sayfa_dosya():
    st.subheader("📂 PDF Çevirici")
    dosya = st.file_uploader("Resim Yükle", type=["png", "jpg", "jpeg"])
    if dosya:
        import img2pdf; st.download_button("⬇️ İndir", img2pdf.convert(dosya.read()), f"{dosya.name}.pdf", "application/pdf")

def sayfa_cihazlar():
    st.markdown("### 🎮 Akıllı Ev")
    st.info("Donanım/Tuya bağlantısı geçici olarak devre dışı bırakılmıştır. (Geliştirme Modu)")

# ==============================================================================
# ÇALIŞTIRMA
# ==============================================================================
karsilama_paneli()
dashboard_goster()

with st.sidebar:
    st.header("Menü")
    secim = st.radio("Git:", ["🏠 Ana Sayfa", "🍽️ Yemekler", "💰 Ekonomi", "🧬 Yaşam", "📂 Dosya", "🎮 Cihazlar"])
    st.markdown("---"); st.header("Linkler")
    st.markdown('<a href="https://www.turkiye.gov.tr/" target="_blank" style="text-decoration:none; color:#333;">🏛️ E-Devlet</a>', unsafe_allow_html=True)
    st.markdown('<br><a href="https://www.enabiz.gov.tr/" target="_blank" style="text-decoration:none; color:#333;">🏥 E-Nabız</a>', unsafe_allow_html=True)

if secim == "🏠 Ana Sayfa": sayfa_ana_ekran()
elif secim == "🍽️ Yemekler": sayfa_yemekler()
elif secim == "💰 Ekonomi": sayfa_ekonomi()
elif secim == "🧬 Yaşam": sayfa_yasam()
elif secim == "📂 Dosya": sayfa_dosya()
elif secim == "🎮 Cihazlar": sayfa_cihazlar()
