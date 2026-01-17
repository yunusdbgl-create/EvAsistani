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

# Grafik Kütüphanesi Kontrolü
try:
    import plotly.express as px
    GRAFIK_VAR = True
except ImportError:
    GRAFIK_VAR = False

# ==============================================================================
# 🎨 MODERN UI STİLLERİ (CSS)
# ==============================================================================
st.markdown("""
<style>
    /* Genel Font ve Arka Plan İyileştirmeleri */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* Kart Tasarımı (Glassmorphism) */
    div.css-1r6slb0, div.stExpander {
        background: white;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 10px;
        border: 1px solid #e9ecef;
    }
    
    /* Özel Butonlar */
    button[kind="primary"] {
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
        border: none;
        transition: all 0.3s ease;
    }
    button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
    
    /* Karşılama Alanları */
    .welcome-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
    }
    .prenses-box {
        background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 99%, #fecfef 100%);
        color: #5e2d48;
        padding: 20px;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 25px;
        border: 2px solid white;
        box-shadow: 0 10px 20px rgba(255, 154, 158, 0.3);
    }
    .welcome-title { font-size: 24px; font-weight: 800; margin-bottom: 8px; }
    .welcome-note { font-size: 16px; font-style: italic; opacity: 0.9; }
    
    /* Kategori Çizgileri */
    .category-line { height: 4px; border-radius: 2px; margin-bottom: 12px; }
    
    /* Mobil Uyumluluk İçin Boşluk Ayarları */
    div[data-testid="column"] { gap: 10px; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 🔌 VERİTABANI BAĞLANTISI (GSPREAD & OFFLINE MOD)
# ==============================================================================
@st.cache_resource
def get_gspread_client():
    """Google Sheets bağlantısını önbelleğe alır."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(dict(st.secrets["connections"]["gsheets"]), scopes=scopes)
        return gspread.authorize(creds), True
    except Exception as e:
        return None, False

# Global Bağlantı Durumu
gc, ONLINE_MOD = get_gspread_client()

def veri_senkronize_et(df, islem_tipi, veri=None):
    """Arka planda veriyi senkronize eder (Thread ile UI donmaz)."""
    if not ONLINE_MOD: return # Offline ise işlem yapma
    
    def thread_gorevi():
        try:
            sheet = gc.open(DOSYA_ADI).sheet1
            if islem_tipi == "ekle":
                sheet.append_row(veri)
            elif islem_tipi == "sil":
                urun_adi = veri
                try:
                    cell = sheet.find(urun_adi)
                    sheet.delete_rows(cell.row)
                except: pass
            elif islem_tipi == "guncelle":
                urun, durum = veri
                try:
                    cell = sheet.find(urun)
                    sheet.update_cell(cell.row, 2, str(durum))
                except: pass
            elif islem_tipi == "yatirim_guncelle":
                 # Karmaşık yatırım mantığı buraya taşınabilir
                 pass 
        except Exception as e:
            print(f"Sync Hatası: {e}")

    threading.Thread(target=thread_gorevi).start()

def verileri_yukle():
    """Başlangıçta verileri çeker."""
    cols = ["Urun", "Durum", "Mesaj", "Zaman", "Tip"]
    if ONLINE_MOD:
        try:
            data = gc.open(DOSYA_ADI).sheet1.get_all_values()
            if len(data) > 1:
                df = pd.DataFrame(data[1:], columns=data[0]).astype(str)
                # Sütun eksikliği kontrolü
                for col in cols:
                    if col not in df.columns: df[col] = ""
                return df
        except: pass
    
    # Fallback (Offline veya Boş Veri)
    return pd.DataFrame(columns=cols)

# Session State Başlatma
if 'local_df' not in st.session_state:
    st.session_state.local_df = verileri_yukle()
    if not ONLINE_MOD:
        st.warning("⚠️ Google Sheets bağlantısı bulunamadı. 'Offline/Demo Mod'dasınız. Değişiklikler sayfayı yenileyince kaybolur.")

# ==============================================================================
# 🧠 YARDIMCI FONKSİYONLAR
# ==============================================================================
def get_kategori_renk(kategori):
    renkler = {
        "Meyve": "#2ecc71", "Sebze": "#27ae60", 
        "Et": "#e74c3c", "Şarküteri": "#c0392b",
        "Süt": "#3498db", "Kahvaltılık": "#f1c40f",
        "Temizlik": "#9b59b6", "Ev": "#8e44ad",
        "Gıda": "#e67e22", "Bakliyat": "#d35400",
        "Atıştırmalık": "#e84393", "Genel": "#95a5a6"
    }
    for key, color in renkler.items():
        if key in kategori: return color
    return "#34495e" # Varsayılan koyu mavi

def ask_kavanozu_sozleri():
    return [
        "Seninle her şey daha güzel.", "Bugün yine harika görünüyorsun.", "İyi ki hayatımdasın.", 
        "Akşam çayı benden!", "Gülüşün güneşten parlak.", "Dünyanın en şanslısıyım.",
        "Seni çok seviyorum.", "Bugün senin günün olsun.", "Seninle yaşlanmak istiyorum.",
        "Evimizin neşesi sensin.", "İyi ki varsın canım."
    ]

def prenses_sozleri():
    return [
        "🐾 Mama kabım neden boş?", "🐾 Koltuğumdan kalkar mısın?", "🐾 Beni sevmeyi unuttun mu?",
        "🐾 Bugün çok tüy döktüm, kolay gelsin.", "🐾 Evin reisi benim, unutma.", "🐾 Miyav! (Sev beni)"
    ]

# ==============================================================================
# ⚡ HIZLI İŞLEM YÖNETİCİSİ
# ==============================================================================
def islem_yap(aksiyon, **kwargs):
    df = st.session_state.local_df
    
    if aksiyon == "ekle":
        yeni_satir = {
            "Urun": kwargs.get("urun"), 
            "Durum": kwargs.get("durum", "0"), 
            "Mesaj": kwargs.get("mesaj", ""), 
            "Zaman": kwargs.get("zaman", ""), 
            "Tip": kwargs.get("tip")
        }
        
        # Mükerrer Kayıt Kontrolü (Sadece belirli tiplerde)
        if kwargs.get("tip") in ["MARKET", "TODO"]:
             if not df[(df["Tip"] == kwargs.get("tip")) & (df["Urun"] == kwargs.get("urun"))].empty:
                 st.toast("⚠️ Bu zaten listede var!", icon="✋")
                 return

        st.session_state.local_df = pd.concat([df, pd.DataFrame([yeni_satir])], ignore_index=True)
        veri_senkronize_et(None, "ekle", list(yeni_satir.values()))
        st.toast(f"✅ {kwargs.get('urun')} eklendi!", icon="🎉")

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
            
    elif aksiyon == "temizle":
        # Sadece tamamlananları temizle (İsteğe bağlı) veya duplicate temizle
        st.session_state.local_df = df.drop_duplicates(subset=['Urun', 'Tip'], keep='first')
        st.toast("🧹 Liste optimize edildi.")
        time.sleep(0.5)
        st.rerun()

# ==============================================================================
# 🧩 UI BİLEŞENLERİ (Components)
# ==============================================================================
def karsilama_paneli():
    if random.random() < 0.25:
        soz = random.choice(prenses_sozleri())
        css_class = "prenses-box"
        baslik = "🐾 PRENSES KONUŞTU!"
    else:
        saat = datetime.now().hour
        selam = "Günaydın" if 5<=saat<12 else "Tünaydın" if 12<=saat<18 else "İyi Akşamlar"
        soz = random.choice(["Bugün harika şeyler olacak.", "Eksikleri hemen not et.", "Evimiz kalemizdir."])
        css_class = "welcome-box"
        baslik = f"{selam}! ☀️"
        
    st.markdown(f'''
    <div class="{css_class}">
        <div class="welcome-title">{baslik}</div>
        <div class="welcome-note">{soz}</div>
    </div>
    ''', unsafe_allow_html=True)

def oge_satiri(index, row, sil_callback, durum_callback):
    """Listelerdeki her bir öğe için standart görünüm."""
    c1, c2 = st.columns([0.85, 0.15], vertical_alignment="center")
    
    with c1:
        is_checked = row['Durum'] == "1"
        label = f"**{row['Urun']}**"
        
        # Checkbox yerine özel mantık (st.checkbox bazen state kaybedebilir)
        if st.checkbox(label, value=is_checked, key=f"chk_{row['Tip']}_{index}"):
            if not is_checked: durum_callback(row['Urun'], "1"); st.rerun()
        else:
            if is_checked: durum_callback(row['Urun'], "0"); st.rerun()
            
    with c2:
        if st.button("🗑️", key=f"del_{row['Tip']}_{index}"):
            sil_callback(row['Urun'])
            st.rerun()

# ==============================================================================
# 📱 SAYFALAR
# ==============================================================================

def sayfa_ana_ekran():
    if st.button("🎁 Sürpriz Yap", type="primary", use_container_width=True):
        st.balloons()
        st.success(f"💌 {random.choice(ask_kavanozu_sozleri())}")

    tab1, tab2, tab3 = st.tabs(["🛒 MARKET", "📝 GÖREVLER", "🔔 ALARM"])
    
    # --- MARKET ---
    with tab1:
        c1, c2 = st.columns([0.7, 0.3], vertical_alignment="bottom")
        with c1:
            yeni_urun = st.text_input("Hızlı Ekle", placeholder="Süt, Ekmek...", label_visibility="collapsed", key="in_market")
        with c2:
            if st.button("EKLE", key="btn_add_market", use_container_width=True):
                if yeni_urun:
                    islem_yap("ekle", urun=yeni_urun, tip="MARKET", mesaj="Genel")
                    st.rerun()

        df = st.session_state.local_df
        df_market = df[df["Tip"] == "MARKET"]
        alinacaklar = df_market[df_market["Durum"] == "0"]
        
        if alinacaklar.empty:
            st.info("Sepetiniz boş! 🎉")
        else:
            kategoriler = sorted(list(set(alinacaklar["Mesaj"].unique())))
            for kat in kategoriler:
                items = alinacaklar[alinacaklar["Mesaj"] == kat]
                renk = get_kategori_renk(kat)
                
                with st.expander(f"{kat if kat else 'Genel'} ({len(items)})", expanded=True):
                    st.markdown(f"<div class='category-line' style='background-color:{renk};'></div>", unsafe_allow_html=True)
                    for i, row in items.iterrows():
                        oge_satiri(i, row, lambda u: islem_yap("sil", urun=u), lambda u, d: islem_yap("guncelle", urun=u, yeni_durum=d))

    # --- GÖREVLER ---
    with tab2:
        c1, c2 = st.columns([0.7, 0.3], vertical_alignment="bottom")
        with c1: yeni_is = st.text_input("Görev", placeholder="Tamirat, Fatura...", label_visibility="collapsed", key="in_todo")
        with c2: 
            if st.button("EKLE", key="btn_add_todo", use_container_width=True):
                 if yeni_is: islem_yap("ekle", urun=yeni_is, tip="TODO", mesaj="Genel"); st.rerun()
        
        df_todo = df[(df["Tip"] == "TODO") & (df["Durum"] == "0")]
        if df_todo.empty: st.success("Yapılacak iş kalmadı! 🏖️")
        else:
            for i, row in df_todo.iterrows():
                st.markdown("---")
                oge_satiri(i+1000, row, lambda u: islem_yap("sil", urun=u), lambda u, d: islem_yap("guncelle", urun=u, yeni_durum=d))

    # --- ALARM ---
    with tab3:
        with st.form("alarm_form"):
            col1, col2 = st.columns([3, 1])
            not_txt = col1.text_input("Alarm Notu", placeholder="Fırını kapat...")
            sure = col2.number_input("Dk", min_value=1, value=15)
            if st.form_submit_button("🔔 Kur", use_container_width=True):
                hedef = datetime.now() + timedelta(minutes=sure)
                islem_yap("ekle", urun=f"{not_txt} ({hedef.strftime('%H:%M')})", tip="ALARM", zaman=hedef.strftime("%Y-%m-%d %H:%M:%S"), mesaj=not_txt, durum="-1")
                # Ntfy bildirimini arka planda gönder
                try: 
                    import requests
                    requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=f"Alarm: {not_txt}".encode("utf-8"))
                except: pass
                st.rerun()

        df_alarm = df[df["Tip"] == "ALARM"]
        if not df_alarm.empty:
            st.subheader("Aktif Alarmlar")
            simdi = datetime.now()
            for i, row in df_alarm.iterrows():
                try:
                    hedef = datetime.strptime(row["Zaman"], "%Y-%m-%d %H:%M:%S")
                    kalan = (hedef - simdi).total_seconds()
                    
                    c1, c2 = st.columns([0.8, 0.2])
                    with c1:
                        st.write(f"⏰ **{row['Mesaj']}**")
                        if kalan > 0: st.caption(f"Kalan: {int(kalan/60)} dk")
                        else: st.error("SÜRE DOLDU!")
                    with c2:
                        if st.button("Kapat", key=f"al_off_{i}"): islem_yap("sil", urun=row["Urun"]); st.rerun()
                    st.divider()
                except: pass

def sayfa_ekonomi():
    st.subheader("💰 Hane Ekonomisi")
    tab1, tab2 = st.tabs(["GELİR/GİDER", "YATIRIMLAR"])
    
    with tab1:
        c1, c2, c3 = st.columns([2, 1, 1], vertical_alignment="bottom")
        with c1: aciklama = st.text_input("İşlem", placeholder="Market, Maaş...")
        with c2: tutar = st.number_input("Tutar", min_value=0.0, step=50.0)
        with c3: 
            tur = st.selectbox("Tür", ["Gider", "Gelir"], label_visibility="collapsed")
        
        if st.button("KAYDET", use_container_width=True, key="btn_eco_save"):
            if aciklama and tutar > 0:
                islem_yap("ekle", urun=aciklama, tip="BUTCE", mesaj=str(tutar), durum=tur, zaman=datetime.now().strftime("%Y-%m-%d"))
                st.rerun()
                
        # Özet Gösterimi
        df_b = st.session_state.local_df[st.session_state.local_df["Tip"] == "BUTCE"]
        if not df_b.empty:
            df_b["Tutar_Sayi"] = pd.to_numeric(df_b["Mesaj"], errors='coerce').fillna(0)
            toplam_gelir = df_b[df_b["Durum"]=="Gelir"]["Tutar_Sayi"].sum()
            toplam_gider = df_b[df_b["Durum"]=="Gider"]["Tutar_Sayi"].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Gelir", f"{toplam_gelir:,.0f} ₺", delta_color="normal")
            c2.metric("Gider", f"{toplam_gider:,.0f} ₺", delta="-", delta_color="inverse")
            c3.metric("Kalan", f"{toplam_gelir - toplam_gider:,.0f} ₺")
            
            st.dataframe(df_b[["Zaman", "Urun", "Mesaj", "Durum"]], use_container_width=True, hide_index=True)

    with tab2:
        if GRAFIK_VAR:
            df_y = st.session_state.local_df[st.session_state.local_df["Tip"] == "YATIRIM"]
            if not df_y.empty:
                df_y["Deger"] = pd.to_numeric(df_y["Mesaj"], errors='coerce').fillna(0)
                fig = px.pie(df_y, values='Deger', names='Urun', title='Varlık Dağılımı', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Henüz yatırım eklemediniz.")
        else:
            st.warning("Grafikler için 'plotly' kütüphanesi gerekli.")

def sayfa_yemek():
    st.subheader("🍽️ Ne Yesek?")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🎲 Akşam Yemeği Çarkı", type="primary", use_container_width=True):
            df_y = st.session_state.local_df[st.session_state.local_df["Tip"] == "YEMEK_OGUN"]
            havuz = df_y["Urun"].tolist()
            if havuz:
                secilen = random.choice(havuz)
                st.balloons()
                st.success(f"Akşama Menüde: **{secilen}** var!")
            else:
                st.error("Listede yemek yok, önce ekleyin!")
                
    with col2:
        if st.button("🍳 Kahvaltı Çarkı", use_container_width=True):
            st.toast("Sucuklu Yumurta iyi gider!", icon="🍳")

    # AI Şef Bölümü
    st.markdown("---")
    with st.expander("👨‍🍳 AI Mutfak Asistanı", expanded=True):
        malzemeler = st.multiselect("Evdeki Malzemeler", ["Yumurta", "Patates", "Kıyma", "Tavuk", "Makarna", "Domates", "Peynir"])
        if st.button("Tarif Öner", use_container_width=True):
            if not malzemeler:
                st.warning("Malzeme seçmelisin.")
            else:
                st.info("AI Şef düşünüyor...")
                time.sleep(1)
                # Basit bir öneri mantığı
                if "Kıyma" in malzemeler and "Patates" in malzemeler: st.success("💡 Öneri: **Köfte Patates** veya **Oturtma**")
                elif "Yumurta" in malzemeler and "Domates" in malzemeler: st.success("💡 Öneri: **Menemen**")
                elif "Makarna" in malzemeler: st.success("💡 Öneri: **Soslu Makarna**")
                else: st.success(f"💡 Öneri: **{malzemeler[0]} ile uydurmasyon bir tava yemeği** yapabilirsin!")

# ==============================================================================
# 🚀 UYGULAMA BAŞLATICI
# ==============================================================================

# Sidebar Menü
with st.sidebar:
    st.title("🏡 Ev Asistanı")
    st.caption("v2.0 Pro")
    menu = st.radio("Menü", ["Ana Ekran", "Ekonomi", "Yemek & Mutfak", "Ayarlar"])
    st.markdown("---")
    st.info(f"Mod: {'🟢 Online' if ONLINE_MOD else '🔴 Offline'}")

# Sayfa Yönlendirme
karsilama_paneli()

if menu == "Ana Ekran":
    sayfa_ana_ekran()
elif menu == "Ekonomi":
    sayfa_ekonomi()
elif menu == "Yemek & Mutfak":
    sayfa_yemek()
elif menu == "Ayarlar":
    st.subheader("⚙️ Sistem Ayarları")
    if st.button("Veritabanını Temizle (Gereksizleri Sil)"):
        islem_yap("temizle")
    
    st.markdown("### Hakkında")
    st.caption("Geliştirici: Evin Mühendisi")
    st.caption("Veri Kaynağı: Google Sheets" if ONLINE_MOD else "Yerel Bellek")
