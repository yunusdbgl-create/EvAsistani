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
    """Tabloyu çeker, yeni sütun (Tip) yoksa ekler"""
    sheet = baglanti_kur()
    if not sheet: return pd.DataFrame()

    try:
        data = sheet.get_all_values()
        
        # Sayfa boşsa başlıkları kur
        if not data:
            basliklar = ["Urun", "Durum", "Mesaj", "Zaman", "Tip"]
            sheet.append_row(basliklar)
            return pd.DataFrame(columns=basliklar)

        # Başlık kontrolü
        headers = data[0]
        if "Tip" not in headers:
            # Eski versiyondan geçiş: Tip sütunu ekle
            sheet.update_cell(1, 5, "Tip") # E1 hücresi
            # Var olan tüm satırlara 'MARKET' yaz
            if len(data) > 1:
                # Toplu güncelleme yapmak yerine boş bırakalım, kod 'MARKET' saysın
                pass
            data = sheet.get_all_values() # Tekrar çek

        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    except:
        return pd.DataFrame()

# ==============================================================================
# İŞLEMLER
# ==============================================================================
def urun_ekle(isim, tip):
    """Tip: MARKET veya TODO"""
    sheet = baglanti_kur()
    if sheet:
        # Urun, Durum(0), Mesaj, Zaman, Tip
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
# YARDIMCI GÖRÜNÜM FONKSİYONU (LİSTELEYİCİ)
# ==============================================================================
def liste_goster(dataframe, liste_tipi):
    """Market ve Yapılacaklar için ortak görünüm fonksiyonu"""
    # İlgili tipi filtrele (Tip sütunu boşsa Market say)
    if liste_tipi == "MARKET":
        df_aktif = dataframe[(dataframe["Tip"] == "MARKET") | (dataframe["Tip"] == "") | (dataframe["Tip"].isnull())]
    else:
        df_aktif = dataframe[dataframe["Tip"] == liste_tipi]

    if not df_aktif.empty:
        alinacaklar = df_aktif[df_aktif["Durum"] == "0"]
        tamamlananlar = df_aktif[df_aktif["Durum"] == "1"]

        # --- AKTİF LİSTE ---
        st.subheader(f"📌 Bekleyenler ({len(alinacaklar)})")
        
        if alinacaklar.empty:
            st.success("Liste tertemiz! 🎉")
        
        for index, row in alinacaklar.iterrows():
            c1, c2 = st.columns([5, 1])
            with c1:
                # Checkbox
                if st.checkbox(f"**{row['Urun']}**", key=f"chk_{liste_tipi}_{index}"):
                    durum_degistir(row['Urun'], "1")
                    st.rerun()
            with c2:
                # SİLME ONAY MEKANİZMASI
                sil_key = f"del_btn_{liste_tipi}_{index}"
                onay_key = f"confirm_{liste_tipi}_{index}"

                # Eğer onay butonuna basılmadıysa çöp kutusunu göster
                if not st.session_state.get(onay_key):
                    if st.button("🗑️", key=sil_key):
                        st.session_state[onay_key] = True
                        st.rerun()
                else:
                    # Onay modundaysa kırmızı buton göster
                    if st.button("Sil?", key=f"yes_{sil_key}", type="primary"):
                        urun_sil(row['Urun'])
                        st.session_state[onay_key] = False # Sıfırla
                        st.rerun()
                    # Vazgeçmek için sayfayı yenileyebilir veya boş bir yere tıklayabilir (Basit tuttum)
                    st.caption("İptal: Sayfayı yenile")

        st.divider()

        # --- TAMAMLANANLAR ---
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
                        # Burada da silme onayı olsun
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
# ANA ARAYÜZ
# ==============================================================================
st.markdown("<h3 style='text-align: center;'>🏠 Yunus Hocam'ın Asistanı</h3>", unsafe_allow_html=True)

df = verileri_hazirla()

# 3 SEKME YAPTIK
tab1, tab2, tab3 = st.tabs(["🛒 MARKET", "📝 YAPILACAKLAR", "⏰ ALARM"])

# --- TAB 1: MARKET ---
with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        yeni_market = st.text_input("Market Ürünü Ekle", placeholder="Süt, Ekmek...", label_visibility="collapsed", key="input_market")
    with col2:
        if st.button("EKLE", key="btn_add_market", use_container_width=True):
            if yeni_market:
                urun_ekle(yeni_market, "MARKET")
                st.success("Eklendi")
                time.sleep(0.5)
                st.rerun()
    
    st.markdown("---")
    liste_goster(df, "MARKET")

# --- TAB 2: YAPILACAKLAR (YENİ!) ---
with tab2:
    col1, col2 = st.columns([3, 1])
    with col1:
        yeni_todo = st.text_input("İş Ekle", placeholder="Fatura öde, Arabayı yıka...", label_visibility="collapsed", key="input_todo")
    with col2:
        if st.button("EKLE", key="btn_add_todo", use_container_width=True):
            if yeni_todo:
                urun_ekle(yeni_todo, "TODO")
                st.success("Eklendi")
                time.sleep(0.5)
                st.rerun()
    
    st.markdown("---")
    liste_goster(df, "TODO")

# --- TAB 3: ALARM ---
with tab3:
    st.info("Süre dolunca bildirim gelir.")
    with st.form("alarm_form"):
        mesaj = st.text_input("Not", placeholder="Fırını kapat")
        sure = st.number_input("Dakika", min_value=1, value=15)
        
        if st.form_submit_button("🔔 Alarmı Kur", use_container_width=True):
            hedef = datetime.now() + timedelta(minutes=sure)
            hedef_str = hedef.strftime("%Y-%m-%d %H:%M:%S")
            alarm_ekle(mesaj, hedef_str)
            bildirim_gonder(f"✅ Alarm kuruldu: {sure} dk sonra '{mesaj}'")
            st.success("Kaydedildi!")
