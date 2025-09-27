from pathlib import Path
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

st.set_page_config(page_title="Análisis ejecutivo de CLV para priorización comercial", layout="wide")
st.title("Análisis ejecutivo de CLV para priorización comercial")
st.caption("Propósito: identificar impulsores y segmentos de alto valor para orientar marketing, ventas y retención.")
alt.themes.enable("default")

@st.cache_data
def read_csv_semicolon(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, delimiter=";", dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def detect_col(df: pd.DataFrame, needles):
    cols_l = {c.lower(): c for c in df.columns}
    for n in needles:
        for low, orig in cols_l.items():
            if n in low:
                return orig
    return None

def to_numeric_smart(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip()
    s1 = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s1, errors="coerce")

def qmarks(v: pd.Series):
    x = pd.to_numeric(v, errors="coerce")
    return [np.nanpercentile(x, 25), np.nanpercentile(x, 50), np.nanpercentile(x, 75)]

data_path = "CLV.csv"
if not Path(data_path).exists():
    st.error("No se encontró CLV.csv en la raíz del repositorio.")
    st.stop()

raw = read_csv_semicolon(data_path)

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
if col_clv is None:
    st.error("No se reconoció la columna de CLV.")
    st.stop()

df[col_clv + "_num"] = to_numeric_smart(df[col_clv])
if col_claim_amt: df[col_claim_amt + "_num"] = to_numeric_smart(df[col_claim_amt])
for c in [col_income, col_premium, col_last_claim, col_tenure, col_open_compl, col_policies]:
    if c: df[c] = to_numeric_smart(df[c])

CLV = col_clv + "_num"
CLAIM = col_claim_amt + "_num" if col_claim_amt else None

st.sidebar.header("Filtros")
def multi_filter(dfin: pd.DataFrame, cname: str, label: str):
    if not cname or cname not in dfin.columns:
        return dfin
    vals = sorted(dfin[cname].dropna().astype(str).unique().tolist())
    if not vals:
        return dfin
    sel = st.sidebar.multiselect(label, vals, default=vals)
    if sel:
        return dfin[dfin[cname].astype(str).isin(sel)]
    return dfin

fdf = df.copy()
fdf = multi_filter(fdf, col_channel, "Sales Channel")
fdf = multi_filter(fdf, col_vehicle_class, "Vehicle Class")
fdf = multi_filter(fdf, col_state, "State")
fdf = multi_filter(fdf, col_response, "Response")
fdf = multi_filter(fdf, col_coverage, "Coverage")
fdf = multi_filter(fdf, col_education, "Education")

st.header("1. Visión general: tamaño, centralidad y concentración del valor")
clv_vals = pd.to_numeric(fdf[CLV], errors="coerce")
q25, q50, q75 = qmarks(clv_vals)
mean_val = float(np.nanmean(clv_vals)) if clv_vals.notna().any() else np.nan
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
    base = fdf[[CLV]].dropna().rename(columns={CLV: "CLV"})
    q25, q50, q75 = qmarks(base["CLV"])
    mean_tab = float(np.nanmean(base["CLV"])) if not base.empty else np.nan
    hist = alt.Chart(base).mark_bar().encode(
        x=alt.X("CLV:Q", bin=alt.Bin(maxbins=40), title="CLV"),
        y=alt.Y("count()", title="Clientes"),
        tooltip=[alt.Tooltip("count()", title="Clientes")]
    ).properties(height=320, title="Distribución del CLV")
    rules = alt.Chart(pd.DataFrame({"x": [q25, q50, q75]})).mark_rule(strokeDash=[6,3], color="red").encode(x="x:Q")
    labels = alt.Chart(pd.DataFrame({"x": [q25, q50, q75], "label": [f"P25 {q25:,.0f}", f"P50 {q50:,.0f}", f"P75 {q75:,.0f}"]})).mark_text(dy=-120, color="red").encode(x="x:Q", y=alt.value(0), text="label:N")
    st.altair_chart(hist + rules + labels, use_container_width=True)
    st.caption(f"Mitad de clientes por debajo de {q50:,.0f}. Cuarto superior por encima de {q75:,.0f}. Media {mean_tab:,.0f}.")

with tab2:
    num_candidates = [c for c in [col_policies, col_income, col_premium, col_last_claim, col_tenure, col_open_compl, CLAIM] if c and c in fdf.columns]
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
            ).properties(height=260, title="Impulsores ordenados por señal lineal"),
            use_container_width=True
        )
        best = corr_df.iloc[0]
        bx = pd.to_numeric(fdf[best["feature"]], errors="coerce")
        by = pd.to_numeric(fdf[CLV], errors="coerce")
        m = ~bx.isna() & ~by.isna()
        if m.sum() > 2:
            x_min, x_max = float(bx[m].min()), float(bx[m].max())
            slope, intercept = np.polyfit(bx[m], by[m], 1)
            grid = pd.DataFrame({"X": np.linspace(x_min, x_max, 50)})
            grid["Yhat"] = slope * grid["X"] + intercept
            disp = alt.Chart(pd.DataFrame({"X": bx[m], "Y": by[m]})).mark_circle(size=40, opacity=0.35).encode(
                x=alt.X("X:Q", title=best["feature"], scale=alt.Scale(zero=False)),
                y=alt.Y("Y:Q", title="CLV", scale=alt.Scale(zero=False)),
                tooltip=[alt.Tooltip("X:Q", title=best["feature"]), alt.Tooltip("Y:Q", title="CLV")]
            ).properties(title=f"Relación CLV vs {best['feature']}")
            trend = alt.Chart(grid).mark_line().encode(x="X:Q", y="Yhat:Q")
            st.altair_chart(disp + trend, use_container_width=True)
        st.caption(f"Mayor correlación: {best['feature']} con r = {best['r']:.3f}.")
    else:
        st.info("No se pudieron calcular correlaciones con suficientes datos.")

with tab3:
    def segment_view(data: pd.DataFrame, dim: str):
        tmp = data[[dim, CLV]].dropna()
        if tmp.empty:
            return None, "Sin datos", 0
        tmp["_count"] = 1
        ag = tmp.groupby(dim, as_index=False).agg(CLV_mediana=(CLV, "median"), n=("_count", "sum"))
        n_total = int(tmp.shape[0])
        min_count = max(30, int(round(0.005 * n_total)))
        ag = ag[ag["n"] >= min_count]
        if ag.shape[0] < 2:
            return None, "Tras el umbral mínimo solo queda una categoría", 0
        topn = min(6, ag.shape[0])
        ag = ag.sort_values("CLV_mediana", ascending=False).head(topn)
        chart = alt.Chart(ag).mark_bar().encode(
            x=alt.X("CLV_mediana:Q", title="CLV mediano"),
            y=alt.Y(f"{dim}:N", sort="-x", title=dim),
            tooltip=[dim, alt.Tooltip("CLV_mediana:Q", format=","), alt.Tooltip("n:Q", title="n")]
        ).properties(height=32*len(ag))
        info = f"Umbral mínimo usado: {min_count}. Top N mostrado: {topn}."
        return chart, info, ag.shape[0]

    dims = [d for d in [col_channel, col_vehicle_class, col_coverage, col_education, col_state] if d]
    if not dims:
        st.info("No hay dimensiones categóricas disponibles para segmentar.")
    else:
        if len(dims) >= 2:
            cA, cB = st.columns(2)
            with cA:
                st.subheader("Sales Channel: categorías con mayor CLV mediano" if col_channel in dims else f"{dims[0]}: categorías con mayor CLV mediano")
                ch1, t1, _ = segment_view(fdf, dims[0])
                if ch1 is None:
                    st.info("Sin variación suficiente con la muestra actual.")
                else:
                    st.altair_chart(ch1, use_container_width=True)
                    st.caption(t1)
            with cB:
                st.subheader("Vehicle Class: categorías con mayor CLV mediano" if col_vehicle_class in dims else f"{dims[1]}: categorías con mayor CLV mediano")
                ch2, t2, _ = segment_view(fdf, dims[1])
                if ch2 is None:
                    st.info("Sin variación suficiente con la muestra actual.")
                else:
                    st.altair_chart(ch2, use_container_width=True)
                    st.caption(t2)
        else:
            container = st.container()
            with container:
                st.subheader(f"{dims[0]}: categorías con mayor CLV mediano")
                ch, t, _ = segment_view(fdf, dims[0])
                if ch is None:
                    st.info("Sin variación suficiente con la muestra actual.")
                else:
                    st.altair_chart(ch, use_container_width=True)
                    st.caption(t)

with tab4:
    if col_tenure in fdf.columns:
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
        st.info("Se requiere Months Since Policy Inception para analizar evolución.")

