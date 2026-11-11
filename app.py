# -*- coding: utf-8 -*-
import time

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_URL = "https://ecshweb.pchome.com.tw/search/v3.3/all/results"
HEADERS = {"User-Agent": "Mozilla/5.0"}

st.set_page_config(page_title="PChome 商品價格分析", layout="wide")
st.title("PChome 商品價格分析")


@st.cache_data(show_spinner=False, ttl=600)
def fetch_page(keyword: str, page: int) -> list:
    """抓取單一頁的商品資料"""
    params = {"q": keyword, "page": page, "sort": "sale/dc"}
    resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json().get("prods", [])


def crawl(keyword: str, pages: int, delay: float) -> pd.DataFrame:
    frames = []
    progress = st.progress(0.0, text="開始爬取…")
    for i in range(1, pages + 1):
        progress.progress((i - 1) / pages, text=f"爬取第 {i}/{pages} 頁…")
        try:
            prods = fetch_page(keyword, i)
        except Exception as e:
            st.warning(f"第 {i} 頁失敗：{e}")
            break
        if not prods:
            st.info(f"第 {i} 頁沒有資料，停止爬取。")
            break
        frames.append(pd.DataFrame(prods))
        if i < pages:
            time.sleep(delay)
    progress.progress(1.0, text="完成")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ---------- 側邊欄輸入 ----------
with st.sidebar:
    keyword = st.text_input("產品名稱", value="行動電源")
    pages = st.number_input("爬取頁數", min_value=1, max_value=20, value=2, step=1)
    delay = st.slider("每頁間隔秒數", 0.0, 10.0, 2.0, 0.5)
    top_n_line = st.slider("折線圖顯示筆數", 10, 200, 70, 10)
    top_n_sun = st.slider("旭日圖顯示商品數", 10, 100, 40, 10)
    run = st.button("開始爬取", type="primary")

if run:
    if not keyword.strip():
        st.error("請輸入產品名稱")
        st.stop()
    with st.spinner("爬取中…"):
        data = crawl(keyword.strip(), int(pages), float(delay))
    st.session_state["data"] = data
    st.session_state["keyword"] = keyword.strip()

data = st.session_state.get("data")
if data is None:
    st.info("請在左側輸入產品名稱與頁數，然後按「開始爬取」。")
    st.stop()
if data.empty or not {"name", "price"}.issubset(data.columns):
    st.error("沒有取得有效資料（或回傳欄位不含 name / price）。")
    st.stop()

kw = st.session_state["keyword"]
df = data[["name", "price"]].copy()
df["price"] = pd.to_numeric(df["price"], errors="coerce")
df = df.dropna(subset=["price"]).reset_index(drop=True)
if df.empty:
    st.error("price 欄位沒有可用數值。")
    st.stop()

# ---------- 統計 ----------
mean_p, max_p, min_p = df["price"].mean(), df["price"].max(), df["price"].min()
c1, c2, c3, c4 = st.columns(4)
c1.metric("商品數", len(df))
c2.metric("平均價", f"{mean_p:,.0f}")
c3.metric("最高價", f"{max_p:,.0f}")
c4.metric("最低價", f"{min_p:,.0f}")

# 價格區間（供圓餅圖、旭日圖使用）
df["價格區間"] = pd.cut(df["price"], bins=5, precision=0).astype(str)

tab1, tab2, tab3, tab4 = st.tabs(["折線圖", "圓餅圖", "旭日圖", "資料表"])

with tab1:
    d = df.head(top_n_line).reset_index().rename(columns={"index": "序號"})
    fig = px.line(d, x="序號", y="price", hover_name="name", markers=True,
                  title=f"PChome 電商網站上「{kw}」售價")
    fig.add_hline(y=mean_p, line_dash="dash", line_color="red",
                  annotation_text=f"平均 {mean_p:,.0f}")
    fig.update_layout(xaxis_title="商品序號", yaxis_title="價格")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    pie = df["價格區間"].value_counts().reset_index()
    pie.columns = ["價格區間", "商品數"]
    fig = px.pie(pie, names="價格區間", values="商品數", title=f"「{kw}」價格區間占比")
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    s = df.head(top_n_sun).copy()
    s["商品"] = s["name"].str.slice(0, 20)
    # 同名商品加上序號避免旭日圖節點重複
    s["商品"] = s["商品"] + " #" + s.index.astype(str)
    fig = px.sunburst(s, path=["價格區間", "商品"], values="price",
                      title=f"「{kw}」價格區間 → 商品")
    st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.dataframe(df[["name", "price"]], use_container_width=True)
    csv = data.to_csv(index=False).encode("utf-8-sig")
    st.download_button("下載完整 CSV", csv,
                       file_name=f"{time.strftime('%Y%m%d')}_PCHOME_{kw}.csv",
                       mime="text/csv")
