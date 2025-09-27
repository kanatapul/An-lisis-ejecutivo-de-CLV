st.set_page_config(page_title="Análisis ejecutivo de CLV para priorización comercial", page_icon=None, layout="wide")
st.markdown(
    """
    <style>
    .block-container{padding-top:1.2rem;padding-bottom:1.5rem;max-width:1200px}
    h1,h2,h3{font-weight:600;margin-bottom:.4rem}
    .stMetric{background:#fafbfe;border:1px solid #e6e8ee;border-radius:10px;padding:10px}
    .caption{color:#5f6775}
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Análisis ejecutivo de CLV para priorización comercial")
st.caption("Propósito: identificar impulsores y segmentos de alto valor para orientar marketing, ventas y retención.")
alt.themes.enable("default")

@st.cache_data
def read_clv_csv(path: str):
    df = pd.read_csv(path, delimiter=";", dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def detect_col(df, candidates):
    cols_l = {c.lower(): c for c in df.columns}
    for cand in candidates:
        for c_l, c in cols_l.items():
            if cand in c_l:
                return c
    return None

def to_numeric_smart(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip()
    euro_pat = re.compile(r"^\d{1,3}(\.\d{3})+(,\d+)?$")
    def parse_one(x):
        if x in ("", "None", "nan", "NaN"):
            return np.nan
        if euro_pat.match(x):
            x2 = x.replace(".", "").replace(",", ".")
            try:
                return float(x2)
            except:
                return np.nan
        try:
            return float(x)
        except:
            try:
                return float(x.replace(",", ""))
            except:
                return np.nan
    return s.map(parse_one)

def qmarks(v):
    return [np.nanpercentile(v, 25), np.nanpercentile(v, 50), np.nanpercentile(v, 75)]

data_path = st.sidebar.text_input("Ruta del archivo CLV.csv", value="CLV.csv")
if not Path(data_path).exists():
    st.error("No se encontró CLV.csv. Especifica la ruta correcta en la barra lateral.")
    st.stop()

raw = read_clv_csv(data_path)

col_clv = detect_col(raw, ["customer lifetime value", "clv", "lifetime value"])
col_income = detect_col(raw, ["income"])
col_premium = detect_col(raw, ["monthly premium"])
col_claim_amt = detect_col(raw, ["total claim amount"])
col_last_claim = detect_col(raw, ["months since last claim"])
col_tenure = detect_col(raw, ["months since policy inception"])
col_open_compl = detect_col(raw, ["number of open complaints"])
col_policies = detect_col(raw, ["number of policies"])
col_channel = detect_col(raw, ["sales channel"])
col_vehicle_class = detect_col(raw, ["vehicle class"])
col_state = detect_col(raw, ["state"])
col_response = detect_col(raw, ["response"])
col_coverage = detect_col(raw, ["coverage"])
col_education = detect_col(raw, ["education"])

df = raw.copy()
if col_clv is not None:
    df[col_clv + " (num)"] = to_numeric_smart(df[col_clv])
if col_claim_amt is not None:
    df[col_claim_amt + " (num)"] = to_numeric_smart(df[col_claim_amt])
for c in [col_income, col_premium, col_last_claim, col_tenure, col_open_compl, col_policies]:
    if c is not None:
        df[c] = to_numeric_smart(df[c])

CLV = col_clv + " (num)" if col_clv is not None else None
CLAIM = col_claim_amt + " (num)" if col_claim_amt is not None else None

st.sidebar.header("Filtros")
def multi_filter(df, cname, label):
    if cname is None or cname not in df.columns:
        return df
    vals = sorted(df[cname].dropna().astype(str).unique().tolist())
    if len(vals) == 0:
        return df
    sel = st.sidebar.multiselect(label, vals, default=vals)
    if len(sel) > 0:
        return df[df[cname].astype(str).isin(sel)]
    return df

fdf = df.copy()
fdf = multi_filter(fdf, col_channel, "Sales Channel")
fdf = multi_filter(fdf, col_vehicle_class, "Vehicle Class")
fdf = multi_filter(fdf, col_state, "State")
fdf = multi_filter(fdf, col_response, "Response")
fdf = multi_filter(fdf, col_coverage, "Coverage")
fdf = multi_filter(fdf, col_education, "Education")

st.header("1. Visión general: tamaño, centralidad y concentración del valor")
if CLV in fdf.columns:
    clv_vals = pd.to_numeric(fdf[CLV], errors="coerce")
    q25, q50, q75 = qmarks(clv_vals)
    mean = float(np.nanmean(clv_vals))
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Clientes analizados", f"{len(fdf):,}")
    with c2: st.metric("CLV mediano", f"{q50:,.0f}")
    with c3: st.metric("P25 / P75", f"{q25:,.0f} / {q75:,.0f}")
    if col_policies in fdf.columns:
        multi_rate = np.mean(pd.to_numeric(fdf[col_policies], errors="coerce") > 1)
        with c4: st.metric("Multipóliza", f"{multi_rate*100:,.1f} %")

tab1, tab2, tab3, tab4 = st.tabs([
    "Distribución del CLV",
    "Impulsores del valor",
    "Segmentos prioritarios",
    "Evolución del valor"
])

with tab1:
    if CLV in fdf.columns:
        base = fdf[[CLV]].dropna().rename(columns={CLV: "CLV"})
        q25, q50, q75 = qmarks(base["CLV"])
        mean_tab = float(np.nanmean(base["CLV"]))
        hist = alt.Chart(base).mark_bar().encode(
            x=alt.X("CLV:Q", bin=alt.Bin(maxbins=40), title="CLV"),
            y=alt.Y("count()", title="Clientes"),
            tooltip=[alt.Tooltip("count()", title="Clientes")]
        ).properties(height=320, title="Distribución para dimensionar concentración del valor")
        rules = alt.Chart(pd.DataFrame({"x": [q25, q50, q75]})).mark_rule(strokeDash=[6,3], color="red").encode(x="x:Q")
        labels = alt.Chart(pd.DataFrame({"x": [q25, q50, q75], "label": [f"P25 {q25:,.0f}", f"P50 {q50:,.0f}", f"P75 {q75:,.0f}"]})).mark_text(dy=-120, color="red").encode(x="x:Q", y=alt.value(0), text="label:N")
        st.altair_chart(hist + rules + labels, use_container_width=True)
        st.caption(f"Mitad de clientes por debajo de {q50:,.0f}. Cuarto superior por encima de {q75:,.0f}. Media {mean_tab:,.0f}.")

with tab2:
    if CLV in fdf.columns:
        num_candidates = []
        for c in [col_policies, col_income, col_premium, col_last_claim, col_tenure, col_open_compl, CLAIM]:
            if c is not None and c in fdf.columns:
                num_candidates.append(c)
        corr_rows = []
        for c in num_candidates:
            x = pd.to_numeric(fdf[c], errors="coerce")
            y = pd.to_numeric(fdf[CLV], errors="coerce")
            m = ~x.isna() & ~y.isna()
            if m.sum() > 10:
                r = float(np.corrcoef(x[m], y[m])[0,1])
                corr_rows.append({"feature": c, "abs_corr": abs(r), "r": r})
        corr_df = pd.DataFrame(corr_rows).sort_values("abs_corr", ascending=False).head(8) if corr_rows else pd.DataFrame(columns=["feature","abs_corr","r"])
        if not corr_df.empty:
            st.altair_chart(
                alt.Chart(corr_df).mark_bar().encode(
                    x=alt.X("abs_corr:Q", title="|correlación|"),
                    y=alt.Y("feature:N", sort="-x", title="Variable"),
                    tooltip=[alt.Tooltip("r:Q", title="r")]
                ).properties(height=260, title="Ordenar impulsores por señal lineal"),
                use_container_width=True
            )
            best = corr_df.iloc[0]
            disp = alt.Chart(fdf).transform_calculate(
                X=f"toNumber(datum['{best['feature']}'])",
                Y=f"toNumber(datum['{CLV}'])"
            ).mark_circle(size=40, opacity=0.35).encode(
                x=alt.X("X:Q", title=best['feature'], scale=alt.Scale(zero=False)),
                y=alt.Y("Y:Q", title="CLV", scale=alt.Scale(zero=False)),
                tooltip=[best['feature'], CLV]
            ).properties(title=f"Relación CLV vs {best['feature']}")
            trend = disp.transform_regression("X", "Y").mark_line(color="orange")
            st.altair_chart(disp + trend, use_container_width=True)
            st.caption(f"Mayor correlación: {best['feature']} con r = {best['r']:.3f}.")
        else:
            st.info("No se pudieron calcular correlaciones con suficientes datos.")

with tab3:
    def segment_chart(data, dim):
        tmp = data[[dim, CLV]].dropna()
        if tmp.empty:
            return None, 0, 0
        tmp["_count"] = 1
        ag = tmp.groupby(dim, as_index=False).agg(CLV_mediana=(CLV, "median"), n=("_count", "sum"))
        n_total = int(tmp.shape[0])
        min_count = max(30, int(round(0.005 * n_total)))
        ag = ag[ag["n"] >= min_count]
        if ag.shape[0] < 2:
            return None, min_count, 0
        n_levels = ag.shape[0]
        topn = min(6, n_levels)
        ag = ag.sort_values("CLV_mediana", ascending=False).head(topn)
        chart = alt.Chart(ag).mark_bar().encode(
            x=alt.X("CLV_mediana:Q", title="CLV mediano"),
            y=alt.Y(f"{dim}:N", sort="-x", title=dim),
            tooltip=[dim, alt.Tooltip("CLV_mediana:Q", format=","), alt.Tooltip("n:Q", title="n")]
        ).properties(height=32*len(ag))
        txt = f"Umbral mínimo usado: {min_count}. Top N mostrado: {topn}."
        return chart, txt, ag.shape[0]

    cols = []
    if col_channel: cols.append(("Sales Channel", col_channel))
    if col_vehicle_class: cols.append(("Vehicle Class", col_vehicle_class))
    if not cols and col_coverage: cols.append(("Coverage", col_coverage))
    if not cols and col_state: cols.append(("State", col_state))

    if cols:
        cA, cB = st.columns(2) if len(cols) > 1 else (st, st)
        ch1, t1, k1 = segment_chart(fdf, cols[0][1])
        with cA:
            st.subheader(f"{cols[0][0]}: categorías con mayor CLV mediano")
            if ch1 is None:
                st.info("Sin variación suficiente con la muestra actual.")
            else:
                st.altair_chart(ch1, use_container_width=True)
                st.caption(t1)
        if len(cols) > 1:
            ch2, t2, k2 = segment_chart(fdf, cols[1][1])
            with cB:
                st.subheader(f"{cols[1][0]}: categorías con mayor CLV mediano")
                if ch2 is None:
                    st.info("Sin variación suficiente con la muestra actual.")
                else:
                    st.altair_chart(ch2, use_container_width=True)
                    st.caption(t2)
    else:
        st.info("No hay dimensiones categóricas disponibles para segmentar.")

with tab4:
    cols_ok = CLV in fdf.columns and col_tenure in fdf.columns
    if cols_ok:
        aux = fdf[[col_tenure, CLV]].dropna()
        aux["tenure_bin"] = pd.to_numeric(aux[col_tenure], errors="coerce")
        aux["tenure_bin"] = (aux["tenure_bin"] // 6) * 6
        coh = aux.groupby("tenure_bin", as_index=False)[CLV].median().sort_values("tenure_bin")
        st.altair_chart(
            alt.Chart(coh).mark_line(point=True).encode(
                x=alt.X("tenure_bin:Q", title="Meses desde inicio de póliza, bines de 6"),
                y=alt.Y(f"{CLV}:Q", title="CLV mediano", scale=alt.Scale(zero=False)),
                tooltip=["tenure_bin", CLV]
            ).properties(height=320, title="Tendencia del CLV mediano según tenencia"),
            use_container_width=True
        )
        start = coh.iloc[0]; end = coh.iloc[-1]
        st.caption(f"Mediana inicial ≈ {start[CLV]:,.0f}. Mediana hacia {int(end['tenure_bin'])} meses ≈ {end[CLV]:,.0f}.")
    else:
        st.info("Se requiere CLV y Months Since Policy Inception para analizar evolución.")


