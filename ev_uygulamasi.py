import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
from datetime import datetime, timedelta
import threading
import random
import plotly.express as px

# ==============================================================================
# AYARLAR
# ==============================================================================
st.set_page_config(page_title="Bizim Evin Paneli", page_icon="🏡", layout="centered", initial_sidebar_state="collapsed")
DOSYA_ADI = "EvAsistaniDB"

# --- CSS TASARIM ---
st.markdown("""
<style>
    div[data-testid="column"] { display: flex; align-items: center; }
    .stButton button { width: 100%; border-radius: 8px; }
    
    /* Prenses ve Not Kutuları */
    .prenses-box {
        background: linear-gradient(135deg, #FF9A9E 0%, #FECFEF 100%);
        color: #5d2e46; padding: 15px; border-radius: 15px; text-align: center;
        border: 2px solid #fff; margin-bottom: 15px;
    }
    .kategori-baslik {
        font-size: 14px; font-weight: bold; color: #555; margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# VERİTABANI VE FONKSİYONLAR
# ==============================================================================
@st.cache_resource
def get_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(dict(st.secrets["connections"]["gsheets"]), scopes=scopes)
    return gspread.authorize(creds)

def verileri_yukle():
    try:
        client = get_client()
        sheet = client.open(DOSYA_ADI).sheet1
        data = sheet.get_all_values()
        if not data: return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman", "Tip"])
        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    except:
        return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman", "Tip"])

# Session State Başlatma
if 'local_df' not in st.session_state:
    st.session_state.local_df = verileri_yukle()

# --- ARKA PLAN İŞLEMLERİ (THREADING) ---
def arka_planda_ekle(satir):
    try: get_client().open(DOSYA_ADI).sheet1.append_row(satir)
    except: pass

def arka_planda_guncelle(urun, durum):
    try:
        sheet = get_client().open(DOSYA_ADI).sheet1
        cell = sheet.find(urun)
        if cell: sheet.update_cell(cell.row, 2, str(durum))
    except: pass

def arka_planda_sil(urun):
    try:
        sheet = get_client().open(DOSYA_ADI).sheet1
        cell = sheet.find(urun)
        if cell: sheet.delete_rows(cell.row)
    except: pass

# --- HIZLI İŞLEMLER (UI ANINDA GÜNCELLENİR) ---
def hizli_ekle(isim, tip, mesaj="", zaman="", durum="0"):
    df = st.session_state.local_df
    # Mükerrer Kontrolü
    if tip in ["MARKET", "YEMEK_OGUN"] and not df[(df["Tip"] == tip) & (df["Urun"] == isim)].empty:
        return
        
    yeni = {"Urun": isim, "Durum": durum, "Mesaj": mesaj, "Zaman": str(zaman), "Tip": tip}
    st.session_state.local_df = pd.concat([df, pd.DataFrame([yeni])], ignore_index=True)
    threading.Thread(target=arka_planda_ekle, args=([isim, durum, mesaj, str(zaman), tip],)).start()

def hizli_durum_degistir(isim, yeni_durum):
    df = st.session_state.local_df
    idx = df[df["Urun"] == isim].index
    if not idx.empty:
        st.session_state.local_df.at[idx[0], "Durum"] = str(yeni_durum)
        threading.Thread(target=arka_planda_guncelle, args=(isim, yeni_durum)).start()
        st.rerun() # Anında yansıması için

def hizli_sil(isim):
    st.session_state.local_df = st.session_state.local_df[st.session_state.local_df["Urun"] != isim]
    threading.Thread(target=arka_planda_sil, args=(isim,)).start()
    st.rerun()

# Renk Haritası
def get_kategori_renk(kategori):
    renkler = {"Meyve": "#2ecc71", "Sebze": "#27ae60", "Et": "#c0392b", "Süt": "#2980b9", "Temizlik": "#8e44ad", "Genel": "#7f8c8d"}
    for k, v in renkler.items():
        if k in kategori: return v
    return "#34495e"

# ==============================================================================
# SAYFALAR
# ==============================================================================

def karsilama_modulu():
    # Kripto Şerit
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd").json()
        btc, eth = r['bitcoin']['usd'], r['ethereum']['usd']
        st.caption(f"📅 {datetime.now().strftime('%d.%m.%Y')} | ₿ BTC: ${btc:,.0f} | Ξ ETH: ${eth:,.0f}")
    except: st.caption(f"📅 {datetime.now().strftime('%d.%m.%Y')}")

    if random.random() < 0.25:
        soz = random.choice(["Mama kabım boş!", "Beni sevmeyi unuttunuz.", "Akşama balık mı var?", "Sizi izliyorum..."])
        st.markdown(f'<div class="prenses-box">🐾 <b>Prenses:</b> {soz}</div>', unsafe_allow_html=True)

def sayfa_market():
    st.subheader("🛒 Market Listesi")
    
    # --- EKLEME KISMI ---
    c1, c2, c3 = st.columns([2, 1.5, 1])
    with c1: urun = st.text_input("Ürün Ekle", key="m_input", label_visibility="collapsed", placeholder="Ürün...")
    with c2: 
        kat_listesi = ["Genel", "🍏 Meyve & Sebze", "🥩 Et & Şarküteri", "🥛 Süt & Kahvaltılık", "🧹 Temizlik", "🍫 Atıştırmalık"]
        kat = st.selectbox("Kategori", kat_listesi, label_visibility="collapsed")
    with c3:
        if st.button("EKLE", use_container_width=True):
            if urun: 
                hizli_ekle(urun, "MARKET", mesaj=kat)
                st.rerun()

    # --- LİSTELEME (ESKİ MANTIK) ---
    df = st.session_state.local_df
    df_market = df[df["Tip"] == "MARKET"]
    
    # 1. Alınacaklar (Durum 0)
    alinacaklar = df_market[df_market["Durum"] == "0"]
    st.markdown("##### 📌 Alınacaklar")
    if alinacaklar.empty: st.info("Sepet boş! 🎉")
    
    mevcut_kategoriler = sorted(list(set(alinacaklar["Mesaj"].unique())))
    for k in mevcut_kategoriler:
        items = alinacaklar[alinacaklar["Mesaj"] == k]
        renk = get_kategori_renk(k)
        with st.expander(f"{k} ({len(items)})", expanded=True):
            st.markdown(f"<div style='height:3px; background-color:{renk}; margin-bottom:5px;'></div>", unsafe_allow_html=True)
            for i, row in items.iterrows():
                col1, col2 = st.columns([0.85, 0.15])
                with col1:
                    if st.checkbox(f"**{row['Urun']}**", key=f"chk_{row['Urun']}"):
                        hizli_durum_degistir(row['Urun'], "1")
                with col2:
                    if st.button("🗑️", key=f"del_{row['Urun']}"): hizli_sil(row['Urun'])

    st.markdown("---")

    # 2. Geçmiş / Alınanlar (Durum 1) - BURASI GERİ GELDİ
    tamamlananlar = df_market[df_market["Durum"] == "1"]
    with st.expander(f"📦 Geçmiş / Alınanlar ({len(tamamlananlar)})", expanded=False):
        if tamamlananlar.empty: st.caption("Henüz geçmiş ürün yok.")
        
        gecmis_kategoriler = sorted(list(set(tamamlananlar["Mesaj"].unique())))
        for k in gecmis_kategoriler:
            items = tamamlananlar[tamamlananlar["Mesaj"] == k]
            st.markdown(f"**{k}**")
            for i, row in items.iterrows():
                col1, col2 = st.columns([0.85, 0.15])
                with col1:
                    # Geri ekleme butonu
                    if st.button(f"➕ {row['Urun']}", key=f"back_{row['Urun']}", use_container_width=True):
                        hizli_durum_degistir(row['Urun'], "0")
                with col2:
                    if st.button("🗑️", key=f"del_hist_{row['Urun']}"): hizli_sil(row['Urun'])

def sayfa_isler():
    st.subheader("📝 Yapılacak İşler")
    
    # --- İŞ EKLEME ---
    c1, c2, c3 = st.columns([2, 1.5, 1])
    with c1: is_adi = st.text_input("Görev", key="t_input", label_visibility="collapsed", placeholder="Tamirat...")
    with c2: 
        is_kat_listesi = ["Genel", "🏠 Ev İçi", "🔧 Tamirat", "🏢 Dışarı İşleri", "🚗 Araba"]
        kat = st.selectbox("Kategori", is_kat_listesi, key="t_kat", label_visibility="collapsed")
    with c3:
        if st.button("EKLE", key="btn_is_ekle", use_container_width=True):
            if is_adi: 
                hizli_ekle(is_adi, "TODO", mesaj=kat)
                st.rerun()

    # --- İŞ LİSTELEME ---
    df = st.session_state.local_df
    df_todo = df[df["Tip"] == "TODO"]
    bekleyenler = df_todo[df_todo["Durum"] == "0"]
    
    if bekleyenler.empty: st.success("Tüm işler bitti! ☕")
    
    mevcut_kategoriler = sorted(list(set(bekleyenler["Mesaj"].unique())))
    for k in mevcut_kategoriler:
        items = bekleyenler[bekleyenler["Mesaj"] == k]
        renk = get_kategori_renk(k)
        # Orijinal koddaki gibi expander yapısı
        with st.expander(f"{k} ({len(items)})", expanded=True):
            st.markdown(f"<div style='height:3px; background-color:{renk}; margin-bottom:5px;'></div>", unsafe_allow_html=True)
            for i, row in items.iterrows():
                c1, c2 = st.columns([0.85, 0.15])
                with c1:
                    if st.checkbox(f"**{row['Urun']}**", key=f"t_chk_{row['Urun']}"):
                        hizli_durum_degistir(row['Urun'], "1")
                with c2:
                    if st.button("🗑️", key=f"t_del_{row['Urun']}"): hizli_sil(row['Urun'])

def sayfa_ekonomi():
    st.subheader("💰 Bütçe & Yatırım")
    
    # Basit Gelir Gider Ekleme
    with st.expander("➕ Gelir/Gider Ekle"):
        c1, c2, c3 = st.columns(3)
        tur = c1.radio("Tip", ["Gider", "Gelir"])
        ad = c2.text_input("Açıklama")
        tutar = c3.number_input("Tutar", min_value=0.0)
        if st.button("Kaydet", use_container_width=True):
            hizli_ekle(ad, "BUTCE", str(tutar), datetime.now().strftime("%Y-%m-%d"), tur)
            st.rerun()

    # Hesaplamalar
    df = st.session_state.local_df
    df_b = df[df["Tip"] == "BUTCE"]
    if not df_b.empty:
        bu_ay = datetime.now().strftime("%Y-%m")
        df_ay = df_b[pd.to_datetime(df_b["Zaman"], errors='coerce').dt.strftime('%Y-%m') == bu_ay]
        
        gelir = sum(float(x) for x in df_ay[df_ay["Durum"]=="Gelir"]["Mesaj"])
        gider = sum(float(x) for x in df_ay[df_ay["Durum"]=="Gider"]["Mesaj"])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Gelir", f"{gelir}₺")
        col2.metric("Gider", f"{gider}₺")
        col3.metric("Kalan", f"{gelir-gider}₺")
        
        st.dataframe(df_ay[["Zaman", "Urun", "Mesaj", "Durum"]], use_container_width=True)

def sayfa_mutfak():
    st.subheader("👨‍🍳 Mutfak Şefi")
    tab1, tab2 = st.tabs(["Ne Pişirsem?", "Yemek Çarkı"])
    with tab1:
        # Eski koddaki malzeme analizi mantığı
        df = st.session_state.local_df
        # Geçmişte alınmış (evde olması muhtemel) ürünler
        stok = df[(df["Tip"] == "MARKET") & (df["Durum"] == "1")]["Urun"].unique().tolist()
        st.write(f"🧊 **Dolap Tahmini:** {', '.join(stok[:8])}...")
        
        if st.button("Tarif Öner"):
            st.success("Tavuk Sote veya Makarna yapabilirsin! (Basit Öneri)")
            
    with tab2:
        if st.button("🎲 Rastgele Yemek Seç"):
            yemekler = df[df["Tip"] == "YEMEK_OGUN"]["Urun"].tolist()
            if yemekler:
                secilen = random.choice(yemekler)
                st.balloons()
                st.success(f"🥘 Bugünün Menüsü: **{secilen}**")

# ==============================================================================
# ANA ÇALIŞTIRMA
# ==============================================================================
karsilama_modulu()

# Yan Menü (Sidebar) - Navigasyon
with st.sidebar:
    st.title("Ev Asistanı")
    secim = st.radio("Menü", ["Market", "İşler", "Ekonomi", "Mutfak"], label_visibility="collapsed")
    st.markdown("---")
    st.caption("v2.1 - Restore Edildi")

if secim == "Market": sayfa_market()
elif secim == "İşler": sayfa_isler()
elif secim == "Ekonomi": sayfa_ekonomi()
elif secim == "Mutfak": sayfa_mutfak()
