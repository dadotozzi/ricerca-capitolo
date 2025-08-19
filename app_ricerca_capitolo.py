
import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ricerca Capitolo di Bilancio", page_icon="📑", layout="wide")

st.title("📑 Assistente Ricerca Capitolo di Bilancio")

st.markdown("""
Seleziona i filtri nella sidebar (a cascata) e cerca nel testo. 
Puoi esportare i risultati o selezionare **una riga** per ottenere i valori da incollare nel tuo Excel.
""")

# --- Sidebar: Caricamento file e filtri ---
st.sidebar.header("📥 Dati")
uploaded = st.sidebar.file_uploader("Carica Excel dati di bilancio", type=["xlsx"])

@st.cache_data
def load_excel(file):
    if file is None:
        # percorso di default dove prevediamo il file
        import os
        # Prefer local file in working dir, fallback to /mnt/data
        candidates = ["DatiBilancio.xlsx", "/mnt/data/DatiBilancio.xlsx"]
        for path in candidates:
            if os.path.exists(path):
                return pd.read_excel(path)
        raise FileNotFoundError("Nessun DatiBilancio.xlsx trovato in repository o /mnt/data")
    else:
        return pd.read_excel(file)

try:
    data = load_excel(uploaded)
except Exception as e:
    st.error(f"Errore nel caricamento del file: {e}")
    st.stop()

# Normalizza nomi colonne (togli spazi extra)
data.columns = [str(c).strip() for c in data.columns]

# Aspettative sui nomi (prova a mappare alias comuni)
aliases = {
    "Ufficio richiedente / Settore": ["Ufficio richiedente / Settore","Ufficio richiedente","Settore"],
    "Responsabile del procedimento": ["Responsabile del procedimento","Responsabile"],
    "Codice Univoco": ["Codice Univoco","Codice univoco"],
    "Capitolo di bilancio attuale": ["Capitolo di bilancio attuale","Capitolo","Capitolo bilancio"],
    "Articolo": ["Articolo"],
    "Descrizione del capitolo": ["Descrizione del capitolo","Descrizione"],
    "Tipologia di spesa": ["Tipologia di spesa","Tipologia"],
    "Stanziamento totale (2025)": ["Stanziamento totale (2025)","Stanziamento 2025","Stanziamento totale"],
    "Disponibilità residua": ["Disponibilità residua","Disponibilita residua","Disponibilità"]
}

def find_col(preferred, options):
    for opt in options:
        if opt in data.columns:
            return opt
    return None

colmap = {std: find_col(std, opts) for std, opts in aliases.items()}

missing = [k for k,v in colmap.items() if v is None]
if missing:
    st.warning("Colonne non trovate e quindi escluse dai filtri: " + ", ".join(missing))

# Helper safe getter
def col(c): 
    return colmap.get(c)

st.sidebar.header("🎛️ Filtri")

def uniq_sorted_str(series, empty_label="(Tutti)"):
    try:
        vals = series.dropna().astype(str).map(lambda s: s.strip())
    except Exception:
        vals = series.dropna().map(lambda s: str(s).strip())
    vals = [v for v in vals.unique().tolist() if v != ""]
    return [empty_label] + sorted(vals, key=lambda s: s.casefold())
# Filtri a cascata
# 1) Ufficio -> Responsabile
filtered = data.copy()

# Ufficio/Settore
if col("Ufficio richiedente / Settore"):
    uff_list = uniq_sorted_str(filtered[col("Ufficio richiedente / Settore")], empty_label="(Tutti)")
    uff = st.sidebar.selectbox("Ufficio richiedente / Settore", uff_list, index=0)
    if uff != "(Tutti)":
        filtered = filtered[filtered[col("Ufficio richiedente / Settore")] == uff]

# Responsabile (dipende da Ufficio)
if col("Responsabile del procedimento"):
    resp_list = uniq_sorted_str(filtered[col("Responsabile del procedimento")], empty_label="(Tutti)")
    resp = st.sidebar.selectbox("Responsabile del procedimento", resp_list, index=0)
    if resp != "(Tutti)":
        filtered = filtered[filtered[col("Responsabile del procedimento")] == resp]

# Tipologia di spesa
if col("Tipologia di spesa"):
    tipo_list = uniq_sorted_str(filtered[col("Tipologia di spesa")], empty_label="(Tutte)")
    tipo = st.sidebar.selectbox("Tipologia di spesa", tipo_list, index=0)
    if tipo != "(Tutte)":
        filtered = filtered[filtered[col("Tipologia di spesa")] == tipo]

# Ricerca testuale (Descrizione / Capitolo / Codice)
st.sidebar.markdown("---")
q = st.sidebar.text_input("🔎 Cerca testo", value="", placeholder="cerca in Descrizione, Capitolo, Codice...").strip()

def contains_safe(series, text):
    try:
        return series.fillna("").str.contains(text, case=False, na=False, regex=False)
    except Exception:
        return series.fillna("").astype(str).str.contains(text, case=False, na=False, regex=False)

if q:
    mask = pd.Series([False]*len(filtered))
    for cand in ["Descrizione del capitolo","Capitolo di bilancio attuale","Codice Univoco"]:
        if col(cand):
            mask = mask | contains_safe(filtered[col(cand)], q)
    filtered = filtered[mask]

st.markdown(f"**Righe trovate:** {len(filtered)}")

# Mostra tabella
filtered_display = filtered.reset_index(drop=True)
st.dataframe(filtered_display, use_container_width=True, hide_index=False)

# Selezione singola riga
st.markdown("---")
st.subheader("🧩 Seleziona riga per compilare il tuo Excel")
if len(filtered) == 0:
    st.info("Nessuna riga da selezionare.")
else:
    # scegli una riga per indice visualizzato
    # creiamo una lista di etichette utili
    def row_label(r):
        desc = col('Descrizione del capitolo')
        cap = col('Capitolo di bilancio attuale')
        cu = col('Codice Univoco')
        parts = []
        if cap: parts.append(f"Capitolo: {r[cap]}")
        if cu: parts.append(f"Codice: {r[cu]}")
        if desc: parts.append(f"Desc: {str(r[desc])[:60]}")
        return " | ".join(parts)

    # costruiamo la mapping index -> label
    labels = {int(i): row_label(r) for i, r in filtered_display.iterrows()}
    idx_options = ["(Nessuna)"] + [f"{i}" for i in labels.keys()]
    chosen = st.selectbox("Scegli una riga (per indice)", idx_options, index=0)
    if chosen != "(Nessuna)":
        ridx = int(chosen)
        row = filtered_display.loc[ridx:ridx].copy()
        st.write("**Riga selezionata:**")
        st.dataframe(row, use_container_width=True)

        # Esporta la riga
        c1, c2 = st.columns(2)
        csv_bytes = row.to_csv(index=False).encode("utf-8")
        c1.download_button("⬇️ Scarica riga (CSV)", csv_bytes, "riga_scelta.csv", "text/csv")

        # Excel one-line
        import io
        import xlsxwriter
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            row.to_excel(writer, sheet_name="Riga", index=False)
        c2.download_button("⬇️ Scarica riga (XLSX)", output.getvalue(), "riga_scelta.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


st.markdown("---")
st.subheader("📝 Richiesta di variazione")

# Archivio richieste: carica opzionale e session state
st.sidebar.markdown("---")
st.sidebar.header("📚 Archivio richieste")
req_upload = st.sidebar.file_uploader("Carica richieste esistenti (CSV/XLSX)", type=["csv","xlsx"], key="req_upload")

import io
def load_requests(file):
    if file is None:
        return pd.DataFrame()
    name = getattr(file, "name", "").lower()
    try:
        if name.endswith(".csv"):
            return pd.read_csv(file)
        else:
            return pd.read_excel(file)
    except Exception as e:
        st.sidebar.error(f"Errore caricamento richieste: {e}")
        return pd.DataFrame()

if "requests_df" not in st.session_state:
    st.session_state.requests_df = load_requests(req_upload)
else:
    # se l'utente carica un file ora, sostituiamo
    if req_upload is not None and st.sidebar.button("↪️ Sostituisci con file caricato"):
        st.session_state.requests_df = load_requests(req_upload)

requests_df = st.session_state.requests_df

# Selezione riga requisito: serve una riga selezionata per precompilare
if len(filtered) == 0:
    st.info("Filtra e seleziona una riga dalla tabella per precompilare la richiesta.")
else:
    if 'ridx' not in locals():
        st.info("Seleziona una riga qui sopra per creare la richiesta.")
    else:
        # Sicurezza: se 'row' non è definita perché l'utente non ha confermato la selectbox
        try:
            _ = row.copy()
        except NameError:
            row = pd.DataFrame()
        
        if not row.empty:
            # Estrai valori base
            def val(colname): 
                c = col(colname)
                if c and c in row.columns:
                    return row.iloc[0][c]
                return ""
            uff_val = val("Ufficio richiedente / Settore")
            resp_val = val("Responsabile del procedimento")
            cod_val = val("Codice Univoco")
            cap_val = val("Capitolo di bilancio attuale")
            art_val = val("Articolo")
            desc_val = val("Descrizione del capitolo")
            tipo_val = val("Tipologia di spesa")
            stanziamento_val = val("Stanziamento totale (2025)")
            disp_val = val("Disponibilità residua")

            with st.form("form_variazione", clear_on_submit=False):
                st.markdown("**Dati selezionati dal capitolo**")
                cA, cB, cC = st.columns([1,1,2])
                with cA:
                    st.text_input("Ufficio richiedente / Settore", value=str(uff_val), key="f_uff", disabled=True)
                    st.text_input("Responsabile del procedimento", value=str(resp_val), key="f_resp", disabled=True)
                    st.text_input("Codice Univoco", value=str(cod_val), key="f_cod", disabled=True)
                with cB:
                    st.text_input("Capitolo di bilancio attuale", value=str(cap_val), key="f_cap", disabled=True)
                    st.text_input("Articolo", value=str(art_val), key="f_art", disabled=True)
                    st.text_input("Tipologia di spesa", value=str(tipo_val), key="f_tipo", disabled=True)
                with cC:
                    st.text_area("Descrizione del capitolo", value=str(desc_val), key="f_desc", height=80, disabled=True)
                    st.text_input("Stanziamento totale (2025)", value=str(stanziamento_val), key="f_stan", disabled=True)
                    st.text_input("Disponibilità residua", value=str(disp_val), key="f_disp", disabled=True)

                st.markdown("**Compila la richiesta**")
                d1, d2, d3, d4 = st.columns([1,1,1,2])
                with d1:
                    anno = st.number_input("Anno", min_value=2025, max_value=2030, value=2025, step=1, key="f_anno")
                with d2:
                    segno = st.selectbox("Variazione", ["Aumento (+)", "Riduzione (-)"], index=0, key="f_segno")
                with d3:
                    importo = st.number_input("Importo variazione", min_value=0.0, step=100.0, format="%.2f", key="f_importo")
                with d4:
                    richiedente = st.text_input("Richiedente (nome/cognome)", key="f_richiedente")

                oggetto = st.text_input("Oggetto della richiesta", key="f_oggetto", placeholder="Es. Manutenzione straordinaria ...")
                motivazione = st.text_area("Motivazione / Note", key="f_motiv", placeholder="Breve motivazione, riferimenti, ecc.", height=80)
                data_richiesta = st.date_input("Data richiesta", key="f_data")

                warn = None
                # Validazione disponibilità (solo se ha senso con il dato numerico)
                try:
                    disp_num = float(str(disp_val).replace(",", ".").split()[0])
                    if segno == "Aumento (+)" and importo > disp_num:
                        warn = f"Importo richiesto ({importo:,.2f}) superiore alla disponibilità residua stimata ({disp_num:,.2f})."
                except Exception:
                    pass

                if warn:
                    st.warning(warn)

                submitted = st.form_submit_button("➕ Aggiungi richiesta")
                if submitted:
                    # costruisci record
                    new_req = {
                        "Anno": anno,
                        "Variazione": segno,
                        "Importo": importo,
                        "Oggetto": oggetto,
                        "Motivazione": motivazione,
                        "Data richiesta": str(data_richiesta),
                        "Richiedente": richiedente,
                        # Dati capitolo
                        "Ufficio richiedente / Settore": str(uff_val),
                        "Responsabile del procedimento": str(resp_val),
                        "Codice Univoco": str(cod_val),
                        "Capitolo di bilancio attuale": str(cap_val),
                        "Articolo": str(art_val),
                        "Descrizione del capitolo": str(desc_val),
                        "Tipologia di spesa": str(tipo_val),
                        "Stanziamento totale (2025)": stanziamento_val,
                        "Disponibilità residua": disp_val,
                    }
                    st.session_state.requests_df = pd.concat([st.session_state.requests_df, pd.DataFrame([new_req])], ignore_index=True)
                    st.success("Richiesta aggiunta all'archivio temporaneo.")

# Tabella richieste + azioni
st.markdown("---")
st.subheader("📦 Archivio richieste (sessione corrente)")
req_df = st.session_state.requests_df
if req_df.empty:
    st.info("Nessuna richiesta registrata.")
else:
    # Mostra tabella e consentire cancellazione di righe
    st.dataframe(req_df, use_container_width=True, hide_index=False)
    # Elimina ultima o tutte
    c1, c2, c3 = st.columns(3)
    if c1.button("❌ Elimina ultima riga"):
        st.session_state.requests_df = st.session_state.requests_df.iloc[:-1, :]
    if c2.button("🧹 Svuota tutto"):
        st.session_state.requests_df = pd.DataFrame()
    # Esporta
    st.markdown("#### 📤 Esporta tutte le richieste")
    csv_all = st.session_state.requests_df.to_csv(index=False).encode("utf-8")
    st.download_button("Scarica CSV", csv_all, "richieste_variazione.csv", "text/csv")
    try:
        import xlsxwriter
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
            st.session_state.requests_df.to_excel(writer, index=False, sheet_name="Richieste")
            # formattazione basilare
            wb = writer.book
            ws = writer.sheets["Richieste"]
            # freeze first row
            ws.freeze_panes(1, 0)
            # auto width
            for i, colname in enumerate(st.session_state.requests_df.columns):
                maxlen = max( len(str(colname)), *(len(str(v)) for v in st.session_state.requests_df[colname].head(200)) )
                ws.set_column(i, i, min(maxlen + 2, 50))
        st.download_button("Scarica XLSX", out.getvalue(), "richieste_variazione.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        st.info("Per esportare in Excel assicurati di avere xlsxwriter installato: `pip install xlsxwriter`")

st.markdown("---")
with st.expander("ℹ️ Note"):
    st.markdown("""
    - I filtri sono **a cascata**: *Responsabile* dipende dall'*Ufficio*, ecc.
    - La **ricerca testo** guarda in *Descrizione*, *Capitolo* e *Codice*.
    - Puoi caricare un tuo Excel dalla sidebar; in assenza, l'app usa automaticamente `DatiBilancio.xlsx`.
    - Se i nomi delle colonne nel tuo file sono leggermente diversi, l'app prova a riconoscerli con alias comuni.
    """)
