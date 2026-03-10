import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import date

st.set_page_config(page_title="DJIA Mean Reversion Backtester", layout="wide")
st.title("Dow Jones Mean Reversion Backtesting Engine")
st.markdown("Hi there! 👋")
st.markdown("")
st.markdown("Does buying beaten-down stocks actually beat the market? This tool lets you find out.")
st.markdown("")
st.markdown("The strategy is based on mean reversion — the idea that stocks tend to deviate from their long-term average in the short run but eventually snap back. It systematically buys the most recent underperformers in the DJIA and rebalances regularly, benchmarked against the DIA ETF as a passive alternative.")
st.markdown("")
st.markdown("Adjust the lookback window, number of stocks, rebalance frequency, and date range to run your own scenarios.")
st.markdown("")
st.markdown("Questions or feedback? Reach out at [claire.lee.bolam@gmail.com](mailto:claire.lee.bolam@gmail.com) 🙂")

st.sidebar.header("Strategy Parameters")

start_date = st.sidebar.date_input("Start Date", value=date(2016, 1, 1))
end_date   = st.sidebar.date_input("End Date",  value=date.today())

lookback   = st.sidebar.slider("Lookback Window (days)", min_value=5, max_value=60, value=20,
                                help="Rolling window to compute mean-reversion signal")
top_n      = st.sidebar.slider("Top N Underperformers to Buy", min_value=3, max_value=15, value=5,
                                help="Number of most-underperforming stocks to go long each period")
initial_capital = st.sidebar.number_input("Initial Capital ($)", value=100000, step=10000)

rebalance_freq = st.sidebar.selectbox("Rebalance Frequency", ["Daily", "Weekly", "Monthly"])

DJIA_TICKERS = [
    "AAPL","AMGN","AXP","BA","CAT","CRM","CSCO","CVX","DIS","DOW",
    "GS","HD","HON","IBM","INTC","JNJ","JPM","KO","MCD","MMM",
    "MRK","MSFT","NKE","PG","TRV","UNH","V","VZ","WBA","WMT"
]

with st.spinner("Loading backtest results..."):

    raw = yf.download(DJIA_TICKERS + ["DIA"], start=start_date, end=end_date,
                      auto_adjust=True, progress=False)["Close"]
    raw.dropna(how="all", inplace=True)

    dia    = raw["DIA"]
    stocks = raw[DJIA_TICKERS].dropna(axis=1, thresh=int(len(raw)*0.8))

    roll_mean = stocks.rolling(lookback).mean()
    roll_std  = stocks.rolling(lookback).std()
    zscore    = (stocks - roll_mean) / roll_std

    if rebalance_freq == "Weekly":
        rebal_dates = set(stocks.resample("W").last().index)
    elif rebalance_freq == "Monthly":
        rebal_dates = set(stocks.resample("ME").last().index)
    else:
        rebal_dates = set(stocks.index)

    port_values = [initial_capital]
    dates_out   = [stocks.index[lookback]]

    weights = pd.Series(0.0, index=stocks.columns)
    daily_ret = stocks.pct_change()

    for i in range(lookback + 1, len(stocks)):
        dt = stocks.index[i]
        if dt in rebal_dates:
            z = zscore.iloc[i - 1]
            bottom = z.nsmallest(top_n).index
            weights = pd.Series(0.0, index=stocks.columns)
            weights[bottom] = 1.0 / top_n
        port_ret = (weights * daily_ret.iloc[i]).sum()
        port_values.append(port_values[-1] * (1 + port_ret))
        dates_out.append(dt)

    strat = pd.Series(port_values, index=dates_out)
    dia_aligned = dia.reindex(strat.index).ffill()
    benchmark   = (dia_aligned / dia_aligned.iloc[0]) * initial_capital

    def metrics(series):
        rets = series.pct_change().dropna()
        n_years = len(rets) / 252
        cagr    = (series.iloc[-1] / series.iloc[0]) ** (1 / n_years) - 1
        vol     = rets.std() * np.sqrt(252)
        sharpe  = (rets.mean() * 252) / (rets.std() * np.sqrt(252))
        roll_max = series.cummax()
        drawdown = ((series - roll_max) / roll_max).min()
        return {"CAGR": f"{cagr:.2%}", "Volatility": f"{vol:.2%}",
                "Sharpe": f"{sharpe:.2f}", "Max Drawdown": f"{drawdown:.2%}"}

    s_metrics = metrics(strat)
    b_metrics = metrics(benchmark)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Mean Reversion Strategy")
        st.metric("CAGR",         s_metrics["CAGR"])
        st.metric("Sharpe Ratio", s_metrics["Sharpe"])
        st.metric("Volatility",   s_metrics["Volatility"])
        st.metric("Max Drawdown", s_metrics["Max Drawdown"])
    with col2:
        st.subheader("DIA ETF Benchmark")
        st.metric("CAGR",         b_metrics["CAGR"])
        st.metric("Sharpe Ratio", b_metrics["Sharpe"])
        st.metric("Volatility",   b_metrics["Volatility"])
        st.metric("Max Drawdown", b_metrics["Max Drawdown"])

    st.subheader("Cumulative Portfolio Value")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=strat.index,     y=strat,     name="Mean Reversion", line=dict(color="#0366d6", width=2)))
    fig.add_trace(go.Scatter(x=benchmark.index, y=benchmark, name="DIA ETF",        line=dict(color="#f0883e", width=2, dash="dash")))
    fig.update_layout(xaxis_title="Date", yaxis_title="Portfolio Value ($)",
                      hovermode="x unified", template="plotly_white", height=500)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Drawdown")
    strat_dd = (strat - strat.cummax()) / strat.cummax()
    bench_dd = (benchmark - benchmark.cummax()) / benchmark.cummax()
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=strat_dd.index, y=strat_dd, name="Mean Reversion",
                              fill="tozeroy", line=dict(color="#0366d6")))
    fig2.add_trace(go.Scatter(x=bench_dd.index, y=bench_dd, name="DIA ETF",
                              fill="tozeroy", line=dict(color="#f0883e")))
    fig2.update_layout(yaxis_tickformat=".0%", template="plotly_white", height=300)
    st.plotly_chart(fig2, use_container_width=True)

    results_df = pd.DataFrame({"Mean Reversion": strat, "DIA ETF": benchmark})
    st.download_button("Download Results CSV", results_df.to_csv().encode(),
                       "backtest_results.csv", "text/csv")

st.sidebar.markdown("---")
st.sidebar.caption("Adjust any parameter above to instantly re-run the backtest.")
