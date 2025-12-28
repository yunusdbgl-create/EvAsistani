import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
from datetime import datetime, timedelta, time as dt_time
import threading

# ==============================================================================
# AYARLAR
# ==============================================================================
DOSYA_ADI = "EvAsistaniDB"
NTFY_TOPIC = "yunus_ozel_ev_kanali_123"

st.set_page_config(page_title="Ev Asistanı Pro", page_icon="🏠", layout="centered")

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
    except: pass

def arka_planda_sil(urun_adi):
    try:
        client = get_client()
        sheet = client.open(DOSYA_ADI).sheet1
        # Kesin Silme (Terminatör Modu)
        try:
            cell = sheet.find(urun_adi)
            sheet.delete_rows(cell.row)
        except:
            # Bulamazsa manuel ara
            tum_veriler = sheet.get_all_values()
            for i, row in enumerate(tum_veriler):
                if row[0] == urun_adi:
                    sheet.delete_rows(i + 1)
                    break 
    except: pass

def arka_planda_guncelle(urun_adi, yeni_durum):
    try:
        client = get_client()
        sheet = client.open(DOSYA_ADI).sheet1
        try:
            cell = sheet.find(urun_adi)
            sheet.update_cell(cell.row, 2, str(yeni_durum))
        except:
            tum_veriler = sheet.get_all_values()
            for i, row in enumerate(tum_veriler):
                if row[0] == urun_adi:
                    sheet.update_cell(i + 1, 2, str(yeni_durum))
                    break
    except: pass

def bildirim_gonder(mesaj):
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", 
                      data=mesaj.encode('utf-8'),
                      headers={"Title": "Ev Asistanı".encode('utf-8'), "Priority": "high"})
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
# OTOMATİK KONTROL (ÖDEME BİLDİRİMİ)
# ==============================================================================
def odeme_kontrolu_yap():
    """Bugün ödemesi olan var mı bakar ve bildirim atar"""
    if 'odeme_kontrol_yapildi' not in st.session_state:
        df = st.session_state.local_df
        odeme_listesi = df[df["Tip"] == "FATURA"]
        bugun_gun = datetime.now().day
        
        for index, row in odeme_listesi.iterrows():
            try:
                odeme_gunu = int(float(row["Zaman"])) # Bazen string "15.0" gelebilir
                if odeme_gunu == bugun_gun:
                    bildirim_gonder(f"💸 ÖDEME GÜNÜ: {row['Urun']} ödemesini unutma!")
            except: pass
        
        st.session_state.odeme_kontrol_yapildi = True

# Uygulama her açıldığında/yenilendiğinde kontrol et
odeme_kontrolu_yap()

# ==============================================================================
# HIZLI İŞLEM FONKSİYONLARI
# ==============================================================================
def hizli_ekle(isim, tip, zaman="", mesaj="", durum="0"):
    # RAM Ekleme
    yeni_satir = {"Urun": isim, "Durum": durum, "Mesaj": mesaj, "Zaman": str(zaman), "Tip": tip}
    st.session_state.local_df = pd.concat([st.session_state.local_df, pd.DataFrame([yeni_satir])], ignore_index=True)
    # Google Ekleme
    t = threading.Thread(target=arka_planda_ekle, args=([isim, durum, mesaj, str(zaman), tip],))
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

# CALLBACKLER (VİRGÜL AYIRMA BURADA)
def ekleme_callback(input_key, tip):
    val = st.session_state[input_key]
    if val:
        # VİRGÜL VARSA PARÇALA
        if "," in val:
            parcalar = val.split(",")
            for p in parcalar:
                temiz_isim = p.strip() # Boşlukları temizle
                if temiz_isim:
                    hizli_ekle(temiz_isim, tip)
        else:
            hizli_ekle(val, tip)
            
        st.session_state[input_key] = ""

def fatura_callback():
    ad = st.session_state.fat_ad
    gun = st.session_state.fat_gun
    saat = st.session_state.fat_saat
    tekrar = st.session_state.fat_tekrar
    if ad:
        tekrar_kod = "HER_AY" if tekrar == "🔁 Her Ay" else "TEK"
        saat_str = str(saat)[0:5]
        hizli_ekle(isim=ad, tip="FATURA", zaman=gun, mesaj=saat_str, durum=tekrar_kod)
        st.session_state.fat_ad = ""

def butce_callback():
    ad = st.session_state.butce_ad
    tutar = st.session_state.butce_tutar
    tur = st.session_state.butce_tur # Gelir / Gider
    
    if ad and tutar > 0:
        # Bütçe için: Mesaj=Tutar, Durum=Gelir/Gider
        hizli_ekle(isim=ad, tip="BUTCE", mesaj=str(tutar), durum=tur)
        st.session_state.butce_ad = ""
        st.session_state.butce_tutar = 0

def alarm_kur(mesaj, sure):
    hedef = datetime.now() + timedelta(minutes=sure)
    hedef_str = hedef.strftime("%Y-%m-%d %H:%M:%S")
    benzersiz_ad = f"{mesaj} ({hedef.strftime('%H:%M')})"
    hizli_ekle(isim=benzersiz_ad, tip="ALARM", zaman=hedef_str, mesaj=mesaj, durum="-1")
    bildirim_gonder(f"✅ Alarm: {sure} dk sonra '{mesaj}'")

# ==============================================================================
# GÖRÜNÜM BİLEŞENLERİ
# ==============================================================================
def silme_butonu_koy(key_prefix, urun_adi):
    sil_key = f"del_{key_prefix}_{urun_adi}"
    conf_key = f"conf_{key_prefix}_{urun_adi}"
    
    if not st.session_state.get(conf_key):
        if st.button("🗑️", key=sil_key):
            st.session_state[conf_key] = True
            st.rerun()
    else:
        if st.button("Sil?", key=f"yes_{sil_key}", type="primary"):
            hizli_sil(urun_adi)
            st.session_state[conf_key] = False
            st.rerun()
        st.caption("İptal: Yenile")

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
                if st.checkbox(f"**{row['Urun']}**", key=f"chk_{liste_tipi}_{index}"):
                    hizli_durum_degistir(row['Urun'], "1")
                    st.rerun()
            with c2:
                silme_butonu_koy(f"{liste_tipi}_{index}", row['Urun'])
        
        st.divider()

        baslik = "📦 Geçmiş" if liste_tipi == "MARKET" else "✅ Biten İşler"
        with st.expander(f"{baslik} ({len(tamamlananlar)})"):
            for index, row in tamamlananlar.iterrows():
                c_a, c_b = st.columns([4, 1])
                with c_a:
                    if st.button(f"➕ {row['Urun']}", key=f"back_{liste_tipi}_{index}", use_container_width=True):
                        hizli_durum_degistir(row['Urun'], "0")
                        st.rerun()
                with c_b:
                    silme_butonu_koy(f"fin_{liste_tipi}_{index}", row['Urun'])

def fatura_listesi_goster():
    df = st.session_state.local_df
    df_fatura = df[df["Tip"] == "FATURA"]
    if df_fatura.empty:
        st.info("Ödeme yok.")
        return

    st.subheader("🗓️ Ödeme Takvimi")
    bugun = datetime.now().day
    df_fatura["Gun_Sayi"] = pd.to_numeric(df_fatura["Zaman"], errors='coerce').fillna(32)
    df_fatura = df_fatura.sort_values("Gun_Sayi")

    for index, row in df_fatura.iterrows():
        try:
            odeme_gunu = int(row["Gun_Sayi"])
            kalan = odeme_gunu - bugun
            saat = row["Mesaj"] if row["Mesaj"] else "09:00"
            tekrar = row["Durum"]
            icon = "🔁" if tekrar == "HER_AY" else "1️⃣"
            
            with st.container():
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    st.write(f"**{row['Urun']}**")
                    st.caption(f"🕒 {saat} | {icon}")
                with c2:
                    if kalan == 0: st.error("❗ BUGÜN!")
                    elif kalan > 0: st.success(f"⏳ {kalan} gün")
                    else: st.warning("Günü geçti")
                with c3:
                    silme_butonu_koy(f"fat_{index}", row['Urun'])
            st.divider()
        except: pass

def butce_goster():
    df = st.session_state.local_df
    df_butce = df[df["Tip"] == "BUTCE"]
    
    # Hesaplama
    toplam_gelir = 0
    toplam_gider = 0
    
    if not df_butce.empty:
        for index, row in df_butce.iterrows():
            try:
                tutar = float(row["Mesaj"])
                if row["Durum"] == "Gelir":
                    toplam_gelir += tutar
                else:
                    toplam_gider += tutar
            except: pass

    kalan = toplam_gelir - toplam_gider

    # Özet Kartları
    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Gelir", f"{toplam_gelir} ₺", delta_color="normal")
    c2.metric("Toplam Gider", f"{toplam_gider} ₺", delta_color="inverse")
    c3.metric("Kalan", f"{kalan} ₺", delta=kalan, delta_color="normal")

    st.divider()
    
    # Liste
    if not df_butce.empty:
        st.subheader("📋 Hareketler")
        for index, row in df_butce.iterrows():
            c1, c2, c3 = st.columns([3, 2, 1])
            with c1:
                renk = "🟢" if row["Durum"] == "Gelir" else "🔴"
                st.write(f"{renk} **{row['Urun']}**")
            with c2:
                st.write(f"{row['Mesaj']} ₺")
            with c3:
                silme_butonu_koy(f"butce_{index}", row['Urun'])
            st.divider()

def alarm_listesi_goster():
    df = st.session_state.local_df
    df_alarm = df[df["Tip"] == "ALARM"]
    if df_alarm.empty: return

    st.markdown("---")
    st.subheader("⏳ Aktif Alarmlar")
    simdi = datetime.now()

    for index, row in df_alarm.iterrows():
        try:
            hedef_zaman = datetime.strptime(row["Zaman"], "%Y-%m-%d %H:%M:%S")
            kalan_sure = hedef_zaman - simdi
            toplam_saniye = kalan_sure.total_seconds()
            
            c1, c2, c3 = st.columns([3, 2, 1])
            with c1:
                st.write(f"**{row['Mesaj']}**")
                st.caption(f"Hedef: {hedef_zaman.strftime('%H:%M')}")
            with c2:
                if toplam_saniye > 0:
                    dakika = int(toplam_saniye / 60)
                    st.info(f"⏳ {dakika} dk")
                else:
                    st.error("🔔 DOLDU")
            with c3:
                silme_butonu_koy(f"alarm_{index}", row['Urun'])
            st.divider()
        except: pass

# ==============================================================================
# ANA EKRAN
# ==============================================================================
st.markdown("<h3 style='text-align: center;'>⚡ Ev Asistanı Pro</h3>", unsafe_allow_html=True)

if st.button("🔄 Verileri Yenile", use_container_width=True):
    st.session_state.local_df = verileri_yukle()
    st.rerun()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🛒 MARKET", "📝 İŞLER", "💸 ÖDEMELER", "💰 BÜTÇE", "⏰ ALARM"])

with tab1:
    c1, c2 = st.columns([3, 1])
    with c1:
        st.text_input("Market (Virgülle ayırabilirsin)", placeholder="Süt, Ekmek, Yumurta...", label_visibility="collapsed", key="market_giris")
    with c2:
        st.button("EKLE", key="btn_m", on_click=ekleme_callback, args=("market_giris", "MARKET"), use_container_width=True)
    st.markdown("---")
    liste_goster("MARKET")

with tab2:
    c1, c2 = st.columns([3, 1])
    with c1:
        st.text_input("Görev (Virgülle ayırabilirsin)", placeholder="Fatura, Araba...", label_visibility="collapsed", key="is_giris")
    with c2:
        st.button("EKLE", key="btn_t", on_click=ekleme_callback, args=("is_giris", "TODO"), use_container_width=True)
    st.markdown("---")
    liste_goster("TODO")

with tab3:
    with st.expander("➕ Yeni Ödeme Ekle", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Ödeme Adı", placeholder="Kira...", key="fat_ad")
            st.number_input("Ayın Günü", min_value=1, max_value=31, value=1, key="fat_gun")
        with c2:
            st.time_input("Saat", value=dt_time(9, 0), key="fat_saat")
            st.radio("Sıklık", ["🔁 Her Ay", "1️⃣ Tek Seferlik"], key="fat_tekrar")
        st.button("KAYDET", key="btn_f", on_click=fatura_callback, use_container_width=True)
    st.markdown("---")
    fatura_listesi_goster()

with tab4:
    with st.expander("➕ Gelir / Gider Ekle", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.radio("Tür", ["Gider", "Gelir"], horizontal=True, key="butce_tur")
            st.text_input("Açıklama", placeholder="Maaş, Market...", key="butce_ad")
        with c2:
            st.number_input("Tutar (TL)", min_value=0, value=0, key="butce_tutar")
            st.write("") # Boşluk
            st.write("")
            st.button("KAYDET", key="btn_b", on_click=butce_callback, use_container_width=True)
    st.markdown("---")
    butce_goster()

with tab5:
    with st.form("alarm"):
        mesaj = st.text_input("Not", placeholder="Fırın...")
        sure = st.number_input("Dakika", min_value=1, value=15)
        if st.form_submit_button("🔔 Kur", use_container_width=True):
            alarm_kur(mesaj, sure)
            st.success("Kuruldu!")
            time.sleep(1)
            st.rerun()
    alarm_listesi_goster()
