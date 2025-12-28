import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
from datetime import datetime, timedelta

# ==============================================================================
# AYARLAR
# ==============================================================================
DOSYA_ADI = "EvAsistaniDB"
NTFY_TOPIC = "yunus_ozel_ev_kanali_123"

st.set_page_config(page_title="Ev Paneli", page_icon="🏠", layout="centered")

# ==============================================================================
# GOOGLE SHEETS BAĞLANTISI
# ==============================================================================
def baglanti_kur():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        creds_dict = dict(st.secrets["connections"]["gsheets"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open(DOSYA_ADI).sheet1
        return sheet
    except Exception as e:
        st.error(f"Bağlantı Hatası: {e}")
        return None

def verileri_hazirla():
    """HATA DUZELTICI FONKSIYON: Sütunlar eksikse tamamlar"""
    sheet = baglanti_kur()
    if not sheet: return pd.DataFrame()

    try:
        data = sheet.get_all_values()
        GEREKLI_BASLIKLAR = ["Urun", "Durum", "Mesaj", "Zaman", "Tip"]

        # 1. Sayfa Bomboşsa -> Başlıkları yaz
        if not data:
            sheet.append_row(GEREKLI_BASLIKLAR)
            return pd.DataFrame(columns=GEREKLI_BASLIKLAR)

        # 2. Veriyi DataFrame'e çevir
        # İlk satırı başlık kabul ediyoruz
        df = pd.DataFrame(data[1:], columns=data[0])

        # 3. EKSİK SÜTUN KONTROLÜ (Hatanın Çözümü)
        # Eğer "Durum" veya "Tip" sütunu yoksa, DataFrame içinde sanal olarak oluştur
        # Böylece uygulama çökmez.
        for col in GEREKLI_BASLIKLAR:
            if col not in df.columns:
                df[col] = "" # Eksik sütunu boşlukla doldur

        return df
    except Exception as e:
        # Çok kötü bir şey olursa boş tablo dön ki uygulama çökmesin
        return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman", "Tip"])

# ==============================================================================
# İŞLEMLER
# ==============================================================================
def urun_ekle(isim, tip):
    sheet = baglanti_kur()
    if sheet:
        # Eğer sayfa boşsa başlıkları eklemesini garantile
        if len(sheet.get_all_values()) == 0:
            sheet.append_row(["Urun", "Durum", "Mesaj", "Zaman", "Tip"])
            
        sheet.append_row([isim, "0", "", "", tip])
        st.cache_data.clear()

def urun_sil(isim):
    sheet = baglanti_kur()
    if sheet:
        try:
            cell = sheet.find(isim)
            sheet.delete_rows(cell.row)
            st.cache_data.clear()
        except: pass

def durum_degistir(isim, yeni_durum):
    sheet = baglanti_kur()
    if sheet:
        try:
            cell = sheet.find(isim)
            # Durum sütunu genelde 2. sütundur ama garanti olsun diye başlığa göre bulalım
            # Basitlik için 2. sütun varsayıyoruz (Standart yapı)
            sheet.update_cell(cell.row, 2, str(yeni_durum))
            st.cache_data.clear()
        except: pass

def alarm_ekle(mesaj, zaman):
    sheet = baglanti_kur()
    if sheet:
        sheet.append_row(["", "-1", mesaj, zaman, "ALARM"])

def bildirim_gonder(mesaj):
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", 
                      data=mesaj.encode('utf-8'),
                      headers={"Title": "Ev Asistanı".encode('utf-8'), "Priority": "high"})
    except: pass

# ==============================================================================
# YARDIMCI GÖRÜNÜM (GÜVENLİ SİLME VE LİSTELEME)
# ==============================================================================
def liste_goster(dataframe, liste_tipi):
    if dataframe.empty:
        st.info("Veri yükleniyor veya liste boş.")
        return

    # Tip filtreleme (Boş olanları MARKET say)
    if liste_tipi == "MARKET":
        df_aktif = dataframe[(dataframe["Tip"] == "MARKET") | (dataframe["Tip"] == "") | (dataframe["Tip"].isnull())]
    else:
        df_aktif = dataframe[dataframe["Tip"] == liste_tipi]

    if not df_aktif.empty:
        # Durum filtresi (String olarak '0' veya '1' kontrolü)
        alinacaklar = df_aktif[df_aktif["Durum"].astype(str) == "0"]
        tamamlananlar = df_aktif[df_aktif["Durum"].astype(str) == "1"]

        # --- BEKLEYENLER ---
        st.subheader(f"📌 Bekleyenler ({len(alinacaklar)})")
        
        if alinacaklar.empty:
            st.success("Temiz! 🎉")
        
        for index, row in alinacaklar.iterrows():
            c1, c2 = st.columns([5, 1])
            with c1:
                if st.checkbox(f"**{row['Urun']}**", key=f"chk_{liste_tipi}_{index}"):
                    durum_degistir(row['Urun'], "1")
                    st.rerun()
            with c2:
                # SİLME ONAY MEKANİZMASI
                sil_key = f"del_btn_{liste_tipi}_{index}"
                onay_key = f"confirm_{liste_tipi}_{index}"

                if not st.session_state.get(onay_key):
                    if st.button("🗑️", key=sil_key):
                        st.session_state[onay_key] = True
                        st.rerun()
                else:
                    if st.button("Sil?", key=f"yes_{sil_key}", type="primary"):
                        urun_sil(row['Urun'])
                        st.session_state[onay_key] = False
                        st.rerun()
                    st.caption("İptal: Yenile")

        st.divider()

        # --- GEÇMİŞ / TAMAMLANAN ---
        baslik = "📦 Evde Var / Geçmiş" if liste_tipi == "MARKET" else "✅ Tamamlanan İşler"
        with st.expander(f"{baslik} ({len(tamamlananlar)})"):
            if tamamlananlar.empty:
                st.caption("Boş.")
            else:
                for index, row in tamamlananlar.iterrows():
                    c_a, c_b = st.columns([4, 1])
                    with c_a:
                        if st.button(f"➕ {row['Urun']}", key=f"back_{liste_tipi}_{index}", use_container_width=True):
                            durum_degistir(row['Urun'], "0")
                            st.rerun()
                    with c_b:
                        sil_key_t = f"del_fin_{liste_tipi}_{index}"
                        onay_key_t = f"conf_fin_{liste_tipi}_{index}"
                        
                        if not st.session_state.get(onay_key_t):
                            if st.button("🗑️", key=sil_key_t):
                                st.session_state[onay_key_t] = True
                                st.rerun()
                        else:
                            if st.button("Sil?", key=f"yes_{sil_key_t}", type="primary"):
                                urun_sil(row['Urun'])
                                st.session_state[onay_key_t] = False
                                st.rerun()
    else:
        st.info("Henüz bir şey eklenmemiş.")

# ==============================================================================
# ANA EKRAN
# ==============================================================================
st.markdown("<h3 style='text-align: center;'>🏠 Yunus Hocam'ın Asistanı</h3>", unsafe_allow_html=True)

# Veriyi güvenli şekilde çek
df = verileri_hazirla()

tab1, tab2, tab3 = st.tabs(["🛒 MARKET", "📝 YAPILACAKLAR", "⏰ ALARM"])

with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        yeni_market = st.text_input("Market Ürünü", placeholder="Süt...", label_visibility="collapsed", key="in_m")
    with col2:
        if st.button("EKLE", key="btn_m", use_container_width=True):
            if yeni_market:
                urun_ekle(yeni_market, "MARKET")
                st.success("Tamam")
                time.sleep(0.5)
                st.rerun()
    st.markdown("---")
    liste_goster(df, "MARKET")

with tab2:
    col1, col2 = st.columns([3, 1])
    with col1:
        yeni_todo = st.text_input("İş Ekle", placeholder="Fatura...", label_visibility="collapsed", key="in_t")
    with col2:
        if st.button("EKLE", key="btn_t", use_container_width=True):
            if yeni_todo:
                urun_ekle(yeni_todo, "TODO")
                st.success("Tamam")
                time.sleep(0.5)
                st.rerun()
    st.markdown("---")
    liste_goster(df, "TODO")

with tab3:
    with st.form("alarm"):
        mesaj = st.text_input("Not", placeholder="Fırın...")
        sure = st.number_input("Dakika", min_value=1, value=15)
        if st.form_submit_button("🔔 Kur", use_container_width=True):
            hedef = datetime.now() + timedelta(minutes=sure)
            alarm_ekle(mesaj, hedef.strftime("%Y-%m-%d %H:%M:%S"))
            bildirim_gonder(f"✅ Alarm: {sure} dk sonra '{mesaj}'")
            st.success("Kuruldu!")
