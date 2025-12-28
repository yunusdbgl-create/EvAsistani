import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
from datetime import datetime, timedelta

# ==============================================================================
# AYARLAR
# ==============================================================================
DOSYA_ADI = "EvAsistaniDB"
NTFY_TOPIC = "yunus_ozel_ev_kanali_123"

st.set_page_config(page_title="Ev Paneli", page_icon="🏠", layout="centered")

# ==============================================================================
# GOOGLE SHEETS BAĞLANTISI (CACHE İLE HIZLANDIRILMIŞ)
# ==============================================================================
@st.cache_resource
def baglanti_getir():
    """Bağlantıyı sadece bir kere kurar, her defasında tekrar bağlanmaz"""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = dict(st.secrets["connections"]["gsheets"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client

def veri_cek():
    """Google Sheets'ten veriyi çeker ve DataFrame'e çevirir"""
    client = baglanti_getir()
    try:
        sheet = client.open(DOSYA_ADI).sheet1
        data = sheet.get_all_records()
        
        # Eğer veri boşsa veya çekilemediyse boş tablo döndür
        if not data:
            return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman"])
        
        df = pd.DataFrame(data)
        
        # Sütun isimleri doğru mu kontrol et, değilse düzelt
        gerekli_sutunlar = ["Urun", "Durum", "Mesaj", "Zaman"]
        for col in gerekli_sutunlar:
            if col not in df.columns:
                df[col] = "" # Eksik sütunu ekle
                
        return df
    except Exception as e:
        # Hata durumunda (mesela dosya boşken) boş tablo dön
        return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman"])

def satir_ekle(yeni_satir_listesi):
    """Veriyi Google Sheets'e ekler"""
    client = baglanti_getir()
    sheet = client.open(DOSYA_ADI).sheet1
    sheet.append_row(yeni_satir_listesi)
    st.cache_data.clear() # Önbelleği temizle ki yeni veriyi görsün

def hucre_guncelle(urun_adi, yeni_durum):
    """Durumu günceller"""
    client = baglanti_getir()
    sheet = client.open(DOSYA_ADI).sheet1
    try:
        hucre = sheet.find(urun_adi)
        sheet.update_cell(hucre.row, 2, yeni_durum) # 2. Sütun (Durum)
        st.cache_data.clear()
    except: pass

# ==============================================================================
# BİLDİRİM
# ==============================================================================
def bildirim_gonder(mesaj):
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", 
                      data=mesaj.encode('utf-8'),
                      headers={"Title": "Ev Asistanı".encode('utf-8'), "Priority": "high"})
    except: pass

# ==============================================================================
# ARAYÜZ
# ==============================================================================
st.markdown("<h3 style='text-align: center;'>🏠 Hızlı Ev Paneli</h3>", unsafe_allow_html=True)

# Veriyi yükle
if 'df' not in st.session_state:
    st.session_state.df = veri_cek()

# Sayfa her yenilendiğinde veriyi taze tutmaya çalış
df = veri_cek()

tab1, tab2 = st.tabs(["🛒 MARKET", "⏰ ALARM"])

# --- TAB 1: MARKET ---
with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        yeni = st.text_input("Hızlı Ekle", placeholder="Ürün adı...", label_visibility="collapsed")
    with col2:
        if st.button("EKLE", use_container_width=True):
            if yeni:
                # Anında Ekranda Göster (Hız Hilesi)
                st.info("Ekleniyor...")
                satir_ekle([yeni, 0, "", ""])
                st.rerun()

    st.divider()

    # Dataframe boş değilse işlemleri yap
    if not df.empty and "Durum" in df.columns:
        # Durum sütununu sayıya çevirmeyi garantiye al
        df['Durum'] = pd.to_numeric(df['Durum'], errors='coerce').fillna(0)
        
        alinacaklar = df[df["Durum"] == 0]
        evde_var = df[df["Durum"] == 1]

        st.subheader(f"📌 Alınacaklar ({len(alinacaklar)})")
        
        # Checkboxlar
        for index, row in alinacaklar.iterrows():
            if st.checkbox(f"**{row['Urun']}**", key=f"chk_{index}"):
                hucre_guncelle(row['Urun'], 1)
                st.rerun()

        st.divider()

        # Evde Var Kutusu
        with st.expander(f"📦 Evde Var / Geçmiş ({len(evde_var)})"):
            if not evde_var.empty:
                cols = st.columns(3)
                for i, (index, row) in enumerate(evde_var.iterrows()):
                    with cols[i % 3]:
                        if st.button(f"➕ {row['Urun']}", key=f"btn_{index}"):
                            hucre_guncelle(row['Urun'], 0)
                            st.rerun()
    else:
        st.warning("Liste şu an boş veya yükleniyor. İlk ürününü ekle!")

# --- TAB 2: ALARM ---
with tab2:
    with st.form("alarm_form"):
        mesaj = st.text_input("Not", placeholder="Fırını kapat")
        sure = st.number_input("Dakika", min_value=1, value=15)
        if st.form_submit_button("Kaydet"):
            hedef = datetime.now() + timedelta(minutes=sure)
            hedef_str = hedef.strftime("%Y-%m-%d %H:%M:%S")
            
            satir_ekle(["", -1, mesaj, hedef_str])
            bildirim_gonder(f"✅ Alarm kuruldu: {sure} dk sonra '{mesaj}'")
            st.success("Kaydedildi!")
