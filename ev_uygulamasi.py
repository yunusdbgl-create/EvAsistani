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
    page_title="Ev Asistanı Full",
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
# 🎨 UI STİLLERİ (Eski tasarıma sadık, temiz görünüm)
# ==============================================================================
st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    
    /* Kartlar ve Genişleyen Kutular */
    div.stExpander {
        background: white; border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 8px; border: 1px solid #e0e0e0;
    }
    
    /* Butonlar */
    button[kind="primary"] {
        background-color: #4b6cb7;
        border: none; transition: all 0.2s;
    }
    
    /* Karşılama Alanları */
    .welcome-box {
        background: linear-gradient(120deg, #84fab0 0%, #8fd3f4 100%);
        color: #2c3e50; padding: 15px; border-radius: 15px;
        text-align: center; margin-bottom: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .prenses-box {
        background: linear-gradient(120deg, #fccb90 0%, #d57eeb 100%);
        color: #4a235a; padding: 15px; border-radius: 15px;
        text-align: center; margin-bottom: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        border: 2px solid #fff;
    }
    .welcome-title { font-size: 20px; font-weight: bold; margin-bottom: 5px; }
    .welcome-note { font-size: 14px; font-style: italic; }
    
    /* Kategori Etiketi */
    .cat-badge { font-size: 12px; font-weight: bold; color: #555; text-transform: uppercase; letter-spacing: 1px; }
    
    div[data-testid="column"] { gap: 5px; }
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
    if not ONLINE_MOD: st.warning("⚠️ Offline Moddasınız.")

# ==============================================================================
# 🧠 YARDIMCI FONKSİYONLAR
# ==============================================================================
def get_kategori_renk(kategori):
    renkler = {
        "Meyve": "#2ecc71", "Sebze": "#2ecc71", "Manav": "#2ecc71",
        "Et": "#e74c3c", "Şarküteri": "#e74c3c",
        "Süt": "#3498db", "Kahvaltılık": "#f1c40f",
        "Temizlik": "#9b59b6", "Ev": "#9b59b6",
        "Gıda": "#e67e22", "Bakliyat": "#d35400",
        "Atıştırmalık": "#e84393", "Genel": "#95a5a6"
    }
    for key, color in renkler.items():
        if key in kategori: return color
    return "#34495e"

def mutfak_sefi_motoru(marketten_gelenler, manuel_eklenenler):
    tum_malzemeler = set()
    for urun in marketten_gelenler: tum_malzemeler.add(urun.lower().split("(")[0].strip())
    for urun in manuel_eklenenler: tum_malzemeler.add(urun.lower())
    tarifler = {
        "Menemen": ["yumurta", "domates", "biber"], "Omlet": ["yumurta", "peynir", "tereyağı"],
        "Mercimek Çorbası": ["mercimek", "soğan", "salça", "yağ"], "Karnıyarık": ["patlıcan", "kıyma", "domates", "soğan"],
        "Köfte Patates": ["kıyma", "patates", "soğan", "ekmek"], "Makarna": ["makarna", "salça", "yağ"],
        "Tavuk Sote": ["tavuk", "biber", "domates", "soğan"], "Kısır": ["bulgur", "salça", "yeşillik", "limon"],
        "Cacık": ["yoğurt", "salatalık", "sarımsak"], "Pilav": ["pirinç", "tereyağı", "şehriye"],
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
        # Çift kayıt kontrolü
        if kwargs.get("tip") in ["MARKET", "TODO"]:
             if not df[(df["Tip"] == kwargs.get("tip")) & (df["Urun"] == kwargs.get("urun"))].empty:
                 st.toast(f"⚠️ {kwargs.get('urun')} zaten listede!"); return

        yeni = {"Urun": kwargs.get("urun"), "Durum": kwargs.get("durum", "0"), 
                "Mesaj": kwargs.get("mesaj", ""), "Zaman": kwargs.get("zaman", ""), 
                "Tip": kwargs.get("tip")}
        
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
            msg = "✅ Alındı!" if yeni_durum == "1" else "📦 Geri eklendi!"
            st.toast(msg)

# ==============================================================================
# 📱 ANA SAYFA & PANELLER
# ==============================================================================
def karsilama_paneli():
    if random.random() < 0.25:
        soz = random.choice(["Mama kabım boş!", "Koltuğumdan kalk!", "Beni sev!", "Tüy döktüm, süpür!", "Evin reisi benim."])
        css, title = "prenses-box", "🐾 PRENSES KONUŞTU!"
    else:
        soz = random.choice(["Seninle her şey güzel.", "Çaylar benden!", "Gülüşün harika.", "İyi ki varsın.", "Evimizin neşesisin."])
        css, title = "welcome-box", "Hoşgeldiniz! 🏡"
    st.markdown(f'<div class="{css}"><div class="welcome-title">{title}</div><div class="welcome-note">{soz}</div></div>', unsafe_allow_html=True)

def dashboard_goster():
    df = st.session_state.local_df
    # Fatura
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
    c1.metric("🧾 Sıradaki", fatura_txt, kalan_txt)
    c2.metric("🛒 Sepet", f"{sepet} Ürün")
    st.markdown("---")

def sayfa_ana_ekran():
    karsilama_paneli()
    dashboard_goster()
    
    if st.button("🎁 Bana Bir Sürpriz Yap", type="primary", use_container_width=True):
        st.balloons(); st.success(f"💌 {random.choice(['Seni seviyorum!', 'Harikasın!', 'Bugün senin günün!'])}")

    tab1, tab2, tab3 = st.tabs(["🛒 MARKET", "📝 İŞLER", "🔔 ALARM"])
    
    # --- MARKET KISMI ---
    with tab1:
        # 1. KATEGORİ SİSTEMİ GERİ GELDİ
        df = st.session_state.local_df
        df_market = df[df["Tip"] == "MARKET"]
        
        VARSAYILAN_KATEGORILER = ["🍏 Meyve & Sebze", "🥩 Et & Şarküteri", "🥛 Süt & Kahvaltılık", "🍞 Gıda & Bakliyat", "🧹 Temizlik", "🍫 Atıştırmalık"]
        kayitli_kat = {k for k in set(df_market["Mesaj"].dropna().unique()) if k and k not in ["Genel", "None", "✏️ Yeni Kategori Yaz"]}
        TUM_KATEGORILER = sorted(list(set(VARSAYILAN_KATEGORILER) | kayitli_kat)) + ["✏️ Yeni Kategori Yaz"]
        
        # 2. EKLEME ALANI (ESKİSİ GİBİ KOLONLU)
        c1, c2, c3 = st.columns([0.40, 0.40, 0.20], vertical_alignment="bottom")
        with c1: urun_giris = st.text_input("Ürün", key="m_in", label_visibility="collapsed", placeholder="Ürün Adı...")
        with c2: kat_secim = st.selectbox("Kategori", TUM_KATEGORILER, key="m_cat", label_visibility="collapsed")
        with c3: btn_ekle = st.button("EKLE", key="m_btn", use_container_width=True)
        
        # Yeni Kategori Inputu
        secilen_kategori = kat_secim
        if kat_secim == "✏️ Yeni Kategori Yaz":
            secilen_kategori = st.text_input("Yeni Kategori Adı:", key="m_cat_new", placeholder="Örn: Tekne")
        
        if btn_ekle and urun_giris:
            islem_yap("ekle", urun=urun_giris, tip="MARKET", mesaj=secilen_kategori if secilen_kategori else "Genel")
            st.rerun()

        st.markdown("---")
        
        # 3. ALINACAKLAR LİSTESİ (Status "0")
        alinacaklar = df_market[df_market["Durum"] == "0"]
        st.subheader("📌 Alınacaklar")
        if alinacaklar.empty: st.success("Sepet Boş! 🎉")
        
        kategori_sirasi = sorted(list(set(TUM_KATEGORILER[:-1]) | {k for k in alinacaklar["Mesaj"].unique() if k}))
        
        for kat in kategori_sirasi:
            items = alinacaklar[alinacaklar["Mesaj"] == kat]
            if items.empty and kat not in alinacaklar["Mesaj"].values: continue # Boş kategoriyi gösterme
            
            if not items.empty:
                renk = get_kategori_renk(kat)
                with st.expander(f"{kat} ({len(items)})", expanded=True):
                    st.markdown(f"<div style='height:3px; background-color:{renk}; border-radius:5px; margin-bottom:10px;'></div>", unsafe_allow_html=True)
                    for i, row in items.iterrows():
                        c1, c2 = st.columns([0.8, 0.2], vertical_alignment="center")
                        with c1:
                            # İşaretleyince "1" (Alındı) olur ve listeyi yeniler
                            if st.checkbox(f"**{row['Urun']}**", key=f"mk_{i}"):
                                islem_yap("guncelle", urun=row['Urun'], yeni_durum="1"); st.rerun()
                        with c2:
                            if st.button("🗑️", key=f"md_{i}"): islem_yap("sil", urun=row['Urun']); st.rerun()

        # 4. ALINANLAR / GEÇMİŞ KISMI (GERİ GELDİ!)
        st.divider()
        tamamlananlar = df_market[df_market["Durum"] == "1"]
        with st.expander(f"📦 Alınanlar / Geçmiş ({len(tamamlananlar)})", expanded=False):
            if tamamlananlar.empty: st.info("Henüz bir şey alınmamış.")
            else:
                for i, row in tamamlananlar.iterrows():
                    c1, c2 = st.columns([0.8, 0.2], vertical_alignment="center")
                    with c1:
                        # Geri Ekleme Butonu
                        if st.button(f"➕ {row['Urun']} (Geri Ekle)", key=f"restore_{i}", use_container_width=True):
                            islem_yap("guncelle", urun=row['Urun'], yeni_durum="0"); st.rerun()
                    with c2:
                        if st.button("🗑️", key=f"del_h_{i}"): islem_yap("sil", urun=row['Urun']); st.rerun()

    # --- İŞLER KISMI ---
    with tab2:
        df_todo = df[df["Tip"] == "TODO"]
        VARSAYILAN_ISLER = ["🏠 Ev İçi", "🔧 Tamirat", "🏢 Dışarı İşleri", "🚗 Araba"]
        kayitli_is = {k for k in set(df_todo["Mesaj"].dropna().unique()) if k and k not in ["Genel", "None", "✏️ Yeni Kategori Yaz"]}
        TUM_ISLER = sorted(list(set(VARSAYILAN_ISLER) | kayitli_is)) + ["✏️ Yeni Kategori Yaz"]

        c1, c2, c3 = st.columns([0.40, 0.40, 0.20], vertical_alignment="bottom")
        with c1: is_giris = st.text_input("Görev", key="t_in", label_visibility="collapsed", placeholder="Yapılacak iş...")
        with c2: is_kat = st.selectbox("Kategori", TUM_ISLER, key="t_cat", label_visibility="collapsed")
        with c3: btn_is = st.button("EKLE", key="t_btn", use_container_width=True)
        
        secilen_is_kat = is_kat
        if is_kat == "✏️ Yeni Kategori Yaz":
            secilen_is_kat = st.text_input("Yeni Kategori:", key="t_cat_new")
        
        if btn_is and is_giris:
            islem_yap("ekle", urun=is_giris, tip="TODO", mesaj=secilen_is_kat if secilen_is_kat else "Genel")
            st.rerun()
            
        # İş Listesi
        yapilacaklar = df_todo[df_todo["Durum"] == "0"]
        if yapilacaklar.empty: st.success("Tüm işler bitti! 🏖️")
        else:
            is_cats = sorted(list(set(TUM_ISLER[:-1]) | {k for k in yapilacaklar["Mesaj"].unique() if k}))
            for kat in is_cats:
                items = yapilacaklar[yapilacaklar["Mesaj"] == kat]
                if items.empty: continue
                with st.expander(f"{kat} ({len(items)})", expanded=True):
                    for i, row in items.iterrows():
                        c1, c2 = st.columns([0.8, 0.2], vertical_alignment="center")
                        with c1:
                            if st.checkbox(f"**{row['Urun']}**", key=f"tk_{i}"): islem_yap("guncelle", urun=row['Urun'], yeni_durum="1"); st.rerun()
                        with c2:
                            if st.button("🗑️", key=f"td_{i}"): islem_yap("sil", urun=row['Urun']); st.rerun()

    # --- ALARM ---
    with tab3:
        with st.form("alarm"):
            c1, c2 = st.columns([3, 1])
            msg = c1.text_input("Alarm Notu")
            sure = c2.number_input("Dk", 1, 60, 15)
            if st.form_submit_button("🔔 Kur", use_container_width=True):
                hedef = datetime.now() + timedelta(minutes=sure)
                islem_yap("ekle", urun=f"{msg} ({hedef.strftime('%H:%M')})", tip="ALARM", zaman=hedef.strftime("%Y-%m-%d %H:%M:%S"), mesaj=msg, durum="-1")
                try: 
                    import requests
                    requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=f"Alarm: {msg}".encode("utf-8"))
                except: pass
                st.rerun()
        
        df_a = df[df["Tip"] == "ALARM"]
        for i, row in df_a.iterrows():
            try:
                kalan = (datetime.strptime(row["Zaman"], "%Y-%m-%d %H:%M:%S") - datetime.now()).total_seconds()
                c1, c2 = st.columns([0.8, 0.2])
                with c1: st.write(f"⏰ **{row['Mesaj']}**"); st.caption(f"Kalan: {int(kalan/60)} dk" if kalan > 0 else "Süre Doldu!")
                with c2: 
                    if st.button("Kapat", key=f"ad_{i}"): islem_yap("sil", urun=row["Urun"]); st.rerun()
                st.divider()
            except: pass

def sayfa_yemek():
    st.subheader("🍽️ Mutfak & Yemek")
    tab1, tab2, tab3 = st.tabs(["🔥 EŞLEŞME", "👨‍🍳 ŞEF", "LİSTE"])
    with tab1:
        st.caption("Kararsız kalınca kullanın:")
        yemekler = st.session_state.local_df[st.session_state.local_df["Tip"] == "YEMEK_OGUN"]["Urun"].tolist()
        if not yemekler: st.warning("Listeye yemek ekleyin.")
        else:
            if 'oyun_yemegi' not in st.session_state: st.session_state.oyun_yemegi = random.choice(yemekler)
            st.markdown(f"<h3 style='text-align:center;'>🍽️ {st.session_state.oyun_yemegi}</h3>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("👎 Olmaz", use_container_width=True): st.session_state.oyun_yemegi = random.choice(yemekler); st.rerun()
            if c2.button("👍 Olur!", type="primary", use_container_width=True): st.balloons(); st.success(f"Seçildi: {st.session_state.oyun_yemegi}")

    with tab2:
        market_stok = st.session_state.local_df[(st.session_state.local_df["Tip"] == "MARKET") & (st.session_state.local_df["Durum"] == "1")]["Urun"].tolist()
        ek = st.multiselect("Ek Malzemeler", ["Yumurta", "Patates", "Kıyma", "Tavuk", "Makarna", "Domates", "Soğan", "Salça"])
        if st.button("Tarif Bul", use_container_width=True):
            tam, eksik = mutfak_sefi_motoru(market_stok, ek)
            if tam: st.success(f"✅ Yapabilirsin: {', '.join(tam)}")
            elif eksik: 
                for y, e in eksik: st.warning(f"🟠 {y} için eksik: {', '.join(e)}")
            else: st.error("Tarif bulunamadı.")
            
    with tab3:
        c1, c2 = st.columns([0.7, 0.3])
        with c1: y_in = st.text_input("Yemek Ekle", key="y_i", label_visibility="collapsed")
        with c2: 
            if st.button("Ekle", key="y_b", use_container_width=True) and y_in:
                islem_yap("ekle", urun=y_in, tip="YEMEK_OGUN", durum="1"); st.rerun()
        
        y_df = st.session_state.local_df[st.session_state.local_df["Tip"] == "YEMEK_OGUN"]
        for i, row in y_df.iterrows():
            c1, c2 = st.columns([0.8, 0.2])
            with c1: st.write(f"🥘 {row['Urun']}")
            with c2: 
                if st.button("🗑️", key=f"yd_{i}"): islem_yap("sil", urun=row['Urun']); st.rerun()

def sayfa_yasam():
    st.subheader("🧬 Yaşam Takibi")
    tab1, tab2, tab3 = st.tabs(["RUTİN", "SAYAÇ", "NOTLAR"])
    with tab1:
        c1, c2 = st.columns([0.7, 0.3])
        with c1: r_in = st.text_input("Rutin", key="r_i", label_visibility="collapsed")
        with c2: 
            if st.button("Ekle", key="r_b", use_container_width=True) and r_in:
                islem_yap("ekle", urun=r_in, tip="RUTIN", durum="0"); st.rerun()
        rutinler = st.session_state.local_df[st.session_state.local_df["Tip"] == "RUTIN"]
        if not rutinler.empty:
            comp = len(rutinler[rutinler["Durum"]=="1"])
            st.progress(comp/len(rutinler))
            for i, row in rutinler.iterrows():
                c1, c2 = st.columns([0.8, 0.2])
                with c1:
                    chk = row['Durum'] == "1"
                    if st.checkbox(f"**{row['Urun']}**", value=chk, key=f"rk_{i}"):
                        if not chk: islem_yap("guncelle", urun=row['Urun'], yeni_durum="1"); st.rerun()
                    else:
                        if chk: islem_yap("guncelle", urun=row['Urun'], yeni_durum="0"); st.rerun()
                with c2:
                    if st.button("🗑️", key=f"rd_{i}"): islem_yap("sil", urun=row['Urun']); st.rerun()

    with tab2:
        with st.expander("Yeni Sayaç"):
            s_ad = st.text_input("Olay")
            s_tr = st.date_input("Tarih")
            if st.button("Kaydet", key="s_b"): islem_yap("ekle", urun=s_ad, tip="COUNTDOWN", zaman=str(s_tr)); st.rerun()
        df_s = st.session_state.local_df[st.session_state.local_df["Tip"] == "COUNTDOWN"]
        for i, row in df_s.iterrows():
            try:
                kalan = (datetime.strptime(row["Zaman"], "%Y-%m-%d").date() - datetime.now().date()).days
                c1, c2 = st.columns([0.8, 0.2])
                with c1: st.write(f"🎉 {row['Urun']}: **{kalan} gün**")
                with c2: 
                    if st.button("🗑️", key=f"sd_{i}"): islem_yap("sil", urun=row['Urun']); st.rerun()
            except: pass

    with tab3:
        with st.expander("Not Ekle"):
            baslik = st.text_input("Başlık")
            icerik = st.text_area("İçerik")
            if st.button("Kaydet", key="n_b"): islem_yap("ekle", urun=baslik, tip="NOTE", mesaj=icerik); st.rerun()
        df_n = st.session_state.local_df[st.session_state.local_df["Tip"] == "NOTE"]
        for i, row in df_n.iterrows():
            with st.expander(f"📒 {row['Urun']}"):
                st.code(row['Mesaj'])
                if st.button("Sil", key=f"nd_{i}"): islem_yap("sil", urun=row['Urun']); st.rerun()

def sayfa_ekonomi():
    st.subheader("💰 Hane Ekonomisi")
    tab1, tab2 = st.tabs(["GELİR/GİDER", "YATIRIM"])
    with tab1:
        with st.expander("Fatura Ekle"):
            f_ad = st.text_input("Fatura")
            f_gun = st.number_input("Gün", 1, 31, 15)
            if st.button("Kaydet", key="f_b"): islem_yap("ekle", urun=f_ad, tip="FATURA", zaman=str(f_gun), mesaj="09:00", durum="HER_AY"); st.rerun()
        
        df_f = st.session_state.local_df[st.session_state.local_df["Tip"] == "FATURA"]
        if not df_f.empty:
            df_f["Gun"] = pd.to_numeric(df_f["Zaman"], errors='coerce').fillna(32)
            for i, row in df_f.sort_values("Gun").iterrows():
                kalan = int(row["Gun"]) - datetime.now().day
                st.write(f"📅 **{row['Urun']}**: {kalan} gün kaldı")
                if st.button("Ödendi", key=f"fd_{i}"): islem_yap("sil", urun=row['Urun']); st.rerun()
            st.divider()

        c1, c2, c3 = st.columns([2,1,1])
        with c1: u = st.text_input("İşlem", key="b_u")
        with c2: t = st.number_input("Tutar", key="b_t")
        with c3: tur = st.selectbox("Tür", ["Gider", "Gelir"], key="b_tr")
        if st.button("Ekle", key="b_b") and u:
             islem_yap("ekle", urun=u, tip="BUTCE", mesaj=str(t), durum=tur, zaman=datetime.now().strftime("%Y-%m-%d")); st.rerun()
        
        df_b = st.session_state.local_df[st.session_state.local_df["Tip"] == "BUTCE"]
        if not df_b.empty:
            df_b["Tutar"] = pd.to_numeric(df_b["Mesaj"], errors='coerce').fillna(0)
            gelir = df_b[df_b["Durum"]=="Gelir"]["Tutar"].sum()
            gider = df_b[df_b["Durum"]=="Gider"]["Tutar"].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("Gelir", f"{gelir:.0f}"); c2.metric("Gider", f"{gider:.0f}"); c3.metric("Net", f"{gelir-gider:.0f}")
            st.dataframe(df_b[["Zaman", "Urun", "Mesaj", "Durum"]], hide_index=True, use_container_width=True)

    with tab2:
        with st.expander("Varlık Ekle"):
            y_ad = st.text_input("Varlık")
            y_dg = st.number_input("Değer")
            if st.button("Kaydet", key="y_b"): islem_yap("ekle", urun=y_ad, tip="YATIRIM", mesaj=str(y_dg)); st.rerun()
        if GRAFIK_VAR:
            df_y = st.session_state.local_df[st.session_state.local_df["Tip"] == "YATIRIM"]
            if not df_y.empty:
                df_y["Deger"] = pd.to_numeric(df_y["Mesaj"], errors='coerce').fillna(0)
                st.plotly_chart(px.pie(df_y, values='Deger', names='Urun', hole=0.4), use_container_width=True)
                for i, row in df_y.iterrows():
                    c1, c2 = st.columns([0.8, 0.2])
                    with c1: st.write(f"💎 {row['Urun']}: {row['Mesaj']} TL")
                    with c2: 
                        if st.button("🗑️", key=f"ydl_{i}"): islem_yap("sil", urun=row['Urun']); st.rerun()

def sayfa_dosya():
    st.subheader("📂 PDF Araçları")
    if PDF_VAR:
        up = st.file_uploader("Resim", type=["jpg","png"])
        if up:
            st.image(up, width=200)
            if st.button("PDF İndir", type="primary"):
                st.download_button("İndir", img2pdf.convert(up.read()), f"{up.name}.pdf", "application/pdf")
    else: st.error("img2pdf modülü eksik.")

# ==============================================================================
# 🚀 BAŞLAT
# ==============================================================================
with st.sidebar:
    st.header("Menü")
    secim = st.radio("Git:", ["Ana Ekran", "Yemek & Mutfak", "Ekonomi", "Yaşam", "Dosya"])
    st.markdown("---"); st.info(f"Mod: {'🟢 Online' if ONLINE_MOD else '🔴 Offline'}")

if secim == "Ana Ekran": sayfa_ana_ekran()
elif secim == "Yemek & Mutfak": sayfa_yemek()
elif secim == "Ekonomi": sayfa_ekonomi()
elif secim == "Yaşam": sayfa_yasam()
elif secim == "Dosya": sayfa_dosya()
