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

# --- CSS (Tasarım) ---
st.markdown("""
<style>
    div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 5px !important; }
    div[data-testid="column"] { display: flex; align-items: center; height: 100%; }
    button { padding: 0.25rem 0.5rem !important; }
    .welcome-box {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        color: white; padding: 15px; border-radius: 12px;
        text-align: center; margin-bottom: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.2);
    }
    .welcome-title { font-size: 20px; font-weight: bold; margin-bottom: 5px; }
    .welcome-note { font-size: 14px; opacity: 0.9; }
    .link-box {
        text-decoration: none; color: #333; background: #f0f2f6; padding: 8px;
        border-radius: 5px; display: block; margin-bottom: 5px;
        text-align: center; font-weight: bold; border: 1px solid #ddd;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# KARŞILAMA
# ==============================================================================
def karsilama_paneli():
    saat = datetime.now().hour
    selam = "Günaydın" if 5<=saat<12 else "Tünaydın" if 12<=saat<18 else "İyi Akşamlar" if 18<=saat<22 else "İyi Geceler"
    sozler = [
        "🏡 Evimiz, huzurumuzdur.", "💡 Gereksiz harcamaları 'Kiler'den kontrol et.",
        "🐈 Prenses'e sevgi gösterdiniz mi?", "❤️ Birbirinize zaman ayırmayı unutmayın.",
        "🎬 Bu akşam bir film mi izlesek?", "🛒 Kileri kontrol etmeden markete gitme!"
    ]
    st.markdown(f'<div class="welcome-box"><div class="welcome-title">{selam} Güzel Ailem! 👋</div><div class="welcome-note">{random.choice(sozler)}</div></div>', unsafe_allow_html=True)

# ==============================================================================
# VERİTABANI İŞLEMLERİ
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

def verileri_yukle():
    try:
        data = get_client().open(DOSYA_ADI).sheet1.get_all_values()
        if not data: return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman", "Tip"])
        if "Urun" not in data[0]: return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman", "Tip"])
        df = pd.DataFrame(data[1:], columns=data[0])
        return df.astype(str)
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

def kiler_alisverise_tasi(isim):
    # 1. Kilerden sil
    hizli_sil(isim)
    # 2. Markete ekle
    hizli_ekle(isim, "MARKET")

# ==============================================================================
# CALLBACKLER
# ==============================================================================
def ekleme_callback(key, tip, durum="0"):
    val = st.session_state[key]
    if val:
        if "," in val:
            for p in val.split(","): 
                if p.strip(): hizli_ekle(p.strip(), tip, durum=durum)
        else: hizli_ekle(val, tip, durum=durum)
        st.session_state[key] = ""

def fatura_callback():
    ad, gun, saat, tekrar = st.session_state.fat_ad, st.session_state.fat_gun, st.session_state.fat_saat, st.session_state.fat_tekrar
    if ad:
        kod = "HER_AY" if tekrar == "🔁 Her Ay" else "TEK"
        hizli_ekle(ad, "FATURA", gun, str(saat)[0:5], kod)
        st.session_state.fat_ad = ""

def abonelik_callback():
    ad, tutar = st.session_state.sub_ad, st.session_state.sub_tutar
    if ad:
        hizli_ekle(ad, "ABONELIK", mesaj=str(tutar))
        st.session_state.sub_ad = ""
        st.session_state.sub_tutar = 0.0

def butce_callback():
    ad, tutar, tur = st.session_state.butce_ad, st.session_state.butce_tutar, st.session_state.butce_tur
    if ad:
        hizli_ekle(ad, "BUTCE", mesaj=str(tutar), durum=tur, zaman=datetime.now().strftime("%Y-%m-%d"))
        st.session_state.butce_ad = ""
        st.session_state.butce_tutar = 0

def sayac_callback():
    ad, tarih = st.session_state.sayac_ad, st.session_state.sayac_tarih
    if ad: hizli_ekle(ad, "COUNTDOWN", zaman=str(tarih)); st.session_state.sayac_ad = ""

# ==============================================================================
# GÖRÜNÜM ELEMANLARI
# ==============================================================================
def silme_butonu_koy(prefix, urun):
    if not st.session_state.get(f"conf_{prefix}_{urun}"):
        if st.button("🗑️", key=f"del_{prefix}_{urun}"): 
            st.session_state[f"conf_{prefix}_{urun}"] = True
            st.rerun()
    else:
        if st.button("Sil?", key=f"yes_{prefix}_{urun}", type="primary"):
            hizli_sil(urun)
            st.session_state[f"conf_{prefix}_{urun}"] = False
            st.rerun()
        st.caption("İptal: Yenile")

# ==============================================================================
# MENÜ: ANA SAYFA (MARKET & KİLER)
# ==============================================================================
def sayfa_ana_ekran():
    tab1, tab2, tab3 = st.tabs(["🛒 MARKET", "📝 İŞLER", "🥫 KİLER"])

    # MARKET
    with tab1:
        c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("Market", placeholder="Eksikler...", key="market_giris", label_visibility="collapsed")
        with c2: st.button("EKLE", key="btn_m", on_click=ekleme_callback, args=("market_giris", "MARKET"), use_container_width=True)
        st.markdown("---")
        
        df = st.session_state.local_df
        df_m = df[(df["Tip"] == "MARKET")]
        alinacaklar = df_m[df_m["Durum"] == "0"]
        
        st.subheader(f"📌 Alınacaklar ({len(alinacaklar)})")
        if alinacaklar.empty: st.success("Sepet Boş!")
        for i, row in alinacaklar.iterrows():
            c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
            with c1:
                if st.checkbox(f"**{row['Urun']}**", key=f"m_chk_{i}"):
                    hizli_durum_degistir(row['Urun'], "1"); st.rerun()
            with c2: silme_butonu_koy(f"m_{i}", row['Urun'])
        
        st.divider()
        with st.expander("📦 Alınanlar"):
            for i, row in df_m[df_m["Durum"] == "1"].iterrows():
                c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
                with c1: 
                    if st.button(f"➕ {row['Urun']}", key=f"back_{i}", use_container_width=True): hizli_durum_degistir(row['Urun'], "0"); st.rerun()
                with c2: silme_butonu_koy(f"fm_{i}", row['Urun'])

    # İŞLER
    with tab2:
        c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("Görev", key="is_giris", label_visibility="collapsed")
        with c2: st.button("EKLE", key="btn_t", on_click=ekleme_callback, args=("is_giris", "TODO"), use_container_width=True)
        st.markdown("---")
        df_t = st.session_state.local_df[st.session_state.local_df["Tip"] == "TODO"]
        for i, row in df_t[df_t["Durum"]=="0"].iterrows():
            c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
            with c1: 
                if st.checkbox(f"**{row['Urun']}**", key=f"t_chk_{i}"): hizli_durum_degistir(row['Urun'], "1"); st.rerun()
            with c2: silme_butonu_koy(f"t_{i}", row['Urun'])

    # YENİ: SANAL KİLER
    with tab3:
        st.info("Evdeki stokları buraya yaz. Bitince 'Bitti' de, market listesine geçsin.")
        c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("Stok Ekle", placeholder="Deterjan...", key="kiler_giris", label_visibility="collapsed")
        with c2: st.button("EKLE", key="btn_k", on_click=ekleme_callback, args=("kiler_giris", "KILER"), use_container_width=True)
        st.markdown("---")
        
        df_k = st.session_state.local_df[st.session_state.local_df["Tip"] == "KILER"]
        for i, row in df_k.iterrows():
            c1, c2, c3 = st.columns([0.6, 0.2, 0.2], gap="small", vertical_alignment="center")
            with c1: st.write(f"🥫 **{row['Urun']}**")
            with c2:
                # Bitti Butonu
                if st.button("Bitti 🔄", key=f"move_{i}", type="secondary", use_container_width=True):
                    kiler_alisverise_tasi(row['Urun'])
                    st.toast(f"{row['Urun']} alışveriş listesine taşındı!")
                    time.sleep(1)
                    st.rerun()
            with c3: silme_butonu_koy(f"k_{i}", row['Urun'])
            st.divider()

# ==============================================================================
# MENÜ: EKONOMİ (ABONELİKLER EKLENDİ)
# ==============================================================================
def sayfa_ekonomi():
    tab1, tab2, tab3 = st.tabs(["💳 ABONELİK", "💸 FATURA", "💰 BÜTÇE"])

    # YENİ: ABONELİKLER
    with tab1:
        with st.expander("➕ Yeni Abonelik", expanded=True):
            c1, c2 = st.columns(2)
            with c1: st.text_input("Platform", placeholder="Netflix...", key="sub_ad")
            with c2: st.number_input("Aylık Ücret", min_value=0.0, key="sub_tutar"); st.button("KAYDET", on_click=abonelik_callback)
        
        df_s = st.session_state.local_df[st.session_state.local_df["Tip"] == "ABONELIK"]
        if not df_s.empty:
            toplam = sum(float(r["Mesaj"]) for _, r in df_s.iterrows() if r["Mesaj"].replace('.','',1).isdigit())
            st.metric("🔥 Aylık Sabit Gider", f"{toplam} ₺")
            st.divider()
            for i, row in df_s.iterrows():
                c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
                with c1: st.write(f"**{row['Urun']}**"); st.caption(f"{row['Mesaj']} TL/Ay")
                with c2: silme_butonu_koy(f"sub_{i}", row['Urun'])

    with tab2:
        with st.expander("➕ Fatura Ekle", expanded=True):
            c1, c2 = st.columns(2)
            with c1: st.text_input("Adı", key="fat_ad"); st.number_input("Günü", 1,31,1, key="fat_gun")
            with c2: st.radio("Sıklık", ["🔁 Her Ay", "1️⃣ Tek"], key="fat_tekrar"); st.button("KAYDET", on_click=fatura_callback)
        st.markdown("---")
        df_f = st.session_state.local_df[st.session_state.local_df["Tip"] == "FATURA"]
        df_f["Gun"] = pd.to_numeric(df_f["Zaman"], errors='coerce').fillna(32); df_f = df_f.sort_values("Gun")
        bugun = datetime.now().day
        for i, row in df_f.iterrows():
            try:
                kalan = int(row["Gun"]) - bugun
                c1, c2, c3 = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="center")
                with c1: st.write(f"**{row['Urun']}**"); st.caption(f"Her Ayın {int(row['Gun'])}'i")
                with c2: 
                    if kalan==0: st.error("❗ BUGÜN")
                    elif kalan>0: st.success(f"⏳ {kalan} gün")
                    else: st.warning("Geçti")
                with c3: silme_butonu_koy(f"fat_{i}", row['Urun'])
                st.divider()
            except: pass

    with tab3:
        with st.expander("➕ Gelir/Gider", expanded=True):
            c1, c2 = st.columns(2)
            with c1: st.radio("Tür", ["Gider", "Gelir"], horizontal=True, key="butce_tur"); st.text_input("Açıklama", key="butce_ad")
            with c2: st.number_input("Tutar", key="butce_tutar"); st.button("KAYDET", on_click=butce_callback)
        
        df_b = st.session_state.local_df[st.session_state.local_df["Tip"] == "BUTCE"].copy()
        if not df_b.empty:
            df_b["Tarih"] = pd.to_datetime(df_b["Zaman"], errors='coerce').fillna(datetime.now())
            bu_ay = datetime.now().strftime("%Y-%m")
            df_bu = df_b[df_b["Tarih"].dt.strftime('%Y-%m') == bu_ay]
            gelir = sum(float(r["Mesaj"]) for _, r in df_bu.iterrows() if r["Durum"] == "Gelir")
            gider = sum(float(r["Mesaj"]) for _, r in df_bu.iterrows() if r["Durum"] == "Gider")
            
            if gelir > 0: st.progress(min(gider/gelir, 1.0), f"Harcama: %{int((gider/gelir)*100)}")
            c1, c2, c3 = st.columns(3); c1.metric("Gelir", f"{gelir:.0f}"); c2.metric("Gider", f"{gider:.0f}"); c3.metric("Kalan", f"{gelir-gider:.0f}")
            st.divider()
            for i, row in df_bu.iterrows():
                c1, c2, c3 = st.columns([0.45, 0.35, 0.20], gap="small", vertical_alignment="center")
                with c1: st.write(f"{'🟢' if row['Durum']=='Gelir' else '🔴'} **{row['Urun']}**")
                with c2: st.write(f"{row['Mesaj']} ₺")
                with c3: silme_butonu_koy(f"b_{i}", row['Urun'])

# ==============================================================================
# MENÜ: YAŞAM (SİNEMA RULETİ EKLENDİ)
# ==============================================================================
def sayfa_yasam():
    tab1, tab2, tab3, tab4 = st.tabs(["🍽️ YEMEK", "🎬 SİNEMA", "⏳ SAYAÇ", "📒 NOTLAR"])

    # YEMEK
    with tab1:
        c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("Yemek", key="yemek_giris", label_visibility="collapsed")
        with c2: st.button("EKLE", key="btn_ymk", on_click=ekleme_callback, args=("yemek_giris", "YEMEK"), use_container_width=True)
        st.markdown("---")
        df_y = st.session_state.local_df[st.session_state.local_df["Tip"] == "YEMEK"]
        havuz = df_y[df_y["Durum"] == "1"]["Urun"].tolist()
        if havuz and st.button(f"🎲 SEÇ ({len(havuz)})", type="primary", use_container_width=True):
            st.balloons(); st.success(f"🍽️ Menü: **{random.choice(havuz)}**")
        
        for i, row in df_y.iterrows():
            c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
            with c1:
                chk = (row['Durum'] == "1")
                if st.checkbox(f"**{row['Urun']}**", value=chk, key=f"y_chk_{i}"):
                     if not chk: hizli_durum_degistir(row['Urun'], "1"); st.rerun()
                else:
                     if chk: hizli_durum_degistir(row['Urun'], "0"); st.rerun()
            with c2: silme_butonu_koy(f"ymk_{i}", row['Urun'])

    # YENİ: SİNEMA
    with tab2:
        st.info("İzlemek istediğiniz Film/Dizileri ekleyin, kura çekin!")
        c1, c2 = st.columns([0.75, 0.25], gap="small", vertical_alignment="bottom")
        with c1: st.text_input("Film/Dizi", key="film_giris", label_visibility="collapsed")
        with c2: st.button("EKLE", key="btn_flm", on_click=ekleme_callback, args=("film_giris", "FILM"), use_container_width=True)
        st.markdown("---")
        df_f = st.session_state.local_df[st.session_state.local_df["Tip"] == "FILM"]
        havuz_f = df_f[df_f["Durum"] == "1"]["Urun"].tolist() # Sadece tikli olanlar
        
        if havuz_f and st.button(f"🎬 KURA ÇEK ({len(havuz_f)})", type="primary", use_container_width=True):
            st.balloons(); st.success(f"🍿 İyi Seyirler: **{random.choice(havuz_f)}**")

        for i, row in df_f.iterrows():
            c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
            with c1:
                chk = (row['Durum'] == "1")
                if st.checkbox(f"**{row['Urun']}**", value=chk, key=f"f_chk_{i}"):
                     if not chk: hizli_durum_degistir(row['Urun'], "1"); st.rerun()
                else:
                     if chk: hizli_durum_degistir(row['Urun'], "0"); st.rerun()
            with c2: silme_butonu_koy(f"flm_{i}", row['Urun'])

    with tab3:
        with st.expander("➕ Yeni Sayaç", expanded=True):
            st.text_input("Etkinlik", key="sayac_ad"); st.date_input("Tarih", key="sayac_tarih")
            st.button("KAYDET", on_click=sayac_callback)
        df_s = st.session_state.local_df[st.session_state.local_df["Tip"] == "COUNTDOWN"]
        if not df_s.empty:
            st.markdown("---")
            bugun = datetime.now().date()
            for i, row in df_s.iterrows():
                try:
                    kalan = (datetime.strptime(row["Zaman"], "%Y-%m-%d").date() - bugun).days
                    c1, c2 = st.columns([0.8, 0.2], gap="small", vertical_alignment="center")
                    with c1:
                        st.write(f"🎉 **{row['Urun']}**")
                        if kalan > 0: st.info(f"⏳ **{kalan}** gün kaldı")
                        elif kalan == 0: st.success("🎉 BUGÜN!")
                    with c2: silme_butonu_koy(f"syc_{i}", row['Urun'])
                except: pass

    with tab4:
        with st.expander("➕ Not Ekle", expanded=True):
            st.text_input("Başlık", key="not_baslik"); st.text_area("İçerik", key="not_icerik")
            st.button("KAYDET", on_click=not_callback)
        df_n = st.session_state.local_df[st.session_state.local_df["Tip"] == "NOTE"]
        for i, row in df_n.iterrows():
            with st.expander(f"📒 {row['Urun']}"):
                st.code(row['Mesaj']); silme_butonu_koy(f"nt_{i}", row['Urun'])

# ==============================================================================
# ANA İSKELET
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
elif secim == "📂 Dosya": 
    st.subheader("📂 PDF Çevirici")
    u = st.file_uploader("Resim", type=["png","jpg"]); 
    if u: 
        import img2pdf; st.download_button("İndir", img2pdf.convert(u.read()), f"{u.name}.pdf")
