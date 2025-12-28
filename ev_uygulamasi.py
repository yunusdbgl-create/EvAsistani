import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
from datetime import datetime, timedelta
import threading

# ==============================================================================
# AYARLAR
# ==============================================================================
DOSYA_ADI = "EvAsistaniDB"
NTFY_TOPIC = "yunus_ozel_ev_kanali_123"

st.set_page_config(page_title="Ev Paneli", page_icon="🏠", layout="centered")

# ==============================================================================
# GOOGLE SHEETS BAĞLANTISI (DÜZELTİLDİ)
# ==============================================================================
def baglanti_kur():
    # DÜZELTME BURADA: Sadece spreadsheets yetmez, Drive izni de lazımdı.
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    try:
        # Secrets verisini al
        creds_dict = dict(st.secrets["connections"]["gsheets"])
        
        # Yetkilendirmeyi yap
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        
        # Dosyayı aç
        sheet = client.open(DOSYA_ADI).sheet1
        return sheet
    except Exception as e:
        st.error(f"Hata! Dosya bulunamadı veya yetki yetmedi. Detay: {e}")
        return None

# ==============================================================================
# VERİ İŞLEMLERİ
# ==============================================================================
def verileri_getir():
    sheet = baglanti_kur()
    if sheet:
        data = sheet.get_all_records()
        if not data:
            sheet.append_row(["Urun", "Durum", "Mesaj", "Zaman"])
            return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman"])
        return pd.DataFrame(data)
    return pd.DataFrame()

def urun_ekle(isim):
    sheet = baglanti_kur()
    if sheet:
        sheet.append_row([isim, 0, "", ""])

def urun_durum_degistir(isim, yeni_durum):
    sheet = baglanti_kur()
    if sheet:
        try:
            hucre = sheet.find(isim)
            sheet.update_cell(hucre.row, 2, yeni_durum)
        except: pass

def alarm_ekle(mesaj, zaman):
    sheet = baglanti_kur()
    if sheet:
        sheet.append_row(["", -1, mesaj, zaman])

# ==============================================================================
# BİLDİRİM SİSTEMİ
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
st.markdown("<h2 style='text-align: center;'>🏠 Bulut Ev Paneli</h2>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🛒 MARKET", "⏰ ALARM"])

# Verileri Çek
df = verileri_getir()

# --- TAB 1: MARKET ---
with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        yeni = st.text_input("Hızlı Ekle", placeholder="Ürün adı...", label_visibility="collapsed")
    with col2:
        if st.button("EKLE", use_container_width=True):
            if yeni:
                urun_ekle(yeni)
                st.success("Eklendi!")
                time.sleep(1)
                st.rerun()

    st.divider()

    if not df.empty and "Durum" in df.columns:
        # Alınacaklar (Durum 0)
        alinacaklar = df[df["Durum"] == 0]
        evde_var = df[df["Durum"] == 1]

        st.subheader(f"📌 Alınacaklar ({len(alinacaklar)})")
        
        for index, row in alinacaklar.iterrows():
            if st.checkbox(f"**{row['Urun']}**", key=f"chk_{index}"):
                urun_durum_degistir(row['Urun'], 1)
                st.rerun()

        st.divider()

        with st.expander(f"📦 Evde Var / Geçmiş ({len(evde_var)})"):
            if not evde_var.empty:
                cols = st.columns(3)
                for i, (index, row) in enumerate(evde_var.iterrows()):
                    with cols[i % 3]:
                        if st.button(f"➕ {row['Urun']}", key=f"btn_{index}"):
                            urun_durum_degistir(row['Urun'], 0)
                            st.rerun()
    else:
        st.info("Liste yükleniyor...")

# --- TAB 2: ALARM ---
with tab2:
    with st.form("alarm_form"):
        mesaj = st.text_input("Not", placeholder="Fırını kapat")
        sure = st.number_input("Dakika", min_value=1, value=15)
        if st.form_submit_button("Kaydet"):
            hedef = datetime.now() + timedelta(minutes=sure)
            hedef_str = hedef.strftime("%Y-%m-%d %H:%M:%S")
            
            alarm_ekle(mesaj, hedef_str)
            
            st.success(f"Not alındı! ({hedef.strftime('%H:%M')})")
            bildirim_gonder(f"✅ Alarm kuruldu: {sure} dk sonra '{mesaj}'")
