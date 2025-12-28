import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
from datetime import datetime, timedelta, time as dt_time
import threading
import random

# ==============================================================================
# AYARLAR VE TASARIM
# ==============================================================================
DOSYA_ADI = "EvAsistaniDB"
NTFY_TOPIC = "yunus_ozel_ev_kanali_123"

st.set_page_config(page_title="Bizim Evin Paneli", page_icon="🏡", layout="centered")

# --- MOBİL UYUM CSS ---
st.markdown("""
<style>
    /* Sütunları yan yana zorla */
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        gap: 5px !important;
    }
    div[data-testid="column"] {
        display: flex;
        align-items: center;
        height: 100%;
    }
    button {
        padding: 0.25rem 0.5rem !important;
    }
    /* Karşılama Kutusu */
    .welcome-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .welcome-title {
        font-size: 22px;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .welcome-note {
        font-size: 15px;
        opacity: 0.95;
    }
    /* Link Kutuları */
    .link-box {
        text-decoration: none;
        color: #333;
        background: #f0f2f6;
        padding: 8px;
        border-radius: 5px;
        display: block;
        margin-bottom: 5px;
        text-align: center;
        font-weight: bold;
        border: 1px solid #ddd;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# AKILLI KARŞILAMA (ÇİFTLERE ÖZEL)
# ==============================================================================
def karsilama_paneli():
    saat = datetime.now().hour
    if 5 <= saat < 12: selam = "Günaydın! ☀️"
    elif 12 <= saat < 18: selam = "Tünaydın! 👋"
    elif 18 <= saat < 22: selam = "İyi Akşamlar! 🌙"
    else: selam = "Gece Kuşları, İyi Geceler! 🦉"

    # Ortak sözler
    sozler = [
        "🏡 Evimiz, kalemizdir.",
        "💡 Bütçemizi kontrol edelim, hayallerimize yaklaşalım.",
        "🐈 Prenses'in mamasını/suyunu kontrol ettiniz mi?",
        "❤️ Bugün birbirinize 'Seni Seviyorum' dediniz mi?",
        "🛒 Eksikleri anında yazın, markette unutmayın.",
        "📅 Birlikte planladığınız o tatili unutmayın!",
        "⚡ Faturalar günü gelmeden ödenirse kafa rahat olur.",
    ]
    secilen_soz = random.choice(sozler)

    st.markdown(f"""
    <div class="welcome-box">
        <div class="welcome-title">{selam}</div>
        <div class="welcome-note">{secilen_soz}</div>
    </div>
    """, unsafe_allow_html=True)

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
        try:
            cell = sheet.find(urun_adi)
            sheet.delete_rows(cell.row)
        except:
            tum_veriler = sheet.get_all_values()
            for i, row in enumerate(tum_veriler):
                if row[0] == urun_adi:
                    sheet.delete_rows(i + 1)
                    break 
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
        if not bulundu:
            sheet.append_row([urun, datetime.now().strftime("%Y-%m-%d"), str(miktar), notlar, tip])
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
# HIZLI İŞLEMLER
# ==============================================================================
def hizli_ekle(isim, tip, zaman="", mesaj="", durum="0"):
    yeni_satir = {"Urun": isim, "Durum": durum, "Mesaj": mesaj, "Zaman": str(zaman), "Tip": tip}
    st.session_state.local_df = pd.concat([st.session_state.local_df, pd.DataFrame([yeni_satir])], ignore_index=True)
    t = threading.Thread(target=arka_planda_ekle, args=([isim, durum, mesaj, str(zaman), tip],))
    t.start()

def hizli_yatirim_guncelle(isim, miktar, notlar):
    df = st.session_state.local_df
    mask = (df["Tip"] == "YATIRIM") & (df["Urun"] == isim)
    
    if df[mask].empty:
        hizli_ekle(isim, "YATIRIM", zaman=notlar, mesaj=str(miktar), durum=datetime.now().strftime("%Y-%m-%d"))
    else:
        idx = df[mask].index[0]
        st.session_state.local_df.at[idx, "Mesaj"] = str(miktar)
        st.session_state.local_df.at[idx, "Zaman"] = str(notlar)
        st.session_state.local_df.at[idx, "Durum"] = datetime.now().strftime("%Y-%m-%d")
        t = threading.Thread(target=arka_planda_guncelle_yatirim, args=(isim, miktar, notlar, "YATIRIM"))
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

# CALLBACKLER
def ekleme_callback(input_key, tip):
    val = st.session_state[input_key]
    if val:
        if "," in val:
            for p in val.split(","):
                if p.strip(): hizli_ekle(p.strip(), tip)
        else:
            hizli_ekle(val, tip)
        st.session_state[input_key] = ""

def not_callback():
    baslik = st.session_state.not_baslik
    icerik = st.session_state.not_icerik
    if baslik and icerik:
        hizli_ekle(isim=baslik, tip="NOTE", mesaj=icerik, durum=datetime.now().strftime("%d-%m-%Y"))
        st.session_state.not_baslik = ""
        st.session_state.not_icerik = ""

def sayac_callback():
    ad = st.session_state.sayac_ad
    tarih = st.session_state.sayac_tarih
    if ad:
        # Zaman'a hedef tarihi kaydediyoruz
        hizli_ekle(isim=ad, tip="COUNTDOWN", zaman=str(tarih))
        st.session_state.sayac_ad = ""

def fatura_callback():
    ad = st.session_state.fat_ad
    gun = st.session_state.fat_gun
    saat = st.session_state.fat_saat
    tekrar = st.session_state.fat_tekrar
    if ad:
        tekrar_kod = "HER_AY" if tekrar == "🔁 Her Ay" else "TEK"
        hizli_ekle(isim=ad, tip="FATURA", zaman=gun, mesaj=str(saat)[0:5], durum=tekrar_kod)
        st.session_state.fat_ad = ""

def butce_callback():
    ad = st.session_state.butce_ad
    tutar = st.session_state.butce_tutar
    tur = st.session_state.butce_tur
    if ad and tutar > 0:
        bugun = datetime.now().strftime("%Y-%m-%d")
        hizli_ekle(isim=ad, tip="BUTCE", mesaj=str(tutar), durum=tur, zaman=bugun)
        st.session_state.butce_ad = ""
        st.session_state.butce_tutar = 0

def yatirim_callback():
    ad = st.session_state.yat_ad
    miktar = st.session_state.yat_mik
    notlar = st.session_state.yat_not
    if ad:
        hizli_yatirim_guncelle(ad, miktar, notlar)
        st.session_state.yat_ad = ""
        st.session_state.yat_not = ""

def alarm_kur(mesaj, sure):
    hedef = datetime.now() + timedelta(minutes=sure)
    benzersiz = f"{mesaj} ({hedef.strftime('%H:%M')})"
    hizli_ekle(isim=benzersiz, tip="ALARM", zaman=hedef.strftime("%Y-%m-%d %H:%M:%S"), mesaj=mesaj, durum="-1")
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

# ==============================================================================
# ANA SAYFA
# ==============================================================================
def sayfa_ana_ekran():
    tab1, tab2, tab3 = st.tabs(["🛒 MARKET", "📝 İŞLER", "⏰ ALARM"])
    
    with tab1:
        c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("Market", placeholder="Ürün...", label_visibility="collapsed", key="market_giris")
        with c2: st.button("EKLE", key="btn_m", on_click=ekleme_callback, args=("market_giris", "MARKET"), use_container_width=True)
        st.markdown("---")
        df = st.session_state.local_df
        alinacaklar = df[(df["Tip"] == "MARKET") & (df["Durum"] == "0")]
        tamamlananlar = df[(df["Tip"] == "MARKET") & (df["Durum"] == "1")]

        st.subheader(f"📌 Bekleyenler ({len(alinacaklar)})")
        if alinacaklar.empty: st.success("Sepet Boş!")
        for i, row in alinacaklar.iterrows():
            c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
            with c1:
                if st.checkbox(f"**{row['Urun']}**", key=f"chk_m_{i}"):
                    hizli_durum_degistir(row['Urun'], "1")
                    st.rerun()
            with c2: silme_butonu_koy(f"m_{i}", row['Urun'])
        
        st.divider()
        with st.expander(f"📦 Geçmiş ({len(tamamlananlar)})"):
            for i, row in tamamlananlar.iterrows():
                c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
                with c1:
                    if st.button(f"➕ {row['Urun']}", key=f"back_m_{i}", use_container_width=True):
                        hizli_durum_degistir(row['Urun'], "0")
                        st.rerun()
                with c2: silme_butonu_koy(f"fin_m_{i}", row['Urun'])

    with tab2:
        c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("Görev", placeholder="İş...", label_visibility="collapsed", key="is_giris")
        with c2: st.button("EKLE", key="btn_t", on_click=ekleme_callback, args=("is_giris", "TODO"), use_container_width=True)
        st.markdown("---")
        df_t = st.session_state.local_df[st.session_state.local_df["Tip"] == "TODO"]
        alinacaklar = df_t[df_t["Durum"] == "0"]
        for i, row in alinacaklar.iterrows():
            c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
            with c1:
                if st.checkbox(f"**{row['Urun']}**", key=f"chk_t_{i}"):
                    hizli_durum_degistir(row['Urun'], "1")
                    st.rerun()
            with c2: silme_butonu_koy(f"t_{i}", row['Urun'])

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
            st.markdown("---")
            simdi = datetime.now()
            for i, row in df_a.iterrows():
                try:
                    hedef = datetime.strptime(row["Zaman"], "%Y-%m-%d %H:%M:%S")
                    kalan = (hedef - simdi).total_seconds()
                    c1, c2, c3 = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="center")
                    with c1: st.write(f"**{row['Mesaj']}**"); st.caption(hedef.strftime('%H:%M'))
                    with c2: 
                        if kalan > 0: st.info(f"⏳ {int(kalan/60)} dk")
                        else: st.error("🔔")
                    with c3: silme_butonu_koy(f"al_{i}", row['Urun'])
                    st.divider()
                except: pass

# ==============================================================================
# EKONOMİ
# ==============================================================================
def sayfa_ekonomi():
    tab1, tab2, tab3 = st.tabs(["💸 ÖDEME", "💰 BÜTÇE", "📈 YATIRIM"])

    with tab1:
        with st.expander("➕ Yeni Ödeme", expanded=True):
            c1, c2 = st.columns(2)
            with c1: st.text_input("Adı", key="fat_ad"); st.number_input("Günü", 1, 31, 1, key="fat_gun")
            with c2: st.time_input("Saat", dt_time(9,0), key="fat_saat"); st.radio("Sıklık", ["🔁 Her Ay", "1️⃣ Tek"], key="fat_tekrar")
            st.button("KAYDET", key="btn_f", on_click=fatura_callback, use_container_width=True)
        st.markdown("---")
        df_f = st.session_state.local_df[st.session_state.local_df["Tip"] == "FATURA"]
        if not df_f.empty:
            bugun = datetime.now().day
            df_f["Gun_Sayi"] = pd.to_numeric(df_f["Zaman"], errors='coerce').fillna(32)
            df_f = df_f.sort_values("Gun_Sayi")
            for i, row in df_f.iterrows():
                try:
                    gun = int(row["Gun_Sayi"]); kalan = gun - bugun
                    c1, c2, c3 = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="center")
                    with c1: st.write(f"**{row['Urun']}**"); st.caption(f"{row.get('Mesaj','09:00')} | {row['Durum']}")
                    with c2: 
                        if kalan == 0: st.error("❗ BUGÜN")
                        elif kalan > 0: st.success(f"⏳ {kalan} gün")
                        else: st.warning("Geçti")
                    with c3: silme_butonu_koy(f"fat_{i}", row['Urun'])
                    st.divider()
                except: pass

    with tab2:
        with st.expander("➕ Gelir/Gider", expanded=True):
            c1, c2 = st.columns(2)
            with c1: st.radio("Tür", ["Gider", "Gelir"], horizontal=True, key="butce_tur"); st.text_input("Açıklama", key="butce_ad")
            with c2: st.number_input("Tutar", min_value=0.0, step=100.0, key="butce_tutar"); st.write(""); st.button("KAYDET", key="btn_b", on_click=butce_callback, use_container_width=True)
        st.markdown("---")
        
        # AKILLI BÜTÇE ÇUBUĞU
        df_b = st.session_state.local_df[st.session_state.local_df["Tip"] == "BUTCE"].copy()
        if not df_b.empty:
            df_b["Tarih"] = pd.to_datetime(df_b["Zaman"], errors='coerce').fillna(datetime.now())
            bu_ay = datetime.now().strftime("%Y-%m")
            df_bu_ay = df_b[df_b["Tarih"].dt.strftime('%Y-%m') == bu_ay]
            
            gelir = sum(float(r["Mesaj"]) for _, r in df_bu_ay.iterrows() if r["Durum"] == "Gelir")
            gider = sum(float(r["Mesaj"]) for _, r in df_bu_ay.iterrows() if r["Durum"] == "Gider")
            kalan = gelir - gider
            
            st.subheader(f"📊 Bu Ayın Durumu ({bu_ay})")
            if gelir > 0:
                oran = min(gider / gelir, 1.0)
                st.progress(oran, text=f"Harcama Oranı: %{int(oran*100)}")
                if oran > 0.9: st.error("⚠️ Dikkat! Bütçe sınırındasın.")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Gelir", f"{gelir:.0f}₺")
            c2.metric("Gider", f"{gider:.0f}₺")
            c3.metric("Kalan", f"{kalan:.0f}₺")
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
            with c2: st.text_area("Not", height=100, key="yat_not"); st.button("KAYDET", key="btn_y", on_click=yatirim_callback, use_container_width=True)
        
        df_y = st.session_state.local_df[st.session_state.local_df["Tip"] == "YATIRIM"]
        if not df_y.empty:
            toplam = sum(float(r["Mesaj"]) for _, r in df_y.iterrows() if r["Mesaj"].replace('.','',1).isdigit())
            st.markdown("---")
            st.metric("💰 TOPLAM VARLIK", f"{toplam:,.0f} ₺")
            st.divider()
            for i, row in df_y.iterrows():
                c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="center")
                with c1: st.subheader(f"💎 {row['Urun']}"); st.caption(f"{row['Mesaj']} ₺ | {row['Durum']}")
                with c2: silme_butonu_koy(f"y_{i}", row['Urun'])

# ==============================================================================
# YAŞAM
# ==============================================================================
def sayfa_yasam():
    tab1, tab2, tab3 = st.tabs(["🍽️ YEMEK", "⏳ SAYAÇ", "📒 NOTLAR"])

    with tab1:
        st.caption("Yemekleri ekle, seç ve kura çek!")
        c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("Yemek", key="yemek_giris", label_visibility="collapsed")
        with c2: st.button("EKLE", key="btn_ymk", on_click=ekleme_callback, args=("yemek_giris", "YEMEK"), use_container_width=True)
        st.markdown("---")
        
        df_ymk = st.session_state.local_df[st.session_state.local_df["Tip"] == "YEMEK"]
        havuz = df_ymk[df_ymk["Durum"] == "1"]["Urun"].tolist()
        if havuz:
            if st.button(f"🎲 KURA ÇEK ({len(havuz)})", type="primary", use_container_width=True):
                st.balloons()
                st.success(f"🍽️ Seçim: **{random.choice(havuz)}**")
        
        st.subheader("Liste")
        for i, row in df_ymk.iterrows():
            c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
            with c1:
                checked = (row['Durum'] == "1")
                if st.checkbox(f"**{row['Urun']}**", value=checked, key=f"y_chk_{i}"):
                    if not checked: hizli_durum_degistir(row['Urun'], "1")
                else:
                    if checked: hizli_durum_degistir(row['Urun'], "0")
            with c2: silme_butonu_koy(f"ymk_{i}", row['Urun'])

    with tab2:
        st.caption("Tatile, Yıl dönümüne kaç gün kaldı?")
        with st.expander("➕ Yeni Sayaç", expanded=True):
            st.text_input("Etkinlik Adı", placeholder="Tatil...", key="sayac_ad")
            st.date_input("Tarih", key="sayac_tarih")
            st.button("KAYDET", key="btn_sayac", on_click=sayac_callback, use_container_width=True)
        
        df_s = st.session_state.local_df[st.session_state.local_df["Tip"] == "COUNTDOWN"]
        if not df_s.empty:
            st.markdown("---")
            bugun = datetime.now().date()
            for i, row in df_s.iterrows():
                try:
                    hedef = datetime.strptime(row["Zaman"], "%Y-%m-%d").date()
                    kalan = (hedef - bugun).days
                    c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
                    with c1:
                        st.write(f"🎉 **{row['Urun']}**")
                        if kalan > 0: st.info(f"⏳ **{kalan}** gün kaldı")
                        elif kalan == 0: st.success("🎉 BUGÜN!")
                        else: st.caption(f"{abs(kalan)} gün geçti")
                    with c2: silme_butonu_koy(f"syc_{i}", row['Urun'])
                    st.divider()
                except: pass

    with tab3:
        with st.expander("➕ Not Ekle", expanded=True):
            st.text_input("Başlık", key="not_baslik")
            st.text_area("İçerik", key="not_icerik")
            st.button("KAYDET", key="btn_nt", on_click=not_callback, use_container_width=True)
        
        df_n = st.session_state.local_df[st.session_state.local_df["Tip"] == "NOTE"]
        for i, row in df_n.iterrows():
            with st.expander(f"📒 {row['Urun']}"):
                st.code(row['Mesaj']); silme_butonu_koy(f"nt_{i}", row['Urun'])

# ==============================================================================
# DOSYA
# ==============================================================================
def sayfa_dosya():
    st.subheader("📂 PDF Çevirici")
    dosya = st.file_uploader("Resim Yükle", type=["png", "jpg", "jpeg"])
    if dosya:
        import img2pdf
        st.download_button("⬇️ İndir", img2pdf.convert(dosya.read()), f"{dosya.name}.pdf", "application/pdf")

# ==============================================================================
# ANA İSKELET
# ==============================================================================
karsilama_paneli()

# SOL MENÜ - HIZLI LİNKLER
with st.sidebar:
    st.header("Menü")
    secim = st.radio("Git:", ["🏠 Ana Sayfa", "💰 Ekonomi", "🧬 Yaşam", "📂 Dosya"])
    st.markdown("---")
    st.header("Hızlı Linkler")
    st.markdown('<a href="https://www.turkiye.gov.tr/" target="_blank" class="link-box">🏛️ E-Devlet</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://www.enabiz.gov.tr/" target="_blank" class="link-box">🏥 E-Nabız</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://www.google.com/maps" target="_blank" class="link-box">🗺️ Haritalar</a>', unsafe_allow_html=True)

if secim == "🏠 Ana Sayfa": sayfa_ana_ekran()
elif secim == "💰 Ekonomi": sayfa_ekonomi()
elif secim == "🧬 Yaşam": sayfa_yasam()
elif secim == "📂 Dosya": sayfa_dosya()
