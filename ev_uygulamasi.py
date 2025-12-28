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
# BAĞLANTI VE VERİ HAZIRLAMA (EN SAĞLAM YAPI)
# ==============================================================================
def baglanti_kur():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
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
    sheet = baglanti_kur()
    if not sheet: return pd.DataFrame()

    try:
        data = sheet.get_all_values()
        BASLIKLAR = ["Urun", "Durum", "Mesaj", "Zaman", "Tip"]
        
        # 1. Sayfa Boşsa -> Başlıkları yaz ve boş dön
        if not data:
            sheet.append_row(BASLIKLAR)
            return pd.DataFrame(columns=BASLIKLAR)

        # 2. Başlık Kontrolü (Excel'in ilk satırı bozuksa düzeltir)
        ilk_satir = data[0]
        if ilk_satir != BASLIKLAR:
            # Eğer ilk satır başlık değilse (veri ise), başlık satırını en tepeye ekle
            if "Urun" not in ilk_satir:
                sheet.insert_row(BASLIKLAR, 1)
                data = sheet.get_all_values() # Yeniden çek
            
        # 3. Veriyi DataFrame'e çevir
        df = pd.DataFrame(data[1:], columns=data[0])

        # 4. TEMİZLİK (Sütun eksikse ekle, veriler string olsun)
        for col in BASLIKLAR:
            if col not in df.columns:
                df[col] = ""
        
        # Tüm verileri yazıya (string) çevir ki filtreleme hatası olmasın
        df = df.astype(str)
        
        return df
    except Exception as e:
        st.error(f"Veri Okuma Hatası: {e}")
        return pd.DataFrame(columns=["Urun", "Durum", "Mesaj", "Zaman", "Tip"])

# ==============================================================================
# İŞLEMLER
# ==============================================================================
def urun_ekle(isim, tip):
    sheet = baglanti_kur()
    if sheet:
        # Garanti olsun: Sayfa boşsa önce başlıkları bas
        if len(sheet.get_all_values()) == 0:
            sheet.append_row(["Urun", "Durum", "Mesaj", "Zaman", "Tip"])
            
        # Veriyi ekle (Her şey string olarak)
        sheet.append_row([str(isim), "0", "", "", str(tip)])
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
            sheet.update_cell(cell.row, 2, str(yeni_durum)) # 2. Sütun Durum
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
# LİSTE GÖRÜNÜMÜ
# ==============================================================================
def liste_goster(dataframe, liste_tipi):
    if dataframe.empty:
        st.info("Liste şu an boş.")
        return

    # FİLTRELEME (Burası çok önemli)
    # Tip sütunundaki boşlukları temizle ve filtrele
    # MARKET ise: Tipi 'MARKET' olanlar VEYA boş olanlar VEYA 'None' olanlar
    if liste_tipi == "MARKET":
        mask = (dataframe["Tip"] == "MARKET") | (dataframe["Tip"] == "") | (dataframe["Tip"] == "None")
        df_aktif = dataframe[mask]
    else:
        df_aktif = dataframe[dataframe["Tip"] == liste_tipi]

    if not df_aktif.empty:
        # Durum filtresi (String olarak kesinleştirildi)
        alinacaklar = df_aktif[df_aktif["Durum"] == "0"]
        tamamlananlar = df_aktif[df_aktif["Durum"] == "1"]

        # --- BEKLEYENLER ---
        st.subheader(f"📌 Bekleyenler ({len(alinacaklar)})")
        
        if alinacaklar.empty:
            st.success("Her şey tamam! ✅")
        
        for index, row in alinacaklar.iterrows():
            c1, c2 = st.columns([5, 1])
            with c1:
                # Checkbox
                if st.checkbox(f"**{row['Urun']}**", key=f"chk_{liste_tipi}_{index}"):
                    durum_degistir(row['Urun'], "1")
                    time.sleep(0.5)
                    st.rerun()
            with c2:
                # SİL BUTONU
                sil_key = f"del_{liste_tipi}_{index}"
                confirm_key = f"conf_{liste_tipi}_{index}"
                
                if not st.session_state.get(confirm_key):
                    if st.button("🗑️", key=sil_key):
                        st.session_state[confirm_key] = True
                        st.rerun()
                else:
                    if st.button("Sil?", key=f"yes_{sil_key}", type="primary"):
                        urun_sil(row['Urun'])
                        st.session_state[confirm_key] = False
                        st.rerun()
                    st.caption("İptal: Yenile")

        st.divider()

        # --- GEÇMİŞ ---
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
                            time.sleep(0.5)
                            st.rerun()
                    with c_b:
                        # Geçmişten Silme
                        del_fin_key = f"delfin_{liste_tipi}_{index}"
                        conf_fin_key = f"conffin_{liste_tipi}_{index}"
                        
                        if not st.session_state.get(conf_fin_key):
                            if st.button("🗑️", key=del_fin_key):
                                st.session_state[conf_fin_key] = True
                                st.rerun()
                        else:
                            if st.button("Sil?", key=f"yes_{del_fin_key}", type="primary"):
                                urun_sil(row['Urun'])
                                st.session_state[conf_fin_key] = False
                                st.rerun()
    else:
        st.info("Bu listeye henüz bir şey eklenmemiş.")

# ==============================================================================
# ANA EKRAN
# ==============================================================================
st.markdown("<h3 style='text-align: center;'>🏠 Yunus Hocam'ın Asistanı</h3>", unsafe_allow_html=True)

df = verileri_hazirla()

tab1, tab2, tab3 = st.tabs(["🛒 MARKET", "📝 YAPILACAKLAR", "⏰ ALARM"])

with tab1:
    c1, c2 = st.columns([3, 1])
    with c1:
        yeni_m = st.text_input("Market", placeholder="Ürün...", label_visibility="collapsed", key="in_m")
    with c2:
        if st.button("EKLE", key="btn_m", use_container_width=True):
            if yeni_m:
                urun_ekle(yeni_m, "MARKET")
                st.success("Eklendi")
                time.sleep(0.5)
                st.rerun()
    st.markdown("---")
    liste_goster(df, "MARKET")

with tab2:
    c1, c2 = st.columns([3, 1])
    with c1:
        yeni_t = st.text_input("Görev", placeholder="İş...", label_visibility="collapsed", key="in_t")
    with c2:
        if st.button("EKLE", key="btn_t", use_container_width=True):
            if yeni_t:
                urun_ekle(yeni_t, "TODO")
                st.success("Eklendi")
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

# DEBUG (HATA AYIKLAMA) BÖLÜMÜ
# Eğer hala liste gelmiyorsa, en alttaki bu kutuyu açıp veriyi görebilirsin.
with st.expander("🛠️ TEKNİK BİLGİ (Liste görünmüyorsa buraya bak)"):
    st.write("Google Sheets'ten Gelen Ham Veri:")
    st.dataframe(df)
