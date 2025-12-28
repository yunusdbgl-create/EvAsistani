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
# AYARLAR
# ==============================================================================
DOSYA_ADI = "EvAsistaniDB"
NTFY_TOPIC = "yunus_ozel_ev_kanali_123"

st.set_page_config(page_title="Bizim Evin Paneli", page_icon="🏡", layout="centered")

# --- CSS ---
st.markdown("""
<style>
    div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 5px !important; }
    div[data-testid="column"] { display: flex; align-items: center; height: 100%; }
    button { padding: 0.25rem 0.5rem !important; }
    .welcome-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; padding: 15px; border-radius: 15px;
        text-align: center; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .welcome-title { font-size: 22px; font-weight: bold; margin-bottom: 5px; }
    .welcome-note { font-size: 15px; opacity: 0.95; }
    .link-box {
        text-decoration: none; color: #333; background: #f0f2f6; padding: 8px;
        border-radius: 5px; display: block; margin-bottom: 5px;
        text-align: center; font-weight: bold; border: 1px solid #ddd;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# AI MUTFAK ŞEFİ MOTORU (GELİŞMİŞ)
# ==============================================================================
def mutfak_sefi_motoru(marketten_gelenler, manuel_eklenenler):
    # Verileri birleştir ve küçük harfe çevir (Eşleşme kolay olsun diye)
    tum_malzemeler = set()
    
    # Marketten gelenleri temizle (Örn: "Yumurta (10lu)" -> "yumurta")
    for urun in marketten_gelenler:
        temiz_ad = urun.lower().split("(")[0].strip()
        tum_malzemeler.add(temiz_ad)
        
    for urun in manuel_eklenenler:
        tum_malzemeler.add(urun.lower())

    # Tarif Veritabanı (Hepsi küçük harf olmalı)
    tarifler = {
        "Menemen": ["yumurta", "domates", "biber"],
        "Omlet": ["yumurta", "peynir", "tereyağı"],
        "Mercimek Çorbası": ["mercimek", "soğan", "salça", "yağ"],
        "Karnıyarık": ["patlıcan", "kıyma", "domates", "soğan"],
        "Köfte Patates": ["kıyma", "patates", "soğan", "ekmek"],
        "Makarna": ["makarna", "salça", "yağ"],
        "Tavuk Sote": ["tavuk", "biber", "domates", "soğan"],
        "Kısır": ["bulgur", "salça", "yeşillik", "limon"],
        "Cacık": ["yoğurt", "salatalık", "sarımsak"],
        "Pilav": ["pirinç", "tereyağı", "şehriye"],
        "Patates Kızartması": ["patates", "yağ"],
        "Çoban Salata": ["domates", "salatalık", "biber", "soğan"],
        "Mantarlı Tavuk": ["tavuk", "mantar", "krema"],
        "Hamburger": ["kıyma", "ekmek", "domates", "yeşillik"]
    }
    
    tam_liste = []
    eksik_liste = []
    
    for yemek, malzemeler in tarifler.items():
        # Eşleşme Kontrolü (İçeriyor mu?)
        eksikler = []
        for m in malzemeler:
            # Malzeme adının herhangi bir parçası envanterde var mı?
            # Örn: Envanterde "Domatesli sos" varsa, "domates" ihtiyacını karşılamaz ama tersi olur.
            # Basit eşleşme:
            if m not in tum_malzemeler:
                eksikler.append(m)
        
        if len(eksikler) == 0:
            tam_liste.append(yemek)
        elif len(eksikler) <= 2:
            eksik_liste.append((yemek, eksikler))
            
    return tam_liste, eksik_liste, list(tum_malzemeler)

# ==============================================================================
# KARŞILAMA
# ==============================================================================
def karsilama_paneli():
    saat = datetime.now().hour
    selam = "Günaydın" if 5<=saat<12 else "Tünaydın" if 12<=saat<18 else "İyi Akşamlar" if 18<=saat<22 else "İyi Geceler"
    sozler = [
        "🏡 Evimiz, huzurumuzdur.", "💡 Bütçeni kontrol et, rahat et.",
        "🐈 Prenses'i sevdiniz mi?", "❤️ Birbirinize zaman ayırın.",
        "🛒 Alışveriş listesine baktın mı?", "👨‍🍳 Şef, market listeni biliyor!"
    ]
    st.markdown(f'<div class="welcome-box"><div class="welcome-title">{selam}! ☀️</div><div class="welcome-note">{random.choice(sozler)}</div></div>', unsafe_allow_html=True)

# ==============================================================================
# VERİTABANI
# ==============================================================================
def get_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["connections"]["gsheets"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
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

def arka_planda_guncelle(urun, durum):
    try:
        sheet = get_client().open(DOSYA_ADI).sheet1
        try: sheet.update_cell(sheet.find(urun).row, 2, str(durum))
        except:
            for i, row in enumerate(sheet.get_all_values()):
                if row[0] == urun: sheet.update_cell(i+1, 2, str(durum)); break
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

def verileri_yukle():
    try:
        data = get_client().open(DOSYA_ADI).sheet1.get_all_values()
        if not data: return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman", "Tip"])
        if "Urun" not in data[0]: return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman", "Tip"])
        return pd.DataFrame(data[1:], columns=data[0]).astype(str)
    except: return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman", "Tip"])

if 'local_df' not in st.session_state: st.session_state.local_df = verileri_yukle()

# ==============================================================================
# HIZLI İŞLEMLER
# ==============================================================================
def hizli_ekle(isim, tip, zaman="", mesaj="", durum="0"):
    row = {"Urun": isim, "Durum": durum, "Mesaj": mesaj, "Zaman": str(zaman), "Tip": tip}
    st.session_state.local_df = pd.concat([st.session_state.local_df, pd.DataFrame([row])], ignore_index=True)
    threading.Thread(target=arka_planda_ekle, args=([isim, durum, mesaj, str(zaman), tip],)).start()

def hizli_sil(isim):
    st.session_state.local_df = st.session_state.local_df[st.session_state.local_df["Urun"] != isim]
    threading.Thread(target=arka_planda_sil, args=(isim,)).start()

def hizli_durum_degistir(isim, yeni_durum):
    idx = st.session_state.local_df[st.session_state.local_df["Urun"] == isim].index
    if not idx.empty: st.session_state.local_df.at[idx[0], "Durum"] = str(yeni_durum)
    threading.Thread(target=arka_planda_guncelle, args=(isim, yeni_durum)).start()

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
        threading.Thread(target=arka_planda_guncelle_yatirim, args=(isim, miktar, notlar, "YATIRIM")).start()

# CALLBACKLER
def ekleme_callback(key, tip):
    val = st.session_state[key]
    if val:
        if "," in val:
            for p in val.split(","): 
                if p.strip(): hizli_ekle(p.strip(), tip)
        else: hizli_ekle(val, tip)
        st.session_state[key] = ""

def not_callback():
    baslik, icerik = st.session_state.not_baslik, st.session_state.not_icerik
    if baslik and icerik:
        hizli_ekle(baslik, "NOTE", mesaj=icerik, durum=datetime.now().strftime("%d-%m-%Y"))
        st.session_state.not_baslik = ""; st.session_state.not_icerik = ""

def sayac_callback():
    ad, tarih = st.session_state.sayac_ad, st.session_state.sayac_tarih
    if ad: hizli_ekle(ad, "COUNTDOWN", zaman=str(tarih)); st.session_state.sayac_ad = ""

def fatura_callback():
    ad, gun, saat, tekrar = st.session_state.fat_ad, st.session_state.fat_gun, st.session_state.fat_saat, st.session_state.fat_tekrar
    if ad:
        kod = "HER_AY" if tekrar == "🔁 Her Ay" else "TEK"
        hizli_ekle(ad, "FATURA", gun, str(saat)[0:5], kod)
        st.session_state.fat_ad = ""

def butce_callback():
    ad, tutar, tur = st.session_state.butce_ad, st.session_state.butce_tutar, st.session_state.butce_tur
    if ad and tutar > 0:
        hizli_ekle(ad, "BUTCE", mesaj=str(tutar), durum=tur, zaman=datetime.now().strftime("%Y-%m-%d"))
        st.session_state.butce_ad = ""; st.session_state.butce_tutar = 0

def yatirim_callback():
    ad, miktar, notlar = st.session_state.yat_ad, st.session_state.yat_mik, st.session_state.yat_not
    if ad:
        hizli_yatirim_guncelle(ad, miktar, notlar)
        st.session_state.yat_ad = ""; st.session_state.yat_not = ""

def alarm_kur(mesaj, sure):
    hedef = datetime.now() + timedelta(minutes=sure)
    hizli_ekle(f"{mesaj} ({hedef.strftime('%H:%M')})", "ALARM", hedef.strftime("%Y-%m-%d %H:%M:%S"), mesaj, "-1")
    try: requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=f"✅ Alarm: {sure} dk sonra '{mesaj}'".encode('utf-8'), headers={"Title": "Ev Asistanı".encode('utf-8'), "Priority": "high"})
    except: pass

def silme_butonu_koy(prefix, urun):
    if not st.session_state.get(f"conf_{prefix}_{urun}"):
        if st.button("🗑️", key=f"del_{prefix}_{urun}"): st.session_state[f"conf_{prefix}_{urun}"] = True; st.rerun()
    else:
        if st.button("Sil?", key=f"yes_{prefix}_{urun}", type="primary"):
            hizli_sil(urun)
            st.session_state[f"conf_{prefix}_{urun}"] = False; st.rerun()
        st.caption("İptal: Yenile")

# ==============================================================================
# SAYFALAR
# ==============================================================================
def sayfa_ana_ekran():
    tab1, tab2, tab3 = st.tabs(["🛒 MARKET", "📝 İŞLER", "⏰ ALARM"])
    with tab1:
        c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("Market", key="market_giris", label_visibility="collapsed")
        with c2: st.button("EKLE", key="btn_m", on_click=ekleme_callback, args=("market_giris", "MARKET"), use_container_width=True)
        st.markdown("---")
        df = st.session_state.local_df
        alinacaklar = df[(df["Tip"] == "MARKET") & (df["Durum"] == "0")]
        tamamlananlar = df[(df["Tip"] == "MARKET") & (df["Durum"] == "1")]
        if alinacaklar.empty: st.success("Sepet Boş!")
        for i, row in alinacaklar.iterrows():
            c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
            with c1:
                if st.checkbox(f"**{row['Urun']}**", key=f"chk_m_{i}"): hizli_durum_degistir(row['Urun'], "1"); st.rerun()
            with c2: silme_butonu_koy(f"m_{i}", row['Urun'])
        st.divider()
        with st.expander("📦 Geçmiş (Şef Burayı Okur)"):
            for i, row in tamamlananlar.iterrows():
                c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
                with c1:
                    if st.button(f"➕ {row['Urun']}", key=f"back_m_{i}", use_container_width=True): hizli_durum_degistir(row['Urun'], "0"); st.rerun()
                with c2: silme_butonu_koy(f"fin_m_{i}", row['Urun'])

    with tab2:
        c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("Görev", key="is_giris", label_visibility="collapsed")
        with c2: st.button("EKLE", key="btn_t", on_click=ekleme_callback, args=("is_giris", "TODO"), use_container_width=True)
        st.markdown("---")
        df_t = st.session_state.local_df[st.session_state.local_df["Tip"] == "TODO"]
        for i, row in df_t[df_t["Durum"] == "0"].iterrows():
            c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
            with c1:
                if st.checkbox(f"**{row['Urun']}**", key=f"chk_t_{i}"): hizli_durum_degistir(row['Urun'], "1"); st.rerun()
            with c2: silme_butonu_koy(f"t_{i}", row['Urun'])

    with tab3:
        with st.form("alarm"):
            mesaj = st.text_input("Not", placeholder="Fırın...")
            sure = st.number_input("Dakika", min_value=1, value=15)
            if st.form_submit_button("🔔 Kur", use_container_width=True): alarm_kur(mesaj, sure); st.success("Kuruldu!"); time.sleep(1); st.rerun()
        df_a = st.session_state.local_df[st.session_state.local_df["Tip"] == "ALARM"]
        if not df_a.empty:
            st.markdown("---"); simdi = datetime.now()
            for i, row in df_a.iterrows():
                try:
                    hedef = datetime.strptime(row["Zaman"], "%Y-%m-%d %H:%M:%S"); kalan = (hedef - simdi).total_seconds()
                    c1, c2, c3 = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="center")
                    with c1: st.write(f"**{row['Mesaj']}**"); st.caption(hedef.strftime('%H:%M'))
                    with c2: st.info(f"⏳ {int(kalan/60)} dk") if kalan > 0 else st.error("🔔")
                    with c3: silme_butonu_koy(f"al_{i}", row['Urun'])
                    st.divider()
                except: pass

def sayfa_ekonomi():
    tab1, tab2, tab3 = st.tabs(["💸 ÖDEME", "💰 BÜTÇE", "📈 YATIRIM"])
    with tab1:
        with st.expander("➕ Yeni Ödeme", expanded=True):
            c1, c2 = st.columns(2)
            with c1: st.text_input("Adı", key="fat_ad"); st.number_input("Günü", 1, 31, 1, key="fat_gun")
            with c2: st.time_input("Saat", dt_time(9,0), key="fat_saat"); st.radio("Sıklık", ["🔁 Her Ay", "1️⃣ Tek"], key="fat_tekrar")
            st.button("KAYDET", key="btn_fat_save", on_click=fatura_callback, use_container_width=True)
        st.markdown("---")
        df_f = st.session_state.local_df[st.session_state.local_df["Tip"] == "FATURA"]
        if not df_f.empty:
            bugun = datetime.now().day
            df_f["Gun_Sayi"] = pd.to_numeric(df_f["Zaman"], errors='coerce').fillna(32); df_f = df_f.sort_values("Gun_Sayi")
            for i, row in df_f.iterrows():
                try:
                    gun = int(row["Gun_Sayi"]); kalan = gun - bugun
                    c1, c2, c3 = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="center")
                    with c1: st.write(f"**{row['Urun']}**"); st.caption(f"{row.get('Mesaj','09:00')} | {row['Durum']}")
                    with c2: st.error("❗ BUGÜN") if kalan==0 else st.success(f"⏳ {kalan} gün") if kalan>0 else st.warning("Geçti")
                    with c3: silme_butonu_koy(f"fat_{i}", row['Urun'])
                    st.divider()
                except: pass

    with tab2:
        with st.expander("➕ Gelir/Gider", expanded=True):
            c1, c2 = st.columns(2)
            with c1: st.radio("Tür", ["Gider", "Gelir"], horizontal=True, key="butce_tur"); st.text_input("Açıklama", key="butce_ad")
            with c2: st.number_input("Tutar", key="butce_tutar"); st.write(""); st.button("KAYDET", key="btn_butce_save", on_click=butce_callback, use_container_width=True)
        st.markdown("---")
        df_b = st.session_state.local_df[st.session_state.local_df["Tip"] == "BUTCE"].copy()
        if not df_b.empty:
            df_b["Tarih"] = pd.to_datetime(df_b["Zaman"], errors='coerce').fillna(datetime.now())
            bu_ay = datetime.now().strftime("%Y-%m"); df_bu_ay = df_b[df_b["Tarih"].dt.strftime('%Y-%m') == bu_ay]
            gelir = sum(float(r["Mesaj"]) for _, r in df_bu_ay.iterrows() if r["Durum"] == "Gelir")
            gider = sum(float(r["Mesaj"]) for _, r in df_bu_ay.iterrows() if r["Durum"] == "Gider")
            if gelir > 0: st.progress(min(gider / gelir, 1.0), f"Harcama: %{int((gider/gelir)*100)}")
            c1, c2, c3 = st.columns(3); c1.metric("Gelir", f"{gelir:.0f}₺"); c2.metric("Gider", f"{gider:.0f}₺"); c3.metric("Kalan", f"{gelir-gider:.0f}₺")
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
            with c2: st.text_area("Not", height=100, key="yat_not"); st.button("KAYDET", key="btn_yat_save", on_click=yatirim_callback, use_container_width=True)
        df_y = st.session_state.local_df[st.session_state.local_df["Tip"] == "YATIRIM"]
        if not df_y.empty:
            toplam = sum(float(r["Mesaj"]) for _, r in df_y.iterrows() if r["Mesaj"].replace('.','',1).isdigit())
            st.markdown("---"); st.metric("💰 TOPLAM VARLIK", f"{toplam:,.0f} ₺"); st.divider()
            for i, row in df_y.iterrows():
                c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="center")
                with c1: st.subheader(f"💎 {row['Urun']}"); st.caption(f"{row['Mesaj']} ₺ | {row['Durum']}")
                with c2: silme_butonu_koy(f"y_{i}", row['Urun'])

def sayfa_yasam():
    tab1, tab2, tab3 = st.tabs(["👨‍🍳 ŞEF", "⏳ SAYAÇ", "📒 NOTLAR"])
    
    with tab1:
        st.subheader("👨‍🍳 AI Mutfak Şefi")
        st.info("Market geçmişine bakar, ek malzemelerle tarif önerir.")
        
        # 1. Market Geçmişini Al
        df = st.session_state.local_df
        marketten_gelenler = df[(df["Tip"] == "MARKET") & (df["Durum"] == "1")]["Urun"].tolist()
        
        # 2. Ekstra Malzeme Seçimi
        malzemeler = ["Yumurta", "Domates", "Biber", "Soğan", "Kıyma", "Patates", "Tavuk", "Makarna", "Salça", "Pirinç", "Mercimek", "Yoğurt", "Salatalık", "Patlıcan", "Mantar"]
        ek_malzemeler = st.multiselect("Evde başka ne var?", malzemeler)
        
        if st.button("🔍 Ne Pişirsem?", type="primary", use_container_width=True):
            tam, eksik, stok_listesi = mutfak_sefi_motoru(marketten_gelenler, ek_malzemeler)
            
            with st.expander("📦 Algılanan Stoklar"):
                st.write(", ".join(stok_listesi))
            
            if tam:
                st.success(f"✅ **Hemen Yapabilirsin:** {', '.join(tam)}")
            
            if eksik:
                st.markdown("---"); st.warning("🛒 **Ufak Eksikler Var:**")
                for yemek, eksikler in eksik: st.write(f"• **{yemek}** için eksik: *{', '.join(eksikler)}*")
                
            if not tam and not eksik: st.error("Bu malzemelerle bir tarif bulamadım. Biraz daha malzeme ekle!")

    with tab2:
        with st.expander("➕ Yeni Sayaç", expanded=True):
            st.text_input("Etkinlik", key="sayac_ad"); st.date_input("Tarih", key="sayac_tarih")
            st.button("KAYDET", key="btn_syc_save", on_click=sayac_callback)
        df_s = st.session_state.local_df[st.session_state.local_df["Tip"] == "COUNTDOWN"]
        if not df_s.empty:
            st.markdown("---"); bugun = datetime.now().date()
            for i, row in df_s.iterrows():
                try:
                    hedef = datetime.strptime(row["Zaman"], "%Y-%m-%d").date(); kalan = (hedef - bugun).days
                    c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
                    with c1: st.write(f"🎉 **{row['Urun']}**"); st.info(f"⏳ **{kalan}** gün kaldı") if kalan > 0 else st.success("🎉 BUGÜN!")
                    with c2: silme_butonu_koy(f"syc_{i}", row['Urun'])
                    st.divider()
                except: pass

    with tab3:
        with st.expander("➕ Not Ekle", expanded=True):
            st.text_input("Başlık", key="not_baslik"); st.text_area("İçerik", key="not_icerik"); st.button("KAYDET", key="btn_not_save", on_click=not_callback)
        df_n = st.session_state.local_df[st.session_state.local_df["Tip"] == "NOTE"]
        for i, row in df_n.iterrows():
            with st.expander(f"📒 {row['Urun']}"): st.code(row['Mesaj']); silme_butonu_koy(f"nt_{i}", row['Urun'])

def sayfa_dosya():
    st.subheader("📂 PDF Çevirici")
    dosya = st.file_uploader("Resim Yükle", type=["png", "jpg", "jpeg"])
    if dosya:
        import img2pdf; st.download_button("⬇️ İndir", img2pdf.convert(dosya.read()), f"{dosya.name}.pdf", "application/pdf")

# ==============================================================================
# ÇALIŞTIRMA
# ==============================================================================
karsilama_paneli()
with st.sidebar:
    st.header("Menü")
    secim = st.radio("Git:", ["🏠 Ana Sayfa", "💰 Ekonomi", "🧬 Yaşam", "📂 Dosya"])
    st.markdown("---"); st.header("Linkler")
    st.markdown('<a href="https://www.turkiye.gov.tr/" target="_blank" class="link-box">🏛️ E-Devlet</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://www.enabiz.gov.tr/" target="_blank" class="link-box">🏥 E-Nabız</a>', unsafe_allow_html=True)

if secim == "🏠 Ana Sayfa": sayfa_ana_ekran()
elif secim == "💰 Ekonomi": sayfa_ekonomi()
elif secim == "🧬 Yaşam": sayfa_yasam()
elif secim == "📂 Dosya": sayfa_dosya()
