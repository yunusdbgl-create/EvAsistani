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

# Grafik kütüphanesi kontrolü (Geri Getirildi)
try:
    import plotly.express as px
    GRAFIK_VAR = True
except ImportError:
    GRAFIK_VAR = False

# ==============================================================================
# ⚙️ AYARLAR
# ==============================================================================
DOSYA_ADI = "EvAsistaniDB"
NTFY_TOPIC = "yunus_ozel_ev_kanali_123"

st.set_page_config(page_title="Bizim Evin Paneli", page_icon="🏡", layout="centered")

# ==============================================================================
# 🖼️ CSS VE HEAD (MOBİL UYUM + GÖRSELLİK)
# ==============================================================================
APP_ICON_URL = "https://cdn-icons-png.flaticon.com/512/2942/2942789.png"

# 1. KISIM: HEAD
st.markdown(f"""
<head>
    <link rel="icon" href="{APP_ICON_URL}">
    <link rel="apple-touch-icon" href="{APP_ICON_URL}">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
</head>
""", unsafe_allow_html=True)

# 2. KISIM: CSS (MENÜLERİ VE BUTONLARI KURTARAN SÜRÜM)
st.markdown("""
<style>
    /* 1. SAYFA KENAR BOŞLUKLARINI DÜZELT (Menüler geri gelsin) */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 5rem !important;
        padding-left: 10px !important; /* Soldan biraz boşluk */
        padding-right: 10px !important; /* Sağdan menü için boşluk */
        max-width: 100% !important;
    }
    
    /* 2. SATIRLARI HİZALA */
    div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important; /* Alt satıra inme yasağı */
        align-items: center !important;
        gap: 5px !important;
    }
    
    /* 3. SÜTUN AYARLARI (Butonlar kaybolmasın) */
    div[data-testid="column"] {
        flex: 1 1 auto !important;
        min-width: 0 !important;
        overflow: hidden !important; /* Taşan yazıyı gizle */
    }

    /* İsim Sütunu (Sol) */
    div[data-testid="column"]:nth-of-type(1) {
        flex-grow: 1 !important;
    }

    /* Buton Sütunları (Orta ve Sağ) - Sabit Genişlik */
    div[data-testid="column"]:nth-last-child(1),
    div[data-testid="column"]:nth-last-child(2) {
        flex: 0 0 auto !important; /* Otomatik sığdır */
        width: auto !important;
        min-width: 35px !important; /* En az bu kadar yer kapla */
    }
    
    /* 4. METİN DÜZENLEMESİ (... ile kısaltma) */
    div[data-testid="column"] p, 
    div[data-testid="column"] div, 
    div[data-testid="column"] label {
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        font-size: 14px !important;
        margin-bottom: 0 !important;
    }
    
    /* 5. BUTON GÖRÜNÜMÜ */
    button {
        padding: 0px 5px !important; /* İç boşluğu azalttık */
        margin: 0 !important;
        height: 40px !important;
        min-height: 40px !important;
        width: 100% !important;
        line-height: 1 !important;
    }

    /* 6. EXTRA DÜZELTMELER */
    .stCheckbox { margin-top: -2px !important; }
    
    /* KUTU TASARIMLARI */
    .welcome-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; padding: 15px; border-radius: 12px;
        text-align: center; margin-bottom: 15px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
    }
    .prenses-box {
        background: linear-gradient(135deg, #f6d365 0%, #fda085 100%);
        color: #5e4a18; padding: 15px; border-radius: 12px;
        text-align: center; margin-bottom: 15px;
        border: 2px solid white;
    }
    .welcome-title { font-size: 20px; font-weight: bold; margin-bottom: 5px; }
    .category-line { height: 3px; border-radius: 2px; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

# YUKARI ÇIK BUTONU
components.html("""
<script>function topaGit() { window.parent.scrollTo({top: 0, behavior: 'smooth'}); }</script>
<button onclick="topaGit()" style="position: fixed; bottom: 20px; left: 15px; background-color: #FF4B4B; color: white; border: none; border-radius: 50%; width: 45px; height: 45px; font-size: 20px; cursor: pointer; box-shadow: 2px 2px 8px rgba(0,0,0,0.3); z-index: 999999; display: flex; align-items: center; justify-content: center;">⬆️</button>
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
        "Seninle yaşlanmak istiyorum.", "Sen benim en güzel şansımsın.", "Kalbimin sahibi sensin."
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
        if yeni_durum is not None: sheet.update_cell(cell.row, 2, str(yeni_durum))
        if yeni_ad is not None: sheet.update_cell(cell.row, 1, str(yeni_ad))
    except: pass

def arka_planda_guncelle_yatirim(urun, miktar, notlar, tip):
    try:
        client = get_client(); sheet = client.open(DOSYA_ADI).sheet1; bulundu = False; tum = sheet.get_all_values()
        for i, row in enumerate(tum):
            if row[0] == urun and row[4] == tip:
                sheet.update_cell(i + 1, 2, datetime.now().strftime("%Y-%m-%d")); sheet.update_cell(i + 1, 3, str(miktar)); sheet.update_cell(i + 1, 4, str(notlar)); bulundu = True; break
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
    urunler = [u.strip() for u in isim_veya_liste.split(",")] if "," in isim_veya_liste else [isim_veya_liste.strip()]
    for isim in urunler:
        if not isim: continue
        if tip in ["MARKET", "YEMEK_OGUN", "YEMEK_KAHVALTI"]:
            if not st.session_state.local_df[(st.session_state.local_df["Tip"] == tip) & (st.session_state.local_df["Urun"] == isim)].empty: continue
        row = {"Urun": isim, "Durum": durum, "Mesaj": mesaj, "Zaman": str(zaman), "Tip": tip}
        st.session_state.local_df = pd.concat([st.session_state.local_df, pd.DataFrame([row])], ignore_index=True)
        threading.Thread(target=arka_planda_ekle, args=([isim, durum, mesaj, str(zaman), tip],)).start()

def hizli_sil(isim):
    st.session_state.local_df = st.session_state.local_df[st.session_state.local_df["Urun"] != isim]
    threading.Thread(target=arka_planda_sil, args=(isim,)).start()

def hizli_duzenle(eski_isim, yeni_isim):
    if not yeni_isim or eski_isim == yeni_isim: return
    idx = st.session_state.local_df[st.session_state.local_df["Urun"] == eski_isim].index
    if not idx.empty: st.session_state.local_df.at[idx[0], "Urun"] = yeni_isim; st.success(f"✅ Değişti: {yeni_isim}")
    threading.Thread(target=arka_planda_guncelle, args=(eski_isim, yeni_isim, None)).start()

def hizli_durum_degistir(isim, yeni_durum):
    idx = st.session_state.local_df[st.session_state.local_df["Urun"] == isim].index
    if not idx.empty: st.session_state.local_df.at[idx[0], "Durum"] = str(yeni_durum)
    threading.Thread(target=arka_planda_guncelle, args=(isim, None, yeni_durum)).start()

def hizli_yatirim_guncelle(isim, miktar, notlar):
    df = st.session_state.local_df; mask = (df["Tip"] == "YATIRIM") & (df["Urun"] == isim)
    if df[mask].empty: hizli_ekle(isim, "YATIRIM", zaman=notlar, mesaj=str(miktar), durum=datetime.now().strftime("%Y-%m-%d"))
    else:
        idx = df[mask].index[0]; st.session_state.local_df.at[idx, "Mesaj"] = str(miktar); st.session_state.local_df.at[idx, "Zaman"] = str(notlar); st.session_state.local_df.at[idx, "Durum"] = datetime.now().strftime("%Y-%m-%d")
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
    val = st.session_state.market_giris; kat_secim = st.session_state.market_kategori_secim; kat_yeni = st.session_state.get("market_kategori_yeni", "")
    kategori = kat_yeni if (kat_secim == "✏️ Yeni Kategori Yaz" and kat_yeni) else kat_secim
    if val: hizli_ekle(val, "MARKET", mesaj=kategori); st.session_state.market_giris = ""

def is_ekleme_callback():
    val = st.session_state.is_giris; kat_secim = st.session_state.is_kategori_secim; kategori = st.session_state.get("is_kategori_yeni", "") if kat_secim == "✏️ Yeni Kategori Yaz" else kat_secim
    if val: hizli_ekle(val, "TODO", mesaj=kategori); st.session_state.is_giris = ""

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
    if ad: kod = "HER_AY" if tekrar == "🔁 Her Ay" else "TEK"; hizli_ekle(ad, "FATURA", gun, str(saat)[0:5], kod); st.session_state.fat_ad = ""

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
    tum = set(); [tum.add(u.lower().split("(")[0].strip()) for u in marketten_gelenler]; [tum.add(u.lower()) for u in manuel_eklenenler]
    tarifler = {"Menemen": ["yumurta", "domates", "biber"], "Omlet": ["yumurta", "peynir", "tereyağı"], "Makarna": ["makarna", "salça", "yağ"], "Köfte": ["kıyma", "soğan", "ekmek"], "Kısır": ["bulgur", "salça", "yeşillik"], "Patates Kızartması": ["patates", "yağ"], "Tavuk Sote": ["tavuk", "biber", "domates"], "Mercimek Çorbası": ["mercimek", "soğan", "salça"]}
    tam, eksik = [], []
    for y, m in tarifler.items():
        e = [x for x in m if x not in tum]
        if not e: tam.append(y)
        elif len(e) <= 2: eksik.append((y, e))
    return tam, eksik, list(tum)

def karsilama_paneli():
    saat = datetime.now().hour
    mesaj = "Günaydın! ☀️" if 5 <= saat < 12 else "Tünaydın! 🌤️" if 12 <= saat < 18 else "İyi Akşamlar! 🌙" if 18 <= saat < 22 else "İyi Geceler! 🦉"
    if random.random() < 0.25: st.markdown(f'<div class="prenses-box"><div class="welcome-title">🐾 MİYAV!</div><div class="welcome-note">{random.choice(prenses_sozleri())}</div></div>', unsafe_allow_html=True)
    else: st.markdown(f'<div class="welcome-box"><div class="welcome-title">{mesaj}</div><div class="welcome-note">Bugün harika şeyler başarabilirsin.</div></div>', unsafe_allow_html=True)

def dashboard_goster():
    df = st.session_state.local_df; df_f = df[df["Tip"] == "FATURA"]; siradaki = "Yok"; kalan_txt = ""
    if not df_f.empty:
        bugun = datetime.now().day; df_f["Gun"] = pd.to_numeric(df_f["Zaman"], errors='coerce').fillna(32); df_f = df_f.sort_values("Gun")
        for _, row in df_f.iterrows():
            k = int(row["Gun"]) - bugun
            if k >= 0: siradaki = row["Urun"]; kalan_txt = "Bugün" if k == 0 else f"{k} gün"; break
    c1, c2 = st.columns(2)
    c1.metric("🧾 Ödeme", siradaki, kalan_txt)
    c2.metric("🛒 Sepet", f"{len(df[(df['Tip'] == 'MARKET') & (df['Durum'] == '0')])} Ürün")
    st.markdown("---")

# ==============================================================================
# LİSTELEME MODÜLÜ (ÇİVİ GİBİ SABİT)
# ==============================================================================
def liste_satiri_olustur(prefix, i, row, checkbox_var=True):
    if st.session_state.get(f"editing_{prefix}") == row['Urun']:
        with st.form(key=f"edit_form_{prefix}_{i}"):
            yeni = st.text_input("Dzn:", value=row['Urun'])
            c1, c2 = st.columns(2)
            if c1.form_submit_button("💾"): hizli_duzenle(row['Urun'], yeni); st.session_state[f"editing_{prefix}"] = None; st.rerun()
            if c2.form_submit_button("❌"): st.session_state[f"editing_{prefix}"] = None; st.rerun()
    else:
        c1, c2, c3 = st.columns([0.7, 0.15, 0.15], gap="small", vertical_alignment="center")
        with c1:
            if checkbox_var:
                if st.checkbox(f"**{row['Urun']}**", key=f"chk_{prefix}_{i}"): hizli_durum_degistir(row['Urun'], "1"); st.rerun()
            else: st.markdown(f"**{row['Urun']}**")
        with c2:
            if st.button("✏️", key=f"ed_{prefix}_{i}"): st.session_state[f"editing_{prefix}"] = row['Urun']; st.rerun()
        with c3:
            if not st.session_state.get(f"conf_{prefix}_{i}"):
                if st.button("🗑️", key=f"del_{prefix}_{i}"): st.session_state[f"conf_{prefix}_{i}"] = True; st.rerun()
            else:
                if st.button("Sil?", key=f"yes_{prefix}_{i}", type="primary"): hizli_sil(row['Urun']); st.session_state[f"conf_{prefix}_{i}"] = False; st.rerun()

def liste_satiri_geri_al(prefix, i, row):
    c1, c2, c3 = st.columns([0.7, 0.15, 0.15], gap="small", vertical_alignment="center")
    with c1:
        if st.button(f"➕ {row['Urun']}", key=f"back_{prefix}_{i}", use_container_width=True): hizli_durum_degistir(row['Urun'], "0"); st.rerun()
    with c2:
         if st.button("✏️", key=f"ed_fin_{prefix}_{i}"): st.session_state[f"editing_{prefix}"] = row['Urun']; st.rerun()
    with c3:
        if st.button("🗑️", key=f"del_fin_{prefix}_{i}"): hizli_sil(row['Urun']); st.rerun()

# ==============================================================================
# SAYFALAR
# ==============================================================================
def sayfa_ana_ekran():
    if st.button("🎁 Sürpriz Kutusu", type="primary", use_container_width=True): st.balloons(); st.success(f"💌 {random.choice(ask_kavanozu_sozleri())}"); time.sleep(4)
    tab1, tab2, tab3 = st.tabs(["🛒 MARKET", "📝 İŞLER", "⏰ ALARM"])
    with tab1:
        df = st.session_state.local_df; df_m = df[df["Tip"] == "MARKET"]
        VARSAYILAN = ["🍏 Meyve & Sebze", "🥩 Et & Şarküteri", "🥛 Süt & Kahvaltılık", "🍞 Gıda & Bakliyat", "🧹 Temizlik", "🍫 Atıştırmalık"]
        kayitli = {k for k in set(df_m["Mesaj"].dropna().unique()) if k and k not in ["Genel", "None", "✏️ Yeni Kategori Yaz"]}
        TUM = sorted(list(set(VARSAYILAN) | kayitli)) + ["✏️ Yeni Kategori Yaz"]
        
        c1, c2, c3 = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("Ürün", key="market_giris", label_visibility="collapsed", placeholder="Ürün...")
        with c2: st.selectbox("Kat.", TUM, key="market_kategori_secim", label_visibility="collapsed")
        with c3: st.button("EKLE", key="btn_m", on_click=market_ekleme_callback, use_container_width=True)
        if st.session_state.market_kategori_secim == "✏️ Yeni Kategori Yaz": st.text_input("Yeni Kat.", key="market_kategori_yeni")
        st.markdown("---")
        
        alinacak = df_m[df_m["Durum"] == "0"]
        kat_list = sorted(list(set(TUM[:-1]) | {"Genel"})); 
        if "Genel" in kat_list: kat_list.remove("Genel"); kat_list.append("Genel")
        
        for kat in kat_list:
            items = alinacak[(alinacak["Mesaj"] == "") | (alinacak["Mesaj"] == "Genel") | (alinacak["Mesaj"] == "None")] if kat == "Genel" else alinacak[alinacak["Mesaj"] == kat]
            if not items.empty:
                renk = get_kategori_renk(kat)
                with st.expander(f"{kat} ({len(items)})", expanded=True):
                    st.markdown(f"<div class='category-line' style='background-color:{renk};'></div>", unsafe_allow_html=True)
                    for i, row in items.iterrows(): liste_satiri_olustur("m", i, row)
        
        st.divider()
        
        # --- GERİ GETİRİLEN KATEGORİLİ GEÇMİŞ ---
        alinan = df_m[df_m["Durum"] == "1"]
        with st.expander(f"📦 Geçmiş / Alınanlar ({len(alinan)})", expanded=False):
            if not alinan.empty:
                for kat in kat_list:
                    items = alinan[(alinan["Mesaj"] == "") | (alinan["Mesaj"] == "Genel") | (alinan["Mesaj"] == "None")] if kat == "Genel" else alinan[alinan["Mesaj"] == kat]
                    if not items.empty:
                        with st.expander(f"{kat} ({len(items)})"): # İÇ İÇE EXPANDER GERİ GELDİ
                            for i, row in items.iterrows(): liste_satiri_geri_al("m", i, row)

    with tab2:
        df_t = st.session_state.local_df[st.session_state.local_df["Tip"] == "TODO"]
        c1, c2, c3 = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("İş", key="is_giris", label_visibility="collapsed")
        with c2: st.selectbox("Kat.", ["Ev", "İş", "Genel"], key="is_kategori_secim", label_visibility="collapsed")
        with c3: st.button("EKLE", key="btn_t", on_click=is_ekleme_callback, use_container_width=True)
        st.markdown("---"); items = df_t[df_t["Durum"] == "0"]
        for i, row in items.iterrows(): liste_satiri_olustur("t", i, row)
    with tab3:
        with st.form("alarm"):
            mesaj = st.text_input("Not"); sure = st.number_input("Dk", 1, value=15)
            if st.form_submit_button("🔔"): alarm_kur(mesaj, sure); st.rerun()
        df_a = st.session_state.local_df[st.session_state.local_df["Tip"] == "ALARM"]; st.markdown("---")
        for i, row in df_a.iterrows():
            c1, c2, c3 = st.columns([0.8, 0.1, 0.1], gap="small", vertical_alignment="center")
            with c1: st.write(f"**{row['Mesaj']}**")
            with c3: 
                if st.button("🗑️", key=f"del_al_{i}"): hizli_sil(row['Urun']); st.rerun()

def sayfa_ekonomi():
    tab1, tab2, tab3 = st.tabs(["💸 ÖDEME", "💰 BÜTÇE", "📈 YATIRIM"])
    with tab1:
        with st.expander("➕ Ekle", expanded=True):
            c1, c2 = st.columns(2); 
            with c1: st.text_input("Ad", key="fat_ad"); st.number_input("Gün", 1, 31, 1, key="fat_gun")
            with c2: st.time_input("Saat", dt_time(9,0), key="fat_saat"); st.radio("Tip", ["🔁", "1️⃣"], key="fat_tekrar")
            st.button("KAYDET", key="btn_fat", on_click=fatura_callback, use_container_width=True)
        st.markdown("---"); df_f = st.session_state.local_df[st.session_state.local_df["Tip"] == "FATURA"]
        for i, row in df_f.iterrows():
            c1, c2, c3 = st.columns([0.8, 0.1, 0.1], gap="small", vertical_alignment="center")
            with c1: st.write(f"**{row['Urun']}** | {row['Zaman']}. Gün")
            with c3: 
                if st.button("🗑️", key=f"del_fat_{i}"): hizli_sil(row['Urun']); st.rerun()
    with tab2:
        with st.expander("➕ Ekle", expanded=True):
            c1, c2 = st.columns(2); 
            with c1: st.radio("Tip", ["Gider", "Gelir"], horizontal=True, key="butce_tur"); st.text_input("Açıklama", key="butce_ad")
            with c2: st.number_input("Tutar", key="butce_tutar"); st.button("KAYDET", key="btn_butce", on_click=butce_callback)
        st.markdown("---"); df_b = st.session_state.local_df[st.session_state.local_df["Tip"] == "BUTCE"]; 
        bu_ay = datetime.now().strftime("%Y-%m"); df_b = df_b[df_b["Durum"].str.contains("Gelir|Gider", na=False)] 
        gelir = sum(float(r["Mesaj"]) for _, r in df_b.iterrows() if r["Durum"] == "Gelir"); gider = sum(float(r["Mesaj"]) for _, r in df_b.iterrows() if r["Durum"] == "Gider")
        c1, c2, c3 = st.columns(3); c1.metric("Gelir", f"{gelir:.0f}"); c2.metric("Gider", f"{gider:.0f}"); c3.metric("Kalan", f"{gelir-gider:.0f}")
        st.divider()
        for i, row in df_b.iterrows():
             c1, c2, c3 = st.columns([0.8, 0.1, 0.1], gap="small", vertical_alignment="center")
             with c1: st.write(f"{'🟢' if row['Durum']=='Gelir' else '🔴'} {row['Urun']}")
             with c2: st.write(f"{row['Mesaj']}₺")
             with c3: 
                if st.button("🗑️", key=f"del_b_{i}"): hizli_sil(row['Urun']); st.rerun()
    with tab3:
        with st.expander("➕ Ekle", expanded=True):
            c1, c2 = st.columns(2); 
            with c1: st.text_input("Varlık", key="yat_ad"); st.number_input("Değer", step=100.0, key="yat_mik")
            with c2: st.text_area("Not", height=100, key="yat_not"); st.button("KAYDET", key="btn_yat", on_click=yatirim_callback)
        df_y = st.session_state.local_df[st.session_state.local_df["Tip"] == "YATIRIM"]; st.markdown("---")
        
        # --- GRAFİK GERİ GELDİ ---
        if not df_y.empty:
            df_y["Tutar"] = df_y["Mesaj"].apply(lambda x: float(x) if str(x).replace('.','',1).isdigit() else 0)
            toplam = df_y["Tutar"].sum()
            c1, c2 = st.columns([1, 2])
            with c1: st.metric("TOPLAM", f"{toplam:,.0f} ₺")
            with c2:
                if GRAFIK_VAR:
                    fig = px.pie(df_y, values='Tutar', names='Urun', hole=0.4)
                    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=200, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
        
        st.divider()
        for i, row in df_y.iterrows():
            c1, c2, c3 = st.columns([0.8, 0.1, 0.1], gap="small", vertical_alignment="center")
            with c1: st.write(f"💎 {row['Urun']} - {row['Mesaj']}₺")
            with c3: 
                if st.button("🗑️", key=f"del_y_{i}"): hizli_sil(row['Urun']); st.rerun()

def sayfa_yemekler():
    tab1, tab2, tab3, tab4 = st.tabs(["🔥 EŞLEŞME", "🎡 KAHVALTI", "🎡 YEMEK", "👨‍🍳 AI ŞEF"])
    with st.expander("⚙️"): 
        if st.button("🧹 Temizle"): listeyi_temizle()
    with tab1:
        # TINDER STİLİ GERİ GELDİ
        df_o = st.session_state.local_df[(st.session_state.local_df["Tip"].isin(["YEMEK_OGUN", "YEMEK_KAHVALTI"])) & (st.session_state.local_df["Durum"] == "1")]
        lst = df_o["Urun"].tolist()
        if lst:
            if 'oyun' not in st.session_state: st.session_state.oyun = random.choice(lst)
            st.markdown(f"<h1 style='text-align: center; color: #ff6b6b;'>{st.session_state.oyun}</h1>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("👎 PAS", use_container_width=True): st.session_state.oyun = random.choice(lst); st.rerun()
            if c2.button("👍 YE", type="primary", use_container_width=True): st.balloons(); st.success(f"AFİYET OLSUN: {st.session_state.oyun}"); 
        else: st.warning("Listede yemek yok!")
    with tab2:
        c1, c2 = st.columns([0.8, 0.2]); 
        with c1: st.text_input("Kahvaltı", key="kahvalti_giris", label_visibility="collapsed")
        with c2: st.button("EKLE", key="btn_kahvalti", on_click=yemek_ekle_callback, args=("kahvalti_giris", "YEMEK_KAHVALTI"))
        st.markdown("---"); df_k = st.session_state.local_df[st.session_state.local_df["Tip"] == "YEMEK_KAHVALTI"]
        for i, row in df_k.iterrows(): liste_satiri_olustur("k", i, row)
    with tab3:
        c1, c2 = st.columns([0.8, 0.2]); 
        with c1: st.text_input("Yemek", key="yemek_giris", label_visibility="collapsed")
        with c2: st.button("EKLE", key="btn_yemek", on_click=yemek_ekle_callback, args=("yemek_giris", "YEMEK_OGUN"))
        st.markdown("---"); df_y = st.session_state.local_df[st.session_state.local_df["Tip"] == "YEMEK_OGUN"]
        for i, row in df_y.iterrows(): liste_satiri_olustur("y", i, row)
    with tab4:
        st.subheader("👨‍🍳 AI"); df = st.session_state.local_df; m = df[(df["Tip"] == "MARKET") & (df["Durum"] == "1")]["Urun"].tolist(); e = st.multiselect("Evde ne var?", ["Yumurta", "Domates", "Patates", "Soğan"])
        if st.button("🔍 Bul"):
            t, ex, s = mutfak_sefi_motoru(m, e); 
            if t: st.success(f"✅ {', '.join(t)}")
            if ex: st.warning("Eksikler var")

def sayfa_yasam():
    tab1, tab2, tab3 = st.tabs(["⛓️ ZİNCİR", "⏳ SAYAÇ", "📒 NOTLAR"])
    with tab1:
        c1, c2 = st.columns([0.8, 0.2]); 
        with c1: st.text_input("Rutin", key="rutin_giris", label_visibility="collapsed")
        with c2: st.button("EKLE", key="btn_rutin", on_click=rutin_ekle_callback)
        df_r = st.session_state.local_df[st.session_state.local_df["Tip"] == "RUTIN"]; st.markdown("---")
        for i, row in df_r.iterrows(): liste_satiri_olustur("r", i, row)
    with tab2:
        with st.expander("➕ Ekle", expanded=True): st.text_input("Ad", key="sayac_ad"); st.date_input("Tarih", key="sayac_tarih"); st.button("KAYDET", key="btn_syc", on_click=sayac_callback)
        df_s = st.session_state.local_df[st.session_state.local_df["Tip"] == "COUNTDOWN"]; st.markdown("---"); bugun = datetime.now().date()
        
        # --- SAYAÇ GÖRÜNÜMÜ ESKİSİ GİBİ ---
        for i, row in df_s.iterrows():
            try:
                hedef = datetime.strptime(row["Zaman"], "%Y-%m-%d").date(); kalan = (hedef - bugun).days
                c1, c2, c3 = st.columns([0.6, 0.3, 0.1], gap="small", vertical_alignment="center")
                with c1: st.write(f"📅 **{row['Urun']}**")
                with c2: 
                    if kalan > 0: st.info(f"{kalan} gün kaldı")
                    elif kalan == 0: st.success("BUGÜN!")
                    else: st.error("Geçti")
                with c3: 
                    if st.button("🗑️", key=f"del_syc_{i}"): hizli_sil(row['Urun']); st.rerun()
                st.divider()
            except: pass
    with tab3:
        with st.expander("➕ Ekle"): st.text_input("Başlık", key="not_baslik"); st.text_area("İçerik", key="not_icerik"); st.button("KAYDET", key="btn_nt", on_click=not_callback)
        df_n = st.session_state.local_df[st.session_state.local_df["Tip"] == "NOTE"]
        for i, row in df_n.iterrows():
             with st.expander(f"📒 {row['Urun']}"): st.code(row['Mesaj']); 
             if st.button("🗑️", key=f"del_nt_{i}"): hizli_sil(row['Urun']); st.rerun()

def sayfa_dosya():
    st.subheader("📂 PDF"); d = st.file_uploader("Resim", type=["png", "jpg"])
    if d: import img2pdf; st.download_button("⬇️", img2pdf.convert(d.read()), f"{d.name}.pdf", "application/pdf")

def sayfa_cihazlar():
    st.markdown("### 🎮 Akıllı Ev"); st.info("Geliştirme Modunda")

# ==============================================================================
# ÇALIŞTIRMA
# ==============================================================================
karsilama_paneli()
dashboard_goster()

with st.sidebar:
    st.header("Menü")
    secim = st.radio("Git:", ["🏠 Ana Sayfa", "🍽️ Yemekler", "💰 Ekonomi", "🧬 Yaşam", "📂 Dosya", "🎮 Cihazlar"])
    st.markdown("---"); st.markdown('<a href="https://www.turkiye.gov.tr/" target="_blank" style="text-decoration:none; color:#333;">🏛️ E-Devlet</a>', unsafe_allow_html=True); st.markdown('<br><a href="https://www.enabiz.gov.tr/" target="_blank" style="text-decoration:none; color:#333;">🏥 E-Nabız</a>', unsafe_allow_html=True)

if secim == "🏠 Ana Sayfa": sayfa_ana_ekran()
elif secim == "🍽️ Yemekler": sayfa_yemekler()
elif secim == "💰 Ekonomi": sayfa_ekonomi()
elif secim == "🧬 Yaşam": sayfa_yasam()
elif secim == "📂 Dosya": sayfa_dosya()
elif secim == "🎮 Cihazlar": sayfa_cihazlar()

