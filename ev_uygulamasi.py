import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
from datetime import datetime, timedelta, time as dt_time
import threading
import io

# ==============================================================================
# AYARLAR VE TASARIM
# ==============================================================================
DOSYA_ADI = "EvAsistaniDB"
NTFY_TOPIC = "yunus_ozel_ev_kanali_123"

st.set_page_config(page_title="Ev Asistanı Pro", page_icon="📱", layout="centered")

# --- CSS (Mobil Uyum) ---
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
    /* Hava Durumu Çerçevesi */
    .weather-frame {
        width: 100%;
        height: 150px;
        border: none;
        border-radius: 10px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# HAVA DURUMU (IFRAME YÖNTEMİ - KESİN ÇÖZÜM)
# ==============================================================================
def hava_durumu_goster():
    """Hava durumunu sunucudan değil, direkt tarayıcıdan çeker"""
    # wttr.in sitesini bir pencere gibi gömeriz
    st.markdown("""
        <iframe class="weather-frame" 
        src="https://wttr.in/Istanbul?lang=tr&format=3&m" 
        scrolling="no"></iframe>
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
# OTOMATİK KONTROL
# ==============================================================================
def odeme_kontrolu_yap():
    if 'odeme_kontrol_yapildi' not in st.session_state:
        df = st.session_state.local_df
        odeme_listesi = df[df["Tip"] == "FATURA"]
        bugun_gun = datetime.now().day
        
        for index, row in odeme_listesi.iterrows():
            try:
                odeme_gunu = int(float(row["Zaman"]))
                if odeme_gunu == bugun_gun:
                    bildirim_gonder(f"💸 ÖDEME GÜNÜ: {row['Urun']} ödemesini unutma!")
            except: pass
        st.session_state.odeme_kontrol_yapildi = True

odeme_kontrolu_yap()

# ==============================================================================
# HIZLI İŞLEM FONKSİYONLARI
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
            parcalar = val.split(",")
            for p in parcalar:
                temiz = p.strip()
                if temiz: hizli_ekle(temiz, tip)
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
    hedef_str = hedef.strftime("%Y-%m-%d %H:%M:%S")
    benzersiz_ad = f"{mesaj} ({hedef.strftime('%H:%M')})"
    hizli_ekle(isim=benzersiz_ad, tip="ALARM", zaman=hedef_str, mesaj=mesaj, durum="-1")
    bildirim_gonder(f"✅ Alarm: {sure} dk sonra '{mesaj}'")

# ==============================================================================
# GÖRÜNÜM PARÇALARI
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
# 1. SAYFA: EV ASİSTANI
# ==============================================================================
def sayfa_ev_asistani():
    if st.button("🔄 Verileri Yenile", use_container_width=True):
        st.session_state.local_df = verileri_yukle()
        st.rerun()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🛒 MARKET", "📝 İŞLER", "💸 ÖDEME", "💰 BÜTÇE", "📈 YATIRIM", "⏰ ALARM"])

    # 1. Market
    with tab1:
        c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="bottom")
        with c1:
            st.text_input("Market", placeholder="Ürün...", label_visibility="collapsed", key="market_giris")
        with c2:
            st.button("EKLE", key="btn_m", on_click=ekleme_callback, args=("market_giris", "MARKET"), use_container_width=True)
        st.markdown("---")
        df = st.session_state.local_df
        mask = (df["Tip"] == "MARKET") | (df["Tip"] == "") | (df["Tip"] == "None")
        df_aktif = df[mask]
        
        alinacaklar = df_aktif[df_aktif["Durum"] == "0"]
        tamamlananlar = df_aktif[df_aktif["Durum"] == "1"]

        st.subheader(f"📌 Bekleyenler ({len(alinacaklar)})")
        if alinacaklar.empty: st.success("Temiz!")
        for index, row in alinacaklar.iterrows():
            c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
            with c1:
                if st.checkbox(f"**{row['Urun']}**", key=f"chk_m_{index}"):
                    hizli_durum_degistir(row['Urun'], "1")
                    st.rerun()
            with c2: silme_butonu_koy(f"m_{index}", row['Urun'])
        
        st.divider()
        with st.expander(f"📦 Geçmiş ({len(tamamlananlar)})"):
            for index, row in tamamlananlar.iterrows():
                c_a, c_b = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
                with c_a:
                    if st.button(f"➕ {row['Urun']}", key=f"back_m_{index}", use_container_width=True):
                        hizli_durum_degistir(row['Urun'], "0")
                        st.rerun()
                with c_b: silme_butonu_koy(f"fin_m_{index}", row['Urun'])

    # 2. İşler
    with tab2:
        c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="bottom")
        with c1:
            st.text_input("Görev", placeholder="İş...", label_visibility="collapsed", key="is_giris")
        with c2:
            st.button("EKLE", key="btn_t", on_click=ekleme_callback, args=("is_giris", "TODO"), use_container_width=True)
        st.markdown("---")
        df_t = st.session_state.local_df[st.session_state.local_df["Tip"] == "TODO"]
        alinacaklar = df_t[df_t["Durum"] == "0"]
        tamamlananlar = df_t[df_t["Durum"] == "1"]
        
        st.subheader(f"📌 Bekleyenler ({len(alinacaklar)})")
        if alinacaklar.empty: st.success("Temiz!")
        for index, row in alinacaklar.iterrows():
            c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
            with c1:
                if st.checkbox(f"**{row['Urun']}**", key=f"chk_t_{index}"):
                    hizli_durum_degistir(row['Urun'], "1")
                    st.rerun()
            with c2: silme_butonu_koy(f"t_{index}", row['Urun'])
            
        with st.expander(f"✅ Bitenler ({len(tamamlananlar)})"):
            for index, row in tamamlananlar.iterrows():
                c_a, c_b = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
                with c_a:
                    if st.button(f"➕ {row['Urun']}", key=f"back_t_{index}", use_container_width=True):
                        hizli_durum_degistir(row['Urun'], "0")
                        st.rerun()
                with c_b: silme_butonu_koy(f"fin_t_{index}", row['Urun'])

    # 3. Ödeme
    with tab3:
        with st.expander("➕ Yeni Ödeme", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Adı", placeholder="Kira...", key="fat_ad")
                st.number_input("Günü", 1, 31, 1, key="fat_gun")
            with c2:
                st.time_input("Saat", dt_time(9, 0), key="fat_saat")
                st.radio("Sıklık", ["🔁 Her Ay", "1️⃣ Tek Seferlik"], key="fat_tekrar")
            st.button("KAYDET", key="btn_f", on_click=fatura_callback, use_container_width=True)
        st.markdown("---")
        
        df_fatura = st.session_state.local_df[st.session_state.local_df["Tip"] == "FATURA"]
        if not df_fatura.empty:
            bugun = datetime.now().day
            df_fatura["Gun_Sayi"] = pd.to_numeric(df_fatura["Zaman"], errors='coerce').fillna(32)
            df_fatura = df_fatura.sort_values("Gun_Sayi")
            for index, row in df_fatura.iterrows():
                try:
                    odeme_gunu = int(row["Gun_Sayi"])
                    kalan = odeme_gunu - bugun
                    saat = row["Mesaj"] if row["Mesaj"] else "09:00"
                    icon = "🔁" if row["Durum"] == "HER_AY" else "1️⃣"
                    with st.container():
                        c1, c2, c3 = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="center")
                        with c1:
                            st.write(f"**{row['Urun']}**")
                            st.caption(f"🕒 {saat} | {icon}")
                        with c2:
                            if kalan == 0: st.error("❗ BUGÜN")
                            elif kalan > 0: st.success(f"⏳ {kalan} gün")
                            else: st.warning("Geçti")
                        with c3: silme_butonu_koy(f"fat_{index}", row['Urun'])
                    st.divider()
                except: pass

    # 4. Bütçe
    with tab4:
        with st.expander("➕ Gelir / Gider Ekle", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                st.radio("Tür", ["Gider", "Gelir"], horizontal=True, key="butce_tur")
                st.text_input("Açıklama", placeholder="Maaş...", key="butce_ad")
            with c2:
                st.number_input("Tutar (TL)", min_value=0.0, step=100.0, key="butce_tutar")
                st.write("")
                st.write("")
                st.button("KAYDET", key="btn_b", on_click=butce_callback, use_container_width=True)
        st.markdown("---")
        df_butce = st.session_state.local_df[st.session_state.local_df["Tip"] == "BUTCE"].copy()
        if not df_butce.empty:
            df_butce["TarihObj"] = pd.to_datetime(df_butce["Zaman"], errors='coerce').fillna(datetime.now())
            df_butce["Ay_Yil"] = df_butce["TarihObj"].dt.strftime('%Y-%m')
            
            gruplar = sorted(df_butce["Ay_Yil"].unique(), reverse=True)
            for grup in gruplar:
                bu_ay_str = datetime.now().strftime("%Y-%m")
                expanded = (grup == bu_ay_str)
                with st.expander(f"📅 {grup}", expanded=expanded):
                    df_grup = df_butce[df_butce["Ay_Yil"] == grup]
                    gelir = sum(float(r["Mesaj"]) for _, r in df_grup.iterrows() if r["Durum"] == "Gelir")
                    gider = sum(float(r["Mesaj"]) for _, r in df_grup.iterrows() if r["Durum"] == "Gider")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Gelir", f"{gelir:.0f}₺")
                    c2.metric("Gider", f"{gider:.0f}₺")
                    c3.metric("Kalan", f"{gelir-gider:.0f}₺")
                    st.divider()
                    for index, row in df_grup.iterrows():
                        c_a, c_b, c_c = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="center")
                        with c_a: st.write(f"{'🟢' if row['Durum']=='Gelir' else '🔴'} **{row['Urun']}**")
                        with c_b: st.write(f"{row['Mesaj']} ₺")
                        with c_c: silme_butonu_koy(f"butce_{index}", row['Urun'])

    # 5. Yatırım
    with tab5:
        with st.expander("➕ Varlık Ekle", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Varlık", placeholder="Altın...", key="yat_ad")
                st.number_input("Değer (TL)", min_value=0.0, step=100.0, key="yat_mik")
            with c2:
                st.text_area("Notlar", height=100, key="yat_not")
                st.button("KAYDET", key="btn_y", on_click=yatirim_callback, use_container_width=True)
        st.markdown("---")
        df_yat = st.session_state.local_df[st.session_state.local_df["Tip"] == "YATIRIM"]
        if not df_yat.empty:
            toplam = sum(float(r["Mesaj"]) for _, r in df_yat.iterrows() if r["Mesaj"].replace('.','',1).isdigit())
            st.metric("💰 TOPLAM", f"{toplam:,.0f} ₺")
            st.divider()
            for index, row in df_yat.iterrows():
                with st.container():
                    c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="center")
                    with c1:
                        st.subheader(f"💎 {row['Urun']}")
                        st.caption(f"{row['Zaman']} | {row['Durum']}")
                        st.success(f"{row['Mesaj']} ₺")
                    with c2: silme_butonu_koy(f"yat_{index}", row['Urun'])
                st.divider()

    # 6. Alarm
    with tab6:
        with st.form("alarm"):
            mesaj = st.text_input("Not", placeholder="Fırın...")
            sure = st.number_input("Dakika", min_value=1, value=15)
            if st.form_submit_button("🔔 Kur", use_container_width=True):
                alarm_kur(mesaj, sure)
                st.success("Kuruldu!")
                time.sleep(1)
                st.rerun()
        
        df_alarm = st.session_state.local_df[st.session_state.local_df["Tip"] == "ALARM"]
        if not df_alarm.empty:
            st.markdown("---")
            simdi = datetime.now()
            for index, row in df_alarm.iterrows():
                try:
                    hedef = datetime.strptime(row["Zaman"], "%Y-%m-%d %H:%M:%S")
                    kalan = (hedef - simdi).total_seconds()
                    c1, c2, c3 = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="center")
                    with c1:
                        st.write(f"**{row['Mesaj']}**")
                        st.caption(hedef.strftime('%H:%M'))
                    with c2:
                        if kalan > 0: st.info(f"⏳ {int(kalan/60)} dk")
                        else: st.error("🔔 DOLDU")
                    with c3: silme_butonu_koy(f"alrm_{index}", row['Urun'])
                    st.divider()
                except: pass

# ==============================================================================
# 2. SAYFA: DOSYA ÇEVİRİCİ (YENİLENMİŞ)
# ==============================================================================
def sayfa_dosya_cevirici():
    st.subheader("📂 Dosya Çevirici Bot (PDF)")
    st.info("💡 Word, Excel, PowerPoint veya Resim dosyalarını buraya yükleyebilirsin.")
    
    # YENİ: Genişletilmiş dosya tipleri
    dosya = st.file_uploader("Dosya Yükle", type=["png", "jpg", "jpeg", "docx", "xlsx", "pptx"])
    
    if dosya:
        st.success(f"✅ {dosya.name} yüklendi!")
        
        if st.button("PDF'e Çevir"):
            # Resim ise çevir (Çünkü kütüphanesi basit)
            if dosya.type in ["image/png", "image/jpeg", "image/jpg"]:
                try:
                    import img2pdf
                    pdf_bytes = img2pdf.convert(dosya.read())
                    st.download_button("⬇️ İndir", pdf_bytes, f"{dosya.name}.pdf", "application/pdf")
                except Exception as e: st.error(f"Hata: {e}")
            
            # Office dosyası ise (docx, xlsx, pptx)
            else:
                st.warning("⚠️ Word/Excel çevirisi için sunucu tarafında Microsoft Office lisansı gereklidir.")
                st.info("Bu özellik şu an 'Demo' modundadır. İleride CloudConvert API ile aktif edilebilir.")

# ==============================================================================
# ANA İSKELET
# ==============================================================================

# 1. En Üst: Hava Durumu (Iframe)
hava_durumu_goster()

# 2. Sol Menü
secim = st.sidebar.radio("Menü", ["🏠 Ev Asistanı", "📂 Dosya Çevirici"])

# 3. Yönlendirme
if secim == "🏠 Ev Asistanı":
    sayfa_ev_asistani()
elif secim == "📂 Dosya Çevirici":
    sayfa_dosya_cevirici()
