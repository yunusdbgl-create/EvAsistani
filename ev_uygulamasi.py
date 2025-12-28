import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import threading

# ==============================================================================
# AYARLAR
# ==============================================================================
# Google Sheet'teki sayfa adın (Altta yazar, genelde Sayfa1 veya Sheet1)
SHEET_NAME = "Sheet1" 
NTFY_TOPIC = "yunus_ozel_ev_kanali_123" 

st.set_page_config(page_title="Ev Paneli", page_icon="🏠", layout="centered")

# ==============================================================================
# GOOGLE SHEETS BAĞLANTISI
# ==============================================================================
# Bağlantıyı kur (Secrets kısmından okur)
conn = st.connection("gsheets", type=GSheetsConnection)

def verileri_getir():
    # Cache kullanmıyoruz (ttl=0), hep taze veri gelsin
    try:
        df = conn.read(worksheet=SHEET_NAME, ttl=0)
        # Eğer tablo boşsa veya sütunlar yoksa oluşturur
        if df.empty or "Urun" not in df.columns:
            df = pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman"])
            conn.update(worksheet=SHEET_NAME, data=df)
        return df
    except:
        # İlk açılışta hata verirse boş tablo oluştur
        df = pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman"])
        return df

def veri_ekle_guncelle(df):
    conn.update(worksheet=SHEET_NAME, data=df)

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
st.caption("Veriler Google Sheets üzerinde saklanıyor.")

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
                # Yeni satır ekle: Urun=yeni, Durum=0 (Alınacak), diğerleri boş
                yeni_satir = pd.DataFrame([{"Urun": yeni, "Durum": 0, "Mesaj": "", "Zaman": ""}])
                df = pd.concat([df, yeni_satir], ignore_index=True)
                veri_ekle_guncelle(df)
                st.rerun()

    st.divider()

    # Alınacaklar (Durum == 0)
    alinacaklar = df[df["Durum"] == 0]
    evde_var = df[df["Durum"] == 1]

    st.subheader(f"📌 Alınacaklar ({len(alinacaklar)})")
    
    # Döngüde index'i kullanmamız lazım güncellemek için
    for index, row in alinacaklar.iterrows():
        # Checkbox işaretlenirse Durum'u 1 yap
        if st.checkbox(f"**{row['Urun']}**", key=f"chk_{index}"):
            df.at[index, "Durum"] = 1
            veri_ekle_guncelle(df)
            st.rerun()

    st.divider()

    with st.expander(f"📦 Evde Var / Geçmiş ({len(evde_var)})"):
        if not evde_var.empty:
            cols = st.columns(3)
            for i, (index, row) in enumerate(evde_var.iterrows()):
                with cols[i % 3]:
                    if st.button(f"➕ {row['Urun']}", key=f"btn_{index}"):
                        df.at[index, "Durum"] = 0
                        veri_ekle_guncelle(df)
                        st.rerun()

# --- TAB 2: ALARM (Basit Versiyon) ---
with tab2:
    st.info("Bulut sistemlerinde anlık arka plan zamanlayıcısı bazen uykuya dalar. Alarmı kurduğunda saati Google Sheet'e yazarım.")
    
    with st.form("alarm_form"):
        mesaj = st.text_input("Not", placeholder="Fırını kapat")
        sure = st.number_input("Dakika", min_value=1, value=15)
        if st.form_submit_button("Kaydet"):
            hedef = datetime.now() + timedelta(minutes=sure)
            hedef_str = hedef.strftime("%Y-%m-%d %H:%M:%S")
            
            # Alarmı da tabloya ekliyoruz (Urun kısmı boş)
            yeni_alarm = pd.DataFrame([{"Urun": "", "Durum": -1, "Mesaj": mesaj, "Zaman": hedef_str}])
            df = pd.concat([df, yeni_alarm], ignore_index=True)
            veri_ekle_guncelle(df)
            
            st.success(f"Not alındı! ({hedef.strftime('%H:%M')})")
            # Anlık bildirim atalım ki çalıştığı belli olsun
            bildirim_gonder(f"✅ Alarm kuruldu: {sure} dk sonra '{mesaj}'")
