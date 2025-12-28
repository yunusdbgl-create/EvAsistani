import streamlit as st
import sqlite3
import requests
import time
from datetime import datetime, timedelta
import threading

# ==============================================================================
# AYARLAR
# ==============================================================================
DB_FILE = "ev_asistani.db"
NTFY_TOPIC = "yunus_ozel_ev_kanali_123" # Ntfy kanal adın

# ==============================================================================
# VERİTABANI
# ==============================================================================
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    # Durum 0: Alınacak, Durum 1: Evde Var (Arşiv)
    c.execute('''CREATE TABLE IF NOT EXISTS alisveris
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT, durum INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS hatirlatmalar
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, mesaj TEXT, zaman TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# ==============================================================================
# BİLDİRİM & ZAMANLAYICI
# ==============================================================================
def bildirim_gonder(mesaj, baslik="Ev Asistanı"):
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", 
                      data=mesaj.encode(encoding='utf-8'),
                      headers={"Title": baslik.encode(encoding='utf-8'), "Priority": "high"})
    except: pass

def zamanlayici_kontrol():
    while True:
        try:
            c = sqlite3.connect(DB_FILE)
            cur = c.cursor()
            cur.execute("SELECT id, mesaj, zaman FROM hatirlatmalar")
            hatirlatmalar = cur.fetchall()
            simdi = datetime.now()
            for h in hatirlatmalar:
                hid, mesaj, zaman_str = h
                hedef_zaman = datetime.strptime(zaman_str, "%Y-%m-%d %H:%M:%S")
                if simdi >= hedef_zaman:
                    bildirim_gonder(f"⏰ ZAMAN GELDİ: {mesaj}")
                    cur.execute("DELETE FROM hatirlatmalar WHERE id = ?", (hid,))
                    c.commit()
            c.close()
        except: pass
        time.sleep(10)

if 'zamanlayici_basladi' not in st.session_state:
    t = threading.Thread(target=zamanlayici_kontrol, daemon=True)
    t.start()
    st.session_state.zamanlayici_basladi = True

# ==============================================================================
# FONKSİYONLAR
# ==============================================================================
def durum_degistir(uid, su_anki_durum):
    """Ürünü Alınacaklar <-> Evde Var arasında taşır"""
    yeni_durum = 1 if su_anki_durum == 0 else 0
    c = conn.cursor()
    c.execute("UPDATE alisveris SET durum = ? WHERE id = ?", (yeni_durum, uid))
    conn.commit()
    st.rerun()

def urunu_tamamen_sil(uid):
    c = conn.cursor()
    c.execute("DELETE FROM alisveris WHERE id = ?", (uid,))
    conn.commit()
    st.rerun()

# ==============================================================================
# ARAYÜZ (GÖRÜNÜM)
# ==============================================================================
st.set_page_config(page_title="Ev Paneli", page_icon="🏠", layout="centered")

st.markdown("<h2 style='text-align: center;'>🏠 Evin Kontrol Paneli</h2>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🛒 MARKET LİSTESİ", "⏰ ALARM KUR"])

# --- TAB 1: AKILLI LİSTE ---
with tab1:
    # Hızlı Ekleme
    col1, col2 = st.columns([3, 1])
    with col1:
        yeni = st.text_input("Hızlı Ekle", placeholder="Ürün adı yaz...", label_visibility="collapsed")
    with col2:
        if st.button("EKLE", use_container_width=True):
            if yeni:
                c = conn.cursor()
                # Önce var mı diye bak, varsa durumunu 0 (alınacak) yap
                c.execute("SELECT id FROM alisveris WHERE item = ?", (yeni,))
                var_mi = c.fetchone()
                if var_mi:
                    c.execute("UPDATE alisveris SET durum = 0 WHERE id = ?", (var_mi[0],))
                else:
                    c.execute("INSERT INTO alisveris (item, durum) VALUES (?, 0)", (yeni,))
                conn.commit()
                st.rerun()

    st.write("---")

    # LİSTELERİ ÇEK
    c = conn.cursor()
    c.execute("SELECT id, item FROM alisveris WHERE durum = 0 ORDER BY id DESC") # Alınacaklar
    alinacaklar = c.fetchall()
    
    c.execute("SELECT id, item FROM alisveris WHERE durum = 1 ORDER BY item ASC") # Evde Var (Alfabetik)
    evde_var = c.fetchall()

    # 1. ALINACAKLAR LİSTESİ (KIRMIZI BÖLGE)
    st.subheader(f"📌 Alınacaklar ({len(alinacaklar)})")
    if not alinacaklar:
        st.success("Her şey tamam! Liste boş.")
    
    for urun in alinacaklar:
        uid, isim = urun
        # Checkbox işaretlenince 'Evde Var'a gönderir
        if st.checkbox(f"**{isim}**", value=False, key=f"chk_{uid}"):
            durum_degistir(uid, 0)

    st.write("---")

    # 2. EVDE VAR / GEÇMİŞ LİSTESİ (GRİ BÖLGE)
    # Burası "Expander" yani açılır kapanır kutu olsun, yer kaplamasın
    with st.expander(f"📦 Evde Var / Geçmiş Ürünler ({len(evde_var)})"):
        st.caption("Markete gidince tekrar yazma, buradan seç geri gelsin.")
        
        # Yan yana butonlar şeklinde gösterelim
        if evde_var:
            # Grid yapısı
            cols = st.columns(3) 
            for i, urun in enumerate(evde_var):
                uid, isim = urun
                with cols[i % 3]:
                    # Butona basınca tekrar "Alınacaklar"a çıkar
                    if st.button(f"➕ {isim}", key=f"btn_{uid}", help="Listeye geri ekle"):
                        durum_degistir(uid, 1)
        else:
            st.info("Geçmiş ürün yok.")

# --- TAB 2: HATIRLATICI ---
with tab2:
    st.info("Süre dolunca telefonuna bildirim gelir.")
    with st.form("alarm_form"):
        mesaj = st.text_input("Hatırlatma Notu", placeholder="Örn: Ocağı kapat")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            sure = st.number_input("Dakika", min_value=1, value=15)
        with col_s2:
            st.write("") 
            st.write("") 
            submitted = st.form_submit_button("🔔 Alarmı Kur", use_container_width=True)
        
        if submitted and mesaj:
            hedef = datetime.now() + timedelta(minutes=sure)
            hedef_str = hedef.strftime("%Y-%m-%d %H:%M:%S")
            c = conn.cursor()
            c.execute("INSERT INTO hatirlatmalar (mesaj, zaman) VALUES (?, ?)", (mesaj, hedef_str))
            conn.commit()
            bildirim_gonder(f"✅ Kurulu: {sure} dk sonra '{mesaj}'")
            st.success("Alarm kuruldu!")