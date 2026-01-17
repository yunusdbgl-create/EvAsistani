import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta, time as dt_time
import random
import threading

# ==============================================================================
# ⚙️ AYARLAR VE YAPILANDIRMA
# ==============================================================================
st.set_page_config(
    page_title="Ev Asistanı Pro",
    page_icon="🏡",
    layout="centered",
    initial_sidebar_state="collapsed"
)

DOSYA_ADI = "EvAsistaniDB"
NTFY_TOPIC = "yunus_ozel_ev_kanali_123"

# Kütüphane Kontrolleri
try:
    import plotly.express as px
    GRAFIK_VAR = True
except ImportError:
    GRAFIK_VAR = False

try:
    import img2pdf
    PDF_VAR = True
except ImportError:
    PDF_VAR = False

# ==============================================================================
# 🎨 MODERN UI STİLLERİ (CSS)
# ==============================================================================
st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    div.css-1r6slb0, div.stExpander {
        background: white; border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 10px; border: 1px solid #e9ecef;
    }
    button[kind="primary"] {
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
        border: none; transition: all 0.3s ease;
    }
    button[kind="primary"]:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); }
    .welcome-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; padding: 20px; border-radius: 20px; text-align: center; margin-bottom: 25px;
        box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
    }
    .prenses-box {
        background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 99%, #fecfef 100%);
        color: #5e2d48; padding: 20px; border-radius: 20px; text-align: center; margin-bottom: 25px;
        border: 2px solid white; box-shadow: 0 10px 20px rgba(255, 154, 158, 0.3);
    }
    .welcome-title { font-size: 24px; font-weight: 800; margin-bottom: 8px; }
    .welcome-note { font-size: 16px; font-style: italic; opacity: 0.9; }
    .category-line { height: 4px; border-radius: 2px; margin-bottom: 12px; }
    div[data-testid="column"] { gap: 10px; }
    .metric-card {
        background-color: white; padding: 15px; border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); text-align: center; border: 1px solid #eee;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 🔌 VERİTABANI BAĞLANTISI
# ==============================================================================
@st.cache_resource
def get_gspread_client():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(dict(st.secrets["connections"]["gsheets"]), scopes=scopes)
        return gspread.authorize(creds), True
    except Exception as e:
        return None, False

gc, ONLINE_MOD = get_gspread_client()

def veri_senkronize_et(df, islem_tipi, veri=None):
    if not ONLINE_MOD: return
    def thread_gorevi():
        try:
            sheet = gc.open(DOSYA_ADI).sheet1
            if islem_tipi == "ekle": sheet.append_row(veri)
            elif islem_tipi == "sil":
                try:
                    cell = sheet.find(veri)
                    sheet.delete_rows(cell.row)
                except: pass
            elif islem_tipi == "guncelle":
                try:
                    cell = sheet.find(veri[0])
                    sheet.update_cell(cell.row, 2, str(veri[1]))
                except: pass
        except Exception as e: print(f"Sync Hatası: {e}")
    threading.Thread(target=thread_gorevi).start()

def verileri_yukle():
    cols = ["Urun", "Durum", "Mesaj", "Zaman", "Tip"]
    if ONLINE_MOD:
        try:
            data = gc.open(DOSYA_ADI).sheet1.get_all_values()
            if len(data) > 1:
                df = pd.DataFrame(data[1:], columns=data[0]).astype(str)
                for col in cols: 
                    if col not in df.columns: df[col] = ""
                return df
        except: pass
    return pd.DataFrame(columns=cols)

if 'local_df' not in st.session_state:
    st.session_state.local_df = verileri_yukle()
    if not ONLINE_MOD: st.warning("⚠️ Offline Mod: Değişiklikler kaydedilmeyecek.")

# ==============================================================================
# 🧠 YARDIMCI FONKSİYONLAR & AI MOTORU
# ==============================================================================
def get_kategori_renk(kategori):
    renkler = {"Meyve": "#2ecc71", "Sebze": "#27ae60", "Et": "#e74c3c", "Süt": "#3498db", "Temizlik": "#9b59b6", "Gıda": "#e67e22"}
    for key, color in renkler.items():
        if key in kategori: return color
    return "#34495e"

def mutfak_sefi_motoru(marketten_gelenler, manuel_eklenenler):
    tum_malzemeler = set()
    for urun in marketten_gelenler: tum_malzemeler.add(urun.lower().split("(")[0].strip())
    for urun in manuel_eklenenler: tum_malzemeler.add(urun.lower())

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
    }
    
    tam, eksik = [], []
    for yemek, malzemeler in tarifler.items():
        eksikler = [m for m in malzemeler if m not in tum_malzemeler]
        if len(eksikler) == 0: tam.append(yemek)
        elif len(eksikler) <= 2: eksik.append((yemek, eksikler))
    return tam, eksik

# ==============================================================================
# ⚡ İŞLEM YÖNETİCİSİ
# ==============================================================================
def islem_yap(aksiyon, **kwargs):
    df = st.session_state.local_df
    
    if aksiyon == "ekle":
        yeni = {"Urun": kwargs.get("urun"), "Durum": kwargs.get("durum", "0"), 
                "Mesaj": kwargs.get("mesaj", ""), "Zaman": kwargs.get("zaman", ""), 
                "Tip": kwargs.get("tip")}
        
        if kwargs.get("tip") in ["MARKET", "TODO"]:
             if not df[(df["Tip"] == kwargs.get("tip")) & (df["Urun"] == kwargs.get("urun"))].empty:
                 st.toast("⚠️ Zaten listede var!"); return

        st.session_state.local_df = pd.concat([df, pd.DataFrame([yeni])], ignore_index=True)
        veri_senkronize_et(None, "ekle", list(yeni.values()))
        st.toast(f"✅ Eklendi: {kwargs.get('urun')}")

    elif aksiyon == "sil":
        urun = kwargs.get("urun")
        st.session_state.local_df = df[df["Urun"] != urun]
        veri_senkronize_et(None, "sil", urun)
        st.toast("🗑️ Silindi!")

    elif aksiyon == "guncelle":
        urun = kwargs.get("urun")
        yeni_durum = kwargs.get("yeni_durum")
        idx = df[df["Urun"] == urun].index
        if not idx.empty:
            st.session_state.local_df.at[idx[0], "Durum"] = str(yeni_durum)
            veri_senkronize_et(None, "guncelle", (urun, yeni_durum))
            if yeni_durum == "1": st.toast("👍 Tamamlandı!")

def oge_satiri(idx, row, sil_fn, durum_fn):
    c1, c2 = st.columns([0.85, 0.15], vertical_alignment="center")
    with c1:
        chk = row['Durum'] == "1"
        if st.checkbox(f"**{row['Urun']}**", value=chk, key=f"c_{row['Tip']}_{idx}"):
            if not chk: durum_fn(row['Urun'], "1"); st.rerun()
        else:
            if chk: durum_fn(row['Urun'], "0"); st.rerun()
    with c2:
        if st.button("🗑️", key=f"d_{row['Tip']}_{idx}"): sil_fn(row['Urun']); st.rerun()

# ==============================================================================
# 📱 SAYFALAR
# ==============================================================================
def dashboard_goster():
    df = st.session_state.local_df
    # Fatura Kontrolü
    df_f = df[df["Tip"] == "FATURA"]
    fatura_txt, kalan_txt = "Fatura Yok", ""
    if not df_f.empty:
        bugun = datetime.now().day
        df_f["Gun"] = pd.to_numeric(df_f["Zaman"], errors='coerce').fillna(32)
        df_f = df_f.sort_values("Gun")
        for _, row in df_f.iterrows():
            kalan = int(row["Gun"]) - bugun
            if kalan >= 0:
                fatura_txt = row["Urun"]
                kalan_txt = "Bugün" if kalan == 0 else f"{kalan} gün"
                break
    
    sepet = len(df[(df["Tip"] == "MARKET") & (df["Durum"] == "0")])
    c1, c2 = st.columns(2)
    with c1: st.markdown(f"<div class='metric-card'>🧾 <b>{fatura_txt}</b><br><small>{kalan_txt}</small></div>", unsafe_allow_html=True)
    with c2: st.markdown(f"<div class='metric-card'>🛒 <b>Sepet</b><br><small>{sepet} Ürün</small></div>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

def sayfa_ana_ekran():
    karsilama_paneli()
    dashboard_goster()
    
    tab1, tab2, tab3 = st.tabs(["🛒 MARKET", "📝 GÖREVLER", "🔔 ALARM"])
    with tab1:
        c1, c2 = st.columns([0.7, 0.3])
        with c1: urun = st.text_input("Hızlı Ekle", key="m_in", label_visibility="collapsed", placeholder="Süt, Ekmek...")
        with c2: 
            if st.button("EKLE", key="m_btn", use_container_width=True) and urun:
                islem_yap("ekle", urun=urun, tip="MARKET", mesaj="Genel"); st.rerun()

        df = st.session_state.local_df
        alinacaklar = df[(df["Tip"] == "MARKET") & (df["Durum"] == "0")]
        
        if alinacaklar.empty: st.info("Sepet boş! 🎉")
        else:
            cats = sorted(list(set(alinacaklar["Mesaj"].unique())))
            for cat in cats:
                items = alinacaklar[alinacaklar["Mesaj"] == cat]
                renk = get_kategori_renk(cat)
                with st.expander(f"{cat if cat else 'Genel'} ({len(items)})", expanded=True):
                    st.markdown(f"<div class='category-line' style='background-color:{renk};'></div>", unsafe_allow_html=True)
                    for i, row in items.iterrows():
                        oge_satiri(i, row, lambda u: islem_yap("sil", urun=u), lambda u, d: islem_yap("guncelle", urun=u, yeni_durum=d))

    with tab2: # GÖREVLER
        c1, c2 = st.columns([0.7, 0.3])
        with c1: is_adi = st.text_input("Görev", key="t_in", label_visibility="collapsed", placeholder="Tamirat...")
        with c2:
             if st.button("EKLE", key="t_btn", use_container_width=True) and is_adi:
                islem_yap("ekle", urun=is_adi, tip="TODO", mesaj="Genel"); st.rerun()
        
        todos = st.session_state.local_df[(st.session_state.local_df["Tip"] == "TODO") & (st.session_state.local_df["Durum"] == "0")]
        if todos.empty: st.success("İşler bitti! 🏖️")
        else:
            for i, row in todos.iterrows():
                st.markdown("---")
                oge_satiri(i+1000, row, lambda u: islem_yap("sil", urun=u), lambda u, d: islem_yap("guncelle", urun=u, yeni_durum=d))

    with tab3: # ALARM
        with st.form("al_form"):
            c1, c2 = st.columns([3, 1])
            msg = c1.text_input("Alarm Adı")
            dk = c2.number_input("Dk", 1, 60, 15)
            if st.form_submit_button("Kur", use_container_width=True):
                hedef = datetime.now() + timedelta(minutes=dk)
                islem_yap("ekle", urun=f"{msg} ({hedef.strftime('%H:%M')})", tip="ALARM", zaman=hedef.strftime("%Y-%m-%d %H:%M:%S"), mesaj=msg, durum="-1")
                try: 
                    import requests
                    requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=f"Alarm: {msg}".encode("utf-8"))
                except: pass
                st.rerun()
        
        alarms = st.session_state.local_df[st.session_state.local_df["Tip"] == "ALARM"]
        for i, row in alarms.iterrows():
            try:
                kalan = (datetime.strptime(row["Zaman"], "%Y-%m-%d %H:%M:%S") - datetime.now()).total_seconds()
                c1, c2 = st.columns([0.8, 0.2])
                with c1: st.write(f"⏰ **{row['Mesaj']}**"); st.caption("Süre doldu!" if kalan < 0 else f"Kalan: {int(kalan/60)} dk")
                with c2: 
                    if st.button("Sil", key=f"ad_{i}"): islem_yap("sil", urun=row["Urun"]); st.rerun()
                st.divider()
            except: pass

def sayfa_yemek():
    st.subheader("🍽️ Mutfak & Yemek")
    tab1, tab2, tab3 = st.tabs(["🔥 EŞLEŞME", "👨‍🍳 ŞEF", "LİSTE"])
    
    with tab1: # OYUN MODU
        st.caption("Tinder usulü yemek seçimi! Kararsız kaldığınızda kullanın.")
        yemekler = st.session_state.local_df[st.session_state.local_df["Tip"] == "YEMEK_OGUN"]["Urun"].tolist()
        
        if not yemekler: st.warning("Listede yemek yok, 'Liste' sekmesinden ekleyin.")
        else:
            if 'oyun_yemegi' not in st.session_state: st.session_state.oyun_yemegi = random.choice(yemekler)
            
            st.markdown(f"<div style='text-align:center; padding:20px; background:#fff; border-radius:15px; box-shadow:0 4px 10px rgba(0,0,0,0.1); margin:20px 0;'><h2>🍽️ {st.session_state.oyun_yemegi} 🍽️</h2></div>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            if c1.button("👎 Olmaz", use_container_width=True):
                st.session_state.oyun_yemegi = random.choice(yemekler); st.rerun()
            if c2.button("👍 Olur!", type="primary", use_container_width=True):
                st.balloons(); st.success(f"Akşama {st.session_state.oyun_yemegi} var! Afiyet olsun.")

    with tab2: # AI ŞEF
        st.info("Evdeki malzemeleri seç, sana yemek önereyim.")
        market_stok = st.session_state.local_df[(st.session_state.local_df["Tip"] == "MARKET") & (st.session_state.local_df["Durum"] == "1")]["Urun"].tolist()
        ek_malzeme = st.multiselect("Ek Malzemeler", ["Yumurta", "Patates", "Kıyma", "Tavuk", "Makarna", "Domates", "Peynir", "Soğan", "Salça"])
        
        if st.button("🔍 Tarif Bul", type="primary", use_container_width=True):
            tam, eksik = mutfak_sefi_motoru(market_stok, ek_malzeme)
            if tam: st.success(f"✅ **Yapabilirsin:** {', '.join(tam)}")
            elif eksik: 
                for y, e in eksik: st.warning(f"🟠 **{y}** için eksik: {', '.join(e)}")
            else: st.error("Bu malzemelerle tarif bulamadım.")

    with tab3: # YEMEK LİSTESİ YÖNETİMİ
        c1, c2 = st.columns([0.7, 0.3])
        with c1: y_ad = st.text_input("Yemek Ekle", key="y_in", label_visibility="collapsed")
        with c2: 
            if st.button("EKLE", key="y_btn", use_container_width=True) and y_ad:
                islem_yap("ekle", urun=y_ad, tip="YEMEK_OGUN", durum="1"); st.rerun()
        
        y_df = st.session_state.local_df[st.session_state.local_df["Tip"] == "YEMEK_OGUN"]
        for i, row in y_df.iterrows():
            c1, c2 = st.columns([0.8, 0.2])
            with c1: st.write(f"🥘 {row['Urun']}")
            with c2: 
                if st.button("🗑️", key=f"yd_{i}"): islem_yap("sil", urun=row['Urun']); st.rerun()

def sayfa_yasam(): # YENİDEN EKLENDİ
    st.subheader("🧬 Yaşam Takibi")
    tab1, tab2, tab3 = st.tabs(["⛓️ RUTİN", "⏳ SAYAÇ", "📒 NOTLAR"])
    
    with tab1: # RUTİN / ZİNCİR
        c1, c2 = st.columns([0.7, 0.3])
        with c1: r_ad = st.text_input("Rutin Ekle", key="r_in", placeholder="Su iç, Kitap oku...")
        with c2: 
            if st.button("EKLE", key="r_btn", use_container_width=True) and r_ad:
                islem_yap("ekle", urun=r_ad, tip="RUTIN", durum="0"); st.rerun()
        
        rutinler = st.session_state.local_df[st.session_state.local_df["Tip"] == "RUTIN"]
        if not rutinler.empty:
            tamamlanan = len(rutinler[rutinler["Durum"]=="1"])
            st.progress(tamamlanan/len(rutinler), text=f"Günlük İlerleme: %{int(tamamlanan/len(rutinler)*100)}")
            st.markdown("---")
            for i, row in rutinler.iterrows():
                oge_satiri(i+2000, row, lambda u: islem_yap("sil", urun=u), lambda u, d: islem_yap("guncelle", urun=u, yeni_durum=d))
    
    with tab2: # SAYAÇ
        with st.expander("➕ Yeni Sayaç", expanded=True):
            s_ad = st.text_input("Etkinlik")
            s_tar = st.date_input("Tarih")
            if st.button("Kaydet", key="s_btn"):
                islem_yap("ekle", urun=s_ad, tip="COUNTDOWN", zaman=str(s_tar))
                st.rerun()
        
        sayaclar = st.session_state.local_df[st.session_state.local_df["Tip"] == "COUNTDOWN"]
        for i, row in sayaclar.iterrows():
            try:
                hedef = datetime.strptime(row["Zaman"], "%Y-%m-%d").date()
                kalan = (hedef - datetime.now().date()).days
                c1, c2 = st.columns([0.8, 0.2])
                with c1: st.write(f"🎉 **{row['Urun']}**"); st.info(f"{kalan} gün kaldı") if kalan>0 else st.success("BUGÜN!")
                with c2: 
                    if st.button("🗑️", key=f"sd_{i}"): islem_yap("sil", urun=row['Urun']); st.rerun()
                st.divider()
            except: pass

    with tab3: # NOTLAR
        with st.expander("➕ Not Ekle"):
            baslik = st.text_input("Başlık")
            icerik = st.text_area("İçerik")
            if st.button("Kaydet", key="n_btn") and baslik:
                islem_yap("ekle", urun=baslik, tip="NOTE", mesaj=icerik)
                st.rerun()
        
        notlar = st.session_state.local_df[st.session_state.local_df["Tip"] == "NOTE"]
        for i, row in notlar.iterrows():
            with st.expander(f"📒 {row['Urun']}"):
                st.code(row['Mesaj'])
                if st.button("Sil", key=f"nd_{i}"): islem_yap("sil", urun=row['Urun']); st.rerun()

def sayfa_dosya(): # YENİDEN EKLENDİ
    st.subheader("📂 PDF Araçları")
    if not PDF_VAR: st.error("Lütfen 'img2pdf' kütüphanesini yükleyin.")
    else:
        uploaded = st.file_uploader("Resim Yükle (JPG/PNG)", type=["jpg", "png", "jpeg"], accept_multiple_files=False)
        if uploaded:
            st.image(uploaded, width=200)
            if st.button("PDF'e Çevir ve İndir", type="primary"):
                pdf_bytes = img2pdf.convert(uploaded.read())
                st.download_button("⬇️ İndir", pdf_bytes, file_name=f"{uploaded.name}.pdf", mime="application/pdf")

def sayfa_ekonomi():
    st.subheader("💰 Hane Ekonomisi")
    tab1, tab2 = st.tabs(["GELİR/GİDER", "YATIRIMLAR"])
    
    with tab1: # FATURALAR & BÜTÇE
        with st.expander("➕ Fatura/Ödeme Ekle", expanded=False):
            col1, col2 = st.columns(2)
            f_ad = col1.text_input("Fatura Adı", placeholder="İnternet...")
            f_gun = col2.number_input("Son Ödeme Günü (1-31)", 1, 31, 15)
            if st.button("Fatura Kaydet", use_container_width=True):
                islem_yap("ekle", urun=f_ad, tip="FATURA", zaman=str(f_gun), mesaj="09:00", durum="HER_AY"); st.rerun()
                
        # Fatura Listesi
        df_f = st.session_state.local_df[st.session_state.local_df["Tip"] == "FATURA"]
        if not df_f.empty:
            st.markdown("##### 📅 Yaklaşan Ödemeler")
            df_f["Gun"] = pd.to_numeric(df_f["Zaman"], errors='coerce').fillna(32)
            for i, row in df_f.sort_values("Gun").iterrows():
                kalan = int(row["Gun"]) - datetime.now().day
                durum_renk = "red" if kalan == 0 else "orange" if kalan < 3 else "green"
                st.markdown(f"**{row['Urun']}**: <span style='color:{durum_renk}'>{kalan} gün kaldı</span>", unsafe_allow_html=True)
                if st.button("Ödendi (Sil)", key=f"fd_{i}"): islem_yap("sil", urun=row['Urun']); st.rerun()
            st.markdown("---")

        # Gelir Gider Ekleme
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1: aciklama = st.text_input("İşlem", placeholder="Market, Maaş...")
        with c2: tutar = st.number_input("Tutar", min_value=0.0, step=50.0)
        with c3: tur = st.selectbox("Tür", ["Gider", "Gelir"], label_visibility="collapsed")
        if st.button("KAYDET", use_container_width=True, key="btn_eco"):
            if aciklama and tutar > 0:
                islem_yap("ekle", urun=aciklama, tip="BUTCE", mesaj=str(tutar), durum=tur, zaman=datetime.now().strftime("%Y-%m-%d")); st.rerun()
        
        # Bütçe Özeti
        df_b = st.session_state.local_df[st.session_state.local_df["Tip"] == "BUTCE"]
        if not df_b.empty:
            df_b["Tutar_Sayi"] = pd.to_numeric(df_b["Mesaj"], errors='coerce').fillna(0)
            gelir = df_b[df_b["Durum"]=="Gelir"]["Tutar_Sayi"].sum()
            gider = df_b[df_b["Durum"]=="Gider"]["Tutar_Sayi"].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("Gelir", f"{gelir:.0f}₺"); c2.metric("Gider", f"{gider:.0f}₺"); c3.metric("Kalan", f"{gelir-gider:.0f}₺")
            st.dataframe(df_b[["Zaman", "Urun", "Mesaj", "Durum"]], use_container_width=True, hide_index=True)

    with tab2: # YATIRIMLAR
        if GRAFIK_VAR:
            df_y = st.session_state.local_df[st.session_state.local_df["Tip"] == "YATIRIM"]
            with st.expander("➕ Varlık Ekle"):
                y_ad = st.text_input("Varlık Adı")
                y_deg = st.number_input("Değer (TL)")
                if st.button("Ekle") and y_ad:
                    islem_yap("ekle", urun=y_ad, tip="YATIRIM", mesaj=str(y_deg)); st.rerun()

            if not df_y.empty:
                df_y["Deger"] = pd.to_numeric(df_y["Mesaj"], errors='coerce').fillna(0)
                fig = px.pie(df_y, values='Deger', names='Urun', title='Varlık Dağılımı', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
                for i, row in df_y.iterrows():
                    c1, c2 = st.columns([0.8, 0.2])
                    with c1: st.write(f"💎 **{row['Urun']}**: {row['Mesaj']} ₺")
                    with c2: 
                         if st.button("Sil", key=f"ydel_{i}"): islem_yap("sil", urun=row['Urun']); st.rerun()
            else: st.info("Yatırım ekleyin.")
        else: st.warning("Grafikler için 'plotly' gerekli.")

def karsilama_paneli():
    if random.random() < 0.25:
        soz = random.choice(prenses_sozleri())
        css, title = "prenses-box", "🐾 PRENSES!"
    else:
        soz = random.choice(ask_kavanozu_sozleri())
        css, title = "welcome-box", "Hoşgeldiniz! 🏡"
    st.markdown(f'<div class="{css}"><div class="welcome-title">{title}</div><div class="welcome-note">{soz}</div></div>', unsafe_allow_html=True)

def prenses_sozleri():
    return ["🐾 Mama kabım boş!", "🐾 Koltuğumdan kalk!", "🐾 Beni sev!", "🐾 Tüy döktüm, süpür!", "🐾 Evin reisi benim."]

def ask_kavanozu_sozleri():
    return ["Seninle her şey güzel.", "Çaylar benden!", "Gülüşün harika.", "İyi ki varsın.", "Evimizin neşesisin."]

# ==============================================================================
# 🚀 UYGULAMA BAŞLATICI
# ==============================================================================
with st.sidebar:
    st.title("🏡 Ev Asistanı")
    st.caption("v2.1 Full")
    menu = st.radio("Menü", ["Ana Ekran", "Yemek & Mutfak", "Ekonomi", "Yaşam", "Dosya"])
    st.markdown("---")
    st.info(f"Mod: {'🟢 Online' if ONLINE_MOD else '🔴 Offline'}")

if menu == "Ana Ekran": sayfa_ana_ekran()
elif menu == "Yemek & Mutfak": sayfa_yemek()
elif menu == "Ekonomi": sayfa_ekonomi()
elif menu == "Yaşam": sayfa_yasam()
elif menu == "Dosya": sayfa_dosya()
