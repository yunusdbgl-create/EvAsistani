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

st.set_page_config(page_title="Hızlı Ev Paneli", page_icon="🏠", layout="centered")

# ==============================================================================
# ARKA PLAN İŞÇİLERİ (GİZLİ KAHRAMANLAR)
# ==============================================================================
def get_client():
    """Her thread kendi bağlantısını açar"""
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["connections"]["gsheets"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client

def arka_planda_ekle(satir_verisi):
    """Google'a veriyi arkadan gönderir"""
    try:
        client = get_client()
        sheet = client.open(DOSYA_ADI).sheet1
        sheet.append_row(satir_verisi)
    except Exception as e:
        print(f"Senkron hatası (Ekle): {e}")

def arka_planda_sil(urun_adi):
    """Google'dan veriyi arkadan siler"""
    try:
        client = get_client()
        sheet = client.open(DOSYA_ADI).sheet1
        cell = sheet.find(urun_adi)
        sheet.delete_rows(cell.row)
    except Exception as e:
        print(f"Senkron hatası (Sil): {e}")

def arka_planda_guncelle(urun_adi, yeni_durum):
    """Google'da durumu arkadan günceller"""
    try:
        client = get_client()
        sheet = client.open(DOSYA_ADI).sheet1
        cell = sheet.find(urun_adi)
        sheet.update_cell(cell.row, 2, str(yeni_durum))
    except Exception as e:
        print(f"Senkron hatası (Güncelle): {e}")

# ==============================================================================
# YEREL VERİ YÖNETİMİ (HIZ İÇİN RAM KULLANIMI)
# ==============================================================================
def verileri_yukle():
    """Veriyi sadece ilk açılışta Google'dan çeker"""
    client = get_client()
    try:
        sheet = client.open(DOSYA_ADI).sheet1
        data = sheet.get_all_values()
        BASLIKLAR = ["Urun", "Durum", "Mesaj", "Zaman", "Tip"]
        
        if not data:
            sheet.append_row(BASLIKLAR)
            return pd.DataFrame(columns=BASLIKLAR)

        # Başlık kontrolü ve düzeltme
        if data[0] != BASLIKLAR:
            if "Urun" not in data[0]:
                sheet.insert_row(BASLIKLAR, 1)
                data = sheet.get_all_values()
        
        df = pd.DataFrame(data[1:], columns=data[0])
        # Temizlik
        for col in BASLIKLAR:
            if col not in df.columns: df[col] = ""
        
        return df.astype(str)
    except:
        return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman", "Tip"])

# Session State Başlat (RAM Hafızası)
if 'local_df' not in st.session_state:
    st.session_state.local_df = verileri_yukle()

# ==============================================================================
# HIZLI İŞLEM FONKSİYONLARI (ANINDA TEPKİ)
# ==============================================================================
def hizli_ekle(isim, tip):
    # 1. Ekranda hemen göster (RAM'e ekle)
    yeni_satir = {"Urun": isim, "Durum": "0", "Mesaj": "", "Zaman": "", "Tip": tip}
    st.session_state.local_df = pd.concat([st.session_state.local_df, pd.DataFrame([yeni_satir])], ignore_index=True)
    
    # 2. Arka planda Google'a gönder (Thread)
    t = threading.Thread(target=arka_planda_ekle, args=([isim, "0", "", "", tip],))
    t.start()

def hizli_sil(isim):
    # 1. Ekranda hemen sil
    st.session_state.local_df = st.session_state.local_df[st.session_state.local_df["Urun"] != isim]
    
    # 2. Arka planda Google'dan sil
    t = threading.Thread(target=arka_planda_sil, args=(isim,))
    t.start()

def hizli_durum_degistir(isim, yeni_durum):
    # 1. Ekranda hemen güncelle
    idx = st.session_state.local_df[st.session_state.local_df["Urun"] == isim].index
    if not idx.empty:
        st.session_state.local_df.at[idx[0], "Durum"] = str(yeni_durum)
    
    # 2. Arka planda Google'ı güncelle
    t = threading.Thread(target=arka_planda_guncelle, args=(isim, yeni_durum))
    t.start()

def bildirim_gonder(mesaj):
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", 
                      data=mesaj.encode('utf-8'),
                      headers={"Title": "Ev Asistanı".encode('utf-8'), "Priority": "high"})
    except: pass

def alarm_kur(mesaj, sure):
    hedef = datetime.now() + timedelta(minutes=sure)
    hedef_str = hedef.strftime("%Y-%m-%d %H:%M:%S")
    # Alarmlar genelde kritik değildir, direkt arkaya atalım
    t = threading.Thread(target=arka_planda_ekle, args=(["", "-1", mesaj, hedef_str, "ALARM"],))
    t.start()
    bildirim_gonder(f"✅ Alarm: {sure} dk sonra '{mesaj}'")

# ==============================================================================
# GÖRÜNÜM (AYNI KALDI)
# ==============================================================================
def liste_goster(liste_tipi):
    df = st.session_state.local_df # RAM'den oku (HIZLI)
    
    if liste_tipi == "MARKET":
        mask = (df["Tip"] == "MARKET") | (df["Tip"] == "") | (df["Tip"] == "None")
        df_aktif = df[mask]
    else:
        df_aktif = df[df["Tip"] == liste_tipi]

    if not df_aktif.empty:
        alinacaklar = df_aktif[df_aktif["Durum"] == "0"]
        tamamlananlar = df_aktif[df_aktif["Durum"] == "1"]

        st.subheader(f"📌 Bekleyenler ({len(alinacaklar)})")
        if alinacaklar.empty: st.success("Temiz! 🎉")
        
        for index, row in alinacaklar.iterrows():
            c1, c2 = st.columns([5, 1])
            with c1:
                # Checkbox
                if st.checkbox(f"**{row['Urun']}**", key=f"chk_{liste_tipi}_{row['Urun']}"):
                    hizli_durum_degistir(row['Urun'], "1")
                    st.rerun()
            with c2:
                # Silme Onayı
                sil_key = f"del_{liste_tipi}_{row['Urun']}"
                conf_key = f"conf_{liste_tipi}_{row['Urun']}"
                if not st.session_state.get(conf_key):
                    if st.button("🗑️", key=sil_key):
                        st.session_state[conf_key] = True
                        st.rerun()
                else:
                    if st.button("Sil?", key=f"yes_{sil_key}", type="primary"):
                        hizli_sil(row['Urun'])
                        st.session_state[conf_key] = False
                        st.rerun()
                    st.caption("İptal: Yenile")
        
        st.divider()

        baslik = "📦 Evde Var / Geçmiş" if liste_tipi == "MARKET" else "✅ Biten İşler"
        with st.expander(f"{baslik} ({len(tamamlananlar)})"):
            for index, row in tamamlananlar.iterrows():
                c_a, c_b = st.columns([4, 1])
                with c_a:
                    if st.button(f"➕ {row['Urun']}", key=f"back_{liste_tipi}_{row['Urun']}", use_container_width=True):
                        hizli_durum_degistir(row['Urun'], "0")
                        st.rerun()
                with c_b:
                    if st.button("🗑️", key=f"delfin_{liste_tipi}_{row['Urun']}"):
                        hizli_sil(row['Urun'])
                        st.rerun()
    else:
        st.info("Liste boş.")

# ==============================================================================
# ANA EKRAN
# ==============================================================================
st.markdown("<h3 style='text-align: center;'>⚡ Yunus Hocam'ın Hızlı Asistanı</h3>", unsafe_allow_html=True)

# Manuel Yenileme Butonu (Senkronize Etmek İçin)
if st.button("🔄 Verileri Google'dan Taze Çek", use_container_width=True):
    st.session_state.local_df = verileri_yukle()
    st.rerun()

tab1, tab2, tab3 = st.tabs(["🛒 MARKET", "📝 YAPILACAKLAR", "⏰ ALARM"])

with tab1:
    c1, c2 = st.columns([3, 1])
    with c1:
        yeni_m = st.text_input("Market", placeholder="Ürün...", label_visibility="collapsed", key="in_m")
    with c2:
        if st.button("EKLE", key="btn_m", use_container_width=True):
            if yeni_m:
                hizli_ekle(yeni_m, "MARKET")
                st.rerun() # Bekleme yok!
    st.markdown("---")
    liste_goster("MARKET")

with tab2:
    c1, c2 = st.columns([3, 1])
    with c1:
        yeni_t = st.text_input("Görev", placeholder="İş...", label_visibility="collapsed", key="in_t")
    with c2:
        if st.button("EKLE", key="btn_t", use_container_width=True):
            if yeni_t:
                hizli_ekle(yeni_t, "TODO")
                st.rerun() # Bekleme yok!
    st.markdown("---")
    liste_goster("TODO")

with tab3:
    with st.form("alarm"):
        mesaj = st.text_input("Not", placeholder="Fırın...")
        sure = st.number_input("Dakika", min_value=1, value=15)
        if st.form_submit_button("🔔 Kur", use_container_width=True):
            alarm_kur(mesaj, sure)
            st.success("Kuruldu!")
