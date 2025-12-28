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
# ARKA PLAN İŞÇİLERİ
# ==============================================================================
def get_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["connections"]["gsheets"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client

def arka_planda_ekle(satir_verisi):
    try:
        client = get_client()
        sheet = client.open(DOSYA_ADI).sheet1
        sheet.append_row(satir_verisi)
    except Exception as e: print(f"Hata: {e}")

def arka_planda_sil(urun_adi):
    try:
        client = get_client()
        sheet = client.open(DOSYA_ADI).sheet1
        cell = sheet.find(urun_adi)
        sheet.delete_rows(cell.row)
    except: pass

def arka_planda_guncelle(urun_adi, yeni_durum):
    try:
        client = get_client()
        sheet = client.open(DOSYA_ADI).sheet1
        cell = sheet.find(urun_adi)
        sheet.update_cell(cell.row, 2, str(yeni_durum))
    except: pass

# ==============================================================================
# YEREL VERİ YÖNETİMİ
# ==============================================================================
def verileri_yukle():
    try:
        client = get_client()
        sheet = client.open(DOSYA_ADI).sheet1
        data = sheet.get_all_values()
        BASLIKLAR = ["Urun", "Durum", "Mesaj", "Zaman", "Tip"]
        
        if not data:
            sheet.append_row(BASLIKLAR)
            return pd.DataFrame(columns=BASLIKLAR)

        if data[0] != BASLIKLAR:
            if "Urun" not in data[0]:
                sheet.insert_row(BASLIKLAR, 1)
                data = sheet.get_all_values()
        
        df = pd.DataFrame(data[1:], columns=data[0])
        for col in BASLIKLAR:
            if col not in df.columns: df[col] = ""
        
        return df.astype(str)
    except:
        return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman", "Tip"])

if 'local_df' not in st.session_state:
    st.session_state.local_df = verileri_yukle()

# ==============================================================================
# HIZLI İŞLEM FONKSİYONLARI
# ==============================================================================
def hizli_ekle(isim, tip, zaman=""):
    # RAM'e ekle
    yeni_satir = {"Urun": isim, "Durum": "0", "Mesaj": "", "Zaman": str(zaman), "Tip": tip}
    st.session_state.local_df = pd.concat([st.session_state.local_df, pd.DataFrame([yeni_satir])], ignore_index=True)
    
    # Google'a gönder
    t = threading.Thread(target=arka_planda_ekle, args=([isim, "0", "", str(zaman), tip],))
    t.start()

def hizli_sil(isim):
    st.session_state.local_df = st.session_state.local_df[st.session_state.local_df["Urun"] != isim]
    t = threading.Thread(target=arka_planda_sil, args=(isim,))
    t.start()

def hizli_durum_degistir(isim, yeni_durum):
    idx = st.session_state.local_df[st.session_state.local_df["Urun"] == isim].index
    if not idx.empty:
        st.session_state.local_df.at[idx[0], "Durum"] = str(yeni_durum)
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
    t = threading.Thread(target=arka_planda_ekle, args=(["", "-1", mesaj, hedef.strftime("%Y-%m-%d %H:%M:%S"), "ALARM"],))
    t.start()
    bildirim_gonder(f"✅ Alarm: {sure} dk sonra '{mesaj}'")

# ==============================================================================
# GÖRÜNÜM BİLEŞENLERİ
# ==============================================================================
def liste_goster(liste_tipi):
    df = st.session_state.local_df
    
    if liste_tipi == "MARKET":
        mask = (df["Tip"] == "MARKET") | (df["Tip"] == "") | (df["Tip"] == "None")
        df_aktif = df[mask]
    else:
        df_aktif = df[df["Tip"] == liste_tipi]

    if not df_aktif.empty:
        alinacaklar = df_aktif[df_aktif["Durum"] == "0"]
        tamamlananlar = df_aktif[df_aktif["Durum"] == "1"]

        st.subheader(f"📌 Bekleyenler ({len(alinacaklar)})")
        if alinacaklar.empty: st.success("Tertemiz! 🎉")
        
        for index, row in alinacaklar.iterrows():
            c1, c2 = st.columns([5, 1])
            with c1:
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
        
        st.divider()

        baslik = "📦 Geçmiş" if liste_tipi == "MARKET" else "✅ Biten İşler"
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

# ==============================================================================
# FATURA HESAPLAMA MODÜLÜ (YENİ)
# ==============================================================================
def fatura_listesi_goster():
    df = st.session_state.local_df
    df_fatura = df[df["Tip"] == "FATURA"]
    
    if df_fatura.empty:
        st.info("Henüz ekli fatura/ödeme yok.")
        return

    st.subheader("🗓️ Aylık Ödemeler")
    bugun = datetime.now().day
    
    # Sıralama yapabilmek için günü sayıya çevir
    df_fatura["Gun_Sayi"] = pd.to_numeric(df_fatura["Zaman"], errors='coerce').fillna(32)
    df_fatura = df_fatura.sort_values("Gun_Sayi")

    for index, row in df_fatura.iterrows():
        try:
            odeme_gunu = int(row["Zaman"])
            kalan = odeme_gunu - bugun
            
            c1, c2, c3 = st.columns([3, 2, 1])
            
            with c1:
                st.write(f"**{row['Urun']}**")
            
            with c2:
                if kalan == 0:
                    st.error("❗ BUGÜN!")
                elif kalan > 0:
                    st.success(f"⏳ {kalan} gün kaldı")
                else:
                    st.caption(f"Gelecek ayın {odeme_gunu}'si")
            
            with c3:
                 if st.button("🗑️", key=f"del_fat_{row['Urun']}"):
                     hizli_sil(row['Urun'])
                     st.rerun()
            st.divider()
        except:
            st.error(f"Hatalı tarih: {row['Urun']}")

# ==============================================================================
# ANA EKRAN
# ==============================================================================
st.markdown("<h3 style='text-align: center;'>⚡ Yunus Hocam'ın Hızlı Asistanı</h3>", unsafe_allow_html=True)

if st.button("🔄 Verileri Yenile", use_container_width=True):
    st.session_state.local_df = verileri_yukle()
    st.rerun()

# 4 SEKME
tab1, tab2, tab3, tab4 = st.tabs(["🛒 MARKET", "📝 İŞLER", "💸 ÖDEMELER", "⏰ ALARM"])

# --- MARKET ---
with tab1:
    c1, c2 = st.columns([3, 1])
    with c1:
        # Key verdik: "market_giris"
        st.text_input("Market", placeholder="Ürün...", label_visibility="collapsed", key="market_giris")
    with c2:
        if st.button("EKLE", key="btn_m", use_container_width=True):
            if st.session_state.market_giris:
                hizli_ekle(st.session_state.market_giris, "MARKET")
                # HİLE BURADA: İçini boşaltıyoruz
                st.session_state.market_giris = "" 
                st.rerun()
    st.markdown("---")
    liste_goster("MARKET")

# --- İŞLER ---
with tab2:
    c1, c2 = st.columns([3, 1])
    with c1:
        st.text_input("Görev", placeholder="İş...", label_visibility="collapsed", key="is_giris")
    with c2:
        if st.button("EKLE", key="btn_t", use_container_width=True):
            if st.session_state.is_giris:
                hizli_ekle(st.session_state.is_giris, "TODO")
                st.session_state.is_giris = "" # Boşalt
                st.rerun()
    st.markdown("---")
    liste_goster("TODO")

# --- ÖDEMELER (YENİ) ---
with tab3:
    st.caption("Her ay tekrarlanan ödemeleri ekle (Örn: Kira, Netflix)")
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1:
        st.text_input("Ödeme Adı", placeholder="Netflix...", label_visibility="collapsed", key="fat_ad")
    with c2:
        st.number_input("Ayın Günü", min_value=1, max_value=31, value=15, label_visibility="collapsed", key="fat_gun")
    with c3:
        if st.button("EKLE", key="btn_f", use_container_width=True):
            if st.session_state.fat_ad:
                hizli_ekle(st.session_state.fat_ad, "FATURA", st.session_state.fat_gun)
                st.session_state.fat_ad = "" # Boşalt
                st.rerun()
    st.markdown("---")
    fatura_listesi_goster()

# --- ALARM ---
with tab4:
    with st.form("alarm"):
        mesaj = st.text_input("Not", placeholder="Fırın...")
        sure = st.number_input("Dakika", min_value=1, value=15)
        if st.form_submit_button("🔔 Kur", use_container_width=True):
            alarm_kur(mesaj, sure)
            st.success("Kuruldu!")
