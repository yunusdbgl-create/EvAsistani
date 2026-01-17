import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
from datetime import datetime, timedelta, time as dt_time
import threading
import random
import plotly.express as px  # Grafik kütüphanesi (Opsiyonel ama önerilir)

# ==============================================================================
# 1. AYARLAR VE SAYFA YAPILANDIRMASI
# ==============================================================================
st.set_page_config(page_title="Bizim Evin Paneli v2", page_icon="🏡", layout="centered", initial_sidebar_state="collapsed")

DOSYA_ADI = "EvAsistaniDB"
NTFY_TOPIC = "yunus_ozel_ev_kanali_123"

# --- MODERN CSS & STİL ---
st.markdown("""
<style>
    /* Genel Düzen */
    .block-container { padding-top: 2rem; padding-bottom: 5rem; }
    div[data-testid="stHorizontalBlock"] { gap: 10px !important; }
    button { border-radius: 8px !important; transition: all 0.2s ease-in-out; }
    button:hover { transform: scale(1.02); }
    
    /* Kart Tasarımları */
    .info-card {
        background-color: #f0f2f6; border-radius: 10px; padding: 15px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05); margin-bottom: 10px;
    }
    .crypto-ticker {
        font-family: 'Courier New', monospace; color: #2ecc71; font-weight: bold; font-size: 14px;
        background: #1e1e1e; padding: 8px; border-radius: 5px; text-align: center;
    }
    
    /* Prenses & Karşılama */
    .prenses-box {
        background: linear-gradient(135deg, #FF9A9E 0%, #FECFEF 100%);
        color: #5d2e46; padding: 20px; border-radius: 15px; text-align: center;
        border: 2px solid #fff; box-shadow: 0 4px 15px rgba(255, 154, 158, 0.4);
    }
    .stoic-box {
        background: linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%);
        color: #2c3e50; padding: 15px; border-radius: 12px; text-align: center; font-style: italic;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. VERİTABANI BAĞLANTISI (CACHED - HIZLANDIRILMIŞ)
# ==============================================================================
@st.cache_resource
def get_google_sheet_client():
    """Google Sheets bağlantısını önbelleğe alır, her işlemde tekrar bağlanmaz."""
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(dict(st.secrets["connections"]["gsheets"]), scopes=scopes)
    return gspread.authorize(creds)

def get_sheet():
    try:
        return get_google_sheet_client().open(DOSYA_ADI).sheet1
    except Exception as e:
        st.error(f"Veritabanı Bağlantı Hatası: {e}")
        return None

# ==============================================================================
# 3. İŞ MANTIĞI & CRUD (ARKA PLAN)
# ==============================================================================
def sync_to_sheet(action, data):
    """
    Tüm yazma işlemleri buradan geçer.
    action: 'append', 'delete', 'update', 'update_cell'
    """
    sheet = get_sheet()
    if not sheet: return

    try:
        if action == 'append':
            sheet.append_row(data)
        elif action == 'delete':
            # Hücre aramayı optimize et
            cell = sheet.find(data[0])
            if cell: sheet.delete_rows(cell.row)
        elif action == 'update_status':
            cell = sheet.find(data[0])
            if cell: sheet.update_cell(cell.row, 2, str(data[1]))
    except Exception as e:
        print(f"Sync Error: {e}")

def verileri_yukle():
    sheet = get_sheet()
    if not sheet: return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman", "Tip"])
    
    try:
        data = sheet.get_all_values()
        if not data: return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman", "Tip"])
        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    except:
        return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman", "Tip"])

# Session State Başlatma
if 'local_df' not in st.session_state:
    st.session_state.local_df = verileri_yukle()

# --- OPTİMİSTİK UI GÜNCELLEMELERİ ---
def hizli_islem(tur, *args):
    """Arayüzü anında günceller, veritabanını arkadan senkronize eder."""
    df = st.session_state.local_df
    
    if tur == "EKLE":
        isim, tip, mesaj, zaman, durum = args
        # Mükerrer kontrolü (Market/Yemek için)
        if tip in ["MARKET", "YEMEK_OGUN"] and not df[df["Urun"] == isim].empty:
            st.toast(f"⚠️ {isim} zaten listede var!"); return

        yeni_satir = {"Urun": isim, "Durum": durum, "Mesaj": mesaj, "Zaman": zaman, "Tip": tip}
        st.session_state.local_df = pd.concat([df, pd.DataFrame([yeni_satir])], ignore_index=True)
        threading.Thread(target=sync_to_sheet, args=('append', [isim, durum, mesaj, zaman, tip])).start()
        st.toast(f"✅ Eklendi: {isim}")

    elif tur == "SIL":
        isim = args[0]
        st.session_state.local_df = df[df["Urun"] != isim]
        threading.Thread(target=sync_to_sheet, args=('delete', [isim])).start()

    elif tur == "DURUM":
        isim, yeni_durum = args
        idx = df[df["Urun"] == isim].index
        if not idx.empty:
            st.session_state.local_df.at[idx[0], "Durum"] = str(yeni_durum)
            threading.Thread(target=sync_to_sheet, args=('update_status', [isim, yeni_durum])).start()
            if yeni_durum == "1" and "MARKET" in df.loc[idx[0], "Tip"]: st.toast("Sepete atıldı! 🛒")

# ==============================================================================
# 4. KİŞİSELLEŞTİRİLMİŞ MODÜLLER (STOA, KRİPTO, PRENSES)
# ==============================================================================
def get_crypto_prices():
    """Basit Kripto Fiyat Çekici (CoinGecko API)"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,tether&vs_currencies=try,usd"
        r = requests.get(url, timeout=2).json()
        btc = r['bitcoin']['usd']
        eth = r['ethereum']['usd']
        return f"₿ BTC: ${btc:,.0f} | Ξ ETH: ${eth:,.0f}"
    except:
        return "Kripto verisi alınamadı"

def get_motivation_quote():
    quotes = [
        "Sabah uyandığında hayatta olmanın, düşünmenin, keyif almanın ve sevmenin ne büyük bir ayrıcalık olduğunu düşün. - M. Aurelius",
        "Engelin kendisi, yolun kendisidir.",
        "Dışarıda ne olursa olsun, içindeki huzur kalesi senin kontrolündedir.",
        "Zorluklar, zihni güçlendirmek içindir; tıpkı çalışmanın bedeni güçlendirdiği gibi - Seneca",
        "Bugün, dünden daha iyi bir sen ol.",
        "Seninle her şey daha güzel, iyi ki varsın.", # Romantik karışık
        "Nöbetin ne kadar zor olursa olsun, evin senin sığınağın."
    ]
    return random.choice(quotes)

def karsilama_paneli():
    # Üst Bilgi Çubuğu (Kripto & Tarih)
    col_l, col_r = st.columns([0.6, 0.4])
    with col_l: st.caption(f"📅 {datetime.now().strftime('%d %B %A')}")
    with col_r: st.markdown(f"<div class='crypto-ticker'>{get_crypto_prices()}</div>", unsafe_allow_html=True)

    # %20 İhtimalle Prenses Konuşur
    if random.random() < 0.20:
        prenses_sozleri = [
            "🐈 Mırmır/Prenses: Mama kabım neden tam dolu değil?",
            "🐈 Bugün çok yoruldunuz, gelin size mırlayayım.",
            "🐈 Evi ben yönetiyorum, siz sadece yaşıyorsunuz.",
            "🐈 Nöbetten mi geldin? Üzerin hastane kokuyor, hemen değiş!"
        ]
        st.markdown(f'<div class="prenses-box"><h3>🐾 MİYAV!</h3><p>{random.choice(prenses_sozleri)}</p></div>', unsafe_allow_html=True)
    else:
        # Stoik/Romantik Karşılama
        saat = datetime.now().hour
        selam = "Günaydın" if 5<=saat<12 else "Tünaydın" if 12<=saat<18 else "İyi Akşamlar"
        quote = get_motivation_quote()
        st.info(f"👋 **{selam} Doktorum!**\n\n_{quote}_")

# ==============================================================================
# 5. SAYFALAR
# ==============================================================================

def sayfa_market():
    st.subheader("🛒 Market & İhtiyaçlar")
    
    # Hızlı Ekleme Alanı
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: urun = st.text_input("Hızlı Ekle", placeholder="Süt, Ekmek...", key="market_input", label_visibility="collapsed")
    with c2: kat = st.selectbox("Kategori", ["Genel", "Kahvaltılık", "Sebze/Meyve", "Temizlik", "Atıştırmalık"], label_visibility="collapsed")
    with c3: 
        if st.button("➕ Ekle", use_container_width=True):
            if urun: 
                hizli_islem("EKLE", urun, "MARKET", kat, "", "0")
                st.rerun()

    # Listeleme (Kart Görünümü)
    df = st.session_state.local_df
    alinacaklar = df[(df["Tip"] == "MARKET") & (df["Durum"] == "0")]
    
    if alinacaklar.empty:
        st.success("Tüm eksikler tamam! 🎉")
    else:
        # Kategorilere göre grupla
        kategoriler = alinacaklar["Mesaj"].unique()
        for k in kategoriler:
            with st.expander(f"📦 {k} ({len(alinacaklar[alinacaklar['Mesaj']==k])})", expanded=True):
                for i, row in alinacaklar[alinacaklar['Mesaj']==k].iterrows():
                    col_text, col_act = st.columns([0.8, 0.2])
                    with col_text: st.markdown(f"**{row['Urun']}**")
                    with col_act: 
                        if st.button("✅", key=f"ok_{i}"): 
                            hizli_islem("DURUM", row['Urun'], "1")
                            st.rerun()

def sayfa_ekonomi():
    st.subheader("💰 Bütçe & Yatırım")
    
    # Bakiye Özeti (Basit Dashboard)
    df = st.session_state.local_df
    df_butce = df[df["Tip"] == "BUTCE"]
    
    # Bu ayki hesaplamalar
    bu_ay = datetime.now().strftime("%Y-%m")
    df_aylik = df_butce[pd.to_datetime(df_butce["Zaman"], errors='coerce').dt.strftime('%Y-%m') == bu_ay]
    
    gelir = pd.to_numeric(df_aylik[df_aylik["Durum"]=="Gelir"]["Mesaj"], errors='coerce').sum()
    gider = pd.to_numeric(df_aylik[df_aylik["Durum"]=="Gider"]["Mesaj"], errors='coerce').sum()
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Gelir", f"{gelir:,.0f} ₺", delta_color="normal")
    k2.metric("Gider", f"{gider:,.0f} ₺", delta_color="inverse")
    k3.metric("Kalan", f"{gelir-gider:,.0f} ₺", delta=f"%{int((gelir-gider)/gelir*100) if gelir>0 else 0} Tasarruf")
    
    st.markdown("---")
    
    # Gelir/Gider Ekleme
    with st.expander("➕ İşlem Ekle", expanded=False):
        ec1, ec2, ec3 = st.columns([1,1,1])
        with ec1: tur = st.radio("Tip", ["Gider", "Gelir"], horizontal=True)
        with ec2: aciklama = st.text_input("Açıklama", placeholder="Market, Kira...")
        with ec3: tutar = st.number_input("Tutar", min_value=0.0, step=100.0)
        
        if st.button("Kaydet", key="btn_eko_save", use_container_width=True):
            if tutar > 0:
                hizli_islem("EKLE", aciklama, "BUTCE", str(tutar), datetime.now().strftime("%Y-%m-%d"), tur)
                st.rerun()

    # Kripto/Fon Portföyü (Grafikli)
    st.subheader("📈 Varlıklar & Fonlar")
    df_yatirim = df[df["Tip"] == "YATIRIM"]
    if not df_yatirim.empty:
        df_yatirim["Deger"] = pd.to_numeric(df_yatirim["Mesaj"], errors='coerce').fillna(0)
        fig = px.pie(df_yatirim, values='Deger', names='Urun', hole=0.5, color_discrete_sequence=px.colors.sequential.RdBu)
        fig.update_layout(height=250, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Henüz yatırım eklenmemiş.")

def sayfa_mutfak():
    st.subheader("👨‍🍳 Akıllı Mutfak")
    
    tab1, tab2 = st.tabs(["Ne Pişirsem?", "Yemek Çarkı"])
    
    with tab1:
        # AI Şef Mantığı
        df = st.session_state.local_df
        # Evdeki malzemeler (Market geçmişinden alınanlar)
        stoktakiler = df[(df["Tip"] == "MARKET") & (df["Durum"] == "1")]["Urun"].tolist()
        
        st.write("🧊 **Dolaptakiler:** " + ", ".join(stoktakiler[:5]) + ("..." if len(stoktakiler)>5 else ""))
        
        tarifler = {
            "Menemen": ["Yumurta", "Domates", "Biber"],
            "Makarna": ["Makarna", "Salça"],
            "Tavuk Sote": ["Tavuk", "Biber", "Soğan"],
            "Köfte Patates": ["Kıyma", "Patates"],
            "Omlet": ["Yumurta", "Peynir"]
        }
        
        if st.button("🍳 AI Şef Önerisi Getir", type="primary"):
            st.markdown("### 🍽️ Öneriler")
            bulunan = False
            for yemek, malz in tarifler.items():
                eksik = [m for m in malz if not any(m.lower() in s.lower() for s in stoktakiler)]
                if not eksik:
                    st.success(f"✅ **{yemek}** yapabilirsin! (Malzemeler tam)")
                    bulunan = True
                elif len(eksik) <= 1:
                    st.warning(f"🤔 **{yemek}** yapabilirsin ama eksik: {eksik[0]}")
                    bulunan = True
            
            if not bulunan: st.error("Eldeki malzemelerle tam bir tarif çıkmadı, basit bir makarna yapalım mı?")

    with tab2:
        if st.button("🎲 Rastgele Yemek Seç"):
            secenekler = df[df["Tip"] == "YEMEK_OGUN"]["Urun"].tolist()
            if secenekler:
                secilen = random.choice(secenekler)
                st.balloons()
                st.markdown(f"<h1 style='text-align:center; color:#e74c3c;'>{secilen}</h1>", unsafe_allow_html=True)
            else:
                st.warning("Listede yemek yok, önce eklemelisin.")

def sayfa_yasam():
    st.subheader("🧬 Yaşam & Rutinler")
    
    # Zinciri Kırma (Streak)
    st.markdown("**🏆 Günlük Rutinler**")
    rutinler = ["Su İç (2L)", "Kitap Oku (20sf)", "Vitamin Al", "Kedi ile Oyna"]
    
    cols = st.columns(len(rutinler))
    for i, rut in enumerate(rutinler):
        # Basit durum takibi (Günübirlik, DB'ye yazmaya gerek duymadan session'da tutulabilir veya DB'ye bağlanabilir)
        # Burada hız için session kullanıyoruz
        key = f"rutin_{rut}_{datetime.now().day}"
        val = st.session_state.get(key, False)
        if cols[i].checkbox(rut, value=val, key=key):
            if not val: st.toast(f"Harikasın! {rut} tamamlandı.")

    st.markdown("---")
    # Notlar & PDF Çevirici
    st.markdown("**📂 Hızlı Araçlar**")
    uploaded_file = st.file_uploader("Resmi PDF'e Çevir (Reçete/Rapor)", type=["jpg", "png"])
    if uploaded_file:
        import img2pdf
        pdf_bytes = img2pdf.convert(uploaded_file.read())
        st.download_button("⬇️ PDF İndir", pdf_bytes, file_name="belge.pdf", mime="application/pdf")

# ==============================================================================
# 6. ANA ÇALIŞTIRMA (NAVİGASYON)
# ==============================================================================
def main():
    karsilama_paneli()
    
    # Modern Alt Menü (Mobilde daha rahat kullanım için)
    secim = st.radio("", ["🏠 Ana Sayfa", "🛒 Market", "💰 Ekonomi", "👨‍🍳 Mutfak", "🧬 Yaşam"], 
                     horizontal=True, label_visibility="collapsed")

    st.markdown("---")

    if secim == "🏠 Ana Sayfa":
        # Dashboard Özeti
        c1, c2 = st.columns(2)
        with c1:
            bekleyen_is = len(st.session_state.local_df[(st.session_state.local_df["Tip"] == "MARKET") & (st.session_state.local_df["Durum"] == "0")])
            st.info(f"🛒 **{bekleyen_is}** Market Eksiği")
        with c2:
            st.success("✅ Fatura/Ödeme Yok (Sakin)") # Burası dinamikleştirilebilir

        # Hızlı Not / Hatırlatıcı
        st.text_area("📌 Hızlı Not Bırak (Eşine)", placeholder="Akşama geç geleceğim, beni bekleme...")
        
    elif secim == "🛒 Market": sayfa_market()
    elif secim == "💰 Ekonomi": sayfa_ekonomi()
    elif secim == "👨‍🍳 Mutfak": sayfa_mutfak()
    elif secim == "🧬 Yaşam": sayfa_yasam()

if __name__ == "__main__":
    main()
